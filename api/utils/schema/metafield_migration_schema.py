from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class MetafieldMigrationResponse(BaseModel):
    """Response model for starting migration job"""
    success: bool
    message: str
    job_id: Optional[str] = None
    validation_stats: Optional[Dict[str, Any]] = None
    preview_results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class MetafieldMigrationStatusResponse(BaseModel):
    """Response model for job status"""
    success: bool
    job_id: str
    status: str  # pending, processing, completed, failed
    total_products: Any  # int or "calculating..."
    processed: int
    updated: int
    skipped: int
    total_metafields_created: int = 0
    errors: List[str]
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration_seconds: Optional[float] = None
    message: Optional[str] = None


class MappingRuleModel(BaseModel):
    """Single mapping rule model"""
    input_namespace: str
    input_key: str
    input_value: str
    input_type: str
    output_namespace: str
    output_key: str
    output_value: str
    output_type: str


class MetafieldMigrationPreviewResponse(BaseModel):
    """Preview response with statistics"""
    success: bool
    message: str
    total_products_checked: int
    products_with_matches: int
    total_matches_found: int
    matches_by_rule: Dict[str, int]
    sample_matches: List[Dict[str, Any]]
    estimated_total_metafields: int = 0


class CSVValidationResponse(BaseModel):
    """Response for CSV validation"""
    success: bool
    message: str
    validation_stats: Dict[str, Any]
    error: Optional[str] = None