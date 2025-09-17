# schema/whatsapp_slack.py

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class MessageRequest(BaseModel):
    """Request model for processing messages"""
    message_type: str = Field(..., description="Type of message: 'whatsapp' or 'slack'")
    phone_number: Optional[str] = Field(None, description="Phone number for WhatsApp messages")
    message_text: str = Field(..., description="The message content")
    sender_name: Optional[str] = Field(None, description="Name of the sender (for WhatsApp)")
    thread_id: Optional[str] = Field(None, description="Slack thread ID (for Slack messages)")

class MessageResponse(BaseModel):
    """Response model for message processing"""
    success: bool
    message: str
    thread_id: Optional[str] = None
    phone_number: Optional[str] = None
    status_code: int = 200

class ThreadMapping(BaseModel):
    """Model for thread mapping data"""
    phone_number: str
    slack_thread_id: str
    created_at: datetime

class ThreadMappingsResponse(BaseModel):
    """Response model for thread mappings"""
    success: bool
    mappings: List[Dict[str, Any]]
    total_count: int

class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    service: str
    timestamp: datetime = Field(default_factory=datetime.now)