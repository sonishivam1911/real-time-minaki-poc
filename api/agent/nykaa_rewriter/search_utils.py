import os
import json
import re
from typing import List, Dict, Any, Optional
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_groq import ChatGroq
from ..output_parser import ActionParser
from .config import SEARCH_CONFIG
from .search_term_prompt import create_search_term_prompt


# Initialize Groq LLM (same as product_writer)
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0.7,
    api_key=os.getenv("GROQ_API_KEY"),
)


# Initialize DuckDuckGo search tool (singleton pattern for efficiency)
_search_tool = None

def _get_search_tool():
    """Get or initialize the DuckDuckGo search tool"""
    global _search_tool
    if _search_tool is None:
        _search_tool = DuckDuckGoSearchRun()
    return _search_tool


def generate_search_terms(
    product_type: str,
    material: str,
    occasion: Optional[str] = None,
    price: Optional[float] = None,
) -> List[str]:
    """
    Generate search terms using AI/LLM
    
    Args:
        product_type: Type of jewelry (Necklace, Choker, etc.)
        material: Material (Kundan, Polki, Gold, etc.)
        occasion: Occasion if applicable (Wedding, Festive, etc.)
        price: Product price (used to determine search strategy)
    
    Returns:
        List of 3-5 AI-generated search query strings
    """
    
    try:
        # Create prompt for search term generation
        prompt = create_search_term_prompt(product_type, material, occasion, price)
        
        # Call LLM with global instance
        messages = prompt.format_messages(
            product_type=product_type,
            material=material,
            occasion=occasion or "General",
            price=price or 5000
        )
        response = llm.invoke(messages)
        response_text = response.content.strip()
        
        # Parse JSON response - expect simple array format
        try:
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text.replace("```json", "").replace("```", "").strip()
            elif response_text.startswith("```"):
                response_text = response_text.replace("```", "").strip()
            
            # Parse JSON
            parsed = json.loads(response_text)
            
            # Handle different response formats
            if isinstance(parsed, list):
                # Direct array format (preferred)
                search_terms = parsed
            elif isinstance(parsed, dict):
                # Handle action/action_input format for backwards compatibility
                if "action" in parsed and "action_input" in parsed:
                    search_terms = parsed["action_input"].get("search_terms", [])
                elif "search_terms" in parsed:
                    search_terms = parsed["search_terms"]
                else:
                    # Fallback: use the dict values if they look like search terms
                    search_terms = []
                    for key, value in parsed.items():
                        if isinstance(value, list):
                            search_terms = value
                            break
            else:
                # Unexpected format
                search_terms = []
                
            if isinstance(search_terms, list) and search_terms:
                # Validate and clean terms
                search_terms = [str(t).strip() for t in search_terms if t and str(t).strip()]
                return search_terms[:5]  # Return max 5 terms
                    
        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            print(f"⚠️ JSON parse error: {e}")
            print(f"⚠️ Response text: {response_text[:200]}...")  # Show first 200 chars for debugging
            pass
        
        # Fallback: extract terms from text - try to find array-like patterns first
        try:
            # Look for array pattern in the response
            array_match = re.search(r'\[(.*?)\]', response_text, re.DOTALL)
            if array_match:
                array_content = array_match.group(1)
                # Split by commas and clean up
                terms = [term.strip().strip('"\'') for term in array_content.split(',')]
                terms = [term for term in terms if term and len(term) > 3]  # Filter out short/empty terms
                if terms:
                    return terms[:5]
        except Exception as e:
            print(f"⚠️ Array extraction error: {e}")
        
        # Last resort fallback: extract terms from text lines
        terms = response_text.split('\n')
        clean_terms = []
        for term in terms:
            # Clean up the term
            cleaned = term.strip().strip('[]"\'- *•')
            # Skip empty, very short, or non-descriptive terms
            if cleaned and len(cleaned) > 5 and not cleaned.lower().startswith(('note:', 'example:', 'format:')):
                clean_terms.append(cleaned)
        
        return clean_terms[:5] if clean_terms else []
        
    except Exception as e:
        print(f"❌ AI search generation error: {e}")
        # Fallback to rule-based generation
        return _generate_search_terms_fallback(product_type, material, occasion, price)


def _generate_search_terms_fallback(
    product_type: str,
    material: str,
    occasion: Optional[str] = None,
    price: Optional[float] = None,
) -> List[str]:
    """
    Fallback rule-based search term generation when AI is unavailable
    """
    
    search_terms = []
    
    # Base term: product + material
    base = f"{material} {product_type}"
    search_terms.append(base)
    
    # With occasion if provided
    if occasion:
        search_terms.append(f"{material} {product_type} {occasion}")
        search_terms.append(f"{occasion} {product_type} Indian jewelry")
    
    # Indian jewelry context
    search_terms.append(f"{material} Indian {product_type}")
    
    # Price-aware search
    if price and price >= 10000:
        search_terms.append(f"luxury {material} {product_type} wedding")
    else:
        search_terms.append(f"traditional {material} jewelry")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_terms = []
    for term in search_terms:
        term_lower = term.lower()
        if term_lower not in seen:
            seen.add(term_lower)
            unique_terms.append(term)
    
    return unique_terms[:5]
_search_tool = None

def _get_search_tool():
    """Get or initialize the DuckDuckGo search tool"""
    global _search_tool
    if _search_tool is None:
        _search_tool = DuckDuckGoSearchRun()
    return _search_tool


def search_duckduckgo(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Search DuckDuckGo using LangChain's built-in tool and return structured results
    
    Args:
        query: Search query string
        max_results: Maximum results to return (default 5)
    
    Returns:
        List of search result dicts with 'title', 'url', 'snippet'
    """
    
    try:
        # Get the search tool
        search_tool = _get_search_tool()
        
        # Execute search - DuckDuckGoSearchRun returns raw text results
        raw_results = search_tool.run(query)
        
        # Parse the raw text results into structured format
        results = _parse_langchain_search_results(raw_results)
        
        if not results:
            print(f"⚠️ No results for query: {query}")
        
        return results[:max_results]
        
    except Exception as e:
        print(f"❌ Search error for query '{query}': {e}")
        return []


def _parse_langchain_search_results(raw_results: str) -> List[Dict[str, str]]:
    """
    Parse raw text results from LangChain's DuckDuckGoSearchRun
    
    LangChain returns results in format:
    [snippet1] URL1
    [snippet2] URL2
    etc.
    
    Args:
        raw_results: Raw text string from DuckDuckGoSearchRun
    
    Returns:
        List of structured result dicts
    """
    
    results = []
    
    if not raw_results or not raw_results.strip():
        return results
    
    try:
        # Split by lines and parse each result
        lines = raw_results.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try to extract snippet and URL
            # Format is typically: [snippet text] followed by URL
            # or: URL - snippet
            
            # Try to find URL in the line
            import re
            url_pattern = r'https?://[^\s]+'
            url_match = re.search(url_pattern, line)
            
            if url_match:
                url = url_match.group(0).strip()
                # Get snippet as the text before or after URL
                snippet = line.replace(url, "").strip()
                # Remove common delimiters
                snippet = snippet.strip('[]- ').strip()
                
                results.append({
                    "title": snippet[:100] if snippet else url.split('/')[2],  # Use domain as title if no snippet
                    "url": url,
                    "snippet": snippet[:200] if snippet else ""  # Truncate snippet
                })
        
    except Exception as e:
        print(f"⚠️ Error parsing search results: {e}")
    
    return results


def fetch_search_context(
    product_type: str,
    material: str,
    occasion: Optional[str] = None,
    price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Generate search terms and fetch results for product context
    
    Args:
        product_type: Type of jewelry
        material: Material specification
        occasion: Occasion if applicable
        price: Product price for search optimization
    
    Returns:
        Dictionary with search_terms and search_results
    """
    
    print(f"🔍 Fetching search context for {material} {product_type}")
    
    # Generate search terms
    search_terms = generate_search_terms(product_type, material, occasion, price)
    print(f"   Generated terms: {search_terms}")
    
    # Fetch results for each term
    all_results = []
    for i, term in enumerate(search_terms[:3]):  # Limit to 3 searches to avoid overload
        print(f"   Searching ({i+1}/3): {term}")
        results = search_duckduckgo(term, max_results=2)
        all_results.extend(results)
    
    # Remove duplicates by URL
    unique_results = []
    seen_urls = set()
    for result in all_results:
        url = result.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(result)
    
    return {
        "search_terms": search_terms,
        "search_results": unique_results[:5],  # Max 5 results
        "search_results_count": len(unique_results),
    }


def format_search_results_as_action(search_results: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Format search results in action/action_input format
    
    Compatible with LangChain tool calling pattern
    
    Args:
        search_results: List of search result dicts with 'title', 'url', 'snippet'
    
    Returns:
        Dictionary in action/action_input format
    """
    
    formatted_results = []
    
    for result in search_results:
        formatted_results.append({
            "title": result.get("title", "").strip(),
            "url": result.get("url", "").strip(),
            "snippet": result.get("snippet", "").strip(),
            "source": "duckduckgo"
        })
    
    return {
        "action": "web_search_results",
        "action_input": {
            "results": formatted_results,
            "total_results": len(formatted_results)
        }
    }


def format_search_context_for_llm(search_context: Dict[str, Any]) -> str:
    """
    Format search context into readable text for LLM prompt
    
    Args:
        search_context: Output from fetch_search_context()
    
    Returns:
        Formatted text for prompt inclusion
    """
    
    results = search_context.get("search_results", [])
    
    if not results:
        return "No search results found. Use product metadata and standard conventions."
    
    text = "Reference Information from Web Search:\n"
    
    for i, result in enumerate(results, 1):
        title = result.get("title", "").strip()
        url = result.get("url", "").strip()
        snippet = result.get("snippet", "").strip()
        
        text += f"\n{i}. {title}"
        if snippet:
            text += f"\n   {snippet[:150]}..."
        if url:
            text += f"\n   {url}"
    
    return text
