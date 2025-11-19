"""
Plating Mapper - Maps Zakya finish to Nykaa plating values
Supports multiple platings (e.g., "18K Gold, Rhodium")
"""

from typing import List, Optional


# Zakya finish → Nykaa plating(s)
FINISH_TO_PLATING = {
    "White Gold Plated": ["White Gold"],
    "Gold Plated": ["18K Gold"],
    "18K Gold Plated": ["18K Gold"],
    "22K Gold Plated": ["22K Gold"],
    "24K Gold Plated": ["24K Gold"],
    "Antique Gold": ["Antique Gold"],
    "Antique Gold Plated": ["Antique Gold"],
    "Rhodium Plated": ["Rhodium"],
    "Rhodium polished in Platinum finish": ["Rhodium", "Platinum"],
    "Silver Plated": ["Silver"],
    "Rose Gold Plated": ["Rose Gold"],
    "Black Oxidized": ["Black"],
    "Oxidized": ["Silver"],  # Oxidized usually silver
    "Brass": ["No Plating"],  # Raw brass, no plating
    "Copper": ["No Plating"],  # Raw copper, no plating
}


def parse_plating_from_text(text: str) -> List[str]:
    """
    Parse plating from description or finish text
    
    Args:
        text: Description or finish text
    
    Returns:
        List of plating values (empty if none found)
    """
    if not text:
        return []
    
    text_lower = text.lower()
    platings = []
    
    # Check for each plating type in priority order
    if "rhodium" in text_lower:
        platings.append("Rhodium")
    
    if "platinum" in text_lower:
        platings.append("Platinum")
    
    # Check for white gold before general gold
    if "white gold" in text_lower:
        if "White Gold" not in platings:  # Avoid duplicates
            platings.append("White Gold")
    
    # Check for rose gold before general gold
    if "rose gold" in text_lower:
        if "Rose Gold" not in platings:
            platings.append("Rose Gold")
    
    # Check for specific karat gold
    if "22k gold" in text_lower or "22 k gold" in text_lower:
        if "22K Gold" not in platings:
            platings.append("22K Gold")
    
    if "24k gold" in text_lower or "24 k gold" in text_lower:
        if "24K Gold" not in platings:
            platings.append("24K Gold")
    
    if "18k gold" in text_lower or "18 k gold" in text_lower:
        if "18K Gold" not in platings:
            platings.append("18K Gold")
    
    # Generic gold plated (only if no specific karat found)
    if "gold plated" in text_lower or "gold polish" in text_lower:
        if not any("Gold" in p for p in platings):
            platings.append("18K Gold")  # Default to 18K
    
    if "silver plated" in text_lower or "silver polish" in text_lower:
        if "Silver" not in platings:
            platings.append("Silver")
    
    if "antique gold" in text_lower:
        if "Antique Gold" not in platings:
            platings.append("Antique Gold")
    
    if "black" in text_lower or "oxidized" in text_lower or "oxidised" in text_lower:
        # Oxidized jewelry usually has silver base
        if not platings:
            platings.append("Silver")
    
    return platings


def get_plating(zakya_finish: Optional[str], description_html: Optional[str]) -> str:
    """
    Get plating value(s) with priority hierarchy
    
    Args:
        zakya_finish: Finish value from Zakya cf_finish
        description_html: Product description HTML
    
    Returns:
        Comma-separated plating values or default "18K Gold"
    """
    platings = []
    
    # Priority 1: Zakya cf_finish (exact match)
    if zakya_finish and zakya_finish in FINISH_TO_PLATING:
        platings = FINISH_TO_PLATING[zakya_finish].copy()
    
    # Priority 2: Parse Zakya finish if not exact match
    if not platings and zakya_finish:
        platings = parse_plating_from_text(zakya_finish)
    
    # Priority 3: Parse from description
    if not platings and description_html:
        # Look for "Finish:" line first
        import re
        finish_match = re.search(r'Finish:\s*([^<\n]+)', description_html, re.IGNORECASE)
        if finish_match:
            finish_text = finish_match.group(1).strip()
            platings = parse_plating_from_text(finish_text)
        
        # If still no platings, parse entire description
        if not platings:
            platings = parse_plating_from_text(description_html)
    
    # Default: 18K Gold
    if not platings:
        platings = ["18K Gold"]
    
    # Remove duplicates while preserving order
    seen = set()
    unique_platings = []
    for p in platings:
        if p not in seen:
            seen.add(p)
            unique_platings.append(p)
    
    # Return comma-separated
    return ", ".join(unique_platings)