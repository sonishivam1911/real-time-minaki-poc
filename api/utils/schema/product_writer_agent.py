from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ProductInput(BaseModel):
    """Input product attributes from CSV/Google Sheet"""
    category: str = Field(..., description="Product category (e.g., Earrings, Necklace)")
    line: str = Field(..., description="Product line/collection name")
    style: str = Field(..., description="Design style")
    components: str = Field(..., description="Materials/parts used")
    base_metal: str = Field(..., description="Base metal (Gold, Silver, etc.)")
    finish: str = Field(..., description="Finish type (Polished, Matte, etc.)")
    work: str = Field(..., description="Craftsmanship type")
    finding: str = Field(..., description="Hardware type (clasps, hooks, etc.)")
    seo_keywords: str = Field(..., description="Comma-separated keywords, first is primary")


class ActionInput(BaseModel):
    """ReAct pattern action_input - the 4 main outputs"""
    title: str = Field(..., max_length=100, description="Product title")
    description: str = Field(..., description="Detailed product description")
    seo_meta_title: str = Field(..., max_length=60, description="SEO meta title")
    seo_meta_description: str = Field(..., max_length=160, description="SEO meta description")
    styling_tip: str = Field(..., description="Styling recommendation")
    faqs: str = Field(..., description="FAQs in format: Q1: ... A1: ... Q2: ... A2: ...")


class ProductOutput(BaseModel):
    """ReAct pattern output format"""
    action: str = Field(default="generate_product_content", description="Action name")
    action_input: ActionInput = Field(..., description="Generated content")


class AgentState(BaseModel):
    """LangGraph state - input and output"""
    product_input: ProductInput
    product_output: Optional[ProductOutput] = None
    error: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class BatchRequest(BaseModel):
    """API request for batch processing"""
    products: list[ProductInput]


class BatchResponse(BaseModel):
    """API response for batch processing"""
    results: list[ProductOutput]
    errors: list[dict] = []
    

class ProductCSVRow(BaseModel):
    """
    Single row from the Product Listing Pipeline CSV
    All columns from your Google Sheet
    """
    timestamp: Optional[str] = Field(None, description="Timestamp")
    email_address: Optional[str] = Field(None, description="Email address")
    product_sku: Optional[str] = Field(None, description="Product SKU")
    
    # Images
    high_resolution_1: Optional[str] = Field(None, description="High Resolution - 1")
    high_resolution_2: Optional[str] = Field(None, description="High Resolution - 2")
    high_resolution_3: Optional[str] = Field(None, description="High Resolution - 3")
    high_resolution_4: Optional[str] = Field(None, description="High Resolution - 4")
    high_resolution_5: Optional[str] = Field(None, description="High Resolution - 5")
    
    web_format_1: Optional[str] = Field(None, description="Web Format - 1")
    web_format_2: Optional[str] = Field(None, description="Web Format - 2")
    web_format_3: Optional[str] = Field(None, description="Web Format - 3")
    web_format_4: Optional[str] = Field(None, description="Web Format - 4")
    web_format_5: Optional[str] = Field(None, description="Wrb Format- 5")
    
    # Product Attributes
    gender: Optional[str] = Field(None, description="Gender")
    category: Optional[str] = Field(None, description="Category")
    line: Optional[str] = Field(None, description="Line")
    style: Optional[str] = Field(None, description="Style")
    hsn_code: Optional[str] = Field(None, description="HSN Code")
    
    # Details
    components: Optional[str] = Field(None, description="Components")
    base_metal: Optional[str] = Field(None, description="Base Metal")
    finish: Optional[str] = Field(None, description="Finish")
    work: Optional[str] = Field(None, description="Work")
    finding: Optional[str] = Field(None, description="Finding")
    
    # Colors
    primary_color: Optional[str] = Field(None, description="Primary Color")
    secondary_color: Optional[str] = Field(None, description="Secondary Color")
    
    # Other
    occasions: Optional[str] = Field(None, description="Occasions")
    
    # Dimensions
    length_cm: Optional[str] = Field(None, description="Length (cm)")
    width_cm: Optional[str] = Field(None, description="Width (cm)")
    height_cm: Optional[str] = Field(None, description="Height (cm)")
    weight_g: Optional[str] = Field(None, description="Weight (g)")
    
    # Designs
    earring_design: Optional[str] = Field(None, description="Earring Design")
    necklace_design: Optional[str] = Field(None, description="Necklace Design")
    bracelet_design: Optional[str] = Field(None, description="Bracelet Design")
    ring_design: Optional[str] = Field(None, description="Ring Design")
    
    # Job Info
    job_id: Optional[str] = Field(None, description="Job ID")
    status: Optional[str] = Field(None, description="Status")
    
    
class CSVUploadResponse(BaseModel):
    """Response after CSV upload"""
    success: bool
    message: str
    total_rows: int
    parsed_rows: int
    data: List[ProductCSVRow]
    errors: Optional[List[dict]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Successfully parsed CSV with 10 rows",
                "total_rows": 10,
                "parsed_rows": 10,
                "data": [],
                "errors": None
            }
        }


# NEW CLASSES FOR FULL SHOPIFY PRODUCT CREATION

class ShopifyImageInput(BaseModel):
    """Image input for Shopify product creation"""
    url: str = Field(..., description="Image URL")
    alt_text: Optional[str] = Field(None, description="Alt text for the image")


class ShopifyVariantInput(BaseModel):
    """Product variant input"""
    title: Optional[str] = Field("Default Title", description="Variant title")
    price: str = Field(..., description="Variant price")
    sku: Optional[str] = Field(None, description="SKU")
    inventory_quantity: Optional[int] = Field(0, description="Inventory quantity")
    barcode: Optional[str] = Field(None, description="Barcode")


class ShopifyMetafieldInput(BaseModel):
    """Metafield input for product"""
    namespace: str = Field(..., description="Metafield namespace")
    key: str = Field(..., description="Metafield key") 
    value: str = Field(..., description="Metafield value")
    type: str = Field(..., description="Metafield type")


class FullShopifyProductInput(BaseModel):
    """Complete Shopify product creation input"""
    # Basic product info
    title: str = Field(..., description="Product title")
    description_html: str = Field(..., description="Product description in HTML")
    product_type: str = Field(..., description="Product type")
    vendor: str = Field("MINAKI", description="Vendor name")
    tags: List[str] = Field([], description="Product tags")
    status: str = Field("DRAFT", description="Product status")
    
    # SEO
    seo_title: str = Field(..., description="SEO title")
    seo_description: str = Field(..., description="SEO description")
    
    # Images
    images: List[ShopifyImageInput] = Field([], description="Product images")
    
    # Variants
    variants: List[ShopifyVariantInput] = Field(..., description="Product variants")
    
    # Metafields
    metafields: List[ShopifyMetafieldInput] = Field([], description="Product metafields")


class FullProductCreationRequest(BaseModel):
    """Request to create a full product from CSV data + AI content"""
    csv_row: ProductCSVRow = Field(..., description="CSV row data")
    ai_content: ActionInput = Field(..., description="AI generated content")
    price: str = Field(..., description="Product price")
    sku: Optional[str] = Field(None, description="Product SKU")


class AutoProductCreationRequest(BaseModel):
    """Request to auto-generate AI content and create full product from CSV data only"""
    csv_row: ProductCSVRow = Field(..., description="CSV row data")
    price: str = Field(..., description="Product price")
    sku: Optional[str] = Field(None, description="Product SKU")
    

class AutoProductCreationWithKeywordsRequest(BaseModel):
    """Request for auto product creation with CSV data and keywords"""
    csv_rows: List[ProductCSVRow] = Field(..., description="List of CSV row data")
    prices: List[str] = Field(..., description="Product prices for each row")
    skus: Optional[List[str]] = Field(None, description="Product SKUs for each row")    
    keywords_data: Dict[str, Any] = Field(..., description="Keywords data from Google Keyword Planner CSV")
    

class FullProductCreationResponse(BaseModel):
    """Response after creating full product"""
    success: bool
    message: str
    product_id: Optional[str] = None
    product_handle: Optional[str] = None
    created_metafields: Optional[List[Dict[str, Any]]] = None
    uploaded_images: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


class ProductMetafieldMapping(BaseModel):
    """Mapping configuration for CSV fields to Shopify metafields"""
    
    # Core product attributes
    gender_namespace: str = "addfea"
    gender_key: str = "gender" 
    
    style_namespace: str = "addfea"
    style_key: str = "style"
    
    components_namespace: str = "custom"
    components_key: str = "components"
    
    color_namespace: str = "addfea"
    color_key: str = "color"
    
    # Material and finish
    finish_namespace: str = "custom"
    finish_key: str = "finish"
    
    finding_namespace: str = "addfea"
    finding_key: str = "data3"
    finding_label_namespace: str = "addfea"
    finding_label_key: str = "label3"
    
    # Work/craftsmanship
    work_namespace: str = "addfea"
    work_key: str = "data1"
    work_label_namespace: str = "addfea"
    work_label_key: str = "label1"
    
    # Base metal
    base_metal_namespace: str = "addfea"
    base_metal_key: str = "data2"
    base_metal_label_namespace: str = "addfea"
    base_metal_label_key: str = "label2"
    
    # Additional attributes
    occasions_namespace: str = "addfea"
    occasions_key: str = "occasion"
    
    styling_tip_namespace: str = "addfea"
    styling_tip_key: str = "styling_tip"
    
    # SEO metafields
    seo_title_namespace: str = "global"
    seo_title_key: str = "title_tag"
    
    seo_description_namespace: str = "global"
    seo_description_key: str = "description_tag"
    
    # Meta description excerpt
    meta_description_namespace: str = "meta"
    meta_description_key: str = "description_excerpt"