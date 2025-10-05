from typing import List, Dict, Any

from .base_connector  import BaseShopifyConnector

class ShopifyMetafieldService:
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