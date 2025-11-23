from typing import TypedDict, List, Dict, Optional
import pandas as pd


class ProductWriterState(TypedDict):
    """State that flows through the LangGraph workflow"""
    
    # ============= INPUT =============
    product_row: Dict
    keywords_df: pd.DataFrame
    
    # ============= NAME GENERATION =============
    jewelry_type: Optional[str]
    primary_color: Optional[str]
    search_query: Optional[str]
    search_results: Optional[str]
    name_pool: Optional[List[Dict]]  # [{"name": "X", "meaning": "Y"}]
    required_names: Optional[int]
    reflection_passed: Optional[bool]
    retry_count: Optional[int]
    
    # ============= INTERMEDIATE =============
    category: str
    line: str
    colors: str
    filtered_keywords: List[str]
    selected_prompt: str
    used_names: List[str]
    image_url: Optional[str]
    
    # ============= OUTPUT =============
    generated_content: Optional[Dict]
    duplicate_resolved: Optional[bool]
    error: Optional[str]