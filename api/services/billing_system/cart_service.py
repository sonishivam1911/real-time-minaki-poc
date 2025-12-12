"""
Cart Service - Business logic for shopping cart management
"""
from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime
from decimal import Decimal

from core.database import db
from core.config import settings
from utils.schema.billing_system.checkout_schema import CartItemCreate, CartItemUpdate


class CartService:
    """Service for cart-related business logic"""
    
    def __init__(self):
        self.crud = db
    
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
                'tax_rate_percent': 3,
                'tax_amount': 0,
                'total_amount': 0,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            self.crud.insert_record('billing_system_carts', cart_record)
            
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
        Add item to cart using new polymorphic schema.
        Supports: item_type + item_id, SKU auto-detection, or legacy fields.
        """
        try:
            # Step 1: Resolve item details using polymorphic approach
            item_info = self._resolve_item_details(item_data)
            if not item_info:
                return {
                    'success': False,
                    'error': 'Product not found'
                }
            
            print(f"✅ Found {item_info['item_type']} item: {item_info['product_name']} - Price: {item_info['price']}")
            
            # Validate expected price if provided
            if hasattr(item_data, 'expected_price') and item_data.expected_price is not None:
                expected_price = float(item_data.expected_price)
                actual_price = float(item_info['price'])
                if abs(expected_price - actual_price) > 0.01:  # Allow 1 cent tolerance
                    print(f"⚠️ Price mismatch: expected {expected_price}, found {actual_price}")
                    return {
                        'success': False,
                        'error': f'Price mismatch: expected ₹{expected_price}, current price is ₹{actual_price}'
                    }
            
            # Step 2: Validate serial number for real jewelry if provided
            if item_info['item_type'] == 'real_jewelry' and hasattr(item_data, 'serial_no') and item_data.serial_no:
                # TODO: Validate serial number exists and is available
                pass
            
            # Step 3: Calculate pricing
            unit_price = float(item_info['price'])
            discount_percent = getattr(item_data, 'discount_percent', 0)
            discount_amount = (unit_price * float(discount_percent) / 100) * item_data.quantity
            line_total = (unit_price * item_data.quantity) - discount_amount
            
            # Step 4: Check if item already exists in cart
            existing_query = f"""
                SELECT id, quantity FROM billing_system_cart_items 
                WHERE cart_id = '{cart_id}' 
                AND item_type = '{item_info['item_type']}'
                AND item_id = '{item_info['item_id']}'
            """
            
            # For real jewelry with serial numbers, treat as separate items
            if item_info['item_type'] == 'real_jewelry' and hasattr(item_data, 'serial_no') and item_data.serial_no:
                existing_query += f" AND serial_no = '{item_data.serial_no}'"
            
            existing_df = self.crud.execute_query(existing_query, return_data=True)
            
            if not existing_df.empty and not (item_info['item_type'] == 'real_jewelry' and hasattr(item_data, 'serial_no')):
                # Update quantity for existing item (except serialized real jewelry)
                existing_id = existing_df.iloc[0]['id']
                new_quantity = int(existing_df.iloc[0]['quantity']) + item_data.quantity
                new_line_total = (unit_price * new_quantity) - (unit_price * new_quantity * float(discount_percent) / 100)
                
                update_query = f"""
                    UPDATE billing_system_cart_items
                    SET quantity = {new_quantity},
                        discount_amount = {unit_price * new_quantity * float(discount_percent) / 100},
                        line_total = {new_line_total},
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = '{existing_id}'
                """
                self.crud.execute_query_new(update_query)
                cart_item_id = existing_id
                print(f"📝 Updated existing cart item quantity to {new_quantity}")
            else:
                # Add new item
                cart_item_id = str(uuid4())
                
                # Build cart item record
                cart_item_record = {
                    'id': cart_item_id,
                    'cart_id': cart_id,
                    'item_type': item_info['item_type'],
                    'item_id': item_info['item_id'],
                    'product_name': item_info['product_name'],
                    'sku': item_info.get('sku'),
                    'quantity': item_data.quantity,
                    'unit_price': unit_price,
                    'discount_percent': float(discount_percent),
                    'discount_amount': discount_amount,
                    'line_total': line_total,
                    'notes': getattr(item_data, 'notes', None),
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                }
                
                # Add type-specific fields
                if item_info['item_type'] == 'real_jewelry':
                    cart_item_record.update({
                        'serial_no': getattr(item_data, 'serial_no', None),
                        'metal_weight_g': item_info.get('metal_weight_g'),
                        'purity_k': item_info.get('purity_k'),
                        'metal_breakdown': item_info.get('metal_breakdown'),
                        'stone_breakdown': item_info.get('stone_breakdown')
                    })
                elif item_info['item_type'] == 'zakya_product':
                    cart_item_record.update({
                        'zakya_stock_available': item_info.get('stock_on_hand', 0)
                    })
                
                self.crud.insert_record('billing_system_cart_items', cart_item_record)
                print(f"➕ Added new cart item: {item_info['product_name']}")
            
            # Step 5: Recalculate cart totals
            self._recalculate_cart_totals(cart_id)
            
            return {
                'success': True,
                'cart_item_id': cart_item_id,
                'item_type': item_info['item_type'],
                'item_id': item_info['item_id'],
                'product_name': item_info['product_name'],
                'sku': item_info.get('sku'),
                'unit_price': unit_price,
                'quantity': item_data.quantity,
                'line_total': line_total,
                'message': f'{item_info["item_type"]} item added to cart'
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
                SELECT * FROM billing_system_cart_items 
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
                UPDATE billing_system_cart_items
                SET quantity = {quantity},
                    discount_percent = {discount_percent},
                    discount_amount = {discount_amount},
                    line_total = {line_total}
                WHERE id = '{cart_item_id}'
            """
            
            self.crud.execute_query_new(update_query)
            
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
            success = self.crud.delete_record('billing_system_cart_items', f"id = '{cart_item_id}'")
            
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
    
    def get_cart(self, cart_id: str, include_details: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get cart with all items using new polymorphic schema
        
        Args:
            cart_id: Cart ID
            include_details: Whether to fetch additional product details (default: False)
        """
        # Get cart
        cart_query = f"SELECT * FROM billing_system_carts WHERE id = '{cart_id}'"
        cart_df = self.crud.execute_query(cart_query, return_data=True)
        
        if cart_df.empty:
            return None
        
        cart = cart_df.iloc[0].to_dict()
        
        # Get cart items with new schema
        items_query = f"""
            SELECT 
                id, cart_id, item_type, item_id, product_name, sku,
                quantity, unit_price, discount_percent, discount_amount, line_total,
                serial_no, metal_weight_g, purity_k, 
                metal_breakdown, stone_breakdown, zakya_stock_available,
                notes, created_at, updated_at
            FROM billing_system_cart_items 
            WHERE cart_id = '{cart_id}'
            ORDER BY created_at
        """
        items_df = self.crud.execute_query(items_query, return_data=True)
        
        cart_items = []
        for _, item in items_df.iterrows():
            item_dict = item.to_dict()
            
            # Parse JSON fields if they exist
            if item_dict.get('metal_breakdown'):
                try:
                    import json
                    item_dict['metal_breakdown'] = json.loads(item_dict['metal_breakdown'])
                except:
                    item_dict['metal_breakdown'] = None
                    
            if item_dict.get('stone_breakdown'):
                try:
                    import json
                    item_dict['stone_breakdown'] = json.loads(item_dict['stone_breakdown'])
                except:
                    item_dict['stone_breakdown'] = None
            
            # Add frontend compatibility fields
            item_dict['price'] = item_dict['unit_price']  # Frontend expects 'price'
            item_dict['name'] = item_dict['product_name']  # Frontend expects 'name'
            
            cart_items.append(item_dict)
        
        cart['items'] = cart_items
        
        return cart
    
    def clear_cart(self, cart_id: str) -> bool:
        """Remove all items from cart"""
        try:
            query = f"DELETE FROM billing_system_cart_items WHERE cart_id = '{cart_id}'"
            self.crud.execute_query_new(query)
            
            # Reset cart totals
            self._recalculate_cart_totals(cart_id)
            
            return True
            
        except Exception as e:
            print(f"❌ Error clearing cart: {e}")
            return False
    
    def _resolve_item_details(self, item_data: CartItemCreate) -> Optional[Dict[str, Any]]:
        """
        Smart item resolution using polymorphic approach.
        Supports: item_type+item_id, SKU auto-detection, legacy fields.
        """
        try:
            # Method 1: Direct polymorphic approach (item_type + item_id)
            if hasattr(item_data, 'item_type') and item_data.item_type and hasattr(item_data, 'item_id') and item_data.item_id:
                if item_data.item_type == 'real_jewelry':
                    details = self._get_real_jewelry_details(item_data.item_id)
                    if details:
                        details['item_type'] = 'real_jewelry'
                        details['item_id'] = item_data.item_id
                        return details
                elif item_data.item_type == 'zakya_product':
                    details = self._get_zakya_details_by_id(item_data.item_id)
                    if details:
                        details['item_type'] = 'zakya_product'
                        details['item_id'] = item_data.item_id
                        return details
            
            # Method 2: Auto-detection by SKU
            if hasattr(item_data, 'sku') and item_data.sku:
                # Try real jewelry first
                details = self._get_real_jewelry_details_by_sku(item_data.sku)
                if details:
                    details['item_type'] = 'real_jewelry'
                    details['item_id'] = details.get('variant_id')  # Use variant_id as item_id
                    return details
                
                # Try Zakya products
                details = self._get_zakya_details_by_sku(item_data.sku)
                if details:
                    details['item_type'] = 'zakya_product'
                    details['item_id'] = details.get('item_id')
                    return details
            
            # Method 3: Legacy field conversion
            if hasattr(item_data, 'variant_id') and item_data.variant_id:
                # Check if it's actually a Zakya item_id (numeric string > 10 chars)
                if item_data.variant_id.isdigit() and len(item_data.variant_id) > 10:
                    details = self._get_zakya_details_by_id(item_data.variant_id)
                    if details:
                        details['item_type'] = 'zakya_product'
                        details['item_id'] = item_data.variant_id
                        return details
                else:
                    # Real jewelry variant
                    details = self._get_real_jewelry_details(item_data.variant_id)
                    if details:
                        details['item_type'] = 'real_jewelry'
                        details['item_id'] = item_data.variant_id
                        return details
            
            if hasattr(item_data, 'zakya_item_id') and item_data.zakya_item_id:
                details = self._get_zakya_details_by_id(item_data.zakya_item_id)
                if details:
                    details['item_type'] = 'zakya_product'
                    details['item_id'] = item_data.zakya_item_id
                    return details
            
            return None
            
        except Exception as e:
            print(f"❌ Error resolving item details: {e}")
            return None
    
    def _get_real_jewelry_details(self, variant_id: str) -> Optional[Dict[str, Any]]:
        """Get real jewelry details from billing_system_product_variants"""
        try:
            variant_query = f"""
                SELECT 
                    pv.id as variant_id,
                    pv.price, 
                    pv.sku, 
                    pv.weight_g as metal_weight_g,
                    pv.purity_k,
                    p.title as product_name,
                    p.description,
                    p.vendor
                FROM bs_product_variants pv
                JOIN bs_products p ON pv.product_id = p.id
                WHERE pv.id = '{variant_id}' AND pv.status = 'active'
            """
            variant_df = self.crud.execute_query(variant_query, return_data=True)
            
            if variant_df.empty:
                return None
            
            variant = variant_df.iloc[0]
            
            # Get metal breakdown
            metal_query = f"""
                SELECT metal_type, purity_k, weight_g, rate_per_g, metal_cost
                FROM bs_metal_components 
                WHERE variant_id = '{variant_id}'
            """
            metal_df = self.crud.execute_query(metal_query, return_data=True)
            metal_breakdown = metal_df.to_dict('records') if not metal_df.empty else []
            
            # Get stone breakdown
            stone_query = f"""
                SELECT stone_type, quantity, carat_weight, clarity, color, cut_grade, shape, stone_cost
                FROM bs_diamond_components 
                WHERE variant_id = '{variant_id}'
            """
            stone_df = self.crud.execute_query(stone_query, return_data=True)
            stone_breakdown = stone_df.to_dict('records') if not stone_df.empty else []
            
            return {
                'variant_id': variant['variant_id'],
                'price': variant['price'],
                'sku': variant['sku'],
                'product_name': variant['product_name'],
                'description': variant.get('description'),
                'vendor': variant.get('vendor'),
                'metal_weight_g': variant.get('metal_weight_g'),
                'purity_k': variant.get('purity_k'),
                'metal_breakdown': metal_breakdown,
                'stone_breakdown': stone_breakdown
            }
            
        except Exception as e:
            print(f"❌ Error fetching real jewelry details: {e}")
            return None
    
    def _get_real_jewelry_details_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """Get real jewelry details by SKU"""
        try:
            variant_query = f"""
                SELECT 
                    pv.id as variant_id,
                    pv.price, 
                    pv.sku, 
                    pv.weight_g as metal_weight_g,
                    pv.purity_k,
                    p.title as product_name,
                    p.description,
                    p.vendor
                FROM bs_product_variants pv
                JOIN bs_products p ON pv.product_id = p.id
                WHERE pv.sku = '{sku}' AND pv.status = 'active'
            """
            variant_df = self.crud.execute_query(variant_query, return_data=True)
            
            if variant_df.empty:
                return None
            
            variant = variant_df.iloc[0]
            return self._get_real_jewelry_details(variant['variant_id'])
            
        except Exception as e:
            print(f"❌ Error fetching real jewelry details by SKU: {e}")
            return None
    
    def _get_zakya_details_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get Zakya product details by item_id"""
        try:
            zakya_query = f"""
                SELECT rate as price, sku, name as product_name, item_id, stock_on_hand
                FROM zakya_products 
                WHERE item_id = '{item_id}'
            """
            zakya_df = self.crud.execute_query(zakya_query, return_data=True)
            
            if zakya_df.empty:
                return None
            
            zakya_item = zakya_df.iloc[0]
            return {
                'price': zakya_item['price'] or 0,
                'sku': zakya_item['sku'] or item_id,
                'product_name': zakya_item['product_name'] or 'Zakya Product',
                'item_id': zakya_item['item_id'],
                'stock_on_hand': zakya_item['stock_on_hand'] or 0
            }
            
        except Exception as e:
            print(f"❌ Error fetching Zakya details by ID: {e}")
            return None
    
    def _get_zakya_details_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """Get Zakya product details by SKU"""
        try:
            zakya_query = f"""
                SELECT rate as price, sku, name as product_name, item_id, stock_on_hand
                FROM zakya_products 
                WHERE sku = '{sku}'
            """
            zakya_df = self.crud.execute_query(zakya_query, return_data=True)
            
            if zakya_df.empty:
                return None
            
            zakya_item = zakya_df.iloc[0]
            return {
                'price': zakya_item['price'] or 0,
                'sku': zakya_item['sku'] or sku,
                'product_name': zakya_item['product_name'] or 'Zakya Product',
                'item_id': zakya_item['item_id'],
                'stock_on_hand': zakya_item['stock_on_hand'] or 0
            }
            
        except Exception as e:
            print(f"❌ Error fetching Zakya details by SKU: {e}")
            return None
    
    def apply_discount_to_cart(
        self, 
        cart_id: str,
        discount_code: str
    ) -> Dict[str, Any]:
        """Apply discount code to cart"""
        try:
            # Get discount
            discount_query = f"""
                SELECT * FROM billing_system_discounts 
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
                UPDATE billing_system_carts
                SET discount_amount = {discount_amount}
                WHERE id = '{cart_id}'
            """
            self.crud.execute_query_new(update_query)
            
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
            FROM billing_system_cart_items
            WHERE cart_id = '{cart_id}'
        """
        items_df = self.crud.execute_query(items_query, return_data=True)
        print(f"Reclalculating totals for cart {cart_id} and items_df: {items_df}")
        
        subtotal = float(items_df.iloc[0]['subtotal']) if not items_df.empty else 0
        
        # Get cart for discount and tax
        cart_query = f"SELECT discount_amount, tax_rate_percent FROM billing_system_carts WHERE id = '{cart_id}'"
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
            UPDATE billing_system_carts
            SET subtotal = {subtotal},
                tax_amount = {tax_amount},
                total_amount = {total_amount},
                updated_at = CURRENT_TIMESTAMP
            WHERE id = '{cart_id}'
        """
        
        print(f"Updating cart totals with query: {update_query}")
        
        self.crud.execute_query_new(update_query)