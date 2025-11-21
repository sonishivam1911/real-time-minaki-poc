"""
Metafield Diagnostic Tool
Use this to inspect all metafields and their definitions in your Shopify store
"""

from services.shopify.base_connector import BaseShopifyConnector
from services.shopify.product import ShopifyProductService
from services.shopify.metafield_validator import MetafieldValidator
import json


def scan_existing_metafields(sample_size: int = 10) -> dict:
    """
    Scan a sample of products to see what metafields actually exist
    """
    client = BaseShopifyConnector()
    product_service = ShopifyProductService(client)
    
    print(f"\n🔍 Scanning {sample_size} products for existing metafields...\n")
    
    # Get sample products
    result = product_service.get_products(first=sample_size)
    products = result.get('data', {}).get('products', {}).get('edges', [])
    
    all_namespaces = set()
    namespace_keys = {}
    
    for i, product_edge in enumerate(products):
        product = product_edge['node']
        product_id = product.get('id')
        product_title = product.get('title', 'Unknown')
        
        metafields = product.get('metafields', {}).get('edges', [])
        
        print(f"Product {i+1}: {product_title}")
        print(f"  Metafields: {len(metafields)}")
        
        for mf_edge in metafields:
            mf = mf_edge['node']
            namespace = mf.get('namespace')
            key = mf.get('key')
            value = mf.get('value', '')[:50]  # First 50 chars
            mf_type = mf.get('type')
            
            all_namespaces.add(namespace)
            
            if namespace not in namespace_keys:
                namespace_keys[namespace] = set()
            namespace_keys[namespace].add(key)
            
            print(f"    • {namespace}.{key} ({mf_type}): {value}...")
    
    print(f"\n📊 Summary:")
    print(f"Total unique namespaces: {len(all_namespaces)}")
    print(f"Namespaces found: {sorted(list(all_namespaces))}")
    
    print(f"\n📌 Keys by namespace:")
    for ns in sorted(namespace_keys.keys()):
        keys = sorted(list(namespace_keys[ns]))
        print(f"  {ns}: {keys}")
    
    return {
        'namespaces': sorted(list(all_namespaces)),
        'namespace_keys': {k: sorted(list(v)) for k, v in namespace_keys.items()}
    }


def inspect_metafield_definition(namespace: str, key: str):
    """
    Inspect the definition of a specific metafield
    """
    client = BaseShopifyConnector()
    validator = MetafieldValidator(client)
    
    print(f"\n🔎 Inspecting {namespace}.{key}...")
    
    definition = validator.get_metafield_definition(namespace, key)
    
    if not definition:
        print(f"❌ Metafield {namespace}.{key} NOT FOUND in Shopify")
        return None
    
    print(f"✅ Found: {namespace}.{key}")
    print(f"   Name: {definition.get('name')}")
    print(f"   Type: {definition.get('type', {}).get('name')}")
    print(f"   Description: {definition.get('description', 'N/A')}")
    
    # Check for allowed values
    allowed_values = validator.get_allowed_values(namespace, key)
    if allowed_values:
        print(f"   Allowed values ({len(allowed_values)}):")
        for val in allowed_values[:10]:
            print(f"     - {val}")
        if len(allowed_values) > 10:
            print(f"     ... and {len(allowed_values) - 10} more")
    else:
        print(f"   Allowed values: None (free text field)")
    
    return definition


def validate_metafield_value(namespace: str, key: str, value: str):
    """
    Test if a value is valid for a metafield
    """
    client = BaseShopifyConnector()
    validator = MetafieldValidator(client)
    
    print(f"\n✔️  Validating '{value}' for {namespace}.{key}...")
    
    is_valid, error = validator.validate_value_for_metafield(value, namespace, key)
    
    if is_valid:
        print(f"✅ Value is VALID")
    else:
        print(f"❌ Value is INVALID: {error}")
        
        # Try to find a close match
        closest = validator.find_closest_match(value, namespace, key)
        if closest:
            print(f"   💡 Suggestion: Use '{closest}' instead")
    
    return is_valid


def generate_safe_mapping_for_namespace(namespace: str) -> dict:
    """
    Generate a safe mapping configuration for a specific namespace
    """
    client = BaseShopifyConnector()
    validator = MetafieldValidator(client)
    
    print(f"\n📋 Generating safe mapping for namespace '{namespace}'...")
    
    definitions = validator.get_all_metafield_definitions_for_namespace(namespace)
    
    if not definitions:
        print(f"❌ No metafield definitions found for namespace '{namespace}'")
        return {}
    
    mapping = {}
    
    for key, definition in definitions.items():
        field_type = definition.get('type', {}).get('name', 'unknown')
        allowed_values = None
        
        validations = definition.get('validations', [])
        for validation in validations:
            if validation.get('name') == 'choices':
                value_str = validation.get('value')
                if isinstance(value_str, str):
                    try:
                        allowed_values = json.loads(value_str)
                    except:
                        pass
        
        mapping[key] = {
            'type': field_type,
            'allowed_values': allowed_values,
            'description': definition.get('description', '')
        }
    
    print(f"Found {len(mapping)} metafields in '{namespace}':")
    for key, info in sorted(mapping.items()):
        print(f"  {key}: {info['type']}")
        if info['allowed_values']:
            print(f"    Choices: {info['allowed_values'][:3]}...")
    
    return mapping


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Metafield Diagnostic Tool")
        print("\nUsage:")
        print("  python metafield_diagnostic.py scan [sample_size]")
        print("  python metafield_diagnostic.py inspect <namespace> <key>")
        print("  python metafield_diagnostic.py validate <namespace> <key> <value>")
        print("  python metafield_diagnostic.py mapping <namespace>")
        print("\nExamples:")
        print("  python metafield_diagnostic.py scan 10")
        print("  python metafield_diagnostic.py inspect custom gender")
        print("  python metafield_diagnostic.py validate addfea gender Women")
        print("  python metafield_diagnostic.py mapping custom")
        sys.exit(0)
    
    command = sys.argv[1]
    
    if command == "scan":
        sample_size = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        scan_existing_metafields(sample_size)
    
    elif command == "inspect":
        namespace = sys.argv[2]
        key = sys.argv[3]
        inspect_metafield_definition(namespace, key)
    
    elif command == "validate":
        namespace = sys.argv[2]
        key = sys.argv[3]
        value = sys.argv[4]
        validate_metafield_value(namespace, key, value)
    
    elif command == "mapping":
        namespace = sys.argv[2]
        generate_safe_mapping_for_namespace(namespace)
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
