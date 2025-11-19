"""
Nykaa Rewriter Agent Configuration
Historical Indian Queen Names and Product Constraints
"""

# Historical Indian Queens & Notable Women
# Used as product name prefixes for kundan/polki jewelry
HISTORICAL_QUEENS = [
    # Mughal Empire
    "Mumtaz",
    "Nur Jahan",
    "Jahanara",
    "Roshanara",
    
    # Marathi & Rajasthani
    "Jhansi Rani",
    "Padmavati",
    "Moomal",
    "Samyukta",
    
    # South Indian
    "Priyamvada",
    "Rudrama",
    "Abhinaya",
    "Chandramati",
    
    # Sikh & North Indian
    "Rania",
    "Lakshmi",
    "Rani",
    "Chandi",
    
    # Modern Era Inspirations
    "Durga",
    "Saraswati",
    "Lakshmi",
    "Parvati",
    "Ganga",
    "Sarada",
    "Usha",
    "Damayanti",
    "Ahalya",
    "Sita",
    "Radha",
]

# Price-based naming boldness
# If product price < 10k, use subtle queen names
# If product price >= 10k, use grand queen names
PRICE_THRESHOLDS = {
    "SUBTLE": {
        "min": 0,
        "max": 9999,
        "names": [
            "Priyamvada",
            "Usha",
            "Chandi",
            "Ahalya",
            "Ganga",
            "Sarada",
            "Moomal",
            "Abhinaya",
        ]
    },
    "GRAND": {
        "min": 10000,
        "max": float('inf'),
        "names": HISTORICAL_QUEENS  # All names available
    }
}

# Nykaa Platform Constraints
NYKAA_CONSTRAINTS = {
    "name_max_chars": 100,
    "description_max_chars": 500,
    "name_min_chars": 30,
}

# Product Type Keywords
PRODUCT_TYPES = {
    "Necklace": ["necklace", "pendant necklace", "long necklace"],
    "Necklace Set": ["necklace set", "necklace with earrings"],
    "Choker": ["choker", "choker set"],
    "Earrings": ["earrings", "jhumka", "studs"],
    "Bracelet": ["bracelet", "bangle", "kada"],
    "Ring": ["ring", "finger ring"],
    "Jhumka": ["jhumka", "long earrings"],
}

# Material Keywords
MATERIAL_KEYWORDS = {
    "Kundan": ["kundan", "kundan polki", "kundan stone"],
    "Polki": ["polki", "polki diamond", "uncut diamond"],
    "Pearl": ["pearl", "pearl beads"],
    "Stones": ["stone", "semi-precious", "topaz", "ruby", "emerald"],
    "Gold": ["gold", "antique gold", "rose gold", "18k", "22k"],
}

# Occasion Keywords for Search Context
OCCASION_KEYWORDS = {
    "Wedding": ["wedding", "bridal", "bride", "marriage", "nuptial"],
    "Festive": ["festive", "diwali", "holi", "festival", "celebration"],
    "Party": ["party", "occasion", "event", "evening"],
    "Temple": ["temple", "shrine", "religious", "pooja"],
    "Daily": ["daily", "casual", "everyday", "wear"],
}

# DuckDuckGo Search Configuration
SEARCH_CONFIG = {
    "max_results": 5,
    "timeout": 10,
    "retry_count": 2,
    "cache_ttl_hours": 24,
}

# EAN-13 Generation
EAN_CONFIG = {
    "length": 13,
    "generation_type": "random",  # random, not deterministic
    "max_retries": 10,  # Retry if duplicate found (unlikely with random)
}

# Quality Control Thresholds
QUALITY_THRESHOLDS = {
    "name_quality_min": 0.60,
    "description_quality_min": 0.60,
    "manual_review_triggers": [
        "search_results_empty",
        "material_unresolved",
        "less_than_2_images",
        "price_outlier",
    ]
}

# Metaobject Cache Configuration
METAOBJECT_CACHE = {
    "enabled": True,
    "ttl_hours": 24,
    "max_cache_size": 1000,
}

# LLM Configuration
LLM_CONFIG = {
    "model": "llama-3.1-8b-instant",
    "temperature": 0.7,
    "max_tokens": 500,
    "top_p": 0.9,
}

# Debug/Logging
DEBUG = {
    "log_searches": True,
    "log_metaobject_calls": True,
    "log_prompt_input": False,  # Don't log full product data
    "log_prompt_output": True,
}
