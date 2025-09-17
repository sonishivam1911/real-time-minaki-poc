# services/whatsapp_slack_service.py

import requests
import os
from typing import Optional
from fastapi import HTTPException
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from core.database import db
from utils.schema.whatsapp_slack_schema import MessageRequest, MessageResponse, ThreadMappingsResponse

class WhatsAppSlackService:
    """Service class for handling WhatsApp and Slack integrations"""
    
    def __init__(self):
        # Environment variables
        self.slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
        self.slack_channel_id = os.getenv("SLACK_CHANNEL_ID")
        self.twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_messaging_service_id = os.getenv("TWILIO_MESSAGING_SERVICE_SID")

        # Validate required environment variables
        self._validate_env_variables()
        
        # Initialize Slack client
        self.slack_client = WebClient(token=self.slack_bot_token)
        # print(f"Calling create thread mapping")
        # # Initialize database table
        # self._create_thread_mappings_table()
    
    def _validate_env_variables(self):
        """Validate that all required environment variables are set"""
        required_vars = [
            ("SLACK_BOT_TOKEN", self.slack_bot_token),
            ("SLACK_CHANNEL_ID", self.slack_channel_id),
            ("TWILIO_ACCOUNT_SID", self.twilio_account_sid),
            ("TWILIO_AUTH_TOKEN", self.twilio_auth_token),
            ("TWILIO_MESSAGING_SERVICE_SID", self.twilio_messaging_service_id)
        ]
        
        missing_vars = [var_name for var_name, var_value in required_vars if not var_value]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    def _create_thread_mappings_table(self):
        """Create the thread_mappings table if it doesn't exist"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS public.thread_mappings (
            phone_number VARCHAR(20) PRIMARY KEY,
            slack_thread_id VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        try:
            print(f"Query being called : {create_table_query}")
            result = db.execute_query(create_table_query)
            print(f"Result is : {result}")
            if result:
                print("✅ thread_mappings table created/verified successfully")
            else:
                print("❌ Failed to create thread_mappings table")
                raise Exception("Table creation failed")
        except Exception as e:
            print(f"❌ Error creating thread_mappings table: {e}")
            raise
    
    def _post_to_slack(self, message_text: str, phone_number: str, sender_name: Optional[str] = None, thread_ts: Optional[str] = None) -> Optional[str]:
        """
        Post message to Slack channel using Web API
        Returns thread_ts for thread continuation
        """
        try:
            # Format the message for Slack
            display_name = sender_name if sender_name else "Unknown"
            formatted_message = f"📱 *New WhatsApp Message*\n*From:* {display_name} ({phone_number})\n*Message:* {message_text}"
            
            # Prepare the payload for chat.postMessage
            payload = {
                "channel": self.slack_channel_id,
                "text": formatted_message,
            }
            
            # If thread_ts provided, add it to continue the thread
            if thread_ts:
                payload["thread_ts"] = thread_ts
            
            # Use Slack Web API to post message
            response = self.slack_client.chat_postMessage(**payload)
            
            # Get the actual thread_ts from the response
            actual_thread_ts = response.get("ts")
            
            print(f"✅ Message posted to Slack successfully. TS: {actual_thread_ts}")
            return actual_thread_ts
            
        except SlackApiError as e:
            print(f"Slack API error: {e.response['error']}")
            raise HTTPException(status_code=500, detail=f"Slack API error: {e.response['error']}")
        except Exception as e:
            print(f"Unexpected error posting to Slack: {e}")
            raise HTTPException(status_code=500, detail=f"Slack integration error: {str(e)}")
    
    def _send_whatsapp_message(self, phone_number: str, message_text: str) -> bool:
        """Send WhatsApp message via Twilio"""
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_account_sid}/Messages.json"
            
            data = {
                'MessagingServiceSid': self.twilio_messaging_service_id,
                'To': f'whatsapp:{phone_number}',
                'Body': message_text
            }
            
            response = requests.post(
                url,
                data=data,
                auth=(self.twilio_account_sid, self.twilio_auth_token),
                timeout=30
            )
            print(f"Response text is : {response.text}")
            response.raise_for_status()
            
            print(f"WhatsApp message sent successfully to {phone_number}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error sending WhatsApp message: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to send WhatsApp message: {str(e)}")
        except Exception as e:
            print(f"Unexpected error sending WhatsApp message: {e}")
            raise HTTPException(status_code=500, detail=f"WhatsApp integration error: {str(e)}")
    


    def _get_thread_mapping(self, phone_number: str) -> Optional[str]:
        """Get existing thread ID for a phone number"""
        try:
            query = f"SELECT slack_thread_id FROM public.thread_mappings WHERE phone_number = '{phone_number}'"
            result = db.execute_query(query, return_data=True)
            
            if not result.empty:
                return result.iloc[0]['slack_thread_id']
            return None
            
        except Exception as e:
            print(f"Error getting thread mapping: {e}")
            return None
    
    def _save_thread_mapping(self, phone_number: str, thread_id: str):
        """Save or update thread mapping"""
        try:
            # Check if mapping exists
            existing_thread = self._get_thread_mapping(phone_number)
            
            if existing_thread:
                # Update existing mapping
                query = f"""
                UPDATE public.thread_mappings 
                SET slack_thread_id = '{thread_id}', created_at = CURRENT_TIMESTAMP 
                WHERE phone_number = '{phone_number}'
                """
            else:
                # Insert new mapping
                query = f"""
                INSERT INTO public.thread_mappings (phone_number, slack_thread_id, created_at) 
                VALUES ('{phone_number}', '{thread_id}', CURRENT_TIMESTAMP)
                """
            
            db.execute_query_new(query)
            print(f"Thread mapping saved: {phone_number} -> {thread_id}")
            
        except Exception as e:
            print(f"Error saving thread mapping: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    def _get_phone_number_from_thread(self, thread_id: str) -> Optional[str]:
        """Get phone number from thread ID"""
        try:
            query = f"SELECT phone_number FROM public.thread_mappings WHERE slack_thread_id = '{thread_id}'"
            result = db.execute_query(query, return_data=True)
            
            if not result.empty:
                return result.iloc[0]['phone_number']
            return None
            
        except Exception as e:
            print(f"Error getting phone number from thread: {e}")
            return None
    
    def process_whatsapp_message(self, request: MessageRequest) -> MessageResponse:
        """Process WhatsApp to Slack message"""
        try:
            if not request.phone_number:
                raise HTTPException(status_code=400, detail="phone_number is required for WhatsApp messages")
            
            # Check for existing thread
            existing_thread_id = self._get_thread_mapping(request.phone_number)
            
            # Post to Slack
            thread_id = self._post_to_slack(
                message_text=request.message_text,
                phone_number=request.phone_number,
                sender_name=request.sender_name,
                thread_ts=existing_thread_id
            )
            
            if thread_id:
                # Save thread mapping
                self._save_thread_mapping(request.phone_number, thread_id)
                
                return MessageResponse(
                    success=True,
                    message="WhatsApp message posted to Slack successfully",
                    thread_id=thread_id,
                    status_code=200
                )
            else:
                raise HTTPException(status_code=500, detail="Failed to post message to Slack")
                
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error processing WhatsApp message: {e}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    def process_slack_message(self, request: MessageRequest) -> MessageResponse:
        """Process Slack to WhatsApp message"""
        try:
            if not request.thread_id:
                raise HTTPException(status_code=400, detail="thread_id is required for Slack messages")
            
            # Get phone number from thread ID
            phone_number = self._get_phone_number_from_thread(request.thread_id)
            
            if not phone_number:
                raise HTTPException(status_code=404, detail="No phone number found for this thread ID")
            
            # Send WhatsApp message
            success = self._send_whatsapp_message(phone_number, request.message_text)
            
            if success:
                return MessageResponse(
                    success=True,
                    message="Slack reply sent to WhatsApp successfully",
                    phone_number=phone_number,
                    status_code=200
                )
            else:
                raise HTTPException(status_code=500, detail="Failed to send WhatsApp message")
                
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error processing Slack message: {e}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    def process_message(self, request: MessageRequest) -> MessageResponse:
        """
        Main method to process messages based on type
        """
        if request.message_type == "whatsapp":
            return self.process_whatsapp_message(request)
        elif request.message_type == "slack":
            return self.process_slack_message(request)
        else:
            raise HTTPException(
                status_code=400, 
                detail="Invalid message_type. Use 'whatsapp' or 'slack'"
            )
    
    def get_all_thread_mappings(self) -> ThreadMappingsResponse:
        """Get all thread mappings for debugging/admin purposes"""
        try:
            # Ensure table exists before querying
            self._ensure_table_exists()
            
            query = "SELECT * FROM public.thread_mappings ORDER BY created_at DESC"
            result = db.execute_query(query, return_data=True)
            
            mappings = result.to_dict('records') if not result.empty else []
            
            return ThreadMappingsResponse(
                success=True,
                mappings=mappings,
                total_count=len(mappings)
            )
            
        except Exception as e:
            print(f"Error fetching thread mappings: {e}")
            raise HTTPException(status_code=500, detail=f"Error fetching thread mappings: {str(e)}")

# Create service instance
whatsapp_slack_service = WhatsAppSlackService()