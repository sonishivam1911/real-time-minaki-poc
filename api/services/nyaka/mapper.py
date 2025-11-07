"""
Updated Nykaa Mapper Service with Metaobject Support
Handles both direct metafields and metaobject references
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import json
from .config import (
    COMPANY_DEFAULTS,
    JEWELRY_DEFAULTS,
    ALL_NYKAA_COLUMNS,
    clean_description,
    remove_brand_from_title,
    generate_pack_contains,
    validate_nykaa_row
)
from services.shopify.metaobject import MetaobjectService


class NykaaProductMapper:
    """
    Maps product data from Shopify/Zakya to Nykaa format
    Handles metaobject references
    """
    
    def __init__(self, shopify_connector=None):
        """
        Initialize mapper
        
        Args:
            shopify_connector: Optional ShopifyGraphQLConnector for resolving metaobjects
        """
        self.brand_name = COMPANY_DEFAULTS["brand_name"]
        self.shopify = shopify_connector
        self.metaobject_cache = {}  # Cache resolved metaobjects
        # Initialize metaobject service using the same connector
        self.metaobject_service = MetaobjectService(shopify_connector) if shopify_connector else None
    
    def get_metafield_value(self, metafields: List[Dict], namespace: str, key: str) -> Optional[str]:
        """
        Get metafield value by namespace and key
        Handles both direct values and metaobject references
        
        Args:
            metafields: List of metafield objects
            namespace: Metafield namespace
            key: Metafield key
        
        Returns:
            Value as string or None
        """
        if not metafields:
            return None
        
        for metafield in metafields:
            if metafield.get("namespace") == namespace and metafield.get("key") == key:
                value = metafield.get("value")
                field_type = metafield.get("type", "")
                
                print(f"🔍 Found metafield {namespace}.{key}: value='{value}', type='{field_type}'")
                
                # Handle metaobject references
                if "metaobject_reference" in field_type:
                    return self._resolve_metaobject_reference(value, field_type)
                
                # Handle list fields
                if field_type.startswith("list."):
                    try:
                        parsed = json.loads(value) if isinstance(value, str) else value
                        if isinstance(parsed, list):
                            # For list.metaobject_reference, resolve each reference
                            if "metaobject_reference" in field_type:
                                resolved = [self._resolve_metaobject_reference(item, field_type) for item in parsed]
                                return ", ".join([r for r in resolved if r])
                            # For other lists, join with comma
                            return ", ".join(str(item) for item in parsed)
                    except:
                        return value
                
                return value
        
        return None
    
    def _resolve_metaobject_reference(self, value: str, field_type: str) -> Optional[str]:
        """
        Resolve metaobject reference to actual value
        
        Args:
            value: Metaobject GID (e.g., "gid://shopify/Metaobject/129887371487")
            field_type: Type of the field
        
        Returns:
            Resolved value or None
        """
        if not value:
            return None
        
        print(f"🔍 Raw metaobject value: '{value}' (type: {type(value)})")
        
        # Clean up the value - handle various formats
        cleaned_value = str(value).strip()
        
        # Handle JSON array format: ["gid://shopify/Metaobject/123"]
        if cleaned_value.startswith('["') and cleaned_value.endswith('"]'):
            try:
                import json
                parsed_array = json.loads(cleaned_value)
                if isinstance(parsed_array, list) and len(parsed_array) > 0:
                    cleaned_value = parsed_array[0]  # Take first item from array
                    print(f"🔧 Extracted from JSON array: '{cleaned_value}'")
            except:
                # If JSON parsing fails, try manual extraction
                cleaned_value = cleaned_value[2:-2]  # Remove [" and "]
                print(f"🔧 Manual extraction from array: '{cleaned_value}'")
        
        # Handle quoted strings with trailing brackets: "value"]
        elif cleaned_value.startswith('"') and cleaned_value.endswith('"]'):
            cleaned_value = cleaned_value[1:-2]  # Remove opening quote and closing quote+bracket
            print(f"🔧 Removed quotes and bracket: '{cleaned_value}'")
        
        # Handle regular quoted strings: "value"
        elif cleaned_value.startswith('"') and cleaned_value.endswith('"'):
            cleaned_value = cleaned_value[1:-1]  # Remove quotes
            print(f"🔧 Removed quotes: '{cleaned_value}'")
        
        print(f"🧹 Final cleaned metaobject value: '{value}' -> '{cleaned_value}'")
        
        # Validate that we have a proper GID format
        if not cleaned_value.startswith('gid://shopify/'):
            print(f"⚠️ Invalid GID format: '{cleaned_value}'")
            return None
        
        # Check cache first
        if cleaned_value in self.metaobject_cache:
            cached_result = self.metaobject_cache[cleaned_value]
            print(f"📋 Using cached metaobject result: {cached_result}")
            return cached_result
        
        # If we have a Shopify connector, fetch the metaobject
        if self.metaobject_service:
            try:
                resolved_value = self._fetch_metaobject_value(cleaned_value)
                if resolved_value:
                    print(f"✅ Resolved metaobject {cleaned_value} -> {resolved_value}")
                    self.metaobject_cache[cleaned_value] = resolved_value
                    return resolved_value
                else:
                    print(f"❌ Failed to resolve metaobject: {cleaned_value}")
            except Exception as e:
                print(f"⚠️ Error resolving metaobject {cleaned_value}: {e}")
        else:
            print(f"⚠️ No metaobject service available for resolving: {cleaned_value}")
        
        # Fallback: extract ID from GID for logging
        # Format: gid://shopify/Metaobject/ID
        try:
            metaobject_id = cleaned_value.split("/")[-1]
            fallback_result = f"metaobject_{metaobject_id}"
            print(f"🔄 Using fallback result: {fallback_result}")
            return fallback_result
        except:
            print(f"💥 Complete failure to parse metaobject: {value}")
            return None
    
    def _fetch_metaobject_value(self, gid: str) -> Optional[str]:
        """
        Fetch metaobject value from Shopify using existing metaobject service
        
        Args:
            gid: Metaobject GID
        
        Returns:
            Display name or handle of the metaobject
        """
        print(f"📡 Fetching metaobject from Shopify using MetaobjectService: {gid}")
        
        try:
            # Use the existing metaobject service
            result = self.metaobject_service.get_metaobject_by_id(gid)
            print(f"📊 Metaobject service response: {result}")
            
            metaobject = result.get("data", {}).get("metaobject")
            
            if metaobject:
                # Try to find display name from fields first
                fields = metaobject.get("fields", [])
                display_name = None
                
                # Look for common display name fields
                for field in fields:
                    field_key = field.get("key", "").lower()
                    if field_key in ["display_name", "name", "title", "label"]:
                        display_name = field.get("value")
                        break
                
                # Fallback to handle if no display name found
                handle = metaobject.get("handle")
                
                resolved_name = display_name or handle
                print(f"🎯 Metaobject resolved: display_name='{display_name}', handle='{handle}', using='{resolved_name}'")
                return resolved_name
            else:
                print(f"⚠️ No metaobject found for GID: {gid}")
                return None
                
        except Exception as e:
            print(f"💥 Exception in _fetch_metaobject_value: {e}")
            return None
    
    def extract_variant_option(self, variants: List[Dict], option_name: str) -> Optional[str]:
        """
        Extract variant option value (e.g., Color, Size)
        """
        if not variants or len(variants) == 0:
            return None
        
        variant = variants[0]
        
        # Check selectedOptions (new GraphQL structure)
        selected_options = variant.get("selectedOptions", [])
        for option in selected_options:
            if option.get("name", "").lower() == option_name.lower():
                return option.get("value")
        
        # Fallback to old option fields for backward compatibility
        for i in range(1, 4):
            option_key = f"option{i}"
            if option_key in variant and variant[option_key]:
                return variant[option_key]
        
        return None
    
    def extract_from_tags(self, tags: List[str], prefix: str) -> Optional[str]:
        """
        Extract value from tags by prefix
        
        Args:
            tags: List of product tags
            prefix: Prefix to search for (e.g., "Color", "Gender")
        
        Returns:
            Extracted value or None
        
        Example:
            tags = ["Color  Red", "Gender:Woman"]
            extract_from_tags(tags, "Color") → "Red"
        """
        if not tags:
            return None
        
        for tag in tags:
            # Handle both ":" and whitespace separators
            if tag.startswith(prefix):
                # Remove prefix and clean
                value = tag[len(prefix):].strip()
                value = value.lstrip(":").strip()
                if value:
                    return value
        
        return None
    
    def map_shopify_product_to_nykaa(self, shopify_product: Dict[str, Any], 
                                     zakya_product: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Map a single Shopify product to Nykaa format
        NOW SUPPORTS: Automatic Zakya data extraction from _zakya_data field
        
        Args:
            shopify_product: Product data from Shopify GraphQL
            zakya_product: Optional product data from Zakya (legacy parameter)
        
        Returns:
            Dictionary with Nykaa column names as keys
        """
        
        # NEW: Check if Zakya data is attached to Shopify product
        if not zakya_product and "_zakya_data" in shopify_product:
            zakya_product = shopify_product["_zakya_data"]
            print(f"📦 Using attached Zakya data for SKU: {zakya_product.get('sku', 'unknown') if zakya_product else 'none'}")
        
        # Extract data from Shopify product
        product_id = shopify_product.get("id", "")
        title = shopify_product.get("title", "")
        description = shopify_product.get("descriptionHtml", "") or shopify_product.get("description", "")
        vendor = shopify_product.get("vendor", self.brand_name)
        product_type = shopify_product.get("productType", "")
        handle = shopify_product.get("handle", "")
        tags = shopify_product.get("tags", [])
        
        # Get variants
        variants = shopify_product.get("variants", {}).get("edges", [])
        variant_nodes = [edge["node"] for edge in variants] if variants else []
        first_variant = variant_nodes[0] if variant_nodes else {}
        
        # Get images
        images = shopify_product.get("images", {}).get("edges", [])
        image_nodes = [edge["node"] for edge in images] if images else []
        
        # Get metafields
        metafields_edges = shopify_product.get("metafields", {}).get("edges", [])
        metafields = [edge["node"] for edge in metafields_edges] if metafields_edges else []
        
        # =====================================================
        # MAP TO NYKAA COLUMNS
        # =====================================================
        
        nykaa_row = {}
        
        # --- VENDOR SKU CODE (Mandatory) ---
        nykaa_row["Vendor SKU Code"] = first_variant.get("sku", "") or handle
        
        # --- GENDER (Mandatory) ---
        # Try: metaobject → tags → default
        gender = self.get_metafield_value(metafields, "shopify", "target-gender")
        if not gender:
            gender = self.extract_from_tags(tags, "Gender")
        nykaa_row["Gender"] = gender or JEWELRY_DEFAULTS["gender"]
        
        # --- BRAND NAME (Mandatory) ---
        nykaa_row["Brand Name"] = vendor or self.brand_name
        
        # --- STYLE CODE (Mandatory) ---
        style_code = first_variant.get("sku", "") or handle
        nykaa_row["Style Code"] = style_code
        
        # --- PRODUCT NAME (Mandatory) ---
        # Remove brand name from title
        product_name = remove_brand_from_title(title, self.brand_name)
        nykaa_row["Product Name"] = product_name
        
        # --- DESCRIPTION (Mandatory) ---
        # Clean description according to Nykaa guidelines
        nykaa_row["Description"] = clean_description(description)
        
        # --- PRICE (Mandatory) ---
        # Priority: Zakya rate > Shopify variant price
        if zakya_product and "rate" in zakya_product:
            nykaa_row["Price"] = str(zakya_product["rate"])
        else:
            nykaa_row["Price"] = str(first_variant.get("price", "0"))
        
        # --- COLOR (Mandatory) ---
        # Try: metaobject → variant → tags → default
        color = self.get_metafield_value(metafields, "shopify", "color-pattern")
        if not color:
            color = self.extract_variant_option(variant_nodes, "Color")
        if not color:
            color = self.extract_from_tags(tags, "Color")
        nykaa_row["Color"] = color or "Multicolor"
        
        # --- COUNTRY OF ORIGIN (Mandatory) ---
        nykaa_row["Country of Origin"] = COMPANY_DEFAULTS["country_of_origin"]
        
        # --- MANUFACTURER NAME (Mandatory) ---
        nykaa_row["Manufacturer Name"] = COMPANY_DEFAULTS["manufacturer_name"]
        
        # --- MANUFACTURER ADDRESS (Mandatory) ---
        nykaa_row["Manufacturer Address"] = COMPANY_DEFAULTS["manufacturer_address"]
        
        # --- RETURN AVAILABLE (Mandatory) ---
        nykaa_row["return_available"] = COMPANY_DEFAULTS["return_available"]
        
        # --- IS REPLACEABLE (Mandatory) ---
        nykaa_row["Is Replaceable"] = COMPANY_DEFAULTS["is_replaceable"]
        
        # --- BRAND SIZE (Mandatory) ---
        size = self.extract_variant_option(variant_nodes, "Size")
        nykaa_row["brand size"] = size or "One Size"
        
        # --- MULTIPACK SET (Mandatory) ---
        nykaa_row["Multipack Set"] = JEWELRY_DEFAULTS["multipack_set"]
        
        # --- OCCASION (Mandatory) ---
        # Try: addfea.occasion metafield → tags → default
        occasion = self.get_metafield_value(metafields, "addfea", "occasion")
        nykaa_row["Occasion"] = occasion or "Party, Wedding, Festive"
        
        # --- SEASON (Mandatory) ---
        nykaa_row["Season"] = JEWELRY_DEFAULTS["season"]
        
        # --- CARE INSTRUCTION (Mandatory) ---
        care = COMPANY_DEFAULTS["care_instructions"]
        nykaa_row["Care Instruction"] = care
        
        # --- SHIPS IN (Mandatory) ---
        # Can extract from meta.estimateStartDate and meta.estimateEndDate
        start_days = self.get_metafield_value(metafields, "meta", "estimateStartDate")
        end_days = self.get_metafield_value(metafields, "meta", "estimateEndDate")
        if start_days and end_days:
            nykaa_row["Ships In"] = f"{start_days}-{end_days} Days"
        else:
            nykaa_row["Ships In"] = COMPANY_DEFAULTS["ships_in"]
        
        # --- HSN CODES (Mandatory) ---
        nykaa_row["HSN Codes"] = COMPANY_DEFAULTS["hsn_code"]
        
        # --- PACK CONTAINS (Mandatory) ---
        # Try to extract from tags (Component:...)
        components = []
        for tag in tags:
            if tag.startswith("Component:"):
                component = tag.replace("Component:", "").strip()
                components.append(component)
        
        if components:
            nykaa_row["Pack Contains"] = generate_pack_contains(", ".join(components), has_box=True)
        else:
            # Use product_type or fallback to generic description
            jewelry_type = product_type or "Jewelry"
            nykaa_row["Pack Contains"] = generate_pack_contains(jewelry_type, has_box=True)
        
        # --- NET QTY (Mandatory) ---
        nykaa_row["Net Qty"] = JEWELRY_DEFAULTS["net_qty"]
        
        # --- MATERIAL (Mandatory) ---
        # From custom.base_metal metaobject
        material = self.get_metafield_value(metafields, "custom", "base_metal")
        nykaa_row["Material"] = material or "Metal"
        
        # --- PLATING (Mandatory) ---
        # From custom.finish metaobject
        plating = self.get_metafield_value(metafields, "custom", "finish")
        if not plating:
            # Try to extract from tags
            plating = self.extract_from_tags(tags, "Finish")
        nykaa_row["Plating"] = plating or "Not Applicable"
        
        # --- STYLES OF JEWELLERY (Mandatory) ---
        # From custom.jewelry_line metaobject
        style = self.get_metafield_value(metafields, "custom", "jewelry_line")
        nykaa_row["Styles of Jewellery"] = style or "Contemporary"
        
        # --- TYPE OF JEWELLERY (Mandatory) ---
        # From shopify.jewelry-type metaobject or product_type
        jewelry_type = self.get_metafield_value(metafields, "shopify", "jewelry-type")
        nykaa_row["Type of Jewellery"] = jewelry_type or product_type or "Jewelry Set"
        
        # --- SEGMENT (Mandatory) ---
        nykaa_row["Segment"] = JEWELRY_DEFAULTS["segment"]
        
        # --- FRONT IMAGE (Mandatory) ---
        nykaa_row["Front Image"] = image_nodes[0]["url"] if len(image_nodes) > 0 else ""
        
        # --- BACK IMAGE (Mandatory) ---
        nykaa_row["Back Image"] = image_nodes[1]["url"] if len(image_nodes) > 1 else ""
        
        # =====================================================
        # OPTIONAL COLUMNS
        # =====================================================
        
        # --- EAN CODES (Optional) ---
        nykaa_row["Ean Codes"] = first_variant.get("barcode", "")
        
        # --- DESIGN CODE (Optional) ---
        nykaa_row["Design Code"] = ""
        
        # --- DISCLAIMER (Optional) ---
        nykaa_row["Disclaimer"] = ""
        
        # --- RESPONSIBILITY CRITERIA (Optional) ---
        nykaa_row["Responsibility Criteria"] = ""
        
        # --- COLLECTIONS FUNCTION (Optional) ---
        nykaa_row["Collections Function"] = ""
        
        # --- WARRANTY (Optional) ---
        nykaa_row["Warranty"] = COMPANY_DEFAULTS["warranty"]
        
        # --- PRODUCT WEIGHT (Optional) ---
        # Try to get weight from metafields first, then from Zakya data
        weight = self.get_metafield_value(metafields, "custom", "weight")
        if not weight and zakya_product:
            weight = zakya_product.get("weight", "")
        nykaa_row["Product Weight"] = str(weight) if weight else ""
        
        # --- DIMENSIONS (Optional) ---
        nykaa_row["Dimensions"] = ""
        
        # --- DIAMETER (Optional) ---
        nykaa_row["Diameter"] = ""
        
        # --- AGE (Optional) ---
        nykaa_row["Age"] = ""
        
        # --- AGE GROUP (Optional) ---
        age_group = self.get_metafield_value(metafields, "shopify", "age-group")
        nykaa_row["Age Group"] = age_group or ""
        
        # --- ADDITIONAL IMAGES (Optional) ---
        for i in range(1, 9):
            image_index = i + 1  # +1 because first 2 are Front and Back
            if image_index < len(image_nodes):
                nykaa_row[f"Additional Image {i}"] = image_nodes[image_index]["url"]
            else:
                nykaa_row[f"Additional Image {i}"] = ""
        
        return nykaa_row
    
    def map_products_to_nykaa_dataframe(self, shopify_products: List[Dict[str, Any]], 
                                        zakya_products: Optional[List[Dict[str, Any]]] = None) -> pd.DataFrame:
        """
        Map multiple products to Nykaa format and return as DataFrame
        """
        
        # Create SKU lookup for Zakya products
        zakya_lookup = {}
        if zakya_products:
            for zp in zakya_products:
                if zp:  # Skip None values
                    sku = zp.get("sku") or zp.get("item_id")
                    if sku:
                        zakya_lookup[sku] = zp
        
        nykaa_rows = []
        
        for shopify_product in shopify_products:
            # Get matching Zakya product if available
            variants = shopify_product.get("variants", {}).get("edges", [])
            variant_nodes = [edge["node"] for edge in variants] if variants else []
            sku = variant_nodes[0].get("sku") if variant_nodes else None
            
            zakya_product = zakya_lookup.get(sku) if sku else None
            
            # Map to Nykaa format
            nykaa_row = self.map_shopify_product_to_nykaa(shopify_product, zakya_product)
            
            # Validate
            is_valid, errors = validate_nykaa_row(nykaa_row)
            if not is_valid:
                print(f"⚠️  Validation errors for SKU {nykaa_row.get('Vendor SKU Code')}:")
                for error in errors:
                    print(f"   - {error}")
            
            nykaa_rows.append(nykaa_row)
        
        # Create DataFrame with all Nykaa columns
        df = pd.DataFrame(nykaa_rows)
        
        # Ensure all columns are present in correct order
        for col in ALL_NYKAA_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        
        df = df[ALL_NYKAA_COLUMNS]
        
        return df