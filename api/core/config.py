import os
import requests
import pandas as pd
from sqlalchemy import create_engine
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
    POSTGRES_URI: str = "postgresql://postgres.xhgaxxwjwtaqijbqkrnj:Wh.ZY*wv9*rA2N5@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
    ORGANIZATION_ID: str = os.getenv("ORGANIZATION_ID")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "3"))
    ENV: str = os.getenv("env", "dev")
    
    # Initialize tokens as class attributes so they persist
    ACCESS_TOKEN: Optional[str] = None
    REFRESH_TOKEN: Optional[str] = None
    
    def get_access_token(self):
        """
        Get the current access token or refresh it if needed.
        """
        try:
            # Create engine only when needed, not at class initialization
            print(f"Postgres URI : postgresql://postgres.xhgaxxwjwtaqijbqkrnj:Wh.ZY*wv9*rA2N5@aws-0-ap-south-1.pooler.supabase.com:6543/postgres")
            engine = create_engine("postgresql://postgres.xhgaxxwjwtaqijbqkrnj:Wh.ZY*wv9*rA2N5@aws-0-ap-south-1.pooler.supabase.com:6543/postgres")
            
            # Query for zakya_auth table
            query = f"""
                SELECT * FROM zakya_auth 
                WHERE env = '{self.ENV}'
            """
            print(f"Query is : {query}")
            # Read token data from database
            zakya_auth_df = pd.read_sql(query, engine)
            
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
            return response.json()
        except Exception as e:
            print(f"Error refreshing token: {e}")
            return {}

settings = Settings()