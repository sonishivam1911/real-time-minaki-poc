"""
Customer Service - Business logic for customer management using customer_master table
"""
from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime

from core.database import db
from core.config import settings
from utils.schema.billing_system.checkout_schema import CustomerCreate, CustomerUpdate


class CustomerService:
    """Service for customer-related business logic"""
    
    def __init__(self):
        self.crud = db
    
    def create_customer(self, customer_data: CustomerCreate) -> Dict[str, Any]:
        """
        Create a new customer in customer_master table.
        
        Args:
            customer_data: Customer creation data
        
        Returns:
            Created customer data
        """
        try:
            # Generate customer number
            customer_number = self._generate_customer_number()
            
            # Get next contact ID
            contact_id = self._get_next_contact_id()
            
            # Map checkout schema to customer_master fields
            customer_record = {
                'Created Time': datetime.utcnow().isoformat(),
                'Last Modified Time': datetime.utcnow().isoformat(),
                'Contact ID': contact_id,
                'Contact Type': 'customer',
                'Customer Number': customer_number,
                'Customer Sub Type': customer_data.customer_type if hasattr(customer_data, 'customer_type') else 'regular',
                'Contact Name': customer_data.full_name,
                'Display Name': customer_data.full_name,
                'First Name': customer_data.full_name.split(' ')[0] if ' ' in customer_data.full_name else customer_data.full_name,
                'Last Name': ' '.join(customer_data.full_name.split(' ')[1:]) if ' ' in customer_data.full_name else '',
                'EmailID': customer_data.email,
                'Phone': customer_data.phone,
                'MobilePhone': customer_data.phone,
                'Billing Address': customer_data.address if hasattr(customer_data, 'address') else None,
                'Billing City': customer_data.city if hasattr(customer_data, 'city') else None,
                'Billing State': customer_data.state if hasattr(customer_data, 'state') else None,
                'Billing Code': customer_data.postal_code if hasattr(customer_data, 'postal_code') else None,
                'Shipping Address': customer_data.address if hasattr(customer_data, 'address') else None,
                'Shipping City': customer_data.city if hasattr(customer_data, 'city') else None,
                'Shipping State': customer_data.state if hasattr(customer_data, 'state') else None,
                'Shipping Code': customer_data.postal_code if hasattr(customer_data, 'postal_code') else None,
                'Currency Code': 'INR',
                'Status': 'Active',
                'Taxable': True
            }
            
            # Add notes if provided
            if hasattr(customer_data, 'notes') and customer_data.notes:
                # Since Notes is double precision in schema, we'll handle it differently
                pass  # Will store notes in a separate field or modify schema
            
            self.crud.insert_record('customer_master', customer_record)
            
            return {
                'success': True,
                'contact_id': contact_id,
                'customer_number': customer_number,
                'customer_data': customer_record
            }
            
        except Exception as e:
            print(f"❌ Error creating customer: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_customer_number(self) -> str:
        """Generate unique customer number"""
        # Get count of customers from customer_master
        count_query = 'SELECT COUNT(*) as count FROM customer_master'
        count_df = self.crud.execute_query(count_query, return_data=True)
        count = int(count_df.iloc[0]['count']) if not count_df.empty else 0
        
        # Format: CUST-0001, CUST-0002, etc.
        return f"CUST-{str(count + 1).zfill(4)}"
    
    def _get_next_contact_id(self) -> int:
        """Get next contact ID"""
        # Get max contact ID from customer_master
        query = 'SELECT COALESCE(MAX("Contact ID"), 0) as max_id FROM customer_master'
        df = self.crud.execute_query(query, return_data=True)
        max_id = int(df.iloc[0]['max_id']) if not df.empty else 0
        
        return max_id + 1
    
    def get_all_customers(
        self, 
    ) -> List[Dict[str, Any]]:
        """Get list of customers with pagination"""
        try:
            query = f'''
                SELECT * FROM customer_master 
                WHERE "Customer Sub Type" = 'individual'
                ORDER BY "Created Time" DESC
            '''
            
            df = self.crud.execute_query(query, return_data=True)
            return df.to_dict('records') if not df.empty else []
            
        except Exception as e:
            print(f"❌ Error fetching customers: {e}")
            return []
    
    def get_customer_by_id(self, contact_id: str) -> Optional[Dict[str, Any]]:
        """Get customer by Contact ID from customer_master"""
        query = f'SELECT * FROM customer_master WHERE "Contact ID" = {contact_id}'
        df = self.crud.execute_query(query, return_data=True)
        
        if df.empty:
            return None
        
        return df.iloc[0].to_dict()
    
    def get_customer_by_number(self, customer_number: str) -> Optional[Dict[str, Any]]:
        """Get customer by Customer Number from customer_master"""
        query = f'SELECT * FROM customer_master WHERE "Customer Number" = \'{customer_number}\''
        df = self.crud.execute_query(query, return_data=True)
        
        if df.empty:
            return None
        
        return df.iloc[0].to_dict()
    
    def search_customers(
        self,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        name: Optional[str] = None,
        customer_number: Optional[str] = None,
        contact_id: Optional[int] = None,
        gstin: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search customers by various criteria in customer_master table.
        
        Args:
            phone: Search by phone number
            email: Search by email
            name: Search by name (partial match)
            customer_number: Search by customer number
            contact_id: Search by contact ID
            gstin: Search by GST number
        
        Returns:
            List of matching customers
        """
        where_clauses = []
        
        if phone:
            where_clauses.append(f'"Phone" ILIKE \'%{phone}%\' OR "MobilePhone" ILIKE \'%{phone}%\'')
        
        if email:
            where_clauses.append(f'"EmailID" ILIKE \'%{email}%\'')
        
        if name:
            where_clauses.append(f'"Contact Name" ILIKE \'%{name}%\' OR "Display Name" ILIKE \'%{name}%\'')
        
        if customer_number:
            where_clauses.append(f'"Customer Number" = \'{customer_number}\'')
        
        if contact_id:
            where_clauses.append(f'"Contact ID" = {contact_id}')
        
        if gstin:
            where_clauses.append(f'"GST Identification Number (GSTIN)" ILIKE \'%{gstin}%\'')
        
        if not where_clauses:
            # Return recent customers if no search criteria
            query = '''
                SELECT * FROM customer_master 
                WHERE "Status" = 'Active'
                ORDER BY "Created Time" DESC 
                LIMIT 50
            '''
        else:
            where_str = " AND ".join(where_clauses)
            query = f'''
                SELECT * FROM customer_master 
                WHERE ({where_str}) AND "Status" = 'Active'
                ORDER BY "Created Time" DESC
                LIMIT 50
            '''
        
        df = self.crud.execute_query(query, return_data=True)
        return df.to_dict('records')
    
    def update_customer(
        self, 
        contact_id: int, 
        update_data: CustomerUpdate
    ) -> Dict[str, Any]:
        """Update customer information in customer_master table"""
        try:
            # Check if customer exists
            customer = self.get_customer_by_id(str(contact_id))
            if not customer:
                return {
                    'success': False,
                    'error': 'Customer not found'
                }
            
            # Build update dict mapping to customer_master fields
            updates = {}
            
            if update_data.full_name:
                updates['"Contact Name"'] = f"'{update_data.full_name}'"
                updates['"Display Name"'] = f"'{update_data.full_name}'"
                # Split full name for first and last name
                name_parts = update_data.full_name.split(' ', 1)
                updates['"First Name"'] = f"'{name_parts[0]}'"
                if len(name_parts) > 1:
                    updates['"Last Name"'] = f"'{name_parts[1]}'"
            
            if update_data.email:
                updates['"EmailID"'] = f"'{update_data.email}'"
            
            if update_data.phone:
                updates['"Phone"'] = f"'{update_data.phone}'"
                updates['"MobilePhone"'] = f"'{update_data.phone}'"
            
            if hasattr(update_data, 'address') and update_data.address:
                updates['"Billing Address"'] = f"'{update_data.address}'"
                updates['"Shipping Address"'] = f"'{update_data.address}'"
            
            if hasattr(update_data, 'city') and update_data.city:
                updates['"Billing City"'] = f"'{update_data.city}'"
                updates['"Shipping City"'] = f"'{update_data.city}'"
            
            if hasattr(update_data, 'state') and update_data.state:
                updates['"Billing State"'] = f"'{update_data.state}'"
                updates['"Shipping State"'] = f"'{update_data.state}'"
            
            if hasattr(update_data, 'postal_code') and update_data.postal_code:
                updates['"Billing Code"'] = f"'{update_data.postal_code}'"
                updates['"Shipping Code"'] = f"'{update_data.postal_code}'"
            
            if hasattr(update_data, 'customer_type') and update_data.customer_type:
                updates['"Customer Sub Type"'] = f"'{update_data.customer_type}'"
            
            if not updates:
                return {
                    'success': False,
                    'error': 'No fields to update'
                }
            
            # Always update last modified time
            updates['"Last Modified Time"'] = f"'{datetime.utcnow().isoformat()}'"
            
            # Build update query
            set_clause = ", ".join([f"{key} = {value}" for key, value in updates.items()])
            query = f'UPDATE customer_master SET {set_clause} WHERE "Contact ID" = {contact_id}'
            
            success = self.crud.execute_query_new(query)
            
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
        contact_id: int
    ) -> List[Dict[str, Any]]:
        """Get customer's purchase history"""
        # Note: This assumes invoices table uses Contact ID to link to customer_master
        query = f"""
            SELECT 
                si.invoice_number,
                si.invoice_date,
                si.total_amount,
                si.payment_status,
                si.paid_amount,
                si.outstanding_amount
            FROM sales_invoices si
            WHERE si.customer_contact_id = {contact_id}
            ORDER BY si.invoice_date DESC
            LIMIT 50
        """
        
        df = self.crud.execute_query(query, return_data=True)
        return df.to_dict('records')
    
    def update_customer_gst_info(
        self, 
        contact_id: int, 
        gstin: str,
        gst_treatment: str = "Regular"
    ) -> bool:
        """Update customer's GST information"""
        try:
            query = f"""
                UPDATE customer_master
                SET "GST Identification Number (GSTIN)" = '{gstin}',
                    "GST Treatment" = '{gst_treatment}',
                    "Taxable" = true,
                    "Last Modified Time" = '{datetime.utcnow().isoformat()}'
                WHERE "Contact ID" = {contact_id}
            """
            
            return self.crud.execute_query_new(query)
            
        except Exception as e:
            print(f"❌ Error updating GST info: {e}")
            return False
    
    def update_customer_status(
        self, 
        contact_id: int, 
        status: str
    ) -> bool:
        """Update customer status (Active/Inactive)"""
        try:
            query = f"""
                UPDATE customer_master
                SET "Status" = '{status}',
                    "Last Modified Time" = '{datetime.utcnow().isoformat()}'
                WHERE "Contact ID" = {contact_id}
            """
            
            return self.crud.execute_query_new(query)
            
        except Exception as e:
            print(f"❌ Error updating customer status: {e}")
            return False
    
    def get_customers_by_location(
        self, 
        state: Optional[str] = None, 
        city: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get customers by location"""
        where_clauses = ['"Status" = \'Active\'']
        
        if state:
            where_clauses.append(f'"Billing State" ILIKE \'%{state}%\'')
        
        if city:
            where_clauses.append(f'"Billing City" ILIKE \'%{city}%\'')
        
        where_str = " AND ".join(where_clauses)
        query = f"""
            SELECT * FROM customer_master 
            WHERE {where_str}
            ORDER BY "Contact Name"
            LIMIT 100
        """
        
        df = self.crud.execute_query(query, return_data=True)
        return df.to_dict('records')