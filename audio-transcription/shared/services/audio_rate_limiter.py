"""
Rate limiter for audio chunks with sliding window algorithm.

This module provides rate limiting for audio chunks to prevent abuse and
ensure stable processing. Uses a sliding window algorithm to track chunks
per second per connection.
"""

import time
import logging
from typing import Dict, List, Optional
from collections import deque
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RateLimitStats:
    """
    Statistics for rate limiting.
    
    Attributes:
        connection_id: WebSocket connection ID
        chunks_in_window: Number of chunks in current window
        limit: Maximum chunks per second
        violations_count: Total violations since start
        consecutive_violations: Consecutive violations
        last_violation_time: Timestamp of last violation
        is_limited: Whether currently rate limited
    """
    connection_id: str
    chunks_in_window: int
    limit: int
    violations_count: int = 0
    consecutive_violations: int = 0
    last_violation_time: Optional[float] = None
    is_limited: bool = False


class AudioRateLimiter:
    """
    Rate limiter for audio chunks using sliding window algorithm.
    
    This class tracks audio chunks per second per connection and enforces
    rate limits. It uses a sliding window to count chunks in the last second.
    
    Features:
    - Sliding window (1 second)
    - Per-connection tracking
    - Violation counting
    - Warning after 5 seconds of violations
    - Connection close after 30 seconds of violations
    - CloudWatch metrics emission
    
    Examples:
        >>> limiter = AudioRateLimiter(limit=50)
        >>> is_allowed = limiter.check_rate_limit('conn-123')
        >>> if not is_allowed:
        ...     print("Rate limit exceeded")
    """
    
    def __init__(
        self,
        limit: int = 50,
        window_seconds: float = 1.0,
        warning_threshold_seconds: float = 5.0,
        close_threshold_seconds: float = 30.0,
        cloudwatch_client=None
    ):
        """
        Initialize audio rate limiter.
        
        Args:
            limit: Maximum chunks per second (default: 50)
            window_seconds: Sliding window size in seconds (default: 1.0)
            warning_threshold_seconds: Send warning after this many seconds of violations (default: 5.0)
            close_threshold_seconds: Close connection after this many seconds of violations (default: 30.0)
            cloudwatch_client: Optional boto3 CloudWatch client for metrics
        """
        self.limit = limit
        self.window_seconds = window_seconds
        self.warning_threshold_seconds = warning_threshold_seconds
        self.close_threshold_seconds = close_threshold_seconds
        self.cloudwatch = cloudwatch_client
        
        # Per-connection tracking: connection_id -> deque of timestamps
        self.connection_windows: Dict[str, deque] = {}
        
        # Violation tracking: connection_id -> first_violation_time
        self.violation_start_times: Dict[str, float] = {}
        
        # Warning tracking: connection_id -> warning_sent
        self.warnings_sent: Dict[str, bool] = {}
        
        # Total violations per connection
        self.total_violations: Dict[str, int] = {}
        
        logger.info(
            f"Initialized AudioRateLimiter: limit={limit}/sec, "
            f"window={window_seconds}s, warning_threshold={warning_threshold_seconds}s, "
            f"close_threshold={close_threshold_seconds}s"
        )
    
    def check_rate_limit(self, connection_id: str) -> bool:
        """
        Check if connection is within rate limit.
        
        Uses sliding window algorithm to count chunks in the last second.
        If limit is exceeded, tracks violations and returns False.
        
        Args:
            connection_id: WebSocket connection ID
        
        Returns:
            True if within limit, False if limit exceeded
        
        Examples:
            >>> limiter = AudioRateLimiter(limit=50)
            >>> for i in range(60):
            ...     is_allowed = limiter.check_rate_limit('conn-123')
            ...     if not is_allowed:
            ...         print(f"Chunk {i} dropped")
        """
        current_time = time.time()
        
        # Initialize window for new connections
        if connection_id not in self.connection_windows:
            self.connection_windows[connection_id] = deque()
            self.total_violations[connection_id] = 0
            self.warnings_sent[connection_id] = False
        
        # Get window for this connection
        window = self.connection_windows[connection_id]
        
        # Remove timestamps outside the sliding window
        cutoff_time = current_time - self.window_seconds
        while window and window[0] < cutoff_time:
            window.popleft()
        
        # Check if within limit
        chunks_in_window = len(window)
        
        if chunks_in_window >= self.limit:
            # Rate limit exceeded
            self._handle_violation(connection_id, current_time, chunks_in_window)
            return False
        
        # Within limit - add timestamp and clear violation tracking
        window.append(current_time)
        self._clear_violation(connection_id)
        
        return True
    
    def _handle_violation(
        self,
        connection_id: str,
        current_time: float,
        chunks_in_window: int
    ) -> None:
        """
        Handle rate limit violation.
        
        Tracks violation start time, increments counters, and emits metrics.
        
        Args:
            connection_id: WebSocket connection ID
            current_time: Current timestamp
            chunks_in_window: Number of chunks in current window
        """
        # Track violation start time
        if connection_id not in self.violation_start_times:
            self.violation_start_times[connection_id] = current_time
            logger.warning(
                f"Rate limit violation started for connection {connection_id}: "
                f"{chunks_in_window}/{self.limit} chunks/sec"
            )
        
        # Increment violation counter
        self.total_violations[connection_id] += 1
        
        # Emit CloudWatch metric
        self._emit_violation_metric(connection_id, chunks_in_window)
        
        # Log periodic warnings
        if self.total_violations[connection_id] % 10 == 0:
            logger.warning(
                f"Connection {connection_id} has {self.total_violations[connection_id]} "
                f"rate limit violations"
            )
    
    def _clear_violation(self, connection_id: str) -> None:
        """
        Clear violation tracking when rate returns to normal.
        
        Args:
            connection_id: WebSocket connection ID
        """
        if connection_id in self.violation_start_times:
            violation_duration = time.time() - self.violation_start_times[connection_id]
            logger.info(
                f"Rate limit violation cleared for connection {connection_id} "
                f"after {violation_duration:.1f} seconds"
            )
            del self.violation_start_times[connection_id]
            self.warnings_sent[connection_id] = False
    
    def should_send_warning(self, connection_id: str) -> bool:
        """
        Check if warning should be sent to speaker.
        
        Sends warning after 5 seconds of continuous violations,
        but only once per violation period.
        
        Args:
            connection_id: WebSocket connection ID
        
        Returns:
            True if warning should be sent, False otherwise
        """
        if connection_id not in self.violation_start_times:
            return False
        
        # Check if warning already sent
        if self.warnings_sent.get(connection_id, False):
            return False
        
        # Check if violation duration exceeds threshold
        violation_duration = time.time() - self.violation_start_times[connection_id]
        
        if violation_duration >= self.warning_threshold_seconds:
            self.warnings_sent[connection_id] = True
            logger.warning(
                f"Sending rate limit warning to connection {connection_id} "
                f"after {violation_duration:.1f} seconds of violations"
            )
            return True
        
        return False
    
    def should_close_connection(self, connection_id: str) -> bool:
        """
        Check if connection should be closed due to excessive violations.
        
        Closes connection after 30 seconds of continuous violations.
        
        Args:
            connection_id: WebSocket connection ID
        
        Returns:
            True if connection should be closed, False otherwise
        """
        if connection_id not in self.violation_start_times:
            return False
        
        violation_duration = time.time() - self.violation_start_times[connection_id]
        
        if violation_duration >= self.close_threshold_seconds:
            logger.error(
                f"Closing connection {connection_id} after "
                f"{violation_duration:.1f} seconds of rate limit violations"
            )
            return True
        
        return False
    
    def get_stats(self, connection_id: str) -> RateLimitStats:
        """
        Get rate limit statistics for connection.
        
        Args:
            connection_id: WebSocket connection ID
        
        Returns:
            RateLimitStats with current statistics
        """
        window = self.connection_windows.get(connection_id, deque())
        chunks_in_window = len(window)
        
        violations_count = self.total_violations.get(connection_id, 0)
        is_limited = connection_id in self.violation_start_times
        last_violation_time = self.violation_start_times.get(connection_id)
        
        # Calculate consecutive violations
        consecutive_violations = 0
        if is_limited:
            consecutive_violations = int(
                time.time() - self.violation_start_times[connection_id]
            )
        
        return RateLimitStats(
            connection_id=connection_id,
            chunks_in_window=chunks_in_window,
            limit=self.limit,
            violations_count=violations_count,
            consecutive_violations=consecutive_violations,
            last_violation_time=last_violation_time,
            is_limited=is_limited
        )
    
    def cleanup_connection(self, connection_id: str) -> None:
        """
        Clean up tracking data for disconnected connection.
        
        Args:
            connection_id: WebSocket connection ID
        """
        if connection_id in self.connection_windows:
            del self.connection_windows[connection_id]
        
        if connection_id in self.violation_start_times:
            del self.violation_start_times[connection_id]
        
        if connection_id in self.warnings_sent:
            del self.warnings_sent[connection_id]
        
        if connection_id in self.total_violations:
            del self.total_violations[connection_id]
        
        logger.debug(f"Cleaned up rate limiter data for connection {connection_id}")
    
    def _emit_violation_metric(
        self,
        connection_id: str,
        chunks_in_window: int
    ) -> None:
        """
        Emit CloudWatch metric for rate limit violation.
        
        Args:
            connection_id: WebSocket connection ID
            chunks_in_window: Number of chunks in current window
        """
        if not self.cloudwatch:
            return
        
        try:
            self.cloudwatch.put_metric_data(
                Namespace='AudioTranscription/RateLimiting',
                MetricData=[
                    {
                        'MetricName': 'RateLimitViolation',
                        'Value': 1,
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'ConnectionId', 'Value': connection_id}
                        ]
                    },
                    {
                        'MetricName': 'ChunksPerSecond',
                        'Value': chunks_in_window,
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'ConnectionId', 'Value': connection_id}
                        ]
                    }
                ]
            )
        except Exception as e:
            logger.warning(f"Failed to emit rate limit metric: {e}")
