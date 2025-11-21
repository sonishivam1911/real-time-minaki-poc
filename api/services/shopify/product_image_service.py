"""
Product Image Service for Shopify
Handles image uploads to Shopify products using GraphQL mutations
Supports downloading from Google Drive and uploading directly to Shopify CDN
"""

import time
import json
import logging
from typing import List, Dict, Any, Optional
from .base_connector import BaseShopifyConnector
from services.google_drive.image_downloader import GoogleDriveImageDownloader
from services.google_drive.cdn_uploader import GoogleDriveToCDN

logger = logging.getLogger(__name__)


class ProductImageService:
    """Service for uploading images to Shopify products"""
    
    def __init__(self, client: BaseShopifyConnector = None):
        self.client = client or BaseShopifyConnector()
    
    def add_images_to_product_via_mutation(self, product_id: str, image_urls: List[str], 
                                           title: str = "") -> List[Dict[str, Any]]:
        """
        Add images to existing product using productCreateMedia mutation
        Automatically handles Google Drive URLs by:
        1. Downloading from Google Drive
        2. Uploading to Shopify CDN via stagedUploadsCreate
        3. Attaching to product via productCreateMedia
        
        Args:
            product_id: Shopify product ID  
            image_urls: List of image URLs (can include Google Drive links)
            title: Product title for alt text
            
        Returns:
            List of image upload results with success/error status for each
        """
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        results = []
        processed_urls = []
        
        # Process and prepare images (download Google Drive links if needed)
        logger.info(f"📸 Processing {len(image_urls)} images for product {product_id}")
        
        for idx, url in enumerate(image_urls):
            if not url or not url.strip():
                continue
            
            url = url.strip()
            position = idx + 1
            
            # Handle Google Drive URLs - download and upload to Shopify CDN
            if GoogleDriveImageDownloader.is_google_drive_url(url):
                logger.info(f"📥 Processing Google Drive image {position}: {url[:60]}...")
                
                # Step 1: Download from Google Drive
                success, image_bytes, error = GoogleDriveImageDownloader.download_image_from_google_drive(url)
                
                if not success:
                    logger.error(f"❌ Failed to download Google Drive image {position}: {error}")
                    results.append({
                        'success': False,
                        'position': position,
                        'url': url,
                        'error': f'Failed to download: {error}',
                        'image_id': None
                    })
                    continue
                
                logger.info(f"✅ Downloaded {len(image_bytes)} bytes from Google Drive")
                
                # Step 2: Upload to Shopify CDN
                filename = f"product-image-{position}.jpg"
                cdn_success, cdn_url, cdn_error = GoogleDriveToCDN.upload_to_shopify_cdn(
                    image_bytes=image_bytes,
                    filename=filename,
                    shopify_client=self.client
                )
                
                if not cdn_success:
                    logger.error(f"❌ Failed to upload to Shopify CDN: {cdn_error}")
                    results.append({
                        'success': False,
                        'position': position,
                        'url': url,
                        'error': f'Failed to upload to CDN: {cdn_error}',
                        'image_id': None,
                        'is_google_drive': True
                    })
                    continue
                
                logger.info(f"✅ Uploaded to Shopify CDN: {cdn_url}")
                
                # Use the CDN URL for product attachment
                processed_urls.append({
                    'original_url': url,
                    'cdn_url': cdn_url,
                    'position': position,
                    'is_google_drive': True
                })
            else:
                # Regular URL - pass through directly
                processed_urls.append({
                    'original_url': url,
                    'cdn_url': url,
                    'position': position,
                    'is_google_drive': False
                })
        
        if not processed_urls:
            logger.warning(f"⚠️  No valid URLs to upload for product {product_id}")
            return results
        
        # Upload to Shopify in batches using productCreateMedia
        batch_size = 10  # Shopify recommends max 10 images per mutation
        
        for batch_start in range(0, len(processed_urls), batch_size):
            batch = processed_urls[batch_start:batch_start + batch_size]
            
            # Build media array for this batch
            media = []
            for item in batch:
                cdn_url = item['cdn_url']
                position = item['position']
                
                media.append({
                    'mediaContentType': 'IMAGE',
                    'originalSource': cdn_url,
                    'alt': f"{title} - Image {position}" if title else f"Product Image {position}"
                })
            
            if not media:
                continue
            
            # Use productCreateMedia mutation
            mutation = """
            mutation productUpdateMedia($input: ProductInput!, $media: [CreateMediaInput!]!) {
                productUpdate(
                    input: $input,
                    media: $media
                ) {
                    product {
                        id
                        media(first: 20) {
                            nodes {
                                ... on MediaImage {
                                    id
                                    alt
                                    image {
                                        url
                                    }
                                }
                            }
                        }
                    }
                    userErrors {
                        field
                        message
                    }
                }
            }
            """

            try:
                logger.info(f"📤 Uploading batch of {len(media)} images to Shopify product...")
                logger.info(f"Media payload: {json.dumps(media, indent=2)}")
                logger.info(f"Product ID: {product_id}")
                
                result = self.client.execute_query(mutation, {
                    'input': {
                        'id': product_id
                    },
                    'media': media
                })

                logger.info(f"Raw image upload response: {result}")
                logger.info(f"Response type: {type(result)}")

                # Check what you're trying to access
                if result is None:
                    logger.error("Response is None!")
                    # Add errors for all images in this batch
                    for item in batch:
                        results.append({
                            'success': False,
                            'position': item['position'],
                            'url': item['original_url'],
                            'error': 'GraphQL response was None',
                            'image_id': None,
                            'is_google_drive': item.get('is_google_drive', False)
                        })
                    continue  # Skip to next batch instead of returning

                if 'data' not in result:
                    logger.error(f"No 'data' key in response. Keys: {result.keys() if result else 'N/A'}")
                    # Add errors for all images in this batch
                    for item in batch:
                        results.append({
                            'success': False,
                            'position': item['position'],
                            'url': item['original_url'],
                            'error': f"No 'data' in response. Keys: {list(result.keys()) if result else 'None'}",
                            'image_id': None,
                            'is_google_drive': item.get('is_google_drive', False)
                        })
                    continue  # Skip to next batch instead of returning
                
                if result.get('errors'):
                    # GraphQL errors
                    error_msg = str(result['errors'])
                    logger.error(f"❌ GraphQL errors: {error_msg}")
                    for item in batch:
                        results.append({
                            'success': False,
                            'position': item['position'],
                            'url': item['original_url'],
                            'error': f'GraphQL error: {error_msg}',
                            'image_id': None,
                            'is_google_drive': item['is_google_drive']
                        })
                else:
                    # Check for user errors
                    mutation_data = result.get('data', {}).get('productUpdate', {})
                    user_errors = mutation_data.get('mediaUserErrors', [])
                    
                    if user_errors:
                        error_msg = ', '.join([f"{err['field']}: {err['message']}" for err in user_errors])
                        logger.error(f"❌ Media user errors: {error_msg}")
                        for item in batch:
                            results.append({
                                'success': False,
                                'position': item['position'],
                                'url': item['original_url'],
                                'error': error_msg,
                                'image_id': None,
                                'is_google_drive': item['is_google_drive']
                            })
                    else:
                        # Success - get the media IDs from response
                        media_items = mutation_data.get('media', [])
                        
                        for item, media_item in zip(batch, media_items):
                            if media_item:
                                results.append({
                                    'success': True,
                                    'position': item['position'],
                                    'url': item['original_url'],
                                    'error': None,
                                    'image_id': media_item.get('id'),
                                    'image_url': media_item.get('image', {}).get('url'),
                                    'is_google_drive': item['is_google_drive']
                                })
                                logger.info(f"✅ Image {item['position']} uploaded successfully")
                            else:
                                results.append({
                                    'success': False,
                                    'position': item['position'],
                                    'url': item['original_url'],
                                    'error': 'Media item not returned in response',
                                    'image_id': None,
                                    'is_google_drive': item['is_google_drive']
                                })
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ Exception uploading batch: {error_msg}")
                for item in batch:
                    results.append({
                        'success': False,
                        'position': item['position'],
                        'url': item['original_url'],
                        'error': error_msg,
                        'image_id': None,
                        'is_google_drive': item['is_google_drive']
                    })
            
            # Rate limiting between batches
            time.sleep(1)
        
        # Summary
        successful = sum(1 for r in results if r['success'])
        google_drive_count = sum(1 for r in results if r.get('is_google_drive'))
        logger.info(f"📊 Image upload summary: {successful}/{len(results)} images uploaded successfully")
        logger.info(f"📊 Google Drive images: {google_drive_count}/{len(results)}")
        
        return results
    
    def validate_image_url(self, url: str) -> tuple:
        """
        Validate if image URL is valid for Shopify
        
        Returns:
            (is_valid, error_message)
        """
        if not url or not url.strip():
            return False, "URL is empty"
        
        url = url.strip()
        
        # Google Drive URLs are now supported (will be uploaded to CDN)
        if 'google.com' in url.lower() or 'drive.google.com' in url.lower():
            return True, None  # Supported via CDN upload
        
        # Check for basic URL format
        if not url.startswith('http'):
            return False, "URL must start with http:// or https://"
        
        # URL looks reasonable
        return True, None
