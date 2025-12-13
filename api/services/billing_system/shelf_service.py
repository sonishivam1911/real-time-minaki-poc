"""
Storage Shelf Service - Business Logic Layer
Handles CRUD operations for storage shelves
"""
from typing import List, Optional
from datetime import datetime


class ShelfService:
    """Service for managing storage shelves"""
    
    def __init__(self, db_connection):
        """
        Initialize with database connection
        Args:
            db_connection: Your database CRUD class instance
        """
        self.db = db_connection
    
    async def create_shelf(self, shelf_data: dict) -> dict:
        """Create a new shelf"""
        # Extract only the fields we need for insertion
        location_id = shelf_data.get('location_id')
        shelf_name = shelf_data.get('shelf_name')
        shelf_code = shelf_data.get('shelf_code')
        is_active = shelf_data.get('is_active', True)
        metadata = shelf_data.get('metadata', None)
        
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
            INSERT INTO billing_system_storage_shelves 
            (location_id, shelf_name, shelf_code, is_active, metadata)
            VALUES ({sql_value(location_id)}, {sql_value(shelf_name)}, {sql_value(shelf_code)}, {sql_value(is_active)}, {sql_value(metadata)})
            RETURNING *
        """
        result = self.db.execute_query_new(query, return_data=True)
        records = self.db._df_to_list_of_dicts(result) if hasattr(result, 'to_dict') else result
        return records[0] if records else None
    
    async def bulk_create_shelves(self, shelves_data: List[dict]) -> List[dict]:
        """Create multiple shelves at once"""
        results = []
        for shelf_data in shelves_data:
            result = await self.create_shelf(shelf_data)
            if result:
                results.append(result)
        return results
    
    async def get_shelf_by_id(self, shelf_id: int) -> Optional[dict]:
        """Get shelf by ID with location details"""
        query = f"""
            SELECT 
                ss.*,
                sl.location_name,
                sl.location_code,
                sl.id as location_id
            FROM billing_system_storage_shelves ss
            JOIN billing_system_storage_locations sl ON ss.location_id = sl.id
            WHERE ss.id = :shelf_id
        """
        result = self.db.execute_query(query, {"shelf_id": shelf_id}, return_data=True)
        records = self.db._df_to_list_of_dicts(result) if hasattr(result, 'to_dict') else result
        return records[0] if records else None
    
    async def get_shelves_by_location(self, location_id: int, active_only: bool = True) -> List[dict]:
        """Get all shelves in a location"""
        where_clause = "AND ss.is_active = TRUE" if active_only else ""
        query = f"""
            SELECT 
                ss.*,
                sl.location_name,
                sl.location_code,
                (SELECT COUNT(*) FROM billing_system_storage_boxes 
                 WHERE shelf_id = ss.id) as box_count,
                (SELECT COALESCE(SUM(quantity), 0) FROM billing_system_product_locations pl
                 JOIN billing_system_storage_boxes sb ON pl.box_id = sb.id
                 WHERE sb.shelf_id = ss.id) as total_quantity
            FROM billing_system_storage_shelves ss
            JOIN billing_system_storage_locations sl ON ss.location_id = sl.id
            WHERE ss.location_id = :location_id
            {where_clause}
            ORDER BY ss.shelf_code
        """
        result = self.db.execute_query(query, {"location_id": location_id}, return_data=True)
        return result if isinstance(result, list) else (result.to_dict('records') if hasattr(result, 'to_dict') else [])
    
    async def get_shelf_grid_layout(self, location_id: int) -> List[dict]:
        """Get shelf grid layout for UI visualization"""
        query = f"""
            SELECT 
                ss.id,
                ss.shelf_code,
                ss.shelf_name,
                ss.visual_x,
                ss.visual_y,
                COUNT(DISTINCT sb.id) as box_count,
                COALESCE(SUM(pl.quantity), 0) as total_quantity
            FROM billing_system_storage_shelves ss
            LEFT JOIN billing_system_storage_boxes sb ON ss.id = sb.shelf_id AND sb.is_active = TRUE
            LEFT JOIN billing_system_product_locations pl ON sb.id = pl.box_id
            WHERE ss.location_id = :location_id
            AND ss.is_active = TRUE
            GROUP BY ss.id, ss.shelf_code, ss.shelf_name, ss.visual_x, ss.visual_y
            ORDER BY ss.shelf_code
        """
        result = self.db.execute_query(query, {"location_id": location_id}, return_data=True)
        return result if isinstance(result, list) else (result.to_dict('records') if hasattr(result, 'to_dict') else [])
    
    async def update_shelf(self, shelf_id: int, update_data: dict) -> Optional[dict]:
        """Update shelf details"""
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
            return await self.get_shelf_by_id(shelf_id)
        
        query = f"""
            UPDATE billing_system_storage_shelves
            SET {', '.join(set_clauses)}, updated_at = NOW()
            WHERE id = :shelf_id
            RETURNING *
        """
        result = self.db.execute_query(query, {"shelf_id": shelf_id}, return_data=True)
        records = self.db._df_to_list_of_dicts(result) if hasattr(result, 'to_dict') else result
        return records[0] if records else None
    
    async def update_shelf_position(self, shelf_id: int, visual_x: float, visual_y: float) -> Optional[dict]:
        """Update shelf visual position for drag-drop UI"""
        query = f"""
            UPDATE billing_system_storage_shelves
            SET visual_x = :visual_x, visual_y = :visual_y, updated_at = NOW()
            WHERE id = :shelf_id
            RETURNING *
        """
        result = self.db.execute_query(query, {
            "shelf_id": shelf_id,
            "visual_x": visual_x,
            "visual_y": visual_y
        }, return_data=True)
        records = self.db._df_to_list_of_dicts(result) if hasattr(result, 'to_dict') else result
        return records[0] if records else None
    
    async def delete_shelf(self, shelf_id: int) -> bool:
        """Soft delete shelf"""
        # Check if shelf has boxes
        check_query = f"""
            SELECT COUNT(*) as count FROM billing_system_storage_boxes
            WHERE shelf_id = :shelf_id
        """
        result = self.db.execute_query(check_query, {"shelf_id": shelf_id}, return_data=True)
        count = result[0]['count'] if isinstance(result, list) and result else (result['count'].iloc[0] if hasattr(result, 'iloc') else 0)
        if count > 0:
            raise ValueError("Cannot delete shelf with boxes. Move boxes first.")
        
        query = f"""
            UPDATE billing_system_storage_shelves
            SET is_active = FALSE, updated_at = NOW()
            WHERE id = :shelf_id
            RETURNING id
        """
        result = self.db.execute_query(query, {"shelf_id": shelf_id}, return_data=True)
        return bool(result if isinstance(result, list) and result else (len(result) > 0 if hasattr(result, '__len__') else False))