"""
Nykaa Catalog Export Controller
FastAPI endpoints for generating Nykaa catalog files
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel
import pandas as pd
import io
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import asyncio

from services.nyaka.service import NykaaExportService
from services.shopify_service import ShopifyGraphQLConnector
from agent.nykaa_rewriter.graph import batch_rewrite_products
from agent.nykaa_rewriter.material_resolver import resolve_material_gid
from agent.nykaa_rewriter.ean_generator import generate_ean13
from services.nyaka.nykaa_validator import validate_batch

router = APIRouter()

class SKUListRequest(BaseModel):
    skus: List[str]

def get_shopify_connector() -> ShopifyGraphQLConnector:
    """Get Shopify GraphQL connector instance"""
    return ShopifyGraphQLConnector()


def get_nykaa_service(
    connector: ShopifyGraphQLConnector = Depends(get_shopify_connector)
) -> NykaaExportService:
    """Get Nykaa export service instance"""
    return NykaaExportService(shopify_connector=connector)


def extract_product_for_rewrite(product: dict) -> dict:
    """
    Extract necessary fields from Shopify product for AI rewriting
    
    Args:
        product: Shopify product dict
    
    Returns:
        Dict with fields needed for graph.py rewriter
    """
    try:
        print(f"🔍 Extracting rewrite data from product: {product.get('id', 'unknown')}")
        
        # Handle variants (GraphQL format: variants.edges[].node)
        variants_data = product.get('variants', {})
        variant_nodes = []
        
        if isinstance(variants_data, dict) and 'edges' in variants_data:
            # GraphQL format
            variant_nodes = [edge.get('node', {}) for edge in variants_data.get('edges', [])]
        elif isinstance(variants_data, list):
            # Already a list of variants
            variant_nodes = variants_data
        
        # Get the first variant (main variant)
        main_variant = variant_nodes[0] if variant_nodes else {}
        
        # Extract SKU from variant (this is critical!)
        sku = ""
        if main_variant:
            sku = main_variant.get('sku', '')
        
        if not sku:
            # Fallback to product-level SKU if available
            sku = product.get('sku', '')
        
        if not sku:
            print(f"⚠️ No SKU found for product {product.get('id', 'unknown')}")
            sku = f"unknown_{product.get('id', 'missing')}"
        
        # Extract metafields (GraphQL format: metafields.edges[].node)
        metafields_data = product.get('metafields', {})
        metafields_dict = {}
        
        if isinstance(metafields_data, dict) and 'edges' in metafields_data:
            # GraphQL format
            for edge in metafields_data.get('edges', []):
                node = edge.get('node', {})
                key = node.get('key')
                value = node.get('value')
                if key and value:
                    metafields_dict[key] = value
        elif isinstance(metafields_data, list):
            # Already a list
            for mf in metafields_data:
                if isinstance(mf, dict):
                    key = mf.get('key')
                    value = mf.get('value')
                    if key and value:
                        metafields_dict[key] = value
        
        # Extract material GID
        material_gid = metafields_dict.get('material') or metafields_dict.get('material_type')
        
        # Get price safely
        price = 0
        if main_variant:
            try:
                price = float(main_variant.get('price', 0))
            except (ValueError, TypeError):
                pass
        
        result = {
            "product_id": product.get('id', ''),
            "sku": sku,  # Ensure SKU is always present
            "current_name": product.get('title', ''),
            "current_description": product.get('description', '') or product.get('descriptionHtml', ''),
            "product_type": product.get('productType', 'Necklace'),
            "material_gid": material_gid,
            "metal_type": metafields_dict.get('metal_finish', 'Antique Gold'),
            "color": metafields_dict.get('color', ''),
            "occasion": metafields_dict.get('occasion', ''),
            "price": price,
            "set_contents": [variant.get('title', '') for variant in variant_nodes if variant.get('title')][:3],
            "image_count": len(product.get('images', {}).get('edges', [])),
            "is_draft": product.get('status') == 'draft',
        }
        
        print(f"✅ Extracted SKU: {result['sku']} for product: {result['current_name'][:50]}")
        return result
        
    except Exception as e:
        print(f"❌ Error in extract_product_for_rewrite: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return minimal safe dict with guaranteed SKU
        fallback_sku = product.get('id', 'unknown')
        print(f"🔄 Using fallback SKU: {fallback_sku}")
        
        return {
            "product_id": product.get('id', ''),
            "sku": fallback_sku,
            "current_name": product.get('title', 'Unknown Product'),
            "current_description": product.get('description', ''),
            "product_type": 'Necklace',
            "material_gid": None,
            "metal_type": 'Antique Gold',
            "color": '',
            "occasion": '',
            "price": 0,
            "set_contents": [],
            "image_count": 0,
            "is_draft": False,
        }
    except Exception as e:
        print(f"❌ Error in extract_product_for_rewrite: {str(e)}")
        import traceback
        traceback.print_exc()
        # Return minimal safe dict
        return {
            "product_id": product.get('id', ''),
            "sku": product.get('sku', 'unknown'),
            "current_name": product.get('title', ''),
            "current_description": product.get('description', ''),
            "product_type": 'Necklace',
            "material_gid": None,
            "metal_type": 'Antique Gold',
            "color": '',
            "occasion": '',
            "price": 0,
            "set_contents": [],
            "image_count": 0,
            "is_draft": False,
        }


async def apply_ai_rewrite_to_products(products: List[dict]) -> tuple[List[dict], List[dict]]:
    """
    Apply AI rewriting to products and merge back into Nykaa rows
    
    This function:
    1. Maps ALL products to Nykaa format using standard mapping
    2. Generates AI names/descriptions for all products  
    3. Merges AI results back into Nykaa rows using SKU as key
    
    Args:
        products: List of Shopify products
    
    Returns:
        Tuple of (updated_nykaa_rows, rewrite_results)
    """
    service = NykaaExportService(shopify_connector=ShopifyGraphQLConnector())
    
    print(f"🤖 Step 1: Mapping {len(products)} products to Nykaa format...")
    
    # STEP 1: Map ALL products to standard Nykaa format
    nykaa_rows = []
    product_sku_map = {}
    successful_products = []  # Track which products were successfully mapped
    
    for i, product in enumerate(products):
        try:
            # Standard Nykaa mapping for all fields
            row = service.mapper.map_shopify_product_to_nykaa(product)
            nykaa_rows.append(row)
            
            # Store SKU mapping for AI merge
            sku = row.get("Vendor SKU Code")
            if sku:
                product_sku_map[sku] = len(nykaa_rows) - 1  # Store row index
                successful_products.append(product)  # Track successful product
                print(f"✅ Mapped product {i}: SKU={sku}")
            else:
                print(f"⚠️ Product {i} mapped but no SKU found in row")
                
        except Exception as e:
            print(f"⚠️ Skipping product {i} {product.get('id', 'unknown')}: {str(e)}")
            continue
    
    print(f"✅ Mapped {len(nykaa_rows)} products to Nykaa format")
    print(f"📊 Product-SKU mapping: {list(product_sku_map.keys())[:5]}...")
    
    # STEP 2: Prepare inputs for AI rewriter (ONLY for successfully mapped products)
    print(f"🤖 Step 2: Generating AI names/descriptions...")
    
    rewrite_inputs = []
    for i, product in enumerate(successful_products):  # Use only successfully mapped products
        try:
            rewrite_input = extract_product_for_rewrite(product)
            rewrite_inputs.append(rewrite_input)
            print(f"✅ AI input {i}: SKU={rewrite_input.get('sku')}")
        except Exception as e:
            print(f"⚠️ Error extracting rewrite input for product {i}: {str(e)}")
            # Add placeholder to maintain index alignment
            rewrite_inputs.append({
                "sku": f"error_{i}",
                "current_name": "Error Product",
                "current_description": "",
                "product_type": "Necklace",
                "material": "Kundan Polki",
                "metal_type": "Antique Gold", 
                "color": "",
                "occasion": "",
                "price": 0,
                "set_contents": [],
            })
            continue
    
    # STEP 3: Run AI rewriter in thread executor
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=1)
    
    try:
        rewrite_results = await loop.run_in_executor(
            executor,
            lambda: batch_rewrite_products(rewrite_inputs)
        )
        print(f"✅ AI rewriter complete. Results count: {len(rewrite_results)}")
    except Exception as e:
        print(f"❌ AI rewriter failed: {str(e)}")
        import traceback
        traceback.print_exc()
        # Return standard mapping without AI enhancement
        return nykaa_rows, []
    
    # STEP 4: Merge AI results back into Nykaa rows using SKU as key
    print(f"🔄 Step 4: Merging AI results with Nykaa rows...")
    print(f"📊 Debug: Product SKU map has {len(product_sku_map)} entries: {list(product_sku_map.keys())[:10]}...")
    print(f"📊 Debug: AI results count: {len(rewrite_results)}")
    
    ai_updated_count = 0
    for i, result in enumerate(rewrite_results):
        try:
            # Validate result structure
            if not isinstance(result, dict):
                print(f"⚠️ Result {i} is type {type(result)}, expected dict")
                continue
            
            sku = result.get("sku")
            print(f"🔍 Processing AI result {i}: SKU='{sku}' (type: {type(sku)})")
            
            if not sku or sku.strip() == "":  # Check for empty string too
                print(f"⚠️ Result {i} has empty/missing SKU field: {list(result.keys())}")
                print(f"   SKU value: '{sku}' (type: {type(sku)})")
                continue
            
            # DEBUG: Show what we're looking for vs what we have
            print(f"   🔍 Looking for SKU '{sku}' in mapping...")
            print(f"   📋 Available SKUs: {list(product_sku_map.keys())}")
            
            # Find corresponding Nykaa row by SKU
            row_index = product_sku_map.get(sku)
            if row_index is None:
                print(f"⚠️ No Nykaa row found for AI result SKU: '{sku}'")
                print(f"   Available SKUs in map: {list(product_sku_map.keys())[:5]}...")
                print(f"   Full AI result: {result}")
                continue
            
            # Update with AI-generated content (use correct column names)
            updates_made = []
            
            if result.get("generated_name") and result["generated_name"].strip():
                nykaa_rows[row_index]["Product Name"] = result["generated_name"]
                updates_made.append("Product Name")
            
            if result.get("generated_description") and result["generated_description"].strip():
                nykaa_rows[row_index]["Description"] = result["generated_description"]
                updates_made.append("Description")
            
            # Note: EAN codes are now generated by standard mapper, no need to override
            # Note: Material resolution is also handled by standard mapping
            
            if updates_made:
                print(f"✅ Updated {', '.join(updates_made)} for SKU {sku}")
                ai_updated_count += 1
            else:
                print(f"⚠️ No valid updates for SKU {sku}")
            
        except Exception as e:
            print(f"❌ Error merging AI result {i}: {str(e)}")
            print(f"   Result: {result}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"🎯 Successfully enhanced {ai_updated_count}/{len(nykaa_rows)} products with AI content")
    return nykaa_rows, rewrite_results


@router.post("/export/skus-xlsx")
async def export_skus_xlsx(
    request: SKUListRequest,
    service: NykaaExportService = Depends(get_nykaa_service)
):
    """
    Export SKUs to Nykaa XLSX format and save to current directory
    
    **Request Body:**
    ```json
    {
        "skus": ["SKU1", "SKU2", "SKU3"]
    }
    ```
    
    **Example:**
    ```bash
    curl -X POST "/nykaa/export/skus-xlsx" \
         -H "Content-Type: application/json" \
         -d '{"skus": ["ABC123", "XYZ789", "DEF456"]}'
    ```
    
    **Response:**
    JSON response with file details and saved to current working directory
    """
    try:
        if not request.skus:
            raise HTTPException(status_code=400, detail="Please provide at least one SKU")
        
        # Remove duplicates from SKU list while preserving order
        seen = set()
        unique_skus = []
        for sku in request.skus:
            if sku not in seen:
                seen.add(sku)
                unique_skus.append(sku)
        
        if len(request.skus) != len(unique_skus):
            print(f"⚠️ Removed {len(request.skus) - len(unique_skus)} duplicate SKUs from request")
        
        # Fetch products by SKUs using hybrid Zakya+Shopify approach
        products = await service.fetch_products_by_skus(unique_skus)
        
        if not products:
            raise HTTPException(status_code=404, detail="No products found for the provided SKUs")
        
        # Convert to Nykaa format
        nykaa_rows = []
        for product in products:
            try:
                row = service.mapper.map_shopify_product_to_nykaa(product)
                nykaa_rows.append(row)
            except Exception as e:
                # Skip problematic products but continue processing
                print(f"⚠️ Skipping product {product.get('id', 'unknown')}: {str(e)}")
                continue
        
        if not nykaa_rows:
            raise HTTPException(status_code=404, detail="No valid products could be processed")
        
        # Create DataFrame and save to XLSX
        df = pd.DataFrame(nykaa_rows)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"nykaa_export_{timestamp}.xlsx"
        
        # Save to current working directory
        current_dir = os.getcwd()
        filepath = os.path.join(current_dir, filename)
        df.to_excel(filepath, index=False, engine='openpyxl')
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Nykaa XLSX export completed successfully",
                "file_details": {
                    "filename": filename,
                    "filepath": filepath,
                    "current_directory": current_dir,
                    "total_skus_requested": len(unique_skus),
                    "products_found": len(products),
                    "products_processed": len(nykaa_rows),
                    "file_size_bytes": os.path.getsize(filepath)
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing SKUs: {str(e)}")


@router.post("/export/skus-xlsx-simple")
async def export_skus_xlsx_simple(
    file: UploadFile = File(..., description="Upload Excel/CSV file with SKUs"),
    use_ai_rewrite: bool = Query(False, description="Use AI agent to rewrite product names and descriptions"),
    service: NykaaExportService = Depends(get_nykaa_service)
):
    """
    Upload file with SKUs and export to Nykaa XLSX format in current directory
    
    **File Requirements:**
    - Supported formats: .csv, .xls, .xlsx
    - Must contain a column with SKUs (will auto-detect column name)
    - Common column names: 'sku', 'SKU', 'item_code', 'product_code', etc.
    
    **Query Parameters:**
    - `use_ai_rewrite` (bool, default=false): If true, use AI agent to generate optimized names and descriptions
    
    **Example without AI:**
    ```bash
    curl -X POST "/nykaa/export/skus-xlsx-simple" \
         -F "file=@skus.xlsx"
    ```
    
    **Example with AI rewrite:**
    ```bash
    curl -X POST "/nykaa/export/skus-xlsx-simple?use_ai_rewrite=true" \
         -F "file=@skus.xlsx"
    ```
    
    **Response:**
    JSON response with file details and saved to current working directory
    """
    try:
        # Validate file extension
        if not file.filename.lower().endswith(('.csv', '.xls', '.xlsx')):
            raise HTTPException(
                status_code=400, 
                detail="Only CSV, XLS, and XLSX files are supported"
            )
        
        # Read file content
        file_content = await file.read()
        
        # Parse file based on extension
        if file.filename.lower().endswith('.csv'):
            # Read CSV
            df = pd.read_csv(io.StringIO(file_content.decode('utf-8')))
        else:
            # Read Excel (XLS/XLSX)
            df = pd.read_excel(io.BytesIO(file_content))
        
        # Auto-detect SKU column
        sku_column = None
        possible_sku_columns = ['sku', 'SKU', 'item_code', 'product_code', 'item_number', 'code', 'item', 'product_sku']
        
        for col in df.columns:
            if col.lower() in [c.lower() for c in possible_sku_columns]:
                sku_column = col
                break
        
        if sku_column is None:
            # If no standard column found, use first column
            sku_column = df.columns[0]
        
        # Extract SKUs from the column
        sku_list = df[sku_column].dropna().astype(str).str.strip().tolist()
        sku_list = [sku for sku in sku_list if sku and sku.lower() != 'nan']
        
        # Remove duplicates while preserving order
        seen = set()
        unique_sku_list = []
        for sku in sku_list:
            if sku not in seen:
                seen.add(sku)
                unique_sku_list.append(sku)
            else:
                print(f"Duplicate SKU found and removed: {sku}")
        
        if len(sku_list) != len(unique_sku_list):
            print(f"⚠️ Removed {len(sku_list) - len(unique_sku_list)} duplicate SKUs from input")
        
        sku_list = unique_sku_list
        print(f"SKU list is as follows: {sku_list}")
        
        if not sku_list:
            raise HTTPException(status_code=400, detail=f"No valid SKUs found in column '{sku_column}'")
        
        # Fetch products by SKUs using hybrid Zakya+Shopify approach
        products = await service.fetch_products_by_skus(sku_list)
        
        if not products:
            raise HTTPException(status_code=404, detail="No products found for the provided SKUs")
        
        # Convert to Nykaa format
        nykaa_rows = []
        rewrite_results = []
        
        if use_ai_rewrite:
            # Use AI agent to rewrite names and descriptions
            print(f"🤖 Running {len(products)} products through AI rewriter...")
            nykaa_rows, rewrite_results = await apply_ai_rewrite_to_products(products)
        else:
            # Standard mapping without AI
            for product in products:
                try:
                    row = service.mapper.map_shopify_product_to_nykaa(product)
                    nykaa_rows.append(row)
                except Exception as e:
                    # Skip problematic products but continue processing
                    print(f"⚠️ Skipping product {product.get('id', 'unknown')}: {str(e)}")
                    continue
        
        if not nykaa_rows:
            raise HTTPException(status_code=404, detail="No valid products could be processed")
        
        print("🔍 Validating all products against Nykaa dropdowns...")
        validation_results = validate_batch(nykaa_rows)

        print(f"\n📊 Validation Summary:")
        print(f"   Total Products: {validation_results['total_products']}")
        print(f"   ✅ Valid: {validation_results['valid_products']}")
        print(f"   ❌ Invalid: {validation_results['invalid_products']}")
        print(f"   Total Errors: {validation_results['total_errors']}")
        print(f"   Total Warnings: {validation_results['total_warnings']}")

        # Print detailed errors
        if validation_results['detailed_results']:
            print("\n⚠️  Products with issues:")
            for result in validation_results['detailed_results'][:10]:  # Show first 10
                print(f"\n   SKU: {result['sku']}")
                if result['errors']:
                    for error in result['errors']:
                        print(f"      ❌ {error}")
                if result['warnings']:
                    for warning in result['warnings']:
                        print(f"      ⚠️  {warning}")        
        
        # Create DataFrame and save to XLSX
        result_df = pd.DataFrame(nykaa_rows)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"nykaa_export_from_file_{timestamp}.xlsx"
        
        # Save to current working directory
        current_dir = os.getcwd()
        filepath = os.path.join(current_dir, filename)
        result_df.to_excel(filepath, index=False, engine='openpyxl')
        
        response = {
            "success": True,
            "message": f"Nykaa XLSX export {'with AI rewrite ' if use_ai_rewrite else ''}completed successfully",
            "file_details": {
                "filename": filename,
                "filepath": filepath,
                "current_directory": current_dir,
                "uploaded_file": file.filename,
                "sku_column_used": sku_column,
                "total_skus_uploaded": len(sku_list),
                "products_found": len(products),
                "products_processed": len(nykaa_rows),
                "file_size_bytes": os.path.getsize(filepath),
                "ai_rewrite_enabled": use_ai_rewrite,
            }
        }
        
        # If AI rewrite was used, include quality metrics
        if use_ai_rewrite and rewrite_results:
            quality_summary = {
                "total_products": len(rewrite_results),
                "manual_review_needed": sum(1 for r in rewrite_results if r.get("manual_review_needed")),
                "products_with_issues": []
            }
            
            for result in rewrite_results:
                if result.get("manual_review_needed"):
                    quality_summary["products_with_issues"].append({
                        "sku": result.get("sku"),
                        "reasons": result.get("manual_review_reasons", []),
                        "quality_score": round(result.get("quality_score", {}).get("overall", 0), 1)
                    })
            
            response["quality_metrics"] = quality_summary
        
        return JSONResponse(status_code=200, content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ FATAL ERROR in export_skus_xlsx_simple: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


# ============================================================================
# LEGACY CSV ENDPOINTS (Redirects to XLSX)
# ============================================================================

@router.post("/export/skus-csv")
async def export_skus_csv_legacy(
    request: SKUListRequest,
    service: NykaaExportService = Depends(get_nykaa_service)
):
    """
    🚨 DEPRECATED: CSV format is no longer supported by Nykaa
    This endpoint now automatically generates XLSX files instead.
    Please use /export/skus-xlsx instead.
    """
    return await export_skus_xlsx(request, service)


@router.post("/export/skus-csv-simple") 
async def export_skus_csv_simple_legacy(
    file: UploadFile = File(..., description="Upload Excel/CSV file with SKUs"),
    use_ai_rewrite: bool = Query(False, description="Use AI agent to rewrite product names and descriptions"),
    service: NykaaExportService = Depends(get_nykaa_service)
):
    """
    🚨 DEPRECATED: CSV format is no longer supported by Nykaa
    This endpoint now automatically generates XLSX files instead.
    Please use /export/skus-xlsx-simple instead.
    """
    return await export_skus_xlsx_simple(file, use_ai_rewrite, service)

