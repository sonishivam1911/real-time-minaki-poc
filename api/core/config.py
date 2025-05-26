import os
import requests
import pandas as pd
from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

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
    
    # Initialize tokens as class attributes so they persist
    ACCESS_TOKEN: Optional[str] = None
    REFRESH_TOKEN: Optional[str] = None
    
    def get_access_token(self):
        """
        Get the current access token or refresh it if needed.
        
        Returns:
            str: The current valid access token
        """
        try:
            # Create engine for database operations
            engine = create_engine(self.POSTGRES_URI)
            
            # Query for zakya_auth table
            query = f"""
                SELECT * FROM zakya_auth 
                WHERE env = '{self.ENV}'
            """
            
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
                print(f"Failed to get access token from refresh token")
                return None
                
            # Store the new access token as class attribute
            self.ACCESS_TOKEN = refresh_token_data['access_token']
            
        
            return self.ACCESS_TOKEN
            
        except Exception as e:
            print(f"Error getting access token: {e}")
            return None
    
    def _get_token_from_refresh(self):
        """
        Get a new access token using the refresh token.
        
        Returns:
            dict: Token data including access_token
        """
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
    
    def _update_refresh_token_in_db(self, engine):
        """
        Update the refresh token in the database.
        
        Args:
            engine: SQLAlchemy database engine
        """
        try:
            update_query = f"""
                UPDATE zakya_auth 
                SET refresh_token = '{self.REFRESH_TOKEN}' 
                WHERE env = '{self.ENV}'
            """
            
            with engine.connect() as connection:
                connection.execute(text(update_query))
                
        except Exception as e:
            print(f"Error updating refresh token in database: {e}")

    def get_auth_headers(self):
        """
        Get authentication headers for Zakya API requests.
        
        Returns:
            dict: Headers with authorization token
        """
        token = self.get_access_token()
        if not token:
            return {}
            
        return {
            "Authorization": f"Zoho-oauthtoken {token}",
            "Content-Type": "application/json"
        }
    
settings = Settings()