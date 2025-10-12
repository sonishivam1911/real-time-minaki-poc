from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from typing import Dict, Any
import uuid
import io

from services.shopify.product import ShopifyProductService
from services.shopify.base_connector import BaseShopifyConnector
from services.shopify.metafield_migration_service import MetafieldMigrationService
from controller.shopify.dependencies import get_shopify_connector
from utils.schema.metafield_migration_schema import (
    MetafieldMigrationResponse,
    MetafieldMigrationStatusResponse,
    CSVValidationResponse
)
from utils.csv_parser import (
    parse_metafield_mapping_csv, 
    validate_mapping_rules,
    export_mapping_template
)


router = APIRouter()


# In-memory job storage (use Redis/Database in production)
migration_jobs: Dict[str, Dict[str, Any]] = {}


def get_migration_service(
    connector = Depends(get_shopify_connector)
) -> MetafieldMigrationService:
    """Dependency injection for MetafieldMigrationService"""
    shopify_service = ShopifyProductService()
    return MetafieldMigrationService(shopify_service)


@router.get("/template")
async def download_csv_template():
    """
    Download CSV template for metafield mapping.
    
    Returns a CSV file with example mapping rules.
    """
    try:
        template_csv = export_mapping_template()
        
        return StreamingResponse(
            io.BytesIO(template_csv),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=metafield_mapping_template.csv"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating template: {str(e)}")


@router.post("/validate", response_model=CSVValidationResponse)
async def validate_csv(
    file: UploadFile = File(..., description="CSV file with metafield mapping rules")
):
    """
    Validate uploaded CSV file without starting migration.
    
    **Upload Requirements:**
    - File format: CSV
    - Required columns: input_namespace, input_key, input_value, input_type, 
                       output_namespace, output_key, output_value, output_type
    
    **Returns:**
    - Validation statistics
    - Sample rules preview
    - Any parsing errors
    """
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Please upload a CSV file."
            )
        
        # Read file content
        file_content = await file.read()
        
        # Parse CSV
        mapping_rules = parse_metafield_mapping_csv(file_content)
        
        # Validate rules
        validation_stats = validate_mapping_rules(mapping_rules)
        
        return CSVValidationResponse(
            success=True,
            message=f"CSV validated successfully. Found {len(mapping_rules)} mapping rules.",
            validation_stats=validation_stats
        )
        
    except ValueError as e:
        return CSVValidationResponse(
            success=False,
            message="CSV validation failed",
            validation_stats={},
            error=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error validating CSV: {str(e)}"
        )


@router.post("/preview", response_model=MetafieldMigrationResponse)
async def preview_migration(
    file: UploadFile = File(..., description="CSV file with metafield mapping rules"),
    max_products: int = Query(default=10, ge=1, le=50, description="Number of products to preview"),
    migration_service: MetafieldMigrationService = Depends(get_migration_service)
):
    """
    Preview what the migration would do without actually creating metafields.
    
    **Process:**
    1. Parses uploaded CSV
    2. Checks first N products (default: 10)
    3. Shows which metafields would be created
    4. Returns statistics and sample matches
    
    **Use this before running full migration to verify your CSV mapping!**
    """
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Please upload a CSV file."
            )
        
        # Read and parse CSV
        file_content = await file.read()
        mapping_rules = parse_metafield_mapping_csv(file_content)
        
        # Validate rules
        validation_stats = validate_mapping_rules(mapping_rules)
        
        # Run preview
        preview_results = migration_service.preview_migration(
            mapping_rules=mapping_rules,
            max_products=max_products
        )
        
        return MetafieldMigrationResponse(
            success=True,
            message=f"Preview completed for {preview_results['total_products_checked']} products. "
                   f"Found {preview_results['total_matches_found']} potential metafields to create.",
            validation_stats=validation_stats,
            preview_results=preview_results
        )
        
    except ValueError as e:
        return MetafieldMigrationResponse(
            success=False,
            message="Preview failed",
            error=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during preview: {str(e)}"
        )


@router.post("/start", response_model=MetafieldMigrationResponse)
async def start_migration(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="CSV file with metafield mapping rules"),
    migration_service: MetafieldMigrationService = Depends(get_migration_service)
):
    """
    Start metafield migration job (async background task).
    
    **CSV Format:**
    ```csv
    input_namespace,input_key,input_value,input_type,output_namespace,output_key,output_value,output_type
    addfica,gender,Women,single_line_text_shopify,shopify,target-gender,gid://shopify/Metaobject/456,metaobject_reference
    addfica,data1,Kundan,single_line_text_shopify,shopify,jewelry-type,gid://shopify/Metaobject/789,metaobject_reference
    ```
    
    **Process:**
    1. Parses CSV with mapping rules
    2. Iterates through ALL products in Shopify (async)
    3. For each product:
       - Checks if metafield matches: input_namespace.input_key = input_value
       - If match found: Creates new metafield output_namespace.output_key = output_value
    4. Respects Shopify rate limits (0.5s between requests)
    
    **Returns immediately** with job_id. Check status at `/status/{job_id}`
    """
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Please upload a CSV file."
            )
        
        # Read and parse CSV
        file_content = await file.read()
        mapping_rules = parse_metafield_mapping_csv(file_content)
        
        # Validate rules
        validation_stats = validate_mapping_rules(mapping_rules)
        
        # Create job ID
        job_id = str(uuid.uuid4())
        
        # Initialize job status
        migration_jobs[job_id] = {
            "status": "pending",
            "total_products": "calculating...",
            "processed": 0,
            "updated": 0,
            "skipped": 0,
            "total_metafields_created": 0,
            "errors": [],
            "mapping_rules_count": len(mapping_rules),
            "filename": file.filename
        }
        
        # Start background task
        background_tasks.add_task(
            migration_service.run_migration,
            mapping_rules,
            job_id,
            migration_jobs[job_id]
        )
        
        return MetafieldMigrationResponse(
            success=True,
            message=f"Migration job started with {len(mapping_rules)} mapping rules. "
                   f"Check status at /metafield-migration/status/{job_id}",
            job_id=job_id,
            validation_stats=validation_stats
        )
        
    except ValueError as e:
        return MetafieldMigrationResponse(
            success=False,
            message="Failed to start migration",
            error=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error starting migration: {str(e)}"
        )


@router.get("/status/{job_id}", response_model=MetafieldMigrationStatusResponse)
async def get_migration_status(job_id: str):
    """
    Get status of a running or completed migration job.
    
    **Status Values:**
    - `pending`: Job created, waiting to start
    - `processing`: Job is currently running
    - `completed`: Job finished successfully
    - `failed`: Job encountered an error
    
    **Returns:**
    - Current progress (processed, updated, skipped)
    - Total metafields created
    - Any errors encountered
    - Timing information (start, end, duration)
    """
    if job_id not in migration_jobs:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found. It may have expired or never existed."
        )
    
    job_data = migration_jobs[job_id]
    
    # Build status message
    status = job_data["status"]
    if status == "processing":
        message = f"Migration in progress... Processed {job_data['processed']} products"
    elif status == "completed":
        message = (f"Migration completed! "
                  f"Processed {job_data['processed']} products, "
                  f"Updated {job_data['updated']}, "
                  f"Created {job_data.get('total_metafields_created', 0)} metafields")
    elif status == "failed":
        message = f"Migration failed. Check errors for details."
    else:
        message = "Migration pending..."
    
    return MetafieldMigrationStatusResponse(
        success=True,
        job_id=job_id,
        message=message,
        **job_data
    )


@router.get("/jobs", response_model=Dict[str, Any])
async def list_all_jobs():
    """
    List all migration jobs (active and completed).
    
    **Returns:**
    - Summary of all jobs
    - Job counts by status
    """
    if not migration_jobs:
        return {
            "success": True,
            "message": "No migration jobs found",
            "total_jobs": 0,
            "jobs": []
        }
    
    # Count by status
    status_counts = {}
    for job_data in migration_jobs.values():
        status = job_data["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # Get job summaries
    job_summaries = []
    for job_id, job_data in migration_jobs.items():
        job_summaries.append({
            "job_id": job_id,
            "status": job_data["status"],
            "processed": job_data["processed"],
            "updated": job_data["updated"],
            "total_metafields_created": job_data.get("total_metafields_created", 0),
            "filename": job_data.get("filename", "unknown"),
            "start_time": job_data.get("start_time")
        })
    
    # Sort by start time (most recent first)
    job_summaries.sort(
        key=lambda x: x.get("start_time", 0) or 0,
        reverse=True
    )
    
    return {
        "success": True,
        "message": f"Found {len(migration_jobs)} migration jobs",
        "total_jobs": len(migration_jobs),
        "status_counts": status_counts,
        "jobs": job_summaries
    }


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """
    Delete a migration job from memory.
    
    **Note:** Only delete completed or failed jobs.
    Cannot delete jobs that are currently processing.
    """
    if job_id not in migration_jobs:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
    
    job_data = migration_jobs[job_id]
    
    if job_data["status"] == "processing":
        raise HTTPException(
            status_code=400,
            detail="Cannot delete job that is currently processing"
        )
    
    del migration_jobs[job_id]
    
    return {
        "success": True,
        "message": f"Job {job_id} deleted successfully"
    }