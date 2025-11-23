"""
Search Query Generator Node
Generates creative search queries for name discovery
"""

import logging
import time
from langsmith import traceable
from ..state import ProductWriterState
from ..llm import llm
from ..prompts.name_search_query_prompt import search_query_prompt
from agent.output_parser import ActionParser

logger = logging.getLogger("ProductWriter.Nodes.SearchQueryGenerator")


@traceable(name="search_query_generator_node", run_type="chain")
def search_query_generator_node(state: ProductWriterState) -> ProductWriterState:
    """
    Generate optimal search query based on product attributes
    """
    logger.info("🔍 Generating search query...")
    
    # Rate limiting
    time.sleep(5)
    
    try:
        product_input = state["product_row"]
        
        # Extract needed fields
        line = product_input.get("jewelry_line") or product_input.get("line", "")
        jewelry_type = "crystal_ad" if "crystal" in line.lower() or "american diamond" in line.lower() or "ad" in line.lower() else "kundan"
        primary_color = product_input.get("primary_color", "")
        secondary_color = product_input.get("secondary_color", "")
        category = product_input.get("category", "")
        
        # Format prompt with input variables
        messages = search_query_prompt.format_messages(
            jewelry_type=jewelry_type,
            primary_color=primary_color,
            secondary_color=secondary_color,
            category=category
        )
        
        # Call LLM
        response = llm.invoke(messages)
        search_query = response.content.strip()
        
        parser = ActionParser(use_json_repair=True)
        parsed_action = parser.parse_llm_output(search_query)
        
        if not parsed_action or 'action_input' not in parsed_action:
            logger.error("❌ ActionParser failed to parse search query")
            state["error"] = "Failed to parse search query from response"
            state["search_query"] = None
            return state
        
        action_input = parsed_action.get("action_input", {})
        search_query = action_input.get("query", "").strip()

        logger.info(f"✅ Generated query: '{search_query}'")
        
        # Update state
        state["jewelry_type"] = jewelry_type
        state["primary_color"] = primary_color
        state["search_query"] = search_query
        state["retry_count"] = state.get("retry_count", 0)
        state["error"] = None
        
        return state
        
    except Exception as e:
        logger.error(f"❌ Error generating search query: {str(e)}", exc_info=True)
        state["error"] = f"Search query generation failed: {str(e)}"
        state["search_query"] = None
        return state