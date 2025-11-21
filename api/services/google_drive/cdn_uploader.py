"""
Google Drive to Shopify CDN Bridge
Downloads from Google Drive and uploads directly to Shopify's CDN
"""

import logging
import requests
import mimetypes
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class GoogleDriveToCDN:
    """Handle downloading from Google Drive and uploading to Shopify CDN"""
    
    @staticmethod
    def get_mime_type_from_bytes(image_bytes: bytes) -> str:
        """
        Detect MIME type from image bytes
        
        Args:
            image_bytes: Image binary data
            
        Returns:
            MIME type string
        """
        # Check magic numbers for common image formats
        if image_bytes.startswith(b'\xff\xd8\xff'):
            return 'image/jpeg'
        elif image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'image/png'
        elif image_bytes.startswith(b'GIF87a') or image_bytes.startswith(b'GIF89a'):
            return 'image/gif'
        elif image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:12]:
            return 'image/webp'
        else:
            # Default to JPEG
            return 'image/jpeg'
    
    @staticmethod
    def upload_to_shopify_cdn(
        image_bytes: bytes,
        filename: str,
        shopify_client
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Upload image bytes directly to Shopify's CDN
        
        Args:
            image_bytes: Image binary data
            filename: Original filename for the image
            shopify_client: BaseShopifyConnector instance
            
        Returns:
            Tuple of (success, cdn_url, error_message)
        """
        try:
            # Step 1: Detect MIME type
            mime_type = GoogleDriveToCDN.get_mime_type_from_bytes(image_bytes)
            file_size = len(image_bytes)
            
            logger.info(f"📤 Uploading {filename} ({file_size} bytes, {mime_type}) to Shopify CDN...")
            
            # Step 2: Create staged upload target
            staged_upload_mutation = """
            mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
                stagedUploadsCreate(input: $input) {
                    stagedTargets {
                        url
                        resourceUrl
                        parameters {
                            name
                            value
                        }
                    }
                    userErrors {
                        field
                        message
                    }
                }
            }
            """
            
            staged_input = {
                "input": [{
                    "resource": "IMAGE",
                    "filename": filename,
                    "mimeType": mime_type,
                    "httpMethod": "POST",
                    "fileSize": str(file_size)
                }]
            }
            
            staged_result = shopify_client.execute_query(staged_upload_mutation, staged_input)
            
            # Check for errors
            if staged_result.get('errors'):
                error_msg = str(staged_result['errors'])
                logger.error(f"❌ Staged upload creation failed: {error_msg}")
                return False, None, error_msg
            
            user_errors = staged_result.get('data', {}).get('stagedUploadsCreate', {}).get('userErrors', [])
            if user_errors:
                error_msg = str(user_errors)
                logger.error(f"❌ Staged upload user errors: {error_msg}")
                return False, None, error_msg
            
            staged_targets = staged_result.get('data', {}).get('stagedUploadsCreate', {}).get('stagedTargets', [])
            
            if not staged_targets:
                error_msg = "No staged targets returned"
                logger.error(f"❌ {error_msg}")
                return False, None, error_msg
            
            staged_target = staged_targets[0]
            upload_url = staged_target['url']
            resource_url = staged_target['resourceUrl']
            parameters = staged_target['parameters']
            
            logger.info(f"✅ Got staged upload URL: {upload_url[:50]}...")
            
            # Step 3: Upload file to staged URL
            form_data = {}
            for param in parameters:
                form_data[param['name']] = param['value']
            
            # Add file to form data
            files = {
                'file': (filename, image_bytes, mime_type)
            }
            
            logger.info(f"📤 Uploading file to Shopify staging area...")
            upload_response = requests.post(
                upload_url,
                data=form_data,
                files=files,
                timeout=60
            )
            
            if upload_response.status_code not in [200, 201, 204]:
                error_msg = f"Upload failed with status {upload_response.status_code}: {upload_response.text}"
                logger.error(f"❌ {error_msg}")
                return False, None, error_msg
            
            logger.info(f"✅ Successfully uploaded to Shopify CDN!")
            logger.info(f"📍 Resource URL: {resource_url}")
            
            return True, resource_url, None
            
        except Exception as e:
            error_msg = f"Exception during CDN upload: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return False, None, error_msg