"""
Rate limiter for partial result processing.

This module implements a sliding window rate limiter that restricts partial result
processing to a maximum of 5 results per second. When the rate limit is exceeded,
the limiter buffers results in 200ms windows and selects the best result (highest
stability score) from each window.
"""

import json
import logging
import time
from typing import List, Optional
from shared.models.transcription_results import PartialResult

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter using sliding window approach.
    
    Limits partial result processing to max_rate per second by buffering results
    in windows and selecting the best result from each window based on stability score.
    """
    
    def __init__(self, max_rate: int = 5, window_ms: int = 200, metrics_emitter=None):
        """
        Initialize rate limiter.
        
        Args:
            max_rate: Maximum results to process per second (default: 5)
            window_ms: Window size in milliseconds (default: 200)
            metrics_emitter: Optional metrics emitter for CloudWatch metrics
        """
        self.max_rate = max_rate
        self.window_ms = window_ms
        self.window_buffer: List[PartialResult] = []
        self.last_window_start: float = 0
        self.processed_count = 0
        self.dropped_count = 0
        self.metrics_emitter = metrics_emitter
    
    def should_process(self, result: PartialResult) -> bool:
        """
        Determine if result should be processed based on rate limit.
        
        Buffers results in windows and returns True only for the best result
        in each window (highest stability score).
        
        Args:
            result: Partial result to check
            
        Returns:
            True if result should be processed, False if buffered/dropped
        """
        current_time = time.time()
        window_duration_seconds = self.window_ms / 1000.0
        
        # Check if we're starting a new window
        if (current_time - self.last_window_start) >= window_duration_seconds:
            # Process best result from previous window if any
            if self.window_buffer:
                best_result = self.get_best_result_in_window()
                # Clear buffer for new window
                self.window_buffer = []
                self.last_window_start = current_time
                
                # Track dropped results
                dropped = len(self.window_buffer)
                if dropped > 0:
                    self.dropped_count += dropped
                
                # Add current result to new window
                self.window_buffer.append(result)
                
                # Return True only if current result is the best from previous window
                # (This shouldn't happen as we cleared the buffer, but for safety)
                return False
            else:
                # First result in new window
                self.last_window_start = current_time
                self.window_buffer.append(result)
                return False
        
        # Add to current window
        self.window_buffer.append(result)
        return False
    
    def get_best_result_in_window(self) -> Optional[PartialResult]:
        """
        Get highest stability result from current window.
        
        Selects result with highest stability score. If multiple results have
        the same stability, selects the most recent (highest timestamp).
        Treats missing stability scores as 0.
        
        Returns:
            Result with highest stability score, or None if buffer empty
        """
        if not self.window_buffer:
            return None
        
        # Sort by stability (descending), then by timestamp (most recent)
        # Treat None stability as 0
        sorted_results = sorted(
            self.window_buffer,
            key=lambda r: (r.stability_score if r.stability_score is not None else 0.0, r.timestamp),
            reverse=True
        )
        
        return sorted_results[0]
    
    def flush_window(self) -> Optional[PartialResult]:
        """
        Flush current window and return best result.
        
        This should be called at the end of each window to process the best
        result and prepare for the next window.
        
        Returns:
            Best result from window, or None if buffer empty
        """
        if not self.window_buffer:
            return None
        
        best_result = self.get_best_result_in_window()
        
        # Track statistics
        dropped = len(self.window_buffer) - 1  # All except best
        if dropped > 0:
            self.dropped_count += dropped
            # Log dropped results at WARNING level
            logger.warning(json.dumps({
                'event': 'rate_limit_dropped_results',
                'dropped_count': dropped,
                'window_size': len(self.window_buffer),
                'best_stability': best_result.stability_score if best_result else None,
                'session_id': best_result.session_id if best_result else None
            }))
            
            # Emit metric for dropped results
            if self.metrics_emitter and best_result:
                self.metrics_emitter.emit_dropped_results(
                    best_result.session_id,
                    dropped
                )
        
        if best_result:
            self.processed_count += 1
        
        # Clear buffer
        self.window_buffer = []
        
        return best_result
    
    def get_statistics(self) -> dict:
        """
        Get rate limiter statistics.
        
        Returns:
            Dictionary with processed_count and dropped_count
        """
        return {
            'processed_count': self.processed_count,
            'dropped_count': self.dropped_count,
            'current_window_size': len(self.window_buffer)
        }
    
    def reset_statistics(self) -> None:
        """Reset statistics counters."""
        self.processed_count = 0
        self.dropped_count = 0
