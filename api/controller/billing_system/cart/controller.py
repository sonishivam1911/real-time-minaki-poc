"""
Cart Controller - API endpoints for shopping cart management
"""
from fastapi import APIRouter, HTTPException, Depends, Path
from typing import Optional

from utils.schema.billing_system.checkout_schema import (
    CartCreate,
    CartResponse,
    CartItemCreate,
    CartItemUpdate
)
from services.billing_system.cart_service import CartService


router = APIRouter()


@router.post("", response_model=dict, status_code=201)
async def create_cart(
    cart_data: CartCreate
):
    """
    Create a new shopping cart.
    
    **Example Request:**
    ```json
    {
      "customer_id": "cust_123"
    }
    ```
    
    For guest checkout, omit customer_id and provide session_id.
    """
    service = CartService()
    result = service.create_cart(
        customer_id=cart_data.customer_id,
        session_id=cart_data.session_id
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Failed to create cart')
        )
    
    return result


@router.get("/{cart_id}", response_model=dict)
async def get_cart(
    cart_id: str = Path(..., description="Cart ID"),
):
    """
    Get cart details with all items.
    
    **Returns:**
    - Cart information
    - All items in cart
    - Calculated totals (subtotal, discount, tax, total)
    """
    service = CartService()
    cart = service.get_cart(cart_id)
    
    if not cart:
        raise HTTPException(
            status_code=404,
            detail=f"Cart {cart_id} not found"
        )
    
    return cart


@router.get("/{cart_id}/debug", response_model=dict)
async def debug_cart(
    cart_id: str = Path(..., description="Cart ID"),
):
    """
    Debug endpoint to see raw cart data structure.
    """
    service = CartService()
    cart = service.get_cart(cart_id, include_details=True)
    
    if not cart:
        raise HTTPException(
            status_code=404,
            detail=f"Cart {cart_id} not found"
        )
    
    # Return debug info
    return {
        "cart_id": cart_id,
        "cart_status": cart.get("status"),
        "items_count": len(cart.get("items", [])),
        "cart_totals": {
            "subtotal": cart.get("subtotal"),
            "discount": cart.get("discount_amount"),
            "tax": cart.get("tax_amount"),
            "total": cart.get("total_amount")
        },
        "items_detail": [
            {
                "item_id": item.get("id"),
                "item_type": item.get("item_type"),
                "product_name": item.get("product_name"),
                "name": item.get("name"),  # Frontend compatibility
                "quantity": item.get("quantity"),
                "unit_price": item.get("unit_price"),
                "price": item.get("price"),  # Frontend compatibility
                "line_total": item.get("line_total"),
                "sku": item.get("sku")
            }
            for item in cart.get("items", [])
        ]
    }


@router.post("/{cart_id}/items", response_model=dict, status_code=201)
async def add_item_to_cart(
    cart_id: str = Path(..., description="Cart ID"),
    item_data: CartItemCreate = ...,
):
    """
    Add item to cart - Simplified polymorphic approach for both real jewelry and zakya products.
    
    **Method 1: Direct Polymorphic (Recommended)**
    ```json
    {
      "item_type": "real_jewelry",
      "item_id": "variant_uuid_123", 
      "quantity": 1,
      "serial_no": "SER001",
      "discount_percent": 5
    }
    
    {
      "item_type": "zakya_product",
      "item_id": "1234567890",
      "quantity": 2,
      "discount_percent": 0
    }
    ```
    
    **Method 2: Auto-detect by SKU**
    ```json
    {
      "sku": "MIN001",
      "quantity": 1,
      "discount_percent": 10
    }
    ```
    
    **Method 3: Legacy Support (Auto-converted)**
    ```json
    {
      "variant_id": "variant_uuid_123",
      "quantity": 1,
      "discount_percent": 5
    }
    
    {
      "zakya_item_id": "1234567890", 
      "quantity": 2
    }
    ```
    
    **Features:**
    - Auto-detects product type if not specified
    - Price locked when added to cart (especially important for real jewelry)
    - Supports serial number tracking for real jewelry
    - Handles both quantity and individual piece tracking
    - Legacy API backward compatibility
    """
    service = CartService()
    result = service.add_item_to_cart(cart_id, item_data)
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Failed to add item')
        )
    
    return result


@router.patch("/{cart_id}/items/{item_id}", response_model=dict)
async def update_cart_item(
    cart_id: str = Path(..., description="Cart ID"),
    item_id: str = Path(..., description="Cart item ID"),
    update_data: CartItemUpdate = ...,
):
    """
    Update cart item quantity or discount.
    
    **Example Request:**
    ```json
    {
      "quantity": 2,
      "discount_percent": 10
    }
    ```
    """
    service = CartService()
    result = service.update_cart_item(cart_id, item_id, update_data)
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Failed to update item')
        )
    
    return result


@router.delete("/{cart_id}/items/{item_id}", status_code=200)
async def remove_item_from_cart(
    cart_id: str = Path(..., description="Cart ID"),
    item_id: str = Path(..., description="Cart item ID"),
):
    """
    Remove item from cart.
    """
    service = CartService()
    result = service.remove_item_from_cart(cart_id, item_id)
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Failed to remove item')
        )
    
    return result


@router.delete("/{cart_id}/items", status_code=200)
async def clear_cart(
    cart_id: str = Path(..., description="Cart ID"),
):
    """
    Remove all items from cart.
    """
    service = CartService()
    success = service.clear_cart(cart_id)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to clear cart"
        )
    
    return {
        "success": True,
        "message": "Cart cleared successfully"
    }


@router.post("/{cart_id}/discount", response_model=dict)
async def apply_discount_to_cart(
    cart_id: str = Path(..., description="Cart ID"),
    discount_code: str = ...,
):
    """
    Apply discount code to cart.
    
    **Example Request:**
    ```json
    {
      "discount_code": "FESTIVE10"
    }
    ```
    
    **Validates:**
    - Discount code exists and is active
    - Discount is within validity period
    - Minimum purchase amount met
    """
    service = CartService()
    result = service.apply_discount_to_cart(cart_id, discount_code)
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Failed to apply discount')
        )
    
    return result