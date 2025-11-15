"""
Unit tests for audio rate limiter.
"""

import pytest
import time
from shared.services.audio_rate_limiter import AudioRateLimiter, RateLimitStats


class TestAudioRateLimiter:
    """Test suite for AudioRateLimiter."""
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter initializes with correct parameters."""
        limiter = AudioRateLimiter(limit=50, window_seconds=1.0)
        
        assert limiter.limit == 50
        assert limiter.window_seconds == 1.0
        assert len(limiter.connection_windows) == 0
    
    def test_check_rate_limit_within_limit(self):
        """Test rate limit check passes when within limit."""
        limiter = AudioRateLimiter(limit=10)
        
        # Send 10 chunks (at limit)
        for i in range(10):
            assert limiter.check_rate_limit('conn-123') is True
    
    def test_check_rate_limit_exceeds_limit(self):
        """Test rate limit check fails when limit exceeded."""
        limiter = AudioRateLimiter(limit=10)
        
        # Send 10 chunks (at limit)
        for i in range(10):
            limiter.check_rate_limit('conn-123')
        
        # 11th chunk should be rejected
        assert limiter.check_rate_limit('conn-123') is False
    
    def test_check_rate_limit_sliding_window(self):
        """Test sliding window allows chunks after window expires."""
        limiter = AudioRateLimiter(limit=5, window_seconds=0.1)
        
        # Fill up the limit
        for i in range(5):
            assert limiter.check_rate_limit('conn-123') is True
        
        # Next chunk should be rejected
        assert limiter.check_rate_limit('conn-123') is False
        
        # Wait for window to slide
        time.sleep(0.15)
        
        # Should be allowed again
        assert limiter.check_rate_limit('conn-123') is True
    
    def test_check_rate_limit_multiple_connections(self):
        """Test rate limiting is per-connection."""
        limiter = AudioRateLimiter(limit=5)
        
        # Fill limit for conn-123
        for i in range(5):
            limiter.check_rate_limit('conn-123')
        
        # conn-123 should be limited
        assert limiter.check_rate_limit('conn-123') is False
        
        # conn-456 should still be allowed
        assert limiter.check_rate_limit('conn-456') is True
    
    def test_should_send_warning_after_threshold(self):
        """Test warning is sent after threshold seconds of violations."""
        limiter = AudioRateLimiter(
            limit=5,
            warning_threshold_seconds=0.1
        )
        
        # Fill limit
        for i in range(5):
            limiter.check_rate_limit('conn-123')
        
        # Trigger violation
        limiter.check_rate_limit('conn-123')
        
        # Should not send warning immediately
        assert limiter.should_send_warning('conn-123') is False
        
        # Wait for threshold
        time.sleep(0.15)
        
        # Should send warning now
        assert limiter.should_send_warning('conn-123') is True
        
        # Should not send warning again
        assert limiter.should_send_warning('conn-123') is False
    
    def test_should_close_connection_after_threshold(self):
        """Test connection close after threshold seconds of violations."""
        limiter = AudioRateLimiter(
            limit=5,
            close_threshold_seconds=0.1
        )
        
        # Fill limit
        for i in range(5):
            limiter.check_rate_limit('conn-123')
        
        # Trigger violation
        limiter.check_rate_limit('conn-123')
        
        # Should not close immediately
        assert limiter.should_close_connection('conn-123') is False
        
        # Wait for threshold
        time.sleep(0.15)
        
        # Should close now
        assert limiter.should_close_connection('conn-123') is True
    
    def test_get_stats(self):
        """Test getting rate limit statistics."""
        limiter = AudioRateLimiter(limit=10)
        
        # Send some chunks
        for i in range(5):
            limiter.check_rate_limit('conn-123')
        
        stats = limiter.get_stats('conn-123')
        
        assert isinstance(stats, RateLimitStats)
        assert stats.connection_id == 'conn-123'
        assert stats.chunks_in_window == 5
        assert stats.limit == 10
        assert stats.is_limited is False
    
    def test_get_stats_with_violations(self):
        """Test statistics include violation counts."""
        limiter = AudioRateLimiter(limit=5)
        
        # Fill limit and trigger violations
        for i in range(10):
            limiter.check_rate_limit('conn-123')
        
        stats = limiter.get_stats('conn-123')
        
        assert stats.violations_count == 5  # 5 violations
        assert stats.is_limited is True
    
    def test_cleanup_connection(self):
        """Test cleaning up connection data."""
        limiter = AudioRateLimiter(limit=10)
        
        # Add some data
        limiter.check_rate_limit('conn-123')
        
        assert 'conn-123' in limiter.connection_windows
        
        # Cleanup
        limiter.cleanup_connection('conn-123')
        
        assert 'conn-123' not in limiter.connection_windows
        assert 'conn-123' not in limiter.total_violations
    
    def test_violation_tracking(self):
        """Test violation tracking and clearing."""
        limiter = AudioRateLimiter(limit=5, window_seconds=0.1)
        
        # Fill limit
        for i in range(5):
            limiter.check_rate_limit('conn-123')
        
        # Trigger violation
        limiter.check_rate_limit('conn-123')
        
        assert 'conn-123' in limiter.violation_start_times
        
        # Wait for window to clear
        time.sleep(0.15)
        
        # Send allowed chunk
        limiter.check_rate_limit('conn-123')
        
        # Violation should be cleared
        assert 'conn-123' not in limiter.violation_start_times
