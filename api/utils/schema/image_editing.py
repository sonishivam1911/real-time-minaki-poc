from pydantic import BaseModel

class NDJSONImportResponse(BaseModel):
    """Response model for NDJSON import"""
    success: bool
    message: str
    total_records: int
    success_count: int
    error_count: int
    status_code: int = 200
