from pydantic import BaseModel, Field
from typing import Optional, List


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