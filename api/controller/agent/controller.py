"""
AGENT CONTROLLER (UPDATED)
Handles both CSVs and runs complete workflow
"""

from fastapi import APIRouter, HTTPException, status, UploadFile, File
from typing import List
import logging
import pandas as pd
import io

from services.agent.normalize_columns import parse_csv_content
from utils.schema.product_writer_agent import ProductCSVRow
from services.shopify.product import ShopifyProductService
from services.shopify.product_filtering import ProductFilterService
from services.agent.product_writer_service import ProductWriterService

router = APIRouter()
logger = logging.getLogger("Agent Controller")


@router.post("/writer-agent", status_code=status.HTTP_200_OK)
async def upload_and_generate_content(
    products_file: UploadFile = File(..., description="Products CSV file"),
    keywords_file: UploadFile = File(..., description="Google Keyword Planner CSV file"),
    limit_per_row: int = 15
):
    """
    **COMPLETE WORKFLOW: Upload CSVs → Filter Products → Generate Content**
    
    Steps:
    1. Parse products CSV
    2. Parse keywords CSV (Google Keyword Planner format)
    3. Filter Shopify products based on criteria (gender, category, line, style)
    4. Run filtered products through LangGraph workflow
    5. Return generated content (title, description, SEO, styling tip)
    
    **This is the MAIN endpoint for content generation!**
    """
    try:
        # STEP 1: Validate and parse PRODUCTS CSV
        if not products_file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Products file must be CSV"
            )
        
        logger.info(f"📤 Step 1: Processing products file: {products_file.filename}")
        
        products_content = await products_file.read()
        csv_content = products_content.decode('utf-8')
        
        parsed_rows, errors = parse_csv_content(csv_content)
        logger.info(f"✅ Parsed {len(parsed_rows)} rows from products CSV")
        
        if not parsed_rows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid rows found in products CSV"
            )
            
        validated_rows = []
        for idx, row in enumerate(parsed_rows):
            try:
                validated_row = ProductCSVRow(**row)
                validated_rows.append(validated_row)
            except Exception as e:
                logger.warning(f"Row {idx + 2} validation failed: {str(e)}")
        
        logger.debug(f"Validated row is : {validated_rows}")
        
        if not keywords_file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Keywords file must be CSV"
            )
        
        logger.info(f"📤 Step 2: Processing keywords file: {keywords_file.filename}")
        
        keywords_content = await keywords_file.read()
        
        try:
            keywords_df = pd.read_csv(
                io.StringIO(keywords_content.decode('utf-16')),
                sep='\t',
                skiprows=2  # Skip title and date rows
            )
        except:
            # Fallback to UTF-8 if UTF-16 fails
            keywords_df = pd.read_csv(
                io.StringIO(keywords_content.decode('utf-8')),
                sep=',',
                skiprows=0
            )
        
        logger.info(f"Keyords CSV columns: {keywords_df.head()}")

        # Initialize writer service
        writer_service = ProductWriterService(keywords_df)
        
        product_dicts = []
        for product in validated_rows:
            # Use attribute access (.property) instead of dictionary access ['property']
            # Or use model_dump() to convert the entire model to a dictionary
            product_dict = {
                'product_sku': product.product_sku if product.product_sku else 'Unknown',
                'category': product.category if product.category else '',
                'line': product.line if product.line else '',
                'style': product.style if product.style else '',
                'finish': product.finish if product.finish else '',
                'work': product.work if product.work else '',
                'components': product.components if product.components else '',
                'finding': product.finding if product.finding else '',
                'primary_color': product.primary_color if product.primary_color else '',
                'secondary_color': product.secondary_color if product.secondary_color else '',
                'occasions': product.occasions if product.occasions else '',
            }
            product_dicts.append(product_dict)
        
        
        # Generate content
        generated_results = writer_service.generate_content_for_products(product_dicts)
        
        logger.info(f"✅ Content generation complete")
    
        success_count = sum(1 for r in generated_results if r['success'])
        
        return {
            "success": True,
            "message": f"Successfully generated content for {success_count}/{len(generated_results)} products",
            "csv_summary": {
                "products_filename": products_file.filename,
                "keywords_filename": keywords_file.filename,
                "total_product_rows": len(parsed_rows),
                "validated_rows": len(validated_rows),
                "total_keywords": len(keywords_df)
            },
            "content_generation": {
                "total_processed": len(generated_results),
                "successful": success_count,
                "failed": len(generated_results) - success_count,
                "results": generated_results
            },
            "errors": errors if errors else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in writer-agent endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing request: {str(e)}"
        )