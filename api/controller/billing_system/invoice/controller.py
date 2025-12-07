"""
Invoice Controller - API endpoints for invoice management
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import Optional
from datetime import date

from services.billing_system.checkout_service import CheckoutService


router = APIRouter()


@router.get("", response_model=list)
async def list_invoices(
    customer_id: Optional[str] = Query(None, description="Filter by customer"),
    payment_status: Optional[str] = Query(None, description="Filter by payment status"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    List all invoices with optional filters.
    
    **Query Parameters:**
    - `customer_id` - Filter by customer
    - `payment_status` - Filter by status (pending, partial, paid, refunded)
    - `start_date` - Filter from date
    - `end_date` - Filter to date
    - `page` - Page number
    - `page_size` - Items per page
    
    **Example:**
    ```
    GET /api/invoices?payment_status=pending&page=1&page_size=20
    GET /api/invoices?customer_id=cust_123
    GET /api/invoices?start_date=2024-01-01&end_date=2024-12-31
    ```
    """
    where_clauses = []
    
    if customer_id:
        where_clauses.append(f"customer_id = '{customer_id}'")
    
    if payment_status:
        where_clauses.append(f"payment_status = '{payment_status}'")
    
    if start_date:
        where_clauses.append(f"invoice_date >= '{start_date}'")
    
    if end_date:
        where_clauses.append(f"invoice_date <= '{end_date}'")
    
    where_str = " AND ".join(where_clauses) if where_clauses else "1=1"
    offset = (page - 1) * page_size
    
    query = f"""
        SELECT * FROM sales_invoices
        WHERE {where_str}
        ORDER BY invoice_date DESC
        LIMIT {page_size} OFFSET {offset}
    """
    service = CheckoutService()
    df = service.crud.execute_query(query, return_data=True)
    return df.to_dict('records')


@router.get("/{invoice_id}", response_model=dict)
async def get_invoice(
    invoice_id: str = Path(..., description="Invoice ID"),
):
    """
    Get invoice details with items and payments.
    
    **Returns:**
    - Invoice information
    - All line items
    - All payments
    - Customer details
    """
    service = CheckoutService()
    # Get invoice
    invoice_query = f"SELECT * FROM sales_invoices WHERE id = '{invoice_id}'"
    invoice_df = service.crud.execute_query(invoice_query, return_data=True)
    
    if invoice_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Invoice {invoice_id} not found"
        )
    
    invoice = invoice_df.iloc[0].to_dict()
    
    # Get invoice items
    items_query = f"SELECT * FROM invoice_items WHERE invoice_id = '{invoice_id}'"
    items_df = service.crud.execute_query(items_query, return_data=True)
    invoice['items'] = items_df.to_dict('records')
    
    # Get payments
    payments_query = f"SELECT * FROM payments WHERE invoice_id = '{invoice_id}'"
    payments_df = service.crud.execute_query(payments_query, return_data=True)
    invoice['payments'] = payments_df.to_dict('records')
    
    # Get customer
    if invoice['customer_id']:
        customer_query = f"SELECT * FROM customers WHERE id = '{invoice['customer_id']}'"
        customer_df = service.crud.execute_query(customer_query, return_data=True)
        if not customer_df.empty:
            invoice['customer'] = customer_df.iloc[0].to_dict()
    
    return invoice


@router.get("/number/{invoice_number}", response_model=dict)
async def get_invoice_by_number(
    invoice_number: str = Path(..., description="Invoice number"),
):
    """
    Get invoice by invoice number.
    
    **Example:**
    ```
    GET /api/invoices/number/INV-2024-0001
    ```
    """
    service = CheckoutService()
    query = f"SELECT id FROM sales_invoices WHERE invoice_number = '{invoice_number}'"
    df = service.crud.execute_query(query, return_data=True)
    
    if df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Invoice {invoice_number} not found"
        )
    
    invoice_id = df.iloc[0]['id']
    
    # Reuse get_invoice logic
    return await get_invoice(invoice_id, service)


@router.get("/customer/{customer_id}/invoices", response_model=list)
async def get_customer_invoices(
    customer_id: str = Path(..., description="Customer ID"),
):
    """
    Get all invoices for a specific customer.
    """
    query = f"""
        SELECT * FROM sales_invoices
        WHERE customer_id = '{customer_id}'
        ORDER BY invoice_date DESC
    """
    service = CheckoutService()
    df = service.crud.execute_query(query, return_data=True)
    return df.to_dict('records')


@router.get("/stats/summary", response_model=dict)
async def get_sales_summary(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    """
    Get sales summary statistics.
    
    **Returns:**
    - Total sales amount
    - Number of invoices
    - Payment status breakdown
    - Average invoice value
    """
    where_clauses = []
    
    if start_date:
        where_clauses.append(f"invoice_date >= '{start_date}'")
    
    if end_date:
        where_clauses.append(f"invoice_date <= '{end_date}'")
    
    where_str = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    query = f"""
        SELECT 
            COUNT(*) as total_invoices,
            SUM(total_amount) as total_sales,
            SUM(paid_amount) as total_paid,
            SUM(outstanding_amount) as total_outstanding,
            AVG(total_amount) as average_invoice_value,
            COUNT(CASE WHEN payment_status = 'paid' THEN 1 END) as paid_invoices,
            COUNT(CASE WHEN payment_status = 'partial' THEN 1 END) as partial_invoices,
            COUNT(CASE WHEN payment_status = 'pending' THEN 1 END) as pending_invoices
        FROM sales_invoices
        WHERE {where_str}
    """
    service = CheckoutService()
    df = service.crud.execute_query(query, return_data=True)
    
    if df.empty:
        return {
            "total_invoices": 0,
            "total_sales": 0,
            "total_paid": 0,
            "total_outstanding": 0,
            "average_invoice_value": 0
        }
    
    return df.iloc[0].to_dict()