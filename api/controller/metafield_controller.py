from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from functools import lru_cache
from typing import Optional, List, Dict

from services.shopify_service import ShopifyGraphQLConnector
from utils.schema.shopify_schema import (
    StandardResponse, MetafieldResponse, 
    MetafieldCreateRequest, MetafieldUpdateRequest
)

router = APIRouter()

# Dependency to get Shopify connector
@lru_cache()
def get_shopify_connector():
    """Get cached Shopify connector instance."""
    return ShopifyGraphQLConnector()

def get_connector():
    """Dependency for FastAPI to inject Shopify connector."""
    return get_shopify_connector()

@router.get("/{product_id}/metafields", response_model=MetafieldResponse)
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

@router.post("/{product_id}/metafields", response_model=StandardResponse)
async def add_metafield_to_product(
    metafield_data: MetafieldCreateRequest,
    product_id: str = Path(..., description="Shopify product ID"),
    connector: ShopifyGraphQLConnector = Depends(get_connector)
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

@router.put("/{product_id}/metafields/{namespace}/{key}", response_model=StandardResponse)
async def update_metafield_value(
    metafield_data: MetafieldUpdateRequest,
    product_id: str = Path(..., description="Shopify product ID"),
    namespace: str = Path(..., description="Metafield namespace"),
    key: str = Path(..., description="Metafield key"),
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

@router.delete("/{product_id}/metafields/{namespace}/{key}", response_model=StandardResponse)
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

@router.post("/{product_id}/namespaces/{namespace}", response_model=StandardResponse)
async def create_namespace_with_fields(
    product_id: str = Path(..., description="Shopify product ID"),
    namespace: str = Path(..., description="New namespace name"),
    fields_data: Dict[str, Dict[str, str]] = Body(..., description="Fields to add to namespace"),
    connector: ShopifyGraphQLConnector = Depends(get_connector)
):
    """
    Create a new namespace by adding multiple fields at once.
    
    Request body example:
    {
        "color": {"value": "Blue", "type": "single_line_text_field"},
        "size": {"value": "Large", "type": "single_line_text_field"},
        "weight": {"value": "1.5", "type": "number_decimal"}
    }
    """
    try:
        result = connector.create_namespace_with_fields(
            product_id=product_id,
            namespace=namespace,
            fields_data=fields_data
        )
        
        if 'errors' in result or result.get('data', {}).get('metafieldsSet', {}).get('userErrors'):
            errors = result.get('errors', []) + result.get('data', {}).get('metafieldsSet', {}).get('userErrors', [])
            return StandardResponse(
                success=False,
                message=f"Failed to create namespace '{namespace}'",
                error=str(errors)
            )
        
        created_count = len(result.get('data', {}).get('metafieldsSet', {}).get('metafields', []))
        return StandardResponse(
            success=True,
            message=f"Created namespace '{namespace}' with {created_count} fields for product {product_id}",
            data={
                "namespace": namespace,
                "fields_created": created_count,
                "metafields": result['data']['metafieldsSet']['metafields']
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating namespace '{namespace}' for product {product_id}: {str(e)}"
        )

# Bulk metafield operations endpoint
@router.post("/bulk/metafields", response_model=StandardResponse)
async def bulk_update_metafields(
    metafields_data: List[Dict[str, str]] = Body(..., description="List of metafields to create/update"),
    connector: ShopifyGraphQLConnector = Depends(get_connector)
):
    """
    Bulk create/update metafields across multiple products.
    
    Request body example:
    [
        {
            "product_id": "5714011652253",
            "namespace": "custom",
            "key": "color",
            "value": "Blue",
            "type": "single_line_text_field"
        },
        {
            "product_id": "5714011652254", 
            "namespace": "seo",
            "key": "focus_keyword",
            "value": "jewelry",
            "type": "single_line_text_field"
        }
    ]
    """
    try:
        result = connector.bulk_create_update_metafields(metafields_data)
        
        if 'errors' in result or result.get('data', {}).get('metafieldsSet', {}).get('userErrors'):
            errors = result.get('errors', []) + result.get('data', {}).get('metafieldsSet', {}).get('userErrors', [])
            return StandardResponse(
                success=False,
                message="Bulk metafield operation failed",
                error=str(errors)
            )
        
        processed_count = len(result.get('data', {}).get('metafieldsSet', {}).get('metafields', []))
        return StandardResponse(
            success=True,
            message=f"Bulk processed {processed_count} metafields",
            data={
                "processed_count": processed_count,
                "metafields": result['data']['metafieldsSet']['metafields']
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error in bulk metafield operation: {str(e)}"
        )