"""
Product Location Service - Core Inventory Tracking
Handles both real_jewelry and zakya_product types
"""
from typing import List, Optional, Dict
from datetime import datetime


class ProductLocationService:
    """Service for managing product locations and movements"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    async def add_product_to_box(self, product_data: dict, moved_by: str) -> dict:
        """
        Add a product to a box
        Args:
            product_data: Product location details
            moved_by: User performing the action
        Returns:
            Created product location record
        """
        # Check if product already exists in this box
        check_query = f"""
            SELECT * FROM billing_system_product_locations
            WHERE box_id = :box_id 
            AND product_type = :product_type 
            AND product_id = :product_id
        """
        existing_result = self.db.execute_query(check_query, {
            "box_id": product_data['box_id'],
            "product_type": product_data['product_type'],
            "product_id": product_data['product_id']
        }, return_data=True)
        existing = existing_result if isinstance(existing_result, list) else (existing_result.to_dict('records') if hasattr(existing_result, 'to_dict') else [])
        
        if existing:
            # Update quantity instead of creating new record
            return await self.update_product_quantity(
                existing[0]['id'],
                existing[0]['quantity'] + product_data['quantity'],
                moved_by,
                "Added to existing stock"
            )
        
        # Create new product location
        insert_query = f"""
            INSERT INTO billing_system_product_locations
            (box_id, product_type, product_id, product_name, sku, quantity,
             serial_numbers, metal_weight_g, purity_k, zakya_metadata,
             last_counted_by)
            VALUES (:box_id, :product_type, :product_id, :product_name,
                    :sku, :quantity, :serial_numbers, :metal_weight_g,
                    :purity_k, :zakya_metadata, :moved_by)
            RETURNING *
        """
        params = {**product_data, "moved_by": moved_by}
        result = self.db.execute_query(insert_query, params, return_data=True)
        result_list = result if isinstance(result, list) else (result.to_dict('records') if hasattr(result, 'to_dict') else [])
        
        if result_list:
            # Record movement history
            await self._record_movement(
                product_type=product_data['product_type'],
                product_id=product_data['product_id'],
                sku=product_data.get('sku'),
                product_name=product_data['product_name'],
                movement_type='add',
                quantity_moved=product_data['quantity'],
                to_box_id=product_data['box_id'],
                moved_by=moved_by,
                reason="Initial stock addition",
                serial_numbers=product_data.get('serial_numbers')
            )
        
        return result_list[0] if result_list else None
    
    async def get_product_location_by_id(self, location_id: int) -> Optional[dict]:
        """Get product location with full details"""
        query = f"""
            SELECT 
                pl.id as location_record_id,
                pl.box_id,
                pl.product_type,
                pl.product_id,
                pl.product_name,
                pl.sku,
                pl.quantity,
                pl.serial_numbers,
                pl.metal_weight_g,
                pl.purity_k,
                pl.zakya_metadata,
                pl.last_counted_by,
                pl.last_counted_at,
                pl.created_at,
                pl.updated_at,
                sb.box_code,
                sb.box_label,
                ss.shelf_code,
                ss.shelf_name,
                sl.location_name,
                sl.location_code,
                sl.id as location_id
            FROM billing_system_product_locations pl
            JOIN billing_system_storage_boxes sb ON pl.box_id = sb.id
            JOIN billing_system_storage_shelves ss ON sb.shelf_id = ss.id
            JOIN billing_system_storage_locations sl ON ss.location_id = sl.id
            WHERE pl.id = :location_id
        """
        result = self.db.execute_query(query, {"location_id": location_id}, return_data=True)
        if isinstance(result, list):
            return result[0] if result else None
        elif hasattr(result, 'empty'):  # pandas DataFrame
            return result.to_dict('records')[0] if not result.empty else None
        return None
    
    async def find_product_locations(self, product_type: str, product_id: str) -> List[dict]:
        """Find all locations where a product is stored"""
        query = f"""
            SELECT 
                pl.id as location_record_id,
                pl.box_id,
                pl.product_type,
                pl.product_id,
                pl.product_name,
                pl.sku,
                pl.quantity,
                pl.serial_numbers,
                pl.metal_weight_g,
                pl.purity_k,
                pl.zakya_metadata,
                pl.last_counted_by,
                pl.last_counted_at,
                pl.created_at,
                pl.updated_at,
                sb.box_code,
                sb.box_label,
                ss.shelf_code,
                ss.shelf_name,
                sl.location_name,
                sl.location_code,
                sl.id as location_id
            FROM billing_system_product_locations pl
            JOIN billing_system_storage_boxes sb ON pl.box_id = sb.id
            JOIN billing_system_storage_shelves ss ON sb.shelf_id = ss.id
            JOIN billing_system_storage_locations sl ON ss.location_id = sl.id
            WHERE pl.product_type = :product_type 
            AND pl.product_id = :product_id
            ORDER BY sl.location_name, ss.shelf_code, sb.box_code
        """
        result = self.db.execute_query(query, {
            "product_type": product_type,
            "product_id": product_id
        }, return_data=True)
        if isinstance(result, list):
            return result
        elif hasattr(result, 'empty'):  # pandas DataFrame
            return result.to_dict('records') if not result.empty else []
        return []
    
    async def search_products(self, filters: dict) -> List[dict]:
        """Search products across all locations"""
        conditions = ["1=1"]
        params = {}
        
        if filters.get('sku'):
            conditions.append("pl.sku ILIKE :sku")
            params['sku'] = f"%{filters['sku']}%"
        
        if filters.get('product_name'):
            conditions.append("pl.product_name ILIKE :product_name")
            params['product_name'] = f"%{filters['product_name']}%"
        
        if filters.get('product_type'):
            conditions.append("pl.product_type = :product_type")
            params['product_type'] = filters['product_type']
        
        if filters.get('location_id'):
            conditions.append("sl.id = :location_id")
            params['location_id'] = filters['location_id']
        
        if filters.get('shelf_id'):
            conditions.append("ss.id = :shelf_id")
            params['shelf_id'] = filters['shelf_id']
        
        if filters.get('box_id'):
            conditions.append("pl.box_id = :box_id")
            params['box_id'] = filters['box_id']
        
        if filters.get('has_serials') is not None:
            if filters['has_serials']:
                conditions.append("pl.serial_numbers IS NOT NULL AND array_length(pl.serial_numbers, 1) > 0")
            else:
                conditions.append("(pl.serial_numbers IS NULL OR array_length(pl.serial_numbers, 1) = 0)")
        
        if filters.get('min_quantity'):
            conditions.append("pl.quantity >= :min_quantity")
            params['min_quantity'] = filters['min_quantity']
        
        if filters.get('max_quantity'):
            conditions.append("pl.quantity <= :max_quantity")
            params['max_quantity'] = filters['max_quantity']
        
        query = f"""
            SELECT 
                pl.id as location_record_id,
                pl.box_id,
                pl.product_type,
                pl.product_id,
                pl.product_name,
                pl.sku,
                pl.quantity,
                pl.serial_numbers,
                pl.metal_weight_g,
                pl.purity_k,
                pl.zakya_metadata,
                pl.last_counted_by,
                pl.last_counted_at,
                pl.created_at,
                pl.updated_at,
                sb.box_code,
                sb.box_label,
                ss.shelf_code,
                ss.shelf_name,
                sl.location_name,
                sl.location_code,
                sl.id as location_id
            FROM billing_system_product_locations pl
            JOIN billing_system_storage_boxes sb ON pl.box_id = sb.id
            JOIN billing_system_storage_shelves ss ON sb.shelf_id = ss.id
            JOIN billing_system_storage_locations sl ON ss.location_id = sl.id
            WHERE {' AND '.join(conditions)}
            ORDER BY sl.location_name, ss.shelf_code, sb.box_code, pl.product_name
        """
        result = self.db.execute_query(query, params, return_data=True)
        print(f"Search products query result: {result}")
        if isinstance(result, list):
            return result
        elif hasattr(result, 'empty'):  # pandas DataFrame
            return result.to_dict('records') if not result.empty else []
        return []
    
    async def transfer_product(self, from_location_id: int, to_box_id: int, 
                               quantity: int, moved_by: str, 
                               reason: str = None, notes: str = None) -> dict:
        """Transfer product from one box to another"""
        # Get source product location
        source = await self.get_product_location_by_id(from_location_id)
        if not source:
            raise ValueError(f"Product location {from_location_id} not found")
        
        if source['quantity'] < quantity:
            raise ValueError(f"Insufficient quantity. Available: {source['quantity']}, Requested: {quantity}")
        
        # Get destination box details
        box_query = f"SELECT * FROM billing_system_storage_boxes WHERE id = :box_id"
        dest_box = self.db.execute_query(box_query, {"box_id": to_box_id}, return_data=True)
        dest_box = dest_box if isinstance(dest_box, list) else (dest_box.to_dict('records') if hasattr(dest_box, 'to_dict') else [])
        if not dest_box:
            raise ValueError(f"Destination box {to_box_id} not found")
        
        # Check if product already exists in destination box
        check_dest = f"""
            SELECT * FROM billing_system_product_locations
            WHERE box_id = :box_id 
            AND product_type = :product_type 
            AND product_id = :product_id
        """
        existing_dest = self.db.execute_query(check_dest, {
            "box_id": to_box_id,
            "product_type": source['product_type'],
            "product_id": source['product_id']
        }, return_data=True)
        existing_dest = existing_dest if isinstance(existing_dest, list) else (existing_dest.to_dict('records') if hasattr(existing_dest, 'to_dict') else [])
        
        # Update source quantity
        new_source_qty = source['quantity'] - quantity
        if new_source_qty == 0:
            # Remove source record if quantity becomes 0
            delete_query = f"DELETE FROM billing_system_product_locations WHERE id = :id"
            self.db.execute_query(delete_query, {"id": from_location_id})
        else:
            update_source = f"""
                UPDATE billing_system_product_locations
                SET quantity = :quantity, updated_at = NOW()
                WHERE id = :id
            """
            self.db.execute_query(update_source, {"id": from_location_id, "quantity": new_source_qty})
        
        # Update or create destination
        if existing_dest:
            update_dest = f"""
                UPDATE billing_system_product_locations
                SET quantity = quantity + :quantity, updated_at = NOW()
                WHERE id = :id
                RETURNING *
            """
            result = self.db.execute_query(update_dest, {
                "id": existing_dest[0]['id'],
                "quantity": quantity
            }, return_data=True)
        else:
            insert_dest = f"""
                INSERT INTO billing_system_product_locations
                (box_id, product_type, product_id, product_name, sku, quantity,
                 metal_weight_g, purity_k, zakya_metadata, last_counted_by)
                VALUES (:box_id, :product_type, :product_id, :product_name,
                        :sku, :quantity, :metal_weight_g, :purity_k,
                        :zakya_metadata, :moved_by)
                RETURNING *
            """
            result = self.db.execute_query(insert_dest, {
                "box_id": to_box_id,
                "product_type": source['product_type'],
                "product_id": source['product_id'],
                "product_name": source['product_name'],
                "sku": source['sku'],
                "quantity": quantity,
                "metal_weight_g": source.get('metal_weight_g'),
                "purity_k": source.get('purity_k'),
                "zakya_metadata": source.get('zakya_metadata'),
                "moved_by": moved_by
            }, return_data=True)
        
        # Record movement
        await self._record_movement(
            product_type=source['product_type'],
            product_id=source['product_id'],
            sku=source['sku'],
            product_name=source['product_name'],
            movement_type='transfer',
            quantity_moved=quantity,
            from_box_id=source['box_id'],
            to_box_id=to_box_id,
            moved_by=moved_by,
            reason=reason,
            notes=notes
        )
        
        result_list = result if isinstance(result, list) else (result.to_dict('records') if hasattr(result, 'to_dict') else [])
        return result_list[0] if result_list else None
    
    async def update_product_quantity(self, location_id: int, new_quantity: int, 
                                      updated_by: str, reason: str = None) -> dict:
        """Update product quantity (for adjustments/recounts)"""
        # Get current record
        current = await self.get_product_location_by_id(location_id)
        if not current:
            raise ValueError(f"Product location {location_id} not found")
        
        old_quantity = current['quantity']
        quantity_diff = new_quantity - old_quantity
        
        # Update quantity
        update_query = f"""
            UPDATE billing_system_product_locations
            SET quantity = :quantity, 
                last_counted_at = NOW(),
                last_counted_by = :updated_by,
                updated_at = NOW()
            WHERE id = :id
            RETURNING *
        """
        result = self.db.execute_query(update_query, {
            "id": location_id,
            "quantity": new_quantity,
            "updated_by": updated_by
        }, return_data=True)
        
        # Record movement
        movement_type = 'adjustment' if reason else 'recount'
        await self._record_movement(
            product_type=current['product_type'],
            product_id=current['product_id'],
            sku=current['sku'],
            product_name=current['product_name'],
            movement_type=movement_type,
            quantity_moved=abs(quantity_diff),
            to_box_id=current['box_id'] if quantity_diff > 0 else None,
            from_box_id=current['box_id'] if quantity_diff < 0 else None,
            moved_by=updated_by,
            reason=reason or f"Quantity adjusted from {old_quantity} to {new_quantity}"
        )
        
        return result[0] if result else None
    
    async def remove_product_from_box(self, location_id: int, quantity: int, 
                                      removed_by: str, reason: str = None) -> bool:
        """Remove product quantity from a box"""
        current = await self.get_product_location_by_id(location_id)
        if not current:
            raise ValueError(f"Product location {location_id} not found")
        
        if current['quantity'] < quantity:
            raise ValueError(f"Insufficient quantity. Available: {current['quantity']}, Requested: {quantity}")
        
        new_quantity = current['quantity'] - quantity
        
        if new_quantity == 0:
            # Delete record
            delete_query = f"DELETE FROM billing_system_product_locations WHERE id = :id"
            self.db.execute_query(delete_query, {"id": location_id}, return_data=False)
        else:
            # Update quantity
            update_query = f"""
                UPDATE billing_system_product_locations
                SET quantity = :quantity, updated_at = NOW()
                WHERE id = :id
            """
            self.db.execute_query(update_query, {"id": location_id, "quantity": new_quantity}, return_data=False)
        
        # Record movement
        await self._record_movement(
            product_type=current['product_type'],
            product_id=current['product_id'],
            sku=current['sku'],
            product_name=current['product_name'],
            movement_type='remove',
            quantity_moved=quantity,
            from_box_id=current['box_id'],
            moved_by=removed_by,
            reason=reason or "Product removed from inventory"
        )
        
        return True
    
    async def get_inventory_summary_by_location(self, location_id: Optional[int] = None) -> List[dict]:
        """Get inventory summary grouped by location"""
        if location_id:
            query = """
                SELECT 
                    sl.id as location_id,
                    sl.location_name,
                    pl.product_type,
                    pl.product_id,
                    pl.product_name,
                    pl.sku,
                    SUM(pl.quantity) as total_quantity,
                    COUNT(DISTINCT pl.box_id) as num_boxes,
                    ARRAY_AGG(DISTINCT sb.box_code ORDER BY sb.box_code) as box_codes
                FROM billing_system_product_locations pl
                JOIN billing_system_storage_boxes sb ON pl.box_id = sb.id
                JOIN billing_system_storage_shelves ss ON sb.shelf_id = ss.id
                JOIN billing_system_storage_locations sl ON ss.location_id = sl.id
                WHERE sl.id = :location_id
                GROUP BY sl.id, sl.location_name, pl.product_type, pl.product_id, pl.product_name, pl.sku
                ORDER BY pl.product_name
            """
            params = {"location_id": location_id}
        else:
            query = """
                SELECT 
                    sl.id as location_id,
                    sl.location_name,
                    pl.product_type,
                    pl.product_id,
                    pl.product_name,
                    pl.sku,
                    SUM(pl.quantity) as total_quantity,
                    COUNT(DISTINCT pl.box_id) as num_boxes,
                    ARRAY_AGG(DISTINCT sb.box_code ORDER BY sb.box_code) as box_codes
                FROM billing_system_product_locations pl
                JOIN billing_system_storage_boxes sb ON pl.box_id = sb.id
                JOIN billing_system_storage_shelves ss ON sb.shelf_id = ss.id
                JOIN billing_system_storage_locations sl ON ss.location_id = sl.id
                GROUP BY sl.id, sl.location_name, pl.product_type, pl.product_id, pl.product_name, pl.sku
                ORDER BY sl.location_name, pl.product_name
            """
            params = {}
        
        result = self.db.execute_query(query, params, return_data=True)
        print(f"Inventory summary query result: {result}")
        # Handle empty DataFrames properly - don't use 'or' as it tries to evaluate truthiness
        if isinstance(result, list):
            return result
        elif hasattr(result, 'empty'):  # pandas DataFrame
            return result.to_dict('records') if not result.empty else []
        else:
            return result if result else []
    
    async def get_product_movement_history(self, product_type: str, product_id: str, 
                                           limit: int = 100) -> List[dict]:
        """Get movement history for a specific product"""
        query = f"""
            SELECT 
                pm.*,
                sl_from.location_name as from_location_name,
                ss_from.shelf_code as from_shelf_code,
                sb_from.box_code as from_box_code,
                sl_to.location_name as to_location_name,
                ss_to.shelf_code as to_shelf_code,
                sb_to.box_code as to_box_code
            FROM billing_system_product_movements pm
            LEFT JOIN billing_system_storage_boxes sb_from ON pm.from_box_id = sb_from.id
            LEFT JOIN billing_system_storage_shelves ss_from ON sb_from.shelf_id = ss_from.id
            LEFT JOIN billing_system_storage_locations sl_from ON ss_from.location_id = sl_from.id
            LEFT JOIN billing_system_storage_boxes sb_to ON pm.to_box_id = sb_to.id
            LEFT JOIN billing_system_storage_shelves ss_to ON sb_to.shelf_id = ss_to.id
            LEFT JOIN billing_system_storage_locations sl_to ON ss_to.location_id = sl_to.id
            WHERE pm.product_type = :product_type 
            AND pm.product_id = :product_id
            ORDER BY pm.movement_date DESC
            LIMIT :limit
        """
        result = self.db.execute_query(query, {
            "product_type": product_type,
            "product_id": product_id,
            "limit": limit
        }, return_data=True)
        return result or []
    
    async def _record_movement(self, **movement_data) -> dict:
        """Internal method to record product movement"""
        # Get box/shelf/location IDs from box_id
        if movement_data.get('from_box_id'):
            from_box_query = f"""
                SELECT sb.id as box_id, ss.id as shelf_id, sl.id as location_id
                FROM billing_system_storage_boxes sb
                JOIN billing_system_storage_shelves ss ON sb.shelf_id = ss.id
                JOIN billing_system_storage_locations sl ON ss.location_id = sl.id
                WHERE sb.id = :box_id
            """
            from_details = self.db.execute_query(from_box_query, {"box_id": movement_data['from_box_id']}, return_data=True)
            from_details = from_details if isinstance(from_details, list) else (from_details.to_dict('records') if hasattr(from_details, 'to_dict') else [])
            if from_details:
                movement_data['from_shelf_id'] = from_details[0]['shelf_id']
                movement_data['from_location_id'] = from_details[0]['location_id']
        
        if movement_data.get('to_box_id'):
            to_box_query = f"""
                SELECT sb.id as box_id, ss.id as shelf_id, sl.id as location_id
                FROM billing_system_storage_boxes sb
                JOIN billing_system_storage_shelves ss ON sb.shelf_id = ss.id
                JOIN billing_system_storage_locations sl ON ss.location_id = sl.id
                WHERE sb.id = :box_id
            """
            to_details = self.db.execute_query(to_box_query, {"box_id": movement_data['to_box_id']}, return_data=True)
            to_details = to_details if isinstance(to_details, list) else (to_details.to_dict('records') if hasattr(to_details, 'to_dict') else [])
            if to_details:
                movement_data['to_shelf_id'] = to_details[0]['shelf_id']
                movement_data['to_location_id'] = to_details[0]['location_id']
        
        insert_query = f"""
            INSERT INTO billing_system_product_movements
            (product_type, product_id, sku, product_name, movement_type, quantity_moved,
             from_location_id, from_shelf_id, from_box_id,
             to_location_id, to_shelf_id, to_box_id,
             moved_by, reason, notes, serial_numbers_moved)
            VALUES (:product_type, :product_id, :sku, :product_name,
                    :movement_type, :quantity_moved,
                    :from_location_id, :from_shelf_id, :from_box_id,
                    :to_location_id, :to_shelf_id, :to_box_id,
                    :moved_by, :reason, :notes, :serial_numbers)
            RETURNING *
        """
        result = self.db.execute_query(insert_query, {
            "product_type": movement_data['product_type'],
            "product_id": movement_data['product_id'],
            "sku": movement_data.get('sku'),
            "product_name": movement_data['product_name'],
            "movement_type": movement_data['movement_type'],
            "quantity_moved": movement_data['quantity_moved'],
            "from_location_id": movement_data.get('from_location_id'),
            "from_shelf_id": movement_data.get('from_shelf_id'),
            "from_box_id": movement_data.get('from_box_id'),
            "to_location_id": movement_data.get('to_location_id'),
            "to_shelf_id": movement_data.get('to_shelf_id'),
            "to_box_id": movement_data.get('to_box_id'),
            "moved_by": movement_data['moved_by'],
            "reason": movement_data.get('reason'),
            "notes": movement_data.get('notes'),
            "serial_numbers": movement_data.get('serial_numbers')
        }, return_data=True)
        result_list = result if isinstance(result, list) else (result.to_dict('records') if hasattr(result, 'to_dict') else [])
        return result_list[0] if result_list else None