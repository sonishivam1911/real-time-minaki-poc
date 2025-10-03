
from fastapi import APIRouter, HTTPException

from services.whatsapp_slack_service import WhatsAppSlackService
from utils.schema.whatsapp_slack_schema import (
    MessageRequest,
    MessageResponse,
    ThreadMappingsResponse
)

router = APIRouter()

@router.post("/process-message", response_model=MessageResponse)
async def process_message(request: MessageRequest):
    """
    Unified endpoint to handle both WhatsApp->Slack and Slack->WhatsApp messages
    
    For WhatsApp messages:
    - message_type: "whatsapp"
    - phone_number: Required
    - message_text: Required
    - sender_name: Optional
    
    For Slack messages:
    - message_type: "slack" 
    - thread_id: Required
    - message_text: Required
    """
    try:
        whatsapp_slack_service = WhatsAppSlackService()
        result = whatsapp_slack_service.process_message(request)
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in process_message endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    


@router.get("/thread-mappings", response_model=ThreadMappingsResponse)
async def get_all_thread_mappings():
    """
    Get all thread mappings for debugging and admin purposes
    """
    try:
        whatsapp_slack_service = WhatsAppSlackService()
        result = whatsapp_slack_service.get_all_thread_mappings()
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_thread_mappings endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")




