import os
import json
from typing import TypedDict
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from langsmith import traceable

from ...utils.schema.product_writer_agent import AgentState, ProductOutput, ActionInput
from .prompts.kundan_jewellery_prompt import kundan_jewelry_prompt
from .prompts.name_search_query_prompt import search_query_prompt
from .prompts.name_reflection_prompt import reflection_prompt
from .prompts.name_parser_prompt import name_parser_prompt
from ...utils.serper_search import search_serper

class GraphState(TypedDict):
    # Existing fields
    product_input: dict
    product_output: dict | None
    error: str | None
    
    jewelry_type: str  # "kundan" or "crystal_ad"
    primary_color: str  # extracted from product_input
    search_query: str | None
    search_results: str | None  # raw text from Serper
    name_pool: list[dict] | None  # [{"name": "X", "meaning": "Y"}]
    selected_name: dict | None  # {"name": "X", "meaning": "Y"}
    reflection_passed: bool  # flag for conditional routing
    retry_count: int  # prevent infinite loops


# Initialize Groq LLM
llm = ChatGroq(
    model="llama-3.1-8b-instant",  # Fast, free tier, excellent quality
    temperature=0.7,  # Creative but controlled
    api_key=os.getenv("GROQ_API_KEY"),
)


@traceable(name="generate_content_node", run_type="chain")
def generate_content_node(state: GraphState) -> GraphState:
    """
    Single node that generates all product content in one LLM call
    Returns JSON with action/action_input pattern
    """
    try:
        # Get product input
        product_data = state["product_input"]
        
        # Format prompt
        messages = kundan_jewelry_prompt.format_messages(**product_data)
        
        # Call LLM
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # Parse JSON response
        # Remove markdown code blocks if present
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        elif content.startswith("```"):
            content = content.replace("```", "").strip()
        
        # Parse JSON
        parsed_output = json.loads(content)
        
        # Validate structure
        if "action" not in parsed_output or "action_input" not in parsed_output:
            raise ValueError("Response missing required 'action' or 'action_input' fields")
        
        # Update state with output
        state["product_output"] = parsed_output
        state["error"] = None
        
        return state
        
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse JSON response: {str(e)}\nResponse: {content[:500]}"
        state["error"] = error_msg
        state["product_output"] = None
        return state
        
    except Exception as e:
        error_msg = f"Error in generate_content_node: {str(e)}"
        state["error"] = error_msg
        state["product_output"] = None
        return state
    
    


@traceable(name="search_query_generator_node", run_type="chain")
def search_query_generator_node(state: GraphState) -> GraphState:
    """
    Generate optimal search query based on product attributes
    """
    try:
        product_input = state["product_input"]
        
        # Extract needed fields
        jewelry_type = "crystal_ad" if "crystal" in product_input.get("jewelry_line", "").lower() else "kundan"
        primary_color = product_input.get("primary_color", "")
        secondary_color = product_input.get("secondary_color", "")
        category = product_input.get("category", "")
        
        # Format prompt
        messages = search_query_prompt.format_messages(
            jewelry_type=jewelry_type,
            primary_color=primary_color,
            secondary_color=secondary_color,
            category=category
        )
        
        # Call LLM
        response = llm.invoke(messages)
        search_query = response.content.strip()
        
        # Update state
        state["jewelry_type"] = jewelry_type
        state["primary_color"] = primary_color
        state["search_query"] = search_query
        state["retry_count"] = state.get("retry_count", 0)
        
        return state
        
    except Exception as e:
        state["error"] = f"Error generating search query: {str(e)}"
        return state   
    
    


@traceable(name="serper_search_node", run_type="chain")
def serper_search_node(state: GraphState) -> GraphState:
    """
    Call Serper API with generated query
    """
    try:
        search_query = state.get("search_query")
        
        if not search_query:
            state["error"] = "No search query provided"
            return state
        
        # Call Serper
        search_results = search_serper(search_query)
        
        # Update state
        state["search_results"] = search_results
        state["error"] = None
        
        return state
        
    except Exception as e:
        state["error"] = f"Serper search failed: {str(e)}"
        state["search_results"] = None
        return state
    
@traceable(name="reflection_node", run_type="chain")
def reflection_node(state: GraphState) -> GraphState:
    """
    Validate we have enough names for all products
    """
    try:
        search_results = state.get("search_results")
        required_names = state.get("required_names", 10)  # Default buffer
        
        if not search_results:
            state["reflection_passed"] = False
            state["error"] = "No search results"
            return state
        
        # Format prompt
        messages = reflection_prompt.format_messages(
            required_names=required_names,
            search_results=search_results[:3000]
        )
        
        # Call LLM
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # Parse JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        result = json.loads(content)
        action_input = result.get("action_input", {})
        
        passed = action_input.get("passed", False)
        count = action_input.get("extracted_names_count", 0)
        
        state["reflection_passed"] = passed
        
        if not passed:
            state["retry_count"] = state.get("retry_count", 0) + 1
            print(f"❌ Reflection FAILED - need {required_names}, found {count}")
        else:
            print(f"✅ Reflection PASSED - {count}/{required_names} names available")
        
        return state
        
    except Exception as e:
        state["reflection_passed"] = False
        state["error"] = f"Reflection error: {str(e)}"
        return state    




@traceable(name="name_parser_node", run_type="chain")
def name_parser_node(state: GraphState) -> GraphState:
    """
    Extract name pool from search results
    """
    try:
        search_results = state.get("search_results")
        
        # Format prompt
        messages = name_parser_prompt.format_messages(
            search_results=search_results[:4000]
        )
        
        # Call LLM
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # Parse JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        result = json.loads(content)
        action_input = result.get("action_input", {})
        name_pool = action_input.get("names", [])
        
        if len(name_pool) < 5:
            state["error"] = f"Only extracted {len(name_pool)} names"
            state["reflection_passed"] = False
            return state
        
        print(f"✅ Extracted {len(name_pool)} names to pool")
        
        # Update state
        state["name_pool"] = name_pool
        state["error"] = None
        
        return state
        
    except Exception as e:
        state["error"] = f"Parser error: {str(e)}"
        state["reflection_passed"] = False
        return state

# Build LangGraph workflow
def create_workflow() -> StateGraph:
    """
    Create simple single-node LangGraph workflow
    
    Flow: START -> generate_content_node -> END
    """
    workflow = StateGraph(GraphState)
    
    # Add single node
    workflow.add_node("generate_content", generate_content_node)
    
    # Set entry point
    workflow.set_entry_point("generate_content")
    
    # Add edge to end
    workflow.add_edge("generate_content", END)
    
    return workflow.compile()


# Create compiled graph
graph = create_workflow()


@traceable(name="run_agent", run_type="chain")
def run_agent(product_input: dict) -> dict:
    """
    Run the agent for a single product
    
    Args:
        product_input: Dictionary with product attributes
        
    Returns:
        Dictionary with product_output or error
    """
    initial_state = {
        "product_input": product_input,
        "product_output": None,
        "error": None,
    }
    
    # Run graph
    result = graph.invoke(initial_state)
    
    return {
        "product_output": result.get("product_output"),
        "error": result.get("error"),
    }


@traceable(name="run_batch", run_type="chain")
def run_batch(products: list[dict]) -> dict:
    """
    Run agent for multiple products
    
    Args:
        products: List of product input dictionaries
        
    Returns:
        Dictionary with results and errors
    """
    results = []
    errors = []
    
    for idx, product in enumerate(products):
        try:
            result = run_agent(product)
            
            if result["error"]:
                errors.append({
                    "product_index": idx,
                    "error": result["error"],
                    "product_data": product,
                })
            else:
                results.append(result["product_output"])
                
        except Exception as e:
            errors.append({
                "product_index": idx,
                "error": str(e),
                "product_data": product,
            })
    
    return {
        "results": results,
        "errors": errors,
    }