"""
Material Resolver - Metaobject GID to Material Name Resolution
Handles Shopify metaobject service integration with caching
"""

import os
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from services.shopify.metaobject import MetaobjectService

# In-memory cache (replace with Redis in production)
MATERIAL_CACHE: Dict[str, Dict[str, Any]] = {}


def _get_cache_key(gid: str) -> str:
    """Generate cache key from metaobject GID"""
    return hashlib.md5(gid.encode()).hexdigest()


def _is_cache_valid(cached_item: Dict[str, Any]) -> bool:
    """Check if cached item is still valid (24hr TTL)"""
    if not cached_item or "timestamp" not in cached_item:
        return False
    
    cached_time = cached_item["timestamp"]
    ttl_hours = 24
    expiry_time = cached_time + timedelta(hours=ttl_hours)
    
    return datetime.now() < expiry_time


def resolve_material_gid(
    gid: str,
    shopify_connector=None
) -> Optional[str]:
    """
    Resolve Shopify metaobject GID to human-readable material name
    
    Args:
        gid: Metaobject GID (e.g., "gid://shopify/Metaobject/129466106079")
        shopify_connector: Optional Shopify GraphQL connector
    
    Returns:
        Material name (e.g., "Antique Gold Kundan Polki") or None if unresolved
    """
    
    # Clean up GID
    gid = str(gid).strip()
    
    if not gid.startswith("gid://shopify/Metaobject/"):
        print(f"⚠️ Invalid GID format: {gid}")
        return None
    
    # Check cache
    cache_key = _get_cache_key(gid)
    if cache_key in MATERIAL_CACHE:
        cached = MATERIAL_CACHE[cache_key]
        if _is_cache_valid(cached):
            print(f"📋 Cache hit for GID: {gid} → {cached['material']}")
            return cached["material"]
        else:
            print(f"⏰ Cache expired for GID: {gid}")
            del MATERIAL_CACHE[cache_key]
    
    # Try to resolve from Shopify
    if shopify_connector is None:
        print(f"⚠️ No Shopify connector provided, cannot resolve GID: {gid}")
        return None
    
    try:
        metaobject_service = MetaobjectService(shopify_connector)
        result = metaobject_service.get_metaobject_by_id(gid)
        
        metaobject = result.get("data", {}).get("metaobject")
        if not metaobject:
            print(f"❌ Metaobject not found for GID: {gid}")
            return None
        
        # Extract material name from fields
        material_name = _extract_material_from_fields(metaobject.get("fields", []))
        
        if material_name:
            # Cache the result
            MATERIAL_CACHE[cache_key] = {
                "gid": gid,
                "material": material_name,
                "timestamp": datetime.now(),
                "metaobject_id": metaobject.get("id"),
            }
            print(f"✅ Resolved GID {gid} → {material_name}")
            return material_name
        else:
            print(f"⚠️ Could not extract material from metaobject fields: {gid}")
            return None
            
    except Exception as e:
        print(f"💥 Error resolving metaobject {gid}: {e}")
        return None


def _extract_material_from_fields(fields: list) -> Optional[str]:
    """
    Extract human-readable material name from metaobject fields
    
    Looks for fields like:
    - display_name
    - name
    - title
    - material_name
    """
    
    if not fields:
        return None
    
    # Priority order for field keys to extract from
    priority_keys = [
        "display_name",
        "name",
        "title",
        "material_name",
        "label",
        "handle",
    ]
    
    for field in fields:
        key = field.get("key", "").lower()
        value = field.get("value", "").strip()
        
        if key in priority_keys and value:
            print(f"   Found material in field '{key}': {value}")
            return value
    
    # Fallback: concatenate all field values
    values = [f.get("value", "").strip() for f in fields if f.get("value")]
    if values:
        result = " ".join(values)
        print(f"   Using concatenated fields: {result}")
        return result
    
    return None


def batch_resolve_material_gids(
    gids: list,
    shopify_connector=None
) -> Dict[str, Optional[str]]:
    """
    Resolve multiple GIDs at once
    
    Args:
        gids: List of metaobject GIDs
        shopify_connector: Shopify GraphQL connector
    
    Returns:
        Dictionary mapping GID → material name
    """
    
    results = {}
    for gid in gids:
        results[gid] = resolve_material_gid(gid, shopify_connector)
    
    return results


def clear_material_cache():
    """Clear all cached material resolutions"""
    global MATERIAL_CACHE
    MATERIAL_CACHE.clear()
    print("🗑️ Material cache cleared")


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    valid_count = 0
    expired_count = 0
    
    for key, cached in MATERIAL_CACHE.items():
        if _is_cache_valid(cached):
            valid_count += 1
        else:
            expired_count += 1
    
    return {
        "total_cached": len(MATERIAL_CACHE),
        "valid": valid_count,
        "expired": expired_count,
        "cache_size_mb": len(str(MATERIAL_CACHE)) / (1024 * 1024),
    }
