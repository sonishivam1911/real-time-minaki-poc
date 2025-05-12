import requests
from core.config import settings
from utils.auth import get_auth_headers, refresh_access_token

class ZakyaService:
    @staticmethod
    async def fetch_object_by_id(endpoint, object_id):
        """
        Fetch a specific object from Zakya API.
        """
        url = f"{settings.API_DOMAIN}inventory/v1/{endpoint}/{object_id}"
        
        headers = get_auth_headers()
        params = {"organization_id": settings.ORGANIZATION_ID}
        
        try:
            response = requests.get(url, headers=headers, params=params)
            
            # If token expired, refresh and try again
            if response.status_code == 401:
                new_token = refresh_access_token()
                if new_token:
                    headers = get_auth_headers()
                    response = requests.get(url, headers=headers, params=params)
                
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            print(f"Error fetching {endpoint}/{object_id}: {e}")
            return None

zakya_service = ZakyaService()