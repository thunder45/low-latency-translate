"""
Audio buffer management for handling backpressure from Transcribe stream.

This module provides a buffer for audio chunks with overflow handling,
allowing graceful degradation when Transcribe stream cannot keep up.
"""

import time
import logging
from typing import List, Optional
from collections import deque
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BufferStats:
    """
    Statistics for audio buffer.
    
    Attributes:
        capacity_seconds: Buffer capacity in seconds
        current_size: Current number of chunks in buffer
        total_added: Total chunks added since creation
        total_dropped: Total chunks dropped due to overflow
        overflow_count: Number of overflow events
        is_full: Whether buffer is currently full
    """
    capacity_seconds: float
    current_size: int
    total_added: int
    total_dropped: int
    overflow_count: int
    is_full: bool


class AudioBuffer:
    """
    Buffer for audio chunks with overflow handling.
    
    This class provides a fixed-capacity buffer for audio chunks, handling
    backpressure from the Transcribe stream. When the buffer is full, it
    drops the oldest chunks to make room for new ones.
    
    Features:
    - Fixed capacity (5 seconds of audio)
    - FIFO queue (oldest chunks dropped first)
    - Overflow tracking and metrics
    - Automatic cleanup on stream close
    
    Examples:
        >>> buffer = AudioBuffer(capacity_seconds=5.0, chunk_duration_ms=100)
        >>> buffer.add_chunk(audio_bytes)
        >>> chunk = buffer.get_chunk()
    """
    
    def __init__(
        self,
        capacity_seconds: float = 5.0,
        chunk_duration_ms: int = 100,
        cloudwatch_client=None
    ):
        """
        Initialize audio buffer.
        
        Args:
            capacity_seconds: Buffer capacity in seconds (default: 5.0)
            chunk_duration_ms: Duration of each audio chunk in milliseconds (default: 100)
            cloudwatch_client: Optional boto3 CloudWatch client for metrics
        """
        self.capacity_seconds = capacity_seconds
        self.chunk_duration_ms = chunk_duration_ms
        self.cloudwatch = cloudwatch_client
        
        # Calculate capacity in chunks
        self.capacity_chunks = int(
            (capacity_seconds * 1000) / chunk_duration_ms
        )
        
        # Buffer storage (FIFO queue)
        self.buffer: deque = deque(maxlen=self.capacity_chunks)
        
        # Statistics
        self.total_added = 0
        self.total_dropped = 0
        self.overflow_count = 0
        self.last_overflow_time: Optional[float] = None
        
        logger.info(
            f"Initialized AudioBuffer: capacity={capacity_seconds}s "
            f"({self.capacity_chunks} chunks @ {chunk_duration_ms}ms each)"
        )
    
    def add_chunk(self, audio_bytes: bytes, session_id: str = "") -> bool:
        """
        Add audio chunk to buffer.
        
        If buffer is full, drops the oldest chunk to make room.
        Tracks overflow events and emits metrics.
        
        Args:
            audio_bytes: Audio data as bytes
            session_id: Session ID for logging and metrics
        
        Returns:
            True if chunk added successfully, False if dropped
        
        Examples:
            >>> buffer = AudioBuffer()
            >>> success = buffer.add_chunk(audio_bytes, 'session-123')
            >>> if not success:
            ...     print("Chunk dropped due to buffer overflow")
        """
        # Check if buffer is full
        was_full = len(self.buffer) >= self.capacity_chunks
        
        if was_full:
            # Buffer is full - oldest chunk will be dropped
            self.total_dropped += 1
            self.overflow_count += 1
            self.last_overflow_time = time.time()
            
            logger.warning(
                f"Buffer overflow for session {session_id}: "
                f"dropping oldest chunk (total_dropped={self.total_dropped})"
            )
            
            # Emit overflow metric
            self._emit_overflow_metric(session_id)
        
        # Add chunk (deque automatically drops oldest if at maxlen)
        self.buffer.append(audio_bytes)
        self.total_added += 1
        
        logger.debug(
            f"Added chunk to buffer: size={len(self.buffer)}/{self.capacity_chunks}"
        )
        
        return not was_full
    
    def get_chunk(self) -> Optional[bytes]:
        """
        Get next chunk from buffer (FIFO).
        
        Returns:
            Audio bytes or None if buffer is empty
        
        Examples:
            >>> buffer = AudioBuffer()
            >>> buffer.add_chunk(audio_bytes)
            >>> chunk = buffer.get_chunk()
            >>> if chunk:
            ...     process_chunk(chunk)
        """
        if not self.buffer:
            return None
        
        chunk = self.buffer.popleft()
        
        logger.debug(
            f"Retrieved chunk from buffer: remaining={len(self.buffer)}"
        )
        
        return chunk
    
    def peek_chunk(self) -> Optional[bytes]:
        """
        Peek at next chunk without removing it.
        
        Returns:
            Audio bytes or None if buffer is empty
        """
        if not self.buffer:
            return None
        
        return self.buffer[0]
    
    def is_empty(self) -> bool:
        """
        Check if buffer is empty.
        
        Returns:
            True if buffer is empty, False otherwise
        """
        return len(self.buffer) == 0
    
    def is_full(self) -> bool:
        """
        Check if buffer is full.
        
        Returns:
            True if buffer is full, False otherwise
        """
        return len(self.buffer) >= self.capacity_chunks
    
    def size(self) -> int:
        """
        Get current buffer size in chunks.
        
        Returns:
            Number of chunks in buffer
        """
        return len(self.buffer)
    
    def clear(self) -> int:
        """
        Clear all chunks from buffer.
        
        Returns:
            Number of chunks cleared
        """
        size = len(self.buffer)
        self.buffer.clear()
        
        logger.info(f"Cleared buffer: removed {size} chunks")
        
        return size
    
    def get_stats(self) -> BufferStats:
        """
        Get buffer statistics.
        
        Returns:
            BufferStats with current statistics
        """
        return BufferStats(
            capacity_seconds=self.capacity_seconds,
            current_size=len(self.buffer),
            total_added=self.total_added,
            total_dropped=self.total_dropped,
            overflow_count=self.overflow_count,
            is_full=self.is_full()
        )
    
    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self.total_added = 0
        self.total_dropped = 0
        self.overflow_count = 0
        self.last_overflow_time = None
        
        logger.info("Reset buffer statistics")
    
    def _emit_overflow_metric(self, session_id: str) -> None:
        """
        Emit CloudWatch metric for buffer overflow.
        
        Args:
            session_id: Session ID for metric dimensions
        """
        if not self.cloudwatch:
            return
        
        try:
            self.cloudwatch.put_metric_data(
                Namespace='AudioTranscription/Buffer',
                MetricData=[
                    {
                        'MetricName': 'BufferOverflow',
                        'Value': 1,
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'SessionId', 'Value': session_id or 'unknown'}
                        ]
                    },
                    {
                        'MetricName': 'BufferSize',
                        'Value': len(self.buffer),
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'SessionId', 'Value': session_id or 'unknown'}
                        ]
                    }
                ]
            )
        except Exception as e:
            logger.warning(f"Failed to emit buffer overflow metric: {e}")
    
    def get_buffer_duration_seconds(self) -> float:
        """
        Get current buffer duration in seconds.
        
        Returns:
            Buffer duration in seconds
        """
        num_chunks = len(self.buffer)
        duration_ms = num_chunks * self.chunk_duration_ms
        return duration_ms / 1000.0
    
    def get_capacity_utilization(self) -> float:
        """
        Get buffer capacity utilization as percentage.
        
        Returns:
            Utilization percentage (0.0-100.0)
        """
        if self.capacity_chunks == 0:
            return 0.0
        
        return (len(self.buffer) / self.capacity_chunks) * 100.0
