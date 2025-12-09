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


# ============================================================================
# NYKA PRODUCT FILTER SCHEMAS
# ============================================================================

class PriceRangeFilter(BaseModel):
    """Price range filter"""
    min_price: Optional[Decimal] = Field(None, ge=0, description="Minimum price")
    max_price: Optional[Decimal] = Field(None, ge=0, description="Maximum price")


class NykaProductFilters(BaseModel):
    """Filters for Nyka product fetching"""
    
    # Pagination
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    
    # Basic filters
    search_query: Optional[str] = Field(None, description="Search in product title/description")
    vendor: Optional[str] = Field(None, description="Filter by vendor/brand")
    product_type: Optional[str] = Field(None, description="Filter by product type")
    tags: Optional[List[str]] = Field(None, description="Filter by tags (any match)")
    
    # Price filters
    price_range: Optional[PriceRangeFilter] = None
    
    # Category filters
    material: Optional[str] = Field(None, description="Filter by material (Alloy, Silver, etc.)")
    plating: Optional[str] = Field(None, description="Filter by plating (Gold, Rhodium, etc.)")
    style: Optional[str] = Field(None, description="Filter by jewelry style")
    occasion: Optional[str] = Field(None, description="Filter by occasion")
    segment: Optional[str] = Field(None, description="Filter by segment (Premium, Basic)")
    
    # Source system filters
    source: Optional[str] = Field(None, description="Filter by source: 'shopify', 'zakya', 'both'", pattern="^(shopify|zakya|both)$")
    has_images: Optional[bool] = Field(None, description="Filter products with/without images")
    stock_available: Optional[bool] = Field(None, description="Filter by stock availability")
    
    # Date filters
    created_after: Optional[datetime] = Field(None, description="Filter products created after this date")
    updated_after: Optional[datetime] = Field(None, description="Filter products updated after this date")
    
    # Sorting
    sort_by: Optional[str] = Field(
        default="created_at", 
        description="Sort field: 'created_at', 'price', 'title', 'vendor'",
        pattern="^(created_at|price|title|vendor)$"
    )
    sort_order: Optional[str] = Field(
        default="desc", 
        description="Sort order: 'asc' or 'desc'",
        pattern="^(asc|desc)$"
    )


class NykaProductCard(BaseModel):
    """Product card format for UI display - matches billing system format"""
    
    # Basic product info
    id: str = Field(..., description="Product identifier (SKU or product ID)")
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    vendor: Optional[str] = Field(None, description="Brand/vendor name")
    product_type: Optional[str] = Field(None, description="Product category")
    tags: List[str] = Field(default=[], description="Product tags")
    
    # Pricing
    price: Decimal = Field(..., description="Product price")
    compare_at_price: Optional[Decimal] = Field(None, description="Compare at price for discounts")
    
    # Inventory
    sku: str = Field(..., description="Product SKU")
    stock_quantity: Optional[int] = Field(None, description="Available stock")
    
    # Media
    image_url: Optional[str] = Field(None, description="Primary product image URL")
    image_alt_text: Optional[str] = Field(None, description="Image alt text")
    
    # Attributes (for jewelry)
    material: Optional[str] = Field(None, description="Material type")
    plating: Optional[str] = Field(None, description="Plating type")
    style: Optional[str] = Field(None, description="Jewelry style")
    color: Optional[str] = Field(None, description="Color")
    size: Optional[str] = Field(None, description="Size")
    
    # Source tracking
    source_system: str = Field(..., description="Source: 'shopify', 'zakya', or 'both'")
    data_quality_score: Optional[float] = Field(None, ge=0, le=1, description="Data completeness score")
    
    # Timestamps
    created_at: Optional[datetime] = Field(None, description="Created timestamp")
    updated_at: Optional[datetime] = Field(None, description="Updated timestamp")


class NykaProductListResponse(BaseModel):
    """Response format matching billing system pattern"""
    total: int = Field(..., description="Total number of products matching filters")
    products: List[NykaProductCard] = Field(..., description="List of product cards")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    filters_applied: dict = Field(..., description="Summary of applied filters")
    data_summary: dict = Field(default={}, description="Additional metadata about the results")