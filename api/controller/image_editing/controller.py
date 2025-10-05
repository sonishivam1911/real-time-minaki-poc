from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from utils.schema.image_editing import (
    NDJSONImportResponse,
)
from fastapi.responses import FileResponse
from typing import List
import os
import shutil
import tempfile
from services.image_editing.service import ImageProcessingService
from services.database_sync.image_editing_table_sync import ProductsService

router = APIRouter()

@router.post("/sync-database", response_model=NDJSONImportResponse)
async def import_products_from_ndjson(
    file: UploadFile = File(..., description="NDJSON file containing product data"),
    table_name: str = Form(default="xuping_product_master", description="Target table name") 
):
    """
    Import products from NDJSON file into database.
    
    - **file**: Upload NDJSON file (.ndjson or .jsonl)
    - **table_name**: Target table name (default: "products")
    """
    
    # Validate file extension
    if not file.filename.endswith(('.ndjson', '.jsonl', '.json')):
        return NDJSONImportResponse(
            success=False,
            message="Invalid file format. Please upload a .ndjson, .jsonl, or .json file",
            total_records=0,
            success_count=0,
            error_count=0,
            status_code=400
        )
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Call service layer
        result = ProductsService.import_ndjson_to_database(
            file_content=file_content,
            table_name=table_name
        )
        
        # Return response
        return NDJSONImportResponse(
            success=result['success'],
            message=result['message'],
            total_records=result['total_records'],
            success_count=result['success_count'],
            error_count=result['error_count'],
            status_code=200 if result['success'] else 400
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/process-and-download")
async def process_images_and_download(
    files: List[UploadFile] = File(..., description="Multiple ZIP files containing images"),
    validate_skus: bool = Form(True, description="Validate SKUs against database"),
    table_name: str = Form("products", description="Database table name for SKU validation")
):
    """
    Single endpoint that:
    1. Processes multiple ZIP files with images
    2. Validates SKUs against database
    3. Removes watermarks
    4. Groups images by SKU
    5. Returns processed images as downloadable ZIP
    6. Automatically cleans up all temporary files
    """
    temp_dir = None
    output_zip_path = None
    
    try:
        # Create temporary directory for processing
        temp_dir = tempfile.mkdtemp()
        processed_dir = os.path.join(temp_dir, "processed")
        os.makedirs(processed_dir, exist_ok=True)
        
        # Read all uploaded ZIP files
        zip_files = []
        zip_names = []
        
        for upload_file in files:
            if not upload_file.filename.endswith('.zip'):
                raise HTTPException(
                    status_code=400,
                    detail=f"File {upload_file.filename} is not a ZIP file"
                )
            
            content = await upload_file.read()
            zip_files.append(content)
            zip_names.append(upload_file.filename)
        
        # Process all images using the batch processing method
        result = ImageProcessingService.process_images_batch(
            zip_files=zip_files,
            zip_names=zip_names,
            output_dir=processed_dir,
            validate_db=validate_skus,
            table_name=table_name
        )
        
        if not result['success']:
            raise HTTPException(
                status_code=400,
                detail=result['message']
            )
        
        if result['processed_images'] == 0:
            raise HTTPException(
                status_code=400,
                detail="No images were successfully processed"
            )
        
        # Create output ZIP file
        output_zip_path = os.path.join(temp_dir, "processed_images.zip")
        shutil.make_archive(
            output_zip_path.replace('.zip', ''),
            'zip',
            processed_dir
        )
        
        # Return the ZIP file for download
        return FileResponse(
            path=output_zip_path,
            media_type="application/zip",
            filename="processed_images.zip",
            headers={
                "Content-Disposition": "attachment; filename=processed_images.zip",
                "X-Total-Images": str(result['total_images']),
                "X-Processed-Images": str(result['processed_images']),
                "X-Failed-Images": str(result['failed_images']),
                "X-Total-SKUs": str(result['total_skus']),
                "X-Invalid-SKUs": str(len(result['invalid_skus']))
            },
            background=lambda: cleanup_files(temp_dir, output_zip_path)
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    
    except Exception as e:
        # Clean up on error
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        raise HTTPException(
            status_code=500,
            detail=f"Image processing failed: {str(e)}"
        )

def cleanup_files(temp_dir: str, output_zip_path: str):
    """Background cleanup task to remove temporary files after download"""
    try:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        if output_zip_path and os.path.exists(output_zip_path):
            os.remove(output_zip_path)
    except Exception as e:
        print(f"Cleanup error: {e}")