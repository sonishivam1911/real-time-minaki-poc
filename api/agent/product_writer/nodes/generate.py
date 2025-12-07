"""
Generate Node
Generates product content using LLM with selected name
"""

import logging
import time
from langsmith import traceable
from ..state import ProductWriterState
from ..llm import llm
from ...utils.name_selector import select_unique_name_from_pool
from agent.output_parser import ActionParser  # ✅ ALREADY USING IT

logger = logging.getLogger("ProductWriter.Nodes.Generate")


@traceable(name="generation_node", run_type="chain")
def generation_node(state: ProductWriterState) -> ProductWriterState:
    """
    Node: Generate content using LLM with name from pool
    """
    logger.info("🤖 Generating content with Groq LLM...")
    
    # Rate limiting
    logger.info("⏱️  Adding 20-second delay to handle Groq rate limits...")
    time.sleep(20)
    
    try:
        product = state['product_row']
        logger.info(f"   Generating for Product ID: {product}")
        
        # Select unique name from pool
        selected_name = select_unique_name_from_pool(state)
        
        # Create prompt parameters
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
            "necklace_design" : product.get('necklace_design', ''),
            "bracelet_design" : product.get('bracelet_design', ''),
            "earring_design" : product.get('earring_design', ''),
            "ring_design" : product.get('ring_design', ''),
            "name_meaning": selected_name.get("meaning", ""),
            "suggested_name": selected_name.get("name", ""),
            "keywords": ', '.join(state['filtered_keywords']),
            "used_names": ', '.join(state['used_names']) if state['used_names'] else 'None'
        }
        
        # Format prompt
        try:
            filled_prompt = state['selected_prompt'].format(**prompt_params)
        except KeyError as e:
            logger.error(f"❌ Error formatting prompt: {str(e)}")
            if hasattr(state['selected_prompt'], 'format_messages'):
                messages = state['selected_prompt'].format_messages(**prompt_params)
                filled_prompt = messages[0]
                logger.info("   Successfully formatted prompt as messages")
            else:
                raise
        
        # Retry logic for rate limiting
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                logger.info(f"   🚀 Making API call (attempt {retry_count + 1}/{max_retries})...")
                response = llm.invoke(filled_prompt)
                content_text = response.content.strip()
                break
                
            except Exception as api_error:
                error_str = str(api_error).lower()
                if "429" in error_str or "rate limit" in error_str or "too many requests" in error_str:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 15 * retry_count
                        logger.warning(f"   ⚠️  Rate limited! Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"   ❌ Max retries reached")
                        raise api_error
                else:
                    logger.error(f"   ❌ Non-rate-limit API error: {str(api_error)}")
                    raise api_error
        
        # ✅ USE ActionParser ONLY - NO MANUAL PARSING
        parser = ActionParser(use_json_repair=True)
        logger.info("   Parsing response with ActionParser...")
        parsed_action = parser.parse_llm_output(content_text)
        
        if parsed_action and isinstance(parsed_action, dict) and 'action_input' in parsed_action:
            action_input = parsed_action.get('action_input', {})
            
            # Validate action_input is a dictionary
            if not isinstance(action_input, dict):
                logger.error(f"❌ action_input is not a dict, got {type(action_input).__name__}: {action_input}")
                state['error'] = f"Invalid action_input format: expected dict, got {type(action_input).__name__}"
                state['generated_content'] = None
                return state
            
            state['generated_content'] = action_input
            
            # Attach image URL
            if state.get('image_url'):
                state['generated_content']['image_url'] = state['image_url']
            
            logger.info("✅ Content generated and parsed successfully")
            logger.info(f"   Title: {state['generated_content'].get('title', 'N/A')}")
            
            # Track generated name
            if state['generated_content'].get('title'):
                generated_title = state['generated_content']['title']
                title_name = generated_title.replace(' Jewellery Set', '').replace(' Set', '').strip()
                state['used_names'].append(title_name)
                logger.info(f"   ✅ Name '{title_name}' added to used names")
        else:
            logger.error("   ❌ ActionParser failed to extract content")
            state['error'] = "ActionParser failed to extract valid content"
            state['generated_content'] = None
        
    except Exception as e:
        logger.error(f"❌ Generation error: {str(e)}", exc_info=True)
        state['error'] = f"Content generation failed: {str(e)}"
        state['generated_content'] = None
    
    return state