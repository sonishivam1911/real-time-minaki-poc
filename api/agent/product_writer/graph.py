import os
import json
from typing import TypedDict
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from langsmith import traceable

from ...utils.schema.product_writer_agent import AgentState, ProductOutput, ActionInput
from .kundan_jewellery_prompt import PRODUCT_CONTENT_PROMPT


class GraphState(TypedDict):
    """State for LangGraph workflow"""
    product_input: dict
    product_output: dict | None
    error: str | None


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
        messages = PRODUCT_CONTENT_PROMPT.format_messages(**product_data)
        
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