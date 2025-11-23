"""
LLM Configuration
Provides Groq LLM instance with fallback handling
"""

import os
import logging
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("ProductWriter.LLM")


def get_groq_llm(temperature: float = 0.7, max_tokens: int = 2000) -> ChatGroq:
    """
    Get Groq LLM instance with fallback
    
    Args:
        temperature: LLM temperature (default: 0.7)
        max_tokens: Max tokens (default: 2000)
    
    Returns:
        ChatGroq instance
    """
    try:
        logger.info("🤖 Initializing Groq LLM (llama-3.1-8b-instant)...")
        llm = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=temperature,
            max_tokens=max_tokens,
            groq_api_key=os.environ.get("GROQ_API_KEY")
        )
        return llm
        
    except Exception as e:
        logger.error(f"❌ Error initializing LLM: {str(e)}")
        raise


# Default instance for import
llm = get_groq_llm()