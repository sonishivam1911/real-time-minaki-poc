# services/shopify/metaobjects.py

from typing import Dict, Any, Optional, List
from .base_connector import BaseShopifyConnector


class MetaobjectService:
    """
    Handles global metaobject operations (not product-specific).
    Use this for:
    - Creating/managing metaobject definitions (schemas)
    - CRUD on metaobject entries
    - Getting all metaobjects across the store
    - Finding metaobjects by type or handle
    """
    
    def __init__(self, client: BaseShopifyConnector = None):
        self.client = client or BaseShopifyConnector()
    
    # ===== METAOBJECT DEFINITIONS (SCHEMAS) =====
    
    def get_all_metaobject_definitions(self) -> Dict[str, Any]:
        """
        Get all metaobject definitions (types/schemas) in the store.
        
        Returns:
            All metaobject definitions
        """
        query = """
        query getMetaobjectDefinitions {
            metaobjectDefinitions(first: 250) {
                edges {
                    node {
                        id
                        name
                        type
                        displayNameKey
                        fieldDefinitions {
                            key
                            name
                            type {
                                name
                            }
                            required
                        }
                    }
                }
            }
        }
        """
        
        return self.client.execute_query(query)
    
    def create_metaobject_definition(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new metaobject definition (schema).
        
        Args:
            definition: Definition data with keys:
                - type: Metaobject type identifier
                - name: Display name
                - fieldDefinitions: List of field definitions
                
        Example:
            {
                "type": "designer",
                "name": "Designer",
                "fieldDefinitions": [
                    {"key": "name", "name": "Name", "type": "single_line_text_field"},
                    {"key": "bio", "name": "Bio", "type": "multi_line_text_field"}
                ]
            }
            
        Returns:
            Created definition
        """
        mutation = """
        mutation createMetaobjectDefinition($definition: MetaobjectDefinitionCreateInput!) {
            metaobjectDefinitionCreate(definition: $definition) {
                metaobjectDefinition {
                    id
                    type
                    name
                    fieldDefinitions {
                        key
                        name
                        type {
                            name
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
        
        return self.client.execute_query(mutation, {'definition': definition})
    
    def get_all_metaobjects_by_definition(self) -> Dict[str, List[Dict]]:
        """
        Get ALL metaobjects in the store, grouped by type.
        This fetches all definitions first, then all entries for each type.
        
        Returns:
            Dictionary mapping metaobject types to their entries
        """
        # Get all definitions first
        definitions_result = self.get_all_metaobject_definitions()
        definitions = definitions_result.get('data', {}).get('metaobjectDefinitions', {}).get('edges', [])
        
        all_metaobjects = {}
        
        for def_edge in definitions:
            metaobject_type = def_edge['node']['type']
            
            # Get all entries for this type
            entries = []
            cursor = None
            
            while True:
                result = self.get_metaobjects_by_type(metaobject_type, first=250, after=cursor)
                metaobjects = result.get('data', {}).get('metaobjects', {})
                edges = metaobjects.get('edges', [])
                
                if not edges:
                    break
                
                entries.extend([edge['node'] for edge in edges])
                
                page_info = metaobjects.get('pageInfo', {})
                if not page_info.get('hasNextPage'):
                    break
                
                cursor = page_info.get('endCursor')
            
            all_metaobjects[metaobject_type] = entries
        
        return all_metaobjects
    
    def get_metaobjects_by_type(self, metaobject_type: str, first: int = 20,
                               after: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metaobjects filtered by type.
        
        Args:
            metaobject_type: Type of metaobject
            first: Number to fetch
            after: Cursor for pagination
            
        Returns:
            Metaobjects of specified type
        """
        query = """
        query getMetaobjects($type: String!, $first: Int, $after: String) {
            metaobjects(type: $type, first: $first, after: $after) {
                edges {
                    node {
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
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
        """
        
        variables = {'type': metaobject_type, 'first': first}
        if after:
            variables['after'] = after
        
        return self.client.execute_query(query, variables)
    
    def get_metaobject_by_id(self, metaobject_id: str) -> Dict[str, Any]:
        """
        Get single metaobject by ID.
        
        Args:
            metaobject_id: Metaobject ID (with gid prefix)
            
        Returns:
            Metaobject data
        """
        query = """
        query getMetaobject($id: ID!) {
            metaobject(id: $id) {
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
        """
        
        return self.client.execute_query(query, {'id': metaobject_id})
    
    def get_metaobject_by_handle(self, metaobject_type: str, handle: str) -> Dict[str, Any]:
        """
        Get metaobject by type and handle.
        
        Args:
            metaobject_type: Metaobject type
            handle: Metaobject handle
            
        Returns:
            Metaobject data
        """
        query = """
        query getMetaobjectByHandle($handle: MetaobjectHandleInput!) {
            metaobject(handle: $handle) {
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
        """
        
        handle_input = {'type': metaobject_type, 'handle': handle}
        return self.client.execute_query(query, {'handle': handle_input})
    
    def create_metaobject(self, metaobject_type: str, fields: List[Dict[str, str]],
                         handle: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new metaobject entry.
        
        Args:
            metaobject_type: Metaobject type (must match existing definition)
            fields: List of field dicts with 'key' and 'value'
            handle: Optional custom handle
            
        Example:
            create_metaobject(
                "designer",
                [
                    {"key": "name", "value": "John Doe"},
                    {"key": "bio", "value": "Famous designer"}
                ]
            )
            
        Returns:
            Created metaobject
        """
        mutation = """
        mutation createMetaobject($metaobject: MetaobjectCreateInput!) {
            metaobjectCreate(metaobject: $metaobject) {
                metaobject {
                    id
                    handle
                    type
                    fields {
                        key
                        value
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        metaobject_input = {'type': metaobject_type, 'fields': fields}
        if handle:
            metaobject_input['handle'] = handle
        
        return self.client.execute_query(mutation, {'metaobject': metaobject_input})
    
    def update_metaobject(self, metaobject_id: str, fields: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Update an existing metaobject.
        
        Args:
            metaobject_id: Metaobject ID
            fields: Updated fields
            
        Returns:
            Updated metaobject
        """
        mutation = """
        mutation updateMetaobject($id: ID!, $metaobject: MetaobjectUpdateInput!) {
            metaobjectUpdate(id: $id, metaobject: $metaobject) {
                metaobject {
                    id
                    handle
                    fields {
                        key
                        value
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        return self.client.execute_query(mutation, {
            'id': metaobject_id,
            'metaobject': {'fields': fields}
        })
    
    def delete_metaobject(self, metaobject_id: str) -> Dict[str, Any]:
        """
        Delete a metaobject.
        
        Args:
            metaobject_id: Metaobject ID
            
        Returns:
            Deletion result
        """
        mutation = """
        mutation deleteMetaobject($id: ID!) {
            metaobjectDelete(id: $id) {
                deletedId
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        return self.client.execute_query(mutation, {'id': metaobject_id})
    
    # ===== FIND PRODUCTS USING METAOBJECT =====
    
    def find_products_using_metaobject(self, metaobject_id: str, max_products: int = 250) -> List[str]:
        """
        Find all products that reference a specific metaobject.
        
        Args:
            metaobject_id: Metaobject ID
            max_products: Max products to scan
            
        Returns:
            List of product IDs that reference this metaobject
        """
        from .product import ShopifyProductService
        
        product_service = ShopifyProductService(self.client)
        product_ids = []
        processed = 0
        
        for batch in product_service.get_products_batch_for_db(batch_size=50):
            for product in batch:
                metafields = product.get('metafields', {}).get('edges', [])
                
                for mf_edge in metafields:
                    metafield = mf_edge['node']
                    value = metafield.get('value', '')
                    
                    # Check if this metafield references our metaobject
                    if metaobject_id in value:
                        product_ids.append(product['id'])
                        break
            
            processed += len(batch)
            if processed >= max_products:
                break
        
        return product_ids