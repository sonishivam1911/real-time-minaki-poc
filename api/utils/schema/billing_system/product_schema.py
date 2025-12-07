"""
Pydantic schemas for Product and related entities
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


# ============================================================================
# METAL COMPONENT SCHEMAS
# ============================================================================

class MetalComponentBase(BaseModel):
    """Base schema for metal component"""
    metal_type: str = Field(..., description="Type of metal (gold, silver, platinum)")
    purity_k: Decimal = Field(..., description="Purity in karats (e.g., 22.00, 18.00)")
    gross_weight_g: Decimal = Field(..., description="Gross weight in grams")
    net_weight_g: Decimal = Field(..., description="Net weight in grams")
    wastage_percent: Decimal = Field(default=8.0, description="Wastage percentage")
    making_charge_per_g: Decimal = Field(default=150.00, description="Making charge per gram")
    making_charge_flat: Decimal = Field(default=0, description="Flat making charge")
    metal_rate_per_g: Decimal = Field(..., description="Metal rate per gram")
    notes: Optional[str] = None


class MetalComponentCreate(MetalComponentBase):
    """Schema for creating metal component"""
    pass


class MetalComponentResponse(MetalComponentBase):
    """Schema for metal component response"""
    id: str
    variant_id: str
    metal_value: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# DIAMOND COMPONENT SCHEMAS
# ============================================================================

class DiamondComponentBase(BaseModel):
    """Base schema for diamond component"""
    cert_no: Optional[str] = Field(None, description="Certificate number (GIA/IGI)")
    shape: str = Field(..., description="Diamond shape (round, princess, etc.)")
    carat: Decimal = Field(..., description="Carat weight")
    cut: Optional[str] = Field(None, description="Cut grade")
    clarity: Optional[str] = Field(None, description="Clarity grade (VVS1, VS2, etc.)")
    color_grade: Optional[str] = Field(None, description="Color grade (D, E, F, etc.)")
    stone_price_per_carat: Decimal = Field(..., description="Price per carat")
    origin: Optional[str] = None
    notes: Optional[str] = None


class DiamondComponentCreate(DiamondComponentBase):
    """Schema for creating diamond component"""
    pass


class DiamondComponentResponse(DiamondComponentBase):
    """Schema for diamond component response"""
    id: str
    variant_id: str
    stone_total_price: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# PRICING BREAKDOWN SCHEMAS
# ============================================================================

class PricingBreakdownResponse(BaseModel):
    """Schema for pricing breakdown response"""
    variant_id: str
    total_metal_value: Decimal
    total_stone_value: Decimal
    total_making_charges: Decimal
    total_wastage_charges: Decimal
    total_discounts: Decimal
    tax_rate_percent: Decimal
    tax_amount: Decimal
    final_cost: Decimal
    suggested_retail_price: Decimal
    last_calculated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# VARIANT SCHEMAS
# ============================================================================

class VariantBase(BaseModel):
    """Base schema for product variant"""
    sku: Optional[str] = None
    barcode: Optional[str] = None
    sku_name: Optional[str] = None
    status: str = Field(default="active", description="Variant status")
    price: Decimal = Field(..., description="Retail price")
    weight_g: Decimal = Field(default=0, description="Gross weight")
    net_weight_g: Decimal = Field(default=0, description="Net weight")
    purity_k: Optional[Decimal] = Field(None, description="Metal purity")
    track_serials: bool = Field(default=False, description="Track serial numbers")


class VariantCreate(VariantBase):
    """Schema for creating variant"""
    metal_components: List[MetalComponentCreate] = []
    diamond_components: List[DiamondComponentCreate] = []


class VariantResponse(VariantBase):
    """Schema for variant response"""
    id: str
    product_id: str
    base_cost: Decimal
    metal_components: List[MetalComponentResponse] = []
    diamond_components: List[DiamondComponentResponse] = []
    pricing_breakdown: Optional[PricingBreakdownResponse] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# PRODUCT SCHEMAS
# ============================================================================

class ProductBase(BaseModel):
    """Base schema for product"""
    title: str = Field(..., description="Product title")
    handle: Optional[str] = Field(None, description="URL-friendly identifier")
    description: Optional[str] = None
    vendor: Optional[str] = None
    product_type: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    is_active: bool = True


class ProductCreate(ProductBase):
    """Schema for creating product with variants"""
    variants: List[VariantCreate] = []


class ProductResponse(ProductBase):
    """Schema for product response"""
    id: str
    variants: List[VariantResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    """Schema for paginated product list"""
    total: int
    products: List[ProductResponse]
    page: int
    page_size: int


# ============================================================================
# UPDATE SCHEMAS
# ============================================================================

class MetalComponentUpdate(BaseModel):
    """Schema for updating metal component"""
    id: str
    metal_rate_per_g: Optional[Decimal] = None
    making_charge_per_g: Optional[Decimal] = None
    making_charge_flat: Optional[Decimal] = None
    wastage_percent: Optional[Decimal] = None


class VariantUpdate(BaseModel):
    """Schema for updating variant"""
    sku: Optional[str] = None
    price: Optional[Decimal] = None
    status: Optional[str] = None
    metal_components: Optional[List[MetalComponentUpdate]] = None


# ============================================================================
# PRICING RECALCULATION SCHEMAS
# ============================================================================

class MetalRateUpdate(BaseModel):
    """Schema for bulk metal rate updates"""
    gold_22k: Optional[Decimal] = None
    gold_18k: Optional[Decimal] = None
    silver: Optional[Decimal] = None
    platinum: Optional[Decimal] = None


class PricingRecalculationRequest(BaseModel):
    """Schema for pricing recalculation request"""
    variant_ids: Optional[List[str]] = Field(
        None, 
        description="Specific variant IDs to recalculate. If None, recalculate all."
    )
    update_metal_rates: Optional[MetalRateUpdate] = Field(
        None,
        description="New metal rates to apply before recalculation"
    )


class PricingRecalculationResponse(BaseModel):
    """Schema for pricing recalculation response"""
    success: bool
    variants_updated: int
    message: str
    errors: List[str] = []