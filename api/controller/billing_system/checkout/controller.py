"""
Checkout Controller - API endpoints for checkout and payment processing
"""
import traceback
from fastapi import APIRouter, HTTPException, Depends

from utils.schema.billing_system.checkout_schema import (
    CheckoutRequest,
    CheckoutResponse,
    HoldTransactionRequest,
    HoldTransactionResponse
)
from services.billing_system.checkout_service import CheckoutService


router = APIRouter()


@router.post("/process", response_model=CheckoutResponse)
async def process_checkout(
    checkout_data: CheckoutRequest,
):
    """
    Process complete checkout: validate cart, record payments, generate invoice.
    
    **Complete Workflow:**
    1. Validate cart and items
    2. Apply discount code (if provided)
    3. Apply tax rate
    4. Validate payment amounts
    5. Create invoice
    6. Record all payments
    7. Update stock items to 'sold'
    8. Update customer loyalty points
    9. Return invoice details
    
    **Example Request:**
    ```json
    {
      "cart_id": "cart_123",
      "customer_id": "cust_456",
      "payments": [
        {
          "payment_method": "cash",
          "payment_amount": 50000.00
        },
        {
          "payment_method": "card",
          "payment_amount": 30000.00,
          "card_type": "visa",
          "card_last_four": "1234",
          "transaction_id": "TXN789"
        }
      ],
      "discount_code": "FESTIVE10",
      "tax_rate_percent": 3.0,
      "notes": "Gift wrap requested",
      "sales_person": "Raj Kumar"
    }
    ```
    
    **Payment Methods:**
    - `cash` - Cash payment
    - `card` - Credit/Debit card
    - `upi` - UPI payment (Google Pay, PhonePe, etc.)
    - `bank_transfer` - NEFT/RTGS/IMPS
    - `cheque` - Cheque payment
    
    **Response:**
    ```json
    {
      "success": true,
      "invoice_id": "inv_001",
      "invoice_number": "INV-2024-0001",
      "total_amount": 79999.00,
      "paid_amount": 80000.00,
      "outstanding_amount": 0,
      "payment_status": "paid",
      "message": "Checkout completed successfully"
    }
    ```
    """
    try:
        service = CheckoutService()
        result = service.process_checkout(checkout_data)
    except Exception as e:
        print(f"❌ Error processing checkout for cart {checkout_data.cart_id}: {e}")
        print(f"{traceback.format_exc()}")
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Checkout failed')
        )
    
    return CheckoutResponse(**result)


@router.post("/hold", response_model=HoldTransactionResponse)
async def hold_transaction(
    hold_data: HoldTransactionRequest,
):
    """
    Hold/park a transaction for later completion.
    
    **Use Case:** Customer wants to browse more or needs time to decide
    
    **Example Request:**
    ```json
    {
      "cart_id": "cart_123",
      "notes": "Customer stepped out, will return in 30 mins"
    }
    ```
    
    The cart status is updated to 'held' and can be retrieved later.
    """
    service = CheckoutService()
    result = service.hold_transaction(
        cart_id=hold_data.cart_id,
        notes=hold_data.notes
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Failed to hold transaction')
        )
    
    return HoldTransactionResponse(
        success=True,
        cart_id=hold_data.cart_id,
        message=result['message']
    )


@router.get("/held", response_model=list)
async def get_held_transactions():
    """
    Get all held/parked transactions.
    
    **Returns:** List of all carts with status 'held'
    
    Useful for:
    - Viewing all parked transactions
    - Resuming a held transaction
    - Managing pending checkouts
    """
    service = CheckoutService()
    held_transactions = service.get_held_transactions()
    return held_transactions


@router.post("/cash-payment", response_model=dict)
async def process_cash_payment(
    total_amount: float,
    amount_tendered: float
):
    """
    Calculate change for cash payment.
    
    **Example:**
    ```
    POST /api/checkout/cash-payment?total_amount=1999.00&amount_tendered=2000.00
    ```
    
    **Response:**
    ```json
    {
      "total_amount": 1999.00,
      "amount_tendered": 2000.00,
      "change_due": 1.00,
      "status": "sufficient"
    }
    ```
    """
    if amount_tendered < total_amount:
        return {
            "total_amount": total_amount,
            "amount_tendered": amount_tendered,
            "shortage": total_amount - amount_tendered,
            "status": "insufficient"
        }
    
    change_due = amount_tendered - total_amount
    
    return {
        "total_amount": total_amount,
        "amount_tendered": amount_tendered,
        "change_due": change_due,
        "status": "sufficient"
    }