import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import JSONResponse

from core.config import settings
from services.salesorder_service import process_single_pdf
from schema.taj_invoices import InvoiceResponse
from services.invoices_service import InvoiceService

app = FastAPI(title="PO PDF Processor API", version="1.0.0")

@app.post("/process-pdf/")
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

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "PO PDF Processor API is running"}

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Welcome to PO PDF Processor API",
        "version": "1.0.0",
        "endpoints": {
            "process_pdf": "/process-pdf/",
            "health": "/health"
        }
    }



async def get_zakya_connection():
    """Get zakya connection object from settings."""
    return settings.get_zakya_connection()

@app.post("/generate-taj-invoices", response_model=InvoiceResponse)
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


if __name__ == "__main__":
    
    uvicorn.run(
        "main:app",  # Use import string instead of app object
        host="0.0.0.0", 
        port=8000, 
        reload=True
    )