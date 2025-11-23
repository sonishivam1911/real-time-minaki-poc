"""
Keyword Filter Node
Filters Google Keyword Planner keywords based on product
"""

import logging
from langsmith import traceable
from ..state import ProductWriterState
from services.agent.keyword_filter import KeywordFilter

logger = logging.getLogger("ProductWriter.Nodes.KeywordFilter")


@traceable(name="keyword_filter_node", run_type="chain")
def keyword_filter_node(state: ProductWriterState) -> ProductWriterState:
    """
    Node: Filter and rank keywords using KeywordFilter
    """
    logger.info("🔑 Filtering keywords...")
    
    try:
        filter_system = KeywordFilter(state['keywords_df'])
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
        
        logger.info(f"✅ Filtered {len(state['filtered_keywords'])} keywords")
        if state['filtered_keywords']:
            logger.info(f"   Top 5: {', '.join(state['filtered_keywords'][:5])}")
        
    except Exception as e:
        logger.error(f"❌ Keyword filtering error: {str(e)}")
        state['error'] = f"Keyword filtering failed: {str(e)}"
        state['filtered_keywords'] = []
        
    return state