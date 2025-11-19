"""
Type Mapper - Maps product type to Nykaa jewellery types
Handles both Zakya category names and Shopify productType
"""

from typing import Optional


# Comprehensive type mapping (Zakya/Shopify → Nykaa)
TYPE_MAPPING = {
    # Rings
    "Rings": "Rings",
    "Ring": "Rings",
    
    # Necklaces
    "Necklace": "Necklaces & Neckpieces",
    "Necklaces": "Necklaces & Neckpieces",
    "Choker": "Choker",
    "Chokers": "Choker",
    "Pendant": "Pendants",
    "Pendants": "Pendants",
    
    # Earrings
    "Earrings": "Earrings",
    "Earring": "Earrings",
    "Jhumkas": "Jhumkas",
    "Jhumka": "Jhumkas",
    "Chandbali": "Chandbalis",
    "Chandbalis": "Chandbalis",
    "Studs": "Studs",
    "Stud": "Studs",
    "Drops": "Drops & Danglers",
    "Danglers": "Drops & Danglers",
    "Drops & Danglers": "Drops & Danglers",
    "Ear Cuff": "Ear Cuffs & Clips",
    "Ear Cuffs": "Ear Cuffs & Clips",
    "Hoops": "Hoops",
    
    # Bracelets & Bangles
    "Bracelet": "Bracelets",
    "Bracelets": "Bracelets",
    "Bangle": "Bangles",
    "Bangles": "Bangles",
    "Kada": "Cuffs & Kadas",
    "Kadas": "Cuffs & Kadas",
    "Cuff": "Cuffs & Kadas",
    "Cuffs": "Cuffs & Kadas",
    
    # Sets
    "Jewelry Sets": "Jewellery Set",
    "Jewelry Set": "Jewellery Set",
    "Jewellery Sets": "Jewellery Set",
    "Jewellery Set": "Jewellery Set",
    "Set": "Jewellery Set",
    "Sets": "Jewellery Set",
    
    # Traditional Indian Jewelry
    "Maang Tikka": "Maang Tikka",
    "Matha Patti": "Matha Patti",
    "Passa": "Passa",
    "Mangalsutra": "Mangalsutra",
    "Nose Pin": "Nose Pin",
    "Nose Ring": "Nose Rings",
    "Nose Rings": "Nose Rings",
    "Nath": "Naths",
    "Naths": "Naths",
    "Anklet": "Anklet",
    "Anklets": "Anklet",
    "Payal": "Anklet",
    "Toe Ring": "Toe Rings",
    "Toe Rings": "Toe Rings",
    "Bichiya": "Toe Rings",
    "Body Chain": "Body Chain",
    "Hand Harness": "Hand Harness",
    "Hath Phool": "Hand Harness",
    "Waist Chain": "Waist Chains",
    "Waist Chains": "Waist Chains",
    "Kamar Bandh": "Waist Chains",
    "Kaleera": "Kaleeras",
    "Kaleeras": "Kaleeras",
    "Armlet": "Armlet",
    "Brooch": "Brooche",
    "Brooche": "Brooche",
}


def map_jewelry_type(type_value: Optional[str]) -> str:
    """
    Map jewelry type to Nykaa format
    
    Args:
        type_value: Type from Zakya category_name or Shopify productType
    
    Returns:
        Nykaa jewellery type
    """
    if not type_value:
        return "Jewellery Set"
    
    # Exact match
    if type_value in TYPE_MAPPING:
        return TYPE_MAPPING[type_value]
    
    # Case-insensitive match
    for key, value in TYPE_MAPPING.items():
        if key.lower() == type_value.lower():
            return value
    
    # Partial match for compound types
    type_lower = type_value.lower()
    
    if "ring" in type_lower:
        return "Rings"
    if "necklace" in type_lower or "neck" in type_lower:
        return "Necklaces & Neckpieces"
    if "earring" in type_lower or "ear" in type_lower:
        return "Earrings"
    if "bracelet" in type_lower:
        return "Bracelets"
    if "bangle" in type_lower:
        return "Bangles"
    if "set" in type_lower:
        return "Jewellery Set"
    
    # Fallback
    return "Jewellery Set"


def get_type_from_components(cf_components: list) -> Optional[str]:
    """
    Determine type from Zakya components list
    
    Args:
        cf_components: List of components
    
    Returns:
        Type value or None
    """
    if not cf_components or len(cf_components) == 0:
        return None
    
    # If single component, use it as type
    if len(cf_components) == 1:
        return map_jewelry_type(cf_components[0])
    
    # Multiple components = Set
    return "Jewellery Set"