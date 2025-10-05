import uvicorn
from fastapi import FastAPI

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

app = FastAPI(
    title="PO PDF Processor API", 
    version="1.0.0",
    description="API for Shopify, Zakya, and WhatsApp-Slack integrations"
)

app.include_router(
    products.router,
    prefix="/products",
    tags=["Shopify - Products"]
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