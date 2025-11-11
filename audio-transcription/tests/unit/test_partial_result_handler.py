"""
Unit tests for PartialResultHandler.

This module tests the partial result handler's processing logic including
rate limiting, stability filtering, buffering, and forwarding.
"""

import time
import pytest
from unittest.mock import Mock, MagicMock
from shared.models.configuration import PartialResultConfig
from shared.models.transcription_results import PartialResult, BufferedResult
from shared.services.partial_result_handler import PartialResultHandler
from shared.services.rate_limiter import RateLimiter
from shared.services.result_buffer import ResultBuffer
from shared.services.sentence_boundary_detector import SentenceBoundaryDetector
from shared.services.translation_forwarder import TranslationForwarder


class TestPartialResultHandler:
    """Test suite for PartialResultHandler."""
    
    @pytest.fixture
    def config(self):
        """Create default configuration."""
        return PartialResultConfig(
            enabled=True,
            min_stability_threshold=0.85,
            max_buffer_timeout_seconds=5.0,
            pause_threshold_seconds=2.0,
            orphan_timeout_seconds=15.0,
            max_rate_per_second=5,
            dedup_cache_ttl_seconds=10
        )
    
    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter."""
        return RateLimiter(max_rate=5, window_ms=200)
    
    @pytest.fixture
    def result_buffer(self):
        """Create result buffer."""
        return ResultBuffer(max_capacity_seconds=10)
    
    @pytest.fixture
    def sentence_detector(self):
        """Create sentence boundary detector."""
        return SentenceBoundaryDetector(
            pause_threshold_seconds=2.0,
            buffer_timeout_seconds=5.0
        )
    
    @pytest.fixture
    def translation_forwarder(self):
        """Create mock translation forwarder."""
        forwarder = Mock(spec=TranslationForwarder)
        forwarder.forward = Mock(return_value=True)
        return forwarder
    
    @pytest.fixture
    def handler(self, config, rate_limiter, result_buffer, sentence_detector, translation_forwarder):
        """Create partial result handler."""
        return PartialResultHandler(
            config=config,
            rate_limiter=rate_limiter,
            result_buffer=result_buffer,
            sentence_detector=sentence_detector,
            translation_forwarder=translation_forwarder
        )
    
    @pytest.fixture
    def partial_result(self):
        """Create sample partial result."""
        return PartialResult(
            result_id='result-123',
            text='Hello everyone',
            stability_score=0.92,
            timestamp=time.time(),
            session_id='session-123',
            source_language='en'
        )
    
    def test_handler_initialization(self, handler, config):
        """Test handler initializes correctly."""
        assert handler.config == config
        assert handler.rate_limiter is not None
        assert handler.result_buffer is not None
        assert handler.sentence_detector is not None
        assert handler.translation_forwarder is not None
    
    def test_handler_initialization_validates_config(
        self,
        rate_limiter,
        result_buffer,
        sentence_detector,
        translation_forwarder
    ):
        """Test handler validates configuration on initialization."""
        # Config validation happens in __post_init__, so we catch it there
        with pytest.raises(ValueError, match="min_stability_threshold must be between"):
            invalid_config = PartialResultConfig(
                min_stability_threshold=1.5  # Invalid: > 0.95
            )
    
    def test_process_with_high_stability_and_complete_sentence(
        self,
        handler,
        partial_result,
        translation_forwarder
    ):
        """Test processing result with high stability and complete sentence."""
        # Make it a complete sentence
        partial_result.text = 'Hello everyone.'
        
        # Process result
        handler.process(partial_result)
        
        # Verify forwarded to translation
        translation_forwarder.forward.assert_called_once_with(
            text='Hello everyone.',
            session_id='session-123',
            source_language='en'
        )
        
        # Verify added to buffer
        assert handler.result_buffer.size() == 1
        
        # Verify marked as forwarded
        buffered = handler.result_buffer.get_by_id('result-123')
        assert buffered.forwarded is True
    
    def test_process_with_high_stability_incomplete_sentence(
        self,
        handler,
        partial_result,
        translation_forwarder
    ):
        """Test processing result with high stability but incomplete sentence."""
        # Incomplete sentence (no punctuation)
        partial_result.text = 'Hello everyone'
        
        # Process result
        handler.process(partial_result)
        
        # Verify NOT forwarded to translation
        translation_forwarder.forward.assert_not_called()
        
        # Verify added to buffer
        assert handler.result_buffer.size() == 1
        
        # Verify NOT marked as forwarded
        buffered = handler.result_buffer.get_by_id('result-123')
        assert buffered.forwarded is False
    
    def test_process_with_low_stability(
        self,
        handler,
        partial_result,
        translation_forwarder
    ):
        """Test processing result with low stability score."""
        # Low stability
        partial_result.stability_score = 0.70
        partial_result.text = 'Hello everyone.'
        
        # Process result
        handler.process(partial_result)
        
        # Verify NOT forwarded to translation
        translation_forwarder.forward.assert_not_called()
        
        # Verify added to buffer
        assert handler.result_buffer.size() == 1
    
    def test_process_with_none_stability_uses_timeout_fallback(
        self,
        handler,
        partial_result,
        translation_forwarder
    ):
        """Test processing result with missing stability uses timeout fallback."""
        # No stability score
        partial_result.stability_score = None
        partial_result.text = 'Hello everyone.'
        
        # First process - should buffer (not old enough)
        handler.process(partial_result)
        translation_forwarder.forward.assert_not_called()
        
        # Simulate 3+ seconds passing
        buffered = handler.result_buffer.get_by_id('result-123')
        buffered.added_at = time.time() - 3.5
        
        # Process again - should forward now
        handler.process(partial_result)
        translation_forwarder.forward.assert_called_once()
    
    def test_process_updates_sentence_detector_after_forwarding(
        self,
        handler,
        partial_result,
        sentence_detector
    ):
        """Test that sentence detector is updated after forwarding."""
        # Complete sentence with high stability
        partial_result.text = 'Hello everyone.'
        partial_result.timestamp = 1234567890.0
        
        # Process result
        handler.process(partial_result)
        
        # Verify sentence detector was updated
        assert sentence_detector.last_result_time == 1234567890.0
    
    def test_process_handles_duplicate_text(
        self,
        handler,
        partial_result,
        translation_forwarder
    ):
        """Test processing handles duplicate text correctly."""
        # Complete sentence
        partial_result.text = 'Hello everyone.'
        
        # Mock forwarder to return False (duplicate)
        translation_forwarder.forward.return_value = False
        
        # Process result
        handler.process(partial_result)
        
        # Verify forward was called
        translation_forwarder.forward.assert_called_once()
        
        # Verify NOT marked as forwarded (since it was duplicate)
        buffered = handler.result_buffer.get_by_id('result-123')
        assert buffered.forwarded is False
    
    def test_process_with_pause_detected(
        self,
        handler,
        partial_result,
        sentence_detector,
        translation_forwarder
    ):
        """Test processing with pause detection."""
        # Set last result time to 3 seconds ago
        sentence_detector.last_result_time = time.time() - 3.0
        
        # Incomplete sentence (no punctuation)
        partial_result.text = 'Hello everyone'
        
        # Process result
        handler.process(partial_result)
        
        # Verify forwarded due to pause
        translation_forwarder.forward.assert_called_once()
    
    def test_process_with_buffer_timeout(
        self,
        handler,
        partial_result,
        translation_forwarder,
        sentence_detector
    ):
        """Test processing with buffer timeout."""
        # Incomplete sentence
        partial_result.text = 'Hello everyone'
        
        # First process - should buffer
        handler.process(partial_result)
        translation_forwarder.forward.assert_not_called()
        
        # Simulate 5+ seconds passing (buffer timeout)
        buffered = handler.result_buffer.get_by_id('result-123')
        buffered.added_at = time.time() - 5.5
        
        # Mock sentence detector to return True (timeout detected)
        sentence_detector.is_complete_sentence = Mock(return_value=True)
        
        # Create a new result with same ID to trigger the check
        # (in real scenario, this would be the same result being re-evaluated)
        new_result = PartialResult(
            result_id='result-123',
            text='Hello everyone',
            stability_score=0.92,
            timestamp=time.time(),
            session_id='session-123',
            source_language='en'
        )
        
        # Process again - should forward due to timeout
        handler.process(new_result)
        translation_forwarder.forward.assert_called_once()
    
    def test_should_forward_based_on_stability_with_valid_score(self, handler):
        """Test stability check with valid score."""
        result = PartialResult(
            result_id='r1',
            text='test',
            stability_score=0.90,
            timestamp=time.time(),
            session_id='s1',
            source_language='en'
        )
        
        assert handler._should_forward_based_on_stability(result) is True
    
    def test_should_forward_based_on_stability_below_threshold(self, handler):
        """Test stability check with score below threshold."""
        result = PartialResult(
            result_id='r1',
            text='test',
            stability_score=0.80,
            timestamp=time.time(),
            session_id='s1',
            source_language='en'
        )
        
        assert handler._should_forward_based_on_stability(result) is False
    
    def test_should_forward_based_on_stability_at_threshold(self, handler):
        """Test stability check with score exactly at threshold."""
        result = PartialResult(
            result_id='r1',
            text='test',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='s1',
            source_language='en'
        )
        
        assert handler._should_forward_based_on_stability(result) is True
    
    def test_should_forward_based_on_stability_none_not_in_buffer(self, handler):
        """Test stability check with None score and result not in buffer."""
        result = PartialResult(
            result_id='r1',
            text='test',
            stability_score=None,
            timestamp=time.time(),
            session_id='s1',
            source_language='en'
        )
        
        assert handler._should_forward_based_on_stability(result) is False
    
    def test_is_complete_sentence_delegates_to_detector(
        self,
        handler,
        partial_result,
        sentence_detector
    ):
        """Test that sentence completion check delegates to detector."""
        # Mock the detector
        sentence_detector.is_complete_sentence = Mock(return_value=True)
        
        # Check sentence completion
        result = handler._is_complete_sentence(partial_result, None)
        
        # Verify detector was called
        sentence_detector.is_complete_sentence.assert_called_once_with(
            result=partial_result,
            is_final=False,
            buffered_result=None
        )
        
        assert result is True
    
    def test_forward_to_translation_success(
        self,
        handler,
        partial_result,
        translation_forwarder
    ):
        """Test successful forwarding to translation."""
        # Add to buffer first
        handler.result_buffer.add(partial_result)
        
        # Forward
        handler._forward_to_translation(partial_result)
        
        # Verify forwarded
        translation_forwarder.forward.assert_called_once_with(
            text='Hello everyone',
            session_id='session-123',
            source_language='en'
        )
        
        # Verify marked as forwarded
        buffered = handler.result_buffer.get_by_id('result-123')
        assert buffered.forwarded is True
    
    def test_forward_to_translation_duplicate_skipped(
        self,
        handler,
        partial_result,
        translation_forwarder
    ):
        """Test forwarding skips duplicates."""
        # Add to buffer first
        handler.result_buffer.add(partial_result)
        
        # Mock forwarder to return False (duplicate)
        translation_forwarder.forward.return_value = False
        
        # Forward
        handler._forward_to_translation(partial_result)
        
        # Verify forward was attempted
        translation_forwarder.forward.assert_called_once()
        
        # Verify NOT marked as forwarded
        buffered = handler.result_buffer.get_by_id('result-123')
        assert buffered.forwarded is False
