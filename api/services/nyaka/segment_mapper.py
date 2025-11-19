"""
Segment Mapper - Determines Nykaa segment based on collection and material
"""

from typing import Optional


# Traditional collections
TRADITIONAL_COLLECTIONS = [
    "Kundan", "Polki", "Temple", "Meenakari", "Minakari",
    "Traditional", "Kaasu Malai"
]

# Western collections
WESTERN_COLLECTIONS = [
    "Eleganza", "Crystal", "Contemporary", "Modern",
    "Fashion", "Statement", "Minimal"
]


def get_segment(zakya_collection: Optional[str], material: str) -> str:
    """
    Get segment with priority hierarchy
    
    Args:
        zakya_collection: Value from Zakya cf_collection
        material: Material value (for silver check)
    
    Returns:
        Nykaa segment value (one of: Traditional, Western, Silver Jewellery, 
        Gold & Diamond Jewellery, Coins & Bars)
    """
    # Priority 1: Traditional collections
    if zakya_collection:
        # Exact match
        if zakya_collection in TRADITIONAL_COLLECTIONS:
            return "Traditional"
        
        # Case-insensitive match
        collection_lower = zakya_collection.lower()
        for trad_col in TRADITIONAL_COLLECTIONS:
            if trad_col.lower() == collection_lower:
                return "Traditional"
    
    # Priority 2: Silver material (check before Western)
    if material:
        if "Sterling Silver" in material or material == "Silver":
            return "Silver Jewellery"
    
    # Priority 3: Western collections
    if zakya_collection:
        # Exact match
        if zakya_collection in WESTERN_COLLECTIONS:
            return "Western"
        
        # Case-insensitive match
        collection_lower = zakya_collection.lower()
        for west_col in WESTERN_COLLECTIONS:
            if west_col.lower() == collection_lower:
                return "Western"
    
    # Default to Western for fashion jewelry
    return "Western"


def get_segment_from_tags(tags: list, material: str) -> str:
    """
    Get segment from Shopify tags (fallback)
    
    Args:
        tags: List of product tags
        material: Material value
    
    Returns:
        Segment value
    """
    if not tags:
        return get_segment(None, material)
    
    tags_lower = [t.lower() for t in tags]
    
    # Check for traditional indicators
    if any(t in tags_lower for t in ["kundan", "polki", "temple", "meenakari", "traditional"]):
        return "Traditional"
    
    # Check for silver
    if "silver" in tags_lower or "Sterling Silver" in material:
        return "Silver Jewellery"
    
    # Check for western indicators
    if any(t in tags_lower for t in ["crystal", "modern jewellery", "contemporary", "eleganza"]):
        return "Western"
    
    return "Western"