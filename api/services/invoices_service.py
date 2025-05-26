import pandas as pd
from core.database import db
from services.zakya_service import zakya_service

class InvoiceService:
    @staticmethod
    async def process_invoice_webhook(invoice_id, action):
        """
        Process webhook notification for an invoice.
        
        Args:
            invoice_id (str): The ID of the invoice
            action (str): The action performed (create, update, delete)
        
        Returns:
            dict: Status of the operation
        """
        try:
            # Define table name constant
            table_name = "invoice_line_item_mapping"
            
            # Check if table exists using information_schema
            table_exists_query = f"""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '{table_name}'
                );
            """
            result_df = db.execute_query(table_exists_query, return_data=True)
            table_exists = result_df.iloc[0, 0] if not result_df.empty else False
            
            if action == "delete":
                # For delete, just remove from database if table exists
                if table_exists:
                    result = db.execute_query(
                        f"DELETE FROM \"{table_name}\" WHERE invoice_id = '{invoice_id}'"
                    )
                    return {"success": result, "message": f"Invoice {invoice_id} deleted"}
                else:
                    return {"success": True, "message": f"No invoice {invoice_id} to delete (table doesn't exist)"}
            
            elif action in ["create", "update"]:
                # For create or update, fetch the latest data from Zakya
                invoice_data = await zakya_service.fetch_object_by_id("invoices", invoice_id)
                
                if not invoice_data or "invoice" not in invoice_data:
                    return {"success": False, "message": f"Failed to fetch invoice {invoice_id}"}
                
                # Process the invoice data into line items
                line_item_records = []
                
                invoice = invoice_data["invoice"]
                line_items = invoice.get("line_items", [])
                
                for line_item in line_items:
                    line_item_record = {
                        # Invoice fields
                        'invoice_id': invoice_id,
                        'invoice_number': invoice.get('invoice_number', ''),
                        'date': invoice.get('date', ''),
                        'status': invoice.get('status', ''),
                        'customer_id': invoice.get('customer_id', ''),
                        'customer_name': invoice.get('customer_name', ''),
                        'currency_code': invoice.get('currency_code', ''),
                        
                        # Line item fields
                        'line_item_id': line_item.get('line_item_id', ''),
                        'item_id': line_item.get('item_id', ''),
                        'name': line_item.get('name', ''),
                        'description': line_item.get('description', ''),
                        'item_order': line_item.get('item_order', 0),
                        'quantity': line_item.get('quantity', 0),
                        'unit': line_item.get('unit', ''),
                        'rate': line_item.get('rate', 0),
                        'bcy_rate': line_item.get('bcy_rate', 0),
                        
                        # Tax fields
                        'tax_id': line_item.get('tax_id', ''),
                        'tax_name': line_item.get('tax_name', ''),
                        'tax_percentage': line_item.get('tax_percentage', 0),
                        'tax_type': line_item.get('tax_type', ''),
                        
                        # Financial fields
                        'discount': line_item.get('discount', 0),
                        'discount_amount': line_item.get('discount_amount', 0),
                        'item_total': line_item.get('item_total', 0),
                        
                        # Additional fields
                        'hsn_or_sac': line_item.get('hsn_or_sac', ''),
                        'project_id': line_item.get('project_id', ''),
                        'warehouse_id': line_item.get('warehouse_id', '')
                    }
                    
                    line_item_records.append(line_item_record)
                
                # Handle database operations
                if not line_item_records:
                    return {"success": False, "message": f"No line items found for invoice {invoice_id}"}
                
                # Convert records to DataFrame for easier manipulation
                line_items_df = pd.DataFrame(line_item_records)
                
                if not table_exists:
                    # If table doesn't exist, create it using the DataFrame
                    success = db.create_table(table_name, line_items_df)
                    if not success:
                        return {"success": False, "message": f"Failed to create {table_name} table"}
                    
                    return {
                        "success": True, 
                        "message": f"Invoice {invoice_id} {action}d successfully (created table)",
                        "details": {
                            "line_items_count": len(line_item_records),
                            "invoice_number": invoice.get('invoice_number', '')
                        }
                    }
                else:
                    # Table exists, handle based on action
                    if action == "create":
                        # Generate and execute INSERT statements
                        insert_statements = db.create_insert_statements(line_items_df, table_name)
                        
                        # Execute each statement
                        for stmt in insert_statements:
                            db.execute_query(stmt)
                        
                        return {
                            "success": True, 
                            "message": f"Invoice {invoice_id} created successfully",
                            "details": {
                                "line_items_count": len(line_item_records),
                                "invoice_number": invoice.get('invoice_number', '')
                            }
                        }
                    
                    elif action == "update":
                        # For update, first delete existing records for this invoice
                        db.execute_query(f"DELETE FROM \"{table_name}\" WHERE invoice_id = '{invoice_id}'")
                        
                        # Define which columns uniquely identify a line item
                        id_columns = ['invoice_id', 'line_item_id']

                        # Generate update statements
                        update_statements = db.create_update_statements(line_items_df, table_name, id_columns)

                        # Execute each statement
                        for stmt in update_statements:
                            db.execute_query(stmt)
                        
                        return {
                            "success": True, 
                            "message": f"Invoice {invoice_id} updated successfully",
                            "details": {
                                "line_items_count": len(line_item_records),
                                "invoice_number": invoice.get('invoice_number', '')
                            }
                        }
            
            else:
                return {"success": False, "message": f"Unknown action: {action}"}
                
        except Exception as e:
            print(f"Error processing invoice webhook: {e}")
            return {"success": False, "message": str(e)}
        

invoice_service = InvoiceService()