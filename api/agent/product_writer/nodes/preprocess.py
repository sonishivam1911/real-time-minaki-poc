import logging
from langsmith import traceable
from ..state import ProductWriterState

logger = logging.getLogger("ProductWriter.Nodes.Preprocess")


@traceable(name="preprocess_node", run_type="chain")
def preprocess_node(state: ProductWriterState) -> ProductWriterState:
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
    
    # Initialize used names list
    if 'used_names' not in state or state['used_names'] is None:
        state['used_names'] = []
    
    # Extract image URL
    image_url = None
    for field in ['high_resolution_1', 'image_url', 'image_1', 'primary_image']:
        if field in product and product[field]:
            image_url = product[field]
            break
    
    state['image_url'] = image_url
    
    logger.info(f"✅ Preprocessed: {state['category']} - {state['line']} ({state['colors']})")
    
    return state