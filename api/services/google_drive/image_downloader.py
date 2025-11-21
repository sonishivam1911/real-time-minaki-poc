"""
Google Drive Image Downloader Service
Downloads images from Google Drive and converts to usable URLs for Shopify
"""

import requests
import re
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qs
import logging

logger = logging.getLogger(__name__)


class GoogleDriveImageDownloader:
    """
    Handle Google Drive image downloads and conversion to direct URLs
    """
    
    @staticmethod
    def extract_file_id_from_url(url: str) -> Optional[str]:
        """
        Extract Google Drive file ID from various Google Drive URL formats
        
        Handles:
        - https://drive.google.com/file/d/{FILE_ID}/view
        - https://drive.google.com/open?id={FILE_ID}
        - https://docs.google.com/uc?id={FILE_ID}
        - https://drive.google.com/uc?id={FILE_ID}
        
        Args:
            url: Google Drive URL
            
        Returns:
            File ID or None if not found
        """
        if not url:
            return None
        
        # Pattern 1: /d/{FILE_ID}/
        match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
        if match:
            return match.group(1)
        
        # Pattern 2: id={FILE_ID}
        match = re.search(r'[?&]id=([a-zA-Z0-9-_]+)', url)
        if match:
            return match.group(1)
        
        return None
    
    @staticmethod
    def convert_to_direct_download_url(file_id: str) -> str:
        """
        Convert Google Drive file ID to direct download URL
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            Direct download URL (can be used in img tags or to download)
        """
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    
    @staticmethod
    def is_google_drive_url(url: str) -> bool:
        """Check if URL is a Google Drive link"""
        if not url:
            return False
        return 'google.com' in url.lower() or 'drive.google.com' in url.lower()
    
    @staticmethod
    def get_direct_url_from_google_drive(url: str) -> Optional[str]:
        """
        Convert Google Drive sharing link to direct usable URL
        
        Args:
            url: Google Drive URL
            
        Returns:
            Direct URL or None if conversion failed
        """
        try:
            file_id = GoogleDriveImageDownloader.extract_file_id_from_url(url)
            if not file_id:
                logger.error(f"Could not extract file ID from Google Drive URL: {url}")
                return None
            
            direct_url = GoogleDriveImageDownloader.convert_to_direct_download_url(file_id)
            logger.info(f"Converted Google Drive URL to: {direct_url}")
            return direct_url
            
        except Exception as e:
            logger.error(f"Error converting Google Drive URL: {str(e)}")
            return None
    
    @staticmethod
    def download_image_from_google_drive(url: str, timeout: int = 30) -> Tuple[bool, Optional[bytes], Optional[str]]:
        """
        Download image from Google Drive URL
        
        Args:
            url: Google Drive URL or direct download URL
            timeout: Request timeout in seconds
            
        Returns:
            (success, image_bytes, error_message)
        """
        try:
            # Convert to direct download URL if needed
            if GoogleDriveImageDownloader.is_google_drive_url(url):
                direct_url = GoogleDriveImageDownloader.get_direct_url_from_google_drive(url)
                if not direct_url:
                    return False, None, "Could not convert Google Drive URL to direct download URL"
            else:
                direct_url = url
            
            logger.info(f"Downloading image from: {direct_url}")
            
            # Download with timeout and follow redirects
            response = requests.get(
                direct_url,
                timeout=timeout,
                allow_redirects=True,
                stream=True
            )
            
            if response.status_code != 200:
                return False, None, f"HTTP {response.status_code}: {response.reason}"
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if not any(img_type in content_type for img_type in ['image', 'jpeg', 'png', 'gif', 'webp']):
                logger.warning(f"Content-Type is {content_type}, but proceeding anyway")
            
            # Get image bytes
            image_bytes = response.content
            
            if not image_bytes:
                return False, None, "Downloaded empty file"
            
            # Check file size (Shopify has limits)
            file_size_mb = len(image_bytes) / (1024 * 1024)
            if file_size_mb > 20:  # Shopify typical limit
                logger.warning(f"Image is {file_size_mb:.1f}MB - may exceed Shopify limits (max ~20MB)")
            
            logger.info(f"✅ Downloaded {len(image_bytes)} bytes ({file_size_mb:.2f}MB)")
            return True, image_bytes, None
            
        except requests.exceptions.Timeout:
            return False, None, f"Download timeout after {timeout}s"
        except requests.exceptions.ConnectionError as e:
            return False, None, f"Connection error: {str(e)}"
        except Exception as e:
            return False, None, f"Download failed: {str(e)}"
    
    @staticmethod
    def get_image_format_from_bytes(image_bytes: bytes) -> str:
        """
        Detect image format from file bytes
        
        Returns:
            Format string: 'jpeg', 'png', 'gif', 'webp', or 'unknown'
        """
        if not image_bytes or len(image_bytes) < 4:
            return 'unknown'
        
        # Magic bytes for common formats
        if image_bytes[:2] == b'\xff\xd8':
            return 'jpeg'
        elif image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            return 'png'
        elif image_bytes[:4] == b'GIF8' or image_bytes[:4] == b'GIF9':
            return 'gif'
        elif image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
            return 'webp'
        
        return 'unknown'
