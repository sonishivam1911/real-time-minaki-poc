"""
Storage Box API Controller
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List

from utils.schema.billing_system.inventory_schema import (
    StorageBoxCreate,
    StorageBoxUpdate,
    StorageBoxResponse,
    StorageBoxWithDetails,
    BoxMovementCreate,
    BoxMovementResponse,
    QRCodeScanResponse
)
from services.billing_system.box_service import BoxService
from core.database import db

router = APIRouter(prefix="/billing_system/api/inventory/boxes", tags=["Storage Boxes"])


def get_box_service():
    return BoxService(db)


@router.post("/", response_model=StorageBoxResponse, status_code=201)
async def create_box(
    box: StorageBoxCreate,
    service: BoxService = Depends(get_box_service)
):
    """Create a new storage box"""
    try:
        result = await service.create_box(box.dict())
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create box")
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/qr/{box_code}", response_model=QRCodeScanResponse)
async def scan_qr_code(
    box_code: str,
    service: BoxService = Depends(get_box_service)
):
    """
    Scan QR code and get box contents
    This endpoint is called when scanning a box QR code
    """
    try:
        result = await service.get_box_contents_by_code(box_code)
        if not result:
            raise HTTPException(status_code=404, detail=f"Box with code {box_code} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shelf/{shelf_id}", response_model=List[StorageBoxResponse])
async def get_boxes_by_shelf(
    shelf_id: int,
    active_only: bool = Query(True),
    service: BoxService = Depends(get_box_service)
):
    """Get all boxes on a specific shelf"""
    try:
        result = await service.get_boxes_by_shelf(shelf_id, active_only)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{box_id}", response_model=StorageBoxWithDetails)
async def get_box(
    box_id: int,
    service: BoxService = Depends(get_box_service)
):
    """Get box by ID with full details"""
    try:
        result = await service.get_box_by_id(box_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Box {box_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{box_id}/contents", response_model=dict)
async def get_box_contents(
    box_id: int,
    service: BoxService = Depends(get_box_service)
):
    """Get all products in a box"""
    try:
        result = await service.get_box_contents(box_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Box {box_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{box_id}/movements", response_model=List[BoxMovementResponse])
async def get_box_movement_history(
    box_id: int,
    limit: int = Query(50, ge=1, le=500),
    service: BoxService = Depends(get_box_service)
):
    """Get movement history for a box"""
    try:
        result = await service.get_box_movement_history(box_id, limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{box_id}", response_model=StorageBoxResponse)
async def update_box(
    box_id: int,
    box: StorageBoxUpdate,
    service: BoxService = Depends(get_box_service)
):
    """Update box details"""
    try:
        update_data = {k: v for k, v in box.dict().items() if v is not None}
        result = await service.update_box(box_id, update_data)
        if not result:
            raise HTTPException(status_code=404, detail=f"Box {box_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{box_id}/move", response_model=dict)
async def move_box_to_shelf(
    box_id: int,
    movement: BoxMovementCreate,
    service: BoxService = Depends(get_box_service)
):
    """Move a box to a different shelf"""
    try:
        result = await service.move_box_to_shelf(
            box_id=box_id,
            new_shelf_id=movement.to_shelf_id,
            moved_by=movement.moved_by,
            reason=movement.reason,
            notes=movement.notes
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{box_id}", status_code=204)
async def delete_box(
    box_id: int,
    service: BoxService = Depends(get_box_service)
):
    """Soft delete a box (must be empty)"""
    try:
        success = await service.delete_box(box_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Box {box_id} not found")
        return {"message": "Box deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))