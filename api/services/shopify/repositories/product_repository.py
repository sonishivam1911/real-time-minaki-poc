import time
from typing import List, Dict, Any, Optional, Iterator
from ..base_connector import BaseShopifyConnector

class ProductRepository(BaseShopifyConnector):
    """Repository for product CRUD operations"""
    
    def get_product_by_id(self, product_id: str, include_variants: bool = True, 
                         include_images: bool = True) -> Dict[str, Any]:
        """Get a single product by ID with configurable includes."""
        
        # Ensure proper GraphQL ID format
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        # Build dynamic fields based on requirements
        variant_fields = """
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
                    weight
                    weightUnit
                }
            }
        }
        """ if include_variants else ""
        
        image_fields = """
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
        featuredImage {
            id
            url
            altText
            width
            height
        }
        """ if include_images else ""
        
        query = f"""
        query getProduct($id: ID!) {{
            product(id: $id) {{
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
                seo {{
                    title
                    description
                }}
                {image_fields}
                {variant_fields}
            }}
        }}
        """
        
        return self.execute_query(query, {'id': product_id})
    
    def get_products(self, first: int = 50, after: Optional[str] = None, 
                    query_filter: Optional[str] = None) -> Dict[str, Any]:
        """Get products with pagination and filtering."""
        
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
    
    def create_product(self, product_input: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new product."""
        
        mutation = """
        mutation productCreate($input: ProductInput!) {
            productCreate(input: $input) {
                product {
                    id
                    title
                    handle
                    status
                    createdAt
                    variants(first: 10) {
                        edges {
                            node {
                                id
                                title
                                price
                                sku
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
        
        return self.execute_mutation(mutation, {'input': product_input})
    
    def update_product(self, product_id: str, product_input: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing product."""
        
        # Ensure proper GraphQL ID format
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        product_input['id'] = product_id
        
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
        
        return self.execute_mutation(mutation, {'input': product_input})
    
    def delete_product(self, product_id: str) -> Dict[str, Any]:
        """Delete a product."""
        
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
        
        return self.execute_mutation(mutation, {'input': {'id': product_id}})
    
    def get_products_batch(self, batch_size: int = 50) -> Iterator[List[Dict]]:
        """Generator that yields batches of products for processing."""
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
    
    def get_products_by_ids(self, product_ids: List[str]) -> Dict[str, Any]:
        """Get multiple products by their IDs in a single query."""
        
        # Ensure proper GraphQL ID format for all IDs
        formatted_ids = []
        for product_id in product_ids:
            if not product_id.startswith('gid://shopify/Product/'):
                formatted_ids.append(f"gid://shopify/Product/{product_id}")
            else:
                formatted_ids.append(product_id)
        
        query = """
        query getProductsByIds($ids: [ID!]!) {
            nodes(ids: $ids) {
                ... on Product {
                    id
                    title
                    handle
                    status
                    totalInventory
                    featuredImage {
                        url
                        altText
                    }
                }
            }
        }
        """
        
        return self.execute_query(query, {'ids': formatted_ids})