from typing import TypedDict, List, Dict, Optional, Annotated
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langsmith import traceable
from dotenv import load_dotenv
import pandas as pd
import json
import logging
import os
import time
from services.agent.keyword_filter import KeywordFilter
from services.agent.duplicate_checker import DuplicateNameChecker
from services.shopify.product import ShopifyProductService
from agent.product_writer.kundan_jewellery_prompt import kundan_jewelry_prompt
from agent.product_writer.crystal_jewellery_prompt import crystal_jewelry_prompt
from agent.output_parser import ActionParser

# Load environment variables for LangSmith tracing
load_dotenv()

logger = logging.getLogger("LangGraph Workflow")

class AgentState(TypedDict):
    """State that flows through the LangGraph workflow"""
    # Input
    product_row: Dict
    keywords_df: pd.DataFrame
    
    # Intermediate
    category: str
    line: str
    colors: str
    filtered_keywords: List[str]
    selected_prompt: str
    used_names: List[str]  # Track names already used to avoid duplicates
    image_url: Optional[str]  # First image URL for attaching to generated content
    
    # Output
    generated_content: Optional[Dict]
    duplicate_resolved: Optional[bool]  # Whether duplicates were resolved
    error: Optional[str]


@traceable(name="preprocess_node", run_type="chain")
def preprocess_node(state: AgentState) -> AgentState:
    """
    Node 1: Extract relevant product attributes
    """
    logger.info("🔧 Node 1: Preprocessing product attributes")
    
    product = state['product_row']
    logger.debug(f"Product row data: {product}")
    
    # Extract key attributes
    state['category'] = product.get('category', '')
    state['line'] = product.get('line', '')
    
    # Combine colors
    primary = product.get('primary_color', '')
    secondary = product.get('secondary_color', '')
    state['colors'] = f"{primary} {secondary}".strip()
    
    # Initialize used names list (this should be passed from outside in real usage)
    # If not provided, initialize as empty list
    if 'used_names' not in state or state['used_names'] is None:
        state['used_names'] = []
    
    # Extract image URL from product data
    image_url = None
    # Try common image field names
    for field in ['high_resolution_1', 'image_url', 'image_1', 'primary_image']:
        if field in product and product[field]:
            image_url = product[field]
            break
    
    state['image_url'] = image_url
    
    
    return state


@traceable(name="keyword_filter_node", run_type="chain")
def keyword_filter_node(state: AgentState) -> AgentState:
    """
    Node 2: Filter and rank keywords using KeywordFilter
    Supports both Kundan-Polki and American Diamond/Crystal lines
    """
    
    try:
        # Initialize keyword filter
        filter_system = KeywordFilter(state['keywords_df'])
        
        # Filter based on line
        line_lower = state['line'].lower()
        
        if 'kundan' in line_lower or 'polki' in line_lower:
            logger.info("   Using Kundan-Polki filter")
            filtered_df = filter_system.filter_for_kundan_polki(
                product_color=state['colors'],
                min_searches=1000,
                top_n=30
            )
            state['filtered_keywords'] = filtered_df['Keyword'].tolist()
        
        elif 'american diamond' in line_lower or 'crystal' in line_lower or 'ad' in line_lower:
            logger.info("   Using American Diamond/Crystal filter")
            # Extract product style from product attributes if available
            product_style = state['product_row'].get('style', None)
            filtered_df = filter_system.filter_for_american_diamond_crystal(
                product_color=state['colors'],
                product_style=product_style,
                min_searches=1000,
                top_n=30
            )
            state['filtered_keywords'] = filtered_df['Keyword'].tolist()
        
        else:
            logger.warning(f"   Line '{state['line']}' not yet supported")
            state['filtered_keywords'] = []
        
        logger.info(f"   ✅ Filtered {len(state['filtered_keywords'])} keywords")
        if state['filtered_keywords']:
            logger.info(f"   Top 5: {', '.join(state['filtered_keywords'][:5])}")
        
    except Exception as e:
        logger.error(f"   ❌ Keyword filtering error: {str(e)}")
        state['error'] = f"Keyword filtering failed: {str(e)}"
        state['filtered_keywords'] = []
        
    return state


@traceable(name="prompt_selection_node", run_type="chain")
def prompt_selection_node(state: AgentState) -> AgentState:
    """
    Node 3: Select the appropriate prompt based on category and line
    """
    
    category = state['category'].lower()
    line = state['line'].lower()
    
    # For now, only Kundan Jewelry Sets
    if 'jewelry set' in category or 'jewellery set' in category:
        if 'kundan' in line or 'polki' in line:
            state['selected_prompt'] = kundan_jewelry_prompt
            logger.info("✅ Selected: kundan_jewelry_prompt")
        elif 'american diamond' in line or 'diamond' in line or 'crystal' in line or 'ad' in line:
            state['selected_prompt'] = crystal_jewelry_prompt
            logger.info("✅ Selected: crystal_jewelry_prompt")
        else:
            # Default fallback to crystal for jewelry sets
            state['selected_prompt'] = crystal_jewelry_prompt
            logger.info("✅ Selected: crystal_jewelry_prompt (fallback)")
    else:
        # Default fallback to crystal for non-jewelry sets
        state['selected_prompt'] = crystal_jewelry_prompt
        logger.info("✅ Selected: crystal_jewelry_prompt (default)")

    return state


@traceable(name="generation_node", run_type="chain")
def generation_node(state: AgentState) -> AgentState:
    """
    Node 4: Generate content using LLM via Groq with rate limiting
    """
    logger.info("🤖 Node 4: Generating content with Groq LLM")
    
    # Add delay to handle rate limiting
    logger.info("⏱️  Adding 10-second delay to handle Groq rate limits...")
    time.sleep(10)
    
    try:
        # Try to initialize Groq LLM with primary model
        try:
            logger.info(" Attempting to use llama3-8b-8192 model...")
            llm = ChatGroq(
                model="llama-3.1-8b-instant",  
                temperature=0.7,
                max_tokens=2000,
                groq_api_key=os.environ.get("GROQ_API_KEY")
            )
        except Exception as model_error:
            # Fallback to Mixtral if Llama has issues
            logger.warning(f"   Error using primary model: {str(model_error)}. Falling back to mixtral-8x7b...")
            llm = ChatGroq(
                model="llama-3.1-8b-instant",  # Fallback to Mixtral if Llama has issues
                temperature=0.7,
                max_tokens=2000,
                groq_api_key=os.environ.get("GROQ_API_KEY")
            )
        
        product = state['product_row']
        
        # Create a dictionary with all the parameters we want to pass to the prompt
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
            "name_meaning": '',  # Not in CSV, leave empty
            "keywords": ', '.join(state['filtered_keywords']),
            "used_names": ', '.join(state['used_names']) if state['used_names'] else 'None'
        }
    
        
        # Format the prompt with product details
        try:
            filled_prompt = state['selected_prompt'].format(**prompt_params)
        except KeyError as e:
            print(f"   ❌ Error formatting prompt: {str(e)}")
            # Attempt a fix by treating the selected_prompt as plain text with a .format_messages() method
            if hasattr(state['selected_prompt'], 'format_messages'):
                messages = state['selected_prompt'].format_messages(**prompt_params)
                filled_prompt = messages[0]
                logger.info("   Successfully formatted prompt as messages")
            else:
                raise
        
        # Add retry logic for rate limiting
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                logger.info(f"   🚀 Making API call (attempt {retry_count + 1}/{max_retries})...")
                response = llm.invoke(filled_prompt)
                content_text = response.content.strip()
                break  # Success, exit retry loop
                
            except Exception as api_error:
                error_str = str(api_error).lower()
                if "429" in error_str or "rate limit" in error_str or "too many requests" in error_str:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 15 * retry_count  # Exponential backoff: 15s, 30s, 45s
                        logger.warning(f"   ⚠️  Rate limited! Waiting {wait_time}s before retry {retry_count + 1}/{max_retries}...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"   ❌ Max retries reached for rate limiting")
                        raise api_error
                else:
                    # Non-rate-limit error, don't retry
                    logger.error(f"   ❌ Non-rate-limit API error: {str(api_error)}")
                    raise api_error
        
        # Use ActionParser for robust JSON handling
        parser = ActionParser(use_json_repair=True)
        
        # Parse and validate the response
        logger.info("   Parsing response with ActionParser...")
        parsed_action = parser.parse_llm_output(content_text)
        
        # Extract content from parsed action
        if parsed_action and isinstance(parsed_action, dict) and 'action_input' in parsed_action:
            state['generated_content'] = parsed_action.get('action_input', {})
            
            # Attach image URL to generated content
            if state.get('image_url'):
                state['generated_content']['image_url'] = state['image_url']
                logger.info(f"   ✅ Image attached to generated content")
            
            logger.info("   ✅ Content generated and parsed successfully")
            logger.info(f"   Title: {state['generated_content'].get('title', 'N/A')}")
            
            # Simply track the generated name for future reference
            if state['generated_content'].get('title'):
                generated_title = state['generated_content']['title']
                title_name = generated_title.replace(' Jewellery Set', '').replace(' Set', '').strip()
                state['used_names'].append(title_name)
                logger.info(f"   ✅ Generated title: '{generated_title}' - Name '{title_name}' added to used names")
        else:
            # Manual fallback parsing
            logger.info("   ActionParser could not extract content, trying manual parsing...")
            
            # Remove markdown code blocks if present
            if content_text.startswith("```json"):
                content_text = content_text[7:]
            if content_text.startswith("```"):
                content_text = content_text[3:]
            if content_text.endswith("```"):
                content_text = content_text[:-3]
            
            content_text = content_text.strip()
            
            # Parse JSON
            try:
                generated_json = json.loads(content_text)
                state['generated_content'] = generated_json.get('action_input', {})
                
                # Attach image URL to generated content
                if state.get('image_url'):
                    state['generated_content']['image_url'] = state['image_url']
                    logger.info(f"   ✅ Image attached to generated content")
                
                logger.info("   ✅ Content generated successfully with manual parsing")
                logger.info(f"   Title: {state['generated_content'].get('title', 'N/A')}")
            except json.JSONDecodeError as e:
                logger.error(f"   ❌ Manual JSON parsing also failed: {str(e)}")
                state['error'] = f"Invalid JSON response: {str(e)}"
                state['generated_content'] = None
        
    except json.JSONDecodeError as e:
        logger.error(f"   ❌ JSON parsing error: {str(e)}")
        state['error'] = f"Invalid JSON response: {str(e)}"
        state['generated_content'] = None
    except Exception as e:
        logger.error(f"   ❌ Generation error: {str(e)}", exc_info=True)
        state['error'] = f"Content generation failed: {str(e)}"
        state['generated_content'] = None
    
    return state


@traceable(name="build_langgraph_workflow", run_type="chain")
def build_langgraph_workflow() -> StateGraph:
    """
    Build the complete LangGraph workflow
    """
    logger.info("🏗️  Building LangGraph workflow...")
    
    # Create workflow
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("preprocess", preprocess_node)
    workflow.add_node("keyword_filter", keyword_filter_node)
    workflow.add_node("prompt_selection", prompt_selection_node)
    workflow.add_node("generate", generation_node)
    
    # Define edges
    workflow.set_entry_point("preprocess")
    workflow.add_edge("preprocess", "keyword_filter")
    workflow.add_edge("keyword_filter", "prompt_selection")
    workflow.add_edge("prompt_selection", "generate")
    workflow.add_edge("generate", END)
    
    logger.info("✅ Workflow built successfully")
    
    return workflow.compile()
