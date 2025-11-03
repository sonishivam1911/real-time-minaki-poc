# """
# AGENT CONTROLLER (UPDATED)
# Handles both CSVs and runs complete workflow
# """

# from fastapi import APIRouter, HTTPException, status, UploadFile, File
# from typing import List
# import logging
# import pandas as pd
# import io

# from services.agent.normalize_columns import parse_csv_content
# from utils.schema.product_writer_agent import ProductCSVRow
# from services.shopify.product import ShopifyProductService
# from services.shopify.product_filtering import ProductFilterService
# from services.agent.product_writer_service import ProductWriterService

# router = APIRouter()
# logger = logging.getLogger("Agent Controller")


# @router.post("/writer-agent", status_code=status.HTTP_200_OK)
# async def upload_and_generate_content(
#     products_file: UploadFile = File(..., description="Products CSV file"),
#     keywords_file: UploadFile = File(..., description="Google Keyword Planner CSV file"),
#     limit_per_row: int = 15
# ):
#     """
#     **COMPLETE WORKFLOW: Upload CSVs → Generate AI Content → Create Shopify Products**
    
#     Steps:
#     1. Parse products CSV
#     2. Parse keywords CSV (Google Keyword Planner format)
#     3. Generate AI content for each product using LangGraph workflow
#     4. Create complete Shopify products with all metafields and images
#     5. Return detailed results for both AI generation and Shopify creation
    
#     **This is the MAIN endpoint for complete product creation!**
#     """
#     try:
#         # STEP 1: Validate and parse PRODUCTS CSV
#         if not products_file.filename.endswith('.csv'):
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Products file must be CSV"
#             )
        
#         logger.info(f"📤 Step 1: Processing products file: {products_file.filename}")
        
#         products_content = await products_file.read()
#         csv_content = products_content.decode('utf-8')
        
#         parsed_rows, errors = parse_csv_content(csv_content)
#         logger.info(f"✅ Parsed {len(parsed_rows)} rows from products CSV")
        
#         if not parsed_rows:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="No valid rows found in products CSV"
#             )
            
#         validated_rows = []
#         for idx, row in enumerate(parsed_rows):
#             try:
#                 validated_row = ProductCSVRow(**row)
#                 validated_rows.append(validated_row)
#             except Exception as e:
#                 logger.warning(f"Row {idx + 2} validation failed: {str(e)}")
        
#         logger.debug(f"Validated row is : {validated_rows}")
        
#         if not keywords_file.filename.endswith('.csv'):
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Keywords file must be CSV"
#             )
        
#         logger.info(f"📤 Step 2: Processing keywords file: {keywords_file.filename}")
        
#         keywords_content = await keywords_file.read()
        
#         try:
#             keywords_df = pd.read_csv(
#                 io.StringIO(keywords_content.decode('utf-16')),
#                 sep='\t',
#                 skiprows=2  # Skip title and date rows
#             )
#         except:
#             # Fallback to UTF-8 if UTF-16 fails
#             keywords_df = pd.read_csv(
#                 io.StringIO(keywords_content.decode('utf-8')),
#                 sep=',',
#                 skiprows=0
#             )
        
#         logger.info(f"Keyords CSV columns: {keywords_df.head()}")

#         # Initialize writer service
#         writer_service = ProductWriterService(keywords_df)
        
#         product_dicts = []
#         for product in validated_rows:
#             # Use attribute access (.property) instead of dictionary access ['property']
#             # Or use model_dump() to convert the entire model to a dictionary
#             product_dict = {
#                 'product_sku': product.product_sku if product.product_sku else 'Unknown',
#                 'category': product.category if product.category else '',
#                 'line': product.line if product.line else '',
#                 'style': product.style if product.style else '',
#                 'finish': product.finish if product.finish else '',
#                 'work': product.work if product.work else '',
#                 'components': product.components if product.components else '',
#                 'finding': product.finding if product.finding else '',
#                 'primary_color': product.primary_color if product.primary_color else '',
#                 'secondary_color': product.secondary_color if product.secondary_color else '',
#                 'occasions': product.occasions if product.occasions else '',
#             }
#             product_dicts.append(product_dict)
        
        
#         # Generate content
#         generated_results = writer_service.generate_content_for_products(product_dicts)
        
#         logger.info(f"✅ Content generation complete")
        
#         logger.info(f"Generated Content is. : {generated_results}")
    
#         success_count = sum(1 for r in generated_results if r['success'])
        
#         # STEP 3: Create Shopify Products from generated content
#         logger.info(f"🛍️ Step 3: Creating Shopify products")

#         # Initialize Shopify service
#         shopify_service = ShopifyProductService()

#         # Create mapping for metafields
#         from utils.schema.product_writer_agent import ProductMetafieldMapping
#         mapping = ProductMetafieldMapping()

#         shopify_results = []

#         for result in generated_results:
#             if not result['success']:
#                 shopify_results.append({
#                     'product_sku': result['product_sku'],
#                     'success': False,
#                     'error': f"AI generation failed: {result['error']}",
#                     'product_id': None
#                 })
#                 continue
            
#             # Find matching CSV row by product_sku
#             matching_csv_row = None
#             for csv_row in validated_rows:
#                 if csv_row.product_sku == result['product_sku']:
#                     matching_csv_row = csv_row
#                     break
            
#             if not matching_csv_row:
#                 shopify_results.append({
#                     'product_sku': result['product_sku'],
#                     'success': False,
#                     'error': "Could not find matching CSV row",
#                     'product_id': None
#                 })
#                 continue
            
#             try:
#                 # Extract AI generated content
#                 ai_content = result['generated_output']['action_input']
#                 title = ai_content.get('title', f"Product {result['product_sku']}")
#                 description = ai_content.get('description', '')
#                 seo_title = ai_content.get('seo_meta_title', title)
#                 seo_description = ai_content.get('seo_meta_description', description[:160])
#                 styling_tip = ai_content.get('styling_tip', '')
                
#                 # Determine product type from category
#                 category_mapping = {
#                     "Earrings": "Earrings",
#                     "Necklace": "Necklaces", 
#                     "Bracelet": "Bracelets",
#                     "Ring": "Rings",
#                     "Set": "Jewelry Sets",
#                     "Bangles": "Bangles",
#                     "Anklet": "Anklets",
#                     "Maang Tikka": "Hair Accessories"
#                 }
#                 product_type = category_mapping.get(matching_csv_row.category, "Jewelry")
                
#                 # Generate tags
#                 tags = []
#                 if matching_csv_row.category:
#                     tags.append(matching_csv_row.category.lower())
#                 if matching_csv_row.style:
#                     tags.extend([matching_csv_row.style, f"{matching_csv_row.style} Jewellery"])
#                 if matching_csv_row.primary_color:
#                     tags.append(matching_csv_row.primary_color)
#                 if matching_csv_row.secondary_color:
#                     tags.append(matching_csv_row.secondary_color)
#                 if matching_csv_row.finish:
#                     tags.append(f"Finish:{matching_csv_row.finish}")
#                 if matching_csv_row.finding:
#                     tags.append(f"Finding:{matching_csv_row.finding}")
#                 if matching_csv_row.gender:
#                     tags.append(matching_csv_row.gender)
#                 tags.extend(["jewellery", "wedding", "Vendor  MINAKI"])
                
#                 # Create base product
#                 product_data = {
#                     "title": title,
#                     "descriptionHtml": f"<p>{description}</p>",
#                     "productType": product_type,
#                     "vendor": "MINAKI",
#                     "tags": list(set(tags)),
#                     "status": "ACTIVE",
#                     "seo": {
#                         "title": seo_title,
#                         "description": seo_description
#                     },
#                     "variants": [{
#                         "title": "Default Title",
#                         "inventoryQuantity": 0,
#                         "taxable": True
#                     }]
#                 }
                
#                 if matching_csv_row.product_sku:
#                     product_data["variants"][0]["sku"] = matching_csv_row.product_sku
#                     product_data["variants"][0]["barcode"] = matching_csv_row.product_sku
                
#                 # Create product in Shopify
#                 product_result = shopify_service.create_product(product_data)
                
#                 if 'errors' in product_result or product_result.get('data', {}).get('productCreate', {}).get('userErrors'):
#                     errors = product_result.get('errors', []) + product_result.get('data', {}).get('productCreate', {}).get('userErrors', [])
#                     shopify_results.append({
#                         'product_sku': result['product_sku'],
#                         'success': False,
#                         'error': f"Product creation failed: {str(errors)}",
#                         'product_id': None
#                     })
#                     continue
                
#                 created_product = product_result['data']['productCreate']['product']
#                 product_id = created_product['id']
                
#                 logger.info(f"✓ Created product: {product_id} for SKU: {result['product_sku']}")
                
#                 # Create metafields
#                 metafields_created = []
#                 import json
#                 import time
                
#                 # Gender
#                 if matching_csv_row.gender:
#                     try:
#                         shopify_service.add_metafield_to_product(
#                             product_id=product_id,
#                             namespace=mapping.gender_namespace,
#                             key=mapping.gender_key,
#                             value=matching_csv_row.gender,
#                             field_type="single_line_text_field"
#                         )
#                         metafields_created.append(f"{mapping.gender_namespace}.{mapping.gender_key}")
#                         time.sleep(0.2)
#                     except Exception as e:
#                         logger.warning(f"Failed to create gender metafield: {str(e)}")
                
#                 # Style
#                 if matching_csv_row.style:
#                     try:
#                         shopify_service.add_metafield_to_product(
#                             product_id=product_id,
#                             namespace=mapping.style_namespace,
#                             key=mapping.style_key,
#                             value=matching_csv_row.style,
#                             field_type="single_line_text_field"
#                         )
#                         metafields_created.append(f"{mapping.style_namespace}.{mapping.style_key}")
#                         time.sleep(0.2)
#                     except Exception as e:
#                         logger.warning(f"Failed to create style metafield: {str(e)}")
                
#                 # Components (as list)
#                 if matching_csv_row.components:
#                     try:
#                         components_list = [comp.strip() for comp in matching_csv_row.components.split(',') if comp.strip()]
#                         shopify_service.add_metafield_to_product(
#                             product_id=product_id,
#                             namespace=mapping.components_namespace,
#                             key=mapping.components_key,
#                             value=json.dumps(components_list),
#                             field_type="list.single_line_text_field"
#                         )
#                         metafields_created.append(f"{mapping.components_namespace}.{mapping.components_key}")
#                         time.sleep(0.2)
#                     except Exception as e:
#                         logger.warning(f"Failed to create components metafield: {str(e)}")
                
#                 # Colors (as list)
#                 colors = []
#                 if matching_csv_row.primary_color:
#                     colors.append(matching_csv_row.primary_color)
#                 if matching_csv_row.secondary_color:
#                     colors.append(matching_csv_row.secondary_color)
#                 if colors:
#                     try:
#                         shopify_service.add_metafield_to_product(
#                             product_id=product_id,
#                             namespace=mapping.color_namespace,
#                             key=mapping.color_key,
#                             value=json.dumps(colors),
#                             field_type="list.single_line_text_field"
#                         )
#                         metafields_created.append(f"{mapping.color_namespace}.{mapping.color_key}")
#                         time.sleep(0.2)
#                     except Exception as e:
#                         logger.warning(f"Failed to create color metafield: {str(e)}")
                
#                 # Work/Stone Setting with label
#                 if matching_csv_row.work:
#                     try:
#                         # Label
#                         shopify_service.add_metafield_to_product(
#                             product_id=product_id,
#                             namespace=mapping.work_label_namespace,
#                             key=mapping.work_label_key,
#                             value="Stone Setting",
#                             field_type="single_line_text_field"
#                         )
#                         time.sleep(0.2)
                        
#                         # Data
#                         shopify_service.add_metafield_to_product(
#                             product_id=product_id,
#                             namespace=mapping.work_namespace,
#                             key=mapping.work_key,
#                             value=json.dumps([matching_csv_row.work]),
#                             field_type="list.single_line_text_field"
#                         )
#                         metafields_created.append(f"{mapping.work_namespace}.{mapping.work_key}")
#                         time.sleep(0.2)
#                     except Exception as e:
#                         logger.warning(f"Failed to create work metafields: {str(e)}")
                
#                 # Finish with label
#                 if matching_csv_row.finish:
#                     try:
#                         # Label
#                         shopify_service.add_metafield_to_product(
#                             product_id=product_id,
#                             namespace=mapping.base_metal_label_namespace,
#                             key=mapping.base_metal_label_key,
#                             value="Finish",
#                             field_type="single_line_text_field"
#                         )
#                         time.sleep(0.2)
                        
#                         # Data
#                         shopify_service.add_metafield_to_product(
#                             product_id=product_id,
#                             namespace=mapping.base_metal_namespace,
#                             key=mapping.base_metal_key,
#                             value=matching_csv_row.finish,
#                             field_type="single_line_text_field"
#                         )
#                         metafields_created.append(f"{mapping.base_metal_namespace}.{mapping.base_metal_key}")
#                         time.sleep(0.2)
#                     except Exception as e:
#                         logger.warning(f"Failed to create finish metafields: {str(e)}")
                
#                 # Finding with label
#                 if matching_csv_row.finding:
#                     try:
#                         # Label
#                         shopify_service.add_metafield_to_product(
#                             product_id=product_id,
#                             namespace=mapping.finding_label_namespace,
#                             key=mapping.finding_label_key,
#                             value="Finding",
#                             field_type="single_line_text_field"
#                         )
#                         time.sleep(0.2)
                        
#                         # Data
#                         shopify_service.add_metafield_to_product(
#                             product_id=product_id,
#                             namespace=mapping.finding_namespace,
#                             key=mapping.finding_key,
#                             value=matching_csv_row.finding,
#                             field_type="single_line_text_field"
#                         )
#                         metafields_created.append(f"{mapping.finding_namespace}.{mapping.finding_key}")
#                         time.sleep(0.2)
#                     except Exception as e:
#                         logger.warning(f"Failed to create finding metafields: {str(e)}")
                
#                 # Occasions (as list)
#                 if matching_csv_row.occasions:
#                     try:
#                         occasions_list = [occ.strip() for occ in matching_csv_row.occasions.split(',') if occ.strip()]
#                         shopify_service.add_metafield_to_product(
#                             product_id=product_id,
#                             namespace=mapping.occasions_namespace,
#                             key=mapping.occasions_key,
#                             value=json.dumps(occasions_list),
#                             field_type="list.single_line_text_field"
#                         )
#                         metafields_created.append(f"{mapping.occasions_namespace}.{mapping.occasions_key}")
#                         time.sleep(0.2)
#                     except Exception as e:
#                         logger.warning(f"Failed to create occasions metafield: {str(e)}")
                
#                 # Styling tip from AI
#                 if styling_tip:
#                     try:
#                         shopify_service.add_metafield_to_product(
#                             product_id=product_id,
#                             namespace=mapping.styling_tip_namespace,
#                             key=mapping.styling_tip_key,
#                             value=styling_tip,
#                             field_type="multi_line_text_field"
#                         )
#                         metafields_created.append(f"{mapping.styling_tip_namespace}.{mapping.styling_tip_key}")
#                         time.sleep(0.2)
#                     except Exception as e:
#                         logger.warning(f"Failed to create styling tip metafield: {str(e)}")
                
#                 # SEO metafields
#                 try:
#                     shopify_service.add_metafield_to_product(
#                         product_id=product_id,
#                         namespace=mapping.seo_title_namespace,
#                         key=mapping.seo_title_key,
#                         value=seo_title,
#                         field_type="string"
#                     )
#                     metafields_created.append(f"{mapping.seo_title_namespace}.{mapping.seo_title_key}")
#                     time.sleep(0.2)
#                 except Exception as e:
#                     logger.warning(f"Failed to create SEO title metafield: {str(e)}")
                
#                 try:
#                     shopify_service.add_metafield_to_product(
#                         product_id=product_id,
#                         namespace=mapping.seo_description_namespace,
#                         key=mapping.seo_description_key,
#                         value=seo_description,
#                         field_type="string"
#                     )
#                     metafields_created.append(f"{mapping.seo_description_namespace}.{mapping.seo_description_key}")
#                     time.sleep(0.2)
#                 except Exception as e:
#                     logger.warning(f"Failed to create SEO description metafield: {str(e)}")
                
#                 try:
#                     shopify_service.add_metafield_to_product(
#                         product_id=product_id,
#                         namespace=mapping.meta_description_namespace,
#                         key=mapping.meta_description_key,
#                         value=seo_description,
#                         field_type="multi_line_text_field"
#                     )
#                     metafields_created.append(f"{mapping.meta_description_namespace}.{mapping.meta_description_key}")
#                     time.sleep(0.2)
#                 except Exception as e:
#                     logger.warning(f"Failed to create meta description metafield: {str(e)}")
                
#                 # Process and upload images to Shopify
#                 uploaded_images = []
#                 image_urls = [
#                     matching_csv_row.high_resolution_1,
#                     matching_csv_row.high_resolution_2,
#                     matching_csv_row.high_resolution_3,
#                     matching_csv_row.high_resolution_4,
#                     matching_csv_row.high_resolution_5
#                 ]
                
#                 # Filter out empty URLs
#                 valid_image_urls = [url for url in image_urls if url and url.strip()]
                
#                 if valid_image_urls:
#                     try:
#                         uploaded_images = shopify_service.add_multiple_images_to_product(
#                             product_id=product_id,
#                             image_urls=valid_image_urls,
#                             title=title
#                         )
                        
#                         successful_uploads = sum(1 for img in uploaded_images if img['success'])
#                         logger.info(f"✓ Uploaded {successful_uploads}/{len(valid_image_urls)} images for SKU: {result['product_sku']}")
                        
#                     except Exception as e:
#                         logger.warning(f"Failed to upload images for SKU {result['product_sku']}: {str(e)}")
#                         uploaded_images = [{
#                             'success': False,
#                             'error': str(e),
#                             'url': url
#                         } for url in valid_image_urls]
                
#                 shopify_results.append({
#                     'product_sku': result['product_sku'],
#                     'success': True,
#                     'error': None,
#                     'product_id': product_id,
#                     'product_handle': created_product.get('handle'),
#                     'metafields_created': metafields_created,
#                     'images_uploaded': uploaded_images,
#                     'total_images': len(valid_image_urls),
#                     'successful_images': sum(1 for img in uploaded_images if img['success'])
#                 })
                
#                 logger.info(f"✅ Successfully created complete product for SKU: {result['product_sku']}")
                
#             except Exception as e:
#                 logger.error(f"Error creating Shopify product for SKU {result['product_sku']}: {str(e)}")
#                 shopify_results.append({
#                     'product_sku': result['product_sku'],
#                     'success': False,
#                     'error': str(e),
#                     'product_id': None
#                 })

#         # Update success counts
#         shopify_success_count = sum(1 for r in shopify_results if r['success'])
#         total_images_uploaded = sum(r.get('successful_images', 0) for r in shopify_results if r['success'])
#         logger.info(f"✅ Shopify product creation complete: {shopify_success_count}/{len(shopify_results)} successful, {total_images_uploaded} images uploaded")
        
#         return {
#             "success": True,
#             "message": f"Successfully processed {success_count}/{len(generated_results)} AI generations, {shopify_success_count}/{len(shopify_results)} Shopify products, and {total_images_uploaded} images uploaded",
#             "csv_summary": {
#                 "products_filename": products_file.filename,
#                 "keywords_filename": keywords_file.filename,
#                 "total_product_rows": len(parsed_rows),
#                 "validated_rows": len(validated_rows),
#                 "total_keywords": len(keywords_df)
#             },
#             "content_generation": {
#                 "total_processed": len(generated_results),
#                 "successful": success_count,
#                 "failed": len(generated_results) - success_count,
#                 "results": generated_results
#             },
#             "shopify_creation": {
#                 "total_processed": len(shopify_results),
#                 "successful": shopify_success_count,
#                 "failed": len(shopify_results) - shopify_success_count,
#                 "total_images_uploaded": total_images_uploaded,
#                 "results": shopify_results
#             },
#             "errors": errors if errors else None
#         }
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error in writer-agent endpoint: {str(e)}", exc_info=True)
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Error processing request: {str(e)}"
#         )