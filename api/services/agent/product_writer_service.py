import pandas as pd
from typing import List, Dict
import logging
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
        
        for idx, product_row in enumerate(product_rows, 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"Processing Product {idx}/{len(product_rows)}: {product_row.get('product_sku', 'Unknown')}")
            logger.info(f"{'='*80}")
            
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
                    'image_url': None,
                    'generated_content': None,
                    'error': None
                }
                
                # Run through workflow
                final_state = self.workflow.invoke(initial_state)
                
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
        
        # Summary
        success_count = sum(1 for r in results if r['success'])
        logger.info(f"\n{'='*80}")
        logger.info(f"GENERATION COMPLETE: {success_count}/{len(results)} successful")
        logger.info(f"{'='*80}\n")
        
        return results
