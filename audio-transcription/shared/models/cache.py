"""
Cache entry data model for deduplication.

This module defines the dataclass for entries in the deduplication cache,
which prevents duplicate synthesis of identical text segments.
"""

import time
from dataclasses import dataclass


@dataclass
class CacheEntry:
    """
    Entry in deduplication cache.
    
    Cache entries store normalized text hashes with TTL to prevent
    duplicate synthesis of identical text segments within a time window.
    
    Attributes:
        text_hash: SHA-256 hash of normalized text
        added_at: Unix timestamp when entry was added
        ttl_seconds: Time-to-live in seconds (default: 10)
    """
    
    text_hash: str
    added_at: float
    ttl_seconds: int = 10
    
    def __post_init__(self):
        """Validate field constraints."""
        if not self.text_hash:
            raise ValueError("text_hash cannot be empty")
        
        if self.added_at <= 0:
            raise ValueError(f"added_at must be positive, got {self.added_at}")
        
        if self.ttl_seconds < 1:
            raise ValueError(f"ttl_seconds must be at least 1, got {self.ttl_seconds}")
    
    def is_expired(self) -> bool:
        """
        Check if entry has expired.
        
        Returns:
            True if current time exceeds added_at + ttl_seconds
        """
        return (time.time() - self.added_at) > self.ttl_seconds
