import pandas as pd
from io import BytesIO
from typing import List, Dict, Any


def parse_metafield_mapping_csv(file_content: bytes) -> List[Dict[str, str]]:
    """
    Parse uploaded CSV file into metafield mapping rules.
    
    Expected CSV columns:
    - input_namespace (e.g., "addfica")
    - input_key (e.g., "gender", "data1")
    - input_value (e.g., "Women", "Kundan")
    - input_type (e.g., "single_line_text_shopify")
    - output_namespace (e.g., "shopify")
    - output_key (e.g., "target-gender", "jewelry-type")
    - output_value (e.g., "gid://shopify/Metaobject/123")
    - output_type (e.g., "metaobject_reference")
    
    Args:
        file_content: Raw CSV file bytes from upload
        
    Returns:
        List of mapping rule dictionaries
        
    Example:
        [
            {
                "input_namespace": "addfica",
                "input_key": "gender",
                "input_value": "Women",
                "input_type": "single_line_text_shopify",
                "output_namespace": "shopify",
                "output_key": "target-gender",
                "output_value": "gid://shopify/Metaobject/456",
                "output_type": "metaobject_reference"
            },
            ...
        ]
    """
    try:
        # Read CSV from uploaded bytes
        df = pd.read_csv(BytesIO(file_content))
        
        # Validate required columns
        required_columns = [
            'input_namespace',
            'input_key',
            'input_value',
            'input_type',
            'output_namespace',
            'output_key',
            'output_value',
            'output_type'
        ]
        
        # Check for missing columns
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(
                f"CSV missing required columns: {', '.join(missing_columns)}\n"
                f"Found columns: {', '.join(df.columns.tolist())}"
            )
        
        # Remove any rows with NaN values in critical columns
        df = df.dropna(subset=required_columns)
        
        # Convert to list of dicts
        mapping_rules = df[required_columns].to_dict('records')
        
        # Clean up - strip whitespace from string values
        for rule in mapping_rules:
            for key, value in rule.items():
                if isinstance(value, str):
                    rule[key] = value.strip()
        
        if not mapping_rules:
            raise ValueError("No valid mapping rules found in CSV after parsing")
        
        print(f"Successfully parsed {len(mapping_rules)} mapping rules from CSV")
        return mapping_rules
        
    except pd.errors.ParserError as e:
        raise ValueError(f"Invalid CSV format: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error parsing CSV: {str(e)}")


def validate_mapping_rules(rules: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Validate and analyze mapping rules.
    
    Args:
        rules: List of mapping rule dictionaries
        
    Returns:
        Validation statistics and summary
    """
    if not rules:
        raise ValueError("No mapping rules provided")
    
    # Extract statistics
    input_namespaces = set(rule['input_namespace'] for rule in rules)
    output_namespaces = set(rule['output_namespace'] for rule in rules)
    input_keys = set(rule['input_key'] for rule in rules)
    output_keys = set(rule['output_key'] for rule in rules)
    
    # Group by input namespace/key combinations
    input_combinations = {}
    for rule in rules:
        combo_key = f"{rule['input_namespace']}.{rule['input_key']}"
        if combo_key not in input_combinations:
            input_combinations[combo_key] = []
        input_combinations[combo_key].append(rule['input_value'])
    
    # Count output types
    output_types = {}
    for rule in rules:
        output_type = rule['output_type']
        output_types[output_type] = output_types.get(output_type, 0) + 1
    
    return {
        "total_rules": len(rules),
        "unique_input_namespaces": len(input_namespaces),
        "unique_output_namespaces": len(output_namespaces),
        "unique_input_keys": len(input_keys),
        "unique_output_keys": len(output_keys),
        "input_namespaces": sorted(list(input_namespaces)),
        "output_namespaces": sorted(list(output_namespaces)),
        "input_keys": sorted(list(input_keys)),
        "output_keys": sorted(list(output_keys)),
        "input_key_combinations": len(input_combinations),
        "output_type_distribution": output_types,
        "sample_rules": rules[:5] if len(rules) > 5 else rules
    }


def export_mapping_template() -> bytes:
    """
    Generate a template CSV file for metafield mapping.
    
    Returns:
        CSV file as bytes
    """
    template_data = {
        'input_namespace': ['addfica', 'addfica', 'addfica'],
        'input_key': ['gender', 'data1', 'data1'],
        'input_value': ['Women', 'Kundan', 'Polki'],
        'input_type': ['single_line_text_shopify', 'single_line_text_shopify', 'single_line_text_shopify'],
        'output_namespace': ['shopify', 'shopify', 'shopify'],
        'output_key': ['target-gender', 'jewelry-type', 'jewelry-type'],
        'output_value': ['gid://shopify/Metaobject/123', 'gid://shopify/Metaobject/456', 'gid://shopify/Metaobject/789'],
        'output_type': ['metaobject_reference', 'metaobject_reference', 'metaobject_reference']
    }
    
    df = pd.DataFrame(template_data)
    
    # Convert to CSV bytes
    return df.to_csv(index=False).encode('utf-8')