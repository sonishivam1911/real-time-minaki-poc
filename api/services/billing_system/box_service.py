"""
Storage Box Service - Business Logic Layer
"""
from typing import List, Optional


class BoxService:
    """Service for managing storage boxes"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    async def create_box(self, box_data: dict) -> dict:
        """Create a new storage box"""
        shelf_id = box_data.get('shelf_id')
        box_code = box_data.get('box_code')
        box_label = box_data.get('box_label')
        length_cm = box_data.get('length_cm')
        width_cm = box_data.get('width_cm')
        height_cm = box_data.get('height_cm')
        color_code = box_data.get('color_code')
        description = box_data.get('description')
        is_active = box_data.get('is_active', True)
        metadata = box_data.get('metadata')
        
        # Helper function to convert Python None to SQL NULL string
        def sql_value(value):
            if value is None:
                return 'NULL'
            elif isinstance(value, bool):
                return str(value).lower()
            elif isinstance(value, (int, float)):
                return str(value)
            else:
                # Escape single quotes in strings
                return f"'{str(value).replace(chr(39), chr(39)+chr(39))}'"
        
        query = f"""
            INSERT INTO billing_system_storage_boxes 
            (shelf_id, box_code, box_label, length_cm, width_cm, height_cm, 
             color_code, description, is_active, metadata)
            VALUES ({sql_value(shelf_id)}, {sql_value(box_code)}, {sql_value(box_label)}, {sql_value(length_cm)}, 
                    {sql_value(width_cm)}, {sql_value(height_cm)}, {sql_value(color_code)},
                    {sql_value(description)}, {sql_value(is_active)}, {sql_value(metadata)})
            RETURNING *
        """
        result = self.db.execute_query_new(query, return_data=True)
        records = self.db._df_to_list_of_dicts(result) if hasattr(result, 'to_dict') else result
        return records[0] if records else None
    
    async def get_box_by_id(self, box_id: int) -> Optional[dict]:
        """Get box with full location details"""
        query = f"""
            SELECT 
                sb.*,
                ss.shelf_code,
                ss.shelf_name,
                sl.location_name,
                sl.location_code,
                sl.id as location_id,
                ss.id as shelf_id
            FROM billing_system_storage_boxes sb
            JOIN billing_system_storage_shelves ss ON sb.shelf_id = ss.id
            JOIN billing_system_storage_locations sl ON ss.location_id = sl.id
            WHERE sb.id = {box_id}
        """
        result = self.db.execute_query_new(query, return_data=True)
        records = self.db._df_to_list_of_dicts(result) if hasattr(result, 'to_dict') else result
        return records[0] if records else None
    
    async def get_box_by_qr_code(self, box_code: str) -> Optional[dict]:
        """Get box by QR code scan"""
        query = f"""
            SELECT 
                sb.*,
                ss.shelf_code,
                ss.shelf_name,
                sl.location_name,
                sl.location_code,
                sl.id as location_id,
                ss.id as shelf_id
            FROM billing_system_storage_boxes sb
            JOIN billing_system_storage_shelves ss ON sb.shelf_id = ss.id
            JOIN billing_system_storage_locations sl ON ss.location_id = sl.id
            WHERE sb.box_code = '{box_code}'
        """
        result = self.db.execute_query_new(query, return_data=True)
        records = self.db._df_to_list_of_dicts(result) if hasattr(result, 'to_dict') else result
        return records[0] if records else None
    
    async def get_boxes_by_shelf(self, shelf_id: int, active_only: bool = True) -> List[dict]:
        """Get all boxes on a shelf"""
        where_clause = "AND sb.is_active = TRUE" if active_only else ""
        query = f"""
            SELECT 
                sb.*,
                (SELECT COUNT(*) FROM billing_system_product_locations 
                 WHERE box_id = sb.id) as product_count,
                (SELECT COALESCE(SUM(quantity), 0) FROM billing_system_product_locations 
                 WHERE box_id = sb.id) as total_quantity
            FROM billing_system_storage_boxes sb
            WHERE sb.shelf_id = :shelf_id
            {where_clause}
            ORDER BY sb.box_code
        """
        result = self.db.execute_query(query, {"shelf_id": shelf_id}, return_data=True)
        return result if isinstance(result, list) else (result.to_dict('records') if hasattr(result, 'to_dict') else [])
    
    async def get_box_contents(self, box_id: int) -> dict:
        """Get all products in a box (for QR code scan)"""
        # Get box details
        box = await self.get_box_by_id(box_id)
        if not box:
            return None
        
        # Get products in box
        products_query = f"""
            SELECT * FROM billing_system_product_locations
            WHERE box_id = :box_id
            ORDER BY product_name
        """
        products_result = self.db.execute_query(products_query, {"box_id": box_id}, return_data=True)
        products = self.db._df_to_list_of_dicts(products_result) if hasattr(products_result, 'to_dict') else products_result
        
        return {
            "box": box,
            "products": products or [],
            "total_items": len(products) if products else 0,
            "total_quantity": sum(p.get('quantity', 0) for p in (products or []))
        }
    
    async def get_box_contents_by_code(self, box_code: str) -> dict:
        """Get all products in a box by QR code"""
        # Get box details by code
        box = await self.get_box_by_qr_code(box_code)
        if not box:
            return None
        
        box_id = box['id']
        
        # Get products in box
        products_query = f"""
            SELECT * FROM billing_system_product_locations
            WHERE box_id = :box_id
            ORDER BY product_name
        """
        products_result = self.db.execute_query(products_query, {"box_id": box_id}, return_data=True)
        products = self.db._df_to_list_of_dicts(products_result) if hasattr(products_result, 'to_dict') else products_result
        
        return {
            "box_id": box_id,
            "box_code": box['box_code'],
            "box_label": box.get('box_label'),
            "shelf_code": box['shelf_code'],
            "location_name": box['location_name'],
            "products": products or [],
            "total_items": len(products) if products else 0,
            "total_quantity": sum(p.get('quantity', 0) for p in (products or []))
        }
    
    async def update_box(self, box_id: int, update_data: dict) -> Optional[dict]:
        """Update box details"""
        set_clauses = []
        
        for key, value in update_data.items():
            if value is not None:
                if isinstance(value, bool):
                    set_clauses.append(f"{key} = {str(value).lower()}")
                elif isinstance(value, (int, float)):
                    set_clauses.append(f"{key} = {value}")
                else:
                    # Escape single quotes in strings
                    escaped_value = str(value).replace(chr(39), chr(39)+chr(39))
                    set_clauses.append(f"{key} = '{escaped_value}'")
        
        if not set_clauses:
            return await self.get_box_by_id(box_id)
        
        query = f"""
            UPDATE billing_system_storage_boxes
            SET {', '.join(set_clauses)}, updated_at = NOW()
            WHERE id = {box_id}
            RETURNING *
        """
        result = self.db.execute_query_new(query, return_data=True)
        records = self.db._df_to_list_of_dicts(result) if hasattr(result, 'to_dict') else result
        return records[0] if records else None
    
    async def move_box_to_shelf(self, box_id: int, new_shelf_id: int, moved_by: str, 
                                reason: str = None, notes: str = None) -> dict:
        """Move a box to a different shelf"""
        # Get current box location
        current_box = await self.get_box_by_id(box_id)
        if not current_box:
            raise ValueError(f"Box {box_id} not found")
        
        old_shelf_id = current_box['shelf_id']
        
        # Update box location
        update_query = f"""
            UPDATE billing_system_storage_boxes
            SET shelf_id = :new_shelf_id, updated_at = NOW()
            WHERE id = :box_id
            RETURNING *
        """
        updated_result = self.db.execute_query(update_query, {
            "new_shelf_id": new_shelf_id,
            "box_id": box_id
        }, return_data=True)
        updated_box = self.db._df_to_list_of_dicts(updated_result) if hasattr(updated_result, 'to_dict') else updated_result
        
        # Record movement in history
        movement_query = f"""
            INSERT INTO billing_system_box_movements
            (box_id, from_shelf_id, to_shelf_id, moved_by, reason, notes)
            VALUES (:box_id, :old_shelf_id, :new_shelf_id, 
                    :moved_by, :reason, :notes)
            RETURNING *
        """
        movement_result = self.db.execute_query(movement_query, {
            "box_id": box_id,
            "old_shelf_id": old_shelf_id,
            "new_shelf_id": new_shelf_id,
            "moved_by": moved_by,
            "reason": reason,
            "notes": notes
        }, return_data=True)
        movement = self.db._df_to_list_of_dicts(movement_result) if hasattr(movement_result, 'to_dict') else movement_result
        
        return {
            "updated_box": updated_box[0] if updated_box else None,
            "movement_record": movement[0] if movement else None
        }
    
    async def delete_box(self, box_id: int) -> bool:
        """Soft delete box"""
        # Check if box has products
        check_query = f"""
            SELECT COUNT(*) as count FROM billing_system_product_locations
            WHERE box_id = :box_id
        """
        result = self.db.execute_query(check_query, {"box_id": box_id}, return_data=True)
        count = result[0]['count'] if isinstance(result, list) and result else (result['count'].iloc[0] if hasattr(result, 'iloc') else 0)
        if count > 0:
            raise ValueError("Cannot delete box with products. Move products first.")
        
        query = f"""
            UPDATE billing_system_storage_boxes
            SET is_active = FALSE, updated_at = NOW()
            WHERE id = :box_id
            RETURNING id
        """
        result = self.db.execute_query(query, {"box_id": box_id}, return_data=True)
        return bool(result if isinstance(result, list) and result else (len(result) > 0 if hasattr(result, '__len__') else False))
    
    async def get_box_movement_history(self, box_id: int, limit: int = 50) -> List[dict]:
        """Get movement history for a box"""
        query = f"""
            SELECT 
                bm.*,
                ss_from.shelf_code as from_shelf_code,
                ss_to.shelf_code as to_shelf_code,
                sl_from.location_name as from_location,
                sl_to.location_name as to_location
            FROM billing_system_box_movements bm
            LEFT JOIN billing_system_storage_shelves ss_from ON bm.from_shelf_id = ss_from.id
            LEFT JOIN billing_system_storage_shelves ss_to ON bm.to_shelf_id = ss_to.id
            LEFT JOIN billing_system_storage_locations sl_from ON ss_from.location_id = sl_from.id
            LEFT JOIN billing_system_storage_locations sl_to ON ss_to.location_id = sl_to.id
            WHERE bm.box_id = :box_id
            ORDER BY bm.movement_date DESC
            LIMIT :limit
        """
        result = self.db.execute_query(query, {"box_id": box_id, "limit": limit}, return_data=True)
        records = self.db._df_to_list_of_dicts(result) if hasattr(result, 'to_dict') else result
        return records or []