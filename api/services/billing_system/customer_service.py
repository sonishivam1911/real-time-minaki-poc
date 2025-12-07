"""
Customer Service - Business logic for customer management
"""
from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime

from core.database import PostgresCRUD
from core.config import settings
from utils.schema.billing_system.checkout_schema import CustomerCreate, CustomerUpdate


class CustomerService:
    """Service for customer-related business logic"""
    
    def __init__(self):
        self.crud = PostgresCRUD(settings.POSTGRES_URI)
    
    def create_customer(self, customer_data: CustomerCreate) -> Dict[str, Any]:
        """
        Create a new customer.
        
        Args:
            customer_data: Customer creation data
        
        Returns:
            Created customer data
        """
        try:
            customer_id = str(uuid4())
            
            # Generate customer code
            customer_code = self._generate_customer_code()
            
            customer_record = {
                'id': customer_id,
                'customer_code': customer_code,
                'full_name': customer_data.full_name,
                'email': customer_data.email,
                'phone': customer_data.phone,
                'address': customer_data.address,
                'city': customer_data.city,
                'state': customer_data.state,
                'postal_code': customer_data.postal_code,
                'customer_type': customer_data.customer_type,
                'credit_limit': 0,
                'outstanding_balance': 0,
                'loyalty_points': 0,
                'notes': customer_data.notes,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            self.crud.insert_record('customers', customer_record)
            
            return {
                'success': True,
                'customer_id': customer_id,
                'customer_code': customer_code
            }
            
        except Exception as e:
            print(f"❌ Error creating customer: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_customer_code(self) -> str:
        """Generate unique customer code"""
        # Get count of customers
        count_query = "SELECT COUNT(*) as count FROM customers"
        count_df = self.crud.execute_query(count_query, return_data=True)
        count = int(count_df.iloc[0]['count']) if not count_df.empty else 0
        
        # Format: CUST-0001, CUST-0002, etc.
        return f"CUST-{str(count + 1).zfill(4)}"
    
    def get_customer_by_id(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get customer by ID"""
        query = f"SELECT * FROM customers WHERE id = '{customer_id}'"
        df = self.crud.execute_query(query, return_data=True)
        
        if df.empty:
            return None
        
        return df.iloc[0].to_dict()
    
    def search_customers(
        self,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        name: Optional[str] = None,
        customer_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search customers by various criteria.
        
        Args:
            phone: Search by phone number
            email: Search by email
            name: Search by name (partial match)
            customer_code: Search by customer code
        
        Returns:
            List of matching customers
        """
        where_clauses = []
        
        if phone:
            where_clauses.append(f"phone LIKE '%{phone}%'")
        
        if email:
            where_clauses.append(f"email ILIKE '%{email}%'")
        
        if name:
            where_clauses.append(f"full_name ILIKE '%{name}%'")
        
        if customer_code:
            where_clauses.append(f"customer_code = '{customer_code}'")
        
        if not where_clauses:
            # Return recent customers if no search criteria
            query = """
                SELECT * FROM customers 
                ORDER BY created_at DESC 
                LIMIT 50
            """
        else:
            where_str = " AND ".join(where_clauses)
            query = f"""
                SELECT * FROM customers 
                WHERE {where_str}
                ORDER BY created_at DESC
                LIMIT 50
            """
        
        df = self.crud.execute_query(query, return_data=True)
        return df.to_dict('records')
    
    def update_customer(
        self, 
        customer_id: str, 
        update_data: CustomerUpdate
    ) -> Dict[str, Any]:
        """Update customer information"""
        try:
            # Check if customer exists
            customer = self.get_customer_by_id(customer_id)
            if not customer:
                return {
                    'success': False,
                    'error': 'Customer not found'
                }
            
            # Build update dict
            updates = {}
            if update_data.full_name:
                updates['full_name'] = update_data.full_name
            if update_data.email:
                updates['email'] = update_data.email
            if update_data.phone:
                updates['phone'] = update_data.phone
            if update_data.address:
                updates['address'] = update_data.address
            if update_data.city:
                updates['city'] = update_data.city
            if update_data.state:
                updates['state'] = update_data.state
            if update_data.postal_code:
                updates['postal_code'] = update_data.postal_code
            if update_data.customer_type:
                updates['customer_type'] = update_data.customer_type
            if update_data.notes:
                updates['notes'] = update_data.notes
            
            if not updates:
                return {
                    'success': False,
                    'error': 'No fields to update'
                }
            
            updates['updated_at'] = datetime.utcnow()
            
            # Update customer
            success = self.crud.update_record(
                'customers',
                customer_id,
                'id',
                updates
            )
            
            if success:
                return {
                    'success': True,
                    'message': 'Customer updated successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to update customer'
                }
                
        except Exception as e:
            print(f"❌ Error updating customer: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_customer_purchase_history(
        self, 
        customer_id: str
    ) -> List[Dict[str, Any]]:
        """Get customer's purchase history"""
        query = f"""
            SELECT 
                si.invoice_number,
                si.invoice_date,
                si.total_amount,
                si.payment_status,
                si.paid_amount,
                si.outstanding_amount
            FROM sales_invoices si
            WHERE si.customer_id = '{customer_id}'
            ORDER BY si.invoice_date DESC
            LIMIT 50
        """
        
        df = self.crud.execute_query(query, return_data=True)
        return df.to_dict('records')
    
    def update_loyalty_points(
        self, 
        customer_id: str, 
        points: int
    ) -> bool:
        """Add or subtract loyalty points"""
        try:
            # Get current points
            customer = self.get_customer_by_id(customer_id)
            if not customer:
                return False
            
            current_points = customer.get('loyalty_points', 0)
            new_points = max(0, current_points + points)  # Can't go negative
            
            query = f"""
                UPDATE customers
                SET loyalty_points = {new_points},
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = '{customer_id}'
            """
            
            return self.crud.execute_query(query)
            
        except Exception as e:
            print(f"❌ Error updating loyalty points: {e}")
            return False
    
    def update_outstanding_balance(
        self, 
        customer_id: str, 
        amount: float
    ) -> bool:
        """Update customer's outstanding balance"""
        try:
            query = f"""
                UPDATE customers
                SET outstanding_balance = outstanding_balance + {amount},
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = '{customer_id}'
            """
            
            return self.crud.execute_query(query)
            
        except Exception as e:
            print(f"❌ Error updating outstanding balance: {e}")
            return False