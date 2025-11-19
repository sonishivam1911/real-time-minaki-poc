"""
Nykaa Product Validator
Validates product names and descriptions against Nykaa requirements
"""

from typing import Tuple, Dict, Any, List


def validate_product_name(name: str) -> Tuple[bool, List[str]]:
    """
    Validate product name against Nykaa standards
    
    Args:
        name: Product name to validate
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    
    errors = []
    
    # Length check
    if len(name) < 30:
        errors.append(f"Name too short ({len(name)} chars, min 30)")
    if len(name) > 100:
        errors.append(f"Name too long ({len(name)} chars, max 100)")
    
    # Capitalization check
    if name.islower():
        errors.append("Name must use Title Case (not all lowercase)")
    if name.isupper():
        errors.append("Name must use Title Case (not all uppercase)")
    
    # Must have colon separator
    if ":" not in name:
        errors.append("Name must contain ':' separator (QueenName: ProductType)")
    
    # Check for SKU presence
    if any(char.isdigit() and len(char) > 1 for char in name.split()):
        # More lenient: allow single digits, but flag number sequences
        import re
        if re.search(r'\b\d{3,}\b', name):  # 3+ digit sequences
            errors.append("Name contains SKU/numbers (remove product codes)")
    
    # Must have product type
    types = ["Necklace", "Choker", "Earring", "Pendant", "Bracelet", 
             "Ring", "Bangle", "Jhumka", "Set"]
    if not any(t in name for t in types):
        errors.append("Name must include product type (Necklace, Choker, etc)")
    
    # Must have material
    materials = ["Kundan", "Polki", "Gold", "Pearl", "Temple", "Silver"]
    if not any(m in name for m in materials):
        errors.append("Name must include material (Kundan, Polki, Gold, etc)")
    
    # Check for brand name
    if "MINAKII" in name or "Minakii" in name:
        errors.append("Name should not include brand name")
    
    return (len(errors) == 0, errors)


def validate_product_description(description: str) -> Tuple[bool, List[str]]:
    """
    Validate product description against Nykaa standards
    
    Args:
        description: Product description to validate
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    
    errors = []
    desc_lower = description.lower()
    
    # Length check
    if len(description) > 500:
        errors.append(f"Description too long ({len(description)} chars, max 500)")
    if len(description) < 50:
        errors.append(f"Description too short ({len(description)} chars, min 50)")
    
    # Must have opening hook
    hook_words = ["add", "celebrate", "elevate", "perfect", "stunning", 
                  "exquisite", "complement", "enhance", "special"]
    has_hook = any(word in desc_lower[:100] for word in hook_words)
    if not has_hook:
        errors.append("Missing opening hook/benefit in first sentences")
    
    # Should mention material
    materials = ["kundan", "polki", "gold", "pearl", "stone"]
    if not any(m in desc_lower for m in materials):
        errors.append("Description should mention material/stones")
    
    # Should mention occasion or wear context
    occasions = ["wedding", "festive", "party", "occasion", "wear", "complement", 
                 "celebrate", "ceremony"]
    if not any(o in desc_lower for o in occasions):
        errors.append("Should mention occasion or wear context")
    
    # Should mention care
    care_words = ["care", "store", "clean", "maintain", "keep", "moisture"]
    if not any(word in desc_lower for word in care_words):
        errors.append("Should include care/maintenance instructions")
    
    # Check for SKU presence
    import re
    if re.search(r'\bMS\d+\b|\bMM\d+\b', description):
        errors.append("Remove SKU codes from description")
    
    # Check for brand repetition
    if desc_lower.count("minakii") > 0:
        errors.append("Remove brand name from description")
    
    return (len(errors) == 0, errors)


def calculate_quality_score(name: str, description: str) -> Dict[str, Any]:
    """
    Calculate overall quality score for name and description
    
    Returns:
        Dictionary with component scores and total
    """
    
    name_valid, name_errors = validate_product_name(name)
    desc_valid, desc_errors = validate_product_description(description)
    
    # Calculate scores based on error count
    name_score = max(0, 100 - (len(name_errors) * 15))
    desc_score = max(0, 100 - (len(desc_errors) * 12))
    
    overall_score = (name_score + desc_score) / 2
    
    return {
        "overall": overall_score,
        "name": {
            "score": name_score,
            "valid": name_valid,
            "errors": name_errors,
        },
        "description": {
            "score": desc_score,
            "valid": desc_valid,
            "errors": desc_errors,
        },
        "passed": name_valid and desc_valid,
    }


def should_flag_for_manual_review(
    quality_score: Dict[str, Any],
    has_images: int = 0,
    search_results_count: int = 0,
    material_resolved: bool = True,
    is_draft: bool = False,
) -> Tuple[bool, List[str]]:
    """
    Determine if product should be flagged for manual review
    
    Args:
        quality_score: Output from calculate_quality_score()
        has_images: Number of product images
        search_results_count: Number of web search results found
        material_resolved: Whether material was successfully resolved
        is_draft: Whether product is in draft status
    
    Returns:
        Tuple of (should_flag, list_of_reasons)
    """
    
    reasons = []
    
    # Quality score check
    if quality_score["overall"] < 60:
        reasons.append(f"Low quality score ({quality_score['overall']:.0f}%)")
    
    # Image check
    if has_images < 2:
        reasons.append(f"Insufficient images ({has_images} < 2)")
    
    # Search context check
    if search_results_count == 0:
        reasons.append("No search context found for reference")
    
    # Material resolution check
    if not material_resolved:
        reasons.append("Material could not be resolved from metaobject")
    
    # Draft status check
    if is_draft:
        reasons.append("Product is in draft status")
    
    should_flag = len(reasons) > 0
    
    return (should_flag, reasons)


def format_validation_report(
    product_sku: str,
    quality_score: Dict[str, Any],
    flags: Tuple[bool, List[str]],
) -> str:
    """
    Format validation results as readable report
    
    Args:
        product_sku: Product SKU for reference
        quality_score: Output from calculate_quality_score()
        flags: Output from should_flag_for_manual_review()
    
    Returns:
        Formatted report string
    """
    
    should_flag, reasons = flags
    
    report = f"""
VALIDATION REPORT - {product_sku}
{'='*50}

QUALITY SCORES:
  Overall: {quality_score['overall']:.1f}%
  Name:    {quality_score['name']['score']:.1f}%
  Description: {quality_score['description']['score']:.1f}%

NAME VALIDATION:
  Status: {'✅ PASS' if quality_score['name']['valid'] else '❌ FAIL'}
"""
    
    if quality_score['name']['errors']:
        report += "  Issues:\n"
        for error in quality_score['name']['errors']:
            report += f"    - {error}\n"
    
    report += f"""
DESCRIPTION VALIDATION:
  Status: {'✅ PASS' if quality_score['description']['valid'] else '❌ FAIL'}
"""
    
    if quality_score['description']['errors']:
        report += "  Issues:\n"
        for error in quality_score['description']['errors']:
            report += f"    - {error}\n"
    
    report += f"""
MANUAL REVIEW NEEDED: {'🚩 YES' if should_flag else '✅ NO'}
"""
    
    if reasons:
        report += "  Reasons:\n"
        for reason in reasons:
            report += f"    - {reason}\n"
    
    return report
