"""
EAN-13 Generator for Nykaa Products
Random generation - no persistence, no deterministic mapping
"""

import random
import secrets
from typing import Set


# In-memory tracking of generated EANs in current session
# to avoid unlikely duplicates within same batch
_GENERATED_EANS_SESSION: Set[str] = set()


def calculate_ean13_checksum(ean12: str) -> str:
    """
    Calculate EAN-13 checksum digit
    
    Args:
        ean12: First 12 digits of EAN code
    
    Returns:
        Single checksum digit (0-9)
    
    Algorithm:
    1. Sum odd-position digits (positions 1,3,5,7,9,11)
    2. Multiply by 3
    3. Sum even-position digits (positions 2,4,6,8,10,12)
    4. Add the two sums
    5. Checksum = (10 - (sum mod 10)) mod 10
    """
    
    if len(ean12) != 12:
        raise ValueError(f"EAN12 must be exactly 12 digits, got {len(ean12)}")
    
    # Sum odd positions (1-indexed: 1,3,5,7,9,11) = indices 0,2,4,6,8,10
    odd_sum = sum(int(ean12[i]) for i in range(0, 12, 2))
    
    # Sum even positions (1-indexed: 2,4,6,8,10,12) = indices 1,3,5,7,9,11
    even_sum = sum(int(ean12[i]) for i in range(1, 12, 2))
    
    # Calculate checksum
    total = (odd_sum * 3) + even_sum
    checksum = (10 - (total % 10)) % 10
    
    return str(checksum)


def generate_ean13() -> str:
    """
    Generate random 13-digit EAN code
    
    Returns:
        Valid EAN-13 code as string
    
    Process:
    1. Generate 12 random digits
    2. Calculate checksum for 13th digit
    3. Validate against session duplicates (extremely unlikely)
    """
    
    max_retries = 10
    
    for attempt in range(max_retries):
        # Generate 12 random digits using secrets for cryptographic randomness
        ean12 = ''.join(str(secrets.randbelow(10)) for _ in range(12))
        
        # Calculate checksum
        checksum = calculate_ean13_checksum(ean12)
        ean13 = ean12 + checksum
        
        # Check for duplicate (extremely unlikely with random generation)
        if ean13 not in _GENERATED_EANS_SESSION:
            _GENERATED_EANS_SESSION.add(ean13)
            return ean13
    
    # Should never reach here, but fallback
    raise RuntimeError(f"Failed to generate unique EAN after {max_retries} retries")


def validate_ean13(ean: str) -> bool:
    """
    Validate an EAN-13 code
    
    Args:
        ean: EAN code as string or integer
    
    Returns:
        True if valid, False otherwise
    """
    
    ean_str = str(ean).strip()
    
    # Must be exactly 13 digits
    if len(ean_str) != 13 or not ean_str.isdigit():
        return False
    
    # Validate checksum
    ean12 = ean_str[:12]
    provided_checksum = ean_str[12]
    calculated_checksum = calculate_ean13_checksum(ean12)
    
    return provided_checksum == calculated_checksum


def batch_generate_ean13(count: int) -> list:
    """
    Generate multiple EAN-13 codes
    
    Args:
        count: Number of EAN codes to generate
    
    Returns:
        List of unique EAN-13 codes
    """
    
    eancodes = []
    for _ in range(count):
        eancodes.append(generate_ean13())
    
    return eancodes


def clear_session_tracking():
    """Clear session EAN tracking (do this between exports)"""
    global _GENERATED_EANS_SESSION
    _GENERATED_EANS_SESSION.clear()
    print("🗑️ EAN session tracking cleared")


def get_session_stats() -> dict:
    """Get statistics about generated EANs in session"""
    return {
        "generated_count": len(_GENERATED_EANS_SESSION),
        "sample_eans": list(_GENERATED_EANS_SESSION)[:5],
    }


# Example usage and tests
if __name__ == "__main__":
    print("=== EAN-13 Generator Test ===\n")
    
    # Test single generation
    print("1. Single EAN generation:")
    ean = generate_ean13()
    print(f"   Generated: {ean}")
    print(f"   Valid: {validate_ean13(ean)}\n")
    
    # Test batch generation
    print("2. Batch generation (5 codes):")
    eancodes = batch_generate_ean13(5)
    for ean in eancodes:
        print(f"   {ean} (valid: {validate_ean13(ean)})")
    
    print(f"\n3. Session stats:")
    stats = get_session_stats()
    print(f"   Total generated: {stats['generated_count']}")
    print(f"   Sample: {stats['sample_eans'][:3]}")
    
    # Test checksum validation
    print(f"\n4. Checksum validation:")
    valid_ean = "5901234123457"  # Known valid EAN
    invalid_ean = "5901234123458"  # Wrong checksum
    print(f"   {valid_ean} is valid: {validate_ean13(valid_ean)}")
    print(f"   {invalid_ean} is valid: {validate_ean13(invalid_ean)}")
