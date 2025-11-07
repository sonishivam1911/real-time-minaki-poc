"""
Nykaa Catalog Export Controller
FastAPI endpoints for generating Nykaa catalog files
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import JSONResponse
from typing import List
from pydantic import BaseModel
import pandas as pd
import io
import os
from datetime import datetime

from services.nyaka.service import NykaaExportService
from services.shopify_service import ShopifyGraphQLConnector

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


@router.post("/export/skus-csv")
async def export_skus_csv(
    request: SKUListRequest,
    service: NykaaExportService = Depends(get_nykaa_service)
):
    """
    Export SKUs to Nykaa CSV format and save to current directory
    
    **Request Body:**
    ```json
    {
        "skus": ["SKU1", "SKU2", "SKU3"]
    }
    ```
    
    **Example:**
    ```bash
    curl -X POST "/nykaa/export/skus-csv" \
         -H "Content-Type: application/json" \
         -d '{"skus": ["ABC123", "XYZ789", "DEF456"]}'
    ```
    
    **Response:**
    JSON response with file details and saved to current working directory
    """
    try:
        if not request.skus:
            raise HTTPException(status_code=400, detail="Please provide at least one SKU")
        
        # Fetch products by SKUs using hybrid Zakya+Shopify approach
        products = await service.fetch_products_by_skus(request.skus)
        
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
        
        # Create DataFrame and save to CSV
        df = pd.DataFrame(nykaa_rows)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"nykaa_export_{timestamp}.csv"
        
        # Save to current working directory
        current_dir = os.getcwd()
        filepath = os.path.join(current_dir, filename)
        df.to_csv(filepath, index=False, encoding='utf-8')
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Nykaa CSV export completed successfully",
                "file_details": {
                    "filename": filename,
                    "filepath": filepath,
                    "current_directory": current_dir,
                    "total_skus_requested": len(request.skus),
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


@router.post("/export/skus-csv-simple")
async def export_skus_csv_simple(
    file: UploadFile = File(..., description="Upload Excel/CSV file with SKUs"),
    service: NykaaExportService = Depends(get_nykaa_service)
):
    """
    Upload file with SKUs and export to Nykaa CSV format in current directory
    
    **File Requirements:**
    - Supported formats: .csv, .xls, .xlsx
    - Must contain a column with SKUs (will auto-detect column name)
    - Common column names: 'sku', 'SKU', 'item_code', 'product_code', etc.
    
    **Example:**
    ```bash
    curl -X POST "/nykaa/export/skus-csv-simple" \
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
        
        if not sku_list:
            raise HTTPException(status_code=400, detail=f"No valid SKUs found in column '{sku_column}'")
        
        # Fetch products by SKUs using hybrid Zakya+Shopify approach
        products = await service.fetch_products_by_skus(sku_list)
        
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
        
        # Create DataFrame and save to CSV
        result_df = pd.DataFrame(nykaa_rows)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"nykaa_export_from_file_{timestamp}.csv"
        
        # Save to current working directory
        current_dir = os.getcwd()
        filepath = os.path.join(current_dir, filename)
        result_df.to_csv(filepath, index=False, encoding='utf-8')
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Nykaa CSV export from uploaded file completed successfully",
                "file_details": {
                    "filename": filename,
                    "filepath": filepath,
                    "current_directory": current_dir,
                    "uploaded_file": file.filename,
                    "sku_column_used": sku_column,
                    "total_skus_uploaded": len(sku_list),
                    "products_found": len(products),
                    "products_processed": len(nykaa_rows),
                    "file_size_bytes": os.path.getsize(filepath)
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

