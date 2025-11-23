import pandas as pd
from typing import List, Dict, Optional
import logging
import time
from services.agent.langgraph_workflow import build_product_writer_workflow
from agent.product_writer.state import ProductWriterState

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
        self.workflow = build_product_writer_workflow()
        self.used_names = []  # Track used names across all products
        logger.info("✅ ProductWriterService initialized")
    
    def _initialize_state(self, product_row: Dict) -> ProductWriterState:
        """
        Create and validate initial state for product processing
        
        Args:
            product_row: Single product dictionary
        
        Returns:
            Properly initialized ProductWriterState
        """
        state: ProductWriterState = {
            # ============= INPUT =============
            'product_row': product_row,
            'keywords_df': self.keywords_df,
            
            # ============= NAME GENERATION =============
            'jewelry_type': None,
            'primary_color': product_row.get('primary_color'),
            'search_query': None,
            'search_results': None,
            'name_pool': None,
            'required_names': 10,  # Default number of names to extract
            'reflection_passed': False,
            'retry_count': 0,
            
            # ============= INTERMEDIATE =============
            'category': product_row.get('category', ''),
            'line': product_row.get('line', ''),
            'colors': f"{product_row.get('primary_color', '')} {product_row.get('secondary_color', '')}".strip(),
            'filtered_keywords': [],
            'selected_prompt': '',
            'used_names': self.used_names.copy(),  # Track used names across products
            'image_url': None,
            
            # ============= OUTPUT =============
            'generated_content': None,
            'duplicate_resolved': False,
            'error': None,
        }
        
        logger.debug(f"✅ State initialized with {len(state)} fields")
        return state
    
    def generate_content_for_products(
        self, 
        product_rows: List[Dict]
    ) -> List[Dict]:
        """
        Process multiple products through LangGraph workflow
        
        Args:
            product_rows: List of product dictionaries from CSV
        
        Returns:
            List of generated content dictionaries with success/error status
        """
        if not product_rows:
            logger.warning("⚠️  No products provided for processing")
            return []
        
        logger.info(f"🚀 Starting content generation for {len(product_rows)} products")
        logger.info(f"   Tracking used names across batch to avoid duplicates")
        
        results = []
        
        for idx, product_row in enumerate(product_rows, 1):
            product_sku = product_row.get('product_sku', 'Unknown SKU')
            logger.info(f"\n📝 Processing product {idx}/{len(product_rows)}: {product_sku}")
            
            # Add delay between products to prevent rate limiting (except for first product)
            if idx > 1:
                logger.debug(f"   ⏱️  Adding 2-second delay between products...")
                time.sleep(2)
            
            try:
                # ============= INITIALIZE STATE PROPERLY =============
                initial_state = self._initialize_state(product_row)
                
                logger.debug(f"   State keys: {list(initial_state.keys())}")
                logger.info(f"   Category: {initial_state['category']}, Line: {initial_state['line']}")
                
                # Run through workflow
                logger.info(f"   Invoking workflow...")
                final_state = self.workflow.invoke(initial_state)
                
                # Update used_names list with any new names from this workflow run
                if final_state.get('used_names'):
                    self.used_names = final_state['used_names']
                    logger.info(f"   ✓ Used names updated: {len(self.used_names)} total")
                
                logger.debug(f"   Workflow completed. Generated content: {bool(final_state.get('generated_content'))}")
                
                # ============= RESULT HANDLING =============
                # Check for errors
                if final_state.get('error'):
                    logger.error(f"   ❌ Error: {final_state['error']}")
                    results.append({
                        'product_sku': product_sku,
                        'success': False,
                        'error': final_state['error'],
                        'content': None
                    })
                elif final_state.get('generated_content'):
                    content = final_state['generated_content']
                    logger.info(f"   ✅ Content generated successfully!")
                    logger.info(f"      Title: {content.get('title', 'N/A')}")
                    logger.debug(f"      Description: {content.get('description', 'N/A')[:100]}...")
                    
                    results.append({
                        'product_sku': product_sku,
                        'success': True,
                        'error': None,
                        'content': content
                    })
                else:
                    logger.error(f"   ❌ No content generated (no error reported)")
                    results.append({
                        'product_sku': product_sku,
                        'success': False,
                        'error': 'No content generated',
                        'content': None
                    })
                
            except Exception as e:
                logger.error(f"   ❌ Workflow execution failed: {str(e)}", exc_info=True)
                results.append({
                    'product_sku': product_sku,
                    'success': False,
                    'error': f"Workflow error: {str(e)}",
                    'content': None
                })
        
        # ============= SUMMARY =============
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        logger.info(f"\n📊 Processing Complete!")
        logger.info(f"   ✅ Successful: {successful}/{len(results)}")
        logger.info(f"   ❌ Failed: {failed}/{len(results)}")
        logger.info(f"   📍 Success rate: {(successful/len(results)*100):.1f}%")
        
        return results
