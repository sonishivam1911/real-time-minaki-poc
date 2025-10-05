from fastapi import APIRouter, Query, Path, HTTPException, Depends
from typing import Optional

from services.shopify_service import ShopifyGraphQLConnector
from utils.schema.shopify_schema import (
    ProductListResponse, 
    ProductResponse, 
    ProductCreateRequest,
    ProductUpdateRequest,
    StandardResponse
)
from controller.shopify.dependencies import get_shopify_connector

router = APIRouter()

# Dependency to get Product Service

@router.get("/", response_model=ProductListResponse)
async def get_products(
    limit: int = Query(20, ge=1, le=250, description="Number of products to fetch"),
    after: Optional[str] = Query(None, description="Cursor for pagination"),
    search: Optional[str] = Query(None, description="Search query (Shopify format)"),
    connector: ShopifyGraphQLConnector = Depends(get_shopify_connector)
):
    """
    Get list of products with pagination.
    
    - **limit**: Number of products per page (1-250)
    - **after**: Pagination cursor from previous response
    - **search**: Search filter (e.g., 'title:shirt', 'tag:summer')
    """
    try:
        result = connector.get_products(
            first=limit,
            after=after,
            query_filter=search
        )
        
        if 'data' not in result or 'products' not in result['data']:
            return ProductListResponse(
                success=False,
                message="No products data found",
                error="Invalid response from Shopify"
            )
        
        products_data = result['data']['products']
        products = [edge['node'] for edge in products_data.get('edges', [])]
        
        pagination_info = products_data.get('pageInfo', {})
        
        return ProductListResponse(
            success=True,
            message=f"Retrieved {len(products)} products",
            products=products,
            pagination={
                "has_next_page": pagination_info.get('hasNextPage', False),
                "has_previous_page": pagination_info.get('hasPreviousPage', False),
                "end_cursor": pagination_info.get('endCursor'),
                "start_cursor": pagination_info.get('startCursor')
            },
            total_count=len(products)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching products: {str(e)}"
        )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str = Path(..., description="Shopify product ID"),
    include_all_metafields: bool = Query(False, description="Include all metafields (may be slow)"),
    connector: ShopifyGraphQLConnector = Depends(get_shopify_connector)
):
    """
    Get a single product by ID.
    
    - **product_id**: Shopify product ID (with or without gid prefix)
    - **include_all_metafields**: If True, fetches ALL metafields using pagination
    """
    try:
        if include_all_metafields:
            result = connector.get_complete_product_with_metafields(product_id)
        else:
            print(f"Fetching product {product_id} without all metafields")
            result = connector.get_product_by_id(product_id)
        
        if not result.get('data', {}).get('product'):
            return ProductResponse(
                success=False,
                message=f"Product {product_id} not found",
                error="Product does not exist"
            )
        
        product = result['data']['product']
        
        return ProductResponse(
            success=True,
            message=f"Retrieved product {product_id}",
            product=product
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching product {product_id}: {str(e)}"
        )


@router.post("/", response_model=ProductResponse)
async def create_product(
    product_data: ProductCreateRequest,
    connector: ShopifyGraphQLConnector = Depends(get_shopify_connector)
):
    """
    Create a new product.
    
    - **title**: Product title (required)
    - **product_type**: Product type category
    - **vendor**: Vendor/brand name
    - **tags**: List of product tags
    - **status**: Product status (DRAFT, ACTIVE, ARCHIVED)
    - **description_html**: Product description in HTML format
    """
    try:
        # Convert Pydantic model to Shopify format
        product_input = {
            "title": product_data.title,
            "status": product_data.status.upper()
        }
        
        if product_data.product_type:
            product_input["productType"] = product_data.product_type
        if product_data.vendor:
            product_input["vendor"] = product_data.vendor
        if product_data.tags:
            product_input["tags"] = product_data.tags
        if product_data.description_html:
            product_input["descriptionHtml"] = product_data.description_html
        
        result = connector.create_product(product_input)
        
        if 'errors' in result or result.get('data', {}).get('productCreate', {}).get('userErrors'):
            errors = result.get('errors', []) + result.get('data', {}).get('productCreate', {}).get('userErrors', [])
            return ProductResponse(
                success=False,
                message="Failed to create product",
                error=str(errors)
            )
        
        created_product = result['data']['productCreate']['product']
        
        return ProductResponse(
            success=True,
            message=f"Product created successfully with ID: {created_product['id']}",
            product=created_product
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating product: {str(e)}"
        )


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str = Path(..., description="Shopify product ID"),
    product_data: ProductUpdateRequest = None,
    connector: ShopifyGraphQLConnector = Depends(get_shopify_connector)
):
    """
    Update an existing product.
    
    - **product_id**: Shopify product ID
    - Only provided fields will be updated
    """
    try:
        # Build update input from provided fields only
        product_input = {}
        
        if product_data.title is not None:
            product_input["title"] = product_data.title
        if product_data.product_type is not None:
            product_input["productType"] = product_data.product_type
        if product_data.vendor is not None:
            product_input["vendor"] = product_data.vendor
        if product_data.tags is not None:
            product_input["tags"] = product_data.tags
        if product_data.status is not None:
            product_input["status"] = product_data.status.upper()
        if product_data.description_html is not None:
            product_input["descriptionHtml"] = product_data.description_html
        
        if not product_input:
            return ProductResponse(
                success=False,
                message="No fields provided for update",
                error="At least one field must be provided"
            )
        
        result = connector.update_product(product_id, product_input)
        
        if 'errors' in result or result.get('data', {}).get('productUpdate', {}).get('userErrors'):
            errors = result.get('errors', []) + result.get('data', {}).get('productUpdate', {}).get('userErrors', [])
            return ProductResponse(
                success=False,
                message="Failed to update product",
                error=str(errors)
            )
        
        updated_product = result['data']['productUpdate']['product']
        
        return ProductResponse(
            success=True,
            message=f"Product {product_id} updated successfully",
            product=updated_product
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating product {product_id}: {str(e)}"
        )


@router.delete("/{product_id}", response_model=StandardResponse)
async def delete_product(
    product_id: str = Path(..., description="Shopify product ID"),
    connector: ShopifyGraphQLConnector = Depends(get_shopify_connector)
):
    """
    Delete a product.
    
    - **product_id**: Shopify product ID to delete
    """
    try:
        result = connector.delete_product(product_id)
        
        if 'errors' in result or result.get('data', {}).get('productDelete', {}).get('userErrors'):
            errors = result.get('errors', []) + result.get('data', {}).get('productDelete', {}).get('userErrors', [])
            return StandardResponse(
                success=False,
                message="Failed to delete product",
                error=str(errors)
            )
        
        deleted_id = result['data']['productDelete']['deletedProductId']
        
        return StandardResponse(
            success=True,
            message=f"Product {deleted_id} deleted successfully"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting product {product_id}: {str(e)}"
        )

