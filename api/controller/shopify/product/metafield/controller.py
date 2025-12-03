from fastapi import APIRouter, Query, Path, HTTPException, Depends
from typing import Optional

from services.shopify_service import ShopifyGraphQLConnector
from utils.schema.shopify_schema import (
    MetafieldResponse,
    MetafieldCreateRequest,
    StandardResponse,
    MetafieldUpdateRequest
)
from controller.shopify.dependencies import get_shopify_connector


router = APIRouter()


@router.get("/", response_model=MetafieldResponse)
async def get_product_metafields(
    product_id: str = Path(..., description="Shopify product ID"),
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    key: Optional[str] = Query(None, description="Filter by key"),
    connector: ShopifyGraphQLConnector = Depends(get_shopify_connector)
):
    """
    Get metafields for a product.
    
    - **product_id**: Shopify product ID
    - **namespace**: Optional namespace filter
    - **key**: Optional key filter (requires namespace)
    """
    try:
        result = connector.get_complete_product_with_metafields(product_id)
        
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

@router.post("/", response_model=StandardResponse)
async def add_metafield_to_product(
    product_id: str = Path(..., description="Shopify product ID"),
    metafield_data: MetafieldCreateRequest = None,
    connector: ShopifyGraphQLConnector = Depends(get_shopify_connector)
):
    """
    Add a metafield to a product (creates namespace automatically if new).
    
    - **product_id**: Shopify product ID
    - **namespace**: Metafield namespace (created automatically if doesn't exist)
    - **key**: Metafield key
    - **value**: Metafield value
    - **type**: Metafield type (default: single_line_text_field)
    """
    try:
        result = connector.add_or_update_metafield(
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
            message=f"Metafield {metafield_data.namespace}.{metafield_data.key} added/updated for product {product_id}",
            data=result['data']['metafieldsSet']['metafields'][0] if result.get('data', {}).get('metafieldsSet', {}).get('metafields') else None
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error adding metafield to product {product_id}: {str(e)}"
        )


@router.put("/{namespace}/{key}", response_model=StandardResponse)
async def update_metafield_value(
    product_id: str = Path(..., description="Shopify product ID"),
    namespace: str = Path(..., description="Metafield namespace"),
    key: str = Path(..., description="Metafield key"),
    metafield_data: MetafieldUpdateRequest = None,
    connector: ShopifyGraphQLConnector = Depends(get_shopify_connector)
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



@router.delete("/{namespace}/{key}", response_model=StandardResponse)
async def delete_metafield(
    product_id: str = Path(..., description="Shopify product ID"),
    namespace: str = Path(..., description="Metafield namespace"),
    key: str = Path(..., description="Metafield key"),
    connector: ShopifyGraphQLConnector = Depends(get_shopify_connector)
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


