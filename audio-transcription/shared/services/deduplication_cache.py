"""
Deduplication cache for preventing duplicate synthesis.

This module provides a cache implementation that prevents duplicate
synthesis of identical text segments within a time window.
"""

import time
import logging
from typing import Dict
from shared.models import CacheEntry
from shared.utils import normalize_text, hash_text

logger = logging.getLogger(__name__)


class DeduplicationCache:
    """
    In-memory cache for deduplication of text segments.
    
    This cache stores normalized text hashes with TTL to prevent
    duplicate synthesis of identical text segments. It includes
    automatic cleanup of expired entries and emergency cleanup
    if the cache grows too large.
    
    Attributes:
        cache: Dictionary mapping text hashes to CacheEntry objects
        ttl_seconds: Time-to-live for cache entries (default: 10)
        last_cleanup: Timestamp of last cleanup operation
        cleanup_interval: Interval between cleanup operations (default: 30)
        max_cache_size: Maximum cache size before emergency cleanup (default: 10000)
    """
    
    def __init__(self, ttl_seconds: int = 10):
        """
        Initialize deduplication cache.
        
        Args:
            ttl_seconds: Time-to-live for cache entries in seconds
        """
        self.cache: Dict[str, CacheEntry] = {}
        self.ttl_seconds = ttl_seconds
        self.last_cleanup = time.time()
        self.cleanup_interval = 30.0  # Cleanup every 30 seconds
        self.max_cache_size = 10000  # Emergency cleanup threshold
        
        logger.info(f"DeduplicationCache initialized with TTL={ttl_seconds}s")
    
    def contains(self, text: str) -> bool:
        """
        Check if normalized text exists in cache.
        
        This method normalizes the input text, generates a hash,
        and checks if a non-expired entry exists in the cache.
        
        Args:
            text: Text to check for in cache
            
        Returns:
            True if text exists in cache and is not expired
            
        Examples:
            >>> cache = DeduplicationCache()
            >>> cache.add("Hello everyone!")
            >>> cache.contains("hello everyone")
            True
            >>> cache.contains("Hello Everyone!")
            True
            >>> cache.contains("different text")
            False
        """
        # Opportunistic cleanup
        self._cleanup_if_needed()
        
        # Generate hash of normalized text
        text_hash = hash_text(text)
        
        # Check if entry exists and is not expired
        if text_hash in self.cache:
            entry = self.cache[text_hash]
            if not entry.is_expired():
                logger.debug(f"Cache hit for text: {text[:50]}...")
                return True
            else:
                # Remove expired entry
                del self.cache[text_hash]
                logger.debug(f"Removed expired entry for text: {text[:50]}...")
        
        return False
    
    def add(self, text: str) -> None:
        """
        Add normalized text to cache with TTL.
        
        This method normalizes the input text, generates a hash,
        and stores it in the cache with the configured TTL.
        
        Args:
            text: Text to add to cache
            
        Examples:
            >>> cache = DeduplicationCache(ttl_seconds=10)
            >>> cache.add("Hello everyone!")
            >>> cache.contains("hello everyone")
            True
        """
        # Opportunistic cleanup
        self._cleanup_if_needed()
        
        # Emergency cleanup if cache too large (before adding new entry)
        if len(self.cache) >= self.max_cache_size:
            logger.warning(
                f"Cache size {len(self.cache)} exceeds limit {self.max_cache_size}, "
                "performing emergency cleanup"
            )
            self._emergency_cleanup()
        
        # Generate hash of normalized text
        text_hash = hash_text(text)
        
        # Create cache entry
        entry = CacheEntry(
            text_hash=text_hash,
            added_at=time.time(),
            ttl_seconds=self.ttl_seconds
        )
        
        # Add to cache
        self.cache[text_hash] = entry
        
        logger.debug(
            f"Added to cache: {text[:50]}... "
            f"(cache size: {len(self.cache)})"
        )
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.
        
        This method iterates through all cache entries and removes
        those that have exceeded their TTL.
        
        Returns:
            Number of entries removed
            
        Examples:
            >>> cache = DeduplicationCache(ttl_seconds=1)
            >>> cache.add("test")
            >>> time.sleep(2)
            >>> cache.cleanup_expired()
            1
        """
        expired_keys = [
            key for key, entry in self.cache.items()
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired entries")
        
        return len(expired_keys)
    
    def _cleanup_if_needed(self) -> None:
        """
        Perform opportunistic cleanup if interval has elapsed.
        
        This method checks if the cleanup interval has elapsed since
        the last cleanup and performs cleanup if needed. This is called
        opportunistically during add() and contains() operations.
        """
        current_time = time.time()
        if (current_time - self.last_cleanup) >= self.cleanup_interval:
            self.cleanup_expired()
            self.last_cleanup = current_time
    
    def _emergency_cleanup(self) -> None:
        """
        Perform emergency cleanup when cache exceeds maximum size.
        
        This method clears the entire cache to prevent memory issues.
        It should only be triggered when the cache grows unexpectedly large.
        """
        cache_size = len(self.cache)
        self.cache.clear()
        self.last_cleanup = time.time()
        
        logger.error(
            f"Emergency cleanup: cleared {cache_size} entries. "
            "This indicates a potential issue with cache management."
        )
    
    def size(self) -> int:
        """
        Get current cache size.
        
        Returns:
            Number of entries in cache
        """
        return len(self.cache)
    
    def clear(self) -> None:
        """
        Clear all entries from cache.
        
        This method removes all entries and resets the cleanup timestamp.
        Useful for testing or manual cache management.
        """
        self.cache.clear()
        self.last_cleanup = time.time()
        logger.info("Cache cleared")
