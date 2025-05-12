import os
from pydantic_settings import BaseSettings
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
    ACCESS_TOKEN: str = os.getenv("ACCESS_TOKEN")
    REFRESH_TOKEN: str = os.getenv("REFRESH_TOKEN")
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET")  # For verifying webhook calls
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "3"))

settings = Settings()