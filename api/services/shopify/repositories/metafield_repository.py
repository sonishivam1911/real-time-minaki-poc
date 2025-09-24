from typing import List, Dict, Any, Optional
from ..base_connector import BaseShopifyConnector

class MetafieldRepository(BaseShopifyConnector):
    """Repository for metafield CRUD operations"""
    
    def get_metafields_by_owner(self, owner_id: str, namespace: Optional[str] = None, 
                               key: Optional[str] = None, limit: int = 250) -> Dict[str, Any]:
        """Get metafields for any owner (product, variant, etc.) with optional filtering."""
        
        # Ensure proper GraphQL ID format
        if not owner_id.startswith('gid://shopify/'):
            owner_id = f"gid://shopify/Product/{owner_id}"
        
        # Build metafields arguments - only namespace filtering is supported in GraphQL
        metafields_args = f"first: {limit}"
        if namespace:
            metafields_args += f', namespace: "{namespace}"'
        
        query = f"""
        query getMetafields($id: ID!) {{
            node(id: $id) {{
                ... on Product {{
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
        }}
        """
        
        result = self.execute_query(query, {'id': owner_id})
        
        # Client-side filtering by key if specified
        if key and result.get('data', {}).get('node', {}).get('metafields'):
            metafields_data = result['data']['node']['metafields']
            filtered_edges = [
                edge for edge in metafields_data.get('edges', [])
                if edge['node'].get('key') == key
            ]
            result['data']['node']['metafields']['edges'] = filtered_edges
        
        return result
    
    def get_all_metafields_paginated(self, owner_id: str, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get ALL metafields for an owner using pagination."""
        
        all_metafields = []
        cursor = None
        
        while True:
            metafields_args = "first: 250"
            if namespace:
                metafields_args += f', namespace: "{namespace}"'
            if cursor:
                metafields_args += f', after: "{cursor}"'
            
            query = f"""
            query getMetafields($id: ID!) {{
                node(id: $id) {{
                    ... on Product {{
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
            }}
            """
            
            result = self.execute_query(query, {'id': owner_id})
            
            if not result.get('data', {}).get('node', {}).get('metafields'):
                break
            
            metafields_data = result['data']['node']['metafields']
            all_metafields.extend([edge['node'] for edge in metafields_data.get('edges', [])])
            
            page_info = metafields_data.get('pageInfo', {})
            if not page_info.get('hasNextPage'):
                break
                
            cursor = page_info.get('endCursor')
        
        return all_metafields
    
    def create_metafields(self, metafields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create multiple metafields in a single request."""
        
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
        
        return self.execute_mutation(mutation, {'metafields': metafields})
    
    def update_metafields(self, metafields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update multiple metafields (uses same mutation as create)."""
        return self.create_metafields(metafields)
    
    def delete_metafield(self, metafield_id: str) -> Dict[str, Any]:
        """Delete a specific metafield by ID."""
        
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
        
        return self.execute_mutation(mutation, {'input': {'id': metafield_id}})
    
    def find_metafield_by_namespace_key(self, owner_id: str, namespace: str, key: str) -> Optional[Dict[str, Any]]:
        """Find a specific metafield by namespace and key with pagination support."""
        cursor = None
        
        while True:
            metafields_args = f'first: 250, namespace: "{namespace}"'
            if cursor:
                metafields_args += f', after: "{cursor}"'
            
            query = f"""
            query findMetafield($id: ID!) {{
                node(id: $id) {{
                    ... on Product {{
                        metafields({metafields_args}) {{
                            edges {{
                                node {{
                                    id
                                    namespace
                                    key
                                    value
                                    type
                                    description
                                }}
                            }}
                            pageInfo {{
                                hasNextPage
                                endCursor
                            }}
                        }}
                    }}
                }}
            }}
            """
            
            result = self.execute_query(query, {'id': owner_id})
            
            if not result.get('data', {}).get('node', {}).get('metafields'):
                return None
            
            metafields_data = result['data']['node']['metafields']
            
            # Look for the specific key in this batch
            for edge in metafields_data.get('edges', []):
                if edge['node'].get('key') == key:
                    return edge['node']
            
            # Check if there are more pages
            page_info = metafields_data.get('pageInfo', {})
            if not page_info.get('hasNextPage'):
                break
            
            cursor = page_info.get('endCursor')
        
        return None
    
    def get_metafields_by_namespace(self, owner_id: str, namespace: str) -> List[Dict[str, Any]]:
        """Get all metafields for a specific namespace."""
        return self.get_all_metafields_paginated(owner_id, namespace)
    
    def bulk_create_metafields(self, metafields_data: List[Dict[str, str]]) -> Dict[str, Any]:
        """Create metafields from simplified data format."""
        metafields = []
        
        for data in metafields_data:
            owner_id = data['owner_id']
            if not owner_id.startswith('gid://shopify/'):
                owner_id = f"gid://shopify/Product/{owner_id}"
            
            metafield = {
                "ownerId": owner_id,
                "namespace": data['namespace'],
                "key": data['key'],
                "value": data['value'],
                "type": data.get('type', 'single_line_text_field')
            }
            metafields.append(metafield)
        
        return self.create_metafields(metafields)