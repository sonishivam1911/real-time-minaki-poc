from typing import List, Dict, Any, Optional, Callable
from ..repositories.metafield_repository import MetafieldRepository
from ..processors.metafield_filter_processor import MetafieldFilterProcessor

class MetafieldService:
    """Service for complex metafield operations including filtering and preprocessing"""
    
    def __init__(self):
        self.metafield_repo = MetafieldRepository()
        self.filter_processor = MetafieldFilterProcessor()
    
    def filter_metafields_by_namespace(self, owner_id: str, namespace: str, 
                                     filters: Optional[Dict[str, Any]] = None,
                                     preprocessing: Optional[Callable] = None) -> Dict[str, Any]:
        """Filter metafields by namespace with optional key-value filtering and preprocessing."""
        
        try:
            # Get all metafields for the namespace
            metafields = self.metafield_repo.get_metafields_by_namespace(owner_id, namespace)
            
            if not metafields:
                return {
                    'success': True,
                    'message': f'No metafields found in namespace "{namespace}"',
                    'metafields': [],
                    'count': 0
                }
            
            filtered_metafields = metafields
            
            # Apply filters if provided
            if filters:
                filtered_metafields = self.filter_processor.apply_filters(filtered_metafields, filters)
            
            # Apply preprocessing if provided
            if preprocessing:
                filtered_metafields = [preprocessing(mf) for mf in filtered_metafields]
            
            return {
                'success': True,
                'message': f'Found {len(filtered_metafields)} metafields in namespace "{namespace}"',
                'namespace': namespace,
                'metafields': filtered_metafields,
                'count': len(filtered_metafields),
                'total_before_filtering': len(metafields)
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error filtering metafields: {str(e)}',
                'error': str(e)
            }
    
    def get_metafields_by_key_value_pairs(self, owner_id: str, key_value_filters: Dict[str, str],
                                        namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get metafields that match specific key-value pairs."""
        
        try:
            if namespace:
                # Filter within specific namespace
                metafields = self.metafield_repo.get_metafields_by_namespace(owner_id, namespace)
            else:
                # Get all metafields and filter across all namespaces
                all_metafields_result = self.metafield_repo.get_metafields_by_owner(owner_id)
                
                if not all_metafields_result.get('data', {}).get('node', {}).get('metafields'):
                    return {
                        'success': True,
                        'message': 'No metafields found',
                        'metafields': [],
                        'count': 0
                    }
                
                metafields_edges = all_metafields_result['data']['node']['metafields']['edges']
                metafields = [edge['node'] for edge in metafields_edges]
            
            # Filter by key-value pairs
            matching_metafields = []
            
            for metafield in metafields:
                matches = True
                for key, expected_value in key_value_filters.items():
                    if metafield.get('key') == key:
                        if not self._value_matches(metafield.get('value'), expected_value):
                            matches = False
                            break
                    else:
                        matches = False
                        break
                
                if matches:
                    matching_metafields.append(metafield)
            
            return {
                'success': True,
                'message': f'Found {len(matching_metafields)} matching metafields',
                'metafields': matching_metafields,
                'count': len(matching_metafields),
                'filters_applied': key_value_filters
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error searching metafields: {str(e)}',
                'error': str(e)
            }
    
    def preprocess_metafields_data(self, owner_id: str, namespace: str, 
                                 preprocessing_rules: Dict[str, Any]) -> Dict[str, Any]:
        """Apply preprocessing rules to metafields data."""
        
        try:
            metafields = self.metafield_repo.get_metafields_by_namespace(owner_id, namespace)
            
            if not metafields:
                return {
                    'success': True,
                    'message': f'No metafields to process in namespace "{namespace}"',
                    'processed_metafields': []
                }
            
            processed_metafields = []
            
            for metafield in metafields:
                processed_mf = self.filter_processor.apply_preprocessing_rules(metafield, preprocessing_rules)
                processed_metafields.append(processed_mf)
            
            return {
                'success': True,
                'message': f'Processed {len(processed_metafields)} metafields',
                'namespace': namespace,
                'processed_metafields': processed_metafields,
                'count': len(processed_metafields)
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error preprocessing metafields: {str(e)}',
                'error': str(e)
            }
    
    def create_or_update_metafield(self, owner_id: str, namespace: str, key: str, 
                                 value: str, field_type: str = "single_line_text_field") -> Dict[str, Any]:
        """Create or update a single metafield."""
        
        try:
            # Ensure proper owner ID format
            if not owner_id.startswith('gid://shopify/'):
                owner_id = f"gid://shopify/Product/{owner_id}"
            
            metafield_data = {
                "ownerId": owner_id,
                "namespace": namespace,
                "key": key,
                "value": value,
                "type": field_type
            }
            
            result = self.metafield_repo.create_metafields([metafield_data])
            
            if 'errors' in result or result.get('data', {}).get('metafieldsSet', {}).get('userErrors'):
                errors = result.get('errors', []) + result.get('data', {}).get('metafieldsSet', {}).get('userErrors', [])
                return {
                    'success': False,
                    'message': 'Failed to create/update metafield',
                    'error': errors
                }
            
            created_metafield = result['data']['metafieldsSet']['metafields'][0]
            
            return {
                'success': True,
                'message': f'Metafield {namespace}.{key} created/updated successfully',
                'metafield': created_metafield
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error creating/updating metafield: {str(e)}',
                'error': str(e)
            }
    
    def bulk_create_namespace_metafields(self, owner_id: str, namespace: str, 
                                       fields_data: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
        """Create multiple metafields in a namespace at once."""
        
        try:
            if not owner_id.startswith('gid://shopify/'):
                owner_id = f"gid://shopify/Product/{owner_id}"
            
            metafields = []
            
            for key, field_info in fields_data.items():
                metafield = {
                    "ownerId": owner_id,
                    "namespace": namespace,
                    "key": key,
                    "value": field_info["value"],
                    "type": field_info.get("type", "single_line_text_field")
                }
                metafields.append(metafield)
            
            result = self.metafield_repo.create_metafields(metafields)
            
            if 'errors' in result or result.get('data', {}).get('metafieldsSet', {}).get('userErrors'):
                errors = result.get('errors', []) + result.get('data', {}).get('metafieldsSet', {}).get('userErrors', [])
                return {
                    'success': False,
                    'message': f'Failed to create metafields in namespace "{namespace}"',
                    'error': errors
                }
            
            created_metafields = result['data']['metafieldsSet']['metafields']
            
            return {
                'success': True,
                'message': f'Created {len(created_metafields)} metafields in namespace "{namespace}"',
                'namespace': namespace,
                'metafields': created_metafields,
                'count': len(created_metafields)
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error creating namespace metafields: {str(e)}',
                'error': str(e)
            }
    
    def delete_metafield_by_key(self, owner_id: str, namespace: str, key: str) -> Dict[str, Any]:
        """Delete a metafield by namespace and key."""
        
        try:
            # Find the metafield first
            metafield = self.metafield_repo.find_metafield_by_namespace_key(owner_id, namespace, key)
            
            if not metafield:
                return {
                    'success': False,
                    'message': f'Metafield {namespace}.{key} not found'
                }
            
            # Delete the metafield
            result = self.metafield_repo.delete_metafield(metafield['id'])
            
            if 'errors' in result or result.get('data', {}).get('metafieldDelete', {}).get('userErrors'):
                errors = result.get('errors', []) + result.get('data', {}).get('metafieldDelete', {}).get('userErrors', [])
                return {
                    'success': False,
                    'message': f'Failed to delete metafield {namespace}.{key}',
                    'error': errors
                }
            
            return {
                'success': True,
                'message': f'Metafield {namespace}.{key} deleted successfully',
                'deleted_id': result['data']['metafieldDelete']['deletedId']
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error deleting metafield: {str(e)}',
                'error': str(e)
            }
    
    def _value_matches(self, actual_value: str, expected_value: str) -> bool:
        """Check if metafield value matches expected value with flexible matching."""
        
        if actual_value == expected_value:
            return True
        
        # Try case-insensitive matching
        if actual_value.lower() == expected_value.lower():
            return True
        
        # Try partial matching for strings
        if expected_value in actual_value or actual_value in expected_value:
            return True
        
        return False
    
    def get_metafield_analytics(self, owner_id: str) -> Dict[str, Any]:
        """Get analytics about metafields for an owner."""
        
        try:
            # Get all metafields
            all_metafields_result = self.metafield_repo.get_metafields_by_owner(owner_id)
            
            if not all_metafields_result.get('data', {}).get('node', {}).get('metafields'):
                return {
                    'success': True,
                    'message': 'No metafields found',
                    'analytics': {
                        'total_metafields': 0,
                        'namespaces': {},
                        'field_types': {}
                    }
                }
            
            metafields_edges = all_metafields_result['data']['node']['metafields']['edges']
            metafields = [edge['node'] for edge in metafields_edges]
            
            analytics = self.filter_processor.analyze_metafields(metafields)
            
            return {
                'success': True,
                'message': f'Analytics for {len(metafields)} metafields',
                'analytics': analytics
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error generating analytics: {str(e)}',
                'error': str(e)
            }