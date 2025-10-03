from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException

from services.invoices_service import InvoiceService
from schema.taj_invoices import InvoiceResponse
from controller.zakya.dependencies import get_zakya_connection


router = APIRouter()

@router.post("/generate-taj-invoices", response_model=InvoiceResponse)
async def generate_invoices(
    file: UploadFile = File(...),
    date: str = Form(...),
    zakya_connection: dict = Depends(get_zakya_connection)
):
    """
    Generate invoices from uploaded Excel file.
    
    - **file**: Excel file upload (.xlsx)
    - **date**: Invoice date in YYYY-MM-DD format
    """
    
    # Validate file type
    if not file.filename.endswith(('.xlsx', '.xls')):
        return InvoiceResponse(
            invoices=[],
            status_code=400,
            message="Invalid file format. Please upload an Excel file (.xlsx or .xls)",
            missing_product_skus=[],
            total_invoices_created=0,
            total_amount=0.0
        )
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Process invoice using service
        response = await InvoiceService.process_invoice_file(
            file_content, date, zakya_connection
        )
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions (like validation errors)
        raise
    except Exception as e:
        return InvoiceResponse(
            invoices=[],
            status_code=500,
            message=f"Unexpected error: {str(e)}",
            missing_product_skus=[],
            total_invoices_created=0,
            total_amount=0.0
        )
    
