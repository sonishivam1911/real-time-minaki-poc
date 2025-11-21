"""
AGENT CONTROLLER (UPDATED)
Handles both CSVs and runs complete workflow
"""

from fastapi import APIRouter, HTTPException, status, UploadFile, File
from typing import List, Optional
import logging
import pandas as pd
import io

from services.agent.normalize_columns import parse_csv_content
from utils.schema.product_writer_agent import ProductCSVRow
from services.shopify.product import ShopifyProductService
from services.shopify.metafield import ShopifyMetafieldService
from services.shopify.product_filtering import ProductFilterService
from services.shopify.metafield_validator import MetafieldValidator
from services.shopify.product_image_service import ProductImageService
from services.agent.product_writer_service import ProductWriterService
from utils.logger import logger
from utils.tag_generator import TagGenerator
from utils.metafield_value_mapper import MetafieldValueMapper

router = APIRouter()


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
        except Exception as utf16_error:
            logger.warning(f"UTF-16 parsing failed: {str(utf16_error)}. Trying UTF-8...")
            try:
                # Fallback to UTF-8 if UTF-16 fails
                keywords_df = pd.read_csv(
                    io.StringIO(keywords_content.decode('utf-8')),
                    sep=',',
                    skiprows=2  # Apply skiprows here too for consistency
                )
            except Exception as utf8_error:
                logger.warning(f"UTF-8 with skiprows=2 failed: {str(utf8_error)}. Trying without skiprows...")
                keywords_df = pd.read_csv(
                    io.StringIO(keywords_content.decode('utf-8')),
                    sep=','
                )
        
        # Clean column names - strip whitespace and normalize
        keywords_df.columns = keywords_df.columns.str.strip()
        
        logger.info(f"Keywords CSV columns: {list(keywords_df.columns)}")
        logger.info(f"Keywords CSV shape: {keywords_df.shape}")
        logger.info(f"First row:\n{keywords_df.head(1)}")
        
        # Check if 'Avg. monthly searches' column exists
        if 'Avg. monthly searches' not in keywords_df.columns:
            logger.error(f"Available columns: {list(keywords_df.columns)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Keywords CSV must contain 'Avg. monthly searches' column. Found columns: {list(keywords_df.columns)}"
            )

        # Initialize writer service
        writer_service = ProductWriterService(keywords_df)
        
        product_dicts = []
        for product in validated_rows:
            # Use model_dump() to get ALL fields from the ProductCSVRow model
            product_dict = product.model_dump()
            
            # Clean up None values to empty strings for better processing
            for key, value in product_dict.items():
                if value is None:
                    product_dict[key] = ''
                    
            product_dicts.append(product_dict)
        
        
        # Generate content
        generated_results = writer_service.generate_content_for_products(product_dicts)

        print(f"✅ Content generation complete")

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


@router.post("/writer-agent-update-on-shopify", status_code=status.HTTP_200_OK)
async def update_existing_products_with_ai_content(
    products_file: UploadFile = File(..., description="Products CSV file"),
    keywords_file: UploadFile = File(..., description="Google Keyword Planner CSV file"),
    limit_per_row: int = 15
):
    """
    **UPDATE EXISTING SHOPIFY PRODUCTS WITH AI CONTENT**
    
    Steps:
    1. Parse products CSV (must contain SKU column)
    2. Parse keywords CSV (Google Keyword Planner format)
    3. Run products through LangGraph workflow to generate AI content
    4. Find existing Shopify products by SKU
    5. Update found products with generated content (title, description, SEO, styling tip metafields)
    
    **This endpoint updates existing products instead of creating new ones**
    """
    try:
        # STEP 1: Validate and parse PRODUCTS CSV
        if not products_file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Products file must be CSV"
            )
        
        # logger.info(f"📤 Step 1: Processing products file for update: {products_file.filename}")
        
        products_content = await products_file.read()
        csv_content = products_content.decode('utf-8')
        
        parsed_rows, errors = parse_csv_content(csv_content)
        # logger.info(f"✅ Parsed {len(parsed_rows)} rows from products CSV")
        
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
        
        # STEP 2: Validate keywords CSV
        if not keywords_file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Keywords file must be CSV"
            )
        
        # logger.info(f"📤 Step 2: Processing keywords file: {keywords_file.filename}")
        
        keywords_content = await keywords_file.read()
        
        try:
            keywords_df = pd.read_csv(
                io.StringIO(keywords_content.decode('utf-16')),
                sep='\t',
                skiprows=2  # Skip title and date rows
            )
        except Exception as utf16_error:
            logger.warning(f"UTF-16 parsing failed: {str(utf16_error)}. Trying UTF-8...")
            try:
                # Fallback to UTF-8 if UTF-16 fails
                keywords_df = pd.read_csv(
                    io.StringIO(keywords_content.decode('utf-8')),
                    sep=',',
                    skiprows=2  # Apply skiprows here too for consistency
                )
            except Exception as utf8_error:
                logger.warning(f"UTF-8 with skiprows=2 failed: {str(utf8_error)}. Trying without skiprows...")
                keywords_df = pd.read_csv(
                    io.StringIO(keywords_content.decode('utf-8')),
                    sep=','
                )
        
        # Clean column names - strip whitespace and normalize
        keywords_df.columns = keywords_df.columns.str.strip()
        
        # Check if 'Avg. monthly searches' column exists
        if 'Avg. monthly searches' not in keywords_df.columns:
            logger.error(f"Available columns: {list(keywords_df.columns)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Keywords CSV must contain 'Avg. monthly searches' column. Found columns: {list(keywords_df.columns)}"
            )

        # STEP 3: Initialize services
        writer_service = ProductWriterService(keywords_df)
        shopify_service = ShopifyProductService()
        
        # STEP 4: Prepare product data and generate AI content
        product_dicts = []
        for product in validated_rows:
            product_dict = product.model_dump()
            
            # Clean up None values to empty strings for better processing
            for key, value in product_dict.items():
                if value is None:
                    product_dict[key] = ''
                    
            product_dicts.append(product_dict)
        
        # Generate AI content
        # logger.info("🤖 Generating AI content for products...")
        generated_results = writer_service.generate_content_for_products(product_dicts)
        
        # STEP 5: Update existing Shopify products with generated content
        update_results = []
        products_not_found = []
        products_updated = []
        
        for idx, result in enumerate(generated_results):
            if not result['success']:
                update_results.append({
                    'sku': product_dicts[idx].get('sku', 'Unknown'),
                    'success': False,
                    'error': f"AI content generation failed: {result.get('error', 'Unknown error')}"
                })
                continue
            
            product_data = product_dicts[idx]
            logger.info(f"Processing update for product : {product_data}")
            generated_content = result['content']
            sku = product_data.get('product_sku', '').strip()
            
            if not sku:
                update_results.append({
                    'sku': 'Missing',
                    'success': False,
                    'error': "SKU is required for product updates"
                })
                continue
            
            try:
                # Search for product by SKU - SKUs are stored at variant level in Shopify
                logger.info(f"🔍 Searching for product with SKU: {sku}")
                
                # Try multiple search approaches to find the product
                search_queries = [
                    f"sku:{sku}",           # Standard SKU search
                    f"variant_sku:{sku}",   # Variant SKU field
                    f"variants.sku:{sku}",  # Nested variant SKU
                    sku                     # Direct search term
                ]
                
                search_result = None
                products = []
                
                # Try each search approach until we find the product
                for search_query in search_queries:
                    search_result = shopify_service.get_products(first=5, query_filter=search_query)
                    products = search_result.get('data', {}).get('products', {}).get('edges', [])
                    
                    if products:
                        logger.debug(f"   ✅ Found {len(products)} products with query: '{search_query}'")
                        break
                    else:
                        logger.info(f"   ❌ No products found with query: '{search_query}'")
                
                if not products:
                    products_not_found.append(sku)
                    update_results.append({
                        'sku': sku,
                        'success': False,
                        'error': f"Product with SKU '{sku}' not found in Shopify after trying multiple search methods"
                    })
                    continue
                
                # Take the first matching product
                product_node = products[0]['node']
                product_id = product_node['id']
                
                logger.debug(f"✅ Found product: {product_node['title']} (ID: {product_id})")
                
                # STEP 6: Build update payload for product fields
                product_update_input = {}
                
                if generated_content.get('title'):
                    product_update_input['title'] = generated_content['title']
                
                if generated_content.get('description'):
                    product_update_input['descriptionHtml'] = generated_content['description']
                
                # Ensure products remain in DRAFT status when updated
                product_update_input['status'] = 'DRAFT'
                 
                # Add these as metafields instead of using productUpdate.seo
                metafields_to_update = []

                if generated_content.get('seo_meta_title'):
                    metafields_to_update.append({
                        "ownerId": product_id,
                        "namespace": "global",
                        "key": "title_tag",
                        "value": generated_content['seo_meta_title'],
                        "type": "string"
                    })

                if generated_content.get('seo_meta_description'):
                    metafields_to_update.append({
                        "ownerId": product_id,
                        "namespace": "global",
                        "key": "description_tag",
                        "value": generated_content['seo_meta_description'],
                        "type": "string"
                    })

                # Add styling_tip with CORRECT namespace
                if generated_content.get('styling_tip'):
                    metafields_to_update.append({
                        "ownerId": product_id,
                        "namespace": "addfea",  # CORRECT namespace
                        "key": "styling_tip",
                        "value": str(generated_content['styling_tip']),
                        "type": "multi_line_text_field"  # CORRECT type
                    })

                # Update all metafields in one call
                if metafields_to_update:
                    logger.info(f"Updating {metafields_to_update} metafields for SKU: {sku}")
                    result=shopify_service.bulk_update_metafields(metafields_to_update)       
                    logger.info(f"Metafield update result: {result}")                 
                
                # STEP 7: Actually update the product in Shopify
                update_successful = True
                update_errors = []
                
                if product_update_input:
                    logger.info(f"📝 Updating product fields for SKU: {sku} with data: {product_update_input}")
                    try:
                        update_result = shopify_service.update_product(product_id, product_update_input)
                        
                        if update_result.get('data', {}).get('productUpdate', {}).get('userErrors'):
                            errors = update_result['data']['productUpdate']['userErrors']
                            update_errors.extend(errors)
                            logger.error(f"Product update errors for SKU {sku}: {errors}")
                            
                        if update_result.get('errors'):
                            update_errors.extend(update_result['errors'])
                            logger.error(f"GraphQL errors for SKU {sku}: {update_result['errors']}")
                            
                        logger.info(f"✅ Product fields updated successfully for SKU: {sku}")
                        
                    except Exception as e:
                        update_successful = False
                        update_errors.append(f"Product update exception: {str(e)}")
                        logger.error(f"Exception updating product {sku}: {str(e)}")
                
                # STEP 8: Update styling tip metafield if available
                metafields_to_update = []
                
                if generated_content.get('styling_tip'):
                    # Use single_line_text_field instead of multi_line_text_field for better compatibility
                    metafield_data = {
                        "ownerId": product_id,
                        "namespace": "custom",
                        "key": "styling_tip",
                        "value": str(generated_content['styling_tip']),  # Ensure it's a string
                        "type": "single_line_text_field"  # Changed from multi_line_text_field
                    }
                    metafields_to_update.append(metafield_data)
                else:
                    logger.warning(f"⚠️  No styling_tip found in generated content for SKU {sku}")
                    logger.info(f"   Generated content keys: {list(generated_content.keys())}")
                    if generated_content:
                        logger.info(f"   Sample generated content: {str(generated_content)[:300]}...")
                
                # Actually update metafields in Shopify
                if metafields_to_update:
                    logger.info(f"🏷️ Sending {len(metafields_to_update)} metafields to Shopify for SKU: {sku}")
                    logger.info(f"   GraphQL Variables: {{'metafields': {metafields_to_update}}}")
                    
                    try:
                        # Call the Shopify service method
                        logger.info(f"📞 Calling shopify_service.bulk_update_metafields()...")
                        metafield_result = shopify_service.bulk_update_metafields(metafields_to_update)
                        
                        # Log the full response for debugging
                        logger.info(f"📊 Raw Shopify API response for SKU {sku}: {metafield_result}")
                        
                        # Check for GraphQL errors first
                        if metafield_result.get('errors'):
                            update_errors.extend(metafield_result['errors'])
                            logger.error(f"❌ GraphQL errors for SKU {sku}: {metafield_result['errors']}")
                        
                        # Check the data structure
                        data = metafield_result.get('data', {})
                        metafields_set_data = data.get('metafieldsSet', {})
                        
                        # Check for user errors
                        user_errors = metafields_set_data.get('userErrors', [])
                        if user_errors:
                            update_errors.extend(user_errors)
                            logger.error(f"❌ Metafield user errors for SKU {sku}: {user_errors}")
                            for error in user_errors:
                                logger.error(f"   - Field: {error.get('field')}, Message: {error.get('message')}")
                        
                        # Check if metafields were actually created
                        metafields_created = metafields_set_data.get('metafields', [])
                        if metafields_created:
                            logger.info(f"✅ SUCCESS: {len(metafields_created)} metafields created for SKU {sku}:")
                            for i, mf in enumerate(metafields_created):
                                logger.info(f"   Metafield {i+1}:")
                                logger.info(f"     - ID: {mf.get('id')}")
                                logger.info(f"     - Namespace: {mf.get('namespace')}")
                                logger.info(f"     - Key: {mf.get('key')}")
                                logger.info(f"     - Type: {mf.get('type')}")
                                logger.info(f"     - Value: {mf.get('value')}")
                        else:
                            logger.error(f"❌ FAILED: No metafields were created for SKU {sku}")
                            logger.error(f"   Expected to create {len(metafields_to_update)} metafields")
                            logger.error(f"   Response data structure: {data}")
                            update_errors.append("No metafields were created in Shopify response")
                            
                    except Exception as e:
                        update_successful = False
                        update_errors.append(f"Metafield update exception: {str(e)}")
                        logger.error(f"💥 Exception during metafield update for {sku}: {str(e)}")
                        logger.error(f"   Exception type: {type(e).__name__}")
                        import traceback
                        logger.error(f"   Full traceback: {traceback.format_exc()}")
                else:
                    logger.warning(f"⚠️  No metafields to update for SKU: {sku} - styling_tip not found in generated content")
                
                # STEP 9: Record the result
                if update_successful and not update_errors:
                    products_updated.append(sku)
                    update_results.append({
                        'sku': sku,
                        'product_id': product_id,
                        'product_title': product_node['title'],
                        'success': True,
                        'updated_fields': {
                            'title': bool(generated_content.get('title')),
                            'description': bool(generated_content.get('description')),
                            'seo_title': bool(generated_content.get('seo_title')),
                            'seo_description': bool(generated_content.get('seo_description')),
                            'styling_tip': bool(generated_content.get('styling_tip'))
                        },
                        'generated_content': generated_content
                    })
                    logger.info(f"✅ Successfully updated product with SKU: {sku}")
                else:
                    update_results.append({
                        'sku': sku,
                        'product_id': product_id,
                        'product_title': product_node['title'],
                        'success': False,
                        'error': f"Update failed with errors: {update_errors}",
                        'generated_content': generated_content
                    })
                    logger.error(f"❌ Failed to update product with SKU: {sku} - Errors: {update_errors}")
                
            except Exception as e:
                logger.error(f"❌ Error processing product with SKU {sku}: {str(e)}")
                update_results.append({
                    'sku': sku,
                    'success': False,
                    'error': f"Processing failed: {str(e)}"
                })
        
        # STEP 8: Return comprehensive results
        success_count = sum(1 for r in update_results if r['success'])
        
        logger.info(f"🎯 Update complete: {success_count}/{len(update_results)} products updated successfully")
        
        return {
            "success": True,
            "message": f"Successfully updated {success_count}/{len(update_results)} products",
            "csv_summary": {
                "products_filename": products_file.filename,
                "keywords_filename": keywords_file.filename,
                "total_product_rows": len(parsed_rows),
                "validated_rows": len(validated_rows),
                "total_keywords": len(keywords_df)
            },
            "update_summary": {
                "total_processed": len(update_results),
                "successful_updates": success_count,
                "failed_updates": len(update_results) - success_count,
                "products_not_found": len(products_not_found),
                "skus_not_found": products_not_found,
                "skus_updated": products_updated
            },
            "detailed_results": update_results,
            "errors": errors if errors else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in writer-agent-update endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing update request: {str(e)}"
        )



@router.post("/writer-agent-create-draft-products", status_code=status.HTTP_200_OK)
async def create_draft_products_with_enhanced_tags(
    products_file: UploadFile = File(..., description="Products CSV file"),
    keywords_file: UploadFile = File(..., description="Google Keyword Planner CSV file"),
    limit_per_row: int = 15
):
    """
    **CREATE DRAFT SHOPIFY PRODUCTS WITH ENHANCED AI CONTENT AND SMART TAGS**
    
    This endpoint creates products in DRAFT status with:
    - AI-generated titles, descriptions, and SEO content
    - Enhanced tag generation system with 40+ relevant tags
    - Comprehensive metafields mapping
    - Image uploads from CSV URLs
    - Price range tags, availability tags, marketing tags
    
    Steps:
    1. Parse products CSV and keywords CSV
    2. Generate AI content for each product using LangGraph workflow  
    3. Generate comprehensive tags using enhanced TagGenerator
    4. Create DRAFT Shopify products with all metafields and images
    5. Return detailed results for both AI generation and Shopify creation
    
    **Products are created in DRAFT status for review before publishing**
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
        
        logger.debug(f"Validated {len(validated_rows)} products")
        
        # STEP 2: Validate and parse KEYWORDS CSV  
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
                skiprows=2
            )
        except Exception as utf16_error:
            logger.warning(f"UTF-16 parsing failed: {str(utf16_error)}. Trying UTF-8...")
            try:
                keywords_df = pd.read_csv(
                    io.StringIO(keywords_content.decode('utf-8')),
                    sep=',',
                    skiprows=2
                )
            except Exception as utf8_error:
                logger.warning(f"UTF-8 with skiprows=2 failed: {str(utf8_error)}. Trying without skiprows...")
                keywords_df = pd.read_csv(
                    io.StringIO(keywords_content.decode('utf-8')),
                    sep=','
                )
        
        keywords_df.columns = keywords_df.columns.str.strip()
        
        logger.info(f"Keywords CSV loaded with {len(keywords_df)} rows")
        logger.info(f"Keywords CSV columns: {list(keywords_df.columns)}")
        
        if 'Avg. monthly searches' not in keywords_df.columns:
            logger.error(f"Available columns: {list(keywords_df.columns)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Keywords CSV must contain 'Avg. monthly searches' column. Found columns: {list(keywords_df.columns)}"
            )

        # STEP 3: Initialize services
        writer_service = ProductWriterService(keywords_df)
        tag_generator = TagGenerator()
        
        # Prepare product data for AI content generation
        product_dicts = []
        for product in validated_rows:
            product_dict = product.model_dump()
            for key, value in product_dict.items():
                if value is None:
                    product_dict[key] = ''
            product_dicts.append(product_dict)
        
        # STEP 4: Generate AI content for all products
        logger.info(f"🤖 Step 3: Generating AI content for {len(product_dicts)} products")
        generated_results = writer_service.generate_content_for_products(product_dicts)
        
        success_count = sum(1 for r in generated_results if r['success'])
        logger.info(f"✅ Content generation complete: {success_count}/{len(generated_results)} successful")
        
        # STEP 5: Create Shopify products in DRAFT status
        logger.info(f"🛍️ Step 4: Creating DRAFT Shopify products")

        # Initialize Shopify services
        shopify_service = ShopifyProductService()
        metafield_service = ShopifyMetafieldService(shopify_service.client)

        shopify_results = []

        for result in generated_results:
            if not result['success']:
                shopify_results.append({
                    'product_sku': result['product_sku'],
                    'success': False,
                    'error': f"AI generation failed: {result['error']}",
                    'product_id': None,
                    'status': 'failed_ai_generation'
                })
                continue
            
            # Find matching CSV row by product_sku
            matching_csv_row = None
            for csv_row in validated_rows:
                if csv_row.product_sku == result['product_sku']:
                    matching_csv_row = csv_row
                    break
            
            if not matching_csv_row:
                shopify_results.append({
                    'product_sku': result['product_sku'],
                    'success': False,
                    'error': "Could not find matching CSV row",
                    'product_id': None,
                    'status': 'csv_row_not_found'
                })
                continue
            
            try:
                # Extract AI generated content
                ai_content = result['content']
                title = ai_content.get('title', f"Product {result['product_sku']}")
                description = ai_content.get('description', '')
                seo_title = ai_content.get('seo_meta_title', title)
                seo_description = ai_content.get('seo_meta_description', description[:160])
                styling_tip = ai_content.get('styling_tip', '')
                
                # Determine product type from category
                category_mapping = {
                    "Earrings": "Earrings",
                    "Necklace": "Necklaces", 
                    "Bracelet": "Bracelets",
                    "Ring": "Rings",
                    "Set": "Jewelry Sets",
                    "Bangles": "Bangles",
                    "Anklet": "Anklets",
                    "Maang Tikka": "Hair Accessories",
                    "Nose Ring": "Nose Jewelry"
                }
                product_type = category_mapping.get(matching_csv_row.category, "Jewelry")
                
                # ENHANCED TAG GENERATION
                logger.info(f"🏷️  Generating enhanced tags for SKU: {result['product_sku']}")
                
                product_data_for_tags = {
                    'product_sku': matching_csv_row.product_sku,
                    'category': matching_csv_row.category,
                    'style': matching_csv_row.style,
                    'finish': matching_csv_row.finish,
                    'work': matching_csv_row.work,
                    'components': matching_csv_row.components,
                    'finding': matching_csv_row.finding,
                    'primary_color': matching_csv_row.primary_color,
                    'secondary_color': matching_csv_row.secondary_color,
                    'occasions': matching_csv_row.occasions,
                    'gender': matching_csv_row.gender
                }
                
                # Get price from CSV
                price = None
                if hasattr(matching_csv_row, 'variant_price') and matching_csv_row.variant_price:
                    try:
                        price = float(matching_csv_row.variant_price)
                    except (ValueError, TypeError):
                        pass
                
                availability_days = 3
                
                # Generate comprehensive tags
                enhanced_tags = tag_generator.generate_comprehensive_tags(
                    product_data=product_data_for_tags,
                    ai_generated_content=ai_content,
                    price=price,
                    availability_days=availability_days
                )
                
                logger.info(f"✅ Generated {len(enhanced_tags)} enhanced tags for SKU: {result['product_sku']}")
                
                # Create base product in DRAFT status
                product_data = {
                    "title": title,
                    "descriptionHtml": f"<p>{description}</p>",
                    "productType": product_type,
                    "vendor": "MINAKI",
                    "tags": enhanced_tags,
                    "status": "DRAFT",
                    "seo": {
                        "title": seo_title,
                        "description": seo_description
                    }
                }
                
                # Store variant data
                variant_data = {
                    "title": "Default Title",
                    "inventoryQuantity": 0,
                    "taxable": True
                }
                
                if matching_csv_row.product_sku:
                    variant_data["sku"] = matching_csv_row.product_sku
                    variant_data["barcode"] = matching_csv_row.product_sku
                
                if price:
                    variant_data["price"] = str(price)
                
                # Create product in Shopify
                logger.info(f"🏗️  Creating DRAFT product in Shopify for SKU: {result['product_sku']}")
                product_result = shopify_service.create_product(product_data)
                
                if 'errors' in product_result or product_result.get('data', {}).get('productCreate', {}).get('userErrors'):
                    errors = product_result.get('errors', []) + product_result.get('data', {}).get('productCreate', {}).get('userErrors', [])
                    shopify_results.append({
                        'product_sku': result['product_sku'],
                        'success': False,
                        'error': f"Product creation failed: {str(errors)}",
                        'product_id': None,
                        'status': 'shopify_creation_failed'
                    })
                    continue
                
                created_product = product_result['data']['productCreate']['product']
                product_id = created_product['id']
                
                logger.info(f"✓ Created DRAFT product: {product_id} for SKU: {result['product_sku']}")
                
                # FIXED: Query product to get variant ID
                default_variant_id = None
                variant_update_success = False
                
                logger.info(f"   🔍 Querying product to get default variant ID...")
                variant_query_result = shopify_service.get_product_with_variant(product_id)
                
                if variant_query_result.get('data', {}).get('product', {}).get('variants', {}).get('edges'):
                    default_variant_id = variant_query_result['data']['product']['variants']['edges'][0]['node']['id']
                    logger.info(f"   ✅ Found default variant ID: {default_variant_id}")
                    
                    # Update variant with SKU, price, and barcode using productVariantUpdate
                    if variant_data:
                        try:
                            variant_update_mutation = """
                            mutation productVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
                                productVariantsBulkUpdate(productId: $productId, variants: $variants) {
                                    productVariants {
                                        id
                                        sku
                                        price
                                        barcode
                                    }
                                    userErrors {
                                        field
                                        message
                                    }
                                }
                            }
                            """
                            
                            # Build variant update input with correct structure for API 2025-01
                            variant_update_input = {
                                "id": default_variant_id,
                                "taxable": variant_data.get("taxable", True)
                            }

                            # Add barcode at top level (this is correct)
                            if variant_data.get("barcode"):
                                variant_update_input["barcode"] = variant_data["barcode"]

                            # Add price at top level (this is correct)
                            if variant_data.get("price"):
                                variant_update_input["price"] = variant_data["price"]

                            # SKU must be nested inside inventoryItem
                            if variant_data.get("sku"):
                                variant_update_input["inventoryItem"] = {
                                    "sku": variant_data["sku"]
                                }

                            logger.info(f"   📝 Updating variant: SKU={variant_data.get('sku')}, Price={variant_data.get('price')}")

                            variant_result = shopify_service.client.execute_query(
                                variant_update_mutation,
                                {
                                    'productId': product_id,
                                    'variants': [variant_update_input]
                                }
                            )
                            
                            # Check for GraphQL errors
                            if variant_result.get('errors'):
                                logger.error(f"   ❌ GraphQL errors: {variant_result.get('errors')}")
                            
                            # Check for user errors
                            variant_errors = variant_result.get('data', {}).get('productVariantUpdate', {}).get('userErrors', [])
                            if variant_errors:
                                logger.error(f"   ❌ Variant user errors: {variant_errors}")
                                for err in variant_errors:
                                    logger.error(f"      - {err.get('field')}: {err.get('message')}")
                            
                            # Check if update was successful
                            updated_variant = variant_result.get('data', {}).get('productVariantUpdate', {}).get('productVariant')
                            if updated_variant:
                                logger.info(f"   ✅ SUCCESS: Updated variant")
                                logger.info(f"      - SKU: {updated_variant.get('sku')}")
                                logger.info(f"      - Price: {updated_variant.get('price')}")
                                logger.info(f"      - Barcode: {updated_variant.get('barcode')}")
                                variant_update_success = True
                            else:
                                logger.error(f"   ❌ FAILED: No variant returned in response")
                                logger.error(f"      Full response: {variant_result}")
                        
                        except Exception as e:
                            logger.error(f"   ❌ Exception updating variant: {str(e)}", exc_info=True)
                else:
                    logger.warning(f"   ⚠️  Could not find variant in query response")                
                
                # ============================================
                # CREATE METAFIELDS USING ShopifyMetafieldService
                # ============================================
                
                metafields_created = []
                import json
                import time
                
                # Helper to track created metafields
                def create_metafield_safe(namespace: str, key: str, value: str, field_type: str = "single_line_text_field") -> bool:
                    """Create metafield with error handling"""
                    if not value:
                        return False
                    
                    try:
                        result = metafield_service.add_or_update_metafield(
                            product_id=product_id,
                            namespace=namespace,
                            key=key,
                            value=value,
                            field_type=field_type
                        )
                        
                        # Check if successful
                        if result.get('data', {}).get('metafieldsSet', {}).get('metafields'):
                            metafields_created.append(f"{namespace}.{key}")
                            logger.debug(f"   ✓ Created {namespace}.{key}")
                            time.sleep(0.1)  # Rate limiting
                            return True
                        else:
                            user_errors = result.get('data', {}).get('metafieldsSet', {}).get('userErrors', [])
                            if user_errors:
                                logger.debug(f"   ⊘ Skipped {namespace}.{key}: {user_errors}")
                            return False
                    except Exception as e:
                        logger.debug(f"   ⊘ Skipped {namespace}.{key}: {str(e)}")
                        return False
                
                logger.info(f"   📝 Creating metafields for SKU: {result['product_sku']}")
                
                # Gender - 'addfea' namespace
                if matching_csv_row.gender:
                    mapped_gender = MetafieldValueMapper.map_gender(matching_csv_row.gender)
                    create_metafield_safe("addfea", "gender", mapped_gender, "single_line_text_field")
                
                # Style - 'addfea' namespace
                if matching_csv_row.style:
                    create_metafield_safe("addfea", "style", matching_csv_row.style, "single_line_text_field")
                
                # Group (category) - 'addfea' namespace
                if matching_csv_row.category:
                    create_metafield_safe("addfea", "group", matching_csv_row.category, "single_line_text_field")
                
                # Components - 'custom' namespace as LIST
                if matching_csv_row.components:
                    components_list = [comp.strip() for comp in matching_csv_row.components.split(',') if comp.strip()]
                    create_metafield_safe("custom", "components", json.dumps(components_list), "list.single_line_text_field")
                
                # Colors - 'addfea' namespace as LIST
                colors = []
                if matching_csv_row.primary_color:
                    colors.append(matching_csv_row.primary_color)
                if matching_csv_row.secondary_color:
                    colors.append(matching_csv_row.secondary_color)
                if colors:
                    create_metafield_safe("addfea", "color", json.dumps(colors), "list.single_line_text_field")
                
                # Work/Craftsmanship - using label/data pattern
                if matching_csv_row.work:
                    create_metafield_safe("addfea", "label1", "Stone Setting", "single_line_text_field")
                    create_metafield_safe("addfea", "data1", json.dumps([matching_csv_row.work]), "list.single_line_text_field")
                
                # Finish - using label/data pattern
                if matching_csv_row.finish:
                    mapped_finish = MetafieldValueMapper.map_finish(matching_csv_row.finish)
                    create_metafield_safe("addfea", "label2", "Finish", "single_line_text_field")
                    create_metafield_safe("addfea", "data2", mapped_finish, "single_line_text_field")
                
                # Finding - using label/data pattern
                if matching_csv_row.finding:
                    create_metafield_safe("addfea", "label3", "Finding", "single_line_text_field")
                    create_metafield_safe("addfea", "data3", matching_csv_row.finding, "single_line_text_field")
                
                # Occasions - 'addfea' namespace as LIST
                if matching_csv_row.occasions:
                    occasions_list = [occ.strip() for occ in matching_csv_row.occasions.split(',') if occ.strip()]
                    create_metafield_safe("addfea", "occasion", json.dumps(occasions_list), "list.single_line_text_field")
                
                # Styling tip - 'addfea' namespace with HTML formatting
                if styling_tip:
                    styling_html = f"<ul>\n<li>{styling_tip}</li>\n</ul>"
                    create_metafield_safe("addfea", "styling_tip", styling_html, "multi_line_text_field")
                
                # SEO metafields - 'global' namespace
                create_metafield_safe("global", "title_tag", seo_title, "string")
                create_metafield_safe("global", "description_tag", seo_description, "string")
                
                # Meta description - 'meta' namespace
                create_metafield_safe("meta", "description_excerpt", seo_description, "multi_line_text_field")
                
                # Estimate dates - 'meta' namespace
                create_metafield_safe("meta", "estimateStartDate", "5", "number_integer")
                create_metafield_safe("meta", "estimateEndDate", "10", "number_integer")
                
                logger.info(f"   ✅ Created {len(metafields_created)} metafields")
                
                # Process and upload images to Shopify
                uploaded_images = []
                image_urls = [
                    matching_csv_row.high_resolution_1,
                    matching_csv_row.high_resolution_2,
                    matching_csv_row.high_resolution_3,
                    matching_csv_row.high_resolution_4,
                    matching_csv_row.high_resolution_5
                ]
                
                valid_image_urls = []
                for url in image_urls:
                    if url and url.strip():
                        valid_image_urls.append(url)
                
                if valid_image_urls:
                    try:
                        logger.info(f"📸 Processing {len(valid_image_urls)} images for SKU: {result['product_sku']}")
                        
                        image_service = ProductImageService(shopify_service.client)
                        uploaded_images = image_service.add_images_to_product_via_mutation(
                            product_id=product_id,
                            image_urls=valid_image_urls,
                            title=title
                        )
                        
                        successful_uploads = sum(1 for img in uploaded_images if img['success'])
                        logger.info(f"✓ Successfully uploaded {successful_uploads}/{len(valid_image_urls)} images")
                        
                        if successful_uploads < len(valid_image_urls):
                            failed_images = [img for img in uploaded_images if not img['success']]
                            logger.warning(f"⚠️  {len(failed_images)} images failed:")
                            for failed_img in failed_images:
                                logger.warning(f"   - Position {failed_img.get('position')}: {failed_img.get('error')}")
                        
                    except Exception as e:
                        logger.error(f"Failed to upload images: {str(e)}", exc_info=True)
                        uploaded_images = [{
                            'success': False,
                            'error': str(e),
                            'url': url
                        } for url in valid_image_urls]
                else:
                    logger.info(f"⚠️  No image URLs found for SKU {result['product_sku']}")
                
                # Comprehensive result tracking
                shopify_results.append({
                    'product_sku': result['product_sku'],
                    'success': True,
                    'error': None,
                    'product_id': product_id,
                    'product_handle': created_product.get('handle'),
                    'product_title': title,
                    'status': 'draft_created',
                    'variant_update_success': variant_update_success,
                    'enhanced_tags_count': len(enhanced_tags),
                    'enhanced_tags_sample': enhanced_tags[:15],
                    'metafields_created': metafields_created,
                    'images_uploaded': uploaded_images,
                    'total_images': len(valid_image_urls),
                    'successful_images': sum(1 for img in uploaded_images if img['success']),
                    'ai_content_quality': {
                        'has_title': bool(ai_content.get('title')),
                        'has_description': bool(ai_content.get('description')),
                        'has_seo_title': bool(ai_content.get('seo_meta_title')),
                        'has_seo_description': bool(ai_content.get('seo_meta_description')),
                        'has_styling_tip': bool(ai_content.get('styling_tip'))
                    }
                })
                
                logger.info(f"✅ Successfully created complete DRAFT product for SKU: {result['product_sku']}")
                
            except Exception as e:
                logger.error(f"Error creating Shopify product for SKU {result['product_sku']}: {str(e)}")
                shopify_results.append({
                    'product_sku': result['product_sku'],
                    'success': False,
                    'error': str(e),
                    'product_id': None,
                    'status': 'creation_exception'
                })

        # STEP 6: Calculate final statistics
        shopify_success_count = sum(1 for r in shopify_results if r['success'])
        total_images_uploaded = sum(r.get('successful_images', 0) for r in shopify_results if r['success'])
        total_metafields_created = sum(len(r.get('metafields_created', [])) for r in shopify_results if r['success'])
        
        logger.info(f"🎯 DRAFT product creation complete!")
        logger.info(f"   ✅ {shopify_success_count}/{len(shopify_results)} products created successfully")
        logger.info(f"   📸 {total_images_uploaded} images uploaded")
        logger.info(f"   🏷️ {total_metafields_created} metafields created")
        
        success_summary = {
            "products_created": shopify_success_count,
            "total_attempted": len(shopify_results),
            "success_rate": f"{(shopify_success_count/len(shopify_results)*100):.1f}%" if shopify_results else "0%",
            "images_uploaded": total_images_uploaded,
            "metafields_created": total_metafields_created
        }
        
        return {
            "success": True,
            "message": f"Successfully created {shopify_success_count}/{len(shopify_results)} DRAFT products with enhanced tags, {total_images_uploaded} images uploaded",
            "success_summary": success_summary,
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
                "failed": len(generated_results) - success_count
            },
            "shopify_creation": {
                "total_processed": len(shopify_results),
                "successful": shopify_success_count,
                "failed": len(shopify_results) - shopify_success_count,
                "total_images_uploaded": total_images_uploaded,
                "total_metafields_created": total_metafields_created
            },
            "detailed_results": shopify_results,
            "errors": errors if errors else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in writer-agent-create-draft-products endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing request: {str(e)}"
        )