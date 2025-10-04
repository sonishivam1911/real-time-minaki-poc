import datetime
import time
from collections import defaultdict
from typing import List, Dict, Any, Optional, Iterator

from .base_connector  import BaseShopifyConnector
from .product import ShopifyProductService

class ShopifyNamespaceService:
    """
    Enhanced Shopify GraphQL API connector with comprehensive CRUD operations
    and optimized namespace management.
    """
    
    def __init__(self, client: BaseShopifyConnector = None):
        """
        Initialize product service.
        
        Args:
            client: GraphQL client (creates new one if not provided)
        """
        self.client = client or BaseShopifyConnector()
        self.product_service = ShopifyProductService(self.client)        
    
    def get_products_batch_for_db(self, batch_size: int = 50) -> Iterator[List[Dict]]:
        """
        Generator that yields batches of products for database storage.
        
        Args:
            batch_size: Number of products per batch
            
        Yields:
            List of product dictionaries
        """
        cursor = None
        
        while True:
            try:
                result = self.product_service.get_products(first=batch_size, after=cursor)
                
                if not result.get('data', {}).get('products', {}).get('edges'):
                    break
                
                products = result['data']['products']
                batch_products = [edge['node'] for edge in products['edges']]
                
                if not batch_products:
                    break
                
                yield batch_products
                
                # Check pagination
                page_info = products.get('pageInfo', {})
                if not page_info.get('hasNextPage'):
                    break
                    
                cursor = page_info.get('endCursor')
                
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Error in batch processing: {str(e)}")
                break

    def get_all_unique_namespaces(self, use_cache: bool = True) -> List[str]:
        """
        Get all unique metafield namespaces across the store.
        
        Args:
            use_cache: Whether to use cached data if available
            
        Returns:
            List of unique namespace strings
        """
        try:
            # For now, do a lightweight scan of recent products
            # In production, this should check cache first
            namespaces = set()
            processed_count = 0
            max_products = 500  # Limit for quick namespace discovery
            
            for batch in self.get_products_batch_for_db(batch_size=50):
                for product in batch:
                    metafields = product.get('metafields', {}).get('edges', [])
                    for metafield_edge in metafields:
                        namespace = metafield_edge['node'].get('namespace')
                        if namespace:
                            namespaces.add(namespace)
                
                processed_count += len(batch)
                if processed_count >= max_products:
                    break
            
            result = sorted(list(namespaces))
            print(f"Found {len(result)} unique namespaces from {processed_count} products")
            return result
            
        except Exception as e:
            print(f"Error getting unique namespaces: {str(e)}")
            return []

    def get_namespace_keys(self, namespace: str, max_products: Optional[int] = 100) -> Dict[str, Any]:
        """
        Get all unique keys for a specific namespace.
        
        Args:
            namespace: Target namespace to analyze
            max_products: Maximum products to scan (None = all products)
            
        Returns:
            Dictionary with namespace keys analysis
        """
        try:
            keys_data = defaultdict(lambda: {
                'count': 0,
                'product_ids': set(),
                'sample_values': [],
                'field_types': set()
            })
            
            products_scanned = 0
            total_metafields_found = 0
            
            print(f"Scanning namespace '{namespace}' for unique keys...")
            
            for batch in self.get_products_batch_for_db(batch_size=50):
                for product in batch:
                    product_id = product.get('id', '').replace('gid://shopify/Product/', '')
                    metafields = product.get('metafields', {}).get('edges', [])
                    
                    for metafield_edge in metafields:
                        metafield = metafield_edge['node']
                        
                        # Only process metafields in the target namespace
                        if metafield.get('namespace') == namespace:
                            key = metafield.get('key', 'unknown')
                            value = metafield.get('value', '')
                            field_type = metafield.get('type', 'unknown')
                            
                            key_stats = keys_data[key]
                            key_stats['count'] += 1
                            key_stats['product_ids'].add(product_id)
                            key_stats['field_types'].add(field_type)
                            
                            # Store sample values (limit to 3 per key)
                            if len(key_stats['sample_values']) < 3:
                                sample_value = value[:150] if len(value) > 150 else value
                                key_stats['sample_values'].append({
                                    'value': sample_value,
                                    'product_id': product_id,
                                    'type': field_type
                                })
                            
                            total_metafields_found += 1
                
                products_scanned += len(batch)
                
                if max_products and products_scanned >= max_products:
                    break
            
            # Convert to final format
            final_keys = {}
            for key, stats in keys_data.items():
                final_keys[key] = {
                    'key': key,
                    'metafield_count': stats['count'],
                    'product_count': len(stats['product_ids']),
                    'field_types': list(stats['field_types']),
                    'sample_values': stats['sample_values'],
                    'sample_product_ids': list(stats['product_ids'])[:5]
                }
            
            result = {
                'namespace': namespace,
                'unique_keys_count': len(keys_data),
                'total_metafields': total_metafields_found,
                'products_scanned': products_scanned,
                'keys': final_keys,
                'analysis_timestamp': datetime.datetime.now().isoformat()
            }
            
            print(f"Found {len(keys_data)} unique keys in namespace '{namespace}'")
            return result
            
        except Exception as e:
            print(f"Error analyzing namespace '{namespace}': {str(e)}")
            raise

    def get_all_namespaces_with_keys(self, max_products: Optional[int] = 200) -> Dict[str, Any]:
        """
        Get all namespaces with their unique keys.
        
        Args:
            max_products: Maximum products to scan
            
        Returns:
            Complete namespace and keys analysis
        """
        try:
            namespace_keys = defaultdict(lambda: defaultdict(lambda: {
                'count': 0,
                'product_ids': set(),
                'field_types': set()
            }))
            
            products_scanned = 0
            
            print("Scanning all namespaces for keys...")
            
            for batch in self.get_products_batch_for_db(batch_size=50):
                for product in batch:
                    product_id = product.get('id', '').replace('gid://shopify/Product/', '')
                    metafields = product.get('metafields', {}).get('edges', [])
                    
                    for metafield_edge in metafields:
                        metafield = metafield_edge['node']
                        namespace = metafield.get('namespace', 'unknown')
                        key = metafield.get('key', 'unknown')
                        field_type = metafield.get('type', 'unknown')
                        
                        key_stats = namespace_keys[namespace][key]
                        key_stats['count'] += 1
                        key_stats['product_ids'].add(product_id)
                        key_stats['field_types'].add(field_type)
                
                products_scanned += len(batch)
                
                if max_products and products_scanned >= max_products:
                    break
            
            # Convert to final format
            final_result = {}
            for namespace, keys in namespace_keys.items():
                namespace_data = {
                    'namespace': namespace,
                    'unique_keys_count': len(keys),
                    'keys': {}
                }
                
                for key, stats in keys.items():
                    namespace_data['keys'][key] = {
                        'key': key,
                        'metafield_count': stats['count'],
                        'product_count': len(stats['product_ids']),
                        'field_types': list(stats['field_types'])
                    }
                
                final_result[namespace] = namespace_data
            
            summary = {
                'total_namespaces': len(namespace_keys),
                'products_scanned': products_scanned,
                'analysis_timestamp': datetime.datetime.now().isoformat()
            }
            
            return {
                'summary': summary,
                'namespaces': final_result
            }
            
        except Exception as e:
            print(f"Error in namespace keys analysis: {str(e)}")
            raise

    def create_namespace_with_fields(self, product_id: str, namespace: str, 
                                    fields_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new namespace by adding multiple fields to it at once.
        
        Args:
            product_id: Target product ID
            namespace: New namespace name
            fields_data: Dictionary of {key: {"value": value, "type": type}}
            
        Example:
            create_namespace_with_fields(
                "5714011652253", 
                "my_custom_namespace",
                {
                    "color": {"value": "Blue", "type": "single_line_text_field"},
                    "size": {"value": "Large", "type": "single_line_text_field"},
                    "weight": {"value": "1.5", "type": "number_decimal"}
                }
            )
        """
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        metafields = []
        for key, field_info in fields_data.items():
            metafield = {
                "ownerId": product_id,
                "namespace": namespace,
                "key": key,
                "value": field_info["value"],
                "type": field_info.get("type", "single_line_text_field")
            }
            metafields.append(metafield)
        
        try:
            result = self.bulk_update_metafields(metafields)
            print(f"Created namespace '{namespace}' with {len(metafields)} fields")
            return result
        except Exception as e:
            print(f"Error creating namespace '{namespace}': {str(e)}")
            raise

 