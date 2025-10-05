from fastapi import APIRouter, Path, HTTPException, Depends, Body
from typing import Dict


from services.shopify_service import ShopifyGraphQLConnector
from utils.schema.shopify_schema import (
    NamespaceResponse,
    StandardResponse
)
from dependencies import get_shopify_connector


router = APIRouter()


@router.get("/", response_model=NamespaceResponse)
async def get_product_namespaces(
    product_id: str = Path(..., description="Shopify product ID"),
    connector: ShopifyGraphQLConnector = Depends(get_shopify_connector)
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



@router.post("/{namespace}", response_model=StandardResponse)
async def create_namespace_with_fields(
    product_id: str = Path(..., description="Shopify product ID"),
    namespace: str = Path(..., description="New namespace name"),
    fields_data: Dict[str, Dict[str, str]] = Body(..., description="Fields to add to namespace"),
    connector: ShopifyGraphQLConnector = Depends(get_shopify_connector)
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

