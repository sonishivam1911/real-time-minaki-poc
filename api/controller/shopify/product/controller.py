from fastapi import APIRouter, Query, Path, HTTPException, Depends
from typing import Optional

from services.shopify.product import ShopifyProductService
from utils.schema.shopify_schema import (
    ProductListResponse, 
    ProductResponse, 
    ProductCreateRequest,
    ProductUpdateRequest,
    StandardResponse
)
from controller.shopify.dependencies import get_shopify_product_service

router = APIRouter()

# Dependency to get Product Service
@router.get("/", response_model=ProductListResponse)
async def get_all_products(
    connector: ShopifyProductService = Depends(get_shopify_product_service)
):
    """
    Get ALL products from your Shopify store.
    Warning: This may take a while for large stores!
    """
    try:
        all_products = []
        batch_count = 0
        
        print("Starting to fetch ALL products...")
        
        for product_batch in connector.get_products_batch_for_db(batch_size=50):
            all_products.extend(product_batch)
            batch_count += 1
            print(f"Fetched batch {batch_count} - Total products so far: {len(all_products)}")
        
        print(f"Completed! Total products fetched: {len(all_products)}")
        
        return ProductListResponse(
            success=True,
            message=f"Retrieved ALL {len(all_products)} products from your store",
            products=all_products,
            pagination={
                "has_next_page": False,
                "has_previous_page": False,
                "end_cursor": None,
                "start_cursor": None
            },
            total_count=len(all_products)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching all products: {str(e)}"
        )
        
@router.get("/all-with-metaobjects", response_model=ProductListResponse)
async def get_all_products_with_metaobjects(
    max_products: Optional[int] = Query(None, description="Maximum number of products to fetch (None = all)"),
    connector: ShopifyProductService = Depends(get_shopify_product_service)
):
    """
    Get ALL products from your Shopify store WITH their metaobjects expanded.
    Uses the existing get_all_products_with_metaobjects service method.
    """
    try:
        all_products = []
        batch_count = 0
        
        print(f"Starting to fetch ALL products with metaobjects (max: {max_products or 'unlimited'})...")
        
        for product_batch in connector.get_all_products_with_metaobjects(max_products=max_products):
            all_products.extend(product_batch)
            batch_count += 1
            print(f"Processed batch {batch_count} - Total products: {len(all_products)}")
        
        # Count total metaobjects
        total_metaobjects = 0
        for product in all_products:
            metaobjects_edges = product.get('metaobjects', {}).get('edges', [])
            total_metaobjects += len(metaobjects_edges)
        
        print(f"🎉 COMPLETED! Fetched {len(all_products)} products with {total_metaobjects} metaobject references")
        
        return ProductListResponse(
            success=True,
            message=f"Retrieved {len(all_products)} products with metaobjects ({total_metaobjects} metaobject references)",
            products=all_products,
            pagination={
                "has_next_page": False,
                "has_previous_page": False,
                "end_cursor": None,
                "start_cursor": None
            },
            total_count=len(all_products)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching all products with metaobjects: {str(e)}"
        )

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str = Path(..., description="Shopify product ID"),
    include_all_metafields: bool = Query(False, description="Include all metafields (may be slow)"),
    connector: ShopifyProductService = Depends(get_shopify_product_service)
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
    connector: ShopifyProductService = Depends(get_shopify_product_service)
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
    connector: ShopifyProductService = Depends(get_shopify_product_service)
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
    connector: ShopifyProductService = Depends(get_shopify_product_service)
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

