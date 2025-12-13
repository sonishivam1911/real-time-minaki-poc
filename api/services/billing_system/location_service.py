"""
Storage Location Service - Business Logic Layer
Handles CRUD operations for storage locations
"""
from typing import List, Optional
from datetime import datetime


class LocationService:
    """Service for managing storage locations"""
    
    def __init__(self, db_connection):
        """
        Initialize with database connection
        Args:
            db_connection: Your database CRUD class instance
        """
        self.db = db_connection
    
    def create_location(self, location_data: dict) -> dict:
        """
        Create a new storage location
        Args:
            location_data: Dictionary with location details
        Returns:
            Created location record
        """
        # Build the INSERT query with properly escaped values
        columns = list(location_data.keys())
        values = []
        
        for v in location_data.values():
            if v is None:
                values.append("NULL")
            elif isinstance(v, bool):
                values.append(str(v).upper())
            elif isinstance(v, str):
                # Escape single quotes by doubling them
                escaped = v.replace("'", "''")
                values.append(f"'{escaped}'")
            else:
                values.append(str(v))
        
        columns_str = ", ".join(columns)
        values_str = ", ".join(values)
        
        query = f"""
            INSERT INTO billing_system_storage_locations 
            ({columns_str})
            VALUES ({values_str})
            RETURNING *
        """
        result = self.db.execute_query_new(query, return_data=True)
        print(f"Create location result: {result}")
        records = self.db._df_to_list_of_dicts(result) if hasattr(result, 'to_dict') else result
        return records[0] if records else None
    
    def get_location_by_id(self, location_id: int) -> Optional[dict]:
        """Get location by ID"""
        query = f"""
            SELECT * FROM billing_system_storage_locations 
            WHERE id = :location_id
        """
        result = self.db.execute_query(query, {"location_id": location_id}, return_data=True)
        records = self.db._df_to_list_of_dicts(result) if hasattr(result, 'to_dict') else result
        return records[0] if records else None
    
    def get_all_locations(self, active_only: bool = True) -> List[dict]:
        """Get all storage locations"""
        where_clause = "WHERE is_active = TRUE" if active_only else ""
        query = f"""
            SELECT * FROM billing_system_storage_locations
            {where_clause}
            ORDER BY location_name
        """
        result = self.db.execute_query_new(query, return_data=True)
        print(f"Get all locations result: {result}")
        return result if isinstance(result, list) else (result.to_dict('records') if hasattr(result, 'to_dict') else [])
    
    def update_location(self, location_id: int, update_data: dict) -> Optional[dict]:
        """Update location details"""
        # Build dynamic SET clause
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
            return self.get_location_by_id(location_id)
        
        query = f"""
            UPDATE billing_system_storage_locations
            SET {', '.join(set_clauses)}, updated_at = NOW()
            WHERE id = :location_id
            RETURNING *
        """
        result = self.db.execute_query(query, {"location_id": location_id}, return_data=True)
        records = self.db._df_to_list_of_dicts(result) if hasattr(result, 'to_dict') else result
        return records[0] if records else None
    
    def delete_location(self, location_id: int) -> bool:
        """Soft delete location (set is_active = false)"""
        query = f"""
            UPDATE billing_system_storage_locations
            SET is_active = FALSE, updated_at = NOW()
            WHERE id = :location_id
            RETURNING id
        """
        result = self.db.execute_query(query, {"location_id": location_id}, return_data=True)
        return bool(result) if hasattr(result, '__len__') else result
    
    def get_location_statistics(self, location_id: int) -> dict:
        """Get statistics for a location"""
        query = f"""
            SELECT 
                sl.id as location_id,
                sl.location_name,
                COUNT(DISTINCT ss.id) as total_shelves,
                COUNT(DISTINCT sb.id) as total_boxes,
                COUNT(DISTINCT pl.id) as total_products,
                COALESCE(SUM(pl.quantity), 0) as total_quantity,
                COUNT(DISTINCT pl.sku) as unique_skus
            FROM billing_system_storage_locations sl
            LEFT JOIN billing_system_storage_shelves ss ON sl.id = ss.location_id AND ss.is_active = TRUE
            LEFT JOIN billing_system_storage_boxes sb ON ss.id = sb.shelf_id AND sb.is_active = TRUE
            LEFT JOIN billing_system_product_locations pl ON sb.id = pl.box_id
            WHERE sl.id = :location_id
            GROUP BY sl.id, sl.location_name
        """
        result = self.db.execute_query(query, {"location_id": location_id}, return_data=True)
        records = self.db._df_to_list_of_dicts(result) if hasattr(result, 'to_dict') else result
        return records[0] if records else None
    
    def get_all_locations_with_stats(self) -> List[dict]:
        """Get all locations with their statistics"""
        query = """
            SELECT 
                sl.id,
                sl.location_name,
                sl.location_code,
                sl.description,
                sl.is_active,
                COUNT(DISTINCT ss.id) as shelf_count,
                COUNT(DISTINCT sb.id) as box_count,
                COUNT(DISTINCT pl.id) as product_count,
                COALESCE(SUM(pl.quantity), 0) as total_quantity
            FROM billing_system_storage_locations sl
            LEFT JOIN billing_system_storage_shelves ss ON sl.id = ss.location_id AND ss.is_active = TRUE
            LEFT JOIN billing_system_storage_boxes sb ON ss.id = sb.shelf_id AND sb.is_active = TRUE
            LEFT JOIN billing_system_product_locations pl ON sb.id = pl.box_id
            WHERE sl.is_active = TRUE
            GROUP BY sl.id, sl.location_name, sl.location_code, sl.description, sl.is_active
            ORDER BY sl.location_name
        """
        result = self.db.execute_query_new(query, return_data=True)
        records = self.db._df_to_list_of_dicts(result) if hasattr(result, 'to_dict') else result
        return records or []