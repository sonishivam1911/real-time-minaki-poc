# services/shopify_service.py
import requests
import datetime
import time
import json
from collections import defaultdict
from typing import List, Dict, Any, Optional, Iterator

from core.config import settings

class ShopifyGraphQLConnector:
    """
    Enhanced Shopify GraphQL API connector with comprehensive CRUD operations
    and optimized namespace management.
    """
    
    def __init__(self):
        """
        Initialize the GraphQL connector.
        
        Args:
            shop_url: Your shop URL (e.g., 'your-shop.myshopify.com')
            api_version: API version (e.g., '2025-01')
            access_token: Your private app access token
        """
        self.shop_url = settings.SHOPIFY_SHOP_URL
        self.api_version = settings.SHOPIFY_API_VERSION
        self.access_token = settings.SHOPIFY_ACCESS_TOKEN
        self.graphql_endpoint = f"https://{self.shop_url}/admin/api/{self.api_version}/graphql.json"
        
        # Setup headers for GraphQL requests
        self.headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': self.access_token
        }
    
    def execute_query(self, query: str, variables: Optional[Dict] = None):
        """Execute a GraphQL query against Shopify's API."""
        try:
            payload = {
                'query': query
            }
            
            if variables:
                payload['variables'] = variables
            
            print(f"Executing GraphQL query to {self.graphql_endpoint}")
            
            response = requests.post(
                self.graphql_endpoint,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Check for GraphQL errors
            if 'errors' in result:
                print(f"GraphQL errors: {result['errors']}")
                raise Exception(f"GraphQL errors: {result['errors']}")
            
            print("GraphQL query executed successfully")
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"HTTP request failed: {str(e)}")
            raise
        except Exception as e:
            print(f"GraphQL query execution failed: {str(e)}")
            raise

    def get_complete_product_with_metafields(self, product_id: str) -> Dict[str, Any]:
        """
        Get a product with ALL metafields using pagination.
        
        Args:
            product_id: Shopify product ID (with or without gid prefix)
            
        Returns:
            Complete product data with all metafields
        """
        # Ensure proper GraphQL ID format
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        # Get basic product info first
        product_result = self.get_product_by_id(product_id)
        
        if not product_result.get('data', {}).get('product'):
            return {"data": {"product": None}, "error": "Product not found"}
        
        product = product_result['data']['product']
        all_metafields = []
        cursor = None
        
        # Paginate through all metafields
        while True:
            metafields_query = """
            query getProductMetafields($id: ID!, $after: String) {
                product(id: $id) {
                    metafields(first: 250, after: $after) {
                        edges {
                            node {
                                id
                                namespace
                                key
                                value
                                type
                                description
                                createdAt
                                updatedAt
                            }
                        }
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                    }
                }
            }
            """
            
            variables = {'id': product_id}
            if cursor:
                variables['after'] = cursor
            
            result = self.execute_query(metafields_query, variables)
            
            if not result.get('data', {}).get('product', {}).get('metafields'):
                break
            
            metafields_data = result['data']['product']['metafields']
            all_metafields.extend(metafields_data['edges'])
            
            page_info = metafields_data.get('pageInfo', {})
            if not page_info.get('hasNextPage'):
                break
                
            cursor = page_info.get('endCursor')
        
        # Replace the limited metafields with complete set
        product['metafields'] = {'edges': all_metafields}
        
        return {"data": {"product": product}}

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
                result = self.get_products(first=batch_size, after=cursor)
                
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

    def delete_product(self, product_id: str) -> Dict[str, Any]:
        """
        Delete a product using GraphQL mutation.
        
        Args:
            product_id: Shopify product ID (with or without gid prefix)
            
        Returns:
            Deletion result
        """
        # Ensure proper GraphQL ID format
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        mutation = """
        mutation productDelete($input: ProductDeleteInput!) {
            productDelete(input: $input) {
                deletedProductId
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variables = {
            'input': {
                'id': product_id
            }
        }
        
        try:
            result = self.execute_query(mutation, variables)
            print(f"Deleted product {product_id}")
            return result
        except Exception as e:
            print(f"Error deleting product {product_id}: {str(e)}")
            raise

    
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

    def get_product_namespaces(self, product_id: str) -> List[str]:
        """
        Get all namespaces for a specific product.
        
        Args:
            product_id: Shopify product ID
            
        Returns:
            List of namespace strings for this product
        """
        try:
            product_data = self.get_complete_product_with_metafields(product_id)
            
            if not product_data.get('data', {}).get('product'):
                return []
            
            metafields = product_data['data']['product'].get('metafields', {}).get('edges', [])
            namespaces = set()
            
            for metafield_edge in metafields:
                namespace = metafield_edge['node'].get('namespace')
                if namespace:
                    namespaces.add(namespace)
            
            return sorted(list(namespaces))
            
        except Exception as e:
            print(f"Error getting namespaces for product {product_id}: {str(e)}")
            return []

    def analyze_metafield_namespaces_for_db(self, max_products: Optional[int] = None) -> Dict[str, Any]:
        """
        Analyze metafield namespaces optimized for database storage.
        
        Args:
            max_products: Maximum products to analyze
            
        Returns:
            Namespace analysis data suitable for database storage
        """
        namespace_stats = defaultdict(lambda: {
            'metafield_count': 0,
            'product_ids': set(),
            'unique_keys': set(),
            'sample_values': []
        })
        
        total_metafields = 0
        products_processed = 0
        
        print("Starting namespace analysis for database storage...")
        
        try:
            for batch in self.get_products_batch_for_db():
                for product in batch:
                    product_id = product.get('id', '').replace('gid://shopify/Product/', '')
                    metafields = product.get('metafields', {}).get('edges', [])
                    
                    for metafield_edge in metafields:
                        metafield = metafield_edge['node']
                        namespace = metafield.get('namespace', 'unknown')
                        key = metafield.get('key', 'unknown')
                        value = metafield.get('value', '')
                        
                        stats = namespace_stats[namespace]
                        stats['metafield_count'] += 1
                        stats['product_ids'].add(product_id)
                        stats['unique_keys'].add(key)
                        
                        # Store limited sample values
                        if len(stats['sample_values']) < 3:
                            sample_value = value[:200] if len(value) > 200 else value
                            stats['sample_values'].append({
                                'key': key,
                                'value': sample_value,
                                'product_id': product_id
                            })
                        
                        total_metafields += 1
                
                products_processed += len(batch)
                
                if max_products and products_processed >= max_products:
                    break
            
            # Convert to database-friendly format
            final_stats = {}
            for namespace, stats in namespace_stats.items():
                final_stats[namespace] = {
                    'namespace': namespace,
                    'metafield_count': stats['metafield_count'],
                    'product_count': len(stats['product_ids']),
                    'unique_keys_count': len(stats['unique_keys']),
                    'unique_keys': list(stats['unique_keys']),
                    'sample_values': stats['sample_values'],
                    'sample_product_ids': list(stats['product_ids'])[:5]
                }
            
            analysis_result = {
                'summary': {
                    'total_products_analyzed': products_processed,
                    'total_metafields': total_metafields,
                    'unique_namespaces': len(namespace_stats),
                    'analysis_timestamp': datetime.datetime.now().isoformat()
                },
                'namespaces': final_stats
            }
            
            print(f"Namespace analysis complete: {len(namespace_stats)} namespaces found")
            return analysis_result
            
        except Exception as e:
            print(f"Error in namespace analysis: {str(e)}")
            raise

    
    def add_metafield_to_product(self, product_id: str, namespace: str, key: str, 
                               value: str, field_type: str = "single_line_text_field") -> Dict[str, Any]:
        """
        Add a metafield to a product.
        
        Args:
            product_id: Shopify product ID
            namespace: Metafield namespace
            key: Metafield key
            value: Metafield value
            field_type: Metafield type
            
        Returns:
            Creation result
        """
        # Ensure proper GraphQL ID format
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        metafield = {
            "ownerId": product_id,
            "namespace": namespace,
            "key": key,
            "value": value,
            "type": field_type
        }
        
        try:
            result = self.bulk_update_metafields([metafield])
            print(f"Added metafield {namespace}.{key} to product {product_id}")
            return result
        except Exception as e:
            print(f"Error adding metafield to product {product_id}: {str(e)}")
            raise

    def get_products(self, first: int = 10, after: Optional[str] = None, 
                    query_filter: Optional[str] = None) -> Dict[str, Any]:
        """Fetch products using GraphQL with pagination."""
        query = """
        query getProducts($first: Int!, $after: String, $query: String) {
            products(first: $first, after: $after, query: $query) {
                edges {
                    node {
                        id
                        title
                        handle
                        descriptionHtml
                        productType
                        vendor
                        tags
                        status
                        createdAt
                        updatedAt
                        publishedAt
                        totalInventory
                        featuredImage {
                            id
                            url
                            altText
                        }
                        images(first: 5) {
                            edges {
                                node {
                                    id
                                    url
                                    altText
                                }
                            }
                        }
                        variants(first: 10) {
                            edges {
                                node {
                                    id
                                    title
                                    price
                                    sku
                                    inventoryQuantity
                                    availableForSale
                                }
                            }
                        }
                        metafields(first: 25) {
                            edges {
                                node {
                                    id
                                    namespace
                                    key
                                    value
                                    type
                                }
                            }
                        }
                    }
                }
                pageInfo {
                    hasNextPage
                    hasPreviousPage
                    startCursor
                    endCursor
                }
            }
        }
        """
        
        variables = {'first': first}
        if after:
            variables['after'] = after
        if query_filter:
            variables['query'] = query_filter
        
        return self.execute_query(query, variables)

    def get_product_by_id(self, product_id: str) -> Dict[str, Any]:
        """Get a single product by ID with basic details."""
        print(f"Fetching product id is : {product_id}")
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        query = """
        query getProduct($id: ID!) {
            product(id: $id) {
                id
                title
                handle
                descriptionHtml
                productType
                vendor
                tags
                status
                createdAt
                updatedAt
                publishedAt
                totalInventory
                seo {
                    title
                    description
                }
                featuredImage {
                    id
                    url
                    altText
                    width
                    height
                }
                images(first: 20) {
                    edges {
                        node {
                            id
                            url
                            altText
                            width
                            height
                        }
                    }
                }
                variants(first: 100) {
                    edges {
                        node {
                            id
                            title
                            price
                            compareAtPrice
                            sku
                            barcode
                            inventoryQuantity
                            availableForSale
                            taxable
                        }
                    }
                }
                metafields(first: 50) {
                    edges {
                        node {
                            id
                            namespace
                            key
                            value
                            type
                            description
                        }
                    }
                }
            }
        }
        """
        
        variables = {'id': product_id}
        return self.execute_query(query, variables)
    
    def create_product(self, product_input: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new product using GraphQL mutation."""
        mutation = """
        mutation productCreate($input: ProductInput!) {
            productCreate(input: $input) {
                product {
                    id
                    title
                    handle
                    status
                    createdAt
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variables = {'input': product_input}
        return self.execute_query(mutation, variables)

    def update_product(self, product_id: str, product_input: Dict[str, Any]) -> Dict[str, Any]:
        """Update a product using GraphQL mutation."""
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        mutation = """
        mutation productUpdate($input: ProductInput!) {
            productUpdate(input: $input) {
                product {
                    id
                    title
                    handle
                    status
                    updatedAt
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        product_input['id'] = product_id
        variables = {'input': product_input}
        return self.execute_query(mutation, variables)

    def bulk_update_metafields(self, metafields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update multiple metafields in a single request."""
        mutation = """
        mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
            metafieldsSet(metafields: $metafields) {
                metafields {
                    id
                    namespace
                    key
                    value
                    type
                    createdAt
                    updatedAt
                }
                userErrors {
                    field
                    message
                    code
                }
            }
        }
        """
        
        variables = {'metafields': metafields}
        return self.execute_query(mutation, variables)

    def delete_metafield_by_key(self, product_id: str, namespace: str, key: str) -> Dict[str, Any]:
        """Delete a specific metafield by namespace and key."""
        try:
            product_result = self.get_product_metafields(product_id, namespace, key)
            
            if not product_result.get('data', {}).get('product', {}).get('metafields', {}).get('edges'):
                print(f"Metafield {namespace}.{key} not found for product {product_id}")
                return {"success": False, "message": "Metafield not found"}
            
            metafield_id = product_result['data']['product']['metafields']['edges'][0]['node']['id']
            
            mutation = """
            mutation metafieldDelete($input: MetafieldDeleteInput!) {
                metafieldDelete(input: $input) {
                    deletedId
                    userErrors {
                        field
                        message
                    }
                }
            }
            """
            
            variables = {'input': {'id': metafield_id}}
            result = self.execute_query(mutation, variables)
            print(f"Deleted metafield {namespace}.{key} for product {product_id}")
            return result
            
        except Exception as e:
            print(f"Error deleting metafield {namespace}.{key} for product {product_id}: {str(e)}")
            raise

    def get_product_metafields(self, product_id: str, namespace: Optional[str] = None, 
                            key: Optional[str] = None) -> Dict[str, Any]:
        """Get all metafields for a product with pagination and optional filtering."""
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        all_metafields = []
        has_next_page = True
        cursor = None
        
        while has_next_page:
            # Build metafields arguments with pagination
            metafields_args = "first: 50"
            if cursor:
                metafields_args += f', after: "{cursor}"'
            if namespace and key:
                metafields_args += f', namespace: "{namespace}", key: "{key}"'
            elif namespace:
                metafields_args += f', namespace: "{namespace}"'
            
            query = f"""
            query getProductMetafields($id: ID!) {{
                product(id: $id) {{
                    id
                    title
                    metafields({metafields_args}) {{
                        edges {{
                            node {{
                                id
                                namespace
                                key
                                value
                                type
                                description
                                createdAt
                                updatedAt
                            }}
                        }}
                        pageInfo {{
                            hasNextPage
                            endCursor
                        }}
                    }}
                }}
            }}
            """
            
            variables = {'id': product_id}
            response = self.execute_query(query, variables)
            
            # Extract metafields from response
            if response and 'data' in response and response['data']['product']:
                metafields_data = response['data']['product']['metafields']
                all_metafields.extend(metafields_data['edges'])
                
                # Check pagination
                page_info = metafields_data['pageInfo']
                has_next_page = page_info['hasNextPage']
                cursor = page_info['endCursor']
            else:
                has_next_page = False
        
        # Return in the same format as original
        return {
            'data': {
                'product': {
                    'id': product_id,
                    'title': response['data']['product']['title'] if response and 'data' in response else None,
                    'metafields': {
                        'edges': all_metafields
                    }
                }
            }
        }
        



# Add this function to your ShopifyGraphQLConnector class

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

    def add_or_update_metafield(self, product_id: str, namespace: str, key: str, 
                            value: str, field_type: str = "single_line_text_field") -> Dict[str, Any]:
        """
        Add a new metafield or update existing one. 
        Creates namespace automatically if it doesn't exist.
        
        Args:
            product_id: Shopify product ID
            namespace: Metafield namespace (created automatically if new)
            key: Metafield key
            value: Metafield value
            field_type: Metafield type (only used for NEW metafields)
            
        Returns:
            Creation/update result
        """
        # Ensure proper GraphQL ID format
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        metafield = {
            "ownerId": product_id,
            "namespace": namespace,
            "key": key,
            "value": value,
            "type": field_type
        }
        
        try:
            result = self.bulk_update_metafields([metafield])
            
            # Check if it was successful
            if result.get('data', {}).get('metafieldsSet', {}).get('metafields'):
                action = "updated" if self._metafield_exists(product_id, namespace, key) else "created"
                print(f"Successfully {action} metafield {namespace}.{key} for product {product_id}")
            
            return result
        except Exception as e:
            print(f"Error adding/updating metafield {namespace}.{key} for product {product_id}: {str(e)}")
            raise

    def _metafield_exists(self, product_id: str, namespace: str, key: str) -> bool:
        """
        Check if a metafield exists (helper method).
        """
        try:
            result = self.get_product_metafields(product_id, namespace, key)
            metafields = result.get('data', {}).get('product', {}).get('metafields', {}).get('edges', [])
            return len(metafields) > 0
        except:
            return False

    def bulk_create_update_metafields(self, metafields_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Bulk create/update multiple metafields across different products/namespaces.
        
        Args:
            metafields_data: List of metafield dictionaries with keys:
                - product_id: Product ID 
                - namespace: Namespace name
                - key: Metafield key
                - value: Metafield value
                - type: Field type (optional, defaults to single_line_text_field)
        
        Returns:
            Bulk operation result
        """
        metafields = []
        
        for data in metafields_data:
            product_id = data['product_id']
            if not product_id.startswith('gid://shopify/Product/'):
                product_id = f"gid://shopify/Product/{product_id}"
            
            metafield = {
                "ownerId": product_id,
                "namespace": data['namespace'],
                "key": data['key'], 
                "value": data['value'],
                "type": data.get('type', 'single_line_text_field')
            }
            metafields.append(metafield)
        
        try:
            result = self.bulk_update_metafields(metafields)
            print(f"Bulk processed {len(metafields)} metafields")
            return result
        except Exception as e:
            print(f"Error in bulk metafield operation: {str(e)}")
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

    # Replace your existing update_metafield_value method with this simpler version:
    def update_metafield_value(self, product_id: str, namespace: str, key: str, 
                            new_value: str) -> Dict[str, Any]:
        """
        Update the value of an existing metafield (simplified version).
        
        Args:
            product_id: Shopify product ID
            namespace: Metafield namespace
            key: Metafield key
            new_value: New metafield value
            
        Returns:
            Update result
        """
        # No need to fetch existing metafield - metafieldsSet preserves type automatically
        return self.add_or_update_metafield(
            product_id=product_id,
            namespace=namespace, 
            key=key,
            value=new_value,
            # Type will be preserved automatically for existing metafields
            field_type="single_line_text_field"  # Only used if metafield doesn't exist
        )

    def get_unique_metafield_values(self, namespace: str, key: str, max_products: Optional[int] = 200) -> Dict[str, Any]:
        """
        Get all unique values for a specific namespace.key combination.
        
        Args:
            namespace: Target namespace
            key: Target key
            max_products: Maximum products to scan (None = all products)
            
        Returns:
            Dictionary with unique values analysis
        """
        try:
            unique_values = set()
            value_stats = defaultdict(lambda: {
                'count': 0,
                'product_ids': set(),
                'sample_full_values': []
            })
            
            products_scanned = 0
            metafields_found = 0
            
            print(f"Scanning for unique values in '{namespace}.{key}'...")
            
            for batch in self.get_products_batch_for_db(batch_size=50):
                for product in batch:
                    product_id = product.get('id', '').replace('gid://shopify/Product/', '')
                    metafields = product.get('metafields', {}).get('edges', [])
                    
                    for metafield_edge in metafields:
                        metafield = metafield_edge['node']
                        
                        # Only process the specific namespace.key combination
                        if (metafield.get('namespace') == namespace and 
                            metafield.get('key') == key):
                            
                            value = metafield.get('value', '')
                            field_type = metafield.get('type', 'unknown')
                            
                            # Handle different value types
                            processed_values = self._extract_individual_values(value, field_type)
                            
                            for processed_value in processed_values:
                                unique_values.add(processed_value)
                                
                                value_stats[processed_value]['count'] += 1
                                value_stats[processed_value]['product_ids'].add(product_id)
                                
                                # Store full original value as sample
                                if len(value_stats[processed_value]['sample_full_values']) < 2:
                                    value_stats[processed_value]['sample_full_values'].append({
                                        'original_value': value,
                                        'product_id': product_id,
                                        'type': field_type
                                    })
                            
                            metafields_found += 1
                
                products_scanned += len(batch)
                
                if max_products and products_scanned >= max_products:
                    break
            
            # Convert to final format
            values_list = []
            for value in sorted(unique_values):
                stats = value_stats[value]
                values_list.append({
                    'value': value,
                    'count': stats['count'],
                    'product_count': len(stats['product_ids']),
                    'sample_product_ids': list(stats['product_ids'])[:3],
                    'sample_full_values': stats['sample_full_values']
                })
            
            result = {
                'namespace': namespace,
                'key': key,
                'unique_values_count': len(unique_values),
                'total_metafields_found': metafields_found,
                'products_scanned': products_scanned,
                'values': values_list,
                'analysis_timestamp': datetime.datetime.now().isoformat()
            }
            
            print(f"Found {len(unique_values)} unique values for '{namespace}.{key}' from {metafields_found} metafields")
            return result
            
        except Exception as e:
            print(f"Error getting unique values for '{namespace}.{key}': {str(e)}")
            raise

    def _extract_individual_values(self, value: str, field_type: str) -> List[str]:
        """
        Extract individual values from metafield value based on type.
        Handles lists, JSON, and regular strings.
        
        Args:
            value: Raw metafield value
            field_type: Metafield type
            
        Returns:
            List of individual values
        """
        try:
            # Handle list types
            if field_type.startswith('list.'):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except:
                    pass
            
            # Handle JSON types
            if field_type == 'json':
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, dict):
                        # Extract values from JSON object
                        return [str(v).strip() for v in parsed.values() if str(v).strip()]
                    elif isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except:
                    pass
            
            # Handle comma-separated values (common pattern)
            if ',' in value and not value.startswith('['):
                return [item.strip() for item in value.split(',') if item.strip()]
            
            # Handle pipe-separated values  
            if '|' in value:
                return [item.strip() for item in value.split('|') if item.strip()]
            
            # Default: return as single value
            return [value.strip()] if value.strip() else []
            
        except Exception as e:
            print(f"Error extracting values from '{value}': {e}")
            return [value] if value else []