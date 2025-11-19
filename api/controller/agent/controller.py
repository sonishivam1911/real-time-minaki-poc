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
from utils.logger import logger
from utils.tag_generator import TagGenerator

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
        except:
            # Fallback to UTF-8 if UTF-16 fails
            keywords_df = pd.read_csv(
                io.StringIO(keywords_content.decode('utf-8')),
                sep=',',
                skiprows=0
            )
        
        # logger.info(f"Keywords CSV columns: {keywords_df.head()}")

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
                skiprows=2  # Skip title and date rows
            )
        except:
            # Fallback to UTF-8 if UTF-16 fails
            keywords_df = pd.read_csv(
                io.StringIO(keywords_content.decode('utf-8')),
                sep=',',
                skiprows=0
            )
        
        logger.info(f"Keywords CSV loaded with {len(keywords_df)} rows")

        # STEP 3: Initialize services
        writer_service = ProductWriterService(keywords_df)
        tag_generator = TagGenerator()
        
        # Prepare product data for AI content generation
        product_dicts = []
        for product in validated_rows:
            product_dict = product.model_dump()
            
            # Clean up None values to empty strings for better processing
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

        # Initialize Shopify service
        shopify_service = ShopifyProductService()

        # Create mapping for metafields
        from utils.schema.product_writer_agent import ProductMetafieldMapping
        mapping = ProductMetafieldMapping()

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
                ai_content = result['generated_output']['action_input']
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
                
                # ENHANCED TAG GENERATION - This is the key improvement!
                logger.info(f"🏷️  Generating enhanced tags for SKU: {result['product_sku']}")
                
                # Prepare product data for tag generation
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
                
                # Get price from CSV if available (assuming it might be in variant_price or price field)
                price = None
                if hasattr(matching_csv_row, 'variant_price') and matching_csv_row.variant_price:
                    try:
                        price = float(matching_csv_row.variant_price)
                    except (ValueError, TypeError):
                        pass
                
                # Generate availability days (default 3 days for quick shipping)
                availability_days = 3  # You can make this configurable
                
                # Generate comprehensive tags using the enhanced system
                enhanced_tags = tag_generator.generate_comprehensive_tags(
                    product_data=product_data_for_tags,
                    ai_generated_content=ai_content,
                    price=price,
                    availability_days=availability_days
                )
                
                logger.info(f"✅ Generated {len(enhanced_tags)} enhanced tags for SKU: {result['product_sku']}")
                logger.debug(f"   Tags: {enhanced_tags[:10]}...")  # Log first 10 tags for debugging
                
                # Create base product in DRAFT status
                product_data = {
                    "title": title,
                    "descriptionHtml": f"<p>{description}</p>",
                    "productType": product_type,
                    "vendor": "MINAKI",
                    "tags": enhanced_tags,  # Use our enhanced tags instead of basic ones
                    "status": "DRAFT",  # Create in DRAFT status for review
                    "seo": {
                        "title": seo_title,
                        "description": seo_description
                    },
                    "variants": [{
                        "title": "Default Title",
                        "inventoryQuantity": 0,
                        "taxable": True
                    }]
                }
                
                if matching_csv_row.product_sku:
                    product_data["variants"][0]["sku"] = matching_csv_row.product_sku
                    product_data["variants"][0]["barcode"] = matching_csv_row.product_sku
                
                # Add price if available
                if price:
                    product_data["variants"][0]["price"] = str(price)
                
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
                
                # Create metafields with enhanced error handling
                metafields_created = []
                import json
                import time
                
                # Gender metafield
                if matching_csv_row.gender:
                    try:
                        shopify_service.add_metafield_to_product(
                            product_id=product_id,
                            namespace=mapping.gender_namespace,
                            key=mapping.gender_key,
                            value=matching_csv_row.gender,
                            field_type="single_line_text_field"
                        )
                        metafields_created.append(f"{mapping.gender_namespace}.{mapping.gender_key}")
                        time.sleep(0.2)
                    except Exception as e:
                        logger.warning(f"Failed to create gender metafield: {str(e)}")
                
                # Style metafield
                if matching_csv_row.style:
                    try:
                        shopify_service.add_metafield_to_product(
                            product_id=product_id,
                            namespace=mapping.style_namespace,
                            key=mapping.style_key,
                            value=matching_csv_row.style,
                            field_type="single_line_text_field"
                        )
                        metafields_created.append(f"{mapping.style_namespace}.{mapping.style_key}")
                        time.sleep(0.2)
                    except Exception as e:
                        logger.warning(f"Failed to create style metafield: {str(e)}")
                
                # Components metafield (as list)
                if matching_csv_row.components:
                    try:
                        components_list = [comp.strip() for comp in matching_csv_row.components.split(',') if comp.strip()]
                        shopify_service.add_metafield_to_product(
                            product_id=product_id,
                            namespace=mapping.components_namespace,
                            key=mapping.components_key,
                            value=json.dumps(components_list),
                            field_type="list.single_line_text_field"
                        )
                        metafields_created.append(f"{mapping.components_namespace}.{mapping.components_key}")
                        time.sleep(0.2)
                    except Exception as e:
                        logger.warning(f"Failed to create components metafield: {str(e)}")
                
                # Colors metafield (as list)
                colors = []
                if matching_csv_row.primary_color:
                    colors.append(matching_csv_row.primary_color)
                if matching_csv_row.secondary_color:
                    colors.append(matching_csv_row.secondary_color)
                if colors:
                    try:
                        shopify_service.add_metafield_to_product(
                            product_id=product_id,
                            namespace=mapping.color_namespace,
                            key=mapping.color_key,
                            value=json.dumps(colors),
                            field_type="list.single_line_text_field"
                        )
                        metafields_created.append(f"{mapping.color_namespace}.{mapping.color_key}")
                        time.sleep(0.2)
                    except Exception as e:
                        logger.warning(f"Failed to create color metafield: {str(e)}")
                
                # Work/Stone Setting with label
                if matching_csv_row.work:
                    try:
                        # Label
                        shopify_service.add_metafield_to_product(
                            product_id=product_id,
                            namespace=mapping.work_label_namespace,
                            key=mapping.work_label_key,
                            value="Stone Setting",
                            field_type="single_line_text_field"
                        )
                        time.sleep(0.2)
                        
                        # Data
                        shopify_service.add_metafield_to_product(
                            product_id=product_id,
                            namespace=mapping.work_namespace,
                            key=mapping.work_key,
                            value=json.dumps([matching_csv_row.work]),
                            field_type="list.single_line_text_field"
                        )
                        metafields_created.append(f"{mapping.work_namespace}.{mapping.work_key}")
                        time.sleep(0.2)
                    except Exception as e:
                        logger.warning(f"Failed to create work metafields: {str(e)}")
                
                # Finish with label
                if matching_csv_row.finish:
                    try:
                        # Label
                        shopify_service.add_metafield_to_product(
                            product_id=product_id,
                            namespace=mapping.base_metal_label_namespace,
                            key=mapping.base_metal_label_key,
                            value="Finish",
                            field_type="single_line_text_field"
                        )
                        time.sleep(0.2)
                        
                        # Data
                        shopify_service.add_metafield_to_product(
                            product_id=product_id,
                            namespace=mapping.base_metal_namespace,
                            key=mapping.base_metal_key,
                            value=matching_csv_row.finish,
                            field_type="single_line_text_field"
                        )
                        metafields_created.append(f"{mapping.base_metal_namespace}.{mapping.base_metal_key}")
                        time.sleep(0.2)
                    except Exception as e:
                        logger.warning(f"Failed to create finish metafields: {str(e)}")
                
                # Finding with label
                if matching_csv_row.finding:
                    try:
                        # Label
                        shopify_service.add_metafield_to_product(
                            product_id=product_id,
                            namespace=mapping.finding_label_namespace,
                            key=mapping.finding_label_key,
                            value="Finding",
                            field_type="single_line_text_field"
                        )
                        time.sleep(0.2)
                        
                        # Data
                        shopify_service.add_metafield_to_product(
                            product_id=product_id,
                            namespace=mapping.finding_namespace,
                            key=mapping.finding_key,
                            value=matching_csv_row.finding,
                            field_type="single_line_text_field"
                        )
                        metafields_created.append(f"{mapping.finding_namespace}.{mapping.finding_key}")
                        time.sleep(0.2)
                    except Exception as e:
                        logger.warning(f"Failed to create finding metafields: {str(e)}")
                
                # Occasions metafield (as list)
                if matching_csv_row.occasions:
                    try:
                        occasions_list = [occ.strip() for occ in matching_csv_row.occasions.split(',') if occ.strip()]
                        shopify_service.add_metafield_to_product(
                            product_id=product_id,
                            namespace=mapping.occasions_namespace,
                            key=mapping.occasions_key,
                            value=json.dumps(occasions_list),
                            field_type="list.single_line_text_field"
                        )
                        metafields_created.append(f"{mapping.occasions_namespace}.{mapping.occasions_key}")
                        time.sleep(0.2)
                    except Exception as e:
                        logger.warning(f"Failed to create occasions metafield: {str(e)}")
                
                # Styling tip from AI
                if styling_tip:
                    try:
                        shopify_service.add_metafield_to_product(
                            product_id=product_id,
                            namespace=mapping.styling_tip_namespace,
                            key=mapping.styling_tip_key,
                            value=styling_tip,
                            field_type="multi_line_text_field"
                        )
                        metafields_created.append(f"{mapping.styling_tip_namespace}.{mapping.styling_tip_key}")
                        time.sleep(0.2)
                    except Exception as e:
                        logger.warning(f"Failed to create styling tip metafield: {str(e)}")
                
                # SEO metafields
                try:
                    shopify_service.add_metafield_to_product(
                        product_id=product_id,
                        namespace=mapping.seo_title_namespace,
                        key=mapping.seo_title_key,
                        value=seo_title,
                        field_type="string"
                    )
                    metafields_created.append(f"{mapping.seo_title_namespace}.{mapping.seo_title_key}")
                    time.sleep(0.2)
                except Exception as e:
                    logger.warning(f"Failed to create SEO title metafield: {str(e)}")
                
                try:
                    shopify_service.add_metafield_to_product(
                        product_id=product_id,
                        namespace=mapping.seo_description_namespace,
                        key=mapping.seo_description_key,
                        value=seo_description,
                        field_type="string"
                    )
                    metafields_created.append(f"{mapping.seo_description_namespace}.{mapping.seo_description_key}")
                    time.sleep(0.2)
                except Exception as e:
                    logger.warning(f"Failed to create SEO description metafield: {str(e)}")
                
                try:
                    shopify_service.add_metafield_to_product(
                        product_id=product_id,
                        namespace=mapping.meta_description_namespace,
                        key=mapping.meta_description_key,
                        value=seo_description,
                        field_type="multi_line_text_field"
                    )
                    metafields_created.append(f"{mapping.meta_description_namespace}.{mapping.meta_description_key}")
                    time.sleep(0.2)
                except Exception as e:
                    logger.warning(f"Failed to create meta description metafield: {str(e)}")
                
                # Process and upload images to Shopify
                uploaded_images = []
                image_urls = [
                    matching_csv_row.high_resolution_1,
                    matching_csv_row.high_resolution_2,
                    matching_csv_row.high_resolution_3,
                    matching_csv_row.high_resolution_4,
                    matching_csv_row.high_resolution_5
                ]
                
                # Filter out empty URLs
                valid_image_urls = [url for url in image_urls if url and url.strip()]
                
                if valid_image_urls:
                    try:
                        logger.info(f"📸 Uploading {len(valid_image_urls)} images for SKU: {result['product_sku']}")
                        uploaded_images = shopify_service.add_multiple_images_to_product(
                            product_id=product_id,
                            image_urls=valid_image_urls,
                            title=title
                        )
                        
                        successful_uploads = sum(1 for img in uploaded_images if img['success'])
                        logger.info(f"✓ Uploaded {successful_uploads}/{len(valid_image_urls)} images for SKU: {result['product_sku']}")
                        
                    except Exception as e:
                        logger.warning(f"Failed to upload images for SKU {result['product_sku']}: {str(e)}")
                        uploaded_images = [{
                            'success': False,
                            'error': str(e),
                            'url': url
                        } for url in valid_image_urls]
                
                # Comprehensive result tracking
                shopify_results.append({
                    'product_sku': result['product_sku'],
                    'success': True,
                    'error': None,
                    'product_id': product_id,
                    'product_handle': created_product.get('handle'),
                    'product_title': title,
                    'status': 'draft_created',
                    'enhanced_tags_count': len(enhanced_tags),
                    'enhanced_tags_sample': enhanced_tags[:15],  # Show first 15 tags as sample
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
        
        # Success summary
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
                "failed": len(generated_results) - success_count,
                "ai_quality_metrics": {
                    "avg_title_length": sum(len(r.get('generated_output', {}).get('action_input', {}).get('title', '')) for r in generated_results if r['success']) // max(success_count, 1),
                    "avg_description_length": sum(len(r.get('generated_output', {}).get('action_input', {}).get('description', '')) for r in generated_results if r['success']) // max(success_count, 1)
                }
            },
            "shopify_creation": {
                "total_processed": len(shopify_results),
                "successful": shopify_success_count,
                "failed": len(shopify_results) - shopify_success_count,
                "total_images_uploaded": total_images_uploaded,
                "total_metafields_created": total_metafields_created,
                "enhanced_tags_info": {
                    "avg_tags_per_product": sum(r.get('enhanced_tags_count', 0) for r in shopify_results if r['success']) // max(shopify_success_count, 1),
                    "tag_categories": ["price_range", "availability", "marketing", "category", "style", "color", "finish", "components", "occasions", "seo"]
                }
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