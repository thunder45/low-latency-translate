"""
Unit tests for deduplication cache.

Tests cache operations, TTL expiration, and cleanup logic.
"""

import time
import pytest
from shared.services import DeduplicationCache


class TestDeduplicationCache:
    """Test suite for DeduplicationCache class."""
    
    def test_cache_initialization(self):
        """Test cache initialization with default TTL."""
        cache = DeduplicationCache()
        assert cache.ttl_seconds == 10
        assert cache.size() == 0
    
    def test_cache_initialization_custom_ttl(self):
        """Test cache initialization with custom TTL."""
        cache = DeduplicationCache(ttl_seconds=20)
        assert cache.ttl_seconds == 20
        assert cache.size() == 0
    
    def test_add_and_contains(self):
        """Test adding text and checking if it exists."""
        cache = DeduplicationCache()
        
        text = "hello everyone"
        cache.add(text)
        
        assert cache.contains(text) is True
        assert cache.size() == 1
    
    def test_contains_normalizes_text(self):
        """Test that contains() normalizes text before checking."""
        cache = DeduplicationCache()
        
        # Add with one format
        cache.add("Hello Everyone!")
        
        # Check with different formats (should all match)
        assert cache.contains("hello everyone") is True
        assert cache.contains("HELLO EVERYONE") is True
        assert cache.contains("hello, everyone!") is True
        assert cache.contains("  hello   everyone  ") is True
    
    def test_contains_returns_false_for_missing_text(self):
        """Test that contains() returns False for text not in cache."""
        cache = DeduplicationCache()
        
        cache.add("hello world")
        
        assert cache.contains("goodbye world") is False
        assert cache.contains("hello") is False
    
    def test_add_multiple_entries(self):
        """Test adding multiple different entries."""
        cache = DeduplicationCache()
        
        texts = [
            "hello world",
            "goodbye world",
            "this is a test",
            "another test message"
        ]
        
        for text in texts:
            cache.add(text)
        
        assert cache.size() == 4
        
        for text in texts:
            assert cache.contains(text) is True
    
    def test_add_duplicate_text_updates_entry(self):
        """Test that adding duplicate text updates the entry."""
        cache = DeduplicationCache(ttl_seconds=5)
        
        text = "hello world"
        
        # Add first time
        cache.add(text)
        assert cache.size() == 1
        
        # Add again (should update, not create new entry)
        cache.add(text)
        assert cache.size() == 1
    
    def test_ttl_expiration(self):
        """Test that entries expire after TTL."""
        cache = DeduplicationCache(ttl_seconds=1)
        
        text = "hello world"
        cache.add(text)
        
        # Should exist immediately
        assert cache.contains(text) is True
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Should be expired
        assert cache.contains(text) is False
        assert cache.size() == 0
    
    def test_cleanup_expired_removes_expired_entries(self):
        """Test that cleanup_expired() removes expired entries."""
        cache = DeduplicationCache(ttl_seconds=1)
        
        # Add multiple entries
        cache.add("text1")
        cache.add("text2")
        cache.add("text3")
        
        assert cache.size() == 3
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Cleanup
        removed_count = cache.cleanup_expired()
        
        assert removed_count == 3
        assert cache.size() == 0
    
    def test_cleanup_expired_keeps_fresh_entries(self):
        """Test that cleanup_expired() keeps non-expired entries."""
        cache = DeduplicationCache(ttl_seconds=10)
        
        # Add entries
        cache.add("text1")
        cache.add("text2")
        
        # Cleanup immediately (nothing should be removed)
        removed_count = cache.cleanup_expired()
        
        assert removed_count == 0
        assert cache.size() == 2
        assert cache.contains("text1") is True
        assert cache.contains("text2") is True
    
    def test_opportunistic_cleanup_on_add(self):
        """Test that cleanup happens opportunistically during add()."""
        cache = DeduplicationCache(ttl_seconds=1)
        cache.cleanup_interval = 0.5  # Reduce interval for testing
        
        # Add entry
        cache.add("text1")
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Add another entry (should trigger cleanup)
        cache.add("text2")
        
        # text1 should be cleaned up, only text2 should remain
        assert cache.size() == 1
        assert cache.contains("text1") is False
        assert cache.contains("text2") is True
    
    def test_opportunistic_cleanup_on_contains(self):
        """Test that cleanup happens opportunistically during contains()."""
        cache = DeduplicationCache(ttl_seconds=1)
        cache.cleanup_interval = 0.5  # Reduce interval for testing
        
        # Add entry
        cache.add("text1")
        
        # Wait for expiration and cleanup interval
        time.sleep(1.5)
        
        # Check for different text (should trigger cleanup)
        cache.contains("text2")
        
        # text1 should be cleaned up
        assert cache.size() == 0
    
    def test_emergency_cleanup_when_cache_too_large(self):
        """Test emergency cleanup when cache exceeds max size."""
        cache = DeduplicationCache()
        cache.max_cache_size = 10  # Set low threshold for testing
        
        # Add entries up to threshold
        for i in range(10):
            cache.add(f"text{i}")
        
        assert cache.size() == 10
        
        # Add one more (should trigger emergency cleanup before adding)
        # Emergency cleanup clears all, then new entry is added
        cache.add("text_overflow")
        
        # Cache should have only the new entry
        assert cache.size() == 1
        assert cache.contains("text_overflow") is True
    
    def test_clear_removes_all_entries(self):
        """Test that clear() removes all entries."""
        cache = DeduplicationCache()
        
        # Add multiple entries
        for i in range(5):
            cache.add(f"text{i}")
        
        assert cache.size() == 5
        
        # Clear cache
        cache.clear()
        
        assert cache.size() == 0
        
        # Verify all entries are gone
        for i in range(5):
            assert cache.contains(f"text{i}") is False
    
    def test_size_returns_correct_count(self):
        """Test that size() returns correct entry count."""
        cache = DeduplicationCache()
        
        assert cache.size() == 0
        
        cache.add("text1")
        assert cache.size() == 1
        
        cache.add("text2")
        assert cache.size() == 2
        
        cache.add("text3")
        assert cache.size() == 3
    
    def test_contains_removes_expired_entry_on_check(self):
        """Test that contains() removes expired entry when checked."""
        cache = DeduplicationCache(ttl_seconds=1)
        
        text = "hello world"
        cache.add(text)
        
        assert cache.size() == 1
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Check (should remove expired entry)
        result = cache.contains(text)
        
        assert result is False
        assert cache.size() == 0
    
    def test_mixed_expired_and_fresh_entries(self):
        """Test cache with mix of expired and fresh entries."""
        cache = DeduplicationCache(ttl_seconds=2)
        
        # Add first entry
        cache.add("old_text")
        
        # Wait 1 second
        time.sleep(1)
        
        # Add second entry
        cache.add("new_text")
        
        # Wait another 1.5 seconds (old_text expired, new_text still fresh)
        time.sleep(1.5)
        
        # Cleanup
        removed_count = cache.cleanup_expired()
        
        assert removed_count == 1
        assert cache.size() == 1
        assert cache.contains("old_text") is False
        assert cache.contains("new_text") is True
    
    def test_cache_handles_empty_string(self):
        """Test that cache handles empty string."""
        cache = DeduplicationCache()
        
        cache.add("")
        
        assert cache.size() == 1
        assert cache.contains("") is True
    
    def test_cache_handles_long_text(self):
        """Test that cache handles very long text."""
        cache = DeduplicationCache()
        
        long_text = "hello world " * 1000  # 12,000 characters
        
        cache.add(long_text)
        
        assert cache.size() == 1
        assert cache.contains(long_text) is True
    
    def test_cache_thread_safety_not_guaranteed(self):
        """
        Note: This cache is NOT thread-safe.
        
        This test documents that the cache is designed for single-threaded
        use within a Lambda function invocation. For multi-threaded use,
        additional synchronization would be needed.
        """
        # This is a documentation test - no actual threading test
        cache = DeduplicationCache()
        assert cache is not None
        # In production, each Lambda invocation has its own cache instance
