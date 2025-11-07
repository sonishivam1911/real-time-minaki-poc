import os
import requests
import pandas as pd
from sqlalchemy import create_engine
from fastapi import HTTPException
from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    API_DOMAIN: str = os.getenv("API_DOMAIN", "https://api.zakya.in/")
    CLIENT_ID: str = os.getenv("ZAKYA_CLIENT_ID")
    CLIENT_SECRET: str = os.getenv("ZAKYA_CLIENT_SECRET")
    REDIRECT_URI: str = os.getenv("ZAKYA_REDIRECT_URI")
    TOKEN_URL: str = os.getenv("TOKEN_URL", "https://accounts.zoho.in/oauth/v2/token")
    POSTGRES_URI: str = os.getenv("POSTGRES_SESSION_POOL_URI")
    ORGANIZATION_ID: str = os.getenv("ORGANIZATION_ID")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "3"))
    ENV: str = os.getenv("env", "dev")
    SHOPIFY_API_KEY : str = os.getenv("SHOPIFY_API_KEY")
    SHOPIFY_API_SECRET : str = os.getenv("SHOPIFY_API_SECRET")
    SHOPIFY_SHOP_URL : str = os.getenv("SHOPIFY_SHOP_URL")
    SHOPIFY_API_VERSION : str = os.getenv("SHOPIFY_API_VERSION")
    SHOPIFY_ACCESS_TOKEN : str = os.getenv("SHOPIFY_ACCESS_TOKEN")
    # Initialize tokens as class attributes so they persist
    ACCESS_TOKEN: Optional[str] = None
    REFRESH_TOKEN: Optional[str] = None
    
    def get_access_token(self):
        """
        Get the current access token or refresh it if needed.
        """
        try:
            # Create engine only when needed, not at class initialization
            print(f"Postgres URI : {self.POSTGRES_URI}")
            engine = create_engine(self.POSTGRES_URI)
            
            # Query for zakya_auth table
            query = f"""
                SELECT * FROM zakya_auth 
                WHERE env = '{self.ENV}'
            """
            print(f"[DEBUG] Query is : {query}")
            # Read token data from database
            zakya_auth_df = pd.read_sql(query, engine)
            print(f"[DEBUG] Data is : {zakya_auth_df}")
            
            if zakya_auth_df.empty:
                print("No authentication data found in database")
                return None
                
            # Get refresh token from database
            self.REFRESH_TOKEN = zakya_auth_df["refresh_token"].iloc[0]
            
            # Use refresh token to get a new access token
            refresh_token_data = self._get_token_from_refresh()
            
            if 'access_token' not in refresh_token_data:
                print("Failed to get access token from refresh token")
                return None
                
            # Store the new access token as class attribute
            self.ACCESS_TOKEN = refresh_token_data['access_token']
            
            return self.ACCESS_TOKEN
            
        except Exception as e:
            print(f"Error getting access token: {e}")
            return None
    
    def _get_token_from_refresh(self):
        """Get a new access token using the refresh token."""
        if not self.REFRESH_TOKEN:
            return {}
            
        payload = {
            "client_id": self.CLIENT_ID,
            "client_secret": self.CLIENT_SECRET,
            "refresh_token": self.REFRESH_TOKEN,
            "grant_type": "refresh_token",
            "redirect_uri": self.REDIRECT_URI
        }
        
        try:
            response = requests.post(self.TOKEN_URL, data=payload)
            response.raise_for_status()
            print(f"[DEBUG] Response after hitting function _get_token_from_refresh : {response.json()}")
            return response.json()
        except Exception as e:
            print(f"Error refreshing token: {e}")
            return {}
    
    def get_auth_headers(self) -> dict:
        """
        Get authentication headers for Zakya API requests.
        Returns headers with current access token.
        """
        try:
            access_token = self.get_access_token()
            if not access_token:
                print("Warning: No access token available for auth headers")
                return {
                    "Content-Type": "application/json"
                }
            
            return {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
        except Exception as e:
            print(f"Error getting auth headers: {e}")
            return {
                "Content-Type": "application/json"
            }
    
    def refresh_access_token(self) -> Optional[str]:
        """
        Force refresh the access token and return it.
        """
        try:
            refresh_data = self._get_token_from_refresh()
            if 'access_token' in refresh_data:
                self.ACCESS_TOKEN = refresh_data['access_token']
                return self.ACCESS_TOKEN
            return None
        except Exception as e:
            print(f"Error forcing token refresh: {e}")
            return None
        
    def get_zakya_connection(self) -> dict:
        """Create zakya connection object."""
        try:
            access_token = self.get_access_token()
            
            if not access_token:
                raise HTTPException(
                    status_code=500, 
                    detail="Failed to get access token from Zakya"
                )
            
            return {
                'base_url': self.API_DOMAIN,
                'access_token': access_token,
                'organization_id': self.ORGANIZATION_ID
            }
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error setting up Zakya connection: {str(e)}"
            )        

settings = Settings()