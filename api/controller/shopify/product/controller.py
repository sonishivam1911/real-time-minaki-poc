import asyncio
import time
import random
from concurrent.futures import ThreadPoolExecutor


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
        
@router.get("/all-with-metafields", response_model=ProductListResponse)
async def get_all_products_with_metafields(
    max_products: Optional[int] = Query(None, description="Maximum number of products to fetch (None = all)"),
    concurrent_requests: int = Query(5, ge=1, le=10, description="Number of concurrent metafield requests (reduced for rate limiting)"),
    delay_between_requests: float = Query(0.5, ge=0.1, le=2.0, description="Delay between requests in seconds"),
    connector: ShopifyProductService = Depends(get_shopify_product_service)
):
    """
    Get ALL products from your Shopify store WITH ALL their metafields expanded.
    Uses async processing with rate limiting to avoid throttling.
    """
    try:
        all_products = []
        batch_count = 0
        
        print(f"Starting to fetch ALL products with metafields (max: {max_products or 'unlimited'}, concurrent: {concurrent_requests}, delay: {delay_between_requests}s)...")
        
        # Create thread pool for blocking I/O operations (reduced workers)
        executor = ThreadPoolExecutor(max_workers=concurrent_requests)
        
        async def fetch_metafields_for_product_with_retry(product, semaphore):
            """Async wrapper with retry logic and rate limiting"""
            async with semaphore:  # Limit concurrent requests
                loop = asyncio.get_event_loop()
                product_id = product['id']
                product_title = product.get('title', 'Unknown')
                
                max_retries = 3
                base_delay = delay_between_requests
                
                for attempt in range(max_retries):
                    try:
                        # Add jitter to prevent thundering herd
                        jitter = random.uniform(0, 0.3)
                        await asyncio.sleep(base_delay + jitter)
                        
                        # Run the blocking operation in thread pool
                        complete_metafields_data = await loop.run_in_executor(
                            executor, 
                            connector.get_complete_product_with_metafields, 
                            product_id
                        )
                        
                        # Replace with complete metafields
                        if complete_metafields_data.get('data', {}).get('product'):
                            complete_product = complete_metafields_data['data']['product']
                            product['metafields'] = complete_product.get('metafields', {'edges': []})
                            metafields_count = len(product['metafields'].get('edges', []))
                            print(f"  ✓ Fetched {metafields_count} metafields for: {product_title}")
                        else:
                            # Keep original metafields if complete fetch fails
                            product['metafields'] = product.get('metafields', {'edges': []})
                            print(f"  ⚠ Using original metafields for: {product_title}")
                        
                        return product
                        
                    except Exception as e:
                        error_msg = str(e)
                        
                        # Check if it's a throttling error
                        if 'THROTTLED' in error_msg or 'Throttled' in error_msg:
                            if attempt < max_retries - 1:
                                # Exponential backoff with jitter
                                retry_delay = (2 ** attempt) * base_delay + random.uniform(0, 1)
                                print(f"  ⏳ Rate limited for {product_title}, retrying in {retry_delay:.1f}s (attempt {attempt + 1}/{max_retries})")
                                await asyncio.sleep(retry_delay)
                                continue
                            else:
                                print(f"  ✗ Max retries exceeded for {product_title} due to rate limiting")
                        else:
                            print(f"  ✗ Error fetching metafields for {product_title}: {error_msg}")
                        
                        # Return product with original metafields on final failure
                        product['metafields'] = product.get('metafields', {'edges': []})
                        return product
                
                # Should never reach here, but just in case
                product['metafields'] = product.get('metafields', {'edges': []})
                return product
        
        processed_count = 0
        
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(concurrent_requests)
        
        for product_batch in connector.get_products_batch_for_db(batch_size=100):  # Smaller batches to reduce load
            batch_count += 1
            print(f"Processing batch {batch_count} with {len(product_batch)} products...")
            
            # Process metafields concurrently for this batch with rate limiting
            tasks = [
                fetch_metafields_for_product_with_retry(product, semaphore) 
                for product in product_batch
            ]
            
            # Execute all tasks concurrently with longer timeout
            try:
                enriched_products = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=300.0  # 5 minute timeout per batch
                )
            except asyncio.TimeoutError:
                print(f"Batch {batch_count} timed out, using original products")
                enriched_products = product_batch
            
            # Filter out exceptions and add successful results
            successful_products = []
            for i, result in enumerate(enriched_products):
                if isinstance(result, Exception):
                    print(f"Exception for product {i}: {result}")
                    product_batch[i]['metafields'] = product_batch[i].get('metafields', {'edges': []})
                    successful_products.append(product_batch[i])
                else:
                    successful_products.append(result)
            
            all_products.extend(successful_products)
            processed_count += len(successful_products)
            
            print(f"Batch {batch_count} completed - Total processed: {processed_count}")
            
            # FIXED: Proper None check for max_products
            # Add delay between batches to be extra safe
            should_continue = True
            if max_products is not None:
                should_continue = processed_count < max_products
            
            if should_continue:
                await asyncio.sleep(1.0)  # 1 second between batches
            
            # Check if we've reached the limit
            if max_products is not None and processed_count >= max_products:
                all_products = all_products[:max_products]
                break
        
        # Count total metafields
        total_metafields = 0
        total_metaobject_references = 0
        
        for product in all_products:
            metafields_edges = product.get('metafields', {}).get('edges', [])
            total_metafields += len(metafields_edges)
            
            # Count metafields that reference metaobjects
            for edge in metafields_edges:
                metafield = edge.get('node', {})
                metafield_type = metafield.get('type', '')
                if 'metaobject_reference' in metafield_type:
                    total_metaobject_references += 1
        
        print(f"🎉 COMPLETED! Fetched {len(all_products)} products with {total_metafields} total metafields ({total_metaobject_references} metaobject references)")
        
        return ProductListResponse(
            success=True,
            message=f"Retrieved {len(all_products)} products with {total_metafields} metafields ({total_metaobject_references} metaobject references)",
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
            detail=f"Error fetching all products with metafields: {str(e)}"
        )
    finally:
        # Clean up executor
        if 'executor' in locals():
            executor.shutdown(wait=False)



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

