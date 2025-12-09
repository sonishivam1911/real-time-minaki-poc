"""
Product Controller - API endpoints for product operations
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Path, Body
from typing import Optional, List

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
        UPDATE billing_system_products
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
        UPDATE billing_system_products
        SET {updates_str}
        WHERE id = '{product_id}'
    """
    service.crud.execute_query(query)
    
    return {
        "success": True,
        "message": "Product updated successfully"
    }


# ============================================================================
# ZAKYA PRODUCT INTEGRATION ENDPOINTS
# ============================================================================

@router.get("/zakya/products", response_model=dict)
async def get_zakya_products(
    # Basic search and pagination
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search_query: Optional[str] = Query(None, description="Search across name, item_name, description"),
    
    # Single value filters
    category_filter: Optional[str] = Query(None, description="Single category exact match"),
    brand_filter: Optional[str] = Query(None, description="Single brand exact match"),
    
    # Multi-value filters (IN clauses)
    category_list: Optional[str] = Query(None, description="Comma-separated list of categories"),
    brand_list: Optional[str] = Query(None, description="Comma-separated list of brands"),
    
    # Price range filters
    price_min: Optional[float] = Query(None, ge=0, description="Minimum price (rate field)"),
    price_max: Optional[float] = Query(None, ge=0, description="Maximum price (rate field)"),
    
    # Stock filters
    stock_min: Optional[float] = Query(None, ge=0, description="Minimum stock (stock_on_hand field)"),
    
    # Date range filters
    created_after: Optional[str] = Query(None, description="Created after date (YYYY-MM-DD)"),
    created_before: Optional[str] = Query(None, description="Created before date (YYYY-MM-DD)"),
    updated_after: Optional[str] = Query(None, description="Updated after date (YYYY-MM-DD)"),
    updated_before: Optional[str] = Query(None, description="Updated before date (YYYY-MM-DD)"),
    
    # Shopify image enrichment
    with_images: bool = Query(True, description="Whether to fetch images from Shopify by SKU")
):
    """
    **🎯 Fetch Zakya Products with Advanced Filtering**
    
    Comprehensive endpoint to fetch products from `zakya_products` table with optional 
    Shopify image enrichment and advanced filtering capabilities.
    
    **Features:**
    - ✅ **Text Search**: Search across name, item_name, description (ILIKE)
    - ✅ **Exact Filters**: Single category/brand exact matching
    - ✅ **List Filters**: Multiple categories/brands (IN clauses)
    - ✅ **Range Filters**: Price and stock range filtering
    - ✅ **Date Filters**: Created/updated date range filtering
    - ✅ **Shopify Integration**: Automatic image fetching by SKU
    - ✅ **Pagination**: Standard page-based pagination
    - ✅ **SQL Safety**: All queries use parameterization
    
    **Query Examples:**
    ```bash
    # Basic search with images
    GET /products/zakya/products?search_query=gold ring&with_images=true
    
    # Category filtering with price range
    GET /products/zakya/products?category_list=Rings,Earrings&price_min=10000&price_max=50000
    
    # Brand filtering with stock requirements
    GET /products/zakya/products?brand_list=Minaki,Premium&stock_min=1
    
    # Date range filtering
    GET /products/zakya/products?created_after=2024-01-01&updated_after=2024-06-01
    
    # Complex filtering
    GET /products/zakya/products?search_query=wedding&category_filter=Rings&price_min=25000&stock_min=1&with_images=true
    ```
    
    **Returns:**
    ```json
    {
        "success": true,
        "total": 150,
        "products": [
            {
                "item_id": "ZAK001",
                "name": "Gold Ring",
                "sku": "GR001",
                "rate": 45000.0,
                "brand": "Minaki",
                "category_name": "Rings",
                "stock_on_hand": 5.0,
                "shopify_image": {
                    "url": "https://cdn.shopify.com/image.jpg",
                    "alt_text": "Gold Ring",
                    "width": 800,
                    "height": 600
                }
            }
        ],
        "page": 1,
        "page_size": 20,
        "total_pages": 8,
        "filters": { ... },
        "sql_debug": { ... }
    }
    ```
    """
    try:
        # Convert comma-separated strings to lists
        category_list_parsed = None
        if category_list:
            category_list_parsed = [cat.strip() for cat in category_list.split(",") if cat.strip()]
        
        brand_list_parsed = None
        if brand_list:
            brand_list_parsed = [brand.strip() for brand in brand_list.split(",") if brand.strip()]
        
        service = ProductService()
        result = service.get_zakya_products(
            page=page,
            page_size=page_size,
            search_query=search_query,
            category_filter=category_filter,
            brand_filter=brand_filter,
            category_list=category_list_parsed,
            brand_list=brand_list_parsed,
            price_min=price_min,
            price_max=price_max,
            stock_min=stock_min,
            created_after=created_after,
            created_before=created_before,
            updated_after=updated_after,
            updated_before=updated_before,
            with_images=with_images
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching zakya products: {str(e)}"
        )


@router.get("/zakya/products/{sku}", response_model=dict)
async def get_zakya_product_by_sku(
    sku: str = Path(..., description="Product SKU"),
    with_image: bool = Query(True, description="Whether to fetch Shopify image")
):
    """
    **🔍 Get Single Zakya Product by SKU**
    
    Fetch a specific product from `zakya_products` table by SKU with optional Shopify image.
    
    **Path Parameters:**
    - **sku**: Product SKU to search for
    
    **Query Parameters:**
    - **with_image**: Include Shopify image data (default: true)
    
    **Returns:**
    - Single product with all zakya_products fields
    - Optional Shopify image data
    """
    try:
        service = ProductService()
        result = service.get_zakya_product_by_sku(sku=sku, with_image=with_image)
        
        if not result.get('success'):
            raise HTTPException(
                status_code=404,
                detail=result.get('error', 'Product not found')
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching product by SKU {sku}: {str(e)}"
        )


@router.post("/zakya/products/search-by-criteria", response_model=dict)
async def search_zakya_products_by_criteria(
    criteria: dict = Body(..., description="Dynamic search criteria")
):
    """
    **🎯 Dynamic Criteria-Based Search**
    
    Advanced search using dynamic criteria dictionary. Demonstrates the power 
    of the WhereClauseBuilder for complex filtering scenarios.
    
    **Request Body Example:**
    ```json
    {
        "text_search": "gold ring",
        "categories": ["Rings", "Necklaces"],
        "brands": ["Minaki", "Premium"],
        "price_min": 10000,
        "price_max": 50000,
        "stock_min": 1,
        "created_after": "2024-01-01",
        "has_sku": true,
        "has_image": true,
        "custom_filters": [
            ["cf_gender_unformatted", "Women"],
            ["cf_collection", "Wedding"]
        ]
    }
    ```
    
    **Supported Criteria:**
    - **text_search**: Search across name, item_name, description
    - **categories**: List of categories (IN clause)
    - **brands**: List of brands (IN clause)  
    - **price_min/price_max**: Price range filtering
    - **stock_min**: Minimum stock filtering
    - **created_after**: Date filtering
    - **has_sku**: Require SKU field
    - **has_image**: Require image field
    - **custom_filters**: Array of [field, value] pairs for exact matches
    
    **Returns:**
    - Filtered products (limited to 50 results)
    - Applied criteria for reference
    - SQL debug information
    """
    try:
        service = ProductService()
        result = service.search_zakya_products_by_criteria(criteria)
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error in criteria search: {str(e)}"
        )


@router.get("/zakya/where-clause-example", response_model=dict)
async def get_where_clause_builder_example():
    """
    **📚 WhereClauseBuilder Usage Example**
    
    Demonstrates various usage patterns of the WhereClauseBuilder class.
    Useful for developers and testing purposes.
    
    **Returns:**
    - Example WHERE clause generated by the builder
    - Parameters used in the query
    - Explanation of each filter type demonstrated
    """
    try:
        service = ProductService()
        result = service.get_zakya_products_advanced_example()
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating example: {str(e)}"
        )