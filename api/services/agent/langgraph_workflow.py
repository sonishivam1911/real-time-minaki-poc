"""
Product Writer Workflow Graph
Builds the complete LangGraph workflow with name generation
"""

import logging
from langgraph.graph import StateGraph, END

from agent.product_writer.state import ProductWriterState
from agent.product_writer.nodes.preprocess import preprocess_node
from agent.product_writer.nodes.search_query_generator import search_query_generator_node
from agent.product_writer.nodes.serper_search import serper_search_node
from agent.product_writer.nodes.reflection import reflection_node
from agent.product_writer.nodes.name_parser import name_parser_node
from agent.product_writer.nodes.keyword_filter import keyword_filter_node
from agent.product_writer.nodes.prompt_selection import prompt_selection_node
from agent.product_writer.nodes.generate import generation_node
from agent.utils.edge_conditions import should_retry_search

logger = logging.getLogger("ProductWriter.Graph")


def build_product_writer_workflow() -> StateGraph:
    """
    Build the complete LangGraph workflow with name generation pipeline
    
    Flow:
    1. Preprocess → Extract product attributes
    2. Search Query Generator → Generate creative search query
    3. Serper Search → Fetch search results
    4. Reflection → Validate quality (retry if needed)
    5. Name Parser → Extract name pool
    6. Keyword Filter → Filter SEO keywords
    7. Prompt Selection → Select appropriate template
    8. Generate → Create content with unique name
    
    Returns:
        Compiled StateGraph workflow
    """
    logger.info("🏗️  Building Product Writer LangGraph workflow...")
    
    # Create workflow
    workflow = StateGraph(ProductWriterState)
    
    # ============= ADD NODES =============
    logger.info("   Adding nodes...")
    workflow.add_node("preprocess", preprocess_node)
    workflow.add_node("search_query_generator", search_query_generator_node)
    workflow.add_node("serper_search", serper_search_node)
    workflow.add_node("reflection", reflection_node)
    workflow.add_node("name_parser", name_parser_node)
    workflow.add_node("keyword_filter", keyword_filter_node)
    workflow.add_node("prompt_selection", prompt_selection_node)
    workflow.add_node("generate", generation_node)
    
    # ============= DEFINE FLOW =============
    logger.info("   Defining edges...")
    
    # Entry point
    workflow.set_entry_point("preprocess")
    
    # Name generation pipeline
    workflow.add_edge("preprocess", "search_query_generator")
    workflow.add_edge("search_query_generator", "serper_search")
    workflow.add_edge("serper_search", "reflection")
    
    # Conditional: retry search or continue
    workflow.add_conditional_edges(
        "reflection",
        should_retry_search,
        {
            "search_query_generator": "search_query_generator",  # Reflection failed, generate new query
            "serper_search": "serper_search",                    # Reflection failed but has suggestion, use it directly
            "name_parser": "name_parser",                        # Extract names (always attempt)
        }
    )
    
    # Continue to main content generation workflow
    workflow.add_edge("name_parser", "keyword_filter")
    workflow.add_edge("keyword_filter", "prompt_selection")
    workflow.add_edge("prompt_selection", "generate")
    workflow.add_edge("generate", END)
    
    logger.info("✅ Workflow built successfully!")
    logger.info("   Total nodes: 8")
    logger.info("   Entry point: preprocess")
    logger.info("   Conditional edges: 1 (reflection)")
    
    return workflow.compile()


def build_name_generation_only_workflow() -> StateGraph:
    """
    Build a standalone workflow for ONLY name generation
    Useful for pre-generating name pools for batches
    
    Flow:
    1. Preprocess → Extract product attributes
    2. Search Query Generator → Generate creative search query
    3. Serper Search → Fetch search results
    4. Reflection → Validate quality (retry if needed)
    5. Name Parser → Extract name pool
    6. END
    
    Returns:
        Compiled StateGraph workflow for name generation only
    """
    logger.info("🏗️  Building Name Generation Only workflow...")
    
    workflow = StateGraph(ProductWriterState)
    
    # Add nodes
    workflow.add_node("preprocess", preprocess_node)
    workflow.add_node("search_query_generator", search_query_generator_node)
    workflow.add_node("serper_search", serper_search_node)
    workflow.add_node("reflection", reflection_node)
    workflow.add_node("name_parser", name_parser_node)
    
    # Define flow
    workflow.set_entry_point("preprocess")
    workflow.add_edge("preprocess", "search_query_generator")
    workflow.add_edge("search_query_generator", "serper_search")
    workflow.add_edge("serper_search", "reflection")
    
    # Conditional: retry or end
    workflow.add_conditional_edges(
        "reflection",
        lambda state: "name_parser" if state.get("reflection_passed") else (
            "serper_search" if state.get("search_query") else (
                "search_query_generator" if state.get("retry_count", 0) < 3 else "end"
            )
        ),
        {
            "search_query_generator": "search_query_generator",  # Generate new query if no suggestion
            "serper_search": "serper_search",                    # Use suggested search term directly
            "name_parser": "name_parser",
            "end": END
        }
    )
    
    workflow.add_edge("name_parser", END)
    
    logger.info("✅ Name Generation workflow built!")
    
    return workflow.compile()