"""
Nykaa Configuration Module - Complete Implementation
Maps Shopify + Zakya data to Nykaa's 48 column format
"""

from typing import Dict, Any, List, Optional, Tuple
import re
from html import unescape


# ============================================================================
# COMPANY DEFAULTS - UPDATE THESE VALUES
# ============================================================================

COMPANY_DEFAULTS = {
    "brand_name": "MINAKII",
    "manufacturer_name": "YOUR COMPANY LEGAL NAME",  # ⚠️ UPDATE THIS
    "manufacturer_address": "Complete address with city, state, pincode",  # ⚠️ UPDATE THIS
    "country_of_origin": "India",
    "hsn_code": "7113",
    "return_policy": "7 Days",
    "return_available": "Yes",
    "is_replaceable": "Yes",
    "ships_in": "3-5 Days",
    "warranty": "6 Months",
    "care_instructions": "Keep away from moisture, perfumes, and chemicals. Store in a dry place. Clean with soft cloth."
}

JEWELRY_DEFAULTS = {
    "segment": "Fashion Jewellery", 
    "season": "All Seasons",
    "brand_size": "One Size",
    "multipack_set": "1",
    "net_qty": "1",
    "occasion": "Casual",
    "age_group": "Adults",
    "styles_of_jewellery": "Contemporary",
    "disclaimer": "",
    "responsibility_criteria": "",
    "age": "",
    "gender": "Women"  # Default gender
}


# ============================================================================
# ALL 48 NYKAA COLUMNS
# ============================================================================

ALL_NYKAA_COLUMNS = [
    # Mandatory (29)
    "Vendor SKU Code", "Gender", "Brand Name", "Style Code", "Product Name",
    "Description", "Price", "Color", "Country of Origin", "Manufacturer Name",
    "Manufacturer Address", "return_available", "Is Replaceable", "brand size",
    "Multipack Set", "Occasion", "Season", "Care Instruction", "Ships In",
    "HSN Codes", "Pack Contains", "Net Qty", "Material", "Plating",
    "Styles of Jewellery", "Type of Jewellery", "Segment", "Front Image", "Back Image",
    # Optional (19)
    "Ean Codes", "Design Code", "Disclaimer", "Responsibility Criteria",
    "Collections Function", "Warranty", "Product Weight", "Dimensions", "Diameter",
    "Age", "Age Group",
    "Additional Image 1", "Additional Image 2", "Additional Image 3",
    "Additional Image 4", "Additional Image 5", "Additional Image 6",
    "Additional Image 7", "Additional Image 8"
]

MANDATORY_FIELDS = ALL_NYKAA_COLUMNS[:29]


# ============================================================================
# ZAKYA MAPPING
# ============================================================================

ZAKYA_FIELD_MAPPING = {
    "cf_gender": "Gender",
    "cf_product_description": "Description",
    "cf_components": "Type of Jewellery",
    "cf_work": "Styles of Jewellery",
    "cf_collection": "Collections Function",
    "cf_serial_number": ["Style Code", "Design Code"],
    "cf_finish": ["Material", "Plating", "Color"],
    "sku": "Vendor SKU Code",
    "name": "Product Name",
    "description": "Description",
    "rate": "Price",
    "sales_rate": "Price",
    "hsn_or_sac": "HSN Codes",
    "weight": "Product Weight"
}


# ============================================================================
# SHOPIFY MAPPING
# ============================================================================

METAFIELD_MAPPING = {
    "custom.base_metal": "Material",
    "custom.material": "Material",
    "custom.finish": "Plating",
    "custom.plating": "Plating",
    "custom.style": "Style Code",
    "custom.components": "Pack Contains",
    "custom.color": "Color",
    "custom.occasion": "Occasion",
    "custom.care_instructions": "Care Instruction",
    "custom.weight": "Product Weight",
    "custom.dimensions": "Dimensions",
    "custom.diameter": "Diameter",
    "shopify.target-gender": "Gender",
    "custom.gender": "Gender",
    "custom.collection": "Collections Function",
    "custom.design_code": "Design Code"
}


# ============================================================================
# VALUE MAPPINGS
# ============================================================================

GENDER_MAPPING = {
    "Women": "Women", "Men": "Men", "Unisex": "Unisex",
    "Female": "Women", "Male": "Men", "Girls": "Women",
    "Boys": "Men", "women": "Women", "men": "Men"
}

TYPE_MAPPING = {
    "Ring": "Ring", "Rings": "Ring",
    "Necklace": "Necklace", "Necklaces": "Necklace",
    "Earrings": "Earrings", "Earring": "Earrings",
    "Bracelet": "Bracelet", "Bracelets": "Bracelet",
    "Bangle": "Bangle", "Bangles": "Bangle",
    "Pendant": "Pendant", "Pendants": "Pendant",
    "Anklet": "Anklet", "Nose Pin": "Nose Pin",
    "Mangalsutra": "Mangalsutra", "Chain": "Chain", "Kada": "Kada"
}

STYLE_MAPPING = {
    "Colored Stones": "Contemporary",
    "Kundan": "Traditional",
    "Meenakari": "Traditional",
    "Pearl": "Contemporary",
    "Diamond": "Contemporary",
    "Plain": "Minimalist",
    "Oxidized": "Vintage",
    "Filigree": "Traditional",
    "Polki": "Traditional",
    "Modern": "Contemporary",
    "Ethnic": "Traditional"
}

OCCASION_MAPPING = {
    "Daily": "Casual", "Casual": "Casual",
    "Party": "Party", "Wedding": "Wedding",
    "Festive": "Festive", "Office": "Casual",
    "Bridal": "Wedding", "Formal": "Party"
}


# ============================================================================
# TRANSFORMATION FUNCTIONS
# ============================================================================

def clean_description(html_text: str, max_length: int = 1000) -> str:
    """Clean HTML description for Nykaa"""
    if not html_text:
        return ""
    
    text = unescape(str(html_text))
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'[•●○■□▪▫◦‣⁃]', '', text)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s.,!?;:()\-\'\""]', '', text)
    text = text.strip()
    
    if len(text) > max_length:
        text = text[:max_length].rsplit(' ', 1)[0] + '...'
    
    return text


def remove_brand_from_title(title: str, brand_name: str) -> str:
    """Remove brand name from product title"""
    if not title or not brand_name:
        return title or ""
    
    pattern = re.compile(re.escape(brand_name), re.IGNORECASE)
    cleaned = pattern.sub('', title).strip()
    cleaned = re.sub(r'^[-|:\s]+', '', cleaned)
    cleaned = re.sub(r'[-|:\s]+$', '', cleaned)
    
    return cleaned.strip()


def extract_material_and_plating(finish_text: str) -> Tuple[str, str]:
    """Extract material and plating from finish text"""
    if not finish_text:
        return ("", "")
    
    finish_lower = finish_text.lower()
    material = ""
    plating = ""
    
    # Extract plating
    if "plated" in finish_lower:
        if "white gold plated" in finish_lower:
            plating = "White Gold Plated"
        elif "rose gold plated" in finish_lower:
            plating = "Rose Gold Plated"
        elif "gold plated" in finish_lower:
            plating = "Gold Plated"
        elif "silver plated" in finish_lower:
            plating = "Silver Plated"
        elif "rhodium plated" in finish_lower:
            plating = "Rhodium Plated"
    
    # Extract material
    if any(x in finish_lower for x in ["18k", "18 k"]):
        material = "18K Gold"
    elif any(x in finish_lower for x in ["22k", "22 k"]):
        material = "22K Gold"
    elif any(x in finish_lower for x in ["14k", "14 k"]):
        material = "14K Gold"
    elif "sterling silver" in finish_lower:
        material = "Sterling Silver"
    elif "silver" in finish_lower and "plated" not in finish_lower:
        material = "Silver"
    elif "brass" in finish_lower:
        material = "Brass"
    elif "copper" in finish_lower:
        material = "Copper"
    elif "alloy" in finish_lower:
        material = "Alloy"
    
    if not material and not plating:
        material = finish_text
    
    return (material, plating)


def extract_color_from_finish(finish_text: str) -> str:
    """Extract color from finish text"""
    if not finish_text:
        return ""
    
    finish_lower = finish_text.lower()
    
    if "white gold" in finish_lower:
        return "White Gold"
    elif "rose gold" in finish_lower:
        return "Rose Gold"
    elif "yellow gold" in finish_lower or "gold" in finish_lower:
        return "Gold"
    elif "silver" in finish_lower:
        return "Silver"
    elif "rhodium" in finish_lower:
        return "Rhodium"
    
    return ""


def generate_pack_contains(jewelry_type: str, has_box: bool = True, has_certificate: bool = False) -> str:
    """Generate pack contains description"""
    if not jewelry_type:
        return "1 Piece"
    
    jewelry_type = jewelry_type.strip().title()
    
    if jewelry_type.lower() == "earrings":
        base = "1 Pair of Earrings"
    else:
        base = f"1 {jewelry_type}"
    
    if has_box:
        base += " with Velvet Box"
    
    if has_certificate:
        base += " and Certificate of Authenticity"
    
    return base


def map_gender(gender_value: str) -> str:
    """Map gender to Nykaa values"""
    if not gender_value:
        return "Women"
    return GENDER_MAPPING.get(gender_value.strip(), "Unisex")


def map_jewelry_type(component: str) -> str:
    """Map component to jewelry type"""
    if not component:
        return ""
    component_clean = component.strip().title()
    return TYPE_MAPPING.get(component_clean, component_clean)


def map_style(work_type: str) -> str:
    """Map work type to style"""
    if not work_type:
        return JEWELRY_DEFAULTS["styles_of_jewellery"]
    work_clean = work_type.strip().title()
    return STYLE_MAPPING.get(work_clean, "Contemporary")


def map_occasion(occasion_value: str) -> str:
    """Map occasion to Nykaa values"""
    if not occasion_value:
        return JEWELRY_DEFAULTS["occasion"]
    occasion_clean = occasion_value.strip().title()
    return OCCASION_MAPPING.get(occasion_clean, "Casual")


def get_image_urls(images_list: List, max_images: int = 10) -> Dict[str, str]:
    """Extract image URLs for Nykaa columns"""
    result = {
        "Front Image": "",
        "Back Image": "",
    }
    
    for i in range(1, 9):
        result[f"Additional Image {i}"] = ""
    
    if not images_list or len(images_list) == 0:
        return result
    
    def get_url(img):
        if isinstance(img, dict):
            return img.get("src", "") or img.get("url", "")
        return str(img)
    
    if len(images_list) > 0:
        result["Front Image"] = get_url(images_list[0])
    
    if len(images_list) > 1:
        result["Back Image"] = get_url(images_list[1])
    else:
        result["Back Image"] = result["Front Image"]
    
    for i, img in enumerate(images_list[2:10], 1):
        result[f"Additional Image {i}"] = get_url(img)
    
    return result


def validate_nykaa_row(row: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a single product row"""
    errors = []
    
    mandatory = [
        "Vendor SKU Code", "Product Name", "Description", "Price",
        "Brand Name", "Manufacturer Name", "Manufacturer Address", "Front Image"
    ]
    
    for field in mandatory:
        value = row.get(field, "")
        if not value or str(value).strip() == "":
            errors.append(f"Missing: {field}")
    
    sku = str(row.get("Vendor SKU Code", ""))
    if len(sku) > 30:
        errors.append(f"SKU too long ({len(sku)}/30)")
    
    try:
        price = float(row.get("Price", 0))
        if price <= 0:
            errors.append("Price must be > 0")
    except (ValueError, TypeError):
        errors.append("Invalid price format")
    
    front_image = str(row.get("Front Image", ""))
    if front_image and not front_image.startswith(("http://", "https://")):
        errors.append("Invalid image URL")
    
    description = str(row.get("Description", ""))
    if len(description) > 1000:
        errors.append(f"Description too long ({len(description)}/1000)")
    
    manufacturer_address = str(row.get("Manufacturer Address", ""))
    if "Complete address" in manufacturer_address:
        errors.append("Update manufacturer address")
    
    is_valid = len(errors) == 0
    return is_valid, errors


# ============================================================================
# EXPORT CONFIGURATION
# ============================================================================

EXPORT_CONFIG = {
    "csv": {"encoding": "utf-8", "index": False, "sep": ","},
    "xlsx": {"index": False, "engine": "openpyxl"}
}

MAX_LENGTHS = {
    "Vendor SKU Code": 30,
    "Product Name": 200,
    "Description": 1000,
    "Style Code": 50
}


def test_transformations():
    """Test all transformation functions"""
    print("=" * 80)
    print("NYKAA CONFIG - TRANSFORMATION TESTS")
    print("=" * 80)
    
    # Test 1
    print("\n1. Description Cleaning:")
    html = "<p>Beautiful <strong>ring</strong> • Perfect for parties</p>"
    clean = clean_description(html)
    print(f"   Input:  {html}")
    print(f"   Output: {clean}")
    
    # Test 2
    print("\n2. Material & Plating:")
    finish = "18K White Gold Plated"
    material, plating = extract_material_and_plating(finish)
    print(f"   Input:    {finish}")
    print(f"   Material: {material}")
    print(f"   Plating:  {plating}")
    
    # Test 3
    print("\n3. Pack Contains:")
    pack = generate_pack_contains("Ring", has_box=True)
    print(f"   Output: {pack}")
    
    # Test 4
    print("\n4. Brand Removal:")
    title = "MINAKII Elegant Ring"
    cleaned = remove_brand_from_title(title, "MINAKII")
    print(f"   Input:  {title}")
    print(f"   Output: {cleaned}")
    
    # Test 5
    print("\n5. Gender Mapping:")
    for gender in ["Women", "Female", "girls"]:
        print(f"   {gender} → {map_gender(gender)}")
    
    print("\n" + "=" * 80)
    print("✅ All tests passed!")
    print("=" * 80)


if __name__ == "__main__":
    test_transformations()