"""
Nykaa Rewriter Agent - LangGraph Workflow Orchestration
Simple workflow for AI-powered product name and description generation
"""

import os
import json
import traceback
import time
from typing import TypedDict, Optional, List, Dict, Any

from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from langsmith import traceable

from .config import LLM_CONFIG, DEBUG
from .nykaa_rewriter_prompt import nykaa_rewriter_prompt
from ..output_parser import ActionParser


# Initialize Groq LLM (same as product_writer)
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0.7,
    api_key=os.getenv("GROQ_API_KEY"),
)

# Initialize output parser
output_parser = ActionParser(use_json_repair=True)


# ============================================================================
# STATE DEFINITION
# ============================================================================

class NykaaRewriterState(TypedDict):
    """LangGraph state for Nykaa rewriter workflow"""
    
    # Input
    sku: str
    current_name: str
    current_description: str
    product_type: str
    material: str  # Material name (already resolved by controller)
    metal_type: str
    color: Optional[str]
    occasion: Optional[str]
    price: float
    set_contents: List[str]
    
    # Output
    generated_name: Optional[str]
    generated_description: Optional[str]
    
    # Errors
    error: Optional[str]


# ============================================================================
# NODE FUNCTIONS
# ============================================================================

# ============================================================================
# NODE FUNCTIONS
# ============================================================================

@traceable(name="llm_rewriter_node", run_type="chain")
def llm_rewriter_node(state: NykaaRewriterState) -> NykaaRewriterState:
    """
    Call LLM to generate product name and description
    
    Input: product details
    Output: generated_name, generated_description
    """
    
    if DEBUG.get("log_prompt_output"):
        print(f"🤖 [LLM Rewriter] Generating content for {state['sku']}")
    
    try:
        # Prepare product data for prompt formatting
        product_data = {
            "sku": state["sku"],
            "product_type": state["product_type"],
            "material": state.get("material", "Kundan Polki"),
            "metal_type": state.get("metal_type", "Antique Gold"),
            "color": state.get("color", "Multicolor"),
            "occasion": state.get("occasion", "Wedding"),
            "price": state["price"],
            "set_contents": ", ".join(state["set_contents"]),
            "used_names": "",  # To be filled by controller if needed
        }
        
        if DEBUG.get("log_prompt_input"):
            print(f"   Product data: {product_data}")
        
        # Format messages directly using the prompt template
        messages = nykaa_rewriter_prompt.format_messages(**product_data)
        
        time.sleep(10)  
        
        # Retry mechanism for rate limiting
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = llm.invoke(messages)
                break  # Success, exit retry loop
            except Exception as e:
                if "429" in str(e) or "Too Many Requests" in str(e):
                    retry_count += 1
                    wait_time = 5 * (2 ** retry_count)  # Exponential backoff: 10s, 20s, 40s
                    if DEBUG.get("log_prompt_output"):
                        print(f"⚠️ Rate limited. Waiting {wait_time}s before retry {retry_count}/{max_retries}")
                    time.sleep(wait_time)
                    if retry_count >= max_retries:
                        raise Exception(f"Max retries ({max_retries}) exceeded for rate limiting")
                else:
                    # Not a rate limit error, re-raise immediately
                    raise
        content = response.content.strip()
        
        
        if DEBUG.get("log_prompt_output"):
            print(f"   Raw response: {content[:300]}...")
        
        # Parse JSON response using ActionParser
        try:
            parsed_json = output_parser.safe_json_parse(content)
            
            if parsed_json and isinstance(parsed_json, dict):
                # Handle action/action_input format (primary format)
                if "action" in parsed_json and "action_input" in parsed_json:
                    action_input = parsed_json["action_input"]
                    if isinstance(action_input, dict):
                        state["generated_name"] = action_input.get("name", "")
                        state["generated_description"] = action_input.get("description", "")
                    else:
                        state["error"] = "action_input is not a dictionary"
                # Handle simple format (fallback)
                elif "name" in parsed_json and "description" in parsed_json:
                    state["generated_name"] = parsed_json["name"]
                    state["generated_description"] = parsed_json["description"]
                else:
                    state["error"] = "Missing name/description fields in parsed JSON"
                
                if state.get("generated_name") and state.get("generated_description"):
                    if DEBUG.get("log_prompt_output"):
                        print(f"✅ Generated name: {state['generated_name'][:60]}")
                        print(f"✅ SKU preserved: {state['sku']}")
                else:
                    state["error"] = f"Empty name or description in response"
                    if DEBUG.get("log_prompt_output"):
                        print(f"⚠️ {state['error']}")
            else:
                state["error"] = "Failed to parse JSON or result is not a dictionary"
                if DEBUG.get("log_prompt_output"):
                    print(f"❌ Parse failed: {state['error']}")
            
        except Exception as e:
            print(f"❌ Error parsing response: {e}")
            print(f"traceback: {traceback.format_exc()}")
            state["error"] = f"ActionParser error: {str(e)}"
            if DEBUG.get("log_prompt_output"):
                print(f"❌ ActionParser error: {e}")
                print(f"   Full content: {content}")
            
            # Try manual fallback for simple cases
            try:
                import re
                name_match = re.search(r'"name"\s*:\s*"([^"]*)"', content)
                desc_match = re.search(r'"description"\s*:\s*"([^"]*)"', content)
                
                if name_match and desc_match:
                    state["generated_name"] = name_match.group(1)
                    state["generated_description"] = desc_match.group(1)
                    state["error"] = None  # Clear error since we recovered
                    if DEBUG.get("log_prompt_output"):
                        print(f"✅ Recovered via regex: {state['generated_name'][:60]}")
            except Exception as regex_e:
                if DEBUG.get("log_prompt_output"):
                    print(f"❌ Regex fallback failed: {regex_e}")
            
    except Exception as e:
        print(f"❌ Error creating prompt: {e}")
        print(f"traceback: {traceback.format_exc()}")
        state["error"] = f"LLM generation error: {str(e)}"
        state["generated_name"] = ""
        state["generated_description"] = ""
        if DEBUG.get("log_prompt_output"):
            print(f"❌ LLM error: {e}")
    
    # Note: SKU is preserved automatically in LangGraph state - no need for manual preservation
    return state



# ============================================================================
# GRAPH BUILDER
# ============================================================================

def create_nykaa_rewriter_graph():
    """
    Build and compile the LangGraph workflow
    
    Flow:
    LLM Rewriter → END
    """
    
    # Initialize graph
    graph = StateGraph(NykaaRewriterState)
    
    # Add nodes
    graph.add_node("llm_rewriter", llm_rewriter_node)
    
    # Define edges (simplified pipeline)
    graph.set_entry_point("llm_rewriter")
    graph.add_edge("llm_rewriter", END)
    
    # Compile and return
    compiled_graph = graph.compile()
    
    return compiled_graph


# Create global instance
nykaa_graph = create_nykaa_rewriter_graph()


# ============================================================================
# EXECUTION FUNCTIONS
# ============================================================================

def rewrite_product(product_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute rewriter workflow for a single product
    
    Args:
        product_input: Dictionary with product details:
            - sku: Product SKU
            - current_name: Current product name
            - current_description: Current description
            - product_type: Type (Necklace, Choker, etc.)
            - material_gid: Optional Shopify metaobject GID
            - metal_type: Metal finish
            - color: Color
            - occasion: Occasion
            - price: Price in INR
            - set_contents: List of included items
            - image_count: Number of product images
            - is_draft: Is product in draft status?
    
    Returns:
        Output state with generated content and quality metrics
    """
    
    # Initialize state (must match NykaaRewriterState TypedDict)
    initial_state = {
        # Required fields from NykaaRewriterState
        "sku": product_input.get("sku", ""),
        "current_name": product_input.get("current_name", ""),
        "current_description": product_input.get("current_description", ""),
        "product_type": product_input.get("product_type", "Necklace"),
        "material": product_input.get("material", "Kundan Polki"),  # Material name (resolved)
        "metal_type": product_input.get("metal_type", "Antique Gold"),
        "color": product_input.get("color"),
        "occasion": product_input.get("occasion"),
        "price": product_input.get("price", 5000),
        "set_contents": product_input.get("set_contents", []),
        
        # Output fields
        "generated_name": None,
        "generated_description": None,
        
        # Error field
        "error": None,
    }
    
    # Execute graph
    result = nykaa_graph.invoke(initial_state)
    
    return result


def batch_rewrite_products(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Execute rewriter workflow for multiple products with rate limiting
    
    Args:
        products: List of product input dictionaries
    
    Returns:
        List of output dictionaries (converted from LangGraph state)
    """
    
    results = []
    
    for i, product in enumerate(products, 1):
        print(f"\n[{i}/{len(products)}] Processing: {product.get('sku')}")
        
        try:
            # Execute graph and get LangGraph state
            graph_result = rewrite_product(product)
            
            # Convert LangGraph state to simple dictionary
            result_dict = {
                "sku": graph_result.get("sku", ""),
                "current_name": graph_result.get("current_name", ""),
                "current_description": graph_result.get("current_description", ""),
                "product_type": graph_result.get("product_type", ""),
                "material": graph_result.get("material", ""),
                "metal_type": graph_result.get("metal_type", ""),
                "color": graph_result.get("color", ""),
                "occasion": graph_result.get("occasion", ""),
                "price": graph_result.get("price", 0),
                "set_contents": graph_result.get("set_contents", []),
                "generated_name": graph_result.get("generated_name"),
                "generated_description": graph_result.get("generated_description"),
                "error": graph_result.get("error"),
            }
            
            results.append(result_dict)
            
            # Add delay between products to respect rate limits
            if i < len(products):  # Don't sleep after the last product
                time.sleep(1)  # 1 second between products
                
        except Exception as e:
            if DEBUG.get("log_prompt_output"):
                print(f"❌ Error processing {product.get('sku', 'unknown')}: {e}")
            
            # Add error result to maintain index consistency
            error_result = {
                "sku": product.get("sku", ""),
                "current_name": product.get("current_name", ""),
                "current_description": product.get("current_description", ""),
                "product_type": product.get("product_type", ""),
                "material": product.get("material", ""),
                "metal_type": product.get("metal_type", ""),
                "color": product.get("color", ""),
                "occasion": product.get("occasion", ""),
                "price": product.get("price", 0),
                "set_contents": product.get("set_contents", []),
                "generated_name": None,
                "generated_description": None,
                "error": str(e),
            }
            results.append(error_result)
    
    return results


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def format_output_for_csv(state: NykaaRewriterState) -> Dict[str, Any]:
    """
    Format output state for CSV export
    
    Returns:
        Dictionary ready for CSV row
    """
    
    return {
        "sku": state["sku"],
        "original_name": state["current_name"],
        "generated_name": state["generated_name"],
        "original_description": state["current_description"],
        "generated_description": state["generated_description"],
        "error": state.get("error", ""),
    }


def format_output_for_api(state: NykaaRewriterState) -> Dict[str, Any]:
    """
    Format output state for API response
    
    Returns:
        Dictionary with generated content and metadata
    """
    
    return {
        "sku": state["sku"],
        "success": state.get("error") is None,
        "generated": {
            "name": state.get("generated_name", ""),
            "description": state.get("generated_description", ""),
        },
        "error": state.get("error"),
    }
