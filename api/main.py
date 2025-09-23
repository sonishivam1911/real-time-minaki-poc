import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Query, Path
from fastapi.responses import JSONResponse
import datetime
from functools import lru_cache
from typing import Optional

from core.config import settings
from services.salesorder_service import process_single_pdf
from schema.taj_invoices import InvoiceResponse
from services.invoices_service import InvoiceService
from services.whatsapp_slack_service import WhatsAppSlackService
from utils.schema.whatsapp_slack_schema import MessageRequest, MessageResponse, ThreadMappingsResponse
from utils.schema.shopify_schema import StandardResponse, ProductResponse, ProductListResponse, ProductCreateRequest, ProductUpdateRequest, MetafieldCreateRequest, MetafieldUpdateRequest, NamespaceResponse, MetafieldResponse, AllNamespacesKeysResponse, NamespaceKeysResponse

from services.shopify_service import ShopifyGraphQLConnector
from core.database import db



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
    
@app.post("/whatsapp-slack/process-message", response_model=MessageResponse)
async def process_message(request: MessageRequest):
    """
    Unified endpoint to handle both WhatsApp->Slack and Slack->WhatsApp messages
    
    For WhatsApp messages:
    - message_type: "whatsapp"
    - phone_number: Required
    - message_text: Required
    - sender_name: Optional
    
    For Slack messages:
    - message_type: "slack" 
    - thread_id: Required
    - message_text: Required
    """
    try:
        whatsapp_slack_service = WhatsAppSlackService()
        result = whatsapp_slack_service.process_message(request)
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in process_message endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    


@app.get("/whatsapp-slack/thread-mappings", response_model=ThreadMappingsResponse)
async def get_all_thread_mappings():
    """
    Get all thread mappings for debugging and admin purposes
    """
    try:
        whatsapp_slack_service = WhatsAppSlackService()
        result = whatsapp_slack_service.get_all_thread_mappings()
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_thread_mappings endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


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
    


# Dependency to get Shopify connector
@lru_cache()
def get_shopify_connector():
    """Get cached Shopify connector instance."""
    return ShopifyGraphQLConnector()


def get_connector():
    """Dependency for FastAPI to inject Shopify connector."""
    return get_shopify_connector()


@app.get("/products", response_model=ProductListResponse)
async def get_products(
    limit: int = Query(20, ge=1, le=250, description="Number of products to fetch"),
    after: Optional[str] = Query(None, description="Cursor for pagination"),
    search: Optional[str] = Query(None, description="Search query (Shopify format)"),
    connector: ShopifyGraphQLConnector = Depends(get_connector)
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


@app.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str = Path(..., description="Shopify product ID"),
    include_all_metafields: bool = Query(False, description="Include all metafields (may be slow)"),
    connector: ShopifyGraphQLConnector = Depends(get_connector)
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


@app.post("/products", response_model=ProductResponse)
async def create_product(
    product_data: ProductCreateRequest,
    connector: ShopifyGraphQLConnector = Depends(get_connector)
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


@app.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str = Path(..., description="Shopify product ID"),
    product_data: ProductUpdateRequest = None,
    connector: ShopifyGraphQLConnector = Depends(get_connector)
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


@app.delete("/products/{product_id}", response_model=StandardResponse)
async def delete_product(
    product_id: str = Path(..., description="Shopify product ID"),
    connector: ShopifyGraphQLConnector = Depends(get_connector)
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



@app.get("/products/{product_id}/metafields", response_model=MetafieldResponse)
async def get_product_metafields(
    product_id: str = Path(..., description="Shopify product ID"),
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    key: Optional[str] = Query(None, description="Filter by key"),
    connector: ShopifyGraphQLConnector = Depends(get_connector)
):
    """
    Get metafields for a product.
    
    - **product_id**: Shopify product ID
    - **namespace**: Optional namespace filter
    - **key**: Optional key filter (requires namespace)
    """
    try:
        result = connector.get_product_metafields(product_id, namespace, key)
        
        if not result.get('data', {}).get('product'):
            return MetafieldResponse(
                success=False,
                message=f"Product {product_id} not found",
                error="Product does not exist"
            )
        
        metafields_data = result['data']['product'].get('metafields', {}).get('edges', [])
        metafields = [edge['node'] for edge in metafields_data]
        
        return MetafieldResponse(
            success=True,
            message=f"Retrieved {len(metafields)} metafields for product {product_id}",
            metafields=metafields
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching metafields for product {product_id}: {str(e)}"
        )


@app.post("/products/{product_id}/metafields", response_model=StandardResponse)
async def add_metafield_to_product(
    product_id: str = Path(..., description="Shopify product ID"),
    metafield_data: MetafieldCreateRequest = None,
    connector: ShopifyGraphQLConnector = Depends(get_connector)
):
    """
    Add a metafield to a product.
    
    - **product_id**: Shopify product ID
    - **namespace**: Metafield namespace
    - **key**: Metafield key
    - **value**: Metafield value
    - **type**: Metafield type (default: single_line_text_field)
    """
    try:
        result = connector.add_metafield_to_product(
            product_id=product_id,
            namespace=metafield_data.namespace,
            key=metafield_data.key,
            value=metafield_data.value,
            field_type=metafield_data.type
        )
        
        if 'errors' in result or result.get('data', {}).get('metafieldsSet', {}).get('userErrors'):
            errors = result.get('errors', []) + result.get('data', {}).get('metafieldsSet', {}).get('userErrors', [])
            return StandardResponse(
                success=False,
                message="Failed to add metafield",
                error=str(errors)
            )
        
        return StandardResponse(
            success=True,
            message=f"Metafield {metafield_data.namespace}.{metafield_data.key} added to product {product_id}",
            data=result['data']['metafieldsSet']['metafields'][0] if result.get('data', {}).get('metafieldsSet', {}).get('metafields') else None
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error adding metafield to product {product_id}: {str(e)}"
        )


@app.put("/products/{product_id}/metafields/{namespace}/{key}", response_model=StandardResponse)
async def update_metafield_value(
    product_id: str = Path(..., description="Shopify product ID"),
    namespace: str = Path(..., description="Metafield namespace"),
    key: str = Path(..., description="Metafield key"),
    metafield_data: MetafieldUpdateRequest = None,
    connector: ShopifyGraphQLConnector = Depends(get_connector)
):
    """
    Update the value of an existing metafield.
    
    - **product_id**: Shopify product ID
    - **namespace**: Metafield namespace
    - **key**: Metafield key
    - **value**: New metafield value
    """
    try:
        result = connector.update_metafield_value(
            product_id=product_id,
            namespace=namespace,
            key=key,
            new_value=metafield_data.value
        )
        
        if 'errors' in result or result.get('data', {}).get('metafieldsSet', {}).get('userErrors'):
            errors = result.get('errors', []) + result.get('data', {}).get('metafieldsSet', {}).get('userErrors', [])
            return StandardResponse(
                success=False,
                message="Failed to update metafield",
                error=str(errors)
            )
        
        return StandardResponse(
            success=True,
            message=f"Metafield {namespace}.{key} updated for product {product_id}",
            data=result['data']['metafieldsSet']['metafields'][0] if result.get('data', {}).get('metafieldsSet', {}).get('metafields') else None
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating metafield {namespace}.{key} for product {product_id}: {str(e)}"
        )


@app.delete("/products/{product_id}/metafields/{namespace}/{key}", response_model=StandardResponse)
async def delete_metafield(
    product_id: str = Path(..., description="Shopify product ID"),
    namespace: str = Path(..., description="Metafield namespace"),
    key: str = Path(..., description="Metafield key"),
    connector: ShopifyGraphQLConnector = Depends(get_connector)
):
    """
    Delete a metafield from a product.
    
    - **product_id**: Shopify product ID
    - **namespace**: Metafield namespace
    - **key**: Metafield key
    """
    try:
        result = connector.delete_metafield_by_key(product_id, namespace, key)
        
        if not result.get('success', True) and 'not found' in result.get('message', ''):
            return StandardResponse(
                success=False,
                message=f"Metafield {namespace}.{key} not found for product {product_id}",
                error="Metafield does not exist"
            )
        
        if 'errors' in result or result.get('data', {}).get('metafieldDelete', {}).get('userErrors'):
            errors = result.get('errors', []) + result.get('data', {}).get('metafieldDelete', {}).get('userErrors', [])
            return StandardResponse(
                success=False,
                message="Failed to delete metafield",
                error=str(errors)
            )
        
        return StandardResponse(
            success=True,
            message=f"Metafield {namespace}.{key} deleted from product {product_id}"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting metafield {namespace}.{key} for product {product_id}: {str(e)}"
        )




# @app.get("/namespaces", response_model=NamespaceResponse)
# async def get_all_namespaces(
#     use_cache: bool = Query(True, description="Use cached namespace data"),
#     connector: ShopifyGraphQLConnector = Depends(get_connector)
# ):
#     """
#     Get all unique metafield namespaces across the store.
    
#     - **use_cache**: Whether to use cached data (faster) or fresh scan
#     """
#     try:
#         # Check database cache first if use_cache is True
#         if use_cache:
#             try:
#                 cached_namespaces = db.execute_query(
#                     "SELECT DISTINCT namespace FROM cached_namespaces ORDER BY namespace",
#                     return_data=True
#                 )
                
#                 if not cached_namespaces.empty:
#                     namespaces_list = cached_namespaces['namespace'].tolist()
#                     return NamespaceResponse(
#                         success=True,
#                         message=f"Retrieved {len(namespaces_list)} cached namespaces",
#                         namespaces=namespaces_list,
#                         count=len(namespaces_list)
#                     )
#             except Exception as e:
#                 print(f"Cache lookup failed: {e}, falling back to fresh scan")
        
#         # Fresh scan from Shopify
#         namespaces = connector.get_all_unique_namespaces(use_cache=False)
        
#         # Cache the results
#         try:
#             if namespaces:
#                 import pandas as pd
#                 namespace_df = pd.DataFrame({
#                     'namespace': namespaces,
#                     'discovered_at': [datetime.datetime.now()] * len(namespaces)
#                 })
#                 db.create_table('cached_namespaces', namespace_df)
#         except Exception as e:
#             print(f"Failed to cache namespaces: {e}")
        
#         return NamespaceResponse(
#             success=True,
#             message=f"Retrieved {len(namespaces)} namespaces",
#             namespaces=namespaces,
#             count=len(namespaces)
#         )
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Error fetching namespaces: {str(e)}"
#         )


@app.get("/products/namespaces/{product_id}", response_model=NamespaceResponse)
async def get_product_namespaces(
    product_id: str = Path(..., description="Shopify product ID"),
    connector: ShopifyGraphQLConnector = Depends(get_connector)
):
    """
    Get all namespaces for a specific product.
    
    - **product_id**: Shopify product ID
    """
    try:
        print(f"Product id is : {product_id}")
        namespaces = connector.get_product_namespaces(product_id)
        
        return NamespaceResponse(
            success=True,
            message=f"Retrieved {len(namespaces)} namespaces for product {product_id}",
            namespaces=namespaces,
            count=len(namespaces)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching namespaces for product {product_id}: {str(e)}"
        )


@app.post("/namespaces/sync", response_model=StandardResponse)
async def sync_namespace_cache(
    max_products: Optional[int] = Query(None, description="Maximum products to analyze"),
    connector: ShopifyGraphQLConnector = Depends(get_connector)
):
    """
    Background job to refresh namespace cache from Shopify.
    
    - **max_products**: Limit analysis to N products (None = all products)
    """
    try:
        # Run namespace analysis
        analysis = connector.analyze_metafield_namespaces_for_db(max_products=max_products)
        
        # Store in database
        import pandas as pd
        
        # Store namespace summary
        summary_df = pd.DataFrame([analysis['summary']])
        db.create_table('namespace_analysis_summary', summary_df)
        
        # Store detailed namespace data
        namespace_rows = []
        for namespace, data in analysis['namespaces'].items():
            namespace_rows.append(data)
        
        if namespace_rows:
            namespace_df = pd.DataFrame(namespace_rows)
            db.create_table('namespace_analysis_detail', namespace_df)
            
            # Update simple namespace cache
            simple_namespaces = pd.DataFrame({
                'namespace': list(analysis['namespaces'].keys()),
                'discovered_at': [datetime.datetime.now()] * len(analysis['namespaces'])
            })
            db.create_table('cached_namespaces', simple_namespaces)
        
        return StandardResponse(
            success=True,
            message=f"Namespace sync completed. Analyzed {analysis['summary']['total_products_analyzed']} products, found {analysis['summary']['unique_namespaces']} namespaces",
            data=analysis['summary']
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error syncing namespace cache: {str(e)}"
        )



@app.get("/namespaces/{namespace}/keys", response_model=NamespaceKeysResponse)
async def get_namespace_keys(
    namespace: str = Path(..., description="Namespace to analyze"),
    max_products: Optional[int] = Query(100, ge=10, le=1000, description="Maximum products to scan"),
    connector: ShopifyGraphQLConnector = Depends(get_connector)
):
    """
    Get all unique keys for a specific namespace.
    
    - **namespace**: Target namespace (e.g., 'reviews', 'seo', 'custom')
    - **max_products**: Limit products to scan (10-1000, default 100)
    
    Returns detailed analysis of all keys within the namespace including:
    - Key names and usage counts
    - Sample values and field types
    - Products that use each key
    """
    try:
        result = connector.get_namespace_keys(namespace, max_products)
        
        return NamespaceKeysResponse(
            success=True,
            message=f"Found {result['unique_keys_count']} unique keys in namespace '{namespace}'",
            namespace=result['namespace'],
            unique_keys_count=result['unique_keys_count'],
            total_metafields=result['total_metafields'],
            products_scanned=result['products_scanned'],
            keys=result['keys'],
            analysis_timestamp=result['analysis_timestamp']
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing namespace '{namespace}': {str(e)}"
        )

@app.get("/namespaces/keys", response_model=AllNamespacesKeysResponse)
async def get_all_namespaces_with_keys(
    max_products: Optional[int] = Query(200, ge=50, le=2000, description="Maximum products to scan"),
    use_cache: bool = Query(False, description="Use cached data (faster but may be outdated)"),
    connector: ShopifyGraphQLConnector = Depends(get_connector)
):
    """
    Get all namespaces with their unique keys.
    
    - **max_products**: Limit products to scan (50-2000, default 200)
    - **use_cache**: Use cached analysis if available
    
    Returns comprehensive analysis of all namespaces and their keys:
    - Complete namespace inventory
    - Key counts per namespace
    - Field type analysis
    """
    try:
        # Check cache first if requested
        if use_cache:
            try:
                cached_data = db.execute_query(
                    "SELECT * FROM namespace_keys_analysis ORDER BY created_at DESC LIMIT 1",
                    return_data=True
                )
                
                if not cached_data.empty:
                    import json
                    cached_result = json.loads(cached_data.iloc[0]['analysis_data'])
                    
                    return AllNamespacesKeysResponse(
                        success=True,
                        message=f"Retrieved cached analysis with {cached_result['summary']['total_namespaces']} namespaces",
                        summary=cached_result['summary'],
                        namespaces=cached_result['namespaces']
                    )
            except Exception as e:
                print(f"Cache lookup failed: {e}, performing fresh analysis")
        
        # Fresh analysis
        result = connector.get_all_namespaces_with_keys(max_products)
        
        # Cache the results
        try:
            import json
            import pandas as pd
            
            cache_df = pd.DataFrame([{
                'analysis_data': json.dumps(result),
                'created_at': datetime.datetime.now(),
                'products_scanned': result['summary']['products_scanned'],
                'namespaces_found': result['summary']['total_namespaces']
            }])
            
            db.create_table('namespace_keys_analysis', cache_df)
        except Exception as e:
            print(f"Failed to cache namespace keys analysis: {e}")
        
        return AllNamespacesKeysResponse(
            success=True,
            message=f"Analyzed {result['summary']['total_namespaces']} namespaces from {result['summary']['products_scanned']} products",
            summary=result['summary'],
            namespaces=result['namespaces']
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing all namespaces: {str(e)}"
        )

# Enhanced namespaces endpoint (update the existing one)
@app.get("/namespaces", response_model=NamespaceResponse)
async def get_all_namespaces(
    use_cache: bool = Query(True, description="Use cached namespace data"),
    include_keys: bool = Query(False, description="Include key counts for each namespace"),
    connector: ShopifyGraphQLConnector = Depends(get_connector)
):
    """
    Get all unique metafield namespaces across the store.
    
    - **use_cache**: Whether to use cached data (faster) or fresh scan
    - **include_keys**: Include key counts (slower but more detailed)
    """
    try:
        if include_keys:
            # Get detailed namespace-keys analysis
            detailed_result = connector.get_all_namespaces_with_keys(max_products=100)
            
            namespaces_with_counts = []
            for namespace, data in detailed_result['namespaces'].items():
                namespaces_with_counts.append({
                    'namespace': namespace,
                    'unique_keys_count': data['unique_keys_count']
                })
            
            return NamespaceResponse(
                success=True,
                message=f"Retrieved {len(namespaces_with_counts)} namespaces with key counts",
                namespaces=[item['namespace'] for item in namespaces_with_counts],
                count=len(namespaces_with_counts),
                data={'namespace_details': namespaces_with_counts}
            )
        
        # Original simple namespace list
        if use_cache:
            try:
                cached_namespaces = db.execute_query(
                    "SELECT DISTINCT namespace FROM cached_namespaces ORDER BY namespace",
                    return_data=True
                )
                
                if not cached_namespaces.empty:
                    namespaces_list = cached_namespaces['namespace'].tolist()
                    return NamespaceResponse(
                        success=True,
                        message=f"Retrieved {len(namespaces_list)} cached namespaces",
                        namespaces=namespaces_list,
                        count=len(namespaces_list)
                    )
            except Exception as e:
                print(f"Cache lookup failed: {e}, falling back to fresh scan")
        
        # Fresh scan from Shopify
        namespaces = connector.get_all_unique_namespaces(use_cache=False)
        
        # Cache the results
        try:
            if namespaces:
                import pandas as pd
                namespace_df = pd.DataFrame({
                    'namespace': namespaces,
                    'discovered_at': [datetime.datetime.now()] * len(namespaces)
                })
                db.create_table('cached_namespaces', namespace_df)
        except Exception as e:
            print(f"Failed to cache namespaces: {e}")
        
        return NamespaceResponse(
            success=True,
            message=f"Retrieved {len(namespaces)} namespaces",
            namespaces=namespaces,
            count=len(namespaces)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching namespaces: {str(e)}"
        )




if __name__ == "__main__":
    
    uvicorn.run(
        "main:app",  # Use import string instead of app object
        host="0.0.0.0", 
        port=8000, 
        reload=True
    )