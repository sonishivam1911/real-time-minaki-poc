"""
Inventory Service - Business logic for inventory management
"""
from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime, date

from core.database import PostgresCRUD
from core.config import settings


class InventoryService:
    """Service for inventory-related business logic"""
    
    def __init__(self):
        self.crud = PostgresCRUD(settings.POSTGRES_URI)
    
    def receive_metal_lot(
        self,
        lot_label: str,
        metal_type: str,
        purity_k: float,
        gross_weight_g: float,
        net_weight_g: float,
        received_from: str,
        received_date: date,
        location: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Receive a metal lot (GRN - Goods Receipt Note).
        
        Args:
            lot_label: Human-readable lot label
            metal_type: Type of metal (gold, silver, platinum)
            purity_k: Purity in karats
            gross_weight_g: Gross weight in grams
            net_weight_g: Net weight in grams
            received_from: Vendor/source
            received_date: Date of receipt
            location: Storage location
            notes: Additional notes
        
        Returns:
            Created lot information
        """
        try:
            lot_id = str(uuid4())
            
            lot_record = {
                'id': lot_id,
                'variant_id': None,  # Raw metal lot
                'lot_label': lot_label,
                'lot_type': 'metal_lot',
                'metal_type': metal_type,
                'purity_k': purity_k,
                'gross_weight_g': gross_weight_g,
                'net_weight_g': net_weight_g,
                'received_from': received_from,
                'received_date': received_date,
                'location': location,
                'status': 'available',
                'notes': notes,
                'created_at': datetime.utcnow()
            }
            
            self.crud.insert_record('inventory_lots', lot_record)
            
            # Create stock movement record
            self._create_stock_movement(
                lot_id=lot_id,
                movement_type='receive',
                weight_g=net_weight_g,
                to_location=location,
                reference=f"GRN: {lot_label}"
            )
            
            return {
                'success': True,
                'lot_id': lot_id,
                'message': f'Metal lot {lot_label} received successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def consume_metal_lot(
        self,
        lot_id: str,
        weight_consumed_g: float,
        variant_id: str,
        work_order_ref: str
    ) -> Dict[str, Any]:
        """
        Consume metal from a lot for production.
        
        Args:
            lot_id: ID of lot to consume from
            weight_consumed_g: Weight to consume in grams
            variant_id: Variant being produced
            work_order_ref: Work order reference
        
        Returns:
            Result dictionary
        """
        try:
            # Get current lot
            lot_query = f"""
                SELECT * FROM inventory_lots WHERE id = '{lot_id}'
            """
            lot_df = self.crud.execute_query(lot_query, return_data=True)
            
            if lot_df.empty:
                return {
                    'success': False,
                    'error': 'Lot not found'
                }
            
            lot = lot_df.iloc[0]
            
            # Check available weight
            if lot['net_weight_g'] < weight_consumed_g:
                return {
                    'success': False,
                    'error': f'Insufficient weight. Available: {lot["net_weight_g"]}g, Required: {weight_consumed_g}g'
                }
            
            # Update lot weight
            new_weight = lot['net_weight_g'] - weight_consumed_g
            status = 'consumed' if new_weight == 0 else 'available'
            update_query = f"""
                UPDATE inventory_lots
                SET net_weight_g = {new_weight},
                    status = '{status}'
                WHERE id = '{lot_id}'
            """
            self.crud.execute_query(update_query)
            
            # Create stock movement
            self._create_stock_movement(
                lot_id=lot_id,
                variant_id=variant_id,
                movement_type='consume',
                weight_g=weight_consumed_g,
                from_location=lot['location'],
                reference=work_order_ref
            )
            
            return {
                'success': True,
                'remaining_weight_g': float(new_weight),
                'message': f'Consumed {weight_consumed_g}g from lot {lot["lot_label"]}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def add_finished_product_to_stock(
        self,
        variant_id: str,
        serial_no: str,
        lot_id: str,
        location: str
    ) -> Dict[str, Any]:
        """
        Add a finished product to stock with serial tracking.
        
        Args:
            variant_id: Variant ID
            serial_no: Serial number/barcode
            lot_id: Lot ID for finished goods
            location: Storage location
        
        Returns:
            Result dictionary
        """
        try:
            stock_item_id = str(uuid4())
            
            stock_record = {
                'id': stock_item_id,
                'lot_id': lot_id,
                'serial_no': serial_no,
                'variant_id': variant_id,
                'current_location': location,
                'status': 'in_stock',
                'purchase_invoice_id': None,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            self.crud.insert_record('stock_items', stock_record)
            
            # Create stock movement
            self._create_stock_movement(
                stock_item_id=stock_item_id,
                variant_id=variant_id,
                movement_type='receive',
                to_location=location,
                reference=f"Finished product: {serial_no}"
            )
            
            return {
                'success': True,
                'stock_item_id': stock_item_id,
                'message': f'Product {serial_no} added to stock'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_available_inventory(
        self,
        metal_type: Optional[str] = None,
        purity_k: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Get available inventory by metal type and purity.
        
        Args:
            metal_type: Filter by metal type
            purity_k: Filter by purity
        
        Returns:
            List of available lots
        """
        where_clauses = ["status = 'available'"]
        
        if metal_type:
            where_clauses.append(f"metal_type = '{metal_type}'")
        
        if purity_k:
            where_clauses.append(f"purity_k = {purity_k}")
        
        where_str = " AND ".join(where_clauses)
        
        query = f"""
            SELECT 
                id,
                lot_label,
                metal_type,
                purity_k,
                net_weight_g,
                location,
                received_date
            FROM inventory_lots
            WHERE {where_str}
            ORDER BY received_date ASC
        """
        
        df = self.crud.execute_query(query, return_data=True)
        
        lots = df.to_dict('records')
        
        # Calculate total weight
        total_weight = df['net_weight_g'].sum() if not df.empty else 0
        
        return {
            'metal_type': metal_type,
            'purity_k': purity_k,
            'total_weight_g': float(total_weight),
            'lots': lots
        }
    
    def record_sale(
        self,
        stock_item_id: str,
        serial_no: str,
        sale_invoice_id: str,
        customer_id: Optional[str] = None,
        sale_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Record a sale of a stock item.
        
        Args:
            stock_item_id: Stock item ID
            serial_no: Serial number
            sale_invoice_id: Invoice ID
            customer_id: Customer ID
            sale_price: Sale price
        
        Returns:
            Result dictionary
        """
        try:
            # Get stock item
            stock_query = f"""
                SELECT * FROM stock_items WHERE id = '{stock_item_id}'
            """
            stock_df = self.crud.execute_query(stock_query, return_data=True)
            
            if stock_df.empty:
                return {
                    'success': False,
                    'error': 'Stock item not found'
                }
            
            stock = stock_df.iloc[0]
            
            # Update stock item status
            update_query = f"""
                UPDATE stock_items
                SET status = 'sold',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = '{stock_item_id}'
            """
            self.crud.execute_query(update_query)
            
            # Create stock movement
            self._create_stock_movement(
                stock_item_id=stock_item_id,
                variant_id=stock['variant_id'],
                movement_type='sale',
                from_location=stock['current_location'],
                reference=sale_invoice_id
            )
            
            return {
                'success': True,
                'message': f'Sale recorded for {serial_no}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_stock_movement(
        self,
        movement_type: str,
        stock_item_id: Optional[str] = None,
        lot_id: Optional[str] = None,
        variant_id: Optional[str] = None,
        weight_g: Optional[float] = None,
        from_location: Optional[str] = None,
        to_location: Optional[str] = None,
        reference: Optional[str] = None
    ) -> str:
        """Create a stock movement record"""
        movement_id = str(uuid4())
        
        movement_record = {
            'id': movement_id,
            'stock_item_id': stock_item_id,
            'lot_id': lot_id,
            'variant_id': variant_id,
            'movement_type': movement_type,
            'qty': 1,
            'weight_g': weight_g,
            'from_location': from_location,
            'to_location': to_location,
            'reference': reference,
            'performed_by': None,  # Would come from auth context
            'performed_at': datetime.utcnow()
        }
        
        self.crud.insert_record('stock_movements', movement_record)
        return movement_id
    
    def get_stock_movement_history(
        self,
        serial_no: Optional[str] = None,
        stock_item_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get movement history for a stock item"""
        where_clause = ""
        if stock_item_id:
            where_clause = f"WHERE stock_item_id = '{stock_item_id}'"
        elif serial_no:
            # Get stock item ID first
            stock_query = f"""
                SELECT id FROM stock_items WHERE serial_no = '{serial_no}'
            """
            stock_df = self.crud.execute_query(stock_query, return_data=True)
            if not stock_df.empty:
                stock_item_id = stock_df.iloc[0]['id']
                where_clause = f"WHERE stock_item_id = '{stock_item_id}'"
        
        query = f"""
            SELECT * FROM stock_movements
            {where_clause}
            ORDER BY performed_at DESC
        """
        
        df = self.crud.execute_query(query, return_data=True)
        return df.to_dict('records')