"""
Inventory Controller - API endpoints for inventory management
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Path
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

from services.billing_system.inventory_service import InventoryService


router = APIRouter()


# ============================================================================
# REQUEST SCHEMAS
# ============================================================================

class MetalLotReceiptRequest(BaseModel):
    """Request schema for receiving metal lot"""
    lot_label: str = Field(..., description="Human-readable lot label")
    metal_type: str = Field(..., description="Type of metal")
    purity_k: float = Field(..., description="Purity in karats")
    gross_weight_g: float = Field(..., description="Gross weight in grams")
    net_weight_g: float = Field(..., description="Net weight in grams")
    received_from: str = Field(..., description="Vendor/source")
    received_date: date = Field(..., description="Date of receipt")
    location: str = Field(..., description="Storage location")
    notes: Optional[str] = None


class MetalConsumptionRequest(BaseModel):
    """Request schema for consuming metal from lot"""
    weight_consumed_g: float = Field(..., description="Weight to consume")
    variant_id: str = Field(..., description="Variant being produced")
    work_order_ref: str = Field(..., description="Work order reference")


class StockItemAddRequest(BaseModel):
    """Request schema for adding finished product to stock"""
    variant_id: str = Field(..., description="Variant ID")
    serial_no: str = Field(..., description="Serial number/barcode")
    lot_id: str = Field(..., description="Finished goods lot ID")
    location: str = Field(..., description="Storage location")


class SaleRecordRequest(BaseModel):
    """Request schema for recording a sale"""
    stock_item_id: str = Field(..., description="Stock item ID")
    serial_no: str = Field(..., description="Serial number")
    sale_invoice_id: str = Field(..., description="Sale invoice ID")
    customer_id: Optional[str] = None
    sale_price: Optional[float] = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/lots/receive", response_model=dict, status_code=201)
async def receive_metal_lot(
    request: MetalLotReceiptRequest
):
    """
    Receive a metal lot (Goods Receipt Note - GRN).
    
    **Use Case:** Record incoming metal from vendors/refineries
    
    **Example:**
    ```json
    {
      "lot_label": "GOLD-22K-LOT-2024-001",
      "metal_type": "gold",
      "purity_k": 22.00,
      "gross_weight_g": 500.00,
      "net_weight_g": 485.00,
      "received_from": "ABC Refinery",
      "received_date": "2024-12-01",
      "location": "VAULT-A",
      "notes": "Monthly purchase"
    }
    ```
    """
    service = InventoryService()
    result = service.receive_metal_lot(
        lot_label=request.lot_label,
        metal_type=request.metal_type,
        purity_k=request.purity_k,
        gross_weight_g=request.gross_weight_g,
        net_weight_g=request.net_weight_g,
        received_from=request.received_from,
        received_date=request.received_date,
        location=request.location,
        notes=request.notes
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Failed to receive metal lot')
        )
    
    return result


@router.post("/lots/{lot_id}/consume", response_model=dict)
async def consume_metal_from_lot(
    lot_id: str = Path(..., description="Lot ID to consume from"),
    request: MetalConsumptionRequest = ...
):
    """
    Consume metal from a lot for production.
    
    **Use Case:** Track metal usage when creating jewelry pieces
    
    **Example:**
    ```json
    {
      "weight_consumed_g": 3.80,
      "variant_id": "var_001",
      "work_order_ref": "WO-2024-456"
    }
    ```
    
    **Validates:**
    - Lot exists and is available
    - Sufficient weight available
    
    **Updates:**
    - Reduces lot weight
    - Creates stock movement record
    - Updates lot status if fully consumed
    """
    service = InventoryService()
    result = service.consume_metal_lot(
        lot_id=lot_id,
        weight_consumed_g=request.weight_consumed_g,
        variant_id=request.variant_id,
        work_order_ref=request.work_order_ref
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Failed to consume metal')
        )
    
    return result


@router.get("/available", response_model=dict)
async def get_available_inventory(
    metal_type: Optional[str] = Query(None, description="Filter by metal type"),
    purity_k: Optional[float] = Query(None, description="Filter by purity")
):
    """
    Get available inventory by metal type and purity.
    
    **Query Parameters:**
    - **metal_type**: Filter by metal type (gold, silver, platinum)
    - **purity_k**: Filter by purity (e.g., 22.00, 18.00)
    
    **Returns:**
    - Total available weight
    - List of lots with details
    - Sorted by received date (FIFO)
    
    **Example:**
    ```
    GET /api/inventory/available?metal_type=gold&purity_k=22
    ```
    
    **Response:**
    ```json
    {
      "metal_type": "gold",
      "purity_k": 22.00,
      "total_weight_g": 1245.50,
      "lots": [
        {
          "lot_id": "lot_123",
          "lot_label": "GOLD-22K-LOT-2024-001",
          "net_weight_g": 485.00,
          "location": "VAULT-A",
          "received_date": "2024-11-15"
        }
      ]
    }
    ```
    """
    service = InventoryService()
    result = service.get_available_inventory(
        metal_type=metal_type,
        purity_k=purity_k
    )
    
    return result


@router.post("/stock-items", response_model=dict, status_code=201)
async def add_stock_item(
    request: StockItemAddRequest
):
    """
    Add a finished product to stock with serial tracking.
    
    **Use Case:** Register completed jewelry pieces in inventory
    
    **Example:**
    ```json
    {
      "variant_id": "var_001",
      "serial_no": "CR001-SN-00123",
      "lot_id": "lot_finished_001",
      "location": "SHOWROOM-1"
    }
    ```
    """
    service = InventoryService()
    result = service.add_finished_product_to_stock(
        variant_id=request.variant_id,
        serial_no=request.serial_no,
        lot_id=request.lot_id,
        location=request.location
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Failed to add stock item')
        )
    
    return result


@router.post("/sales/record", response_model=dict)
async def record_sale(
    request: SaleRecordRequest,
):
    """
    Record a sale of a stock item.
    
    **Use Case:** Track when jewelry pieces are sold
    
    **Updates:**
    - Changes stock item status to 'sold'
    - Creates stock movement record
    - Links to sale invoice
    
    **Example:**
    ```json
    {
      "stock_item_id": "stock_123",
      "serial_no": "CR001-SN-00123",
      "sale_invoice_id": "INV-SALE-001",
      "customer_id": "cust_456",
      "sale_price": 99999.00
    }
    ```
    """
    service = InventoryService()
    result = service.record_sale(
        stock_item_id=request.stock_item_id,
        serial_no=request.serial_no,
        sale_invoice_id=request.sale_invoice_id,
        customer_id=request.customer_id,
        sale_price=request.sale_price
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Failed to record sale')
        )
    
    return result


@router.get("/movements", response_model=dict)
async def get_stock_movements(
    serial_no: Optional[str] = Query(None, description="Filter by serial number"),
    stock_item_id: Optional[str] = Query(None, description="Filter by stock item ID"),
):
    """
    Get stock movement history for audit trail.
    
    **Query Parameters:**
    - **serial_no**: Filter by serial number
    - **stock_item_id**: Filter by stock item ID
    
    **Returns:** Complete movement history for the item
    
    **Movement Types:**
    - `receive`: Item received into stock
    - `consume`: Metal consumed for production
    - `transfer`: Location transfer
    - `sale`: Item sold
    - `return`: Customer return
    - `scrap`: Item scrapped
    """
    if not serial_no and not stock_item_id:
        raise HTTPException(
            status_code=400,
            detail="Either serial_no or stock_item_id must be provided"
        )
    
    service = InventoryService()
    movements = service.get_stock_movement_history(
        serial_no=serial_no,
        stock_item_id=stock_item_id
    )
    
    return {
        "movements": movements
    }