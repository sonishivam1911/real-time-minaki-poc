"""
Pydantic Schemas for Inventory Management System
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal
from datetime import datetime
from decimal import Decimal


# ============================================================================
# STORAGE LOCATION SCHEMAS
# ============================================================================

class StorageLocationBase(BaseModel):
    location_name: str
    location_code: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    metadata: Optional[dict] = None


class StorageLocationCreate(StorageLocationBase):
    pass


class StorageLocationUpdate(BaseModel):
    location_name: Optional[str] = None
    location_code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    metadata: Optional[dict] = None


class StorageLocationResponse(StorageLocationBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# STORAGE SHELF SCHEMAS
# ============================================================================

class StorageShelfBase(BaseModel):
    location_id: int
    shelf_code: str
    shelf_name: Optional[str] = None
    row_position: Optional[int] = None
    column_position: Optional[int] = None
    visual_x: Optional[Decimal] = None
    visual_y: Optional[Decimal] = None
    description: Optional[str] = None
    is_active: bool = True
    metadata: Optional[dict] = None

    class Config:
        extra = 'ignore'  # Ignore extra fields like shelf_level, capacity


class StorageShelfCreate(StorageShelfBase):
    pass


class StorageShelfUpdate(BaseModel):
    location_id: Optional[int] = None
    shelf_code: Optional[str] = None
    shelf_name: Optional[str] = None
    row_position: Optional[int] = None
    column_position: Optional[int] = None
    visual_x: Optional[Decimal] = None
    visual_y: Optional[Decimal] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    metadata: Optional[dict] = None

    class Config:
        extra = 'ignore'  # Ignore extra fields like shelf_level, capacity


class StorageShelfResponse(StorageShelfBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StorageShelfWithLocation(StorageShelfResponse):
    location_name: str
    location_code: Optional[str] = None


# ============================================================================
# STORAGE BOX SCHEMAS
# ============================================================================

class StorageBoxBase(BaseModel):
    shelf_id: int
    box_code: str
    box_label: Optional[str] = None
    length_cm: Optional[Decimal] = None
    width_cm: Optional[Decimal] = None
    height_cm: Optional[Decimal] = None
    color_code: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    metadata: Optional[dict] = None


class StorageBoxCreate(StorageBoxBase):
    pass


class StorageBoxUpdate(BaseModel):
    shelf_id: Optional[int] = None
    box_code: Optional[str] = None
    box_label: Optional[str] = None
    length_cm: Optional[Decimal] = None
    width_cm: Optional[Decimal] = None
    height_cm: Optional[Decimal] = None
    color_code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    metadata: Optional[dict] = None


class StorageBoxResponse(StorageBoxBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StorageBoxWithDetails(StorageBoxResponse):
    shelf_code: str
    shelf_name: Optional[str] = None
    location_name: str
    location_id: int


# ============================================================================
# PRODUCT LOCATION SCHEMAS
# ============================================================================

ProductType = Literal["real_jewelry", "zakya_product"]


class ProductLocationBase(BaseModel):
    box_id: int
    product_type: ProductType
    product_id: str  # UUID for real jewelry, item_id for Zakya
    product_name: str
    sku: Optional[str] = None
    quantity: int = Field(ge=0)
    
    # Real jewelry specific
    serial_numbers: Optional[List[str]] = None
    metal_weight_g: Optional[Decimal] = None
    purity_k: Optional[Decimal] = None
    
    # Zakya specific
    zakya_metadata: Optional[dict] = None
    
    # Tracking
    last_counted_at: Optional[datetime] = None
    last_counted_by: Optional[str] = None
    discrepancy_notes: Optional[str] = None


class ProductLocationCreate(ProductLocationBase):
    pass


class ProductLocationUpdate(BaseModel):
    box_id: Optional[int] = None
    quantity: Optional[int] = Field(None, ge=0)
    serial_numbers: Optional[List[str]] = None
    metal_weight_g: Optional[Decimal] = None
    purity_k: Optional[Decimal] = None
    zakya_metadata: Optional[dict] = None
    last_counted_at: Optional[datetime] = None
    last_counted_by: Optional[str] = None
    discrepancy_notes: Optional[str] = None


class ProductLocationResponse(ProductLocationBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductLocationFullDetails(ProductLocationResponse):
    location_id: int
    location_name: str
    location_code: Optional[str] = None
    shelf_id: int
    shelf_code: str
    shelf_name: Optional[str] = None
    box_code: str
    box_label: Optional[str] = None


# ============================================================================
# PRODUCT MOVEMENT SCHEMAS
# ============================================================================

MovementType = Literal["add", "remove", "transfer", "adjustment", "recount"]


class ProductMovementBase(BaseModel):
    product_type: ProductType
    product_id: str
    sku: Optional[str] = None
    product_name: Optional[str] = None
    movement_type: MovementType
    quantity_moved: int
    
    # From location
    from_location_id: Optional[int] = None
    from_shelf_id: Optional[int] = None
    from_box_id: Optional[int] = None
    
    # To location
    to_location_id: Optional[int] = None
    to_shelf_id: Optional[int] = None
    to_box_id: Optional[int] = None
    
    # Tracking
    moved_by: str
    reason: Optional[str] = None
    notes: Optional[str] = None
    serial_numbers_moved: Optional[List[str]] = None


class ProductMovementCreate(ProductMovementBase):
    pass


class ProductMovementResponse(ProductMovementBase):
    id: int
    movement_date: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class ProductMovementWithDetails(ProductMovementResponse):
    from_location_name: Optional[str] = None
    from_shelf_code: Optional[str] = None
    from_box_code: Optional[str] = None
    to_location_name: Optional[str] = None
    to_shelf_code: Optional[str] = None
    to_box_code: Optional[str] = None


# ============================================================================
# BOX MOVEMENT SCHEMAS
# ============================================================================

class BoxMovementBase(BaseModel):
    box_id: int
    from_shelf_id: Optional[int] = None
    to_shelf_id: int
    moved_by: str
    reason: Optional[str] = None
    notes: Optional[str] = None


class BoxMovementCreate(BoxMovementBase):
    pass


class BoxMovementResponse(BoxMovementBase):
    id: int
    movement_date: datetime
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# SEARCH & FILTER SCHEMAS
# ============================================================================

class ProductSearchFilters(BaseModel):
    sku: Optional[str] = None
    product_name: Optional[str] = None
    product_type: Optional[ProductType] = None
    location_id: Optional[int] = None
    shelf_id: Optional[int] = None
    box_id: Optional[int] = None
    has_serials: Optional[bool] = None
    min_quantity: Optional[int] = None
    max_quantity: Optional[int] = None


class LocationInventorySummary(BaseModel):
    location_id: int
    location_name: str
    product_type: ProductType
    product_id: str
    product_name: str
    sku: Optional[str] = None
    total_quantity: int
    num_boxes: int
    box_codes: List[str]


# ============================================================================
# BULK OPERATIONS SCHEMAS
# ============================================================================

class BulkProductTransfer(BaseModel):
    product_locations: List[int]  # List of product_location IDs
    target_box_id: int
    moved_by: str
    reason: Optional[str] = None


class BulkQuantityAdjustment(BaseModel):
    adjustments: List[dict]  # [{"product_location_id": 1, "new_quantity": 10}]
    adjusted_by: str
    reason: str


# ============================================================================
# QR CODE SCHEMAS
# ============================================================================

class QRCodeScanResponse(BaseModel):
    box_id: int
    box_code: str
    box_label: Optional[str] = None
    shelf_code: str
    location_name: str
    products: List[ProductLocationResponse]
    total_items: int


# ============================================================================
# STATISTICS SCHEMAS
# ============================================================================

class LocationStatistics(BaseModel):
    location_id: int
    location_name: str
    total_boxes: int
    total_shelves: int
    total_products: int
    total_quantity: int
    unique_skus: int


class InventoryValueSummary(BaseModel):
    location_id: int
    location_name: str
    total_value: Decimal
    product_count: int