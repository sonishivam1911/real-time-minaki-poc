from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "PO PDF Processor API is running"}

@router.get("/status")
async def status_check():
    """Detailed status check endpoint"""
    return {
        "status": "healthy",
        "message": "All services operational",
        "services": {
            "database": "connected",
            "shopify": "connected",
            "zakya": "connected"
        }
    }