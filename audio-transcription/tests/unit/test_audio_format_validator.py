"""
Unit tests for audio format validator.
"""

import pytest
import struct
from shared.services.audio_format_validator import (
    AudioFormatValidator,
    AudioFormatError,
    AudioFormat
)


class TestAudioFormatValidator:
    """Test suite for AudioFormatValidator."""
    
    def test_validator_initialization(self):
        """Test validator initializes correctly."""
        validator = AudioFormatValidator()
        
        assert validator.EXPECTED_ENCODING == 'pcm'
        assert validator.EXPECTED_SAMPLE_RATE == 16000
        assert validator.EXPECTED_BIT_DEPTH == 16
        assert validator.EXPECTED_CHANNELS == 1
        assert len(validator.validation_cache) == 0
    
    def test_validate_audio_chunk_valid_pcm(self):
        """Test validation passes for valid PCM audio."""
        validator = AudioFormatValidator()
        
        # Create valid PCM 16-bit audio (10 samples)
        audio_bytes = struct.pack('<10h', *range(-5, 5))
        
        is_valid = validator.validate_audio_chunk('conn-123', audio_bytes)
        
        assert is_valid is True
        assert 'conn-123' in validator.validation_cache
    
    def test_validate_audio_chunk_uses_cache(self):
        """Test validation uses cache for subsequent chunks."""
        validator = AudioFormatValidator()
        
        # First chunk - performs validation
        audio_bytes = struct.pack('<10h', *range(-5, 5))
        validator.validate_audio_chunk('conn-123', audio_bytes)
        
        # Second chunk - should use cache
        # We can verify by checking the cache directly
        assert validator.is_format_cached('conn-123') is True
        
        # Validation should still pass
        is_valid = validator.validate_audio_chunk('conn-123', audio_bytes)
        assert is_valid is True
    
    def test_validate_audio_chunk_invalid_byte_length(self):
        """Test validation fails for odd byte length."""
        validator = AudioFormatValidator()
        
        # Odd number of bytes (invalid for 16-bit)
        audio_bytes = b"abc"
        
        with pytest.raises(AudioFormatError, match="Invalid byte length"):
            validator.validate_audio_chunk('conn-123', audio_bytes)
    
    def test_validate_audio_chunk_empty_data(self):
        """Test validation fails for empty data."""
        validator = AudioFormatValidator()
        
        audio_bytes = b""
        
        with pytest.raises(AudioFormatError, match="Empty audio data"):
            validator.validate_audio_chunk('conn-123', audio_bytes)
    
    def test_validate_audio_chunk_force_revalidate(self):
        """Test force revalidation bypasses cache."""
        validator = AudioFormatValidator()
        
        # First validation
        audio_bytes = struct.pack('<10h', *range(-5, 5))
        validator.validate_audio_chunk('conn-123', audio_bytes)
        
        # Cache should exist
        assert validator.is_format_cached('conn-123') is True
        
        # Force revalidation
        is_valid = validator.validate_audio_chunk(
            'conn-123',
            audio_bytes,
            force_revalidate=True
        )
        
        assert is_valid is True
    
    def test_get_cached_format(self):
        """Test getting cached format."""
        validator = AudioFormatValidator()
        
        audio_bytes = struct.pack('<10h', *range(-5, 5))
        validator.validate_audio_chunk('conn-123', audio_bytes)
        
        cached_format = validator.get_cached_format('conn-123')
        
        assert cached_format is not None
        assert isinstance(cached_format, AudioFormat)
        assert cached_format.encoding == 'pcm'
        assert cached_format.bit_depth == 16
    
    def test_get_cached_format_not_cached(self):
        """Test getting cached format when not cached."""
        validator = AudioFormatValidator()
        
        cached_format = validator.get_cached_format('conn-999')
        
        assert cached_format is None
    
    def test_is_format_cached(self):
        """Test checking if format is cached."""
        validator = AudioFormatValidator()
        
        assert validator.is_format_cached('conn-123') is False
        
        audio_bytes = struct.pack('<10h', *range(-5, 5))
        validator.validate_audio_chunk('conn-123', audio_bytes)
        
        assert validator.is_format_cached('conn-123') is True
    
    def test_clear_cache(self):
        """Test clearing cache for connection."""
        validator = AudioFormatValidator()
        
        audio_bytes = struct.pack('<10h', *range(-5, 5))
        validator.validate_audio_chunk('conn-123', audio_bytes)
        
        assert validator.is_format_cached('conn-123') is True
        
        validator.clear_cache('conn-123')
        
        assert validator.is_format_cached('conn-123') is False
    
    def test_clear_all_cache(self):
        """Test clearing all cache."""
        validator = AudioFormatValidator()
        
        audio_bytes = struct.pack('<10h', *range(-5, 5))
        validator.validate_audio_chunk('conn-123', audio_bytes)
        validator.validate_audio_chunk('conn-456', audio_bytes)
        
        assert len(validator.validation_cache) == 2
        
        validator.clear_all_cache()
        
        assert len(validator.validation_cache) == 0
    
    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        validator = AudioFormatValidator()
        
        audio_bytes = struct.pack('<10h', *range(-5, 5))
        validator.validate_audio_chunk('conn-123', audio_bytes)
        validator.validate_audio_chunk('conn-456', audio_bytes)
        
        stats = validator.get_cache_stats()
        
        assert stats['cached_connections'] == 2
        assert stats['valid_connections'] == 2
        assert stats['invalid_connections'] == 0
    
    def test_detect_format_valid_samples(self):
        """Test format detection with valid samples."""
        validator = AudioFormatValidator()
        
        # Create audio with samples in valid range
        audio_bytes = struct.pack('<5h', -1000, -500, 0, 500, 1000)
        
        audio_format = validator._detect_format(audio_bytes)
        
        assert audio_format.encoding == 'pcm'
        assert audio_format.bit_depth == 16
        assert audio_format.channels == 1
        assert audio_format.sample_rate == 16000
