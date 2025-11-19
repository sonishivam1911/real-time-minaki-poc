"""
Pack Mapper - Determines multipack set and pack contains from components
"""

from typing import List, Optional


def get_multipack_set(cf_components: Optional[List[str]]) -> str:
    """
    Get multipack set value from Zakya components
    
    Args:
        cf_components: List of components from Zakya (e.g., ["Necklace", "Earrings"])
    
    Returns:
        Nykaa multipack value ("Single", "Pack of 2", etc.)
    """
    if not cf_components or not isinstance(cf_components, list):
        return "Single"
    
    count = len(cf_components)
    
    if count == 0:
        return "Single"
    elif count == 1:
        return "Single"
    else:
        return f"Pack of {count}"


def get_pack_contains(cf_components: Optional[List[str]]) -> str:
    """
    Generate pack contains description with velvet box
    
    Args:
        cf_components: List of components from Zakya
    
    Returns:
        Clean pack contains description
    """
    # Import here to avoid circular imports
    from .config import clean_pack_contains
    
    if not cf_components or not isinstance(cf_components, list) or len(cf_components) == 0:
        return "1 Piece with Velvet Box"
    
    count = len(cf_components)
    
    if count == 1:
        item = cf_components[0]
        
        # Special case for earrings (sold as pair)
        if item.lower() in ["earrings", "earring", "jhumkas", "jhumka", "studs", "stud"]:
            return "1 Pair of Earrings with Velvet Box"
        
        # Single item
        return f"1 {item} with Velvet Box"
    
    # Multiple items
    if count == 2:
        items_str = f"{cf_components[0]} and {cf_components[1]}"
    else:
        # More than 2: "Item1, Item2 and Item3"
        items_str = ", ".join(cf_components[:-1]) + " and " + cf_components[-1]
    
    pack_description = f"{count} Pieces: {items_str} with Velvet Box"
    
    # Clean the description to remove HTML entities and special characters
    return clean_pack_contains(pack_description)


def parse_components_from_description(description_html: str) -> Optional[List[str]]:
    """
    Parse components from description HTML (fallback when Zakya missing)
    
    Args:
        description_html: Product description HTML
    
    Returns:
        List of component names or None
    """
    if not description_html:
        return None
    
    import re
    
    description_lower = description_html.lower()
    
    # Look for "Item(s):" line
    items_match = re.search(r'item\(s\):\s*([^<\n]+)', description_lower, re.IGNORECASE)
    if items_match:
        items_text = items_match.group(1).strip()
        # Split by "and" or ","
        items = re.split(r'\s+and\s+|,\s*', items_text)
        return [item.strip().title() for item in items if item.strip()]
    
    # Look for common patterns like "necklace and earrings"
    if "necklace and earrings" in description_lower or "necklace & earrings" in description_lower:
        return ["Necklace", "Earrings"]
    
    if "set" in description_lower:
        # Try to detect what kind of set
        if "earring" in description_lower:
            return ["Necklace", "Earrings"]  # Common jewelry set
    
    return None