from functools import lru_cache
from services.shopify_service import ShopifyGraphQLConnector
from services.shopify.product import ShopifyProductService

@lru_cache()
def get_shopify_connector():
    """Get cached Shopify connector instance."""
    return ShopifyGraphQLConnector()


@lru_cache()
def get_shopify_product_service():
    """Get cached Shopify Product Service instance."""
    return ShopifyProductService()
