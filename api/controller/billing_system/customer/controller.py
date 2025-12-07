"""
Customer Controller - API endpoints for customer management
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
    customer_code: Optional[str] = Query(None, description="Search by code")
):
    """
    Search customers by various criteria.
    
    **Usage:**
    ```
    GET /api/customers/search?phone=9876543210
    GET /api/customers/search?email=john@example.com
    GET /api/customers/search?name=John
    GET /api/customers/search?customer_code=CUST-0001
    ```
    
    Returns up to 50 matching customers.
    """
    service = CustomerService()
    customers = service.search_customers(
        phone=phone,
        email=email,
        name=name,
        customer_code=customer_code
    )
    
    return customers


@router.get("/{customer_id}", response_model=dict)
async def get_customer(
    customer_id: str = Path(..., description="Customer ID"),

):
    """
    Get customer by ID with purchase history.
    """
    service = CustomerService()
    customer = service.get_customer_by_id(customer_id)
    
    if not customer:
        raise HTTPException(
            status_code=404,
            detail=f"Customer {customer_id} not found"
        )
    
    # Get purchase history
    purchase_history = service.get_customer_purchase_history(customer_id)
    customer['purchase_history'] = purchase_history
    
    return customer


@router.patch("/{customer_id}", response_model=dict)
async def update_customer(
    customer_id: str = Path(..., description="Customer ID"),
    update_data: CustomerUpdate = ...,

):
    """
    Update customer information.
    """
    service = CustomerService()
    result = service.update_customer(customer_id, update_data)
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Failed to update customer')
        )
    
    return result


@router.get("/{customer_id}/purchases", response_model=list)
async def get_customer_purchases(
    customer_id: str = Path(..., description="Customer ID"),
):
    """
    Get customer's purchase history.
    """
    service = CustomerService()
    purchases = service.get_customer_purchase_history(customer_id)
    return purchases


@router.post("/{customer_id}/loyalty-points", response_model=dict)
async def update_loyalty_points(
    customer_id: str = Path(..., description="Customer ID"),
    points: int = Query(..., description="Points to add/subtract"),
):
    """
    Update customer loyalty points.
    
    **Usage:**
    ```
    POST /api/customers/{id}/loyalty-points?points=100   # Add 100 points
    POST /api/customers/{id}/loyalty-points?points=-50   # Subtract 50 points
    ```
    """
    service = CustomerService()
    success = service.update_loyalty_points(customer_id, points)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to update loyalty points"
        )
    
    return {
        "success": True,
        "message": f"Loyalty points updated by {points}"
    }