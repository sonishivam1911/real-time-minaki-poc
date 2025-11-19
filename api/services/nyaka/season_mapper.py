"""
Season Mapper - Generates current season dynamically
"""

from datetime import datetime


def get_current_season() -> str:
    """
    Get current season based on current date
    
    Returns:
        Season string in Nykaa format (e.g., "Autumn/Winter 2025")
    """
    now = datetime.now()
    month = now.month
    year = now.year
    
    # Determine season based on month
    # Spring/Summer: March (3) to August (8)
    # Autumn/Winter: September (9) to February (2)
    
    if month in [3, 4, 5, 6, 7, 8]:
        # Spring/Summer season
        season = f"Spring/Summer {year}"
    else:
        # Autumn/Winter season
        # If January or February, use current year
        # If September onwards, use current year
        season = f"Autumn/Winter {year}"
    
    return season


def get_season_from_tags(tags: list) -> str:
    """
    Get season from tags if specified (fallback)
    
    Args:
        tags: List of product tags
    
    Returns:
        Season string
    """
    if not tags:
        return get_current_season()
    
    tags_lower = [t.lower() for t in tags]
    
    # Check for season indicators in tags
    for tag in tags_lower:
        if "spring" in tag or "summer" in tag:
            year = datetime.now().year
            return f"Spring/Summer {year}"
        if "autumn" in tag or "winter" in tag or "fall" in tag:
            year = datetime.now().year
            return f"Autumn/Winter {year}"
        if "core" in tag:
            year = datetime.now().year
            return f"CORE {year}"
    
    # Default to current season
    return get_current_season()