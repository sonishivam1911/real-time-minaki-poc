import requests
import time
from typing import Dict, Any, Optional
from core.config import settings

class BaseShopifyConnector:
    """Base connector handling GraphQL communication with Shopify"""
    
    def __init__(self):
        self.shop_url = settings.SHOPIFY_SHOP_URL
        self.api_version = settings.SHOPIFY_API_VERSION
        self.access_token = settings.SHOPIFY_ACCESS_TOKEN
        self.graphql_endpoint = f"https://{self.shop_url}/admin/api/{self.api_version}/graphql.json"
        
        self.headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': self.access_token
        }
    
    def execute_query(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a GraphQL query against Shopify's API with rate limiting."""
        try:
            payload = {'query': query}
            if variables:
                payload['variables'] = variables
            
            response = requests.post(
                self.graphql_endpoint,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 2))
                print(f"Rate limited, waiting {retry_after} seconds...")
                time.sleep(retry_after)
                return self.execute_query(query, variables)
            
            response.raise_for_status()
            result = response.json()
            
            if 'errors' in result:
                raise Exception(f"GraphQL errors: {result['errors']}")
            
            return result
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"HTTP request failed: {str(e)}")
        except Exception as e:
            raise Exception(f"GraphQL query execution failed: {str(e)}")
    
    def execute_mutation(self, mutation: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a GraphQL mutation (alias for execute_query for clarity)."""
        return self.execute_query(mutation, variables)