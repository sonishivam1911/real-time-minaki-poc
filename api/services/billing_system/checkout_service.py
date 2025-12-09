"""
Checkout Service - Business logic for checkout and payment processing
"""
from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime, date
from decimal import Decimal

from core.database import db
from core.config import settings
from utils.schema.billing_system.checkout_schema import CheckoutRequest, PaymentCreate


class CheckoutService:
    """Service for checkout and payment processing"""
    
    def __init__(self):
        self.crud = db
    
    def process_checkout(
        self, 
        checkout_data: CheckoutRequest
    ) -> Dict[str, Any]:
        """
        Process complete checkout: create invoice, record payments, update stock.
        
        Args:
            checkout_data: Checkout request data
        
        Returns:
            Result dictionary with invoice details
        """
        try:
            # 1. Get cart
            cart = self._get_cart(checkout_data.cart_id)
            if not cart:
                return {
                    'success': False,
                    'error': 'Cart not found'
                }
            
            if not cart['items']:
                return {
                    'success': False,
                    'error': 'Cart is empty'
                }
            
            # 2. Apply discount if provided
            if checkout_data.discount_code:
                discount_result = self._apply_discount(
                    checkout_data.cart_id, 
                    checkout_data.discount_code
                )
                if not discount_result['success']:
                    return discount_result
                
                # Refresh cart
                cart = self._get_cart(checkout_data.cart_id)
            
            # 3. Apply tax rate
            if checkout_data.tax_rate_percent > 0:
                self._update_cart_tax(checkout_data.cart_id, float(checkout_data.tax_rate_percent))
                cart = self._get_cart(checkout_data.cart_id)
            
            # 4. Validate payment amounts
            total_payment = sum(float(p.payment_amount) for p in checkout_data.payments)
            cart_total = float(cart['total_amount'])
            
            if total_payment < cart_total:
                return {
                    'success': False,
                    'error': f'Insufficient payment. Total: {cart_total}, Paid: {total_payment}'
                }
            
            # 5. Create invoice
            invoice_result = self._create_invoice(cart, checkout_data)
            if not invoice_result['success']:
                return invoice_result
            
            invoice_id = invoice_result['invoice_id']
            
            # 6. Record payments
            payment_result = self._record_payments(
                invoice_id,
                checkout_data.customer_id,
                checkout_data.payments
            )
            if not payment_result['success']:
                return payment_result
            
            # 7. Update stock items
            stock_result = self._update_stock_items(cart['items'])
            if not stock_result['success']:
                return stock_result
            
            # 8. Update cart status
            self._update_cart_status(checkout_data.cart_id, 'converted')
            
            # 9. Update customer loyalty points (if applicable)
            if checkout_data.customer_id:
                self._update_customer_loyalty(checkout_data.customer_id, cart_total)
            
            return {
                'success': True,
                'invoice_id': invoice_id,
                'invoice_number': invoice_result['invoice_number'],
                'total_amount': cart_total,
                'paid_amount': total_payment,
                'outstanding_amount': max(0, cart_total - total_payment),
                'payment_status': 'paid' if total_payment >= cart_total else 'partial',
                'message': 'Checkout completed successfully'
            }
            
        except Exception as e:
            print(f"❌ Error processing checkout: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_cart(self, cart_id: str) -> Optional[Dict[str, Any]]:
        """Get cart with items"""
        cart_query = f"SELECT * FROM carts WHERE id = '{cart_id}'"
        cart_df = self.crud.execute_query(cart_query, return_data=True)
        
        if cart_df.empty:
            return None
        
        cart = cart_df.iloc[0].to_dict()
        
        items_query = f"SELECT * FROM cart_items WHERE cart_id = '{cart_id}'"
        items_df = self.crud.execute_query(items_query, return_data=True)
        
        cart['items'] = items_df.to_dict('records')
        
        return cart
    
    def _apply_discount(self, cart_id: str, discount_code: str) -> Dict[str, Any]:
        """Apply discount code"""
        # Get discount
        discount_query = f"""
            SELECT * FROM discounts 
            WHERE discount_code = '{discount_code}'
            AND is_active = true
        """
        discount_df = self.crud.execute_query(discount_query, return_data=True)
        
        if discount_df.empty:
            return {
                'success': False,
                'error': 'Invalid discount code'
            }
        
        discount = discount_df.iloc[0]
        
        # Get cart
        cart_query = f"SELECT subtotal FROM carts WHERE id = '{cart_id}'"
        cart_df = self.crud.execute_query(cart_query, return_data=True)
        subtotal = float(cart_df.iloc[0]['subtotal'])
        
        # Calculate discount
        if discount['discount_type'] == 'percentage':
            discount_amount = subtotal * (float(discount['discount_value']) / 100)
        else:
            discount_amount = float(discount['discount_value'])
        
        if discount['max_discount_amount']:
            discount_amount = min(discount_amount, float(discount['max_discount_amount']))
        
        # Update cart
        update_query = f"""
            UPDATE carts
            SET discount_amount = {discount_amount}
            WHERE id = '{cart_id}'
        """
        self.crud.execute_query(update_query)
        
        return {'success': True}
    
    def _update_cart_tax(self, cart_id: str, tax_rate: float):
        """Update cart tax rate and recalculate"""
        # Get cart
        cart_query = f"SELECT subtotal, discount_amount FROM carts WHERE id = '{cart_id}'"
        cart_df = self.crud.execute_query(cart_query, return_data=True)
        
        subtotal = float(cart_df.iloc[0]['subtotal'])
        discount_amount = float(cart_df.iloc[0]['discount_amount'])
        
        taxable_amount = subtotal - discount_amount
        tax_amount = taxable_amount * (tax_rate / 100)
        total_amount = taxable_amount + tax_amount
        
        update_query = f"""
            UPDATE carts
            SET tax_rate_percent = {tax_rate},
                tax_amount = {tax_amount},
                total_amount = {total_amount}
            WHERE id = '{cart_id}'
        """
        self.crud.execute_query(update_query)
    
    def _create_invoice(
        self, 
        cart: Dict[str, Any],
        checkout_data: CheckoutRequest
    ) -> Dict[str, Any]:
        """Create sales invoice from cart"""
        try:
            invoice_id = str(uuid4())
            invoice_number = self._generate_invoice_number()
            
            invoice_record = {
                'id': invoice_id,
                'invoice_number': invoice_number,
                'customer_id': checkout_data.customer_id,
                'cart_id': checkout_data.cart_id,
                'invoice_date': datetime.utcnow(),
                'due_date': None,
                'subtotal': float(cart['subtotal']),
                'discount_amount': float(cart['discount_amount']),
                'tax_rate_percent': float(cart['tax_rate_percent']),
                'tax_amount': float(cart['tax_amount']),
                'total_amount': float(cart['total_amount']),
                'payment_status': 'pending',
                'paid_amount': 0,
                'outstanding_amount': float(cart['total_amount']),
                'notes': checkout_data.notes,
                'sales_person': checkout_data.sales_person,
                'created_at': datetime.utcnow()
            }
            
            self.crud.insert_record('sales_invoices', invoice_record)
            
            # Create invoice items
            for item in cart['items']:
                invoice_item_id = str(uuid4())
                
                invoice_item_record = {
                    'id': invoice_item_id,
                    'invoice_id': invoice_id,
                    'variant_id': item['variant_id'],
                    'stock_item_id': item['stock_item_id'],
                    'product_name': item['product_name'],
                    'sku': item['sku'],
                    'serial_no': item['serial_no'],
                    'quantity': int(item['quantity']),
                    'unit_price': float(item['unit_price']),
                    'discount_percent': float(item['discount_percent']),
                    'discount_amount': float(item['discount_amount']),
                    'line_total': float(item['line_total']),
                    'created_at': datetime.utcnow()
                }
                
                self.crud.insert_record('invoice_items', invoice_item_record)
            
            return {
                'success': True,
                'invoice_id': invoice_id,
                'invoice_number': invoice_number
            }
            
        except Exception as e:
            print(f"❌ Error creating invoice: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_invoice_number(self) -> str:
        """Generate unique invoice number"""
        # Get count
        count_query = "SELECT COUNT(*) as count FROM sales_invoices"
        count_df = self.crud.execute_query(count_query, return_data=True)
        count = int(count_df.iloc[0]['count']) if not count_df.empty else 0
        
        # Format: INV-2024-0001
        year = datetime.now().year
        return f"INV-{year}-{str(count + 1).zfill(4)}"
    
    def _record_payments(
        self,
        invoice_id: str,
        customer_id: Optional[str],
        payments: List[PaymentCreate]
    ) -> Dict[str, Any]:
        """Record payments for invoice"""
        try:
            total_paid = 0
            
            for payment in payments:
                payment_id = str(uuid4())
                payment_number = self._generate_payment_number()
                
                payment_record = {
                    'id': payment_id,
                    'payment_number': payment_number,
                    'invoice_id': invoice_id,
                    'customer_id': customer_id,
                    'payment_date': datetime.utcnow(),
                    'payment_method': payment.payment_method,
                    'payment_amount': float(payment.payment_amount),
                    'card_type': payment.card_type,
                    'card_last_four': payment.card_last_four,
                    'transaction_id': payment.transaction_id,
                    'bank_name': payment.bank_name,
                    'cheque_number': payment.cheque_number,
                    'cheque_date': payment.cheque_date,
                    'upi_id': payment.upi_id,
                    'payment_status': 'completed',
                    'notes': payment.notes,
                    'created_at': datetime.utcnow()
                }
                
                self.crud.insert_record('payments', payment_record)
                total_paid += float(payment.payment_amount)
            
            # Update invoice payment status
            invoice_query = f"SELECT total_amount FROM sales_invoices WHERE id = '{invoice_id}'"
            invoice_df = self.crud.execute_query(invoice_query, return_data=True)
            total_amount = float(invoice_df.iloc[0]['total_amount'])
            
            outstanding = max(0, total_amount - total_paid)
            
            if outstanding == 0:
                payment_status = 'paid'
            elif total_paid > 0:
                payment_status = 'partial'
            else:
                payment_status = 'pending'
            
            update_query = f"""
                UPDATE sales_invoices
                SET paid_amount = {total_paid},
                    outstanding_amount = {outstanding},
                    payment_status = '{payment_status}'
                WHERE id = '{invoice_id}'
            """
            self.crud.execute_query(update_query)
            
            return {'success': True}
            
        except Exception as e:
            print(f"❌ Error recording payments: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_payment_number(self) -> str:
        """Generate unique payment number"""
        count_query = "SELECT COUNT(*) as count FROM payments"
        count_df = self.crud.execute_query(count_query, return_data=True)
        count = int(count_df.iloc[0]['count']) if not count_df.empty else 0
        
        return f"PAY-{str(count + 1).zfill(6)}"
    
    def _update_stock_items(self, cart_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update stock items to sold"""
        try:
            for item in cart_items:
                if item['stock_item_id']:
                    # Update stock item status
                    update_query = f"""
                        UPDATE stock_items
                        SET status = 'sold',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = '{item['stock_item_id']}'
                    """
                    self.crud.execute_query(update_query)
                    
                    # Create stock movement
                    movement_id = str(uuid4())
                    movement_record = {
                        'id': movement_id,
                        'stock_item_id': item['stock_item_id'],
                        'variant_id': item['variant_id'],
                        'movement_type': 'sale',
                        'qty': int(item['quantity']),
                        'reference': f"Sale",
                        'performed_at': datetime.utcnow()
                    }
                    self.crud.insert_record('stock_movements', movement_record)
            
            return {'success': True}
            
        except Exception as e:
            print(f"❌ Error updating stock: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _update_cart_status(self, cart_id: str, status: str):
        """Update cart status"""
        query = f"""
            UPDATE carts
            SET status = '{status}',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = '{cart_id}'
        """
        self.crud.execute_query(query)
    
    def _update_customer_loyalty(self, customer_id: str, amount: float):
        """Update customer loyalty points (1 point per 100 spent)"""
        points = int(amount / 100)
        
        if points > 0:
            query = f"""
                UPDATE customers
                SET loyalty_points = loyalty_points + {points}
                WHERE id = '{customer_id}'
            """
            self.crud.execute_query(query)
    
    def hold_transaction(self, cart_id: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """Hold transaction for later completion"""
        try:
            query = f"""
                UPDATE carts
                SET status = 'held',
                    notes = '{notes if notes else ""}',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = '{cart_id}'
            """
            
            self.crud.execute_query(query)
            
            return {
                'success': True,
                'message': 'Transaction held successfully'
            }
            
        except Exception as e:
            print(f"❌ Error holding transaction: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_held_transactions(self) -> List[Dict[str, Any]]:
        """Get all held transactions"""
        query = """
            SELECT c.*, cu.full_name as customer_name
            FROM carts c
            LEFT JOIN customers cu ON c.customer_id = cu.id
            WHERE c.status = 'held'
            ORDER BY c.updated_at DESC
        """
        
        df = self.crud.execute_query(query, return_data=True)
        return df.to_dict('records')