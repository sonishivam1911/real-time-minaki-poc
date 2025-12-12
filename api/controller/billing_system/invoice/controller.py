"""
Invoice Controller - API endpoints for invoice management and PDF generation
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Path, Response
from fastapi.responses import FileResponse, StreamingResponse
from typing import Optional
from datetime import date
from pydantic import BaseModel, EmailStr
from io import BytesIO

from services.billing_system.checkout_service import CheckoutService
from services.billing_system.invoice_service import InvoiceService


# Request/Response models
class SendInvoiceWhatsAppRequest(BaseModel):
    phone_number: str
    message: Optional[str] = None

class SendInvoiceEmailRequest(BaseModel):
    email: EmailStr
    subject: Optional[str] = None
    message: Optional[str] = None

class InvoiceResponse(BaseModel):
    success: bool
    message: str
    filename: Optional[str] = None
    message_sid: Optional[str] = None  # For WhatsApp
    error: Optional[str] = None


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
        SELECT * FROM billing_system_invoices_master
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
    invoice_query = f"SELECT * FROM billing_system_invoices_master WHERE id = '{invoice_id}'"
    invoice_df = service.crud.execute_query(invoice_query, return_data=True)
    
    if invoice_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Invoice {invoice_id} not found"
        )
    
    invoice = invoice_df.iloc[0].to_dict()
    
    # Get invoice items
    items_query = f"SELECT * FROM billing_system_invoice_items WHERE invoice_id = '{invoice_id}'"
    items_df = service.crud.execute_query(items_query, return_data=True)
    invoice['items'] = items_df.to_dict('records')
    
    # Get payments
    payments_query = f"SELECT * FROM billing_system_payments WHERE invoice_id = '{invoice_id}'"
    payments_df = service.crud.execute_query(payments_query, return_data=True)
    invoice['payments'] = payments_df.to_dict('records')
    
    # Get customer
    if invoice['customer_id']:
        customer_query = f"SELECT * FROM billing_system_customers WHERE id = '{invoice['customer_id']}'"
        customer_df = service.crud.execute_query(customer_query, return_data=True)
        if not customer_df.empty:
            invoice['customer'] = customer_df.iloc[0].to_dict()
    
    return invoice


@router.get("/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: str = Path(..., description="Invoice ID"),
):
    """
    Generate and download invoice PDF
    
    **Returns:**
    - PDF file as downloadable attachment
    
    **Example:**
    ```
    GET /api/invoices/{invoice_id}/pdf
    ```
    """
    invoice_service = InvoiceService()
    
    # Generate PDF
    result = invoice_service.generate_invoice_pdf(invoice_id)
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Failed to generate PDF')
        )
    
    # Return PDF as streaming response
    pdf_stream = BytesIO(result['pdf_bytes'])
    
    return StreamingResponse(
        pdf_stream,
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{result["filename"]}"'
        }
    )


@router.post("/{invoice_id}/send/whatsapp", response_model=InvoiceResponse)
async def send_invoice_whatsapp(
    invoice_id: str = Path(..., description="Invoice ID"),
    request: SendInvoiceWhatsAppRequest = None
):
    """
    Send invoice PDF via WhatsApp
    
    **Request Body:**
    ```json
    {
        "phone_number": "+911234567890",
        "message": "Optional custom message"
    }
    ```
    
    **Note:** 
    - Phone number should include country code (e.g., +91 for India)
    - Twilio WhatsApp API must be configured
    
    **Example:**
    ```
    POST /api/invoices/{invoice_id}/send/whatsapp
    {
        "phone_number": "+911234567890"
    }
    ```
    """
    if not request:
        raise HTTPException(
            status_code=400,
            detail="Request body required"
        )
    
    invoice_service = InvoiceService()
    
    # Send via WhatsApp
    result = invoice_service.send_invoice_via_whatsapp(
        invoice_id=invoice_id,
        phone_number=request.phone_number,
        message=request.message
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Failed to send invoice')
        )
    
    return InvoiceResponse(
        success=True,
        message=result['message'],
        filename=result.get('filename'),
        message_sid=result.get('message_sid')
    )


@router.post("/{invoice_id}/send/email", response_model=InvoiceResponse)
async def send_invoice_email(
    invoice_id: str = Path(..., description="Invoice ID"),
    request: SendInvoiceEmailRequest = None
):
    """
    Send invoice PDF via Email
    
    **Request Body:**
    ```json
    {
        "email": "customer@email.com",
        "subject": "Optional custom subject",
        "message": "Optional custom message"
    }
    ```
    
    **Note:** 
    - SMTP configuration must be set in environment variables
    
    **Example:**
    ```
    POST /api/invoices/{invoice_id}/send/email
    {
        "email": "customer@email.com"
    }
    ```
    """
    if not request:
        raise HTTPException(
            status_code=400,
            detail="Request body required"
        )
    
    invoice_service = InvoiceService()
    
    # Send via email
    result = invoice_service.send_invoice_via_email(
        invoice_id=invoice_id,
        recipient_email=request.email,
        subject=request.subject,
        message=request.message
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Failed to send invoice')
        )
    
    return InvoiceResponse(
        success=True,
        message=result['message'],
        filename=result.get('filename')
    )


@router.get("/{invoice_id}/communications")
async def get_invoice_communications(
    invoice_id: str = Path(..., description="Invoice ID"),
):
    """
    Get communication history for an invoice
    
    **Returns:**
    - List of all communications (WhatsApp, Email) sent for this invoice
    
    **Example:**
    ```
    GET /api/invoices/{invoice_id}/communications
    ```
    """
    service = CheckoutService()
    
    query = f"""
        SELECT * FROM billing_system_invoice_communications 
        WHERE invoice_id = '{invoice_id}'
        ORDER BY sent_at DESC
    """
    
    df = service.crud.execute_query(query, return_data=True)
    
    if df.empty:
        return []
    
    return df.to_dict('records')


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
    query = f"SELECT id FROM billing_system_invoices_master WHERE invoice_number = '{invoice_number}'"
    df = service.crud.execute_query(query, return_data=True)
    
    if df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Invoice {invoice_number} not found"
        )
    
    invoice_id = df.iloc[0]['id']
    
    # Reuse get_invoice logic
    return await get_invoice(invoice_id)


@router.get("/number/{invoice_number}/pdf")
async def download_invoice_pdf_by_number(
    invoice_number: str = Path(..., description="Invoice number"),
):
    """
    Generate and download invoice PDF by invoice number
    
    **Example:**
    ```
    GET /api/invoices/number/INV-2024-0001/pdf
    ```
    """
    service = CheckoutService()
    query = f"SELECT id FROM billing_system_invoices_master WHERE invoice_number = '{invoice_number}'"
    df = service.crud.execute_query(query, return_data=True)
    
    if df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Invoice {invoice_number} not found"
        )
    
    invoice_id = df.iloc[0]['id']
    
    # Reuse PDF generation logic
    return await download_invoice_pdf(invoice_id)


@router.get("/customer/{customer_id}/invoices", response_model=list)
async def get_customer_invoices(
    customer_id: str = Path(..., description="Customer ID"),
):
    """
    Get all invoices for a specific customer.
    """
    query = f"""
        SELECT * FROM billing_system_invoices_master
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
            COUNT(CASE WHEN payment_status = 'unpaid' THEN 1 END) as pending_invoices
        FROM billing_system_invoices_master
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
            "average_invoice_value": 0,
            "paid_invoices": 0,
            "partial_invoices": 0,
            "pending_invoices": 0
        }
    
    return df.iloc[0].to_dict()


# Batch operations
@router.post("/batch/send-reminders")
async def send_payment_reminders(
    overdue_days: int = Query(7, description="Days overdue to send reminder"),
):
    """
    Send payment reminders for overdue invoices
    
    **Query Parameters:**
    - `overdue_days` - Minimum days overdue to trigger reminder (default: 7)
    
    **Example:**
    ```
    POST /api/invoices/batch/send-reminders?overdue_days=7
    ```
    """
    service = CheckoutService()
    invoice_service = InvoiceService()
    
    # Get overdue invoices with customer contact info
    query = f"""
        SELECT si.*, c.email, c.phone, c.full_name
        FROM billing_system_invoices_master si
        LEFT JOIN billing_system_customers c ON si.customer_id = c.id
        WHERE si.outstanding_amount > 0
        AND si.due_date < CURRENT_DATE - INTERVAL '{overdue_days} days'
        AND c.email IS NOT NULL
    """
    
    df = service.crud.execute_query(query, return_data=True)
    
    sent_count = 0
    failed_count = 0
    results = []
    
    for _, invoice in df.iterrows():
        try:
            # Send email reminder
            reminder_message = f"""
Dear {invoice['full_name']},

This is a friendly reminder that your invoice #{invoice['invoice_number']} is overdue.

Invoice Details:
- Invoice Date: {invoice['invoice_date']}
- Due Date: {invoice['due_date']}
- Outstanding Amount: ₹{float(invoice['outstanding_amount']):.2f}

Please arrange payment at your earliest convenience.

Thank you for your business.
            """.strip()
            
            result = invoice_service.send_invoice_via_email(
                invoice_id=invoice['id'],
                recipient_email=invoice['email'],
                subject=f"Payment Reminder - Invoice #{invoice['invoice_number']}",
                message=reminder_message
            )
            
            if result['success']:
                sent_count += 1
                results.append({
                    'invoice_number': invoice['invoice_number'],
                    'customer_email': invoice['email'],
                    'status': 'sent'
                })
            else:
                failed_count += 1
                results.append({
                    'invoice_number': invoice['invoice_number'],
                    'customer_email': invoice['email'],
                    'status': 'failed',
                    'error': result.get('error')
                })
                
        except Exception as e:
            failed_count += 1
            results.append({
                'invoice_number': invoice['invoice_number'],
                'customer_email': invoice.get('email', 'N/A'),
                'status': 'failed',
                'error': str(e)
            })
    
    return {
        'success': True,
        'message': f'Payment reminders processed: {sent_count} sent, {failed_count} failed',
        'sent_count': sent_count,
        'failed_count': failed_count,
        'results': results
    }