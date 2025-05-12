from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime
from services.invoices_service import invoice_service

# Create router
router = APIRouter()

# Define models for webhook payloads
class InvoiceWebhookPayload(BaseModel):
    invoice_id: str
    action: Literal["create", "update", "delete"]
    timestamp: Optional[datetime] = None

# Webhook endpoints
@router.post("/invoice")
async def process_invoice_webhook(payload: InvoiceWebhookPayload):
    """Handle webhook notifications for invoice events."""
    # Process the webhook
    result = await invoice_service.process_invoice_webhook(
        invoice_id=payload.invoice_id,
        action=payload.action
    )
    
    if not result.get("success", False):
        error_msg = result.get("message", "Unknown error")
        return {
            "success": False,
            "message": error_msg
        }
    
    return {
        "success": True,
        "message": result.get("message", "Processed successfully"),
        "details": result.get("details", {})
    }