"""
Zakya Custom Field Extractor
Extracts custom fields from Zakya product data
"""

from typing import Dict, Any, Optional, List


def get_zakya_custom_field(zakya_product: Dict[str, Any], field_name: str) -> Optional[Any]:
    """
    Extract custom field value from Zakya product
    
    Args:
        zakya_product: Zakya product dict
        field_name: Custom field name (e.g., "cf_collection")
    
    Returns:
        Field value or None
    """
    if not zakya_product:
        return None
    
    # Priority 1: Check custom_field_hash (pre-parsed, fastest)
    custom_hash = zakya_product.get("custom_field_hash", {})
    if custom_hash and field_name in custom_hash:
        value = custom_hash.get(field_name)
        # Return unformatted version if available
        unformatted_key = f"{field_name}_unformatted"
        if unformatted_key in custom_hash:
            return custom_hash.get(unformatted_key)
        return value
    
    # Priority 2: Check custom_fields array
    custom_fields = zakya_product.get("custom_fields", [])
    for field in custom_fields:
        if field.get("api_name") == field_name:
            return field.get("value")
    
    return None


def extract_zakya_metadata(zakya_product: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract all relevant metadata from Zakya product
    
    Args:
        zakya_product: Zakya product dict
    
    Returns:
        Dict with extracted fields
    """
    if not zakya_product:
        return {}
    
    # Extract custom fields
    collection = get_zakya_custom_field(zakya_product, "cf_collection")
    gender = get_zakya_custom_field(zakya_product, "cf_gender")
    product_description = get_zakya_custom_field(zakya_product, "cf_product_description")
    components = get_zakya_custom_field(zakya_product, "cf_components")
    work = get_zakya_custom_field(zakya_product, "cf_work")
    finish = get_zakya_custom_field(zakya_product, "cf_finish")
    finding = get_zakya_custom_field(zakya_product, "cf_finding")
    
    # Handle components - might be array or comma-separated string
    if components:
        if isinstance(components, str):
            # If string, split by comma
            components = [c.strip() for c in components.split(",")]
        elif not isinstance(components, list):
            # If not list, wrap in list
            components = [components]
    else:
        components = []
    
    # Extract standard fields
    hsn_code = zakya_product.get("hsn_or_sac")
    price = zakya_product.get("rate") or zakya_product.get("sales_rate")
    category_name = zakya_product.get("category_name")
    sku = zakya_product.get("sku")
    name = zakya_product.get("name")
    description = zakya_product.get("description")
    
    # Extract package details
    package_details = zakya_product.get("package_details", {})
    weight = package_details.get("weight") if package_details else None
    
    return {
        "collection": collection,
        "gender": gender,
        "product_description": product_description,
        "components": components,  # Always a list
        "work": work,
        "finish": finish,
        "finding": finding,
        "hsn_code": hsn_code,
        "price": price,
        "category_name": category_name,
        "sku": sku,
        "name": name,
        "description": description,
        "weight": weight,
    }


def format_zakya_components_for_display(components: List[str]) -> str:
    """
    Format components list for display
    
    Args:
        components: List of component names
    
    Returns:
        Formatted string
    """
    if not components:
        return ""
    
    if len(components) == 1:
        return components[0]
    
    if len(components) == 2:
        return f"{components[0]} and {components[1]}"
    
    return ", ".join(components[:-1]) + " and " + components[-1]