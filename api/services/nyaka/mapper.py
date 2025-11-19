"""
Updated Nykaa Mapper with Zakya Priority
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import json

from .config import (
    ALL_NYKAA_COLUMNS, COMPANY_DEFAULTS, JEWELRY_DEFAULTS,
    validate_nykaa_row,
    normalize_dropdown_value, clean_description, remove_brand_from_title,
    normalize_sku, COLOR_MAPPING,
    GENDER_MAPPING, 
    OCCASION_MAPPING, 
    STYLES_MAPPING,
    clean_pack_contains,
    validate_hsn
)# Import all the new mappers
from .zakya_extractor import extract_zakya_metadata
from .plating_mapper import get_plating
from .style_mapper import get_style, get_style_from_tags, detect_style_from_text
from .segment_mapper import get_segment, get_segment_from_tags
from .pack_mapper import (
    get_multipack_set, 
    get_pack_contains, 
    parse_components_from_description
)
from .season_mapper import get_current_season
from .type_mapper import map_jewelry_type, get_type_from_components

from services.shopify.metaobject import MetaobjectService


class NykaaProductMapper:
    """
    Maps product data from Shopify/Zakya to Nykaa format
    NOW WITH ZAKYA-FIRST PRIORITY
    """
    
    def __init__(self, shopify_connector=None):
        """
        Initialize mapper
        
        Args:
            shopify_connector: Optional ShopifyGraphQLConnector for resolving metaobjects
        """
        self.brand_name = COMPANY_DEFAULTS["brand_name"]
        self.shopify = shopify_connector
        self.metaobject_cache = {}
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
                
                # Handle metaobject references
                if "metaobject_reference" in field_type:
                    return self._resolve_metaobject_reference(value, field_type)
                
                # Handle list fields
                if field_type.startswith("list."):
                    try:
                        parsed = json.loads(value) if isinstance(value, str) else value
                        if isinstance(parsed, list):
                            if "metaobject_reference" in field_type:
                                resolved = [self._resolve_metaobject_reference(item, field_type) for item in parsed]
                                return ", ".join([r for r in resolved if r])
                            return ", ".join(str(item) for item in parsed)
                    except:
                        return value
                
                return value
        
        return None
    
    def _resolve_metaobject_reference(self, value: str, field_type: str) -> Optional[str]:
        """
        Resolve metaobject reference to actual value
        
        Args:
            value: Metaobject GID
            field_type: Type of the field
        
        Returns:
            Resolved value or None
        """
        if not value:
            return None
        
        # Clean up the value
        cleaned_value = str(value).strip()
        
        # Handle JSON array format
        if cleaned_value.startswith('["') and cleaned_value.endswith('"]'):
            try:
                parsed_array = json.loads(cleaned_value)
                if isinstance(parsed_array, list) and len(parsed_array) > 0:
                    cleaned_value = parsed_array[0]
            except:
                cleaned_value = cleaned_value[2:-2]
        
        # Handle quoted strings
        elif cleaned_value.startswith('"') and cleaned_value.endswith('"'):
            cleaned_value = cleaned_value[1:-1]
        
        # Validate GID format
        if not cleaned_value.startswith('gid://shopify/'):
            return None
        
        # Check cache
        if cleaned_value in self.metaobject_cache:
            return self.metaobject_cache[cleaned_value]
        
        # Fetch from Shopify
        if self.metaobject_service:
            try:
                resolved_value = self._fetch_metaobject_value(cleaned_value)
                if resolved_value:
                    self.metaobject_cache[cleaned_value] = resolved_value
                    return resolved_value
            except Exception as e:
                print(f"⚠️ Error resolving metaobject {cleaned_value}: {e}")
        
        return None
    
    def _fetch_metaobject_value(self, gid: str) -> Optional[str]:
        """
        Fetch metaobject value from Shopify
        
        Args:
            gid: Metaobject GID
        
        Returns:
            Display name or handle
        """
        try:
            result = self.metaobject_service.get_metaobject_by_id(gid)
            metaobject = result.get("data", {}).get("metaobject")
            
            if metaobject:
                fields = metaobject.get("fields", [])
                
                # Look for display name
                for field in fields:
                    field_key = field.get("key", "").lower()
                    if field_key in ["display_name", "name", "title", "label"]:
                        return field.get("value")
                
                # Fallback to handle
                return metaobject.get("handle")
            
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
        
        # Check selectedOptions
        selected_options = variant.get("selectedOptions", [])
        for option in selected_options:
            if option.get("name", "").lower() == option_name.lower():
                return option.get("value")
        
        return None
    
    def extract_from_tags(self, tags: List[str], prefix: str) -> Optional[str]:
        """
        Extract value from tags by prefix
        
        Args:
            tags: List of product tags
            prefix: Prefix to search for
        
        Returns:
            Extracted value or None
        """
        if not tags:
            return None
        
        for tag in tags:
            if tag.startswith(prefix):
                value = tag[len(prefix):].strip()
                value = value.lstrip(":").strip()
                if value:
                    return value
        
        return None
    
    def map_shopify_product_to_nykaa(self, shopify_product: Dict[str, Any], 
                                     zakya_product: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Map a single Shopify product to Nykaa format
        NOW WITH ZAKYA-FIRST PRIORITY
        
        Args:
            shopify_product: Product data from Shopify GraphQL
            zakya_product: Optional product data from Zakya
        
        Returns:
            Dictionary with Nykaa column names as keys
        """
        
        # Check if Zakya data is attached to Shopify product
        if not zakya_product and "_zakya_data" in shopify_product:
            zakya_product = shopify_product["_zakya_data"]
        
        # =====================================================
        # EXTRACT ZAKYA METADATA (PRIORITY SOURCE)
        # =====================================================
        zakya_meta = extract_zakya_metadata(zakya_product) if zakya_product else {}
        
        # =====================================================
        # EXTRACT SHOPIFY DATA
        # =====================================================
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
        # MAP TO NYKAA COLUMNS WITH ZAKYA PRIORITY
        # =====================================================
        
        nykaa_row = {}
        
        # --- VENDOR SKU CODE (Mandatory) ---
        raw_sku = (
            zakya_meta.get("sku") or
            first_variant.get("sku", "") or
            handle
        )
        # Normalize SKU to remove variant suffixes
        nykaa_row["Vendor SKU Code"] = normalize_sku(raw_sku)
        
        # --- GENDER (Mandatory) ---
        # Priority: Zakya → Shopify metafield → tags → default
        gender = (
            zakya_meta.get("gender") or
            self.get_metafield_value(metafields, "shopify", "target-gender") or
            self.extract_from_tags(tags, "Gender")
        )
        nykaa_row["Gender"] = gender or JEWELRY_DEFAULTS["gender"]
        
        # --- BRAND NAME (Mandatory) ---
        nykaa_row["Brand Name"] = vendor or self.brand_name
        
        # --- STYLE CODE (Mandatory) ---
        nykaa_row["Style Code"] = nykaa_row["Vendor SKU Code"]
        
        # --- PRODUCT NAME (Mandatory) ---
        product_name = remove_brand_from_title(title, self.brand_name)
        nykaa_row["Product Name"] = product_name
        
        # --- DESCRIPTION (Mandatory) ---
        # Priority: Zakya cf_product_description → Shopify description
        desc_text = zakya_meta.get("product_description") or description
        nykaa_row["Description"] = clean_description(desc_text)
        
        # --- PRICE (Mandatory) ---
        # Priority: Zakya rate → Shopify variant price
        price = zakya_meta.get("price") or first_variant.get("price", "0")
        nykaa_row["Price"] = str(price)
        
        # --- COLOR (Mandatory) ---
        color = (
            self.get_metafield_value(metafields, "shopify", "color-pattern") or
            self.extract_variant_option(variant_nodes, "Color") or
            self.extract_from_tags(tags, "Color") or
            self.extract_from_tags(tags, "color")
        )
        # NORMALIZE THE COLOR
        nykaa_row["Color"] = normalize_dropdown_value(color, COLOR_MAPPING) if color else "Multi-Color"
        
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
        # Priority: Zakya components → parse description
        components = zakya_meta.get("components")
        if not components:
            components = parse_components_from_description(description)
        nykaa_row["Multipack Set"] = get_multipack_set(components)
        
        # --- OCCASION (Mandatory) ---
        # Priority: Shopify metafield → parse description → default
        occasion = self.get_metafield_value(metafields, "addfea", "occasion")
        if not occasion:
            # Parse from description for keywords
            desc_lower = description.lower() if description else ""
            if "any function" in desc_lower or "any occasion" in desc_lower:
                occasion = "Any Occasion"
            elif "wedding" in desc_lower:
                occasion = "Wedding, Party"
            elif "party" in desc_lower:
                occasion = "Party"

        # NORMALIZE THE OCCASION
        nykaa_row["Occasion"] = normalize_dropdown_value(occasion, OCCASION_MAPPING) if occasion else JEWELRY_DEFAULTS["occasion"]
        
        # --- SEASON (Mandatory) ---
        # Dynamic based on current date
        nykaa_row["Season"] = get_current_season()
        
        # --- CARE INSTRUCTION (Mandatory) ---
        nykaa_row["Care Instruction"] = COMPANY_DEFAULTS["care_instructions"]
        
        # --- SHIPS IN (Mandatory) ---
        # Try to get from metafields, otherwise use default integer value
        start_days = self.get_metafield_value(metafields, "meta", "estimateStartDate")
        end_days = self.get_metafield_value(metafields, "meta", "estimateEndDate")
        
        if end_days:
            try:
                # Use the end_days as integer (maximum shipping time)
                nykaa_row["Ships In"] = int(end_days)
            except (ValueError, TypeError):
                nykaa_row["Ships In"] = COMPANY_DEFAULTS["ships_in"]
        else:
            nykaa_row["Ships In"] = COMPANY_DEFAULTS["ships_in"]
        
        # --- HSN CODES (Mandatory) ---
        # Priority: Zakya hsn_or_sac → Shopify metafield → default
        hsn = (
            zakya_meta.get("hsn_code") or
            self.get_metafield_value(metafields, "custom", "hsn_code")
        )
        # Validate and ensure HSN is 6 or 8 digits
        nykaa_row["HSN Codes"] = validate_hsn(hsn or COMPANY_DEFAULTS["hsn_code"])
        
        # --- PACK CONTAINS (Mandatory) ---
        pack_contains_raw = get_pack_contains(components)
        nykaa_row["Pack Contains"] = clean_pack_contains(pack_contains_raw)
                
        # --- NET QTY (Mandatory) ---
        nykaa_row["Net Qty"] = JEWELRY_DEFAULTS["net_qty"]
        
        # --- MATERIAL (Mandatory) ---
        # ALWAYS "Alloy" for fashion jewelry
        nykaa_row["Material"] = "Alloy"
        
        # --- PLATING (Mandatory) ---
        # Priority: Zakya cf_finish → parse description → default
        # Returns comma-separated if multiple (e.g., "18K Gold, Rhodium")
        nykaa_row["Plating"] = get_plating(
            zakya_meta.get("finish"),
            description
        )
        
        # --- STYLES OF JEWELLERY (Mandatory) ---
        # Priority: Zakya cf_work → cf_collection → detect from name/description → tags → default
        style = get_style(
            zakya_meta.get("work"),
            zakya_meta.get("collection")
        )

        # If no style, try to detect from product text
        if not style or style == "Contemporary":
            detected_style = detect_style_from_text(f"{title} {description}")
            if detected_style:
                style = detected_style
            else:
                # Try tags as last resort
                tag_style = get_style_from_tags(tags)
                if tag_style:
                    style = tag_style

        # NORMALIZE THE STYLE  
        nykaa_row["Styles of Jewellery"] = normalize_dropdown_value(style, STYLES_MAPPING)
                # --- TYPE OF JEWELLERY (Mandatory) ---
        # Priority: Zakya category_name → cf_components → Shopify productType
        jewelry_type = (
            zakya_meta.get("category_name") or
            get_type_from_components(components) or
            product_type
        )
        nykaa_row["Type of Jewellery"] = map_jewelry_type(jewelry_type)
        
        # --- SEGMENT (Mandatory) ---
        # Collection-based logic
        segment = get_segment(
            zakya_meta.get("collection"),
            nykaa_row["Material"]
        )
        # Fallback to tags
        if not zakya_meta.get("collection"):
            segment = get_segment_from_tags(tags, nykaa_row["Material"])
        nykaa_row["Segment"] = segment
        
        # --- FRONT IMAGE (Mandatory) ---
        nykaa_row["Front Image"] = image_nodes[0]["url"] if len(image_nodes) > 0 else ""
        
        # --- BACK IMAGE (Mandatory) - Must be different from front image ---
        nykaa_row["Back Image"] = image_nodes[1]["url"] if len(image_nodes) > 1 else ""
        
        # =====================================================
        # OPTIONAL COLUMNS
        # =====================================================
        
        # --- EAN CODES (Optional) ---
        barcode = first_variant.get("barcode", "")
        if barcode and len(barcode) == 13 and barcode.isdigit():
            nykaa_row["Ean Codes"] = barcode
        else:
            try:
                from agent.nykaa_rewriter.ean_generator import generate_ean13
                nykaa_row["Ean Codes"] = generate_ean13()
            except Exception as e:
                print(f"⚠️ Failed to generate EAN: {e}")
                nykaa_row["Ean Codes"] = ""
        
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
        weight = zakya_meta.get("weight") or self.get_metafield_value(metafields, "custom", "weight")
        nykaa_row["Product Weight"] = str(weight) if weight else ""
        
        # --- DIMENSIONS (Optional) ---
        nykaa_row["Dimensions"] = ""
        
        # --- DIAMETER (Optional) ---
        nykaa_row["Diameter"] = ""
        
        # --- AGE (Optional) ---
        nykaa_row["Age"] = ""
        
        # --- AGE GROUP (Optional) ---
        nykaa_row["Age Group"] = ""  # Empty for adults
        
        # --- ADDITIONAL IMAGES (Optional) ---
        for i in range(1, 9):
            image_index = i + 1
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
                if zp:
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
                print(f"⚠️  Skipping product with SKU {nykaa_row.get('Vendor SKU Code')} due to validation errors:")
                for error in errors:
                    print(f"   - {error}")
                continue  # Skip this product - don't add to nykaa_rows
            
            # Only add valid products
            nykaa_rows.append(nykaa_row)
        
        # Create DataFrame with all Nykaa columns
        df = pd.DataFrame(nykaa_rows)
        
        # Ensure all columns are present in correct order
        for col in ALL_NYKAA_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        
        df = df[ALL_NYKAA_COLUMNS]
        
        return df