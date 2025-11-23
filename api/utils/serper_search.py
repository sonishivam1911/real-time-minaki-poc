import os
import logging
import time
from langchain_community.utilities import GoogleSerperAPIWrapper

logger = logging.getLogger("Serper.Search")


def search_serper(query: str, retry_count: int = 0, max_retries: int = 3) -> str:
    """
    Call Serper API with single query
    Includes retry logic for rate limiting (429) and 403 errors
    
    Args:
        query: Search query string
        retry_count: Current retry attempt (internal use)
        max_retries: Maximum number of retries (default 3)
    
    Returns:
        Raw text results concatenated
    
    Raises:
        ValueError: If SERPER_API_KEY is not set
        Exception: If API call fails after all retries
    """
    api_key = os.getenv("SERPER_API_KEY")
    
    if not api_key:
        logger.error("❌ SERPER_API_KEY not set in environment")
        raise ValueError("SERPER_API_KEY environment variable is not set")
    
    logger.debug(f"Using SERPER_API_KEY: {api_key[:10]}...")
    
    try:
        search = GoogleSerperAPIWrapper(
            serper_api_key=api_key,
            k=10,  # top 10 results
            type="search"  # can be "search", "news", "places"
        )
        
        logger.info(f"🔍 Searching for: {query[:100]}...")
        results = search.results(query)
        
        # Extract organic results text
        text_results = []
        if "organic" in results:
            for result in results["organic"]:
                snippet = result.get("snippet", "")
                if snippet:
                    text_results.append(snippet)
        
        if not text_results:
            logger.warning("⚠️  No organic results found in API response")
            logger.debug(f"Full response: {results}")
            return ""
        
        logger.info(f"✅ Got {len(text_results)} search results")
        return "\n\n".join(text_results)
        
    except Exception as e:
        error_str = str(e).lower()
        
        # Check for rate limiting or permission errors
        if ("403" in str(e) or "forbidden" in error_str or 
            "429" in str(e) or "too many requests" in error_str or
            "quota" in error_str):
            
            if retry_count < max_retries:
                wait_time = (2 ** retry_count) * 5  # Exponential backoff: 5s, 10s, 20s
                logger.warning(f"⚠️  Rate limited/Forbidden (attempt {retry_count + 1}/{max_retries})")
                logger.info(f"   Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                
                return search_serper(query, retry_count + 1, max_retries)
            else:
                logger.error(f"❌ Max retries reached for Serper API")
                raise
        else:
            logger.error(f"❌ Serper API error: {str(e)}", exc_info=True)
            raise