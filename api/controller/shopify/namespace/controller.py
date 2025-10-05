from fastapi import APIRouter, Query, Path, HTTPException, Depends
from typing import Optional

import datetime
from core.database import db
from services.shopify_service import ShopifyGraphQLConnector
from utils.schema.shopify_schema import (
    StandardResponse,
    NamespaceResponse,
    NamespaceKeysResponse,
    AllNamespacesKeysResponse
)
from controller.shopify.dependencies import get_shopify_connector

router = APIRouter()


@router.post("/sync", response_model=StandardResponse)
async def sync_namespace_cache(
    max_products: Optional[int] = Query(None, description="Maximum products to analyze"),
    connector: ShopifyGraphQLConnector = Depends(get_shopify_connector)
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
    connector: ShopifyGraphQLConnector = Depends(get_shopify_connector)
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
            unique_keys_count=result['unique_keys_count'],
            total_metafields=result['total_metafields'],
            products_scanned=result['products_scanned'],
            keys=result['keys'],
            analysis_timestamp=result['analysis_timestamp']
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing namespace '{namespace}': {str(e)}"
        )

@router.get("/keys", response_model=AllNamespacesKeysResponse)
async def get_all_namespaces_with_keys(
    max_products: Optional[int] = Query(200, ge=50, le=2000, description="Maximum products to scan"),
    use_cache: bool = Query(False, description="Use cached data (faster but may be outdated)"),
    connector: ShopifyGraphQLConnector = Depends(get_shopify_connector)
):
    """
    Get all namespaces with their unique keys.
    
    - **max_products**: Limit products to scan (50-2000, default 200)
    - **use_cache**: Use cached analysis if available
    
    Returns comprehensive analysis of all namespaces and their keys:
    - Complete namespace inventory
    - Key counts per namespace
    - Field type analysis
    """
    try:
        # Check cache first if requested
        if use_cache:
            try:
                cached_data = db.execute_query(
                    "SELECT * FROM namespace_keys_analysis ORDER BY created_at DESC LIMIT 1",
                    return_data=True
                )
                
                if not cached_data.empty:
                    import json
                    cached_result = json.loads(cached_data.iloc[0]['analysis_data'])
                    
                    return AllNamespacesKeysResponse(
                        success=True,
                        message=f"Retrieved cached analysis with {cached_result['summary']['total_namespaces']} namespaces",
                        summary=cached_result['summary'],
                        namespaces=cached_result['namespaces']
                    )
            except Exception as e:
                print(f"Cache lookup failed: {e}, performing fresh analysis")
        
        # Fresh analysis
        result = connector.get_all_namespaces_with_keys(max_products)
        
        # Cache the results
        try:
            import json
            import pandas as pd
            
            cache_df = pd.DataFrame([{
                'analysis_data': json.dumps(result),
                'created_at': datetime.datetime.now(),
                'products_scanned': result['summary']['products_scanned'],
                'namespaces_found': result['summary']['total_namespaces']
            }])
            
            db.create_table('namespace_keys_analysis', cache_df)
        except Exception as e:
            print(f"Failed to cache namespace keys analysis: {e}")
        
        return AllNamespacesKeysResponse(
            success=True,
            message=f"Analyzed {result['summary']['total_namespaces']} namespaces from {result['summary']['products_scanned']} products",
            summary=result['summary'],
            namespaces=result['namespaces']
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing all namespaces: {str(e)}"
        )

# Enhanced namespaces endpoint (update the existing one)
@router.get("/", response_model=NamespaceResponse)
async def get_all_namespaces(
    use_cache: bool = Query(True, description="Use cached namespace data"),
    include_keys: bool = Query(False, description="Include key counts for each namespace"),
    connector: ShopifyGraphQLConnector = Depends(get_shopify_connector)
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
  