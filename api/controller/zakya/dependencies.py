from core.config import settings

async def get_zakya_connection():
    """Get zakya connection object from settings."""
    return settings.get_zakya_connection()