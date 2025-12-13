"""
Product Location API Controller
Core inventory tracking endpoints
"""
import traceback
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import List, Optional

from utils.schema.billing_system.inventory_schema import (
    ProductLocationCreate,
    ProductLocationUpdate,
    ProductLocationResponse,
    ProductLocationFullDetails,
    ProductMovementCreate,
    ProductMovementResponse,
    ProductMovementWithDetails,
    ProductSearchFilters,
    LocationInventorySummary,
    BulkProductTransfer,
    BulkQuantityAdjustment
)
from services.billing_system.product_location_service import ProductLocationService
from core.database import db

router = APIRouter(prefix="/billing_system/api/inventory/products", tags=["Product Locations"])


def get_product_location_service():
    return ProductLocationService(db)


@router.post("/", response_model=ProductLocationResponse, status_code=201)
async def add_product_to_box(
    product: ProductLocationCreate,
    moved_by: str = Query(..., description="User performing the action"),
    service: ProductLocationService = Depends(get_product_location_service)
):
    """
    Add a product to a box
    
    Example for Real Jewelry:
    ```json
    {
        "box_id": 123,
        "product_type": "real_jewelry",
        "product_id": "uuid-of-variant",
        "product_name": "Gold Ring",
        "sku": "GR-001",
        "quantity": 5,
        "metal_weight_g": 3.5,
        "purity_k": 22.0
    }
    ```
    
    Example for Zakya Product:
    ```json
    {
        "box_id": 123,
        "product_type": "zakya_product",
        "product_id": "1923531000012345678",
        "product_name": "Silver Bracelet",
        "sku": "SB-001",
        "quantity": 10
    }
    ```
    """
    try:
        result = await service.add_product_to_box(product.dict(), moved_by)
        if not result:
            raise HTTPException(status_code=400, detail="Failed to add product")
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/search", response_model=List[ProductLocationFullDetails])
async def search_products(
    sku: Optional[str] = Query(None),
    product_name: Optional[str] = Query(None),
    product_type: Optional[str] = Query(None),
    location_id: Optional[int] = Query(None),
    shelf_id: Optional[int] = Query(None),
    box_id: Optional[int] = Query(None),
    has_serials: Optional[bool] = Query(None),
    min_quantity: Optional[int] = Query(None),
    max_quantity: Optional[int] = Query(None),
    service: ProductLocationService = Depends(get_product_location_service)
):
    """
    Search products across all locations with flexible filters
    """
    try:
        filters = {
            "sku": sku,
            "product_name": product_name,
            "product_type": product_type,
            "location_id": location_id,
            "shelf_id": shelf_id,
            "box_id": box_id,
            "has_serials": has_serials,
            "min_quantity": min_quantity,
            "max_quantity": max_quantity
        }
        result = await service.search_products(filters)
        return result
    except Exception as e:
        print(f"Traceback is {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/find/{product_type}/{product_id}", response_model=List[ProductLocationFullDetails])
async def find_product_locations(
    product_type: str,
    product_id: str,
    service: ProductLocationService = Depends(get_product_location_service)
):
    """
    Find all locations where a specific product is stored
    
    Example: GET /find/real_jewelry/uuid-123
    Example: GET /find/zakya_product/1923531000012345678
    """
    try:
        result = await service.find_product_locations(product_type, product_id)
        return result
    except Exception as e:
        print(f"Traceback is {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/inventory/summary", response_model=List[LocationInventorySummary])
async def get_inventory_summary(
    location_id: Optional[int] = Query(None),
    service: ProductLocationService = Depends(get_product_location_service)
):
    """
    Get inventory summary grouped by location
    If location_id provided, only shows that location's inventory
    """
    try:
        result = await service.get_inventory_summary_by_location(location_id)
        return result
    except Exception as e:
        print(f"Traceback is {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{location_id}", response_model=ProductLocationFullDetails)
async def get_product_location(
    location_id: int,
    service: ProductLocationService = Depends(get_product_location_service)
):
    """Get product location by ID with full details"""
    try:
        result = await service.get_product_location_by_id(location_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Product location {location_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{location_id}/quantity", response_model=ProductLocationResponse)
async def update_product_quantity(
    location_id: int,
    new_quantity: int = Body(..., ge=0),
    updated_by: str = Body(...),
    reason: Optional[str] = Body(None),
    service: ProductLocationService = Depends(get_product_location_service)
):
    """
    Update product quantity (for stock adjustments/recounts)
    
    Example:
    ```json
    {
        "new_quantity": 15,
        "updated_by": "john_doe",
        "reason": "Physical stock count correction"
    }
    ```
    """
    try:
        result = await service.update_product_quantity(location_id, new_quantity, updated_by, reason)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transfer", response_model=ProductLocationResponse)
async def transfer_product(
    from_location_id: int = Body(...),
    to_box_id: int = Body(...),
    quantity: int = Body(..., gt=0),
    moved_by: str = Body(...),
    reason: Optional[str] = Body(None),
    notes: Optional[str] = Body(None),
    service: ProductLocationService = Depends(get_product_location_service)
):
    """
    Transfer product from one box to another
    
    Example:
    ```json
    {
        "from_location_id": 45,
        "to_box_id": 78,
        "quantity": 3,
        "moved_by": "warehouse_manager",
        "reason": "Reorganizing inventory"
    }
    ```
    """
    try:
        result = await service.transfer_product(
            from_location_id, to_box_id, quantity, moved_by, reason, notes
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk-transfer", response_model=dict)
async def bulk_transfer_products(
    transfer: BulkProductTransfer,
    service: ProductLocationService = Depends(get_product_location_service)
):
    """
    Transfer multiple products to a single box at once
    
    Example:
    ```json
    {
        "product_locations": [12, 34, 56],
        "target_box_id": 78,
        "moved_by": "admin",
        "reason": "Consolidating inventory"
    }
    ```
    """
    try:
        transferred = []
        failed = []
        
        for location_id in transfer.product_locations:
            try:
                # Get current location to determine quantity
                location = await service.get_product_location_by_id(location_id)
                if location:
                    result = await service.transfer_product(
                        from_location_id=location_id,
                        to_box_id=transfer.target_box_id,
                        quantity=location['quantity'],
                        moved_by=transfer.moved_by,
                        reason=transfer.reason
                    )
                    transferred.append(location_id)
                else:
                    failed.append({"location_id": location_id, "error": "Not found"})
            except Exception as e:
                failed.append({"location_id": location_id, "error": str(e)})
        
        return {
            "transferred_count": len(transferred),
            "failed_count": len(failed),
            "transferred": transferred,
            "failed": failed
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{location_id}", status_code=200)
async def remove_product_from_box(
    location_id: int,
    quantity: int = Query(..., gt=0),
    removed_by: str = Query(...),
    reason: Optional[str] = Query(None),
    service: ProductLocationService = Depends(get_product_location_service)
):
    """
    Remove product quantity from a box
    If quantity equals total, the location record is deleted
    """
    try:
        success = await service.remove_product_from_box(location_id, quantity, removed_by, reason)
        return {"message": f"Successfully removed {quantity} units", "success": success}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/movements/{product_type}/{product_id}", response_model=List[ProductMovementWithDetails])
async def get_product_movement_history(
    product_type: str,
    product_id: str,
    limit: int = Query(100, ge=1, le=1000),
    service: ProductLocationService = Depends(get_product_location_service)
):
    """
    Get complete movement history for a specific product
    Shows all additions, transfers, removals, and adjustments
    """
    try:
        result = await service.get_product_movement_history(product_type, product_id, limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))