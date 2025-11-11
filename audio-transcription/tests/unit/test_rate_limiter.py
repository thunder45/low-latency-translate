"""
Unit tests for RateLimiter class.

Tests rate limiting functionality including:
- Rate limit enforcement (5 per second)
- Best result selection with varying stability scores
- Window reset behavior
- Handling of missing stability scores
"""

import time
import pytest
from shared.services.rate_limiter import RateLimiter
from shared.models.transcription_results import PartialResult


class TestRateLimiter:
    """Test suite for RateLimiter."""
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter initializes with correct defaults."""
        limiter = RateLimiter()
        
        assert limiter.max_rate == 5
        assert limiter.window_ms == 200
        assert limiter.window_buffer == []
        assert limiter.processed_count == 0
        assert limiter.dropped_count == 0
    
    def test_rate_limiter_custom_configuration(self):
        """Test rate limiter accepts custom configuration."""
        limiter = RateLimiter(max_rate=10, window_ms=100)
        
        assert limiter.max_rate == 10
        assert limiter.window_ms == 100
    
    def test_should_process_buffers_results_in_window(self):
        """Test that results are buffered within a window."""
        limiter = RateLimiter(max_rate=5, window_ms=200)
        
        result1 = PartialResult(
            result_id='r1',
            text='hello',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        # First result should be buffered
        should_process = limiter.should_process(result1)
        assert should_process is False
        assert len(limiter.window_buffer) == 1
    
    def test_get_best_result_selects_highest_stability(self):
        """Test that best result selection chooses highest stability score."""
        limiter = RateLimiter()
        
        # Add results with different stability scores
        results = [
            PartialResult(
                result_id=f'r{i}',
                text=f'text{i}',
                stability_score=0.70 + i * 0.05,
                timestamp=time.time(),
                session_id='test-session'
            )
            for i in range(5)
        ]
        
        for result in results:
            limiter.window_buffer.append(result)
        
        best = limiter.get_best_result_in_window()
        
        assert best is not None
        assert best.result_id == 'r4'  # Highest stability (0.90)
        assert abs(best.stability_score - 0.90) < 0.001  # Floating point comparison
    
    def test_get_best_result_handles_tie_with_timestamp(self):
        """Test that ties in stability are broken by most recent timestamp."""
        limiter = RateLimiter()
        
        base_time = time.time()
        
        # Add results with same stability but different timestamps
        result1 = PartialResult(
            result_id='r1',
            text='text1',
            stability_score=0.85,
            timestamp=base_time,
            session_id='test-session'
        )
        
        result2 = PartialResult(
            result_id='r2',
            text='text2',
            stability_score=0.85,
            timestamp=base_time + 0.1,  # More recent
            session_id='test-session'
        )
        
        limiter.window_buffer.extend([result1, result2])
        
        best = limiter.get_best_result_in_window()
        
        assert best is not None
        assert best.result_id == 'r2'  # Most recent
        assert best.timestamp == base_time + 0.1
    
    def test_get_best_result_treats_none_stability_as_zero(self):
        """Test that missing stability scores are treated as 0."""
        limiter = RateLimiter()
        
        # Add results with None and valid stability scores
        result_none = PartialResult(
            result_id='r_none',
            text='text_none',
            stability_score=None,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        result_low = PartialResult(
            result_id='r_low',
            text='text_low',
            stability_score=0.50,
            timestamp=time.time(),
            session_id='test-session'
        )
        
        limiter.window_buffer.extend([result_none, result_low])
        
        best = limiter.get_best_result_in_window()
        
        assert best is not None
        assert best.result_id == 'r_low'  # 0.50 > None (treated as 0)
        assert best.stability_score == 0.50
    
    def test_get_best_result_returns_none_for_empty_buffer(self):
        """Test that get_best_result returns None when buffer is empty."""
        limiter = RateLimiter()
        
        best = limiter.get_best_result_in_window()
        
        assert best is None
    
    def test_flush_window_returns_best_and_clears_buffer(self):
        """Test that flush_window returns best result and clears buffer."""
        limiter = RateLimiter()
        
        # Add multiple results
        results = [
            PartialResult(
                result_id=f'r{i}',
                text=f'text{i}',
                stability_score=0.70 + i * 0.05,
                timestamp=time.time(),
                session_id='test-session'
            )
            for i in range(3)
        ]
        
        for result in results:
            limiter.window_buffer.append(result)
        
        best = limiter.flush_window()
        
        assert best is not None
        assert best.result_id == 'r2'  # Highest stability
        assert len(limiter.window_buffer) == 0  # Buffer cleared
    
    def test_flush_window_tracks_statistics(self):
        """Test that flush_window tracks processed and dropped counts."""
        limiter = RateLimiter()
        
        # Add 5 results
        for i in range(5):
            result = PartialResult(
                result_id=f'r{i}',
                text=f'text{i}',
                stability_score=0.80 + i * 0.02,
                timestamp=time.time(),
                session_id='test-session'
            )
            limiter.window_buffer.append(result)
        
        limiter.flush_window()
        
        stats = limiter.get_statistics()
        assert stats['processed_count'] == 1  # 1 best result
        assert stats['dropped_count'] == 4  # 4 dropped results
    
    def test_flush_window_returns_none_for_empty_buffer(self):
        """Test that flush_window returns None when buffer is empty."""
        limiter = RateLimiter()
        
        best = limiter.flush_window()
        
        assert best is None
        assert limiter.processed_count == 0
        assert limiter.dropped_count == 0
    
    def test_window_reset_after_duration(self):
        """Test that window resets after window duration elapses."""
        limiter = RateLimiter(max_rate=5, window_ms=100)  # 100ms window
        
        # Add first result
        result1 = PartialResult(
            result_id='r1',
            text='text1',
            stability_score=0.85,
            timestamp=time.time(),
            session_id='test-session'
        )
        limiter.should_process(result1)
        
        # Wait for window to expire
        time.sleep(0.15)  # 150ms > 100ms window
        
        # Add second result (should start new window)
        result2 = PartialResult(
            result_id='r2',
            text='text2',
            stability_score=0.90,
            timestamp=time.time(),
            session_id='test-session'
        )
        limiter.should_process(result2)
        
        # Buffer should contain only the new result
        assert len(limiter.window_buffer) == 1
        assert limiter.window_buffer[0].result_id == 'r2'
    
    def test_rate_limit_enforcement_with_multiple_windows(self):
        """Test rate limiting across multiple windows."""
        limiter = RateLimiter(max_rate=5, window_ms=100)
        
        processed_results = []
        
        # Simulate 10 results over 2 windows (5 per window)
        for window in range(2):
            for i in range(5):
                result = PartialResult(
                    result_id=f'r{window}_{i}',
                    text=f'text{window}_{i}',
                    stability_score=0.70 + i * 0.05,
                    timestamp=time.time(),
                    session_id='test-session'
                )
                limiter.should_process(result)
            
            # Flush window
            best = limiter.flush_window()
            if best:
                processed_results.append(best)
            
            # Wait for next window
            if window < 1:
                time.sleep(0.12)  # 120ms > 100ms window
        
        # Should have processed 2 results (1 per window)
        assert len(processed_results) == 2
        
        # Should have dropped 8 results (4 per window)
        stats = limiter.get_statistics()
        assert stats['dropped_count'] == 8
        assert stats['processed_count'] == 2
    
    def test_get_statistics_returns_correct_counts(self):
        """Test that get_statistics returns accurate counts."""
        limiter = RateLimiter()
        
        # Add and flush multiple windows
        for _ in range(3):
            for i in range(4):
                result = PartialResult(
                    result_id=f'r{i}',
                    text=f'text{i}',
                    stability_score=0.80,
                    timestamp=time.time(),
                    session_id='test-session'
                )
                limiter.window_buffer.append(result)
            
            limiter.flush_window()
        
        stats = limiter.get_statistics()
        
        assert stats['processed_count'] == 3  # 3 windows
        assert stats['dropped_count'] == 9  # 3 dropped per window
        assert stats['current_window_size'] == 0  # Buffer cleared
    
    def test_reset_statistics_clears_counts(self):
        """Test that reset_statistics clears all counters."""
        limiter = RateLimiter()
        
        # Add some results and flush
        for i in range(3):
            result = PartialResult(
                result_id=f'r{i}',
                text=f'text{i}',
                stability_score=0.80,
                timestamp=time.time(),
                session_id='test-session'
            )
            limiter.window_buffer.append(result)
        
        limiter.flush_window()
        
        # Verify counts are non-zero
        stats = limiter.get_statistics()
        assert stats['processed_count'] > 0
        assert stats['dropped_count'] > 0
        
        # Reset
        limiter.reset_statistics()
        
        # Verify counts are zero
        stats = limiter.get_statistics()
        assert stats['processed_count'] == 0
        assert stats['dropped_count'] == 0
    
    def test_all_none_stability_scores(self):
        """Test handling when all results have None stability scores."""
        limiter = RateLimiter()
        
        base_time = time.time()
        
        # Add results with None stability but different timestamps
        for i in range(3):
            result = PartialResult(
                result_id=f'r{i}',
                text=f'text{i}',
                stability_score=None,
                timestamp=base_time + i * 0.1,
                session_id='test-session'
            )
            limiter.window_buffer.append(result)
        
        best = limiter.get_best_result_in_window()
        
        # Should select most recent (all have same stability of 0)
        assert best is not None
        assert best.result_id == 'r2'  # Most recent
        assert best.timestamp == base_time + 0.2
