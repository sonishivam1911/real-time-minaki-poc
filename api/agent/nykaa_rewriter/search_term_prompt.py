from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate


SEARCH_TERM_GENERATION_PROMPT = """
You are an expert jewelry search specialist. Generate optimized search queries to find reference information for jewelry products.

---

## INPUT DATA:

**Product Details:**
- Product Type: {product_type}
- Material: {material}
- Occasion: {occasion}
- Price: ₹{price}

---

## TASK:

Generate 3-5 optimized, specific search queries that will find the best reference information for this jewelry product.

**Requirements:**
1. Generate specific, targeted search queries
2. Include material + product type combinations
3. Consider occasion and price point in searches
4. Make searches detailed for luxury items (>₹10,000), general for others
5. Focus on design inspiration, craftsmanship, and styling references
6. Return ONLY a JSON array of strings, no explanation

**Examples:**
- For Kundan Wedding Necklace: ["kundan polki wedding necklace designs", "traditional indian wedding jewelry kundan", "bridal kundan necklace styles"]
- For Crystal Casual Set: ["crystal jewelry everyday wear", "american diamond casual jewelry", "contemporary crystal necklace designs"]

---

## RESPONSE FORMAT:

Return ONLY a simple JSON array of search terms (no markdown, no backticks, no action wrapper):
["search term 1", "search term 2", "search term 3"]

**JSON Formatting Rules:**
- Return a simple array of strings
- All string values in double quotes
- No trailing commas
- ONLY return the JSON array - no markdown blocks, no extra text
- Maximum 5 search terms

Generate the search queries now:
"""


search_term_prompt = ChatPromptTemplate.from_messages([
    HumanMessagePromptTemplate.from_template(SEARCH_TERM_GENERATION_PROMPT),
])


def create_search_term_prompt(product_type: str, material: str, occasion: str, price: float):
    """
    Create search term generation prompt with product details
    
    Args:
        product_type: Type of jewelry (Necklace, Choker, etc.)
        material: Material (Kundan, Crystal, AD, etc.)
        occasion: Occasion (Wedding, Casual, Festive, etc.)
        price: Product price in INR
    
    Returns:
        Formatted prompt ready for LLM
    """
    
    formatted_prompt = SEARCH_TERM_GENERATION_PROMPT.format(
        product_type=product_type,
        material=material,
        occasion=occasion or "General",
        price=price or 5000
    )
    
    return ChatPromptTemplate.from_messages([
        HumanMessagePromptTemplate.from_template(formatted_prompt),
    ])
