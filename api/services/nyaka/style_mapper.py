"""
Style Mapper - Maps Zakya work/collection to Nykaa styles
"""

from typing import Optional


# Zakya cf_work → Nykaa Styles of Jewellery
# Zakya cf_work → Nykaa Styles of Jewellery
WORK_TO_STYLE = {
    "Colored Stones": "Coloured Stone",  # British spelling for Nykaa
    "Kundan": "Kundan",
    "Meenakari": "Meenakari",
    "Minakari": "Minakari",
    "Pearl": "Pearl",
    "Plain": "Minimal",
    "Oxidized": "Oxidised",  # British spelling
    "Oxidised": "Oxidised",
    "Temple": "Temple",
    "Diamond Look": "Contemporary",
    "Statement": "Statement",
    "Minimal": "Minimal",
    "Essential": "Essential",
    "Dramatic": "Dramatic",
    "Fusion": "Fusion",
    "Resort": "Resort",
    "Traditional": "Temple",  # ✅ ADD THIS: Map Traditional work → Temple style
    "Stones": "Stones",  # ✅ ADD THIS
    "White Stones": "White Stones",  # ✅ ADD THIS
    "Coloured Stone": "Coloured Stone",  # ✅ ADD THIS
}

# Zakya cf_collection → Nykaa Styles of Jewellery
COLLECTION_TO_STYLE = {
    "Eleganza": "Contemporary",
    "Kundan": "Kundan",
    "Polki": "Kundan",  # ✅ FIXED: Polki jewelry uses Kundan style
    "Temple": "Temple",
    "Crystal": "Contemporary",
    "Silver": "Sterling Silver",
    "Oxidised": "Oxidised",
    "Pearl": "Pearl",
    "Contemporary": "Contemporary",
    "Traditional": "Temple",  # ✅ FIXED: Map Traditional collection → Temple style
    "Meenakari": "Meenakari",
    "Minakari": "Minakari",
}


def detect_style_from_text(text: str) -> Optional[str]:
    """
    Detect jewelry style from product name or description
    
    Args:
        text: Product name or description
        
    Returns:
        Detected style or None
    """
    if not text:
        return None
    
    text_lower = text.lower()
    
    # Priority order matters!
    if "kundan" in text_lower or "polki" in text_lower:
        return "Kundan"
    elif "meenakari" in text_lower or "minakari" in text_lower:
        return "Meenakari"
    elif "temple" in text_lower:
        return "Temple"
    elif "oxidised" in text_lower or "oxidized" in text_lower:
        return "Oxidised"
    elif "pearl" in text_lower:
        return "Pearl"
    elif "stone" in text_lower or "stones" in text_lower:
        return "Stones"
    
    return None

def get_style(zakya_work: Optional[str], zakya_collection: Optional[str]) -> str:
    """
    Get style of jewellery with priority hierarchy
    
    Args:
        zakya_work: Value from Zakya cf_work
        zakya_collection: Value from Zakya cf_collection
    
    Returns:
        Nykaa Styles of Jewellery value
    """
    # Priority 1: Map from cf_work (most specific)
    if zakya_work:
        # Exact match
        if zakya_work in WORK_TO_STYLE:
            return WORK_TO_STYLE[zakya_work]
        
        # Case-insensitive match
        for key, value in WORK_TO_STYLE.items():
            if key.lower() == zakya_work.lower():
                return value
    
    # Priority 2: Map from cf_collection
    if zakya_collection:
        # Exact match
        if zakya_collection in COLLECTION_TO_STYLE:
            return COLLECTION_TO_STYLE[zakya_collection]
        
        # Case-insensitive match
        for key, value in COLLECTION_TO_STYLE.items():
            if key.lower() == zakya_collection.lower():
                return value
    
    # Default
    return "Contemporary"


def get_style_from_tags(tags: list) -> Optional[str]:
    """
    Extract style from Shopify tags (fallback)
    
    Args:
        tags: List of product tags
    
    Returns:
        Style value or None
    """
    if not tags:
        return None
    
    tags_lower = [t.lower() for t in tags]
    
    # Check tags for style indicators
    if "kundan" in tags_lower:
        return "Kundan"
    if "polki" in tags_lower:
        return "Traditional"
    if "crystal" in tags_lower or "modern jewellery" in tags_lower:
        return "Contemporary"
    if "pearl" in tags_lower:
        return "Pearl"
    if "oxidised" in tags_lower or "oxidized" in tags_lower:
        return "Oxidised"
    if "temple" in tags_lower:
        return "Temple"
    
    return None