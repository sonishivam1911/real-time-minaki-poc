import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import time
import json

# Import routers
from controller.shopify.product.metafield import controller as metafields
from controller.shopify.product.metafield import controller as product_namespaces
from controller.shopify.namespace import controller as namespaces
from controller.zakya.salesorder import controller as salesorders
from controller.zakya.invoice import controller as invoices
from controller.shopify.product import controller as products
from controller.whatsapp_slack import controller as  whatsapp_slack
from controller.shopify.product.metaobject import controller as product_metaobjects
from controller.shopify.metaobject import controller as metaobjects
from controller.image_editing import controller as image_editing_controller
from controller.shopify.metafield_migration import controller as metafield_migration_controller
from controller.agent import controller as agent_controller
from controller.agent import test_controller as agent_test_controller
from controller.nayka import controller as nykaa_controller
from controller.billing_system.inventory import controller as inventory_controller
from controller.billing_system.location import controller as location_controller
from controller.billing_system.shelf import controller as shelf_controller
from controller.billing_system.box import controller as box_controller
from controller.billing_system.product_location import controller as product_location_controller
from controller.billing_system.pricing import controller as pricing_controller
from controller.billing_system.product import controller as billing_product_controller
from controller.billing_system.variant import controller as variant_controller
from controller.billing_system.cart import controller as cart_controller
from controller.billing_system.checkout import controller as checkout_controller
from controller.billing_system.customer import controller as customer_controller
from controller.billing_system.invoice import controller as invoice_controller
from controller.billing_system.upload_inventory import controller as upload_inventory_controller

app = FastAPI(
    title="PO PDF Processor API", 
    version="1.0.0",
    description="API for Shopify, Zakya, and WhatsApp-Slack integrations"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # Expose all headers
)

# Add logging middleware to debug requests/responses
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log incoming request
    print(f"🔵 Incoming {request.method} {request.url}")
    print(f"🔵 Headers: {dict(request.headers)}")
    
    # Get request body if it exists
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            body = await request.body()
            if body:
                print(f"🔵 Body: {body.decode()}")
        except:
            pass
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    
    # Log response
    print(f"🟢 Response {response.status_code} for {request.method} {request.url}")
    print(f"🟢 Processing time: {process_time:.4f}s")
    print(f"🟢 Response headers: {dict(response.headers)}")
    
    return response

app.include_router(
    products.router,
    prefix="/products",
    tags=["Shopify - Products"]
)


app.include_router(
    metafield_migration_controller.router,
    prefix="/metafield-migration",
    tags=["Shopify - Metafield Migration"]
)

app.include_router(
    nykaa_controller.router,
    prefix="/nykaa",
    tags=["Nykaa - Product Export"]
)

app.include_router(
    metafields.router,
    prefix="/products/{product_id}/metafields",
    tags=["Shopify - Metafields"]
)


app.include_router(
    product_namespaces.router,
    prefix="/products/{product_id}/namespaces",
    tags=["Shopify - Product Namespaces"]
)

app.include_router(
    namespaces.router,
    prefix="/namespaces",
    tags=["Shopify - Namespaces"]
)

# Include Zakya routers
app.include_router(
    invoices.router,
    prefix="/process-pdf",
    tags=["Zakya - Invoices"]
)

app.include_router(
    salesorders.router,
    prefix="/generate-taj-invoices",
    tags=["Zakya - Sales Orders"]
)

# Include WhatsApp-Slack router
app.include_router(
    whatsapp_slack.router,
    prefix="/whatsapp-slack",
    tags=["Integrations - WhatsApp/Slack"]
)

app.include_router(
    product_metaobjects.router,
    prefix="/products/{product_id}/metaobjects",
    tags=["Shopify - Product Metaobjects"]
)

# Global metaobject routes
app.include_router(
    metaobjects.router,
    prefix="/metaobjects",
    tags=["Shopify - Metaobjects"]
)

app.include_router(
    image_editing_controller.router,
    prefix="/api/image-editing",
    tags=["Image Editing"]
)

app.include_router(
    agent_controller.router,
    prefix="/api/agent",
    tags=["Minaki Agents"]
)

app.include_router(
    agent_test_controller.router,
    prefix="/api/agent/test",
    tags=["Minaki Agents - Testing"]
)

# Include Billing System routers
app.include_router(
    inventory_controller.router,
    prefix="/billing_system/api/inventory",
    tags=["Billing System - Inventory"]
)

app.include_router(
    location_controller.router,
    tags=["Billing System - Inventory Locations"]
)

app.include_router(
    shelf_controller.router,
    tags=["Billing System - Inventory Shelves"]
)

app.include_router(
    box_controller.router,
    tags=["Billing System - Inventory Boxes"]
)

app.include_router(
    product_location_controller.router,
    tags=["Billing System - Product Locations"]
)

app.include_router(
    pricing_controller.router,
    prefix="/billing_system/api/pricing",
    tags=["Billing System - Pricing"]
)

app.include_router(
    billing_product_controller.router,
    prefix="/billing_system/api/products",
    tags=["Billing System - Products"]
)

app.include_router(
    variant_controller.router,
    prefix="/billing_system/api/products/{product_id}/variants",
    tags=["Billing System - Variants"]
)

app.include_router(
    cart_controller.router,
    prefix="/billing_system/api/carts",
    tags=["Billing System - Cart"]
)

app.include_router(
    checkout_controller.router,
    prefix="/billing_system/api/checkout",
    tags=["Billing System - Checkout"]
)

app.include_router(
    customer_controller.router,
    prefix="/billing_system/api/customers",
    tags=["Billing System - Customers"]
)

app.include_router(
    invoice_controller.router,
    prefix="/billing_system/api/invoices",
    tags=["Billing System - Invoices"]
)

app.include_router(
    upload_inventory_controller.router,
    prefix="/billing_system",
    tags=["Billing System - Upload Inventory"]
)

@app.get("/", tags=["System"])
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Welcome to PO PDF Processor API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "API is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)