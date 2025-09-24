from typing import List, Dict, Any, Optional
from ..repositories.product_repository import ProductRepository
from ..repositories.metafield_repository import MetafieldRepository
from ..repositories.image_repository import ImageRepository
from ..processors.variant_processor import VariantProcessor
from ..processors.image_processor import ImageProcessor

class ProductService:
    """Service for complex product operations combining multiple repositories"""
    
    def __init__(self):
        self.product_repo = ProductRepository()
        self.metafield_repo = MetafieldRepository()
        self.image_repo = ImageRepository()
        self.variant_processor = VariantProcessor()
        self.image_processor = ImageProcessor()
    
    def create_product_with_variants(
        self, 
        product_data: Dict[str, Any], 
        variants_data: Optional[List[Dict[str, Any]]] = None,
        images_data: Optional[List[Dict[str, Any]]] = None,
        metafields_data: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Create a product with variants, images, and metafields in a coordinated way."""
        
        try:
            # Step 1: Create the base product
            product_result = self.product_repo.create_product(product_data)
            
            if 'errors' in product_result or product_result.get('data', {}).get('productCreate', {}).get('userErrors'):
                return {
                    'success': False,
                    'message': 'Failed to create product',
                    'error': product_result.get('errors') or product_result.get('data', {}).get('productCreate', {}).get('userErrors')
                }
            
            created_product = product_result['data']['productCreate']['product']
            product_id = created_product['id']
            
            results = {
                'success': True,
                'product': created_product,
                'product_id': product_id,
                'variants_created': 0,
                'images_uploaded': 0,
                'metafields_created': 0
            }
            
            # Step 2: Create variants if provided
            if variants_data:
                variants_result = self.variant_processor.create_variants_for_product(product_id, variants_data)
                results['variants_result'] = variants_result
                results['variants_created'] = len(variants_result.get('variants', []))
            
            # Step 3: Upload images if provided
            if images_data:
                processed_images = self.image_processor.process_and_upload_images(product_id, images_data)
                results['images_result'] = processed_images
                results['images_uploaded'] = len([img for img in processed_images if 'error' not in img])
            
            # Step 4: Add metafields if provided
            if metafields_data:
                formatted_metafields = []
                for mf_data in metafields_data:
                    mf_data['owner_id'] = product_id
                    formatted_metafields.append(mf_data)
                
                metafields_result = self.metafield_repo.bulk_create_metafields(formatted_metafields)
                results['metafields_result'] = metafields_result
                
                if metafields_result.get('data', {}).get('metafieldsSet', {}).get('metafields'):
                    results['metafields_created'] = len(metafields_result['data']['metafieldsSet']['metafields'])
            
            return results
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error creating product with variants: {str(e)}',
                'error': str(e)
            }
    
    def get_product_with_all_data(self, product_id: str, include_all_metafields: bool = False) -> Dict[str, Any]:
        """Get a product with all its data - variants, images, and metafields."""
        
        try:
            # Get basic product data
            product_result = self.product_repo.get_product_by_id(
                product_id, 
                include_variants=True, 
                include_images=True
            )
            
            if not product_result.get('data', {}).get('product'):
                return {
                    'success': False,
                    'message': f'Product {product_id} not found'
                }
            
            product_data = product_result['data']['product']
            
            # Get metafields if requested
            if include_all_metafields:
                metafields = self.metafield_repo.get_all_metafields_paginated(product_id)
                product_data['all_metafields'] = metafields
            
            return {
                'success': True,
                'product': product_data
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error fetching product data: {str(e)}',
                'error': str(e)
            }
    
    def filter_products(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Filter products based on various criteria including metafields."""
        
        try:
            # Build Shopify query from filters
            query_parts = []
            
            # Basic product filters
            if filters.get('title'):
                query_parts.append(f"title:*{filters['title']}*")
            if filters.get('product_type'):
                query_parts.append(f"product_type:{filters['product_type']}")
            if filters.get('vendor'):
                query_parts.append(f"vendor:{filters['vendor']}")
            if filters.get('status'):
                query_parts.append(f"status:{filters['status']}")
            if filters.get('tags'):
                for tag in filters['tags']:
                    query_parts.append(f"tag:{tag}")
            
            shopify_query = " AND ".join(query_parts) if query_parts else None
            
            # Get products from repository
            result = self.product_repo.get_products(
                first=filters.get('limit', 50),
                after=filters.get('after'),
                query_filter=shopify_query
            )
            
            # Post-process for metafield filtering if needed
            if filters.get('metafield_filters'):
                filtered_products = self._filter_by_metafields(
                    result.get('data', {}).get('products', {}).get('edges', []),
                    filters['metafield_filters']
                )
                result['data']['products']['edges'] = filtered_products
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error filtering products: {str(e)}',
                'error': str(e)
            }
    
    def _filter_by_metafields(self, product_edges: List[Dict], metafield_filters: Dict) -> List[Dict]:
        """Filter products based on metafield criteria."""
        
        filtered_edges = []
        
        for edge in product_edges:
            product = edge['node']
            product_id = product['id']
            
            # Check if product matches metafield filters
            matches_filters = True
            
            for namespace, key_filters in metafield_filters.items():
                if not matches_filters:
                    break
                
                # Get metafields for this namespace
                metafields = self.metafield_repo.get_metafields_by_namespace(product_id, namespace)
                
                for key, expected_value in key_filters.items():
                    metafield_found = False
                    for mf in metafields:
                        if mf['key'] == key and mf['value'] == expected_value:
                            metafield_found = True
                            break
                    
                    if not metafield_found:
                        matches_filters = False
                        break
            
            if matches_filters:
                filtered_edges.append(edge)
        
        return filtered_edges
    
    def update_product_with_variants(self, product_id: str, product_data: Dict[str, Any], 
                                   variants_updates: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Update a product and its variants."""
        
        try:
            results = {
                'success': True,
                'product_updated': False,
                'variants_updated': 0
            }
            
            # Update product if data provided
            if product_data:
                product_result = self.product_repo.update_product(product_id, product_data)
                
                if 'errors' in product_result or product_result.get('data', {}).get('productUpdate', {}).get('userErrors'):
                    return {
                        'success': False,
                        'message': 'Failed to update product',
                        'error': product_result.get('errors') or product_result.get('data', {}).get('productUpdate', {}).get('userErrors')
                    }
                
                results['product_updated'] = True
                results['product'] = product_result['data']['productUpdate']['product']
            
            # Update variants if provided
            if variants_updates:
                variants_result = self.variant_processor.update_variants(variants_updates)
                results['variants_result'] = variants_result
                results['variants_updated'] = len(variants_updates)
            
            return results
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error updating product: {str(e)}',
                'error': str(e)
            }
    
    def delete_product_completely(self, product_id: str) -> Dict[str, Any]:
        """Delete a product and all its associated data."""
        
        try:
            # Get product first to check if it exists
            product_result = self.product_repo.get_product_by_id(product_id, include_variants=False, include_images=False)
            
            if not product_result.get('data', {}).get('product'):
                return {
                    'success': False,
                    'message': f'Product {product_id} not found'
                }
            
            # Delete the product (this will cascade delete variants, images, and metafields)
            delete_result = self.product_repo.delete_product(product_id)
            
            if 'errors' in delete_result or delete_result.get('data', {}).get('productDelete', {}).get('userErrors'):
                return {
                    'success': False,
                    'message': 'Failed to delete product',
                    'error': delete_result.get('errors') or delete_result.get('data', {}).get('productDelete', {}).get('userErrors')
                }
            
            return {
                'success': True,
                'message': f'Product {product_id} deleted successfully',
                'deleted_product_id': delete_result['data']['productDelete']['deletedProductId']
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error deleting product: {str(e)}',
                'error': str(e)
            }