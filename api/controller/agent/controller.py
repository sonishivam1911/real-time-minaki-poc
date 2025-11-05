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