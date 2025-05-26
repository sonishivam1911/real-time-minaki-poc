from fastapi import FastAPI
from webhooks import invoice_webhook
import uvicorn
from core.config import settings

app = FastAPI(title="Zakya Webhook Service")

# Include routers
app.include_router(invoice_webhook.router, prefix="/webhooks", tags=["webhooks"])
# app.include_router(salesorder_webhook.router, prefix="/webhooks", tags=["webhooks"])

@app.get("/")
async def root():
    return {"message": "Zakya Webhook Service is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)