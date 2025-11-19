"""
Nykaa Rewriter Agent Module
AI-powered product name and description generation for Nykaa marketplace
Uses historical Indian queen names and web search context for authentic content
"""

from .config import (
    HISTORICAL_QUEENS,
    PRICE_THRESHOLDS,
    NYKAA_CONSTRAINTS,
    PRODUCT_TYPES,
    MATERIAL_KEYWORDS,
    OCCASION_KEYWORDS,
)
from .material_resolver import resolve_material_gid, batch_resolve_material_gids
from .ean_generator import generate_ean13, validate_ean13, batch_generate_ean13
from .search_utils import generate_search_terms, fetch_search_context, search_duckduckgo
from .nykaa_rewriter_prompt import get_queen_names_for_price
from .validator import (
    validate_product_name,
    validate_product_description,
    calculate_quality_score,
    should_flag_for_manual_review,
)

__all__ = [
    # Config
    "HISTORICAL_QUEENS",
    "PRICE_THRESHOLDS",
    "NYKAA_CONSTRAINTS",
    "PRODUCT_TYPES",
    "MATERIAL_KEYWORDS",
    "OCCASION_KEYWORDS",
    # Material Resolver
    "resolve_material_gid",
    "batch_resolve_material_gids",
    # EAN Generator
    "generate_ean13",
    "validate_ean13",
    "batch_generate_ean13",
    # Search
    "generate_search_terms",
    "fetch_search_context",
    "search_duckduckgo",
    # Prompts
    "get_queen_names_for_price",
    # Validation
    "validate_product_name",
    "validate_product_description",
    "calculate_quality_score",
    "should_flag_for_manual_review",
]

__version__ = "1.0.0"
__author__ = "Minakii AI Team"
__description__ = "Nykaa Rewriter Agent - Product name and description generation using AI"
