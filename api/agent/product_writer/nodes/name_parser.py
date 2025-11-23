"""
Name Parser Node
Extracts name pool from validated search results
"""

import logging
import time
from langsmith import traceable
from ..state import ProductWriterState
from ..llm import llm
from ..prompts.name_parser_prompt import name_parser_prompt
from agent.output_parser import ActionParser

logger = logging.getLogger("ProductWriter.Nodes.NameParser")


@traceable(name="name_parser_node", run_type="chain")
def name_parser_node(state: ProductWriterState) -> ProductWriterState:
    """
    Extract name pool from search results
    """
    logger.info("📝 Parsing names from search results...")
    
    # Rate limiting
    time.sleep(8)
    
    try:
        search_results = state.get("search_results")
        
        # Format prompt
        messages = name_parser_prompt.format_messages(
            search_results=search_results[:4000]
        )
        
        # Call LLM
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # ✅ USE ActionParser
        parser = ActionParser(use_json_repair=True)
        parsed_action = parser.parse_llm_output(content)
        
        print(f"Parsed Action: {parsed_action}\n")
        
        # Check if action_input is empty dict or missing
        if not parsed_action or not isinstance(parsed_action.get('action_input'), dict):
            logger.error(f"❌ ActionParser failed to parse names - invalid action_input: {parsed_action}")
            state["error"] = "Failed to parse names from response"
            state["reflection_passed"] = False
            return state
        
        action_input = parsed_action.get("action_input", {})
        name_pool = action_input.get("names", [])
        
        # Validate name_pool is a list
        if not isinstance(name_pool, list):
            logger.error(f"❌ Expected names to be a list, got {type(name_pool).__name__}")
            state["error"] = f"Invalid name_pool format: expected list, got {type(name_pool).__name__}"
            state["reflection_passed"] = False
            return state
        
        if len(name_pool) < 5:
            logger.warning(f"⚠️  Only extracted {len(name_pool)} names")
            state["error"] = f"Only extracted {len(name_pool)} names"
            state["reflection_passed"] = False
            return state
        
        logger.info(f"✅ Extracted {len(name_pool)} names to pool")
        if name_pool and isinstance(name_pool[0], dict):
            logger.info(f"   Sample: {name_pool[0].get('name', 'N/A')} ({name_pool[0].get('meaning', 'N/A')})")
        elif name_pool:
            logger.info(f"   Sample: {name_pool[0]}")
        
        # Update state
        state["name_pool"] = name_pool
        state["error"] = None
        
        return state
        
    except Exception as e:
        logger.error(f"❌ Parser error: {str(e)}")
        state["error"] = f"Parser error: {str(e)}"
        state["reflection_passed"] = False
        return state