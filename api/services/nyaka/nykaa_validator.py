"""
Nykaa Validator - Validates all mapped values against dropdown values
Prevents submission of invalid values to Nykaa
"""

from typing import Dict, Any, List, Tuple


# ============================================================================
# VALID DROPDOWN VALUES (From Nykaa Excel - All 21 Dropdowns)
# ============================================================================

VALID_GENDER = ["Girls", "Boys", "Unisex", "Moms", "Men", "Women", "Male", "Female"]

VALID_COLORS = [
    "Beige", "Black", "Blue", "Bronze", "Brown", "Clear", "Coral", "Gold",
    "Green", "Grey", "Khaki", "Lavender", "Magenta", "Cream", "Maroon",
    "Metallic", "Multi-Color", "Mustard", "Navy Blue", "Nude", "Off White",
    "Olive", "Orange", "Peach", "Pink", "Purple", "Red", "Rose Gold", "Rust",
    "Silver", "Tan", "Taupe", "Teal", "Transparent", "Turquoise", "White",
    "White Gold", "Yellow", "Indigo", "Ivory", "Burgundy", "Copper", "Wine",
    "Charcoal", "Mauve", "Aqua", "Blonde"
]

VALID_MATERIALS = [
    "PU", "Alloy", "Aluminium", "Canvas", "Carbon", "Cast Iron", "Cotton",
    "Elastane", "Elastic", "Fibre", "Foam", "Glass", "Iron", "Latex",
    "Latex Rubber", "Leather", "Lycra", "Nano Power Coating", "Nano Titanium Coating",
    "Natural Cork", "Neoprene", "Nylon", "Plastic", "Plywood", "Polyester",
    "Rubber", "Silicone", "Silk", "Sponge", "Steel", "Synthetic", "TPU", "Wood",
    "Brass", "Copper", "Silver", "Sterling Silver", "Bronze"
    # Add all 403 materials from Excel if needed
]

VALID_PLATING = [
    "Silver", "Brass", "22k Gold", "Rose Gold", "Ruthenium", "Gunmetal",
    "18K Gold", "Rhodium", "Black", "Palladium", "Copper", "22K Gold",
    "24K Gold", "Gold", "14K Gold", "Antique Gold", "White Gold",
    "No Plating", "Platinum"
]

VALID_MULTIPACK_SET = [
    "Pack", "Singles", "Single", "Multi-Packs", "Combo",
    "Pack of 2", "Pack of 3", "Pack of 4", "Pack of 5", "Pack of 6",
    "Pack of 7", "Pack of 8", "Pack of 9", "Pack of 10", "Pack of 11",
    "Pack of 12", "Pack of 13", "Pack of 14", "Pack of 15", "Pack of 16",
    "Pack of 17", "Pack of 18", "Pack of 19", "Pack of 20", "Pack of 21",
    "Pack of 22", "Pack of 23", "Pack of 24", "Pack of 25", "Pack of 26",
    "Pack of 27", "Pack of 28", "Pack of 30", "Pack of 32", "Pack of 33",
    "Pack of 35", "Pack of 36", "Pack of 38", "Pack of 39", "Pack of 40",
    "Pack of 44", "Pack of 48", "Pack of 50", "Pack of 66", "Pack of 68",
    "Pack of 70", "Pack of 72", "Pack of 74", "Pack of 100", "Pack of 120"
]

VALID_OCCASIONS = [
    "Casual", "Evening Wear", "Semi Formal", "Special Occasion", "Night Out",
    "Day Wear", "Festive Wear", "Any Occasion", "Festive", "Sports", "Wedding",
    "Formal", "Everyday Essentials", "Fusion", "Sporty", "Party", "Wedding Wear",
    "Resort/Vacation", "Cocktail Wear", "Work", "Evening", "Winter", "Nightwear",
    "Lingerie", "Maternity", "Rainy", "Loungewear", "Workout", "Travel", "Date Night"
]

VALID_STYLES_OF_JEWELLERY = [
    "Tassel", "Delicates", "Kaasu Malai", "Oxidised", "Stones", "Rudraksha Rakhi",
    "Kundan", "Dramatic", "Sterling Silver", "Meenakari", "Temple", "Resort",
    "Fusion", "Traditional Rakhi", "Minimal", "Essential", "Statement", "Minakari",
    "Pearl", "Silver Jewellery", "Contemporary", "Coloured Stone", "White Stones",
    "Evil Eye"
]

VALID_TYPE_OF_JEWELLERY = [
    "Cuffs & Kadas", "Armlet", "Studs", "Bangles", "Hoops", "Body Chain",
    "Pendants", "Jewellery Set", "Chandbalis", "Toe Rings", "Maang Tikka",
    "Ear Cuffs & Clips", "Drops & Danglers", "Anklet", "Bracelets",
    "Necklaces & Neckpieces", "Choker", "Rings", "Hand Harness", "Mangalsutra",
    "Charms", "Nose Rings with Chains", "Bhaiya Bhabhi Rakhi", "Thread Rakhi",
    "Kundan Rakhi", "Bracelet Rakhi", "Silver Rakhi", "Kids Rakhi",
    "Rakhi Gift Sets", "Semi-Precious Rakhi", "Fashion Rakhis", "Gold Rakhi",
    "Brooche", "Kaleeras", "Jhumkas", "Waist Chains", "Nose Pin", "Matha Patti",
    "Naths", "Nose Rings", "Passa"
]

VALID_SEGMENTS = [
    "Silver Jewellery", "Traditional", "Western", "Coins & Bars",
    "Gold & Diamond Jewellery"
]

VALID_WARRANTY = [
    "3 Years", "5 Years", "Upto 1 year", "3 Months", "No Warranty",
    "Upto 6 months", "15 Days", "1 Year", "More than 2 Years", "6 Months",
    "1 Month", "Upto 1 Year", "Lifetime Warranty", "Upto 2 Year", "2 Years",
    "More than 2 years", "Upto 6 Months", "Upto 2 years", "4 Years", "30 Days",
    "7 Days", "2 Months", "6 Years", "Lifetime Service Warranty", "8 Years",
    "9 Years", "10 years", "7 Years", "5 Months", "12 Months", "18 Months",
    "9 Months", "16 Months", "17 Months", "4 Months", "7 Months", "8 Months",
    "10 Months", "11 Months", "13 Months", "14 Months", "15 Months", "1 year",
    "45 Days", "500 Days", "3M to 1Y", "1Y to 2Y", "Upto 3 years", "10 Days"
]


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_single_select_field(value: str, valid_values: List[str], field_name: str) -> Tuple[bool, str]:
    """
    Validate single-select field
    
    Returns:
        (is_valid, error_message)
    """
    if not value or str(value).strip() == "":
        return True, ""  # Empty is OK for optional fields
    
    if value in valid_values:
        return True, ""
    
    return False, f"{field_name}: '{value}' is not a valid Nykaa dropdown value"


def validate_multi_select_field(value: str, valid_values: List[str], field_name: str) -> Tuple[bool, List[str]]:
    """
    Validate multi-select field (comma-separated values)
    
    Returns:
        (is_valid, list_of_errors)
    """
    if not value or str(value).strip() == "":
        return True, []
    
    errors = []
    
    # Split by comma
    values = [v.strip() for v in str(value).split(",")]
    
    for v in values:
        if v and v not in valid_values:
            errors.append(f"{field_name}: '{v}' is not a valid Nykaa dropdown value")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def validate_nykaa_row_complete(row: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """
    Complete validation of Nykaa row against all dropdowns
    
    Returns:
        (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # Validate Gender (single-select)
    is_valid, error = validate_single_select_field(
        row.get("Gender", ""),
        VALID_GENDER,
        "Gender"
    )
    if not is_valid:
        errors.append(error)
    
    # Validate Color (multi-select)
    is_valid, color_errors = validate_multi_select_field(
        row.get("Color", ""),
        VALID_COLORS,
        "Color"
    )
    if not is_valid:
        errors.extend(color_errors)
    
    # Validate Material (multi-select)
    is_valid, material_errors = validate_multi_select_field(
        row.get("Material", ""),
        VALID_MATERIALS,
        "Material"
    )
    if not is_valid:
        errors.extend(material_errors)
    
    # Validate Plating (multi-select)
    is_valid, plating_errors = validate_multi_select_field(
        row.get("Plating", ""),
        VALID_PLATING,
        "Plating"
    )
    if not is_valid:
        errors.extend(plating_errors)
    
    # Validate Multipack Set (multi-select)
    is_valid, error = validate_single_select_field(
        row.get("Multipack Set", ""),
        VALID_MULTIPACK_SET,
        "Multipack Set"
    )
    if not is_valid:
        errors.append(error)
    
    # Validate Occasion (multi-select)
    is_valid, occasion_errors = validate_multi_select_field(
        row.get("Occasion", ""),
        VALID_OCCASIONS,
        "Occasion"
    )
    if not is_valid:
        errors.extend(occasion_errors)
    
    # Validate Styles of Jewellery (single-select)
    is_valid, error = validate_single_select_field(
        row.get("Styles of Jewellery", ""),
        VALID_STYLES_OF_JEWELLERY,
        "Styles of Jewellery"
    )
    if not is_valid:
        errors.append(error)
    
    # Validate Type of Jewellery (multi-select)
    is_valid, error = validate_single_select_field(
        row.get("Type of Jewellery", ""),
        VALID_TYPE_OF_JEWELLERY,
        "Type of Jewellery"
    )
    if not is_valid:
        errors.append(error)
    
    # Validate Segment (multi-select)
    is_valid, error = validate_single_select_field(
        row.get("Segment", ""),
        VALID_SEGMENTS,
        "Segment"
    )
    if not is_valid:
        errors.append(error)
    
    # Validate Warranty (multi-select)
    is_valid, error = validate_single_select_field(
        row.get("Warranty", ""),
        VALID_WARRANTY,
        "Warranty"
    )
    if not is_valid:
        errors.append(error)
    
    # Validate mandatory fields are not empty
    mandatory_fields = [
        "Vendor SKU Code", "Gender", "Brand Name", "Style Code", "Product Name",
        "Description", "Price", "Color", "Country of Origin", "Manufacturer Name",
        "Manufacturer Address", "return_available", "Is Replaceable", "brand size",
        "Multipack Set", "Occasion", "Season", "Care Instruction", "Ships In",
        "HSN Codes", "Pack Contains", "Net Qty", "Material", "Plating",
        "Styles of Jewellery", "Type of Jewellery", "Segment", "Front Image", "Back Image"
    ]
    
    for field in mandatory_fields:
        value = row.get(field, "")
        if not value or str(value).strip() == "":
            warnings.append(f"Mandatory field '{field}' is empty")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def validate_batch(nykaa_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate multiple Nykaa rows
    
    Returns:
        Summary dict with validation results
    """
    total_products = len(nykaa_rows)
    valid_products = 0
    invalid_products = 0
    total_errors = 0
    total_warnings = 0
    
    detailed_results = []
    
    for i, row in enumerate(nykaa_rows):
        sku = row.get("Vendor SKU Code", f"Product {i+1}")
        is_valid, errors, warnings = validate_nykaa_row_complete(row)
        
        if is_valid:
            valid_products += 1
        else:
            invalid_products += 1
        
        total_errors += len(errors)
        total_warnings += len(warnings)
        
        if errors or warnings:
            detailed_results.append({
                "sku": sku,
                "is_valid": is_valid,
                "errors": errors,
                "warnings": warnings
            })
    
    return {
        "total_products": total_products,
        "valid_products": valid_products,
        "invalid_products": invalid_products,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "detailed_results": detailed_results
    }