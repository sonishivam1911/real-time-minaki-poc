"""
AGENT TEST CONTROLLER  
For testing individual components and debugging
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
logger = logging.getLogger("Agent Test Controller")


@router.get("/test-health", status_code=status.HTTP_200_OK)
async def test_health():
    """Simple health check for agent test endpoints"""
    return {
        "status": "healthy",
        "message": "Agent test controller is working",
        "available_endpoints": [
            "GET /test-health",
            "POST /test-ai-generation", 
            "POST /test-tag-generation"
        ]
    }


@router.post("/test-ai-generation", status_code=status.HTTP_200_OK)
async def test_ai_content_generation_only(
    products_file: UploadFile = File(..., description="Products CSV file"),
    keywords_file: UploadFile = File(..., description="Google Keyword Planner CSV file"),
    limit_per_row: int = 5
):
    """
    **TEST ENDPOINT: AI Content Generation Only**
    
    This endpoint only tests the AI content generation without creating Shopify products.
    Useful for debugging and testing the LangGraph workflow.
    """
    try:
        # Parse CSV files (same as main endpoint)
        if not products_file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Products file must be CSV"
            )
        
        products_content = await products_file.read()
        csv_content = products_content.decode('utf-8')
        
        parsed_rows, errors = parse_csv_content(csv_content)
        
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
        
        # Limit to specified number for testing
        validated_rows = validated_rows[:limit_per_row]
        
        if not keywords_file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Keywords file must be CSV"
            )
        
        keywords_content = await keywords_file.read()
        
        try:
            keywords_df = pd.read_csv(
                io.StringIO(keywords_content.decode('utf-16')),
                sep='\t',
                skiprows=2
            )
        except:
            keywords_df = pd.read_csv(
                io.StringIO(keywords_content.decode('utf-8')),
                sep=',',
                skiprows=0
            )

        # Initialize writer service and generate content only
        writer_service = ProductWriterService(keywords_df)
        
        product_dicts = []
        for product in validated_rows:
            product_dict = product.model_dump()
            for key, value in product_dict.items():
                if value is None:
                    product_dict[key] = ''
            product_dicts.append(product_dict)
        
        # Generate content (this is what we're testing)
        generated_results = writer_service.generate_content_for_products(product_dicts)
        
        success_count = sum(1 for r in generated_results if r['success'])
        
        return {
            "success": True,
            "message": f"AI content generation test completed: {success_count}/{len(generated_results)} successful",
            "test_summary": {
                "products_tested": len(validated_rows),
                "successful_generations": success_count,
                "failed_generations": len(generated_results) - success_count
            },
            "generated_results": generated_results,
            "errors": errors if errors else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in AI generation test: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error testing AI generation: {str(e)}"
        )


@router.post("/test-tag-generation", status_code=status.HTTP_200_OK)
async def test_tag_generation_system(
    products_file: UploadFile = File(..., description="Products CSV file"),
    limit_per_row: int = 5
):
    """
    **TEST ENDPOINT: Enhanced Tag Generation System**
    
    This endpoint tests the new tag generation system without creating products.
    Shows how tags are generated for different products.
    """
    try:
        from utils.tag_generator import TagGenerator
        
        if not products_file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Products file must be CSV"
            )
        
        products_content = await products_file.read()
        csv_content = products_content.decode('utf-8')
        
        parsed_rows, errors = parse_csv_content(csv_content)
        
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
        
        # Limit for testing
        validated_rows = validated_rows[:limit_per_row]
        
        # Initialize tag generator
        tag_generator = TagGenerator()
        
        tag_test_results = []
        
        for product in validated_rows:
            product_data = {
                'product_sku': product.product_sku,
                'category': product.category,
                'style': product.style,
                'finish': product.finish,
                'work': product.work,
                'components': product.components,
                'finding': product.finding,
                'primary_color': product.primary_color,
                'secondary_color': product.secondary_color,
                'occasions': product.occasions,
                'gender': product.gender
            }
            
            # Generate tags with different scenarios
            basic_tags = tag_generator.generate_simple_tags(product_data)
            enhanced_tags = tag_generator.generate_comprehensive_tags(
                product_data=product_data,
                ai_generated_content={'title': f'Beautiful {product.category} for {product.occasions}'},
                price=2500.0,
                availability_days=3
            )
            
            tag_test_results.append({
                'product_sku': product.product_sku,
                'product_info': {
                    'category': product.category,
                    'style': product.style,
                    'colors': f"{product.primary_color}, {product.secondary_color}".strip(', '),
                    'finish': product.finish,
                    'occasions': product.occasions
                },
                'basic_tags': basic_tags,
                'basic_tags_count': len(basic_tags),
                'enhanced_tags': enhanced_tags,
                'enhanced_tags_count': len(enhanced_tags),
                'tag_categories_detected': {
                    'price_range': any('₹' in tag for tag in enhanced_tags),
                    'availability': any('days' in tag.lower() for tag in enhanced_tags),
                    'color': any('color-' in tag.lower() for tag in enhanced_tags),
                    'finish': any('finish:' in tag.lower() for tag in enhanced_tags),
                    'gender': any('gender:' in tag.lower() for tag in enhanced_tags),
                    'components': any('component:' in tag.lower() for tag in enhanced_tags),
                    'occasions': any(occ in ' '.join(enhanced_tags).lower() for occ in ['wedding', 'party', 'daily'] if occ),
                    'marketing': any(marketing in enhanced_tags for marketing in ['best seller', 'trending', 'handcrafted'])
                }
            })
        
        return {
            "success": True,
            "message": f"Tag generation test completed for {len(tag_test_results)} products",
            "test_summary": {
                "products_tested": len(validated_rows),
                "avg_basic_tags": sum(r['basic_tags_count'] for r in tag_test_results) // len(tag_test_results),
                "avg_enhanced_tags": sum(r['enhanced_tags_count'] for r in tag_test_results) // len(tag_test_results),
                "tag_improvement": f"{((sum(r['enhanced_tags_count'] for r in tag_test_results) / sum(r['basic_tags_count'] for r in tag_test_results)) - 1) * 100:.1f}% more tags"
            },
            "tag_generation_results": tag_test_results,
            "tag_system_info": {
                "enhanced_features": [
                    "Price range tags (₹0-₹999, ₹1000-₹2999, etc.)",
                    "Availability tags (3days, availability-X Days)",
                    "Style-specific marketing tags (best seller, handcrafted, trending)",
                    "Comprehensive color mapping (color-Gold, color-Silver, etc.)",
                    "Component breakdown (Component:Necklace, Component:Earrings)",
                    "Stone setting details (Stone Setting:Crystal, Stone Setting:Zircon)",
                    "Finish specifications (Finish:Gold Plated, Finish:Oxidized)",
                    "Gender targeting (Gender:Woman, women, feminine)",
                    "Occasion matching (wedding, party wear, daily wear)",
                    "SEO-optimized core tags (jewellery, Vendor MINAKI)"
                ],
                "tag_categories": [
                    "Core Business", "Category & Style", "Colors", "Finish & Materials", 
                    "Components", "Price Range", "Availability", "Gender", "Occasions", 
                    "Marketing & SEO"
                ]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in tag generation test: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error testing tag generation: {str(e)}"
        )