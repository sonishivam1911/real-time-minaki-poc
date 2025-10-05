# controller/shopify/product/metaobject/controller.py

from fastapi import APIRouter, Path, HTTPException, Depends

from services.shopify.product import ShopifyProductService
from services.shopify.metaobject import MetaobjectService
from utils.schema.shopify_schema import (
    MetaobjectResponse,
    MetaobjectListResponse,
    MetaobjectCreateRequest,
    MetaobjectLinkRequest,
    StandardResponse
)
from controller.shopify.dependencies import get_shopify_connector

router = APIRouter()


@router.get("/", response_model=MetaobjectResponse)
async def get_product_metaobjects(
    product_id: str = Path(..., description="Shopify product ID"),
    connector = Depends(get_shopify_connector)
):
    """
    Get all metaobjects referenced by a product.
    
    - **product_id**: Shopify product ID
    """
    try:
        product_service = ShopifyProductService(connector)
        result = product_service.get_product_metaobjects(product_id)
        
        if not result.get('data', {}).get('product'):
            return MetaobjectResponse(
                success=False,
                message=f"Product {product_id} not found",
                error="Product does not exist"
            )
        
        # Extract metaobjects from metafields
        metafields = result['data']['product'].get('metafields', {}).get('edges', [])
        metaobjects = []
        
        for mf_edge in metafields:
            metafield = mf_edge['node']
            
            # Single reference
            if metafield.get('reference'):
                metaobjects.append(metafield['reference'])
            
            # List references
            if metafield.get('references'):
                refs = metafield['references'].get('edges', [])
                metaobjects.extend([ref['node'] for ref in refs])
        
        return MetaobjectResponse(
            success=True,
            message=f"Retrieved {len(metaobjects)} metaobjects for product {product_id}",
            metaobjects=metaobjects
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching metaobjects for product {product_id}: {str(e)}"
        )


@router.post("/link", response_model=StandardResponse)
async def link_metaobject_to_product(
    product_id: str = Path(..., description="Shopify product ID"),
    link_data: MetaobjectLinkRequest = None,
    connector = Depends(get_shopify_connector)
):
    """
    Link a metaobject to a product via metafield reference.
    
    - **product_id**: Shopify product ID
    - **metaobject_id**: Metaobject ID to link
    - **namespace**: Metafield namespace for the reference
    - **key**: Metafield key for the reference
    """
    try:
        product_service = ShopifyProductService(connector)
        result = product_service.link_metaobject_to_product(
            product_id=product_id,
            metaobject_id=link_data.metaobject_id,
            namespace=link_data.namespace,
            key=link_data.key
        )
        
        if 'errors' in result or result.get('data', {}).get('metafieldsSet', {}).get('userErrors'):
            errors = result.get('errors', []) + result.get('data', {}).get('metafieldsSet', {}).get('userErrors', [])
            return StandardResponse(
                success=False,
                message="Failed to link metaobject",
                error=str(errors)
            )
        
        return StandardResponse(
            success=True,
            message=f"Metaobject {link_data.metaobject_id} linked to product {product_id}",
            data=result['data']['metafieldsSet']['metafields'][0] if result.get('data', {}).get('metafieldsSet', {}).get('metafields') else None
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error linking metaobject to product {product_id}: {str(e)}"
        )


@router.delete("/{namespace}/{key}", response_model=StandardResponse)
async def unlink_metaobject_from_product(
    product_id: str = Path(..., description="Shopify product ID"),
    namespace: str = Path(..., description="Metafield namespace"),
    key: str = Path(..., description="Metafield key"),
    connector = Depends(get_shopify_connector)
):
    """
    Unlink metaobject from product by deleting the metafield reference.
    
    - **product_id**: Shopify product ID
    - **namespace**: Metafield namespace
    - **key**: Metafield key
    """
    try:
        product_service = ShopifyProductService(connector)
        result = product_service.unlink_metaobject_from_product(product_id, namespace, key)
        
        if not result.get('success', True):
            return StandardResponse(
                success=False,
                message=result.get('message', 'Failed to unlink metaobject'),
                error="Metafield not found"
            )
        
        if 'errors' in result or result.get('data', {}).get('metafieldDelete', {}).get('userErrors'):
            errors = result.get('errors', []) + result.get('data', {}).get('metafieldDelete', {}).get('userErrors', [])
            return StandardResponse(
                success=False,
                message="Failed to unlink metaobject",
                error=str(errors)
            )
        
        return StandardResponse(
            success=True,
            message=f"Metaobject unlinked from product {product_id}"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error unlinking metaobject from product {product_id}: {str(e)}"
        )