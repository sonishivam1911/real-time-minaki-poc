from typing import List, Dict, Any, Optional
from ..repositories.image_repository import ImageRepository
import base64
import os
from urllib.parse import urlparse

class ImageProcessor:
    """Processor for handling image operations and preprocessing"""
    
    def __init__(self):
        self.image_repo = ImageRepository()
        self.supported_formats = ['jpg', 'jpeg', 'png', 'gif', 'webp']
        self.max_file_size = 20 * 1024 * 1024  # 20MB limit
    
    def process_and_upload_images(self, product_id: str, images_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process and upload multiple images to a product."""
        
        results = []
        
        for image_data in images_data:
            try:
                # Validate image
                validation_result = self.validate_image_data(image_data)
                
                if not validation_result['valid']:
                    results.append({
                        'error': f"Image validation failed: {validation_result['error']}",
                        'image_data': image_data
                    })
                    continue
                
                # Process image
                processed_image = self.preprocess_image_data(image_data)
                
                # Upload to Shopify
                upload_result = self.image_repo.upload_product_image(product_id, processed_image)
                
                if 'errors' in upload_result or upload_result.get('data', {}).get('productImageCreate', {}).get('userErrors'):
                    errors = upload_result.get('errors', []) + upload_result.get('data', {}).get('productImageCreate', {}).get('userErrors', [])
                    results.append({
                        'error': f"Upload failed: {errors}",
                        'image_data': image_data
                    })
                else:
                    uploaded_image = upload_result['data']['productImageCreate']['image']
                    results.append({
                        'success': True,
                        'image': uploaded_image,
                        'original_data': image_data
                    })
                    
            except Exception as e:
                results.append({
                    'error': f"Processing error: {str(e)}",
                    'image_data': image_data
                })
        
        return results
    
    def validate_image_data(self, image_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate image data before processing."""
        
        # Check required fields
        if 'src' not in image_data and 'attachment' not in image_data:
            return {
                'valid': False,
                'error': 'Image must have either "src" (URL) or "attachment" (base64) field'
            }
        
        # Validate URL if provided
        if 'src' in image_data:
            url = image_data['src']
            parsed_url = urlparse(url)
            
            if not parsed_url.scheme or not parsed_url.netloc:
                return {
                    'valid': False,
                    'error': 'Invalid image URL format'
                }
            
            # Check file extension
            path = parsed_url.path.lower()
            if not any(path.endswith(f'.{fmt}') for fmt in self.supported_formats):
                return {
                    'valid': False,
                    'error': f'Unsupported image format. Supported: {", ".join(self.supported_formats)}'
                }
        
        # Validate base64 attachment if provided
        if 'attachment' in image_data:
            try:
                attachment = image_data['attachment']
                if not isinstance(attachment, str):
                    return {
                        'valid': False,
                        'error': 'Attachment must be a base64 encoded string'
                    }
                
                # Try to decode to validate
                decoded = base64.b64decode(attachment)
                
                # Check file size
                if len(decoded) > self.max_file_size:
                    return {
                        'valid': False,
                        'error': f'Image too large. Max size: {self.max_file_size / (1024*1024):.1f}MB'
                    }
                
            except Exception as e:
                return {
                    'valid': False,
                    'error': f'Invalid base64 attachment: {str(e)}'
                }
        
        return {'valid': True}
    
    def preprocess_image_data(self, image_data: Dict[str, Any]) -> Dict[str, Any]:
        """Preprocess image data before upload."""
        
        processed_data = image_data.copy()
        
        # Clean alt text
        if 'altText' in processed_data:
            alt_text = processed_data['altText'].strip()
            # Remove excessive whitespace
            alt_text = ' '.join(alt_text.split())
            # Limit length
            if len(alt_text) > 512:
                alt_text = alt_text[:509] + '...'
            processed_data['altText'] = alt_text
        
        # Set default alt text if not provided
        if 'altText' not in processed_data or not processed_data['altText']:
            if 'filename' in image_data:
                # Generate alt text from filename
                filename = os.path.splitext(image_data['filename'])[0]
                processed_data['altText'] = filename.replace('_', ' ').replace('-', ' ').title()
            else:
                processed_data['altText'] = 'Product image'
        
        return processed_data
    
    def upload_images_from_urls(self, product_id: str, image_urls: List[str], 
                              alt_texts: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Upload images from URLs."""
        
        images_data = []
        
        for i, url in enumerate(image_urls):
            image_data = {'src': url}
            
            # Add alt text if provided
            if alt_texts and i < len(alt_texts):
                image_data['altText'] = alt_texts[i]
            
            images_data.append(image_data)
        
        return self.process_and_upload_images(product_id, images_data)
    
    def upload_images_from_base64(self, product_id: str, base64_images: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Upload images from base64 encoded data."""
        
        images_data = []
        
        for img_data in base64_images:
            image_data = {
                'attachment': img_data['data'],
                'filename': img_data.get('filename', 'image.jpg'),
                'altText': img_data.get('alt_text', '')
            }
            images_data.append(image_data)
        
        return self.process_and_upload_images(product_id, images_data)
    
    def associate_images_with_variants(self, product_id: str, variant_image_mapping: Dict[str, str]) -> Dict[str, Any]:
        """Associate uploaded images with specific variants."""
        
        results = {
            'success': True,
            'associations': [],
            'errors': []
        }
        
        for variant_id, image_id in variant_image_mapping.items():
            try:
                result = self.image_repo.associate_image_to_variant(variant_id, image_id)
                
                if 'errors' in result or result.get('data', {}).get('productVariantUpdate', {}).get('userErrors'):
                    errors = result.get('errors', []) + result.get('data', {}).get('productVariantUpdate', {}).get('userErrors', [])
                    results['errors'].append({
                        'variant_id': variant_id,
                        'image_id': image_id,
                        'error': errors
                    })
                    results['success'] = False
                else:
                    updated_variant = result['data']['productVariantUpdate']['productVariant']
                    results['associations'].append({
                        'variant_id': variant_id,
                        'image_id': image_id,
                        'variant': updated_variant
                    })
                    
            except Exception as e:
                results['errors'].append({
                    'variant_id': variant_id,
                    'image_id': image_id,
                    'error': str(e)
                })
                results['success'] = False
        
        return results
    
    def set_product_featured_image(self, product_id: str, image_id: str) -> Dict[str, Any]:
        """Set a specific image as the featured image."""
        
        try:
            result = self.image_repo.set_featured_image(product_id, image_id)
            
            if 'errors' in result or result.get('data', {}).get('productUpdate', {}).get('userErrors'):
                errors = result.get('errors', []) + result.get('data', {}).get('productUpdate', {}).get('userErrors', [])
                return {
                    'success': False,
                    'message': 'Failed to set featured image',
                    'error': errors
                }
            
            updated_product = result['data']['productUpdate']['product']
            
            return {
                'success': True,
                'message': f'Featured image set successfully',
                'product': updated_product,
                'featured_image': updated_product.get('featuredImage')
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error setting featured image: {str(e)}',
                'error': str(e)
            }
    
    def optimize_image_order(self, product_id: str, optimization_strategy: str = 'featured_first') -> Dict[str, Any]:
        """Optimize the order of product images based on strategy."""
        
        try:
            # Get current images
            images_result = self.image_repo.get_product_images(product_id)
            
            if not images_result.get('data', {}).get('product', {}).get('images'):
                return {
                    'success': False,
                    'message': 'No images found for product'
                }
            
            images_data = images_result['data']['product']['images']['edges']
            images = [edge['node'] for edge in images_data]
            
            if len(images) <= 1:
                return {
                    'success': True,
                    'message': 'Only one image, no reordering needed'
                }
            
            # Apply optimization strategy
            if optimization_strategy == 'featured_first':
                featured_image = images_result['data']['product'].get('featuredImage')
                if featured_image:
                    # Move featured image to first position
                    other_images = [img for img in images if img['id'] != featured_image['id']]
                    optimized_order = [featured_image['id']] + [img['id'] for img in other_images]
                else:
                    optimized_order = [img['id'] for img in images]
            elif optimization_strategy == 'alphabetical':
                # Sort by alt text alphabetically
                sorted_images = sorted(images, key=lambda x: x.get('altText', ''))
                optimized_order = [img['id'] for img in sorted_images]
            else:
                # Default: keep current order
                optimized_order = [img['id'] for img in images]
            
            # Reorder images
            reorder_result = self.image_repo.reorder_product_images(product_id, optimized_order)
            
            return {
                'success': True,
                'message': f'Images reordered using {optimization_strategy} strategy',
                'new_order': optimized_order,
                'reorder_result': reorder_result
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error optimizing image order: {str(e)}',
                'error': str(e)
            }