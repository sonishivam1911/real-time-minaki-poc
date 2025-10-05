from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse

from core.config import settings
from services.salesorder_service import process_single_pdf


router = APIRouter()


@router.post("/")
async def upload_and_process_pdf(
    pdf_file: UploadFile = File(..., description="PDF file containing Purchase Order"),
    vendor: str = Form(..., description="Vendor type: 'AZA' or 'PPUS'")
):
    """
    Process a PDF Purchase Order file and create a sales order.
    
    Args:
        pdf_file: PDF file containing the Purchase Order
        vendor: Vendor type - either 'AZA' or 'PPUS'
    
    Returns:
        JSON response with sales order ID and processing status
    """
    
    # Validate file type
    if pdf_file.content_type != "application/pdf":
        return JSONResponse(
            status_code=400, 
            content={
                "success": False,
                "message": "File must be a PDF",
                "sales_order_id": None
            }
        )
    
    # Validate vendor
    if vendor.upper() not in ["AZA", "PPUS"]:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Vendor must be either 'AZA' or 'PPUS'",
                "sales_order_id": None
            }
        )
    
    try:
        # Read PDF content
        pdf_content = await pdf_file.read()
        
        if len(pdf_content) == 0:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "PDF file is empty",
                    "sales_order_id": None
                }
            )
        
        print(f"Processing PDF file: {pdf_file.filename} for vendor: {vendor}")
        
        # Process the PDF using the service
        result = process_single_pdf(pdf_content, vendor, settings)
        
        # Return appropriate response based on result
        if result["success"]:
            return JSONResponse(
                status_code=200,
                content=result
            )
        else:
            return JSONResponse(
                status_code=200,  # As per your requirement, return 200 even for business logic errors
                content=result
            )
            
    except Exception as e:
        print(f"Unexpected error processing PDF {pdf_file.filename}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Internal server error: {str(e)}",
                "sales_order_id": None
            }
        )
    



