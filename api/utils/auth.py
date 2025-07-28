import requests
from core.config import settings

def refresh_access_token():
    """
    Refresh the Zakya API access token.
    """
    try:
        payload = {
            "client_id": settings.CLIENT_ID,
            "client_secret": settings.CLIENT_SECRET,
            "refresh_token": settings.REFRESH_TOKEN,
            "grant_type": "refresh_token",
            "redirect_uri": settings.REDIRECT_URI
        }
        
        response = requests.post(settings.TOKEN_URL, data=payload)
        response.raise_for_status()
        token_data = response.json()
        
        if 'access_token' in token_data:
            # Update the access token in environment
            settings.ACCESS_TOKEN = token_data['access_token']
            return token_data['access_token']
        else:
            raise ValueError("No access token in response")
            
    except Exception as e:
        print(f"Error refreshing access token: {e}")
        return None

def get_auth_headers():
    """
    Get authentication headers for Zakya API requests.
    """
    return {
        "Authorization": f"Zoho-oauthtoken {settings.ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }