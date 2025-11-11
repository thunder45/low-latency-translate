"""
Text normalization utilities for deduplication.

This module provides functions to normalize text for comparison and
generate consistent hashes for deduplication purposes.
"""

import re
import hashlib


def normalize_text(text: str) -> str:
    """
    Normalize text for deduplication comparison.
    
    Normalization steps:
    1. Convert to lowercase
    2. Remove punctuation (. , ! ? ; : ' ")
    3. Collapse multiple spaces to single space
    4. Strip leading/trailing whitespace
    
    This ensures that text segments that differ only in capitalization
    or punctuation are recognized as duplicates.
    
    Args:
        text: Input text to normalize
        
    Returns:
        Normalized text string
        
    Examples:
        >>> normalize_text("Hello everyone, this is important!")
        'hello everyone this is important'
        
        >>> normalize_text("Hello Everyone This Is Important")
        'hello everyone this is important'
        
        >>> normalize_text("hello   everyone,   this   is   important.")
        'hello everyone this is important'
    """
    if not text:
        return ""
    
    # Convert to lowercase
    normalized = text.lower()
    
    # Remove punctuation
    # Pattern matches: . , ! ? ; : ' "
    normalized = re.sub(r'[.,!?;:\'\"]', '', normalized)
    
    # Collapse multiple spaces to single space
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Strip leading/trailing whitespace
    normalized = normalized.strip()
    
    return normalized


def hash_text(text: str) -> str:
    """
    Generate SHA-256 hash of normalized text.
    
    This function normalizes the text first, then generates a consistent
    hash that can be used as a cache key for deduplication.
    
    Args:
        text: Input text to hash
        
    Returns:
        Hexadecimal SHA-256 hash string (64 characters)
        
    Examples:
        >>> hash_text("Hello everyone!")
        'a1b2c3d4...'  # 64-character hex string
        
        >>> hash_text("hello everyone") == hash_text("Hello Everyone!")
        True  # Same normalized text produces same hash
    """
    # Normalize text first
    normalized = normalize_text(text)
    
    # Generate SHA-256 hash
    hash_obj = hashlib.sha256(normalized.encode('utf-8'))
    
    return hash_obj.hexdigest()
