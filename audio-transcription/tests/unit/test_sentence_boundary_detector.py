"""
Unit tests for SentenceBoundaryDetector class.

Tests sentence boundary detection functionality including:
- Punctuation detection (. ? !)
- Pause threshold detection
- Buffer timeout detection
- Final result handling
"""

import time
import pytest
from shared.services.sentence_boundary_detector import SentenceBoundaryDetector
from shared.models.transcription_results import PartialResult, BufferedResult


class TestSentenceBoundaryDetector:
    """Test suite for SentenceBoundaryDetector."""
    
    def test_detector_initialization_with_defaults(self):
        """Test detector initializes with correct default values."""
        detector = SentenceBoundaryDetector()
        
        assert detector.pause_threshold == 2.0
        assert detector.buffer_timeout == 5.0
        assert detector.last_result_time is None
    
    def test_detector_initialization_with_custom_values(self):
        """Test detector accepts custom threshold values."""
        detector = SentenceBoundaryDetector(
            pause_threshold_seconds=3.0,
            buffer_timeout_seconds=7.0
        )
        
        assert detector.pause_threshold == 3.0
        assert detector.buffer_timeout == 7.0
    
    def test_initialization_rejects_negative_pause_threshold(self):
        """Test that negative pause threshold raises ValueError."""
        with pytest.raises(ValueError, match="pause_threshold_seconds must be positive"):
            SentenceBoundaryDetector(pause_threshold_seconds=-1.0)
    
    def test_initialization_rejects_zero_pause_threshold(self):
        """Test that zero pause threshold raises ValueError."""
        with pytest.raises(ValueError, match="pause_threshold_seconds must be positive"):
            SentenceBoundaryDetector(pause_threshold_seconds=0.0)
    
    def test_initialization_rejects_negative_buffer_timeout(self):
        """Test that negative buffer timeout raises ValueError."""
        with pytest.raises(ValueError, match="buffer_timeout_seconds must be positive"):
            SentenceBoundaryDetector(buffer_timeout_seconds=-1.0)
    
    def test_initialization_rejects_zero_buffer_timeout(self):
        """Test that zero buffer timeout raises ValueError."""
        with pytest.raises(ValueError, match="buffer_timeout_seconds must be positive"):
            SentenceBoundaryDetector(buffer_timeout_seconds=0.0)
    
    # Punctuation Detection Tests
    
    def test_detects_period_as_sentence_ending(self):
        """Test that period is detected as sentence ending."""
        detector = SentenceBoundaryDetector()
        
        result = PartialResult(
            result_id='r1',
            text='Hello everyone.',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(result, is_final=False)
        
        assert is_complete is True
    
    def test_detects_question_mark_as_sentence_ending(self):
        """Test that question mark is detected as sentence ending."""
        detector = SentenceBoundaryDetector()
        
        result = PartialResult(
            result_id='r1',
            text='How are you?',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(result, is_final=False)
        
        assert is_complete is True
    
    def test_detects_exclamation_mark_as_sentence_ending(self):
        """Test that exclamation mark is detected as sentence ending."""
        detector = SentenceBoundaryDetector()
        
        result = PartialResult(
            result_id='r1',
            text='That is amazing!',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(result, is_final=False)
        
        assert is_complete is True
    
    def test_detects_punctuation_with_trailing_whitespace(self):
        """Test that punctuation is detected even with trailing whitespace."""
        detector = SentenceBoundaryDetector()
        
        result = PartialResult(
            result_id='r1',
            text='Hello everyone.   ',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(result, is_final=False)
        
        assert is_complete is True
    
    def test_no_punctuation_returns_false(self):
        """Test that text without sentence-ending punctuation returns False."""
        detector = SentenceBoundaryDetector()
        
        result = PartialResult(
            result_id='r1',
            text='Hello everyone',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(result, is_final=False)
        
        assert is_complete is False
    
    def test_comma_not_detected_as_sentence_ending(self):
        """Test that comma is not detected as sentence ending."""
        detector = SentenceBoundaryDetector()
        
        result = PartialResult(
            result_id='r1',
            text='Hello everyone,',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(result, is_final=False)
        
        assert is_complete is False
    
    def test_whitespace_only_text_returns_false(self):
        """Test that whitespace-only text returns False."""
        detector = SentenceBoundaryDetector()
        
        result = PartialResult(
            result_id='r1',
            text='   ',  # Whitespace only
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(result, is_final=False)
        
        assert is_complete is False
    
    # Pause Detection Tests
    
    def test_pause_detected_when_threshold_exceeded(self):
        """Test that pause is detected when threshold is exceeded."""
        detector = SentenceBoundaryDetector(pause_threshold_seconds=1.0)
        
        # Set last result time to 2 seconds ago
        detector.last_result_time = time.time() - 2.0
        
        result = PartialResult(
            result_id='r1',
            text='Hello',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(result, is_final=False)
        
        assert is_complete is True
    
    def test_pause_not_detected_when_below_threshold(self):
        """Test that pause is not detected when below threshold."""
        detector = SentenceBoundaryDetector(pause_threshold_seconds=2.0)
        
        # Set last result time to 1 second ago (below 2 second threshold)
        detector.last_result_time = time.time() - 1.0
        
        result = PartialResult(
            result_id='r1',
            text='Hello',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(result, is_final=False)
        
        assert is_complete is False
    
    def test_pause_not_detected_when_no_previous_result(self):
        """Test that pause is not detected when there's no previous result."""
        detector = SentenceBoundaryDetector(pause_threshold_seconds=1.0)
        
        # last_result_time is None (no previous result)
        result = PartialResult(
            result_id='r1',
            text='Hello',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(result, is_final=False)
        
        assert is_complete is False
    
    def test_update_last_result_time_with_explicit_timestamp(self):
        """Test updating last result time with explicit timestamp."""
        detector = SentenceBoundaryDetector()
        
        test_time = 1234567890.0
        detector.update_last_result_time(test_time)
        
        assert detector.last_result_time == test_time
    
    def test_update_last_result_time_with_current_time(self):
        """Test updating last result time with current time."""
        detector = SentenceBoundaryDetector()
        
        before = time.time()
        detector.update_last_result_time()
        after = time.time()
        
        assert detector.last_result_time is not None
        assert before <= detector.last_result_time <= after
    
    # Buffer Timeout Tests
    
    def test_buffer_timeout_detected_when_exceeded(self):
        """Test that buffer timeout is detected when exceeded."""
        detector = SentenceBoundaryDetector(buffer_timeout_seconds=3.0)
        
        # Create buffered result added 4 seconds ago
        buffered_result = BufferedResult(
            result_id='r1',
            text='Hello',
            stability_score=0.85,
            timestamp=time.time(),
            added_at=time.time() - 4.0,  # 4 seconds ago
            session_id='test-session'
        )
        
        result = PartialResult(
            result_id='r1',
            text='Hello',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(
            result,
            is_final=False,
            buffered_result=buffered_result
        )
        
        assert is_complete is True
    
    def test_buffer_timeout_not_detected_when_below_threshold(self):
        """Test that buffer timeout is not detected when below threshold."""
        detector = SentenceBoundaryDetector(buffer_timeout_seconds=5.0)
        
        # Create buffered result added 3 seconds ago (below 5 second threshold)
        buffered_result = BufferedResult(
            result_id='r1',
            text='Hello',
            stability_score=0.85,
            timestamp=time.time(),
            added_at=time.time() - 3.0,
            session_id='test-session'
        )
        
        result = PartialResult(
            result_id='r1',
            text='Hello',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(
            result,
            is_final=False,
            buffered_result=buffered_result
        )
        
        assert is_complete is False
    
    def test_buffer_timeout_not_checked_without_buffered_result(self):
        """Test that buffer timeout is not checked when buffered_result is None."""
        detector = SentenceBoundaryDetector(buffer_timeout_seconds=1.0)
        
        result = PartialResult(
            result_id='r1',
            text='Hello',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(
            result,
            is_final=False,
            buffered_result=None
        )
        
        assert is_complete is False
    
    # Final Result Tests
    
    def test_final_result_always_complete(self):
        """Test that final results are always considered complete."""
        detector = SentenceBoundaryDetector()
        
        result = PartialResult(
            result_id='r1',
            text='Hello',  # No punctuation
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(result, is_final=True)
        
        assert is_complete is True
    
    def test_final_result_complete_regardless_of_punctuation(self):
        """Test that final results are complete even without punctuation."""
        detector = SentenceBoundaryDetector()
        
        result = PartialResult(
            result_id='r1',
            text='incomplete sentence without',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(result, is_final=True)
        
        assert is_complete is True
    
    def test_final_result_complete_regardless_of_pause(self):
        """Test that final results are complete regardless of pause."""
        detector = SentenceBoundaryDetector(pause_threshold_seconds=10.0)
        
        # Set last result time to just now (no pause)
        detector.last_result_time = time.time()
        
        result = PartialResult(
            result_id='r1',
            text='Hello',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(result, is_final=True)
        
        assert is_complete is True
    
    # Combined Condition Tests
    
    def test_multiple_conditions_met_returns_true(self):
        """Test that sentence is complete when multiple conditions are met."""
        detector = SentenceBoundaryDetector(
            pause_threshold_seconds=1.0,
            buffer_timeout_seconds=3.0
        )
        
        # Set up conditions: punctuation + pause + buffer timeout
        detector.last_result_time = time.time() - 2.0  # Pause exceeded
        
        buffered_result = BufferedResult(
            result_id='r1',
            text='Hello everyone.',
            stability_score=0.85,
            timestamp=time.time(),
            added_at=time.time() - 4.0,  # Buffer timeout exceeded
            session_id='test-session'
        )
        
        result = PartialResult(
            result_id='r1',
            text='Hello everyone.',  # Has punctuation
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(
            result,
            is_final=False,
            buffered_result=buffered_result
        )
        
        assert is_complete is True
    
    def test_no_conditions_met_returns_false(self):
        """Test that sentence is not complete when no conditions are met."""
        detector = SentenceBoundaryDetector(
            pause_threshold_seconds=5.0,
            buffer_timeout_seconds=10.0
        )
        
        # Set up conditions: no punctuation, no pause, no buffer timeout
        detector.last_result_time = time.time() - 1.0  # Below pause threshold
        
        buffered_result = BufferedResult(
            result_id='r1',
            text='Hello everyone',
            stability_score=0.85,
            timestamp=time.time(),
            added_at=time.time() - 2.0,  # Below buffer timeout
            session_id='test-session'
        )
        
        result = PartialResult(
            result_id='r1',
            text='Hello everyone',  # No punctuation
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(
            result,
            is_final=False,
            buffered_result=buffered_result
        )
        
        assert is_complete is False
    
    def test_punctuation_takes_precedence(self):
        """Test that punctuation detection works even without other conditions."""
        detector = SentenceBoundaryDetector(
            pause_threshold_seconds=10.0,  # High threshold
            buffer_timeout_seconds=20.0   # High threshold
        )
        
        # No pause, no buffer timeout, but has punctuation
        detector.last_result_time = time.time()  # Just now
        
        result = PartialResult(
            result_id='r1',
            text='Hello everyone.',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(result, is_final=False)
        
        assert is_complete is True
    
    # Edge Case Tests
    
    def test_exact_pause_threshold_boundary(self):
        """Test behavior at exact pause threshold boundary."""
        detector = SentenceBoundaryDetector(pause_threshold_seconds=2.0)
        
        # Set last result time to exactly 2.0 seconds ago
        detector.last_result_time = time.time() - 2.0
        
        result = PartialResult(
            result_id='r1',
            text='Hello',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(result, is_final=False)
        
        # Should be True (>= threshold)
        assert is_complete is True
    
    def test_exact_buffer_timeout_boundary(self):
        """Test behavior at exact buffer timeout boundary."""
        detector = SentenceBoundaryDetector(buffer_timeout_seconds=5.0)
        
        # Create buffered result added exactly 5.0 seconds ago
        buffered_result = BufferedResult(
            result_id='r1',
            text='Hello',
            stability_score=0.85,
            timestamp=time.time(),
            added_at=time.time() - 5.0,
            session_id='test-session'
        )
        
        result = PartialResult(
            result_id='r1',
            text='Hello',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        is_complete = detector.is_complete_sentence(
            result,
            is_final=False,
            buffered_result=buffered_result
        )
        
        # Should be True (>= threshold)
        assert is_complete is True
