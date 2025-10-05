from functools import lru_cache
from services.shopify_service import ShopifyGraphQLConnector

@lru_cache()
def get_shopify_connector():
    """Get cached Shopify connector instance."""
    return ShopifyGraphQLConnector()