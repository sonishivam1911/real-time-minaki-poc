"""
Storage Shelf API Controller
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional

from utils.schema.billing_system.inventory_schema import (
    StorageShelfCreate,
    StorageShelfUpdate,
    StorageShelfResponse,
    StorageShelfWithLocation
)
from services.billing_system.shelf_service import ShelfService
from core.database import db

router = APIRouter(prefix="/billing_system/api/inventory/shelves", tags=["Storage Shelves"])


def get_shelf_service():
    return ShelfService(db)


@router.post("/", response_model=StorageShelfResponse, status_code=201)
async def create_shelf(
    shelf: StorageShelfCreate,
    service: ShelfService = Depends(get_shelf_service)
):
    """Create a new shelf"""
    try:
        result = await service.create_shelf(shelf.dict())
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create shelf")
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bulk", response_model=List[StorageShelfResponse])
async def bulk_create_shelves(
    shelves: List[StorageShelfCreate],
    service: ShelfService = Depends(get_shelf_service)
):
    """Create multiple shelves at once (for grid setup)"""
    try:
        shelves_data = [shelf.dict() for shelf in shelves]
        result = await service.bulk_create_shelves(shelves_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/location/{location_id}", response_model=List[StorageShelfWithLocation])
async def get_shelves_by_location(
    location_id: int,
    active_only: bool = Query(True),
    service: ShelfService = Depends(get_shelf_service)
):
    """Get all shelves in a specific location"""
    try:
        result = await service.get_shelves_by_location(location_id, active_only)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/location/{location_id}/grid", response_model=List[dict])
async def get_shelf_grid_layout(
    location_id: int,
    service: ShelfService = Depends(get_shelf_service)
):
    """Get shelf grid layout for drag-drop UI"""
    try:
        result = await service.get_shelf_grid_layout(location_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{shelf_id}", response_model=StorageShelfWithLocation)
async def get_shelf(
    shelf_id: int,
    service: ShelfService = Depends(get_shelf_service)
):
    """Get shelf by ID"""
    try:
        result = await service.get_shelf_by_id(shelf_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Shelf {shelf_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{shelf_id}", response_model=StorageShelfResponse)
async def update_shelf(
    shelf_id: int,
    shelf: StorageShelfUpdate,
    service: ShelfService = Depends(get_shelf_service)
):
    """Update shelf details"""
    try:
        update_data = {k: v for k, v in shelf.dict().items() if v is not None}
        result = await service.update_shelf(shelf_id, update_data)
        if not result:
            raise HTTPException(status_code=404, detail=f"Shelf {shelf_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{shelf_id}/position")
async def update_shelf_position(
    shelf_id: int,
    visual_x: float,
    visual_y: float,
    service: ShelfService = Depends(get_shelf_service)
):
    """Update shelf visual position (for drag-drop)"""
    try:
        result = await service.update_shelf_position(shelf_id, visual_x, visual_y)
        if not result:
            raise HTTPException(status_code=404, detail=f"Shelf {shelf_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{shelf_id}", status_code=204)
async def delete_shelf(
    shelf_id: int,
    service: ShelfService = Depends(get_shelf_service)
):
    """Soft delete a shelf"""
    try:
        success = await service.delete_shelf(shelf_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Shelf {shelf_id} not found")
        return {"message": "Shelf deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))