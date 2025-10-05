from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ProductCreateRequest(BaseModel):
    title: str = Field(..., description="Product title")
    product_type: Optional[str] = Field(None, description="Product type")
    vendor: Optional[str] = Field(None, description="Vendor name")
    tags: Optional[List[str]] = Field([], description="Product tags")
    status: Optional[str] = Field("DRAFT", description="Product status")
    description_html: Optional[str] = Field(None, description="Product description in HTML")

class ProductUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, description="Product title")
    product_type: Optional[str] = Field(None, description="Product type")
    vendor: Optional[str] = Field(None, description="Vendor name")
    tags: Optional[List[str]] = Field(None, description="Product tags")
    status: Optional[str] = Field(None, description="Product status")
    description_html: Optional[str] = Field(None, description="Product description in HTML")

class MetafieldCreateRequest(BaseModel):
    namespace: str = Field(..., description="Metafield namespace")
    key: str = Field(..., description="Metafield key")
    value: str = Field(..., description="Metafield value")
    type: str = Field("single_line_text_field", description="Metafield type")

class MetafieldUpdateRequest(BaseModel):
    value: str = Field(..., description="New metafield value")

class StandardResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class ProductResponse(StandardResponse):
    product: Optional[Dict[str, Any]] = None

class ProductListResponse(StandardResponse):
    products: List[Dict[str, Any]] = []
    pagination: Optional[Dict[str, Any]] = None
    total_count: Optional[int] = None

class NamespaceResponse(StandardResponse):
    namespaces: List[str] = []
    count: Optional[int] = None

class MetafieldResponse(StandardResponse):
    metafields: List[Dict[str, Any]] = []



class NamespaceKeysResponse(BaseModel):
    success: bool
    message: str
    namespace: str
    unique_keys_count: int
    total_metafields: int
    products_scanned: int
    keys: Dict[str, Any]
    analysis_timestamp: str
    error: Optional[str] = None

class AllNamespacesKeysResponse(BaseModel):
    success: bool
    message: str
    summary: Dict[str, Any]
    namespaces: Dict[str, Any]
    error: Optional[str] = None


class MetaobjectLinkRequest(BaseModel):
    metaobject_id: str
    namespace: str
    key: str

class MetaobjectCreateRequest(BaseModel):
    type: str
    fields: List[Dict[str, str]]
    handle: Optional[str] = None

class MetaobjectUpdateRequest(BaseModel):
    fields: List[Dict[str, str]]

class MetaobjectDefinitionRequest(BaseModel):
    type: str
    name: str
    field_definitions: List[Dict[str, Any]]

class MetaobjectResponse(BaseModel):
    success: bool
    message: str
    metaobjects: Optional[List[Dict]] = None
    error: Optional[str] = None

class MetaobjectListResponse(BaseModel):
    success: bool
    message: str
    metaobjects: Optional[Dict[str, List[Dict]]] = None
    pagination: Optional[Dict] = None
    error: Optional[str] = None    