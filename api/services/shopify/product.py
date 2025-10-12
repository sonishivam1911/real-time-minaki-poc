import time
import json
from typing import List, Dict, Any, Optional, Iterator
from .base_connector  import BaseShopifyConnector

class ShopifyProductService:
    """
        Shopify product service class which handles all operations peratining to products
    """
    
    def __init__(self, client: BaseShopifyConnector = None):
        """
        Initialize product service.
        
        Args:
            client: GraphQL client (creates new one if not provided)
        """
        self.client = client or BaseShopifyConnector()
    
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
            
            result = self.client.execute_query(metafields_query, variables)
            
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
            result = self.client.execute_query(mutation, variables)
            print(f"Deleted product {product_id}")
            return result
        except Exception as e:
            print(f"Error deleting product {product_id}: {str(e)}")
            raise

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

    def add_metafield_to_product(self, product_id: str, namespace: str, key: str, 
                            value: str, field_type: str = "single_line_text_field") -> Dict[str, Any]:
        """
        Add a metafield to a product with automatic type handling.
        """
        # Ensure proper GraphQL ID format
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        if field_type=="metaobject_reference":
            field_type = "list.metaobject_reference"
            value = value.strip().strip('"').strip("'")
            value = json.dumps([value])
        

        mutation = """
        mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
            metafieldsSet(metafields: $metafields) {
                metafields {
                    id
                    namespace
                    key
                    value
                    type
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        metafield = {
            "ownerId": product_id,
            "namespace": namespace,
            "key": key,
            "value": value,
            "type": field_type
        }
        
        variables = {"metafields": [metafield]}
        
        try:
            result = self.client.execute_query(mutation, variables)
            
            mutation_data = result.get('data', {}).get('metafieldsSet', {})
            user_errors = mutation_data.get('userErrors', [])
            
            if user_errors:
                error_messages = [f"{err.get('field')}: {err.get('message')}" for err in user_errors]
                raise Exception(f"Metafield creation failed: {', '.join(error_messages)}")
            
            print(f"✓ Added metafield {namespace}.{key} to product {product_id}")
            return result
            
        except Exception as e:
            error_msg = f"Error adding metafield {namespace}.{key} to product {product_id} and {field_type}: {str(e)}"
            print(f"✗ {error_msg}")
            raise Exception(error_msg)

    def bulk_update_metafields(self, metafields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Bulk create/update multiple metafields in a single GraphQL call.
        More efficient than calling add_metafield_to_product multiple times.
        
        Args:
            metafields: List of metafield objects
            
        Returns:
            GraphQL mutation result
            
        Example:
            service.bulk_update_metafields([
                {
                    "ownerId": "gid://shopify/Product/123",
                    "namespace": "custom",
                    "key": "finish",
                    "value": "gid://shopify/Metaobject/456",
                    "type": "metaobject_reference"
                },
                {
                    "ownerId": "gid://shopify/Product/123",
                    "namespace": "custom",
                    "key": "jewelry_closure",
                    "value": "gid://shopify/Metaobject/789",
                    "type": "metaobject_reference"
                }
            ])
        """
        mutation = """
        mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
            metafieldsSet(metafields: $metafields) {
                metafields {
                    id
                    namespace
                    key
                    value
                    type
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variables = {"metafields": metafields}
        
        try:
            result = self.client.execute_query(mutation, variables)
            
            # Check for errors
            mutation_data = result.get('data', {}).get('metafieldsSet', {})
            user_errors = mutation_data.get('userErrors', [])
            
            if user_errors:
                error_messages = [f"{err.get('field')}: {err.get('message')}" for err in user_errors]
                raise Exception(f"Bulk metafield update failed: {', '.join(error_messages)}")
            
            created_count = len(mutation_data.get('metafields', []))
            print(f"✓ Bulk updated {created_count} metafields")
            
            return result
            
        except Exception as e:
            print(f"✗ Error in bulk_update_metafields: {str(e)}")
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
        
        return self.client.execute_query(query, variables)

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
        return self.client.execute_query(query, variables)
    
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
        return self.client.execute_query(mutation, variables)

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
        return self.client.execute_query(mutation, variables)

    def get_product_metafields(self, product_id: str, namespace: Optional[str] = None, 
                             key: Optional[str] = None) -> Dict[str, Any]:
        """Get metafields for a product with optional filtering."""
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        metafields_args = "first: 50"
        if namespace and key:
            metafields_args = f'first: 50, namespace: "{namespace}", key: "{key}"'
        elif namespace:
            metafields_args = f'first: 50, namespace: "{namespace}"'
        
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
                }}
            }}
        }}
        """
        
        variables = {'id': product_id}
        return self.client.execute_query(query, variables)

    def get_product_metaobjects(self, product_id: str) -> Dict[str, Any]:
        """
        Get all metaobjects referenced by a product via its metafields.
        
        Args:
            product_id: Product ID (with or without gid prefix)
            
        Returns:
            Product data with metaobjects expanded
        """
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        query = """
        query getProductMetaobjects($id: ID!) {
            product(id: $id) {
                id
                title
                metafields(first: 50) {
                    edges {
                        node {
                            id
                            namespace
                            key
                            value
                            type
                            reference {
                                ... on Metaobject {
                                    id
                                    handle
                                    type
                                    updatedAt
                                    fields {
                                        key
                                        value
                                        type
                                    }
                                }
                            }
                            references(first: 10) {
                                edges {
                                    node {
                                        ... on Metaobject {
                                            id
                                            handle
                                            type
                                            updatedAt
                                            fields {
                                                key
                                                value
                                                type
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        return self.client.execute_query(query, {'id': product_id})

    def link_metaobject_to_product(self, product_id: str, metaobject_id: str, 
                                namespace: str, key: str) -> Dict[str, Any]:
        """
        Link a metaobject to a product by creating a metafield reference.
        
        Args:
            product_id: Product ID
            metaobject_id: Metaobject ID (with gid prefix)
            namespace: Metafield namespace
            key: Metafield key
            
        Returns:
            Created metafield linking to metaobject
        """
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        mutation = """
        mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
            metafieldsSet(metafields: $metafields) {
                metafields {
                    id
                    namespace
                    key
                    value
                    reference {
                        ... on Metaobject {
                            id
                            handle
                            type
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
        
        metafield = {
            "ownerId": product_id,
            "namespace": namespace,
            "key": key,
            "value": metaobject_id,
            "type": "metaobject_reference"
        }
        
        try:
            result = self.client.execute_query(mutation, {'metafields': [metafield]})
            print(f"Linked metaobject {metaobject_id} to product {product_id}")
            return result
        except Exception as e:
            print(f"Error linking metaobject to product: {str(e)}")
            raise

    def link_metaobject_list_to_product(self, product_id: str, metaobject_ids: List[str],
                                    namespace: str, key: str) -> Dict[str, Any]:
        """
        Link multiple metaobjects to a product (list reference).
        
        Args:
            product_id: Product ID
            metaobject_ids: List of metaobject IDs
            namespace: Metafield namespace
            key: Metafield key
            
        Returns:
            Created metafield with list reference
        """
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        mutation = """
        mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
            metafieldsSet(metafields: $metafields) {
                metafields {
                    id
                    namespace
                    key
                    value
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        # Format as JSON array string
        import json
        value = json.dumps(metaobject_ids)
        
        metafield = {
            "ownerId": product_id,
            "namespace": namespace,
            "key": key,
            "value": value,
            "type": "list.metaobject_reference"
        }
        
        return self.client.execute_query(mutation, {'metafields': [metafield]})

    def unlink_metaobject_from_product(self, product_id: str, namespace: str, key: str) -> Dict[str, Any]:
        """
        Remove metaobject reference from product by deleting the metafield.
        
        Args:
            product_id: Product ID
            namespace: Metafield namespace
            key: Metafield key
            
        Returns:
            Deletion result
        """
        # First get the metafield ID
        metafields = self.get_product_metafields(product_id, namespace, key)
        edges = metafields.get('data', {}).get('product', {}).get('metafields', {}).get('edges', [])
        
        if not edges:
            return {"success": False, "message": "Metafield not found"}
        
        metafield_id = edges[0]['node']['id']
        
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
        
        return self.client.execute_query(mutation, {'input': {'id': metafield_id}})

    def bulk_link_metaobjects_to_products(self, links: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Bulk link metaobjects to multiple products.
        
        Args:
            links: List of dicts with keys:
                - product_id: Product ID
                - metaobject_id: Metaobject ID
                - namespace: Metafield namespace
                - key: Metafield key
                
        Returns:
            Bulk operation result
        """
        mutation = """
        mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
            metafieldsSet(metafields: $metafields) {
                metafields {
                    id
                    namespace
                    key
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        metafields = []
        for link in links:
            product_id = link['product_id']
            if not product_id.startswith('gid://shopify/Product/'):
                product_id = f"gid://shopify/Product/{product_id}"
            
            metafield = {
                "ownerId": product_id,
                "namespace": link['namespace'],
                "key": link['key'],
                "value": link['metaobject_id'],
                "type": "metaobject_reference"
            }
            metafields.append(metafield)
        
        return self.client.execute_query(mutation, {'metafields': metafields})

    def get_all_products_with_metaobjects(self, max_products: Optional[int] = None) -> Iterator[List[Dict]]:
        """
        Generator that yields products with their metaobjects expanded.
        
        Args:
            max_products: Max products to fetch
            
        Yields:
            Batches of products with metaobjects
        """
        processed = 0
        
        for batch in self.get_products_batch_for_db(batch_size=50):
            # For each product, fetch its metaobjects
            enriched_batch = []
            for product in batch:
                product_id = product['id']
                metaobjects_data = self.get_product_metaobjects(product_id)
                product['metaobjects'] = metaobjects_data.get('data', {}).get('product', {}).get('metafields')
                enriched_batch.append(product)
            
            yield enriched_batch
            
            processed += len(batch)
            if max_products and processed >= max_products:
                break