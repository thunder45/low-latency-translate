"""
Sentence boundary detection for partial transcription results.

This module provides the SentenceBoundaryDetector class which determines
when partial results form complete sentences based on punctuation, pauses,
and buffer timeouts.
"""

import time
from typing import Optional
from shared.models.transcription_results import PartialResult, BufferedResult


class SentenceBoundaryDetector:
    """
    Detects sentence boundaries in transcription results.
    
    This class determines when partial results should be considered complete
    sentences and forwarded to translation. It uses multiple detection methods:
    - Sentence-ending punctuation (. ? !)
    - Pause detection (2+ seconds since last result)
    - Buffer timeout (5 seconds since first buffered result)
    - Final results (always complete)
    
    Attributes:
        pause_threshold: Seconds of silence to trigger sentence boundary (default: 2.0)
        buffer_timeout: Maximum seconds to buffer before forcing completion (default: 5.0)
        last_result_time: Timestamp of last processed result (None initially)
    """
    
    def __init__(
        self,
        pause_threshold_seconds: float = 2.0,
        buffer_timeout_seconds: float = 5.0
    ):
        """
        Initialize sentence boundary detector.
        
        Args:
            pause_threshold_seconds: Pause duration to trigger sentence boundary (default: 2.0)
            buffer_timeout_seconds: Maximum time to buffer results (default: 5.0)
        
        Raises:
            ValueError: If thresholds are not positive
        """
        if pause_threshold_seconds <= 0:
            raise ValueError(f"pause_threshold_seconds must be positive, got {pause_threshold_seconds}")
        
        if buffer_timeout_seconds <= 0:
            raise ValueError(f"buffer_timeout_seconds must be positive, got {buffer_timeout_seconds}")
        
        self.pause_threshold = pause_threshold_seconds
        self.buffer_timeout = buffer_timeout_seconds
        self.last_result_time: Optional[float] = None
    
    def is_complete_sentence(
        self,
        result: PartialResult,
        is_final: bool,
        buffered_result: Optional[BufferedResult] = None
    ) -> bool:
        """
        Determine if result represents a complete sentence.
        
        A sentence is considered complete if any of these conditions are met:
        1. Result is a final result (is_final=True)
        2. Text ends with sentence-ending punctuation (. ? !)
        3. Pause detected (2+ seconds since last result)
        4. Buffer timeout (5 seconds since first buffered result)
        
        Args:
            result: Partial result to check
            is_final: Whether this is a final result
            buffered_result: Optional buffered result with added_at timestamp
        
        Returns:
            True if sentence is complete and should be forwarded
        """
        # Condition 1: Final result (always complete)
        if is_final:
            return True
        
        # Condition 2: Ends with sentence punctuation
        if self._has_sentence_ending_punctuation(result.text):
            return True
        
        # Condition 3: Pause detected (2+ seconds since last result)
        current_time = time.time()
        if self._pause_detected(current_time):
            return True
        
        # Condition 4: Buffer timeout (5 seconds since first buffered result)
        if buffered_result and self._buffer_timeout_exceeded(buffered_result.added_at, current_time):
            return True
        
        return False
    
    def update_last_result_time(self, timestamp: Optional[float] = None) -> None:
        """
        Update the timestamp of the last processed result.
        
        This should be called after processing each result to track pauses.
        
        Args:
            timestamp: Timestamp to set (defaults to current time)
        """
        self.last_result_time = timestamp if timestamp is not None else time.time()
    
    def _has_sentence_ending_punctuation(self, text: str) -> bool:
        """
        Check if text ends with sentence-ending punctuation.
        
        Checks for period (.), question mark (?), or exclamation point (!).
        
        Args:
            text: Text to check
        
        Returns:
            True if text ends with . ? or !
        """
        if not text:
            return False
        
        # Strip trailing whitespace before checking
        text = text.rstrip()
        
        return text.endswith(('.', '?', '!'))
    
    def _pause_detected(self, current_time: float) -> bool:
        """
        Check if pause exceeds threshold since last result.
        
        Args:
            current_time: Current timestamp
        
        Returns:
            True if pause >= pause_threshold seconds
        """
        if self.last_result_time is None:
            return False
        
        pause_duration = current_time - self.last_result_time
        return pause_duration >= self.pause_threshold
    
    def _buffer_timeout_exceeded(self, added_at: float, current_time: float) -> bool:
        """
        Check if buffer timeout has been exceeded.
        
        Args:
            added_at: Timestamp when result was added to buffer
            current_time: Current timestamp
        
        Returns:
            True if time since added_at >= buffer_timeout
        """
        buffer_duration = current_time - added_at
        return buffer_duration >= self.buffer_timeout
