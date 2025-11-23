"""
Serper Search Node
Calls Serper API with generated query
"""

import logging
from langsmith import traceable
from ..state import ProductWriterState
# Adjust import path based on your project structure
from utils.serper_search import search_serper

logger = logging.getLogger("ProductWriter.Nodes.SerperSearch")


@traceable(name="serper_search_node", run_type="chain")
def serper_search_node(state: ProductWriterState) -> ProductWriterState:
    """
    Call Serper API with generated query
    """
    logger.info("🌐 Calling Serper API...")
    
    try:
        search_query = state.get("search_query")
        
        if not search_query:
            state["error"] = "No search query provided"
            logger.error("❌ No search query in state")
            return state
        
        logger.info(f"   Query: {search_query}")
        
        # Call Serper
        search_results = search_serper(search_query)
        
        if not search_results:
            logger.warning("⚠️  No search results returned")
            state["error"] = "No search results found"
            state["search_results"] = None
            return state
        
        logger.info(f"✅ Got {len(search_results)} characters of results")
        
        # Update state
        state["search_results"] = search_results
        state["error"] = None
        
        return state
        
    except Exception as e:
        logger.error(f"❌ Serper search failed: {str(e)}", exc_info=True)
        state["error"] = f"Serper search failed: {str(e)}"
        state["search_results"] = None
        return state