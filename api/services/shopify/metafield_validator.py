"""
Metafield Validator Service
Validates and safely creates metafields with proper error handling
"""

import json
from typing import Dict, Any, List, Optional, Tuple
from .base_connector import BaseShopifyConnector


class MetafieldValidator:
    """
    Validates metafields before creation and handles choice restrictions gracefully
    """
    
    def __init__(self, client: BaseShopifyConnector = None):
        self.client = client or BaseShopifyConnector()
        self._metafield_definitions_cache = {}
    
    def get_metafield_definition(self, namespace: str, key: str, 
                                owner_type: str = "PRODUCT") -> Optional[Dict[str, Any]]:
        """
        Get metafield definition with caching
        """
        cache_key = f"{namespace}.{key}"
        if cache_key in self._metafield_definitions_cache:
            return self._metafield_definitions_cache[cache_key]
        
        query = """
        query getMetafieldDefinition($namespace: String!, $key: String!, $ownerType: MetafieldOwnerType!) {
            metafieldDefinitions(first: 1, namespace: $namespace, key: $key, ownerType: $ownerType) {
                edges {
                    node {
                        id
                        namespace
                        key
                        name
                        description
                        type {
                            name
                            category
                        }
                        validations {
                            name
                            value
                        }
                    }
                }
            }
        }
        """
        
        try:
            result = self.client.execute_query(query, {
                'namespace': namespace,
                'key': key,
                'ownerType': owner_type
            })
            
            definitions = result.get('data', {}).get('metafieldDefinitions', {}).get('edges', [])
            
            if definitions:
                definition = definitions[0]['node']
                self._metafield_definitions_cache[cache_key] = definition
                return definition
            
            return None
            
        except Exception as e:
            print(f"Error getting metafield definition for {namespace}.{key}: {str(e)}")
            return None
    
    def get_allowed_values(self, namespace: str, key: str) -> Optional[List[str]]:
        """
        Get allowed values for choice-based metafield
        """
        definition = self.get_metafield_definition(namespace, key)
        if not definition:
            return None
        
        # Check validations for choices
        validations = definition.get('validations', [])
        for validation in validations:
            if validation.get('name') == 'choices':
                value = validation.get('value')
                if isinstance(value, str):
                    try:
                        choices = json.loads(value)
                        return [choice.strip() for choice in choices]
                    except json.JSONDecodeError:
                        return None
        
        return None
    
    def validate_value_for_metafield(self, value: str, namespace: str, key: str) -> Tuple[bool, Optional[str]]:
        """
        Validate if value is allowed for given metafield
        
        Returns:
            (is_valid, error_message)
        """
        definition = self.get_metafield_definition(namespace, key)
        
        if not definition:
            return False, f"Metafield {namespace}.{key} does not exist in Shopify"
        
        # Get allowed values if this is a choice field
        allowed_values = self.get_allowed_values(namespace, key)
        
        if allowed_values:
            # This is a choice-based field
            if value not in allowed_values:
                return False, f"Value '{value}' not in allowed choices: {allowed_values[:5]}..."
        
        return True, None
    
    def find_closest_match(self, value: str, namespace: str, key: str) -> Optional[str]:
        """
        Find the closest matching value from allowed choices
        Uses simple substring matching
        """
        allowed_values = self.get_allowed_values(namespace, key)
        
        if not allowed_values:
            return None
        
        value_lower = value.lower().strip()
        
        # Exact match (case-insensitive)
        for allowed in allowed_values:
            if allowed.lower() == value_lower:
                return allowed
        
        # Substring match
        for allowed in allowed_values:
            if value_lower in allowed.lower() or allowed.lower() in value_lower:
                return allowed
        
        # No match found
        return None
    
    def safe_create_metafield(self, product_id: str, namespace: str, key: str, 
                             value: str, field_type: str = "single_line_text_field",
                             fallback_value: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Safely create metafield with validation and fallback
        
        Returns:
            (success, error_message)
        """
        # Ensure proper GraphQL ID format
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        # Clean the value
        value = str(value).strip()
        
        # Validate the value
        is_valid, error_msg = self.validate_value_for_metafield(value, namespace, key)
        
        if not is_valid:
            # Try to find a close match
            if error_msg and "not in allowed choices" in error_msg:
                closest_match = self.find_closest_match(value, namespace, key)
                if closest_match:
                    print(f"⚠️  Value '{value}' not allowed. Using closest match: '{closest_match}'")
                    value = closest_match
                    is_valid = True
                elif fallback_value:
                    print(f"⚠️  Value '{value}' not allowed and no match found. Using fallback: '{fallback_value}'")
                    value = fallback_value
                    is_valid = True
                else:
                    return False, f"Value '{value}' not allowed for {namespace}.{key}: {error_msg}"
        
        # Attempt to create metafield
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
        
        try:
            result = self.client.execute_query(mutation, {"metafields": [metafield]})
            
            user_errors = result.get('data', {}).get('metafieldsSet', {}).get('userErrors', [])
            
            if user_errors:
                error_messages = [f"{err.get('field')}: {err.get('message')}" for err in user_errors]
                return False, f"Metafield creation failed: {', '.join(error_messages)}"
            
            return True, None
            
        except Exception as e:
            return False, f"Exception creating metafield: {str(e)}"
    
    def get_all_metafield_definitions_for_namespace(self, namespace: str) -> Dict[str, Any]:
        """
        Get all metafield definitions for a namespace
        """
        query = """
        query getMetafieldDefinitionsByNamespace($namespace: String!) {
            metafieldDefinitions(first: 250, namespace: $namespace) {
                edges {
                    node {
                        id
                        namespace
                        key
                        name
                        type {
                            name
                        }
                        validations {
                            name
                            value
                        }
                    }
                }
            }
        }
        """
        
        try:
            result = self.client.execute_query(query, {'namespace': namespace})
            definitions = result.get('data', {}).get('metafieldDefinitions', {}).get('edges', [])
            
            metafield_map = {}
            for edge in definitions:
                node = edge['node']
                key = node.get('key')
                metafield_map[key] = node
            
            return metafield_map
            
        except Exception as e:
            print(f"Error getting metafield definitions for namespace {namespace}: {str(e)}")
            return {}
