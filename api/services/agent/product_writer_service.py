import pandas as pd
from typing import List, Dict
import logging
import time
from services.agent.langgraph_workflow import build_langgraph_workflow

logger = logging.getLogger("Product Writer Service")


class ProductWriterService:
    """
    Orchestrates the entire content generation pipeline using LangGraph
    """
    
    def __init__(self, keywords_df: pd.DataFrame):
        """
        Initialize with keywords DataFrame
        
        Args:
            keywords_df: DataFrame from Google Keyword Planner CSV
        """
        self.keywords_df = keywords_df
        self.workflow = build_langgraph_workflow()
        logger.info("✅ ProductWriterService initialized")
    
    def generate_content_for_products(
        self, 
        product_rows: List[Dict]
    ) -> List[Dict]:
        """
        Process multiple products through LangGraph workflow
        
        Args:
            product_rows: List of product dictionaries from CSV
        
        Returns:
            List of generated content dictionaries
        """
        logger.info(f"🚀 Starting content generation for {len(product_rows)} products")
        
        results = []
        used_names = []  # Track used names across all products
        
        for idx, product_row in enumerate(product_rows, 1):
            
            logger.info(f"📝 Processing product {idx}/{len(product_rows)}: {product_row.get('product_sku', 'Unknown SKU')}")
            
            # Add delay between products to prevent rate limiting (except for first product)
            if idx > 1:
                logger.info("⏱️  Adding 1-second delay between products...")
                time.sleep(1)
            
            try:
                # Initialize state
                initial_state = {
                    'product_row': product_row,
                    'keywords_df': self.keywords_df,
                    'category': '',
                    'line': '',
                    'colors': '',
                    'filtered_keywords': [],
                    'selected_prompt': '',
                    'used_names': used_names.copy(),  # Pass current used names
                    'image_url': None,
                    'generated_content': None,
                    'error': None
                }
                
                # Run through workflow
                final_state = self.workflow.invoke(initial_state)
                
                # Update used_names list with any new names from this workflow run
                used_names = final_state.get('used_names', used_names)
                
                # Check for errors
                if final_state.get('error'):
                    logger.error(f"   ❌ Error: {final_state['error']}")
                    results.append({
                        'product_sku': product_row.get('product_sku', 'Unknown'),
                        'success': False,
                        'error': final_state['error'],
                        'content': None
                    })
                elif final_state.get('generated_content'):
                    logger.info(f"   ✅ Success!")
                    results.append({
                        'product_sku': product_row.get('product_sku', 'Unknown'),
                        'success': True,
                        'error': None,
                        'content': final_state['generated_content']
                    })
                else:
                    logger.error(f"   ❌ No content generated")
                    results.append({
                        'product_sku': product_row.get('product_sku', 'Unknown'),
                        'success': False,
                        'error': 'No content generated',
                        'content': None
                    })
                
            except Exception as e:
                logger.error(f"   ❌ Workflow error: {str(e)}", exc_info=True)
                results.append({
                    'product_sku': product_row.get('product_sku', 'Unknown'),
                    'success': False,
                    'error': str(e),
                    'content': None
                })
        
        return results
