"""
Nykaa Configuration Module - Complete Implementation
Maps Shopify + Zakya data to Nykaa's 48 column format
"""

from typing import Dict, Any, List, Optional, Tuple
import re
from html import unescape


# ============================================================================
# COMPANY DEFAULTS - FIXED VALUES
# ============================================================================

COMPANY_DEFAULTS = {
    "brand_name": "MINAKI",
    "manufacturer_name": "MINAKI",
    "manufacturer_address": "Second Floor, Mckenzie Tower, C-97, Satguru Ram Singh Rd, Mayapuri Industrial Area Phase II, Delhi 110064",
    "country_of_origin": "India",
    "hsn_code": "711790",  # Imitation jewelry - 6 digit code
    "return_policy": "No Returns",
    "return_available": "NO",  # Updated - we don't take returns
    "is_replaceable": "NO",  # Updated - we don't take returns
    "ships_in": 5,  # Integer value - maximum days for shipping
    "warranty": "No Warranty",  # Changed from "0 Months"
    "care_instructions": "Keep away from moisture, perfumes, and chemicals. Store in a dry place. Clean with soft cloth."
}

JEWELRY_DEFAULTS = {
    "segment": "Western",  # Changed from "Fashion Jewellery"
    "season": "Autumn/Winter 2025",  # Will be dynamic
    "brand_size": "One Size",
    "multipack_set": "Single",  # Changed from "1"
    "net_qty": "1N",  # Changed from "1"
    "occasion": "Party",  # Changed to single valid occasion
    "age_group": "",  # Empty for adults
    "styles_of_jewellery": "Contemporary",
    "disclaimer": "",
    "responsibility_criteria": "",
    "age": "",
    "gender": "Women"
}


# ============================================================================
# NYKAA VALUE MAPPINGS - Fix Validation Issues
# ============================================================================

# Map common invalid colors to valid Nykaa colors
# Map invalid styles to valid Nykaa styles
STYLES_MAPPING = {
    # Map to exact matches from Nykaa dropdown
    "traditional": "Temple",  # Traditional jewelry should go to Temple, not Traditional Rakhi
    "ethnic": "Temple", 
    "modern": "Contemporary",
    "classic": "Contemporary",
    "kundan": "Kundan",  # Kundan should map directly to Kundan
    "temple": "Temple",  # Temple maps to Temple
    "meenakari": "Meenakari",  # Meenakari maps to Meenakari
    "minakari": "Meenakari",  # Alternative spelling
    "oxidised": "Oxidised",
    "oxidized": "Oxidised",  # US spelling
    "pearl": "Pearl",
    "pearls": "Pearl",
    "stones": "Stones",
    "stone": "Stones",
    "coloured stone": "Coloured Stone",
    "colored stone": "Coloured Stone",  # US spelling
    "white stones": "White Stones",
    "dramatic": "Dramatic",
    "minimal": "Minimal",
    "minimalist": "Minimal",
    "essential": "Essential",
    "statement": "Statement",
    "fusion": "Fusion",
    "resort": "Resort",
    "sterling silver": "Sterling Silver",
    "silver": "Silver Jewellery",
    "tassel": "Tassel",
    "delicate": "Delicates",
    "delicates": "Delicates",
    "contemporary": "Contemporary",
    "evil eye": "Evil Eye",
    "kaasu malai": "Kaasu Malai",
    "rudraksha": "Rudraksha Rakhi",  # This one is specifically for Rakhi
    "rakhi": "Traditional Rakhi"  # Only actual Rakhi products should use this
}

def normalize_sku(sku: str) -> str:
    """
    Normalize SKU by removing common variant suffixes
    
    Args:
        sku: Original SKU
        
    Returns:
        Normalized SKU without variant suffixes
    """
    if not sku:
        return ""
    
    normalized = sku.upper().strip()
    
    # Remove common variant suffixes
    suffixes_to_remove = [
        "/MC",  # Multi-color
        "/BK",  # Black
        "/WH",  # White  
        "/GD",  # Gold
        "/SL",  # Silver
        "/RG",  # Rose Gold
        "/Gy",  # Grey/Gray
        "GR",   # Green (without slash)
        "Y",    # Yellow (single letter)
    ]
    
    for suffix in suffixes_to_remove:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]
            break
    
    return normalized

def normalize_dropdown_value(value: str, mapping_dict: Dict[str, str]) -> str:
    """
    Normalize a dropdown value using the provided mapping
    
    Args:
        value: Original value
        mapping_dict: Mapping dictionary
        
    Returns:
        Normalized value or default fallback if no mapping found
    """
    if not value:
        return value
        
    # Clean and lowercase for comparison
    cleaned = value.strip().lower()
    
    # Check direct mapping
    if cleaned in mapping_dict:
        return mapping_dict[cleaned]
    
    # Check case-insensitive mapping
    for key, value in mapping_dict.items():
        if key.lower() == cleaned:
            return value
    
    # Check partial matches for occasions (comma-separated)
    if mapping_dict == OCCASION_MAPPING:
        parts = [part.strip() for part in value.split(',')]
        mapped_parts = []
        
        for part in parts:
            part_lower = part.strip().lower()
            mapped = None
            
            # First try exact lowercase match
            if part_lower in mapping_dict:
                mapped = mapping_dict[part_lower]
            else:
                # Try case-insensitive match
                for key, val in mapping_dict.items():
                    if key.lower() == part_lower:
                        mapped = val
                        break
            
            if mapped:  # If mapping found
                if mapped not in mapped_parts:  # Avoid duplicates
                    mapped_parts.append(mapped)
            # If no mapping found, try to find a sensible default
            elif "wedding" in part_lower or "bridal" in part_lower or "marriage" in part_lower:
                if "Wedding" not in mapped_parts:
                    mapped_parts.append("Wedding")
            elif "party" in part_lower or "cocktail" in part_lower or "celebration" in part_lower:
                if "Party" not in mapped_parts:
                    mapped_parts.append("Party")
            elif "festive" in part_lower or "festival" in part_lower or "mehendi" in part_lower or "haldi" in part_lower:
                if "Festive Wear" not in mapped_parts:
                    mapped_parts.append("Festive Wear")
        
        # Return mapped values or fallback to "Party"
        return ', '.join(mapped_parts) if mapped_parts else "Party"
    
    # For color mapping, provide fallbacks
    if mapping_dict == COLOR_MAPPING:
        # Try to find color keywords in the value
        value_lower = value.lower()
        if "gold" in value_lower or "golden" in value_lower:
            return "Gold"
        elif "silver" in value_lower:
            return "Silver"
        elif "rose" in value_lower:
            return "Rose Gold"
        elif "green" in value_lower or "emerald" in value_lower:
            return "Green"
        elif "blue" in value_lower:
            return "Blue"
        elif "red" in value_lower:
            return "Red"
        elif "pink" in value_lower:
            return "Pink"
        elif "black" in value_lower:
            return "Black"
        elif "white" in value_lower:
            return "White"
        else:
            return "Multi-Color"  # Safe default for any unrecognized color
    
    # For other mappings, return the original value (should be rare)
    return value

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
# VALUE MAPPINGS
# ============================================================================

GENDER_MAPPING = {
    "Women": "Women", "Men": "Men", "Unisex": "Unisex",
    "Female": "Women", "Male": "Men", "Girls": "Girls",
    "Boys": "Boys", "women": "Women", "men": "Men",
    "Moms": "Moms"
}

OCCASION_MAPPING = {
    "Daily": "Casual", 
    "Casual": "Casual",
    "Party": "Party", 
    "Wedding": "Wedding",
    "Festive": "Festive Wear",
    "Office": "Work",
    "Formal": "Formal",
    "Bridal": "Wedding",  # Map Bridal → Wedding
    "Anniversary": "Special Occasion",
    "Night Out": "Night Out",
    "Day Wear": "Day Wear",
    "Semi Formal": "Semi Formal",
    "Evening": "Evening Wear",
    "Cocktail": "Cocktail Wear",  # Already exists!
    "Date Night": "Date Night",
    "Festive Wear": "Festive Wear",
    "Wedding Wear": "Wedding Wear",
    "Sporty": "Sports",
    "Any": "Any Occasion",
    "Everyday": "Everyday Essentials",
    "Fusion": "Fusion",
    "Resort": "Resort/Vacation",
    "Vacation": "Resort/Vacation",
    "Lounge": "Loungewear",
    
    # ADD THESE CUSTOM WEDDING OCCASIONS - FIXED TO VALID VALUES:
    "Wedding Tribe": "Wedding",
    "Sangeet": "Wedding Wear", 
    "Mehendi": "Wedding Wear",
    "Haldi": "Wedding Wear", 
    "Mehendi & Haldi": "Wedding Wear",
    "Mehandi & Haldi": "Wedding Wear",  # Alternative spelling
    "Destination Wedding": "Wedding",
    "Celebration": "Special Occasion",  # This IS in valid list
}

# Color normalization mapping
COLOR_MAPPING = {
    # Common color variations → Nykaa colors
    "Golden": "Gold",
    "Emerald": "Green",
    "Emerald Green": "Green",
    "Sky Blue": "Blue",
    "Light Blue": "Blue",
    "Dark Blue": "Navy Blue",
    "Light Pink": "Pink",
    "Dark Pink": "Magenta",
    "Light Green": "Green",
    "Dark Green": "Green",
    "Lime Green": "Green",
    "Neon": "Multi-Color",
    "Multicolor": "Multi-Color",
    "Multi Color": "Multi-Color",
    "Rose": "Rose Gold",
    "Champagne": "Beige",
    "Antique Gold": "Gold",
}

def normalize_color(color: str) -> str:
    """Normalize color to valid Nykaa value"""
    if not color:
        return "Multi-Color"
    
    # Direct match
    if color in COLOR_MAPPING:
        return COLOR_MAPPING[color]
    
    # Case-insensitive match
    for key, value in COLOR_MAPPING.items():
        if key.lower() == color.lower():
            return value
    
    # Return as-is if already valid
    return color


def clean_pack_contains(text: str) -> str:
    """Clean pack contains field for Nykaa"""
    if not text:
        return text
    
    # Remove HTML entities
    text = text.replace('&Amp;', 'and')
    text = text.replace('&amp;', 'and')
    text = text.replace('&AMP;', 'and')
    text = text.replace('&', 'and')  # Any remaining ampersands
    
    # Remove other special characters that Nykaa doesn't allow
    text = text.replace('---', '')
    text = text.replace('#', '')
    text = text.replace('%', '')
    text = text.replace('*', '')
    
    # Clean and trim whitespace
    text = ' '.join(text.split())  # Remove extra spaces
    
    return text


def validate_hsn(hsn: str) -> str:
    """Ensure HSN is 6 or 8 digits"""
    if not hsn:
        return COMPANY_DEFAULTS["hsn_code"]
        
    hsn = str(hsn).strip()
    
    # Remove any non-numeric characters
    hsn = ''.join(filter(str.isdigit, hsn))
    
    if len(hsn) not in [6, 8]:
        # Default to jewelry HSN if invalid
        return COMPANY_DEFAULTS["hsn_code"]
    
    return hsn

def normalize_occasion(occasion: str) -> str:
    """
    Normalize occasion to valid Nykaa value(s)
    Handles comma-separated occasions
    """
    if not occasion:
        return JEWELRY_DEFAULTS["occasion"]
    
    # Split by comma if multiple occasions
    occasions = [o.strip() for o in occasion.split(",")]
    normalized = []
    
    for occ in occasions:
        if occ in OCCASION_MAPPING:
            normalized_occ = OCCASION_MAPPING[occ]
        else:
            # Try case-insensitive match
            found = False
            for key, value in OCCASION_MAPPING.items():
                if key.lower() == occ.lower():
                    normalized_occ = value
                    found = True
                    break
            
            if not found:
                # Skip invalid occasions
                continue
        
        # Avoid duplicates
        if normalized_occ not in normalized:
            normalized.append(normalized_occ)
    
    if not normalized:
        return JEWELRY_DEFAULTS["occasion"]
    
    return ", ".join(normalized)

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


def map_gender(gender_value: str) -> str:
    """Map gender to Nykaa values"""
    if not gender_value:
        return "Women"
    return GENDER_MAPPING.get(gender_value.strip(), "Women")


def map_occasion(occasion_value: str) -> str:
    """Map occasion to Nykaa values"""
    if not occasion_value:
        return JEWELRY_DEFAULTS["occasion"]
    occasion_clean = occasion_value.strip().title()
    return OCCASION_MAPPING.get(occasion_clean, "Party")


def get_image_urls(images_list: List, max_images: int = 10) -> Dict[str, str]:
    """Extract image URLs for Nykaa columns - requires at least 2 different images"""
    result = {
        "Front Image": "",
        "Back Image": "",
    }
    
    for i in range(1, 9):
        result[f"Additional Image {i}"] = ""
    
    if not images_list or len(images_list) < 2:
        return result  # Return empty if less than 2 images
    
    def get_url(img):
        if isinstance(img, dict):
            return img.get("src", "") or img.get("url", "")
        return str(img)
    
    # Only set images if we have at least 2 different images
    if len(images_list) >= 2:
        result["Front Image"] = get_url(images_list[0])
        result["Back Image"] = get_url(images_list[1])
        
        # Only proceed if front and back are actually different
        if result["Front Image"] == result["Back Image"]:
            result["Front Image"] = ""
            result["Back Image"] = ""
            return result
    
    # Add additional images starting from the 3rd image
    for i, img in enumerate(images_list[2:10], 1):
        result[f"Additional Image {i}"] = get_url(img)
    
    return result


def validate_nykaa_row(row: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a single product row"""
    errors = []
    
    mandatory = [
        "Vendor SKU Code", "Product Name", "Description", "Price",
        "Brand Name", "Manufacturer Name", "Manufacturer Address", "Front Image", "Back Image"
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
    
    # Validate both front and back images
    front_image = str(row.get("Front Image", ""))
    back_image = str(row.get("Back Image", ""))
    
    if front_image and not front_image.startswith(("http://", "https://")):
        errors.append("Invalid Front Image URL")
    
    if back_image and not back_image.startswith(("http://", "https://")):
        errors.append("Invalid Back Image URL")
    
    # Ensure both front and back images are present and different
    if front_image and back_image:
        if front_image == back_image:
            errors.append("Front and Back images must be different - product needs unique front and back images")
    
    description = str(row.get("Description", ""))
    if len(description) > 1000:
        errors.append(f"Description too long ({len(description)}/1000)")
    
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