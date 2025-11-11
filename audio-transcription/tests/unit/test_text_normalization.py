"""
Unit tests for text normalization utilities.

Tests normalization logic and hash generation for deduplication.
"""

import pytest
from shared.utils import normalize_text, hash_text


class TestNormalizeText:
    """Test suite for normalize_text function."""
    
    def test_normalize_lowercase_conversion(self):
        """Test that text is converted to lowercase."""
        assert normalize_text("HELLO WORLD") == "hello world"
        assert normalize_text("Hello World") == "hello world"
        assert normalize_text("HeLLo WoRLd") == "hello world"
    
    def test_normalize_removes_punctuation(self):
        """Test that punctuation is removed."""
        assert normalize_text("Hello, world!") == "hello world"
        assert normalize_text("Hello. World?") == "hello world"
        assert normalize_text("Hello; world:") == "hello world"
        assert normalize_text("Hello 'world'") == "hello world"
        assert normalize_text('Hello "world"') == "hello world"
    
    def test_normalize_collapses_multiple_spaces(self):
        """Test that multiple spaces are collapsed to single space."""
        assert normalize_text("hello   world") == "hello world"
        assert normalize_text("hello     world") == "hello world"
        assert normalize_text("hello\t\tworld") == "hello world"
        assert normalize_text("hello\n\nworld") == "hello world"
    
    def test_normalize_strips_whitespace(self):
        """Test that leading/trailing whitespace is removed."""
        assert normalize_text("  hello world  ") == "hello world"
        assert normalize_text("\thello world\t") == "hello world"
        assert normalize_text("\nhello world\n") == "hello world"
    
    def test_normalize_combined_operations(self):
        """Test normalization with multiple operations."""
        input_text = "  Hello,   Everyone!  This   is   IMPORTANT.  "
        expected = "hello everyone this is important"
        assert normalize_text(input_text) == expected
    
    def test_normalize_empty_string(self):
        """Test that empty string returns empty string."""
        assert normalize_text("") == ""
    
    def test_normalize_only_punctuation(self):
        """Test text with only punctuation."""
        assert normalize_text(".,!?;:'\"") == ""
    
    def test_normalize_only_whitespace(self):
        """Test text with only whitespace."""
        assert normalize_text("   \t\n   ") == ""
    
    def test_normalize_preserves_numbers(self):
        """Test that numbers are preserved."""
        assert normalize_text("Hello 123 world") == "hello 123 world"
        assert normalize_text("Test 456.789") == "test 456789"
    
    def test_normalize_preserves_special_characters(self):
        """Test that non-punctuation special characters are preserved."""
        assert normalize_text("hello@world") == "hello@world"
        assert normalize_text("hello#world") == "hello#world"
        assert normalize_text("hello$world") == "hello$world"
    
    def test_normalize_unicode_characters(self):
        """Test normalization with unicode characters."""
        assert normalize_text("Héllo Wörld") == "héllo wörld"
        assert normalize_text("你好 世界") == "你好 世界"
    
    def test_normalize_idempotent(self):
        """Test that normalizing twice produces same result."""
        text = "Hello, World!"
        normalized_once = normalize_text(text)
        normalized_twice = normalize_text(normalized_once)
        assert normalized_once == normalized_twice


class TestHashText:
    """Test suite for hash_text function."""
    
    def test_hash_generates_consistent_hash(self):
        """Test that same text produces same hash."""
        text = "hello world"
        hash1 = hash_text(text)
        hash2 = hash_text(text)
        assert hash1 == hash2
    
    def test_hash_length_is_64_characters(self):
        """Test that SHA-256 hash is 64 hex characters."""
        text = "hello world"
        hash_value = hash_text(text)
        assert len(hash_value) == 64
        assert all(c in '0123456789abcdef' for c in hash_value)
    
    def test_hash_normalizes_before_hashing(self):
        """Test that text is normalized before hashing."""
        # These should produce the same hash
        hash1 = hash_text("Hello World")
        hash2 = hash_text("hello world")
        hash3 = hash_text("HELLO WORLD")
        hash4 = hash_text("hello, world!")
        
        assert hash1 == hash2
        assert hash2 == hash3
        assert hash3 == hash4
    
    def test_hash_different_text_produces_different_hash(self):
        """Test that different text produces different hash."""
        hash1 = hash_text("hello world")
        hash2 = hash_text("goodbye world")
        assert hash1 != hash2
    
    def test_hash_empty_string(self):
        """Test hashing empty string."""
        hash_value = hash_text("")
        assert len(hash_value) == 64
        # Empty string should produce consistent hash
        assert hash_value == hash_text("")
    
    def test_hash_with_punctuation_variations(self):
        """Test that punctuation variations produce same hash."""
        variations = [
            "Hello everyone, this is important!",
            "Hello everyone this is important",
            "hello everyone, this is important.",
            "HELLO EVERYONE THIS IS IMPORTANT"
        ]
        
        hashes = [hash_text(text) for text in variations]
        
        # All should produce the same hash
        assert len(set(hashes)) == 1
    
    def test_hash_with_whitespace_variations(self):
        """Test that whitespace variations produce same hash."""
        variations = [
            "hello world",
            "hello   world",
            "  hello world  ",
            "hello\tworld",
            "hello\nworld"
        ]
        
        hashes = [hash_text(text) for text in variations]
        
        # All should produce the same hash
        assert len(set(hashes)) == 1
    
    def test_hash_deterministic(self):
        """Test that hash is deterministic across multiple calls."""
        text = "This is a test message for hashing"
        hashes = [hash_text(text) for _ in range(10)]
        
        # All hashes should be identical
        assert len(set(hashes)) == 1
    
    def test_hash_collision_resistance(self):
        """Test that similar texts produce different hashes."""
        # These are similar but should produce different hashes
        hash1 = hash_text("hello world")
        hash2 = hash_text("hello world!")  # Extra punctuation (removed)
        hash3 = hash_text("hello worlds")  # Extra character
        hash4 = hash_text("helo world")    # Missing character
        
        # hash1 and hash2 should be same (punctuation removed)
        assert hash1 == hash2
        
        # hash3 and hash4 should be different from hash1
        assert hash1 != hash3
        assert hash1 != hash4
        assert hash3 != hash4
