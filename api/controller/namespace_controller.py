from fastapi import APIRouter, Depends, HTTPException, Query, Path
from functools import lru_cache
from typing import Optional
import datetime

from services.shopify_service import ShopifyGraphQLConnector
from utils.schema.shopify_schema import (
    StandardResponse, NamespaceResponse, 
    AllNamespacesKeysResponse, NamespaceKeysResponse
)
from core.database import db

router = APIRouter()

# Dependency to get Shopify connector
@lru_cache()
def get_shopify_connector():
    """Get cached Shopify connector instance."""
    return ShopifyGraphQLConnector()

def get_connector():
    """Dependency for FastAPI to inject Shopify connector."""
    return get_shopify_connector()

@router.get("", response_model=NamespaceResponse)
async def get_all_namespaces(
    use_cache: bool = Query(True, description="Use cached namespace data"),
    include_keys: bool = Query(False, description="Include key counts for each namespace"),
    connector: ShopifyGraphQLConnector = Depends(get_connector)
):
    """
    Get all unique metafield namespaces across the store.
    
    - **use_cache**: Whether to use cached data (faster) or fresh scan
    - **include_keys**: Include key counts (slower but more detailed)
    """
    try:
        if include_keys:
            # Get detailed namespace-keys analysis
            detailed_result = connector.get_all_namespaces_with_keys(max_products=100)
            
            namespaces_with_counts = []
            for namespace, data in detailed_result['namespaces'].items():
                namespaces_with_counts.append({
                    'namespace': namespace,
                    'unique_keys_count': data['unique_keys_count']
                })
            
            return NamespaceResponse(
                success=True,
                message=f"Retrieved {len(namespaces_with_counts)} namespaces with key counts",
                namespaces=[item['namespace'] for item in namespaces_with_counts],
                count=len(namespaces_with_counts),
                data={'namespace_details': namespaces_with_counts}
            )
        
        # Original simple namespace list
        if use_cache:
            try:
                cached_namespaces = db.execute_query(
                    "SELECT DISTINCT namespace FROM cached_namespaces ORDER BY namespace",
                    return_data=True
                )
                
                if not cached_namespaces.empty:
                    namespaces_list = cached_namespaces['namespace'].tolist()
                    return NamespaceResponse(
                        success=True,
                        message=f"Retrieved {len(namespaces_list)} cached namespaces",
                        namespaces=namespaces_list,
                        count=len(namespaces_list)
                    )
            except Exception as e:
                print(f"Cache lookup failed: {e}, falling back to fresh scan")
        
        # Fresh scan from Shopify
        namespaces = connector.get_all_unique_namespaces(use_cache=False)
        
        # Cache the results
        try:
            if namespaces:
                import pandas as pd
                namespace_df = pd.DataFrame({
                    'namespace': namespaces,
                    'discovered_at': [datetime.datetime.now()] * len(namespaces)
                })
                db.create_table('cached_namespaces', namespace_df)
        except Exception as e:
            print(f"Failed to cache namespaces: {e}")
        
        return NamespaceResponse(
            success=True,
            message=f"Retrieved {len(namespaces)} namespaces",
            namespaces=namespaces,
            count=len(namespaces)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching namespaces: {str(e)}"
        )

@router.get("/products/{product_id}", response_model=NamespaceResponse)
async def get_product_namespaces(
    product_id: str = Path(..., description="Shopify product ID"),
    connector: ShopifyGraphQLConnector = Depends(get_connector)
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

@router.post("/sync", response_model=StandardResponse)
async def sync_namespace_cache(
    max_products: Optional[int] = Query(None, description="Maximum products to analyze"),
    connector: ShopifyGraphQLConnector = Depends(get_connector)
):
    """
    Background job to refresh namespace cache from Shopify.
    
    - **max_products**: Limit analysis to N products (None = all products)
    """
    try:
        # Run namespace analysis
        analysis = connector.analyze_metafield_namespaces_for_db(max_products=max_products)
        
        # Store in database
        import pandas as pd
        
        # Store namespace summary
        summary_df = pd.DataFrame([analysis['summary']])
        db.create_table('namespace_analysis_summary', summary_df)
        
        # Store detailed namespace data
        namespace_rows = []
        for namespace, data in analysis['namespaces'].items():
            namespace_rows.append(data)
        
        if namespace_rows:
            namespace_df = pd.DataFrame(namespace_rows)
            db.create_table('namespace_analysis_detail', namespace_df)
            
            # Update simple namespace cache
            simple_namespaces = pd.DataFrame({
                'namespace': list(analysis['namespaces'].keys()),
                'discovered_at': [datetime.datetime.now()] * len(analysis['namespaces'])
            })
            db.create_table('cached_namespaces', simple_namespaces)
        
        return StandardResponse(
            success=True,
            message=f"Namespace sync completed. Analyzed {analysis['summary']['total_products_analyzed']} products, found {analysis['summary']['unique_namespaces']} namespaces",
            data=analysis['summary']
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error syncing namespace cache: {str(e)}"
        )

@router.get("/{namespace}/keys", response_model=NamespaceKeysResponse)
async def get_namespace_keys(
    namespace: str = Path(..., description="Namespace to analyze"),
    max_products: Optional[int] = Query(100, ge=10, le=1000, description="Maximum products to scan"),
    connector: ShopifyGraphQLConnector = Depends(get_connector)
):
    """
    Get all unique keys for a specific namespace.
    
    - **namespace**: Target namespace (e.g., 'reviews', 'seo', 'custom')
    - **max_products**: Limit products to scan (10-1000, default 100)
    
    Returns detailed analysis of all keys within the namespace including:
    - Key names and usage counts
    - Sample values and field types
    - Products that use each key
    """
    try:
        result = connector.get_namespace_keys(namespace, max_products)
        
        return NamespaceKeysResponse(
            success=True,
            message=f"Found {result['unique_keys_count']} unique keys in namespace '{namespace}'",
            namespace=result['namespace'],
            unique_keys_count=result['unique_keys_