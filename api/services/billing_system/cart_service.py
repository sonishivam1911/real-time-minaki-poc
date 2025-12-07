"""
Cart Service - Business logic for shopping cart management
"""
from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime
from decimal import Decimal

from core.database import PostgresCRUD
from core.config import settings
from utils.schema.billing_system.checkout_schema import CartItemCreate, CartItemUpdate


class CartService:
    """Service for cart-related business logic"""
    
    def __init__(self):
        self.crud = PostgresCRUD(settings.POSTGRES_URI)
    
    def create_cart(
        self, 
        customer_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new shopping cart.
        
        Args:
            customer_id: Customer ID (for logged-in users)
            session_id: Session ID (for guest users)
        
        Returns:
            Created cart data
        """
        try:
            cart_id = str(uuid4())
            
            cart_record = {
                'id': cart_id,
                'customer_id': customer_id,
                'session_id': session_id,
                'status': 'active',
                'subtotal': 0,
                'discount_amount': 0,
                'tax_rate_percent': 0,
                'tax_amount': 0,
                'total_amount': 0,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            self.crud.insert_record('carts', cart_record)
            
            return {
                'success': True,
                'cart_id': cart_id
            }
            
        except Exception as e:
            print(f"❌ Error creating cart: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def add_item_to_cart(
        self, 
        cart_id: str, 
        item_data: CartItemCreate
    ) -> Dict[str, Any]:
        """
        Add item to cart.
        
        Args:
            cart_id: Cart ID
            item_data: Item data to add
        
        Returns:
            Result dictionary
        """
        try:
            # Get variant details
            variant_query = f"""
                SELECT pv.*, p.title as product_name
                FROM product_variants pv
                JOIN products p ON pv.product_id = p.id
                WHERE pv.id = '{item_data.variant_id}'
            """
            variant_df = self.crud.execute_query(variant_query, return_data=True)
            
            if variant_df.empty:
                return {
                    'success': False,
                    'error': 'Variant not found'
                }
            
            variant = variant_df.iloc[0]
            
            # If stock_item_id provided, get serial number
            serial_no = None
            if item_data.stock_item_id:
                stock_query = f"""
                    SELECT serial_no FROM stock_items 
                    WHERE id = '{item_data.stock_item_id}' 
                    AND status = 'in_stock'
                """
                stock_df = self.crud.execute_query(stock_query, return_data=True)
                
                if stock_df.empty:
                    return {
                        'success': False,
                        'error': 'Stock item not available'
                    }
                
                serial_no = stock_df.iloc[0]['serial_no']
            
            # Calculate amounts
            unit_price = float(variant['price'])
            discount_amount = (unit_price * float(item_data.discount_percent) / 100) * item_data.quantity
            line_total = (unit_price * item_data.quantity) - discount_amount
            
            # Check if item already exists in cart
            existing_query = f"""
                SELECT id, quantity FROM cart_items 
                WHERE cart_id = '{cart_id}' 
                AND variant_id = '{item_data.variant_id}'
            """
            existing_df = self.crud.execute_query(existing_query, return_data=True)
            
            if not existing_df.empty:
                # Update quantity
                existing_id = existing_df.iloc[0]['id']
                new_quantity = int(existing_df.iloc[0]['quantity']) + item_data.quantity
                
                update_query = f"""
                    UPDATE cart_items
                    SET quantity = {new_quantity},
                        line_total = {unit_price * new_quantity - (unit_price * new_quantity * float(item_data.discount_percent) / 100)}
                    WHERE id = '{existing_id}'
                """
                self.crud.execute_query(update_query)
                cart_item_id = existing_id
            else:
                # Add new item
                cart_item_id = str(uuid4())
                
                cart_item_record = {
                    'id': cart_item_id,
                    'cart_id': cart_id,
                    'variant_id': item_data.variant_id,
                    'stock_item_id': item_data.stock_item_id,
                    'product_name': variant['product_name'],
                    'sku': variant['sku'],
                    'serial_no': serial_no,
                    'quantity': item_data.quantity,
                    'unit_price': unit_price,
                    'discount_percent': float(item_data.discount_percent),
                    'discount_amount': discount_amount,
                    'line_total': line_total,
                    'created_at': datetime.utcnow()
                }
                
                self.crud.insert_record('cart_items', cart_item_record)
            
            # Recalculate cart totals
            self._recalculate_cart_totals(cart_id)
            
            return {
                'success': True,
                'cart_item_id': cart_item_id,
                'message': 'Item added to cart'
            }
            
        except Exception as e:
            print(f"❌ Error adding item to cart: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_cart_item(
        self, 
        cart_id: str,
        cart_item_id: str,
        update_data: CartItemUpdate
    ) -> Dict[str, Any]:
        """Update cart item quantity or discount"""
        try:
            # Get current item
            item_query = f"""
                SELECT * FROM cart_items 
                WHERE id = '{cart_item_id}' AND cart_id = '{cart_id}'
            """
            item_df = self.crud.execute_query(item_query, return_data=True)
            
            if item_df.empty:
                return {
                    'success': False,
                    'error': 'Cart item not found'
                }
            
            item = item_df.iloc[0]
            
            # Update fields
            quantity = update_data.quantity if update_data.quantity else int(item['quantity'])
            discount_percent = float(update_data.discount_percent) if update_data.discount_percent is not None else float(item['discount_percent'])
            
            # Recalculate
            unit_price = float(item['unit_price'])
            discount_amount = (unit_price * discount_percent / 100) * quantity
            line_total = (unit_price * quantity) - discount_amount
            
            update_query = f"""
                UPDATE cart_items
                SET quantity = {quantity},
                    discount_percent = {discount_percent},
                    discount_amount = {discount_amount},
                    line_total = {line_total}
                WHERE id = '{cart_item_id}'
            """
            
            self.crud.execute_query(update_query)
            
            # Recalculate cart totals
            self._recalculate_cart_totals(cart_id)
            
            return {
                'success': True,
                'message': 'Cart item updated'
            }
            
        except Exception as e:
            print(f"❌ Error updating cart item: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def remove_item_from_cart(
        self, 
        cart_id: str,
        cart_item_id: str
    ) -> Dict[str, Any]:
        """Remove item from cart"""
        try:
            # Delete item
            success = self.crud.delete_record('cart_items', cart_item_id, 'id')
            
            if success:
                # Recalculate cart totals
                self._recalculate_cart_totals(cart_id)
                
                return {
                    'success': True,
                    'message': 'Item removed from cart'
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to remove item'
                }
                
        except Exception as e:
            print(f"❌ Error removing cart item: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_cart(self, cart_id: str) -> Optional[Dict[str, Any]]:
        """Get cart with all items"""
        # Get cart
        cart_query = f"SELECT * FROM carts WHERE id = '{cart_id}'"
        cart_df = self.crud.execute_query(cart_query, return_data=True)
        
        if cart_df.empty:
            return None
        
        cart = cart_df.iloc[0].to_dict()
        
        # Get cart items
        items_query = f"SELECT * FROM cart_items WHERE cart_id = '{cart_id}'"
        items_df = self.crud.execute_query(items_query, return_data=True)
        
        cart['items'] = items_df.to_dict('records')
        
        return cart
    
    def clear_cart(self, cart_id: str) -> bool:
        """Remove all items from cart"""
        try:
            query = f"DELETE FROM cart_items WHERE cart_id = '{cart_id}'"
            self.crud.execute_query(query)
            
            # Reset cart totals
            self._recalculate_cart_totals(cart_id)
            
            return True
            
        except Exception as e:
            print(f"❌ Error clearing cart: {e}")
            return False
    
    def apply_discount_to_cart(
        self, 
        cart_id: str,
        discount_code: str
    ) -> Dict[str, Any]:
        """Apply discount code to cart"""
        try:
            # Get discount
            discount_query = f"""
                SELECT * FROM discounts 
                WHERE discount_code = '{discount_code}'
                AND is_active = true
                AND (valid_from IS NULL OR valid_from <= CURRENT_DATE)
                AND (valid_to IS NULL OR valid_to >= CURRENT_DATE)
            """
            discount_df = self.crud.execute_query(discount_query, return_data=True)
            
            if discount_df.empty:
                return {
                    'success': False,
                    'error': 'Invalid or expired discount code'
                }
            
            discount = discount_df.iloc[0]
            
            # Get cart
            cart = self.get_cart(cart_id)
            if not cart:
                return {
                    'success': False,
                    'error': 'Cart not found'
                }
            
            subtotal = float(cart['subtotal'])
            
            # Check minimum purchase
            if subtotal < float(discount['min_purchase_amount']):
                return {
                    'success': False,
                    'error': f"Minimum purchase amount is {discount['min_purchase_amount']}"
                }
            
            # Calculate discount
            if discount['discount_type'] == 'percentage':
                discount_amount = subtotal * (float(discount['discount_value']) / 100)
            else:  # fixed_amount
                discount_amount = float(discount['discount_value'])
            
            # Apply max discount limit
            if discount['max_discount_amount']:
                discount_amount = min(discount_amount, float(discount['max_discount_amount']))
            
            # Update cart
            update_query = f"""
                UPDATE carts
                SET discount_amount = {discount_amount}
                WHERE id = '{cart_id}'
            """
            self.crud.execute_query(update_query)
            
            # Recalculate totals
            self._recalculate_cart_totals(cart_id)
            
            return {
                'success': True,
                'discount_amount': discount_amount,
                'message': f'Discount "{discount["discount_name"]}" applied'
            }
            
        except Exception as e:
            print(f"❌ Error applying discount: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _recalculate_cart_totals(self, cart_id: str):
        """Recalculate cart subtotal and total"""
        # Sum line totals
        items_query = f"""
            SELECT 
                COALESCE(SUM(line_total), 0) as subtotal
            FROM cart_items
            WHERE cart_id = '{cart_id}'
        """
        items_df = self.crud.execute_query(items_query, return_data=True)
        
        subtotal = float(items_df.iloc[0]['subtotal']) if not items_df.empty else 0
        
        # Get cart for discount and tax
        cart_query = f"SELECT discount_amount, tax_rate_percent FROM carts WHERE id = '{cart_id}'"
        cart_df = self.crud.execute_query(cart_query, return_data=True)
        
        if cart_df.empty:
            return
        
        discount_amount = float(cart_df.iloc[0]['discount_amount'])
        tax_rate_percent = float(cart_df.iloc[0]['tax_rate_percent'])
        
        # Calculate tax on (subtotal - discount)
        taxable_amount = subtotal - discount_amount
        tax_amount = taxable_amount * (tax_rate_percent / 100)
        
        total_amount = taxable_amount + tax_amount
        
        # Update cart
        update_query = f"""
            UPDATE carts
            SET subtotal = {subtotal},
                tax_amount = {tax_amount},
                total_amount = {total_amount},
                updated_at = CURRENT_TIMESTAMP
            WHERE id = '{cart_id}'
        """
        
        self.crud.execute_query(update_query)