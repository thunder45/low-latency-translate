"""
Unit tests for transcription data models.

Tests validation logic for PartialResult, FinalResult, BufferedResult,
PartialResultConfig, and CacheEntry dataclasses.
"""

import time
import pytest
from shared.models import (
    PartialResult,
    FinalResult,
    BufferedResult,
    ResultMetadata,
    PartialResultConfig,
    CacheEntry
)


class TestPartialResult:
    """Test suite for PartialResult dataclass."""
    
    def test_create_valid_partial_result(self):
        """Test creating a valid partial result."""
        result = PartialResult(
            result_id='result-123',
            text='hello everyone',
            stability_score=0.92,
            timestamp=time.time(),
            session_id='session-456',
            source_language='en'
        )
        
        assert result.result_id == 'result-123'
        assert result.text == 'hello everyone'
        assert result.stability_score == 0.92
        assert result.is_partial is True
        assert result.session_id == 'session-456'
        assert result.source_language == 'en'
    
    def test_partial_result_with_none_stability(self):
        """Test partial result with missing stability score."""
        result = PartialResult(
            result_id='result-123',
            text='hello',
            stability_score=None,
            timestamp=time.time()
        )
        
        assert result.stability_score is None
    
    def test_partial_result_empty_result_id_fails(self):
        """Test that empty result_id raises ValueError."""
        with pytest.raises(ValueError, match='result_id cannot be empty'):
            PartialResult(
                result_id='',
                text='hello',
                stability_score=0.9,
                timestamp=time.time()
            )
    
    def test_partial_result_empty_text_fails(self):
        """Test that empty text raises ValueError."""
        with pytest.raises(ValueError, match='text cannot be empty'):
            PartialResult(
                result_id='result-123',
                text='',
                stability_score=0.9,
                timestamp=time.time()
            )
    
    def test_partial_result_invalid_stability_score_fails(self):
        """Test that stability score outside 0.0-1.0 raises ValueError."""
        with pytest.raises(ValueError, match='stability_score must be between 0.0 and 1.0'):
            PartialResult(
                result_id='result-123',
                text='hello',
                stability_score=1.5,
                timestamp=time.time()
            )
        
        with pytest.raises(ValueError, match='stability_score must be between 0.0 and 1.0'):
            PartialResult(
                result_id='result-123',
                text='hello',
                stability_score=-0.1,
                timestamp=time.time()
            )
    
    def test_partial_result_invalid_timestamp_fails(self):
        """Test that non-positive timestamp raises ValueError."""
        with pytest.raises(ValueError, match='timestamp must be positive'):
            PartialResult(
                result_id='result-123',
                text='hello',
                stability_score=0.9,
                timestamp=0
            )
        
        with pytest.raises(ValueError, match='timestamp must be positive'):
            PartialResult(
                result_id='result-123',
                text='hello',
                stability_score=0.9,
                timestamp=-1.0
            )
    
    def test_partial_result_invalid_language_code_fails(self):
        """Test that invalid language code raises ValueError."""
        with pytest.raises(ValueError, match='source_language must be 2-character ISO 639-1 code'):
            PartialResult(
                result_id='result-123',
                text='hello',
                stability_score=0.9,
                timestamp=time.time(),
                source_language='eng'  # Should be 'en'
            )


class TestFinalResult:
    """Test suite for FinalResult dataclass."""
    
    def test_create_valid_final_result(self):
        """Test creating a valid final result."""
        result = FinalResult(
            result_id='result-456',
            text='hello everyone this is important',
            timestamp=time.time(),
            session_id='session-789',
            source_language='en',
            replaces_result_ids=['result-123', 'result-124']
        )
        
        assert result.result_id == 'result-456'
        assert result.text == 'hello everyone this is important'
        assert result.is_partial is False
        assert result.session_id == 'session-789'
        assert result.source_language == 'en'
        assert len(result.replaces_result_ids) == 2
    
    def test_final_result_empty_result_id_fails(self):
        """Test that empty result_id raises ValueError."""
        with pytest.raises(ValueError, match='result_id cannot be empty'):
            FinalResult(
                result_id='',
                text='hello',
                timestamp=time.time()
            )
    
    def test_final_result_empty_text_fails(self):
        """Test that empty text raises ValueError."""
        with pytest.raises(ValueError, match='text cannot be empty'):
            FinalResult(
                result_id='result-456',
                text='',
                timestamp=time.time()
            )
    
    def test_final_result_invalid_timestamp_fails(self):
        """Test that non-positive timestamp raises ValueError."""
        with pytest.raises(ValueError, match='timestamp must be positive'):
            FinalResult(
                result_id='result-456',
                text='hello',
                timestamp=0
            )


class TestBufferedResult:
    """Test suite for BufferedResult dataclass."""
    
    def test_create_valid_buffered_result(self):
        """Test creating a valid buffered result."""
        now = time.time()
        result = BufferedResult(
            result_id='result-123',
            text='hello',
            stability_score=0.85,
            timestamp=now,
            added_at=now + 0.1,
            forwarded=False,
            session_id='session-456'
        )
        
        assert result.result_id == 'result-123'
        assert result.text == 'hello'
        assert result.stability_score == 0.85
        assert result.forwarded is False
        assert result.session_id == 'session-456'
    
    def test_buffered_result_invalid_added_at_fails(self):
        """Test that non-positive added_at raises ValueError."""
        with pytest.raises(ValueError, match='added_at must be positive'):
            BufferedResult(
                result_id='result-123',
                text='hello',
                stability_score=0.85,
                timestamp=time.time(),
                added_at=0
            )


class TestResultMetadata:
    """Test suite for ResultMetadata dataclass."""
    
    def test_create_valid_result_metadata(self):
        """Test creating valid result metadata."""
        metadata = ResultMetadata(
            is_partial=True,
            stability_score=0.92,
            text='hello everyone',
            result_id='result-123',
            timestamp=time.time(),
            alternatives=['hello every one', 'hello everyone']
        )
        
        assert metadata.is_partial is True
        assert metadata.stability_score == 0.92
        assert metadata.text == 'hello everyone'
        assert len(metadata.alternatives) == 2
    
    def test_result_metadata_empty_result_id_fails(self):
        """Test that empty result_id raises ValueError."""
        with pytest.raises(ValueError, match='result_id cannot be empty'):
            ResultMetadata(
                is_partial=True,
                stability_score=0.92,
                text='hello',
                result_id='',
                timestamp=time.time()
            )


class TestPartialResultConfig:
    """Test suite for PartialResultConfig dataclass."""
    
    def test_create_valid_config_with_defaults(self):
        """Test creating config with default values."""
        config = PartialResultConfig()
        
        assert config.enabled is True
        assert config.min_stability_threshold == 0.85
        assert config.max_buffer_timeout_seconds == 5.0
        assert config.pause_threshold_seconds == 2.0
        assert config.orphan_timeout_seconds == 15.0
        assert config.max_rate_per_second == 5
        assert config.dedup_cache_ttl_seconds == 10
    
    def test_create_valid_config_with_custom_values(self):
        """Test creating config with custom values."""
        config = PartialResultConfig(
            enabled=False,
            min_stability_threshold=0.90,
            max_buffer_timeout_seconds=7.0,
            pause_threshold_seconds=3.0,
            orphan_timeout_seconds=20.0,
            max_rate_per_second=10,
            dedup_cache_ttl_seconds=15
        )
        
        assert config.enabled is False
        assert config.min_stability_threshold == 0.90
        assert config.max_buffer_timeout_seconds == 7.0
    
    def test_config_invalid_stability_threshold_fails(self):
        """Test that stability threshold outside 0.70-0.95 raises ValueError."""
        with pytest.raises(ValueError, match='min_stability_threshold must be between 0.70 and 0.95'):
            PartialResultConfig(min_stability_threshold=0.65)
        
        with pytest.raises(ValueError, match='min_stability_threshold must be between 0.70 and 0.95'):
            PartialResultConfig(min_stability_threshold=0.96)
    
    def test_config_invalid_buffer_timeout_fails(self):
        """Test that buffer timeout outside 2-10 raises ValueError."""
        with pytest.raises(ValueError, match='max_buffer_timeout_seconds must be between 2 and 10'):
            PartialResultConfig(max_buffer_timeout_seconds=1.5)
        
        with pytest.raises(ValueError, match='max_buffer_timeout_seconds must be between 2 and 10'):
            PartialResultConfig(max_buffer_timeout_seconds=11.0)
    
    def test_config_negative_pause_threshold_fails(self):
        """Test that negative pause threshold raises ValueError."""
        with pytest.raises(ValueError, match='pause_threshold_seconds must be non-negative'):
            PartialResultConfig(pause_threshold_seconds=-1.0)
    
    def test_config_negative_orphan_timeout_fails(self):
        """Test that negative orphan timeout raises ValueError."""
        with pytest.raises(ValueError, match='orphan_timeout_seconds must be non-negative'):
            PartialResultConfig(orphan_timeout_seconds=-5.0)
    
    def test_config_invalid_max_rate_fails(self):
        """Test that max_rate_per_second < 1 raises ValueError."""
        with pytest.raises(ValueError, match='max_rate_per_second must be at least 1'):
            PartialResultConfig(max_rate_per_second=0)
    
    def test_config_invalid_cache_ttl_fails(self):
        """Test that dedup_cache_ttl_seconds < 1 raises ValueError."""
        with pytest.raises(ValueError, match='dedup_cache_ttl_seconds must be at least 1'):
            PartialResultConfig(dedup_cache_ttl_seconds=0)
    
    def test_config_validate_method(self):
        """Test explicit validate() method call."""
        config = PartialResultConfig()
        config.validate()  # Should not raise
        
        config.min_stability_threshold = 0.60
        with pytest.raises(ValueError):
            config.validate()


class TestCacheEntry:
    """Test suite for CacheEntry dataclass."""
    
    def test_create_valid_cache_entry(self):
        """Test creating a valid cache entry."""
        now = time.time()
        entry = CacheEntry(
            text_hash='abc123def456',
            added_at=now,
            ttl_seconds=10
        )
        
        assert entry.text_hash == 'abc123def456'
        assert entry.added_at == now
        assert entry.ttl_seconds == 10
    
    def test_cache_entry_empty_hash_fails(self):
        """Test that empty text_hash raises ValueError."""
        with pytest.raises(ValueError, match='text_hash cannot be empty'):
            CacheEntry(
                text_hash='',
                added_at=time.time()
            )
    
    def test_cache_entry_invalid_added_at_fails(self):
        """Test that non-positive added_at raises ValueError."""
        with pytest.raises(ValueError, match='added_at must be positive'):
            CacheEntry(
                text_hash='abc123',
                added_at=0
            )
    
    def test_cache_entry_invalid_ttl_fails(self):
        """Test that ttl_seconds < 1 raises ValueError."""
        with pytest.raises(ValueError, match='ttl_seconds must be at least 1'):
            CacheEntry(
                text_hash='abc123',
                added_at=time.time(),
                ttl_seconds=0
            )
    
    def test_cache_entry_is_expired(self):
        """Test is_expired() method."""
        # Create entry that's already expired
        old_time = time.time() - 20  # 20 seconds ago
        entry = CacheEntry(
            text_hash='abc123',
            added_at=old_time,
            ttl_seconds=10
        )
        
        assert entry.is_expired() is True
    
    def test_cache_entry_not_expired(self):
        """Test is_expired() returns False for fresh entry."""
        now = time.time()
        entry = CacheEntry(
            text_hash='abc123',
            added_at=now,
            ttl_seconds=10
        )
        
        assert entry.is_expired() is False
