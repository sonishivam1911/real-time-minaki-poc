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
from services.agent.keyword_filter import KeywordFilter
from services.agent.visual_context_service import MinakiVisualContextService
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
    image_description: Optional[str]  # Concise image description for LLM
    visual_context: Optional[Dict]  # Full visual analysis data
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
    
    # Extract key attributes
    state['category'] = product.get('category', '')
    state['line'] = product.get('line', '')
    
    # Combine colors
    primary = product.get('primary_color', '')
    secondary = product.get('secondary_color', '')
    state['colors'] = f"{primary} {secondary}".strip()
    
    # Initialize image_url
    state['image_url'] = None
    
    logger.info(f"   Category: {state['category']}")
    logger.info(f"   Line: {state['line']}")
    logger.info(f"   Colors: {state['colors']}")
    
    return state


@traceable(name="image_analysis_node", run_type="chain")
def image_analysis_node(state: AgentState) -> AgentState:
    """
    Node 2: Analyze product images using Minaki Image RAG
    """
    logger.info("🖼️  Node 2: Analyzing product images")
    
    try:
        # Initialize Visual Context Service
        visual_service = MinakiVisualContextService()
        
        # Extract image URLs from product data
        print(f" Product row keys: {list(state['product_row'].keys())}")
        print(f" high_resolution_1 value: {state['product_row'].get('high_resolution_1', 'NOT FOUND')}")
        image_urls = visual_service.extract_image_urls_from_csv_row(state['product_row'])
        
        if not image_urls:
            logger.warning("   No image URLs found in product data")
            state['image_description'] = "No images available for analysis."
            state['visual_context'] = {}
            state['image_url'] = None
            return state
        
        # Analyze the first available image
        first_image_url = image_urls[0]
        state['image_url'] = first_image_url  # Store image URL for attaching to generated content
        logger.info(f"   Analyzing image: {first_image_url[:100]}...")
        
        # Create visual context using multimodal LLM
        visual_context = visual_service.create_visual_context(first_image_url)
        print(f"Visual context: {visual_context}")
        
        if 'error' in visual_context:
            logger.warning(f"   Image analysis failed: {visual_context['error']}")
            state['image_description'] = "Image analysis unavailable."
            state['visual_context'] = {}
        else:
            # Get token-efficient description
            image_description = visual_context.get('token_efficient_description', 'Image analysis completed.')
            state['image_description'] = image_description
            state['visual_context'] = visual_context
            
            analysis = visual_context.get('analysis', {})
            logger.info(f"   ✅ Image analyzed - Collection: {analysis.get('suggested_collection', 'unknown')}")
            logger.info(f"   Style: {analysis.get('style_aesthetic', 'unknown')}")
            logger.info(f"   Complexity: {analysis.get('complexity_level', 'unknown')}")
            logger.info(f"   Name tone: {analysis.get('name_tone', 'unknown')}")
    
    except Exception as e:
        logger.error(f"   ❌ Image analysis error: {str(e)}")
        state['error'] = f"Image analysis failed: {str(e)}"
        state['image_description'] = "Image analysis failed."
        state['visual_context'] = {}
    
    return state


@traceable(name="keyword_filter_node", run_type="chain")
def keyword_filter_node(state: AgentState) -> AgentState:
    """
    Node 3: Filter and rank keywords using KeywordFilter
    Supports both Kundan-Polki and American Diamond/Crystal lines
    """
    logger.info("🔍 Node 3: Filtering keywords")
    
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
        
    print(f"Filtered keywords: {state['filtered_keywords']}")
    return state


@traceable(name="prompt_selection_node", run_type="chain")
def prompt_selection_node(state: AgentState) -> AgentState:
    """
    Node 4: Select the appropriate prompt based on category and line
    """
    logger.info("📝 Node 4: Selecting prompt template")
    
    category = state['category'].lower()
    line = state['line'].lower()
    
    print(f"Category: {category}, Line: {line}")
    
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
    Node 5: Generate content using LLM via Groq
    """
    logger.info("🤖 Node 4: Generating content with Groq LLM")
    
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
            "image_analysis": state.get('image_description', 'No image analysis available.')
        }
        
        # Format the prompt with product details
        try:
            filled_prompt = state['selected_prompt'].format(**prompt_params)
            logger.info("Successfully formatted prompt with product details")
        except KeyError as e:
            print(f"   ❌ Error formatting prompt: {str(e)}")
            # Attempt a fix by treating the selected_prompt as plain text with a .format_messages() method
            if hasattr(state['selected_prompt'], 'format_messages'):
                messages = state['selected_prompt'].format_messages(**prompt_params)
                filled_prompt = messages[0]
                logger.info("   Successfully formatted prompt as messages")
            else:
                raise
        
        logger.info("   Calling Groq LLM...")
        response = llm.invoke(filled_prompt)
        content_text = response.content.strip()
        
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
            
            # Check for duplicate title immediately after generation
            if state['generated_content'].get('title'):
                duplicate_checker = DuplicateNameChecker()
                generated_title = state['generated_content']['title']
                
                # Check if title is duplicate
                if duplicate_checker.check_for_duplicates(generated_title):
                    logger.warning(f"   ⚠️  Duplicate title detected: '{generated_title}'")
                    
                    # Generate unique variation using visual context
                    visual_context = state.get('visual_context', {})
                    unique_title = duplicate_checker.generate_unique_title(
                        base_title=generated_title,
                        visual_context=visual_context
                    )
                    
                    if unique_title and unique_title != generated_title:
                        state['generated_content']['title'] = unique_title
                        logger.info(f"   ✅ Duplicate resolved: '{unique_title}'")
                    else:
                        logger.warning(f"   Could not generate unique title for: {generated_title}")
                else:
                    logger.info(f"   ✅ Title is unique: '{generated_title}'")
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
    workflow.add_node("image_analysis", image_analysis_node)
    workflow.add_node("keyword_filter", keyword_filter_node)
    workflow.add_node("prompt_selection", prompt_selection_node)
    workflow.add_node("generate", generation_node)
    
    # Define edges
    workflow.set_entry_point("preprocess")
    workflow.add_edge("preprocess", "image_analysis")
    workflow.add_edge("image_analysis", "keyword_filter")
    workflow.add_edge("keyword_filter", "prompt_selection")
    workflow.add_edge("prompt_selection", "generate")
    workflow.add_edge("generate", END)
    
    logger.info("✅ Workflow built successfully")
    
    return workflow.compile()
