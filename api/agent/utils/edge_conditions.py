"""
Edge Condition Functions
Conditional logic for workflow routing
"""

import logging
from ..product_writer.state import ProductWriterState

logger = logging.getLogger("ProductWriter.Utils.EdgeConditions")


def should_retry_search(state: ProductWriterState) -> str:
    """
    Decide whether to retry search or proceed to parsing
    
    Returns:
        - "name_parser": Reflection passed, extract names
        - "serper_search": Reflection failed but has suggested_search_term (skip generator, use suggestion directly)
        - "search_query_generator": Reflection failed, need to generate new query
        - "name_parser": Max retries reached, attempt name parsing anyway (better than nothing)
    """
    max_retries = 3
    
    # Check for errors
    if state.get("error"):
        logger.error(f"❌ Error in pipeline: {state['error']}")
        logger.info("→ Proceeding to name_parser despite error (salvage attempt)")
        return "name_parser"
    
    # Check if reflection passed
    if state.get("reflection_passed"):
        logger.info("→ Reflection passed, proceeding to name_parser")
        return "name_parser"
    
    # Check retry count
    retry_count = state.get("retry_count", 0)
    if retry_count >= max_retries:
        logger.warning(f"❌ Max retries reached ({max_retries}), proceeding to name_parser anyway")
        logger.info("→ Attempting name extraction with partial results")
        return "name_parser"
    
    # Reflection failed - check if we have a suggested search term from reflection node
    current_search_query = state.get("search_query", "")
    if current_search_query:
        logger.info(f"→ Reflection failed but has suggested term, skipping generator")
        logger.info(f"→ Using updated query directly in serper_search: '{current_search_query}'")
        return "serper_search"
    
    # No suggestion available - generate new query
    logger.info(f"→ Reflection failed, retry {retry_count + 1}/{max_retries} - generating new query")
    return "search_query_generator"