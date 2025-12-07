"""
Pydantic schemas for Checkout System
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal


# ============================================================================
# CUSTOMER SCHEMAS
# ============================================================================

class CustomerBase(BaseModel):
    """Base customer schema"""
    full_name: str = Field(..., description="Customer full name")
    email: Optional[EmailStr] = None
    phone: str = Field(..., description="Customer phone number")
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    customer_type: str = Field(default="regular", description="regular, vip, wholesale")
    notes: Optional[str] = None


class CustomerCreate(CustomerBase):
    """Schema for creating customer"""
    pass


class CustomerResponse(CustomerBase):
    """Schema for customer response"""
    id: str
    customer_code: str
    credit_limit: Decimal
    outstanding_balance: Decimal
    loyalty_points: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerUpdate(BaseModel):
    """Schema for updating customer"""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    customer_type: Optional[str] = None
    notes: Optional[str] = None


# ============================================================================
# CART SCHEMAS
# ============================================================================

class CartItemBase(BaseModel):
    """Base cart item schema"""
    variant_id: str = Field(..., description="Product variant ID")
    stock_item_id: Optional[str] = Field(None, description="Specific serial item")
    quantity: int = Field(default=1, ge=1)
    discount_percent: Decimal = Field(default=0, ge=0, le=100)


class CartItemCreate(CartItemBase):
    """Schema for adding item to cart"""
    pass


class CartItemResponse(BaseModel):
    """Schema for cart item response"""
    id: str
    cart_id: str
    variant_id: str
    stock_item_id: Optional[str]
    product_name: str
    sku: Optional[str]
    serial_no: Optional[str]
    quantity: int
    unit_price: Decimal
    discount_percent: Decimal
    discount_amount: Decimal
    line_total: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


class CartCreate(BaseModel):
    """Schema for creating cart"""
    customer_id: Optional[str] = None
    session_id: Optional[str] = None


class CartResponse(BaseModel):
    """Schema for cart response"""
    id: str
    customer_id: Optional[str]
    session_id: Optional[str]
    status: str
    subtotal: Decimal
    discount_amount: Decimal
    tax_rate_percent: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    items: List[CartItemResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CartItemUpdate(BaseModel):
    """Schema for updating cart item"""
    quantity: Optional[int] = Field(None, ge=1)
    discount_percent: Optional[Decimal] = Field(None, ge=0, le=100)


# ============================================================================
# DISCOUNT SCHEMAS
# ============================================================================

class DiscountBase(BaseModel):
    """Base discount schema"""
    discount_code: str = Field(..., description="Unique discount code")
    discount_name: str = Field(..., description="Discount name")
    discount_type: str = Field(..., description="percentage or fixed_amount")
    discount_value: Decimal = Field(..., gt=0)
    applicable_to: str = Field(default="all", description="all, product, category")
    min_purchase_amount: Decimal = Field(default=0, ge=0)
    max_discount_amount: Optional[Decimal] = Field(None, gt=0)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    usage_limit: Optional[int] = Field(None, gt=0)


class DiscountCreate(DiscountBase):
    """Schema for creating discount"""
    pass


class DiscountResponse(DiscountBase):
    """Schema for discount response"""
    id: str
    is_active: bool
    usage_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DiscountValidation(BaseModel):
    """Schema for validating discount"""
    discount_code: str
    cart_total: Decimal


# ============================================================================
# PAYMENT SCHEMAS
# ============================================================================

class PaymentBase(BaseModel):
    """Base payment schema"""
    payment_method: str = Field(..., description="cash, card, upi, bank_transfer, cheque")
    payment_amount: Decimal = Field(..., gt=0)
    
    # Optional fields based on payment method
    card_type: Optional[str] = Field(None, description="visa, mastercard, amex, rupay")
    card_last_four: Optional[str] = Field(None, max_length=4)
    transaction_id: Optional[str] = None
    bank_name: Optional[str] = None
    cheque_number: Optional[str] = None
    cheque_date: Optional[date] = None
    upi_id: Optional[str] = None
    notes: Optional[str] = None


class PaymentCreate(PaymentBase):
    """Schema for creating payment"""
    pass


class PaymentResponse(PaymentBase):
    """Schema for payment response"""
    id: str
    payment_number: str
    invoice_id: str
    customer_id: Optional[str]
    payment_date: datetime
    payment_status: str
    processed_by: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# INVOICE SCHEMAS
# ============================================================================

class InvoiceItemResponse(BaseModel):
    """Schema for invoice item"""
    id: str
    variant_id: str
    stock_item_id: Optional[str]
    product_name: str
    sku: Optional[str]
    serial_no: Optional[str]
    quantity: int
    unit_price: Decimal
    discount_percent: Decimal
    discount_amount: Decimal
    line_total: Decimal

    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    """Schema for invoice response"""
    id: str
    invoice_number: str
    customer_id: Optional[str]
    invoice_date: datetime
    due_date: Optional[date]
    
    subtotal: Decimal
    discount_amount: Decimal
    tax_rate_percent: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    
    payment_status: str
    paid_amount: Decimal
    outstanding_amount: Decimal
    
    items: List[InvoiceItemResponse] = []
    payments: List[PaymentResponse] = []
    
    notes: Optional[str]
    sales_person: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# CHECKOUT SCHEMAS
# ============================================================================

class CheckoutRequest(BaseModel):
    """Schema for checkout request"""
    cart_id: str = Field(..., description="Cart ID to checkout")
    customer_id: Optional[str] = Field(None, description="Customer ID")
    
    payments: List[PaymentCreate] = Field(..., description="Payment methods")
    
    discount_code: Optional[str] = Field(None, description="Discount code to apply")
    tax_rate_percent: Decimal = Field(default=0, ge=0, description="Tax rate percentage")
    
    notes: Optional[str] = None
    sales_person: Optional[str] = None


class CheckoutResponse(BaseModel):
    """Schema for checkout response"""
    success: bool
    invoice_id: str
    invoice_number: str
    total_amount: Decimal
    paid_amount: Decimal
    outstanding_amount: Decimal
    payment_status: str
    message: str


class HoldTransactionRequest(BaseModel):
    """Schema for holding a transaction"""
    cart_id: str
    notes: Optional[str] = None


class HoldTransactionResponse(BaseModel):
    """Schema for hold transaction response"""
    success: bool
    cart_id: str
    message: str


# ============================================================================
# SEARCH/FILTER SCHEMAS
# ============================================================================

class CustomerSearchParams(BaseModel):
    """Schema for customer search"""
    phone: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    customer_code: Optional[str] = None


class InvoiceSearchParams(BaseModel):
    """Schema for invoice search"""
    customer_id: Optional[str] = None
    invoice_number: Optional[str] = None
    payment_status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# ============================================================================
# SUMMARY SCHEMAS
# ============================================================================

class CartSummary(BaseModel):
    """Schema for cart summary"""
    cart_id: str
    items_count: int
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal


class PaymentSummary(BaseModel):
    """Schema for payment summary"""
    total_amount: Decimal
    paid_amount: Decimal
    outstanding_amount: Decimal
    payment_methods: List[str]