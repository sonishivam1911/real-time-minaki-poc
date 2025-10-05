# controller/shopify/metaobject/controller.py

from fastapi import APIRouter, Query, Path, HTTPException, Depends
from typing import Optional

from services.shopify.metaobject import MetaobjectService
from utils.schema.shopify_schema import (
    MetaobjectResponse,
    MetaobjectListResponse,
    MetaobjectCreateRequest,
    MetaobjectUpdateRequest,
    MetaobjectDefinitionRequest,
    StandardResponse
)
from controller.shopify.dependencies import get_shopify_connector

router = APIRouter()


@router.get("/", response_model=MetaobjectListResponse)
async def get_all_metaobjects(
    connector = Depends(get_shopify_connector)
):
    """
    Get ALL metaobjects in the store, grouped by type.
    WARNING: This can be slow for stores with many metaobjects.
    """
    try:
        metaobject_service = MetaobjectService(connector)
        all_metaobjects = metaobject_service.get_all_metaobjects_by_definition()
        
        total = sum(len(entries) for entries in all_metaobjects.values())
        
        return MetaobjectListResponse(
            success=True,
            message=f"Retrieved {total} metaobjects across {len(all_metaobjects)} types",
            metaobjects=all_metaobjects
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching metaobjects: {str(e)}"
        )


@router.get("/definitions", response_model=StandardResponse)
async def get_metaobject_definitions(
    connector = Depends(get_shopify_connector)
):
    """
    Get all metaobject definitions (types/schemas) in the store.
    """
    try:
        metaobject_service = MetaobjectService(connector)
        result = metaobject_service.get_all_metaobject_definitions()
        
        definitions = result.get('data', {}).get('metaobjectDefinitions', {}).get('edges', [])
        definitions_list = [edge['node'] for edge in definitions]
        
        return StandardResponse(
            success=True,
            message=f"Retrieved {len(definitions_list)} metaobject definitions",
            data=definitions_list
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching metaobject definitions: {str(e)}"
        )


@router.get("/type/{metaobject_type}", response_model=MetaobjectListResponse)
async def get_metaobjects_by_type(
    metaobject_type: str = Path(..., description="Metaobject type"),
    limit: int = Query(20, ge=1, le=250),
    after: Optional[str] = Query(None, description="Cursor for pagination"),
    connector = Depends(get_shopify_connector)
):
    """
    Get metaobjects filtered by type.
    
    - **metaobject_type**: Type of metaobject (e.g., 'designer', 'feature')
    - **limit**: Number per page
    - **after**: Pagination cursor
    """
    try:
        metaobject_service = MetaobjectService(connector)
        result = metaobject_service.get_metaobjects_by_type(metaobject_type, first=limit, after=after)
        
        metaobjects_data = result.get('data', {}).get('metaobjects', {})
        edges = metaobjects_data.get('edges', [])
        metaobjects = [edge['node'] for edge in edges]
        
        pagination_info = metaobjects_data.get('pageInfo', {})
        
        return MetaobjectListResponse(
            success=True,
            message=f"Retrieved {len(metaobjects)} metaobjects of type '{metaobject_type}'",
            metaobjects={metaobject_type: metaobjects},
            pagination={
                "has_next_page": pagination_info.get('hasNextPage', False),
                "end_cursor": pagination_info.get('endCursor')
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching metaobjects of type {metaobject_type}: {str(e)}"
        )


@router.get("/{metaobject_id}", response_model=MetaobjectResponse)
async def get_metaobject_by_id(
    metaobject_id: str = Path(..., description="Metaobject ID"),
    connector = Depends(get_shopify_connector)
):
    """
    Get single metaobject by ID.
    
    - **metaobject_id**: Metaobject ID (with gid prefix)
    """
    try:
        metaobject_service = MetaobjectService(connector)
        result = metaobject_service.get_metaobject_by_id(metaobject_id)
        
        metaobject = result.get('data', {}).get('metaobject')
        
        if not metaobject:
            return MetaobjectResponse(
                success=False,
                message=f"Metaobject {metaobject_id} not found",
                error="Metaobject does not exist"
            )
        
        return MetaobjectResponse(
            success=True,
            message=f"Retrieved metaobject {metaobject_id}",
            metaobjects=[metaobject]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching metaobject {metaobject_id}: {str(e)}"
        )


@router.post("/definitions", response_model=StandardResponse)
async def create_metaobject_definition(
    definition_data: MetaobjectDefinitionRequest = None,
    connector = Depends(get_shopify_connector)
):
    """
    Create a new metaobject definition (schema/type).
    
    - **type**: Metaobject type identifier
    - **name**: Display name
    - **fieldDefinitions**: List of field definitions
    """
    try:
        metaobject_service = MetaobjectService(connector)
        
        definition = {
            "type": definition_data.type,
            "name": definition_data.name,
            "fieldDefinitions": definition_data.field_definitions
        }
        
        result = metaobject_service.create_metaobject_definition(definition)
        
        if 'errors' in result or result.get('data', {}).get('metaobjectDefinitionCreate', {}).get('userErrors'):
            errors = result.get('errors', []) + result.get('data', {}).get('metaobjectDefinitionCreate', {}).get('userErrors', [])
            return StandardResponse(
                success=False,
                message="Failed to create metaobject definition",
                error=str(errors)
            )
        
        created_def = result['data']['metaobjectDefinitionCreate']['metaobjectDefinition']
        
        return StandardResponse(
            success=True,
            message=f"Metaobject definition '{definition_data.type}' created successfully",
            data=created_def
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating metaobject definition: {str(e)}"
        )


@router.post("/", response_model=MetaobjectResponse)
async def create_metaobject(
    metaobject_data: MetaobjectCreateRequest = None,
    connector = Depends(get_shopify_connector)
):
    """
    Create a new metaobject entry.
    
    - **type**: Metaobject type (must match existing definition)
    - **fields**: List of field key-value pairs
    - **handle**: Optional custom handle
    """
    try:
        metaobject_service = MetaobjectService(connector)
        
        result = metaobject_service.create_metaobject(
            metaobject_type=metaobject_data.type,
            fields=metaobject_data.fields,
            handle=metaobject_data.handle
        )
        
        if 'errors' in result or result.get('data', {}).get('metaobjectCreate', {}).get('userErrors'):
            errors = result.get('errors', []) + result.get('data', {}).get('metaobjectCreate', {}).get('userErrors', [])
            return MetaobjectResponse(
                success=False,
                message="Failed to create metaobject",
                error=str(errors)
            )
        
        created_metaobject = result['data']['metaobjectCreate']['metaobject']
        
        return MetaobjectResponse(
            success=True,
            message=f"Metaobject created with ID: {created_metaobject['id']}",
            metaobjects=[created_metaobject]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating metaobject: {str(e)}"
        )


@router.put("/{metaobject_id}", response_model=MetaobjectResponse)
async def update_metaobject(
    metaobject_id: str = Path(..., description="Metaobject ID"),
    metaobject_data: MetaobjectUpdateRequest = None,
    connector = Depends(get_shopify_connector)
):
    """
    Update an existing metaobject.
    
    - **metaobject_id**: Metaobject ID
    - **fields**: Updated fields
    """
    try:
        metaobject_service = MetaobjectService(connector)
        
        result = metaobject_service.update_metaobject(metaobject_id, metaobject_data.fields)
        
        if 'errors' in result or result.get('data', {}).get('metaobjectUpdate', {}).get('userErrors'):
            errors = result.get('errors', []) + result.get('data', {}).get('metaobjectUpdate', {}).get('userErrors', [])
            return MetaobjectResponse(
                success=False,
                message="Failed to update metaobject",
                error=str(errors)
            )
        
        updated_metaobject = result['data']['metaobjectUpdate']['metaobject']
        
        return MetaobjectResponse(
            success=True,
            message=f"Metaobject {metaobject_id} updated successfully",
            metaobjects=[updated_metaobject]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating metaobject {metaobject_id}: {str(e)}"
        )


@router.delete("/{metaobject_id}", response_model=StandardResponse)
async def delete_metaobject(
    metaobject_id: str = Path(..., description="Metaobject ID"),
    connector = Depends(get_shopify_connector)
):
    """
    Delete a metaobject.
    
    - **metaobject_id**: Metaobject ID to delete
    """
    try:
        metaobject_service = MetaobjectService(connector)
        result = metaobject_service.delete_metaobject(metaobject_id)
        
        if 'errors' in result or result.get('data', {}).get('metaobjectDelete', {}).get('userErrors'):
            errors = result.get('errors', []) + result.get('data', {}).get('metaobjectDelete', {}).get('userErrors', [])
            return StandardResponse(
                success=False,
                message="Failed to delete metaobject",
                error=str(errors)
            )
        
        deleted_id = result['data']['metaobjectDelete']['deletedId']
        
        return StandardResponse(
            success=True,
            message=f"Metaobject {deleted_id} deleted successfully"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting metaobject {metaobject_id}: {str(e)}"
        )