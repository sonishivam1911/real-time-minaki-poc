from typing import List
import pandas as pd

from services.taj_invoice_service import process_taj_sales, preprocess_products
from schema.taj_invoices import InvoiceResponse, InvoiceDetail
from utils.file_processors import preprocess_excel_file, validate_required_columns, parse_date

class InvoiceService:
    
    @staticmethod
    async def process_invoice_file(
        file_content: bytes, 
        date_string: str, 
        zakya_connection: dict
    ) -> InvoiceResponse:
        """Process invoice file and return response."""
        
        try:
            # Parse date
            invoice_date = parse_date(date_string)
            
            # Read and preprocess file
            taj_sales_df = preprocess_excel_file(file_content)
            
            # Validate required columns
            validate_required_columns(taj_sales_df)
            
            # Check if DataFrame is empty after preprocessing
            if taj_sales_df.empty:
                return InvoiceResponse(
                    invoices=[],
                    status_code=400,
                    message="No valid data found in the Excel file after preprocessing",
                    missing_product_skus=[],
                    total_invoices_created=0,
                    total_amount=0.0
                )
            
            # Get missing products before processing
            try:
                product_config = await preprocess_products(taj_sales_df)
                missing_product_skus = product_config.get('missing_products', [])
            except Exception as e:
                return InvoiceResponse(
                    invoices=[],
                    status_code=500,
                    message=f"Error checking product availability: {str(e)}",
                    missing_product_skus=[],
                    total_invoices_created=0,
                    total_amount=0.0
                )
            
            # Process invoices
            try:
                invoice_df, product_config = await process_taj_sales(
                    taj_sales_df, invoice_date, zakya_connection
                )
                missing_product_skus = product_config.get('missing_products', [])
                
                # Handle case where no invoices were created
                if invoice_df.empty:
                    return InvoiceResponse(
                        invoices=[],
                        status_code=400,
                        message="No invoices were generated. Please check the data and try again.",
                        missing_product_skus=missing_product_skus,
                        total_invoices_created=0,
                        total_amount=0.0
                    )
                
                # Process invoice results
                return InvoiceService._process_invoice_results(
                    invoice_df, missing_product_skus
                )
                
            except Exception as e:
                return InvoiceResponse(
                    invoices=[],
                    status_code=500,
                    message=f"Error processing invoices: {str(e)}",
                    missing_product_skus=missing_product_skus,
                    total_invoices_created=0,
                    total_amount=0.0
                )
                
        except Exception as e:
            return InvoiceResponse(
                invoices=[],
                status_code=500,
                message=f"Unexpected error: {str(e)}",
                missing_product_skus=[],
                total_invoices_created=0,
                total_amount=0.0
            )
    
    @staticmethod
    def _process_invoice_results(
        invoice_df: pd.DataFrame, 
        missing_product_skus: List[str]
    ) -> InvoiceResponse:
        """Process invoice results and create response."""
        
        invoices = []
        total_amount = 0.0
        successful_invoices = 0
        failed_invoices = []
        
        for _, row in invoice_df.iterrows():
            invoice_detail = InvoiceDetail(
                invoice_id=row.get('invoice_id'),
                invoice_number=row.get('invoice_number'),
                customer_name=row.get('customer_name', ''),
                amount=row.get('amount', 0.0),
                date=row.get('date', ''),
                due_date=row.get('due_date'),
                status=row.get('status', 'Unknown')
            )
            
            invoices.append(invoice_detail)
            
            if invoice_detail.status == 'Success':
                successful_invoices += 1
                total_amount += invoice_detail.amount or 0.0
            else:
                failed_invoices.append({
                    'customer': invoice_detail.customer_name,
                    'error': row.get('error', 'Unknown error')
                })
        
        # Prepare response message
        if successful_invoices > 0 and len(failed_invoices) == 0:
            message = f"Successfully created {successful_invoices} invoices"
            status_code = 200
        elif successful_invoices > 0 and len(failed_invoices) > 0:
            message = f"Created {successful_invoices} invoices successfully, {len(failed_invoices)} failed"
            status_code = 207  # Multi-status
        else:
            message = f"All invoice creation failed. {len(failed_invoices)} invoices failed to create"
            status_code = 400
        
        # Add missing products to message if any
        if missing_product_skus:
            message += f". {len(missing_product_skus)} products not found in system"
        
        return InvoiceResponse(
            invoices=invoices,
            status_code=status_code,
            message=message,
            missing_product_skus=missing_product_skus,
            total_invoices_created=successful_invoices,
            total_amount=round(total_amount, 2)
        )