"""
Variant Controller - API endpoints for product variant operations
"""
from fastapi import APIRouter, HTTPException, Depends, Path
from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal

from services.billing_system.product_service import ProductService


router = APIRouter()


# ============================================================================
# REQUEST SCHEMAS
# ============================================================================

class MetalComponentUpdateRequest(BaseModel):
    """Request schema for updating metal component"""
    id: str
    metal_rate_per_g: Optional[Decimal] = None
    making_charge_per_g: Optional[Decimal] = None
    making_charge_flat: Optional[Decimal] = None
    wastage_percent: Optional[Decimal] = None


class VariantComponentsUpdateRequest(BaseModel):
    """Request schema for updating variant components"""
    metal_components: Optional[List[MetalComponentUpdateRequest]] = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("", response_model=dict)
async def get_variants_for_product(
    product_id: str = Path(..., description="Product ID")
):
    """
    Get all variants for a specific product.
    
    **Returns:**
    - List of variants with their components
    - Pricing breakdown for each variant
    """
    # Get product with variants
    service = ProductService()
    product = service.get_product_by_id(product_id)
    
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Product {product_id} not found"
        )
    
    return {
        "product_id": product_id,
        "variants": product.get('variants', [])
    }


@router.get("/{variant_id}", response_model=dict)
async def get_variant_details(
    product_id: str = Path(..., description="Product ID"),
    variant_id: str = Path(..., description="Variant ID")
):
    """
    Get detailed information for a specific variant.
    
    **Returns:**
    - Variant details
    - All metal components
    - All diamond components
    - Complete pricing breakdown
    """
    # Get variant
    query = f"""
        SELECT * FROM product_variants 
        WHERE id = '{variant_id}' AND product_id = '{product_id}'
    """
    service = ProductService()
    variant_df = service.crud.execute_query(query, return_data=True)
    
    if variant_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Variant {variant_id} not found for product {product_id}"
        )
    
    variant = variant_df.iloc[0].to_dict()
    
    # Get metal components
    metal_query = f"""
        SELECT * FROM metal_components WHERE variant_id = '{variant_id}'
    """
    metal_df = service.crud.execute_query(metal_query, return_data=True)
    variant['metal_components'] = metal_df.to_dict('records')
    
    # Get diamond components
    diamond_query = f"""
        SELECT * FROM diamond_components WHERE variant_id = '{variant_id}'
    """
    diamond_df = service.crud.execute_query(diamond_query, return_data=True)
    variant['diamond_components'] = diamond_df.to_dict('records')
    
    # Get pricing breakdown
    pricing_query = f"""
        SELECT * FROM variant_pricing_breakdown WHERE variant_id = '{variant_id}'
    """
    pricing_df = service.crud.execute_query(pricing_query, return_data=True)
    if not pricing_df.empty:
        variant['pricing_breakdown'] = pricing_df.iloc[0].to_dict()
    
    return variant


@router.patch("/{variant_id}/components", response_model=dict)
async def update_variant_components(
    product_id: str = Path(..., description="Product ID"),
    variant_id: str = Path(..., description="Variant ID"),
    request: VariantComponentsUpdateRequest = ...
):
    """
    Update metal component pricing for a variant.
    
    **Use Case:** Update metal rates or making charges and recalculate pricing
    
    **Example:**
    ```json
    {
      "metal_components": [
        {
          "id": "metal_comp_123",
          "metal_rate_per_g": 5800.00
        }
      ]
    }
    ```
    
    **Process:**
    1. Updates specified metal components
    2. Automatically recalculates pricing breakdown
    3. Updates variant base_cost
    """
    # Verify variant exists
    query = f"""
        SELECT id FROM product_variants 
        WHERE id = '{variant_id}' AND product_id = '{product_id}'
    """
    
    service = ProductService()
    variant_df = service.crud.execute_query(query, return_data=True)
    
    if variant_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Variant {variant_id} not found"
        )
    
    # Update metal components
    if request.metal_components:
        for metal_comp in request.metal_components:
            updates = []
            
            if metal_comp.metal_rate_per_g is not None:
                updates.append(f"metal_rate_per_g = {float(metal_comp.metal_rate_per_g)}")
            if metal_comp.making_charge_per_g is not None:
                updates.append(f"making_charge_per_g = {float(metal_comp.making_charge_per_g)}")
            if metal_comp.making_charge_flat is not None:
                updates.append(f"making_charge_flat = {float(metal_comp.making_charge_flat)}")
            if metal_comp.wastage_percent is not None:
                updates.append(f"wastage_percent = {float(metal_comp.wastage_percent)}")
            
            if updates:
                updates_str = ", ".join(updates)
                update_query = f"""
                    UPDATE metal_components
                    SET {updates_str}
                    WHERE id = '{metal_comp.id}' AND variant_id = '{variant_id}'
                """
                service.crud.execute_query(update_query)
    
    # Recalculate pricing
    service._calculate_pricing_breakdown(variant_id)
    
    return {
        "success": True,
        "message": "Variant components updated and pricing recalculated",
        "variant_id": variant_id
    }


@router.patch("/{variant_id}", response_model=dict)
async def update_variant_metadata(
    product_id: str = Path(..., description="Product ID"),
    variant_id: str = Path(..., description="Variant ID"),
    sku: Optional[str] = None,
    price: Optional[Decimal] = None,
    status: Optional[str] = None
):
    """
    Update variant metadata (SKU, price, status).
    
    **Updatable Fields:**
    - **sku**: Stock keeping unit
    - **price**: Retail price
    - **status**: Variant status (active, discontinued)
    """
    # Verify variant exists
    query = f"""
        SELECT id FROM product_variants 
        WHERE id = '{variant_id}' AND product_id = '{product_id}'
    """
    
    service = ProductService()
    variant_df = service.crud.execute_query(query, return_data=True)
    
    if variant_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Variant {variant_id} not found"
        )
    
    # Build update query
    updates = []
    if sku:
        updates.append(f"sku = '{sku}'")
    if price is not None:
        updates.append(f"price = {float(price)}")
    if status:
        updates.append(f"status = '{status}'")
    
    if not updates:
        raise HTTPException(
            status_code=400,
            detail="No fields to update"
        )
    
    updates.append("updated_at = CURRENT_TIMESTAMP")
    updates_str = ", ".join(updates)
    
    update_query = f"""
        UPDATE product_variants
        SET {updates_str}
        WHERE id = '{variant_id}'
    """
    service.crud.execute_query(update_query)
    
    return {
        "success": True,
        "message": "Variant updated successfully",
        "variant_id": variant_id
    }


@router.delete("/{variant_id}", status_code=200)
async def delete_variant(
    product_id: str = Path(..., description="Product ID"),
    variant_id: str = Path(..., description="Variant ID"),
):
    """
    Delete a variant (sets status to discontinued).
    
    **Note:** This is a soft delete. The variant is marked as discontinued
    but not removed from the database.
    """
    # Verify variant exists
    query = f"""
        SELECT id FROM product_variants 
        WHERE id = '{variant_id}' AND product_id = '{product_id}'
    """
    
    service = ProductService()
    variant_df = service.crud.execute_query(query, return_data=True)
    
    if variant_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Variant {variant_id} not found"
        )
    
    # Soft delete
    update_query = f"""
        UPDATE product_variants
        SET status = 'discontinued', updated_at = CURRENT_TIMESTAMP
        WHERE id = '{variant_id}'
    """
    service.crud.execute_query(update_query)
    
    return {
        "success": True,
        "message": f"Variant {variant_id} marked as discontinued"
    }