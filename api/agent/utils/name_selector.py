"""
Name Selection Utility
Selects unique names from the pool
"""

import logging
from typing import Dict
from ..product_writer.state import ProductWriterState

logger = logging.getLogger("ProductWriter.Utils.NameSelector")


def select_unique_name_from_pool(state: ProductWriterState) -> Dict:
    """
    Select an unused name from the pool
    
    Args:
        state: Current workflow state
    
    Returns:
        Dict with {"name": "X", "meaning": "Y"}
    """
    name_pool = state.get("name_pool", [])
    used_names = state.get("used_names", [])
    
    if not name_pool:
        logger.warning("⚠️  No name pool available, returning empty name")
        return {"name": "", "meaning": ""}
    
    # Validate name_pool contains dictionaries
    if not all(isinstance(n, dict) for n in name_pool):
        logger.error(f"❌ Invalid name_pool format: expected list of dicts, got {[type(n).__name__ for n in name_pool[:3]]}")
        return {"name": "", "meaning": ""}
    
    # Normalize used names for comparison
    used_names_lower = [name.lower() for name in used_names]
    
    # Filter out used names
    available_names = [
        n for n in name_pool 
        if n.get("name", "").lower() not in used_names_lower
    ]
    
    if not available_names:
        logger.warning("⚠️  Name pool exhausted! Reusing from full pool")
        available_names = name_pool
    
    # Select first available
    selected = available_names[0]
    logger.info(f"✅ Selected name: {selected.get('name', '')} ({selected.get('meaning', '')})")
    
    return selected