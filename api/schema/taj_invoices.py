from pydantic import BaseModel
from typing import List, Optional

class InvoiceDetail(BaseModel):
    invoice_id: Optional[str] = None
    invoice_number: Optional[str] = None
    customer_name: str
    amount: Optional[float] = None
    date: str
    due_date: Optional[str] = None
    status: str

class InvoiceResponse(BaseModel):
    invoices: List[InvoiceDetail]
    status_code: int
    message: str
    missing_product_skus: List[str]
    total_invoices_created: int
    total_amount: float