"""
Pricing Controller - API endpoints for pricing recalculation
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from utils.schema.billing_system.product_schema import (
    PricingRecalculationRequest,
    PricingRecalculationResponse
)
from services.billing_system.pricing_service import PricingService


router = APIRouter()


@router.post("/recalculate", response_model=PricingRecalculationResponse)
async def recalculate_pricing(
    request: PricingRecalculationRequest,
):
    """
    Recalculate pricing for all variants or specific variants.
    
    **Use Cases:**
    1. **Daily metal rate updates**: Update metal rates and recalculate all products
    2. **Single product update**: Recalculate after changing components
    3. **Making charge updates**: Update making charges and recalculate
    
    **Request Body:**
    ```json
    {
      "variant_ids": ["var_001", "var_002"],  // Optional: specific variants
      "update_metal_rates": {
        "gold_22k": 6200.00,
        "gold_18k": 4800.00,
        "silver": 80.00,
        "platinum": 3500.00
      }
    }
    ```
    
    **If variant_ids is null or empty**: Recalculates ALL variants
    
    **If update_metal_rates provided**: Updates metal rates first, then recalculates
    
    **Returns:**
    - Number of variants successfully updated
    - List of any errors encountered
    """
    service = PricingService()
    result = service.recalculate_pricing(
        variant_ids=request.variant_ids,
        update_metal_rates=request.update_metal_rates
    )
    
    if not result['success'] and result['variants_updated'] == 0:
        raise HTTPException(
            status_code=500,
            detail=result['message']
        )
    
    return PricingRecalculationResponse(**result)


@router.get("/current-rates", response_model=dict)
async def get_current_metal_rates():
    """
    Get current average metal rates from all components in the system.
    
    **Returns:**
    ```json
    {
      "gold_22k": 6200.00,
      "gold_18k": 4800.00,
      "silver": 80.00,
      "platinum": 3500.00
    }
    ```
    
    These are the current average rates across all metal components.
    """
    service = PricingService()
    rates = service.get_current_metal_rates()
    
    return {
        "success": True,
        "rates": rates
    }


@router.get("/variant/{variant_id}/breakdown", response_model=dict)
async def get_variant_pricing_breakdown(
    variant_id: str
):
    """
    Get detailed pricing breakdown for a specific variant.
    
    **Returns:**
    - Metal value breakdown
    - Stone value breakdown
    - Making charges
    - Wastage charges
    - Final cost
    - Suggested retail price
    """
    query = f"""
        SELECT * FROM variant_pricing_breakdown
        WHERE variant_id = '{variant_id}'
    """
    
    service = PricingService()
    df = service.crud.execute_query(query, return_data=True)
    
    if df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Pricing breakdown not found for variant {variant_id}"
        )
    
    breakdown = df.iloc[0].to_dict()
    
    # Get metal components detail
    metal_query = f"""
        SELECT 
            metal_type,
            purity_k,
            net_weight_g,
            metal_rate_per_g,
            (net_weight_g * metal_rate_per_g) as metal_value,
            making_charge_per_g,
            making_charge_flat,
            (net_weight_g * making_charge_per_g + making_charge_flat) as total_making
        FROM metal_components
        WHERE variant_id = '{variant_id}'
    """
    metal_df = service.crud.execute_query(metal_query, return_data=True)
    
    # Get diamond components detail
    diamond_query = f"""
        SELECT 
            cert_no,
            shape,
            carat,
            cut,
            clarity,
            color_grade,
            stone_price_per_carat,
            (carat * stone_price_per_carat) as stone_value
        FROM diamond_components
        WHERE variant_id = '{variant_id}'
    """
    diamond_df = service.crud.execute_query(diamond_query, return_data=True)
    
    return {
        "variant_id": variant_id,
        "summary": breakdown,
        "metal_components": metal_df.to_dict('records'),
        "diamond_components": diamond_df.to_dict('records')
    }