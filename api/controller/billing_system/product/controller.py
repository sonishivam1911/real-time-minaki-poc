"""
Product Controller - API endpoints for product operations
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import Optional

from utils.schema.billing_system.product_schema import (
    ProductCreate,
    ProductResponse,
    ProductListResponse
)
from services.billing_system.product_service import ProductService


router = APIRouter()


@router.post("", response_model=dict, status_code=201)
async def create_product(
    product_data: ProductCreate
):
    """
    Create a new product with variants and components.
    
    **Request Body:**
    - **title**: Product title (required)
    - **variants**: List of variants with metal and diamond components
    - **tags**: Product tags for categorization
    
    **Example:**
    ```json
    {
      "title": "Classic Solitaire Ring",
      "tags": ["ring", "solitaire", "wedding"],
      "variants": [
        {
          "sku": "CR-001-18K",
          "price": 79999.00,
          "net_weight_g": 3.50,
          "purity_k": 18.00,
          "metal_components": [
            {
              "metal_type": "gold",
              "purity_k": 18.00,
              "gross_weight_g": 3.80,
              "net_weight_g": 3.50,
              "making_charge_per_g": 150.00,
              "metal_rate_per_g": 5500.00
            }
          ],
          "diamond_components": [
            {
              "cert_no": "GIA12345",
              "shape": "round",
              "carat": 0.50,
              "cut": "Excellent",
              "clarity": "VS2",
              "color_grade": "F",
              "stone_price_per_carat": 120000.00
            }
          ]
        }
      ]
    }
    ```
    """
    service = ProductService()
    result = service.create_product_with_variants(product_data)
    
    if not result.get('success'):
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Failed to create product')
        )
    
    return {
        "success": True,
        "product_id": result['product_id'],
        "variant_ids": result['variant_ids'],
        "message": "Product created successfully"
    }


@router.get("/{product_id}", response_model=dict)
async def get_product(
    product_id: str = Path(..., description="Product ID")
):
    """
    Get a product by ID with all related data.
    
    **Returns:**
    - Complete product information
    - All variants with their components
    - Pricing breakdowns for each variant
    """
    service = ProductService()
    product = service.get_product_by_id(product_id)
    
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Product {product_id} not found"
        )
    
    return product


@router.get("", response_model=dict)
async def list_products(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page")
):
    """
    List all active products with pagination.
    
    **Query Parameters:**
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 20, max: 100)
    
    **Returns:**
    - List of products with variants and components
    - Pagination metadata
    """
    service = ProductService()
    result = service.list_products(page=page, page_size=page_size)
    return result


@router.delete("/{product_id}", status_code=200)
async def delete_product(
    product_id: str = Path(..., description="Product ID"),
):
    """
    Soft delete a product (sets is_active to false).
    
    **Note:** This does not permanently delete the product, just marks it as inactive.
    """
    # Get product first to verify it exists
    service = ProductService()
    product = service.get_product_by_id(product_id)
    
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Product {product_id} not found"
        )
    
    # Soft delete
    query = f"""
        UPDATE products
        SET is_active = false, updated_at = CURRENT_TIMESTAMP
        WHERE id = '{product_id}'
    """
    service.crud.execute_query(query)
    
    return {
        "success": True,
        "message": f"Product {product_id} deleted successfully"
    }


@router.patch("/{product_id}", response_model=dict)
async def update_product(
    product_id: str = Path(..., description="Product ID"),
    title: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[list] = None
):
    """
    Update product metadata (title, description, tags).
    
    **Note:** To update variants, use the variant endpoints.
    """
    # Verify product exists
    service = ProductService()
    product = service.get_product_by_id(product_id)
    
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Product {product_id} not found"
        )
    
    # Build update query
    updates = []
    if title:
        updates.append(f"title = '{title}'")
    if description:
        updates.append(f"description = '{description}'")
    if tags is not None:
        # Convert list to PostgreSQL array
        tags_str = "{" + ",".join([f'"{tag}"' for tag in tags]) + "}"
        updates.append(f"tags = '{tags_str}'")
    
    if not updates:
        raise HTTPException(
            status_code=400,
            detail="No fields to update"
        )
    
    updates.append("updated_at = CURRENT_TIMESTAMP")
    updates_str = ", ".join(updates)
    
    query = f"""
        UPDATE products
        SET {updates_str}
        WHERE id = '{product_id}'
    """
    service.crud.execute_query(query)
    
    return {
        "success": True,
        "message": "Product updated successfully"
    }