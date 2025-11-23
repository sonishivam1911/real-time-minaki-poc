"""
Reflection Node
Validates if we have enough names from search results
"""

import logging
import time
from langsmith import traceable
from ..state import ProductWriterState
from ..llm import llm
from ..prompts.name_reflection_prompt import reflection_prompt
from agent.output_parser import ActionParser

logger = logging.getLogger("ProductWriter.Nodes.Reflection")


@traceable(name="reflection_node", run_type="chain")
def reflection_node(state: ProductWriterState) -> ProductWriterState:
    """
    Validate we have enough names for all products
    """
    logger.info("🤔 Reflecting on search results quality...")
    product = state['product_row']
    
    # Rate limiting
    time.sleep(8)
    
    try:
        search_results = state.get("search_results")
        required_names = state.get("required_names", 10)
        
        if not search_results:
            state["reflection_passed"] = False
            state["error"] = "No search results"
            logger.error("❌ No search results to reflect on")
            return state
        
        prompt_params = {
            "category": product.get('category', ''),
            "jewelry_line": product.get('line', ''),
            "finish": product.get('finish', ''),
            "work": product.get('work', ''),
            "components": product.get('components', ''),
            "finding": product.get('finding', ''),
            "primary_color": product.get('primary_color', ''),
            "secondary_color": product.get('secondary_color', ''),
            "occasions": product.get('occasions', ''),
            "required_names" : required_names,
            "search_results" : search_results[:3000],
        }        
        
        # Format prompt
        messages = reflection_prompt.format(
            **prompt_params  
        )
        
        # Call LLM
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # ✅ USE ActionParser
        parser = ActionParser(use_json_repair=True)
        parsed_action = parser.parse_llm_output(content)
        
        if not parsed_action or 'action_input' not in parsed_action:
            logger.error("❌ ActionParser failed to parse reflection response")
            state["reflection_passed"] = False
            state["error"] = "Failed to parse reflection response"
            return state
        
        action_input = parsed_action.get("action_input", {})
        passed = action_input.get("passed", False)
        count = action_input.get("extracted_names_count", 0)
        
        state["reflection_passed"] = passed
        state["error"] = None
        
        if not passed:
            state["retry_count"] = state.get("retry_count", 0) + 1
            
            # Extract suggested search term on failure
            suggested_search_term = action_input.get("suggested_search_term")
            if suggested_search_term:
                state["search_query"] = suggested_search_term
                logger.info(f"📝 Updated search query: {suggested_search_term}")
            
            # Log failure reason
            alignment_issue = action_input.get("alignment_issue", "Unknown reason")
            logger.warning(f"❌ Reflection FAILED - need {required_names}, found {count}")
            logger.warning(f"   Issue: {alignment_issue}")
        else:
            logger.info(f"✅ Reflection PASSED - {count}/{required_names} names available")
        
        return state
        
    except Exception as e:
        logger.error(f"❌ Reflection error: {str(e)}")
        state["reflection_passed"] = False
        state["error"] = f"Reflection error: {str(e)}"
        return state