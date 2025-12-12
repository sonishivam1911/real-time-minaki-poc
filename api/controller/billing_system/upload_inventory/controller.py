"""
Inventory Upload Controller
API endpoint for CSV upload
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from services.billing_system.inventory_upload_service import InventoryUploadService


router = APIRouter(prefix="/api/inventory", tags=["Inventory"])


class UploadResponse(BaseModel):
    success: bool
    message: str
    total_rows: int
    processed: int
    failed: int
    errors: List[Dict]
    summary: Dict


@router.post("/upload", response_model=UploadResponse)
async def upload_inventory(
    file: UploadFile = File(...)
):
    """
    Upload CSV and populate billing_system_* tables
    
    Tables populated:
    - billing_system_products
    - billing_system_product_variants  
    - billing_system_metal_components
    - billing_system_diamond_components
    - billing_system_product_pricing
    - billing_system_inventory_lots
    - billing_system_stock_serials
    """
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(400, "File must be CSV")
    
    content = await file.read()
    service = InventoryUploadService()
    result = service.upload_csv(content)
    
    if not result['success'] and result['processed'] == 0:
        raise HTTPException(400, result['message'])
    
    return UploadResponse(**result)