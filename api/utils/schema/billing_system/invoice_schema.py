"""
Invoice Schema - Request/Response models for invoice operations
"""
from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from datetime import datetime, date


class SendInvoiceWhatsAppRequest(BaseModel):
    """Request model for sending invoice via WhatsApp"""
    phone_number: str
    message: Optional[str] = None
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        # Basic phone number validation
        if not v.startswith('+'):
            raise ValueError('Phone number must include country code (e.g., +91)')
        if len(v.replace('+', '').replace('-', '').replace(' ', '')) < 10:
            raise ValueError('Invalid phone number format')
        return v


class SendInvoiceEmailRequest(BaseModel):
    """Request model for sending invoice via email"""
    email: EmailStr
    subject: Optional[str] = None
    message: Optional[str] = None


class InvoiceResponse(BaseModel):
    """Response model for invoice operations"""
    success: bool
    message: str
    filename: Optional[str] = None
    message_sid: Optional[str] = None  # For WhatsApp
    error: Optional[str] = None


class InvoiceCommunication(BaseModel):
    """Model for invoice communication history"""
    id: str
    invoice_id: str
    communication_method: str  # 'email' or 'whatsapp'
    recipient: str
    status: str  # 'sent', 'failed', 'delivered', 'read'
    message_id: Optional[str] = None
    sent_at: datetime


class InvoiceItemCreate(BaseModel):
    """Model for creating invoice items"""
    variant_id: str
    stock_item_id: Optional[str] = None
    product_name: str
    sku: str
    serial_no: Optional[str] = None
    quantity: int
    unit_price: float
    discount_percent: Optional[float] = 0.0
    discount_amount: Optional[float] = 0.0
    line_total: float


class InvoiceCreate(BaseModel):
    """Model for creating invoices manually"""
    customer_id: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    items: List[InvoiceItemCreate]
    discount_code: Optional[str] = None
    tax_rate_percent: Optional[float] = 0.0
    notes: Optional[str] = None
    sales_person: Optional[str] = None


class PaymentReminder(BaseModel):
    """Model for payment reminder configuration"""
    overdue_days: int = 7
    include_whatsapp: bool = False
    include_email: bool = True
    custom_message: Optional[str] = None


class BulkInvoiceOperation(BaseModel):
    """Model for bulk invoice operations"""
    invoice_ids: List[str]
    operation: str  # 'send_email', 'send_whatsapp', 'mark_paid', etc.
    email_addresses: Optional[List[EmailStr]] = None
    phone_numbers: Optional[List[str]] = None
    custom_message: Optional[str] = None


class InvoiceFilter(BaseModel):
    """Model for invoice filtering"""
    customer_id: Optional[str] = None
    payment_status: Optional[str] = None  # 'pending', 'partial', 'paid', 'refunded'
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    sales_person: Optional[str] = None
    
    @validator('payment_status')
    def validate_payment_status(cls, v):
        if v and v not in ['pending', 'partial', 'paid', 'refunded']:
            raise ValueError('Invalid payment status')
        return v


class InvoiceStats(BaseModel):
    """Model for invoice statistics"""
    total_invoices: int
    total_sales: float
    total_paid: float
    total_outstanding: float
    average_invoice_value: float
    paid_invoices: int
    partial_invoices: int
    pending_invoices: int


class PDFCustomization(BaseModel):
    """Model for PDF customization options"""
    include_logo: bool = True
    color_theme: str = 'default'  # 'default', 'blue', 'green', 'red'
    font_size: str = 'normal'  # 'small', 'normal', 'large'
    include_payment_terms: bool = True
    include_bank_details: bool = True
    watermark_text: Optional[str] = None
    
    @validator('color_theme')
    def validate_color_theme(cls, v):
        if v not in ['default', 'blue', 'green', 'red']:
            raise ValueError('Invalid color theme')
        return v
    
    @validator('font_size')
    def validate_font_size(cls, v):
        if v not in ['small', 'normal', 'large']:
            raise ValueError('Invalid font size')
        return v


# Company information model for invoice headers
class CompanyInfo(BaseModel):
    """Model for company information"""
    name: str
    address: str
    phone: str
    email: EmailStr
    website: Optional[str] = None
    tax_id: Optional[str] = None
    logo_path: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    payment_terms: Optional[str] = None


# Extended invoice model with all details
class InvoiceDetails(BaseModel):
    """Detailed invoice model with all related data"""
    id: str
    invoice_number: str
    customer_id: Optional[str] = None
    cart_id: Optional[str] = None
    invoice_date: datetime
    due_date: Optional[date] = None
    subtotal: float
    discount_amount: float
    tax_rate_percent: float
    tax_amount: float
    total_amount: float
    payment_status: str
    paid_amount: float
    outstanding_amount: float
    notes: Optional[str] = None
    sales_person: Optional[str] = None
    created_at: datetime
    
    # Related data
    items: List[dict] = []
    payments: List[dict] = []
    customer: Optional[dict] = None
    communications: List[InvoiceCommunication] = []


# Response models for different operations
class InvoiceCreatedResponse(BaseModel):
    """Response when invoice is created"""
    success: bool
    invoice_id: str
    invoice_number: str
    total_amount: float
    message: str


class BatchOperationResponse(BaseModel):
    """Response for batch operations"""
    success: bool
    message: str
    processed_count: int
    success_count: int
    failed_count: int
    results: List[dict] = []


class PaymentReminderResult(BaseModel):
    """Result for payment reminder operation"""
    invoice_number: str
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    status: str  # 'sent', 'failed'
    error: Optional[str] = None


class PaymentReminderResponse(BaseModel):
    """Response for payment reminder batch operation"""
    success: bool
    message: str
    sent_count: int
    failed_count: int
    results: List[PaymentReminderResult]


# Configuration models
class InvoiceSettings(BaseModel):
    """Model for invoice configuration settings"""
    invoice_prefix: str = "INV"
    auto_generate_number: bool = True
    default_tax_rate: float = 18.0
    default_payment_terms: str = "Net 30"
    require_customer: bool = False
    auto_send_email: bool = False
    auto_send_whatsapp: bool = False
    pdf_password_protect: bool = False
    include_qr_code: bool = True