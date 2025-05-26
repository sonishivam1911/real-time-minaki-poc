from fastapi import APIRouter
from pydantic import BaseModel
from typing import Literal
from services.invoices_service import invoice_service

# Create router
router = APIRouter()

# Define models for webhook payloads
class InvoiceWebhookPayload(BaseModel):
    object_id: str
    action: Literal["create", "update", "delete"]
    endpoint: str

# Webhook endpoints
@router.post("/invoice")
async def process_invoice_webhook(payload: InvoiceWebhookPayload):
    """Handle webhook notifications for invoice events."""

    # before this we have to get the access token via refresh token which be found 

    # Process the webhook
    result = await invoice_service.process_invoice_webhook(
        invoice_id=payload.object_id,
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