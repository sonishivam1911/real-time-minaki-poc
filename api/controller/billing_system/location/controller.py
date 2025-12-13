"""
Storage Location API Controller
FastAPI router for location management
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List

from utils.schema.billing_system.inventory_schema import (
    StorageLocationCreate,
    StorageLocationUpdate,
    StorageLocationResponse,
    LocationStatistics
)
from services.billing_system.location_service import LocationService
from core.database import db

router = APIRouter(prefix="/billing_system/api/inventory/locations", tags=["Storage Locations"])


# Dependency to get service (you'll inject your db connection)
def get_location_service():
    return LocationService(db)


@router.post("/", response_model=StorageLocationResponse, status_code=201)
def create_location(
    location: StorageLocationCreate,
    service: LocationService = Depends(get_location_service)
):
    """
    Create a new storage location
    
    Example:
    ```json
    {
        "location_name": "Upper Floor",
        "location_code": "UF",
        "description": "Main showroom upper floor",
        "is_active": true
    }
    ```
    """
    try:
        result = service.create_location(location.dict())
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create location")
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[StorageLocationResponse])
def get_all_locations(
    active_only: bool = True,
    service: LocationService = Depends(get_location_service)
):
    """Get all storage locations"""
    try:
        result = service.get_all_locations(active_only)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/with-stats", response_model=List[dict])
def get_locations_with_stats(
    service: LocationService = Depends(get_location_service)
):
    """Get all locations with statistics (shelf count, box count, product count)"""
    try:
        result = service.get_all_locations_with_stats()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{location_id}", response_model=StorageLocationResponse)
def get_location(
    location_id: int,
    service: LocationService = Depends(get_location_service)
):
    """Get location by ID"""
    try:
        result = service.get_location_by_id(location_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Location {location_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{location_id}/statistics", response_model=LocationStatistics)
def get_location_statistics(
    location_id: int,
    service: LocationService = Depends(get_location_service)
):
    """Get detailed statistics for a location"""
    try:
        result = service.get_location_statistics(location_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Location {location_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{location_id}", response_model=StorageLocationResponse)
def update_location(
    location_id: int,
    location: StorageLocationUpdate,
    service: LocationService = Depends(get_location_service)
):
    """Update location details"""
    try:
        # Filter out None values
        update_data = {k: v for k, v in location.dict().items() if v is not None}
        result = service.update_location(location_id, update_data)
        if not result:
            raise HTTPException(status_code=404, detail=f"Location {location_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{location_id}", status_code=204)
def delete_location(
    location_id: int,
    service: LocationService = Depends(get_location_service)
):
    """Soft delete a location (sets is_active to false)"""
    try:
        success = service.delete_location(location_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Location {location_id} not found")
        return {"message": "Location deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))