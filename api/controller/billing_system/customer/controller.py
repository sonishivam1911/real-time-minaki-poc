"""
Customer Controller - API endpoints for customer management using customer_master table
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import Optional

from utils.schema.billing_system.checkout_schema import (
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    CustomerSearchParams
)
from services.billing_system.customer_service import CustomerService


router = APIRouter()


@router.get("", response_model=list)
async def list_customers(
    limit: int = Query(50, description="Number of customers to return", le=100),
    offset: int = Query(0, description="Number of customers to skip", ge=0),
    status: str = Query("Active", description="Customer status filter")
):
    """
    Get list of customers from customer_master table.
    
    **Usage:**
    ```
    GET /api/customers                    # Get first 50 active customers
    GET /api/customers?limit=20&offset=0  # Get first 20 customers
    GET /api/customers?status=Inactive    # Get inactive customers
    ```
    
    Returns customers ordered by creation date (newest first).
    """
    service = CustomerService()
    
    try:
        customers = service.get_all_customers()
        return customers
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch customers: {str(e)}"
        )


@router.post("", response_model=dict, status_code=201)
async def create_customer(
    customer_data: CustomerCreate
):
    """
    Create a new customer.
    
    **Example Request:**
    ```json
    {
      "full_name": "John Doe",
      "email": "john@example.com",
      "phone": "+91-9876543210",
      "address": "123 Main St",
      "city": "Mumbai",
      "state": "Maharashtra",
      "postal_code": "400001",
      "customer_type": "regular"
    }
    ```
    
    **Customer Types:**
    - `regular` - Regular customer
    - `vip` - VIP customer with special benefits
    - `wholesale` - Wholesale/bulk buyer
    """
    service = CustomerService()
    result = service.create_customer(customer_data)
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Failed to create customer')
        )
    
    return result


@router.get("/search", response_model=list)
async def search_customers(
    phone: Optional[str] = Query(None, description="Search by phone"),
    email: Optional[str] = Query(None, description="Search by email"),
    name: Optional[str] = Query(None, description="Search by name"),
    customer_number: Optional[str] = Query(None, description="Search by customer number"),
    contact_id: Optional[int] = Query(None, description="Search by contact ID"),
    gstin: Optional[str] = Query(None, description="Search by GST number")
):
    """
    Search customers by various criteria in customer_master table.
    
    **Usage:**
    ```
    GET /api/customers/search?phone=9876543210
    GET /api/customers/search?email=john@example.com
    GET /api/customers/search?name=John
    GET /api/customers/search?customer_number=CUST-0001
    GET /api/customers/search?contact_id=123
    GET /api/customers/search?gstin=27ABCDE1234F1Z5
    ```
    
    Returns up to 50 matching customers.
    """
    service = CustomerService()
    customers = service.search_customers(
        phone=phone,
        email=email,
        name=name,
        customer_number=customer_number,
        contact_id=contact_id,
        gstin=gstin
    )
    
    return customers


@router.get("/by-contact-id/{contact_id}", response_model=dict)
async def get_customer_by_contact_id(
    contact_id: int = Path(..., description="Contact ID from customer_master"),
):
    """
    Get customer by Contact ID with purchase history.
    """
    service = CustomerService()
    customer = service.get_customer_by_id(str(contact_id))
    
    if not customer:
        raise HTTPException(
            status_code=404,
            detail=f"Customer with Contact ID {contact_id} not found"
        )
    
    # Get purchase history
    purchase_history = service.get_customer_purchase_history(contact_id)
    customer['purchase_history'] = purchase_history
    
    return customer


@router.get("/by-number/{customer_number}", response_model=dict)
async def get_customer_by_number(
    customer_number: str = Path(..., description="Customer Number"),
):
    """
    Get customer by Customer Number with purchase history.
    """
    service = CustomerService()
    customer = service.get_customer_by_number(customer_number)
    
    if not customer:
        raise HTTPException(
            status_code=404,
            detail=f"Customer {customer_number} not found"
        )
    
    # Get purchase history using Contact ID
    contact_id = customer.get('Contact ID')
    if contact_id:
        purchase_history = service.get_customer_purchase_history(contact_id)
        customer['purchase_history'] = purchase_history
    
    return customer


@router.patch("/contact-id/{contact_id}", response_model=dict)
async def update_customer(
    contact_id: int = Path(..., description="Contact ID"),
    update_data: CustomerUpdate = ...,
):
    """
    Update customer information using Contact ID.
    """
    service = CustomerService()
    result = service.update_customer(contact_id, update_data)
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Failed to update customer')
        )
    
    return result


@router.get("/contact-id/{contact_id}/purchases", response_model=list)
async def get_customer_purchases(
    contact_id: int = Path(..., description="Contact ID"),
):
    """
    Get customer's purchase history using Contact ID.
    """
    service = CustomerService()
    purchases = service.get_customer_purchase_history(contact_id)
    return purchases


@router.post("/contact-id/{contact_id}/gst", response_model=dict)
async def update_customer_gst(
    contact_id: int = Path(..., description="Contact ID"),
    gstin: str = Query(..., description="GST Identification Number"),
    gst_treatment: str = Query("Regular", description="GST Treatment type"),
):
    """
    Update customer GST information.
    
    **Usage:**
    ```
    POST /api/customers/contact-id/123/gst?gstin=27ABCDE1234F1Z5&gst_treatment=Regular
    ```
    """
    service = CustomerService()
    success = service.update_customer_gst_info(contact_id, gstin, gst_treatment)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to update GST information"
        )
    
    return {
        "success": True,
        "message": "GST information updated successfully"
    }


@router.post("/contact-id/{contact_id}/status", response_model=dict)
async def update_customer_status(
    contact_id: int = Path(..., description="Contact ID"),
    status: str = Query(..., description="Customer status (Active/Inactive)"),
):
    """
    Update customer status.
    
    **Usage:**
    ```
    POST /api/customers/contact-id/123/status?status=Active
    POST /api/customers/contact-id/123/status?status=Inactive
    ```
    """
    service = CustomerService()
    success = service.update_customer_status(contact_id, status)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to update customer status"
        )
    
    return {
        "success": True,
        "message": f"Customer status updated to {status}"
    }


@router.get("/location", response_model=list)
async def get_customers_by_location(
    state: Optional[str] = Query(None, description="Filter by state"),
    city: Optional[str] = Query(None, description="Filter by city"),
):
    """
    Get customers by location (state/city).
    
    **Usage:**
    ```
    GET /api/customers/location?state=Maharashtra
    GET /api/customers/location?city=Mumbai
    GET /api/customers/location?state=Maharashtra&city=Mumbai
    ```
    """
    service = CustomerService()
    customers = service.get_customers_by_location(state=state, city=city)
    return customers