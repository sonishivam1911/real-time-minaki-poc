"""
Prompt Selection Node
Selects appropriate prompt based on jewelry type
"""

import logging
from langsmith import traceable
from ..state import ProductWriterState
from ..prompts.kundan_jewellery_prompt import kundan_jewelry_prompt
from ..prompts.crystal_jewellery_prompt import crystal_jewelry_prompt

logger = logging.getLogger("ProductWriter.Nodes.PromptSelection")


@traceable(name="prompt_selection_node", run_type="chain")
def prompt_selection_node(state: ProductWriterState) -> ProductWriterState:
    """
    Node: Select the appropriate prompt based on category and line
    """
    logger.info("📋 Selecting prompt template...")
    
    category = state['category'].lower()
    line = state['line'].lower()
    
    if 'jewelry set' in category or 'jewellery set' in category:
        if 'kundan' in line or 'polki' in line:
            state['selected_prompt'] = kundan_jewelry_prompt
            logger.info("✅ Selected: kundan_jewelry_prompt")
        elif 'american diamond' in line or 'diamond' in line or 'crystal' in line or 'ad' in line:
            state['selected_prompt'] = crystal_jewelry_prompt
            logger.info("✅ Selected: crystal_jewelry_prompt")
        else:
            state['selected_prompt'] = crystal_jewelry_prompt
            logger.info("✅ Selected: crystal_jewelry_prompt (fallback)")
    else:
        state['selected_prompt'] = crystal_jewelry_prompt
        logger.info("✅ Selected: crystal_jewelry_prompt (default)")

    return state