from typing import List, Dict, Any, Callable
from collections import defaultdict
import re
import json

class MetafieldFilterProcessor:
    """Processor for filtering and preprocessing metafields data"""
    
    def apply_filters(self, metafields: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply various filters to metafields list."""
        
        filtered_metafields = metafields
        
        # Filter by key
        if filters.get('key'):
            key_filter = filters['key']
            if isinstance(key_filter, str):
                filtered_metafields = [mf for mf in filtered_metafields if mf.get('key') == key_filter]
            elif isinstance(key_filter, list):
                filtered_metafields = [mf for mf in filtered_metafields if mf.get('key') in key_filter]
        
        # Filter by value (exact match)
        if filters.get('value'):
            value_filter = filters['value']
            filtered_metafields = [mf for mf in filtered_metafields if mf.get('value') == value_filter]
        
        # Filter by value pattern (regex)
        if filters.get('value_pattern'):
            pattern = re.compile(filters['value_pattern'])
            filtered_metafields = [mf for mf in filtered_metafields if pattern.search(mf.get('value', ''))]
        
        # Filter by value contains
        if filters.get('value_contains'):
            contains_filter = filters['value_contains']
            filtered_metafields = [mf for mf in filtered_metafields if contains_filter.lower() in mf.get('value', '').lower()]
        
        # Filter by field type
        if filters.get('type'):
            type_filter = filters['type']
            if isinstance(type_filter, str):
                filtered_metafields = [mf for mf in filtered_metafields if mf.get('type') == type_filter]
            elif isinstance(type_filter, list):
                filtered_metafields = [mf for mf in filtered_metafields if mf.get('type') in type_filter]
        
        # Filter by date range
        if filters.get('created_after') or filters.get('created_before'):
            filtered_metafields = self._filter_by_date_range(
                filtered_metafields, 
                filters.get('created_after'), 
                filters.get('created_before')
            )
        
        # Custom filter function
        if filters.get('custom_filter') and callable(filters['custom_filter']):
            filtered_metafields = [mf for mf in filtered_metafields if filters['custom_filter'](mf)]
        
        return filtered_metafields
    
    def apply_preprocessing_rules(self, metafield: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
        """Apply preprocessing rules to a single metafield."""
        
        processed_metafield = metafield.copy()
        
        # Transform value based on type
        if rules.get('transform_value'):
            transform_type = rules['transform_value']
            
            if transform_type == 'uppercase':
                processed_metafield['value'] = processed_metafield.get('value', '').upper()
            elif transform_type == 'lowercase':
                processed_metafield['value'] = processed_metafield.get('value', '').lower()
            elif transform_type == 'title_case':
                processed_metafield['value'] = processed_metafield.get('value', '').title()
            elif transform_type == 'strip_whitespace':
                processed_metafield['value'] = processed_metafield.get('value', '').strip()
            elif transform_type == 'remove_special_chars':
                processed_metafield['value'] = re.sub(r'[^a-zA-Z0-9\s]', '', processed_metafield.get('value', ''))
        
        # Parse JSON values
        if rules.get('parse_json') and processed_metafield.get('type') in ['json', 'json_string']:
            try:
                processed_metafield['parsed_value'] = json.loads(processed_metafield.get('value', '{}'))
            except json.JSONDecodeError:
                processed_metafield['parsed_value'] = None
                processed_metafield['parse_error'] = 'Invalid JSON'
        
        # Extract numeric values
        if rules.get('extract_numbers'):
            value = processed_metafield.get('value', '')
            numbers = re.findall(r'-?\d+\.?\d*', value)
            processed_metafield['extracted_numbers'] = [float(n) if '.' in n else int(n) for n in numbers]
        
        # Add computed fields
        if rules.get('add_computed_fields'):
            computed_rules = rules['add_computed_fields']
            
            if computed_rules.get('character_count'):
                processed_metafield['character_count'] = len(processed_metafield.get('value', ''))
            
            if computed_rules.get('word_count'):
                processed_metafield['word_count'] = len(processed_metafield.get('value', '').split())
            
            if computed_rules.get('is_empty'):
                processed_metafield['is_empty'] = not bool(processed_metafield.get('value', '').strip())
        
        # Custom preprocessing function
        if rules.get('custom_preprocessor') and callable(rules['custom_preprocessor']):
            processed_metafield = rules['custom_preprocessor'](processed_metafield)
        
        return processed_metafield
    
    def group_metafields_by_key(self, metafields: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group metafields by their key."""
        grouped = defaultdict(list)
        
        for metafield in metafields:
            key = metafield.get('key', 'unknown')
            grouped[key].append(metafield)
        
        return dict(grouped)
    
    def analyze_metafields(self, metafields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze metafields and provide analytics."""
        
        if not metafields:
            return {
                'total_metafields': 0,
                'namespaces': {},
                'field_types': {},
                'keys': {}
            }
        
        namespaces = defaultdict(int)
        field_types = defaultdict(int)
        keys = defaultdict(int)
        value_lengths = []
        
        for metafield in metafields:
            namespace = metafield.get('namespace', 'unknown')
            field_type = metafield.get('type', 'unknown')
            key = metafield.get('key', 'unknown')
            value = metafield.get('value', '')
            
            namespaces[namespace] += 1
            field_types[field_type] += 1
            keys[key] += 1
            value_lengths.append(len(value))
        
        # Calculate value length statistics
        avg_value_length = sum(value_lengths) / len(value_lengths) if value_lengths else 0
        
        return {
            'total_metafields': len(metafields),
            'unique_namespaces': len(namespaces),
            'unique_keys': len(keys),
            'unique_types': len(field_types),
            'namespaces': dict(namespaces),
            'field_types': dict(field_types),
            'keys': dict(keys),
            'value_stats': {
                'average_length': round(avg_value_length, 2),
                'min_length': min(value_lengths) if value_lengths else 0,
                'max_length': max(value_lengths) if value_lengths else 0
            }
        }
    
    def find_duplicate_values(self, metafields: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Find metafields with duplicate values."""
        
        value_groups = defaultdict(list)
        
        for metafield in metafields:
            value = metafield.get('value', '')
            if value:  # Only group non-empty values
                value_groups[value].append(metafield)
        
        # Return only groups with duplicates
        duplicates = {value: mfs for value, mfs in value_groups.items() if len(mfs) > 1}
        
        return duplicates
    
    def validate_metafield_values(self, metafields: List[Dict[str, Any]], 
                                validation_rules: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate metafield values against rules."""
        
        validation_results = []
        
        for metafield in metafields:
            key = metafield.get('key')
            value = metafield.get('value', '')
            
            if key in validation_rules:
                rules = validation_rules[key]
                validation_result = {
                    'metafield': metafield,
                    'valid': True,
                    'errors': []
                }
                
                # Required field check
                if rules.get('required') and not value.strip():
                    validation_result['valid'] = False
                    validation_result['errors'].append('Field is required but empty')
                
                # Length validation
                if rules.get('min_length') and len(value) < rules['min_length']:
                    validation_result['valid'] = False
                    validation_result['errors'].append(f'Value too short (min: {rules["min_length"]})')
                
                if rules.get('max_length') and len(value) > rules['max_length']:
                    validation_result['valid'] = False
                    validation_result['errors'].append(f'Value too long (max: {rules["max_length"]})')
                
                # Pattern validation
                if rules.get('pattern'):
                    pattern = re.compile(rules['pattern'])
                    if not pattern.match(value):
                        validation_result['valid'] = False
                        validation_result['errors'].append(f'Value does not match pattern: {rules["pattern"]}')
                
                # Allowed values
                if rules.get('allowed_values') and value not in rules['allowed_values']:
                    validation_result['valid'] = False
                    validation_result['errors'].append(f'Value not in allowed list: {rules["allowed_values"]}')
                
                # Custom validation
                if rules.get('custom_validator') and callable(rules['custom_validator']):
                    try:
                        is_valid, error_message = rules['custom_validator'](value)
                        if not is_valid:
                            validation_result['valid'] = False
                            validation_result['errors'].append(error_message)
                    except Exception as e:
                        validation_result['valid'] = False
                        validation_result['errors'].append(f'Custom validation error: {str(e)}')
                
                validation_results.append(validation_result)
        
        return validation_results
    
    def _filter_by_date_range(self, metafields: List[Dict[str, Any]], 
                            created_after: str, created_before: str) -> List[Dict[str, Any]]:
        """Filter metafields by creation date range."""
        
        from datetime import datetime
        
        filtered = []
        
        for metafield in metafields:
            created_at = metafield.get('createdAt')
            if not created_at:
                continue
            
            try:
                # Parse ISO date string
                created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                
                if created_after:
                    after_date = datetime.fromisoformat(created_after)
                    if created_date < after_date:
                        continue
                
                if created_before:
                    before_date = datetime.fromisoformat(created_before)
                    if created_date > before_date:
                        continue
                
                filtered.append(metafield)
                
            except ValueError:
                # Skip if date parsing fails
                continue
        
        return filtered