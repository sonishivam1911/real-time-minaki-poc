from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from utils.schema.image_editing import (
    NDJSONImportResponse,
)
from fastapi.responses import FileResponse
from typing import List
import os
import shutil
import tempfile
import pandas as pd
import requests
from services.image_editing.service import ImageProcessingService
from services.database_sync.image_editing_table_sync import ProductsService
from utils.logger import logger
import time
from datetime import datetime


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
    background_tasks: BackgroundTasks,
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
        
        # Create output ZIP file in current working directory
        current_dir = os.getcwd()
        downloads_dir = os.path.join(current_dir, "downloads")
        os.makedirs(downloads_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"processed_images_{timestamp}.zip"
        output_zip_path = os.path.join(downloads_dir, zip_filename)
        
        shutil.make_archive(
            output_zip_path.replace('.zip', ''),
            'zip',
            processed_dir
        )
        
        logger.info(f"ZIP file created in downloads directory: {output_zip_path}")
        
        # Return the ZIP file for download
        background_tasks.add_task(cleanup_with_delay, temp_dir, output_zip_path, 300)  # 5 minutes delay
        
        return FileResponse(
            path=output_zip_path,
            media_type="application/zip",
            filename=zip_filename,
            headers={
                "Content-Disposition": f"attachment; filename={zip_filename}",
                "X-Total-Images": str(result['total_images']),
                "X-Processed-Images": str(result['processed_images']),
                "X-Failed-Images": str(result['failed_images']),
                "X-Total-SKUs": str(result['total_skus']),
                "X-Invalid-SKUs": str(len(result['invalid_skus']))
            }
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
        
@router.post("/process-minaki-images")
async def process_minaki_images(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Process Minaki images from XLS file.
    Upload XLS with Item number and MINAKI CODE columns.
    """
    logger.info(f"Starting Minaki image processing for file: {file.filename}")
    temp_dir = None
    output_zip_path = None
    
    try:
        # Validate file
        logger.info("Validating uploaded file format")
        if not file.filename.endswith(('.xls', '.xlsx')):
            logger.error(f"Invalid file format: {file.filename}. Expected .xls or .xlsx")
            raise HTTPException(status_code=400, detail="Upload .xls or .xlsx file")
        
        logger.info("File format validation passed")
        
        # Setup temp directories
        temp_dir = tempfile.mkdtemp()
        processed_dir = os.path.join(temp_dir, "processed")
        os.makedirs(processed_dir, exist_ok=True)
        logger.info(f"Created temporary directory: {temp_dir}")
        
        # Read XLS file
        logger.info("Reading XLS file content")
        file_content = await file.read()
        
        # Parse XLS to get SKU -> MINAKI CODE mapping
        logger.info("Parsing XLS file to extract SKU-MINAKI CODE mapping")
        temp_xls = tempfile.NamedTemporaryFile(delete=False, suffix='.xls')
        temp_xls.write(file_content)
        temp_xls.close()
        
        df = pd.read_excel(temp_xls.name, header=9)
        os.remove(temp_xls.name)
        
        df = df.dropna(subset=['Item number', 'MINAKI CODE'])
        
        sku_minaki_mapping = {}
        for _, row in df.iterrows():
            sku_minaki_mapping[str(row['Item number']).strip()] = str(row['MINAKI CODE']).strip()
        
        logger.info(f"Extracted {len(sku_minaki_mapping)} SKU-MINAKI CODE mappings from XLS")
        
        if not sku_minaki_mapping:
            logger.error("No valid SKU-MINAKI CODE mappings found in XLS file")
            raise HTTPException(status_code=400, detail="No valid mappings found in XLS")
        
        # Query database for pics
        logger.info(f"Querying database for pics data for {len(sku_minaki_mapping)} SKUs")
        from core.database import db
        sku_str = "', '".join(sku_minaki_mapping.keys())
        query = f"SELECT sku, pics FROM xuping_product_master WHERE sku IN ('{sku_str}')"
        pics_df = db.execute_query(query, return_data=True)
        
        if pics_df.empty:
            logger.error("No SKUs found in database")
            raise HTTPException(status_code=400, detail="No SKUs found in database")
        
        logger.info(f"Found {len(pics_df)} SKUs with pics data in database")
        
        pics_mapping = {}
        for _, row in pics_df.iterrows():
            pics_mapping[str(row['sku']).strip()] = row['pics'] if pd.notna(row['pics']) else ""
        
        # Process each SKU
        logger.info("Starting image processing for each SKU")
        total_images = 0
        processed_images = 0
        
        for sku, minaki_code in sku_minaki_mapping.items():
            logger.debug(f"Processing SKU: {sku} -> MINAKI CODE: {minaki_code}")
            
            if sku not in pics_mapping:
                logger.warning(f"SKU {sku} not found in database pics mapping")
                continue
            
            pics_string = pics_mapping[sku]
            if not pics_string:
                logger.warning(f"No pics data found for SKU {sku}")
                continue
            
            image_urls = [url.strip() for url in pics_string.split(',') if url.strip()]
            if not image_urls:
                logger.warning(f"No valid image URLs found for SKU {sku}")
                continue
            
            logger.info(f"Processing {len(image_urls)} images for SKU {sku} (MINAKI CODE: {minaki_code})")
            
            # Create folder
            minaki_folder = os.path.join(processed_dir, minaki_code)
            os.makedirs(minaki_folder, exist_ok=True)
            
            # Download and process each image
            for idx, image_url in enumerate(image_urls, start=1):
                total_images += 1
                logger.debug(f"Processing image {idx}/{len(image_urls)} for SKU {sku}: {image_url}")
                
                try:
                    # Download
                    response = requests.get(image_url.strip(), timeout=30)
                    response.raise_for_status()
                    image_bytes = response.content
                    logger.debug(f"Successfully downloaded image {idx} for SKU {sku}")
                    
                    # Save to temp file for processing
                    temp_img = os.path.join(temp_dir, f"temp_{idx}.jpg")
                    with open(temp_img, 'wb') as f:
                        f.write(image_bytes)
                    
                    # Use your existing watermark removal function
                    output_path = ImageProcessingService.remove_watermark(
                        temp_img, 
                        minaki_folder, 
                        minaki_code, 
                        str(idx)
                    )
                    
                    if output_path:
                        processed_images += 1
                        logger.debug(f"Successfully processed image {idx} for SKU {sku}")
                    else:
                        logger.warning(f"Failed to process image {idx} for SKU {sku}")
                    
                    # Cleanup temp
                    if os.path.exists(temp_img):
                        os.remove(temp_img)
                        
                except Exception as e:
                    logger.error(f"Failed to process image {idx} for SKU {sku} from URL {image_url}: {str(e)}")
                    continue
        
        logger.info(f"Image processing completed. Total: {total_images}, Processed: {processed_images}")
        
        if processed_images == 0:
            logger.error("No images were successfully processed")
            raise HTTPException(status_code=400, detail="No images were processed")
        
        # Create ZIP in current working directory
        logger.info("Creating ZIP file with processed images")
        current_dir = os.getcwd()
        downloads_dir = os.path.join(current_dir, "downloads")
        os.makedirs(downloads_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"minaki_processed_images_{timestamp}.zip"
        output_zip_path = os.path.join(downloads_dir, zip_filename)
        
        shutil.make_archive(output_zip_path.replace('.zip', ''), 'zip', processed_dir)
        logger.info(f"ZIP file created in downloads directory: {output_zip_path}")
        
        # Return ZIP with delayed cleanup
        logger.info(f"Returning processed images ZIP file. Total images: {total_images}, Processed: {processed_images}")
        
        # Add cleanup as background task with 5 minute delay
        background_tasks.add_task(cleanup_with_delay, temp_dir, output_zip_path, 300)
        
        return FileResponse(
            path=output_zip_path,
            media_type="application/zip",
            filename=zip_filename,
            headers={
                "X-Total-Images": str(total_images),
                "X-Processed-Images": str(processed_images)
            }
        )
    
    except HTTPException as he:
        logger.error(f"HTTP Exception in process_minaki_images: {he.detail}")
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temporary directory after HTTPException: {temp_dir}")
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error in process_minaki_images: {str(e)}", exc_info=True)
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temporary directory after exception: {temp_dir}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Note: We don't clean up temp_dir here because FileResponse needs the file
        # The temporary files will be cleaned up by the OS eventually
        # Alternative: implement a background task scheduler for cleanup
        pass

def cleanup(temp_dir: str):
    """Cleanup temp files"""
    try:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Successfully cleaned up temporary directory: {temp_dir}")
    except Exception as e:
        logger.error(f"Cleanup error for directory {temp_dir}: {e}")

def cleanup_with_delay(temp_dir: str, zip_file_path: str, delay_seconds: int):
    """Cleanup temp files and download file after delay"""
    try:
        # First cleanup temp directory immediately
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Successfully cleaned up temporary directory: {temp_dir}")
        
        # Wait for specified delay before deleting download file
        logger.info(f"Waiting {delay_seconds} seconds before deleting download file: {zip_file_path}")
        time.sleep(delay_seconds)
        
        # Delete the download file
        if zip_file_path and os.path.exists(zip_file_path):
            os.remove(zip_file_path)
            logger.info(f"Successfully deleted download file: {zip_file_path}")
        
    except Exception as e:
        logger.error(f"Cleanup with delay error: {e}")

@router.get("/downloads/{filename}")
async def download_file(filename: str):
    """
    Common download API for processed files.
    Files are stored in downloads directory and auto-deleted after download.
    """
    try:
        current_dir = os.getcwd()
        downloads_dir = os.path.join(current_dir, "downloads")
        file_path = os.path.join(downloads_dir, filename)
        
        if not os.path.exists(file_path):
            logger.error(f"Download file not found: {file_path}")
            raise HTTPException(status_code=404, detail="File not found")
        
        logger.info(f"Serving download file: {file_path}")
        
        return FileResponse(
            path=file_path,
            media_type="application/zip",
            filename=filename,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving download file {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error serving file")

@router.get("/downloads")
async def list_downloads():
    """
    List all available download files.
    """
    try:
        current_dir = os.getcwd()
        downloads_dir = os.path.join(current_dir, "downloads")
        
        if not os.path.exists(downloads_dir):
            return {"files": []}
        
        files = []
        for filename in os.listdir(downloads_dir):
            file_path = os.path.join(downloads_dir, filename)
            if os.path.isfile(file_path):
                stat = os.stat(file_path)
                files.append({
                    "filename": filename,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "download_url": f"/api/image-editing/downloads/{filename}"
                })
        
        logger.info(f"Listed {len(files)} download files")
        return {"files": files}
        
    except Exception as e:
        logger.error(f"Error listing downloads: {str(e)}")
        raise HTTPException(status_code=500, detail="Error listing downloads")

@router.delete("/downloads/{filename}")
async def delete_download(filename: str):
    """
    Manually delete a download file.
    """
    try:
        current_dir = os.getcwd()
        downloads_dir = os.path.join(current_dir, "downloads")
        file_path = os.path.join(downloads_dir, filename)
        
        if not os.path.exists(file_path):
            logger.error(f"Download file not found for deletion: {file_path}")
            raise HTTPException(status_code=404, detail="File not found")
        
        os.remove(file_path)
        logger.info(f"Successfully deleted download file: {file_path}")
        
        return {"message": f"File {filename} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting download file {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error deleting file")
        