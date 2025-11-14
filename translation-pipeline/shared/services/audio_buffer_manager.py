"""Audio Buffer Manager for per-listener audio buffering."""

import logging
from collections import deque
from typing import Dict, List, Optional
import time


logger = logging.getLogger(__name__)


class AudioBufferManager:
    """
    Manages per-listener audio buffers with overflow handling.
    
    Maintains a maximum buffer duration per listener to prevent unbounded
    memory growth during high-latency broadcasting scenarios.
    """
    
    # Audio format constants
    SAMPLE_RATE = 16000  # 16kHz
    BYTES_PER_SAMPLE = 2  # 16-bit PCM
    BYTES_PER_SECOND = SAMPLE_RATE * BYTES_PER_SAMPLE  # 32,000 bytes/sec
    
    def __init__(
        self,
        max_buffer_seconds: int = 10,
        cloudwatch_client: Optional[object] = None
    ):
        """
        Initialize Audio Buffer Manager.
        
        Args:
            max_buffer_seconds: Maximum buffer duration in seconds (default: 10)
            cloudwatch_client: Optional CloudWatch client for metrics
        """
        self.max_buffer_seconds = max_buffer_seconds
        self.max_buffer_bytes = max_buffer_seconds * self.BYTES_PER_SECOND
        self.cloudwatch_client = cloudwatch_client
        
        # Per-connection buffers: {connection_id: deque of (audio_chunk, timestamp)}
        self.buffers: Dict[str, deque] = {}
        
        # Track buffer sizes in bytes: {connection_id: total_bytes}
        self.buffer_sizes: Dict[str, int] = {}
        
        # Track overflow events for metrics
        self.overflow_count = 0
    
    def add_audio(
        self,
        connection_id: str,
        audio_chunk: bytes,
        session_id: Optional[str] = None
    ) -> bool:
        """
        Add audio chunk to listener buffer.
        
        Args:
            connection_id: Listener connection ID
            audio_chunk: PCM audio bytes to buffer
            session_id: Optional session ID for logging
            
        Returns:
            True if added successfully, False if buffer overflow occurred
        """
        timestamp = time.time()
        
        # Initialize buffer if needed
        if connection_id not in self.buffers:
            self.buffers[connection_id] = deque()
            self.buffer_sizes[connection_id] = 0
        
        # Check if adding this chunk would exceed capacity
        current_size = self.buffer_sizes[connection_id]
        chunk_size = len(audio_chunk)
        
        if current_size + chunk_size > self.max_buffer_bytes:
            # Buffer overflow - drop oldest packets
            overflow_occurred = self._handle_overflow(
                connection_id,
                chunk_size,
                session_id
            )
            
            if overflow_occurred:
                self.overflow_count += 1
                self._emit_overflow_metric(session_id)
                
                logger.warning(
                    f"Buffer overflow for connection {connection_id}",
                    extra={
                        'session_id': session_id,
                        'connection_id': connection_id,
                        'current_size_bytes': current_size,
                        'chunk_size_bytes': chunk_size,
                        'max_buffer_bytes': self.max_buffer_bytes,
                        'buffer_utilization_percent': self._calculate_utilization(connection_id)
                    }
                )
        
        # Add chunk to buffer
        self.buffers[connection_id].append((audio_chunk, timestamp))
        self.buffer_sizes[connection_id] += chunk_size
        
        return True
    
    def get_buffered_audio(self, connection_id: str) -> List[bytes]:
        """
        Get all buffered audio for connection.
        
        Args:
            connection_id: Listener connection ID
            
        Returns:
            List of audio chunks in order
        """
        if connection_id not in self.buffers:
            return []
        
        # Extract just the audio chunks (not timestamps)
        return [chunk for chunk, _ in self.buffers[connection_id]]
    
    def clear_buffer(self, connection_id: str) -> None:
        """
        Clear buffer for connection.
        
        Args:
            connection_id: Listener connection ID
        """
        if connection_id in self.buffers:
            del self.buffers[connection_id]
            del self.buffer_sizes[connection_id]
    
    def get_buffer_utilization(self, connection_id: str) -> float:
        """
        Get buffer utilization percentage for connection.
        
        Args:
            connection_id: Listener connection ID
            
        Returns:
            Utilization percentage (0.0 to 100.0)
        """
        return self._calculate_utilization(connection_id)
    
    def get_buffer_duration(self, connection_id: str) -> float:
        """
        Get buffer duration in seconds for connection.
        
        Args:
            connection_id: Listener connection ID
            
        Returns:
            Buffer duration in seconds
        """
        if connection_id not in self.buffer_sizes:
            return 0.0
        
        buffer_bytes = self.buffer_sizes[connection_id]
        return buffer_bytes / self.BYTES_PER_SECOND
    
    def _handle_overflow(
        self,
        connection_id: str,
        new_chunk_size: int,
        session_id: Optional[str] = None
    ) -> bool:
        """
        Handle buffer overflow by dropping oldest packets.
        
        Args:
            connection_id: Listener connection ID
            new_chunk_size: Size of new chunk to add
            session_id: Optional session ID for logging
            
        Returns:
            True if overflow occurred and packets were dropped
        """
        buffer = self.buffers[connection_id]
        current_size = self.buffer_sizes[connection_id]
        
        # Calculate how much space we need
        space_needed = (current_size + new_chunk_size) - self.max_buffer_bytes
        
        if space_needed <= 0:
            return False
        
        # Drop oldest packets until we have enough space
        dropped_count = 0
        bytes_dropped = 0
        
        while buffer and bytes_dropped < space_needed:
            oldest_chunk, _ = buffer.popleft()
            bytes_dropped += len(oldest_chunk)
            dropped_count += 1
        
        # Update buffer size
        self.buffer_sizes[connection_id] = current_size - bytes_dropped
        
        logger.debug(
            f"Dropped {dropped_count} packets ({bytes_dropped} bytes) from buffer",
            extra={
                'session_id': session_id,
                'connection_id': connection_id,
                'dropped_count': dropped_count,
                'bytes_dropped': bytes_dropped
            }
        )
        
        return True
    
    def _calculate_utilization(self, connection_id: str) -> float:
        """
        Calculate buffer utilization percentage.
        
        Args:
            connection_id: Listener connection ID
            
        Returns:
            Utilization percentage (0.0 to 100.0)
        """
        if connection_id not in self.buffer_sizes:
            return 0.0
        
        current_size = self.buffer_sizes[connection_id]
        return (current_size / self.max_buffer_bytes) * 100.0
    
    def _emit_overflow_metric(self, session_id: Optional[str] = None) -> None:
        """
        Emit CloudWatch metric for buffer overflow event.
        
        Args:
            session_id: Optional session ID for metric dimensions
        """
        if self.cloudwatch_client is None:
            return
        
        try:
            dimensions = []
            if session_id:
                dimensions.append({
                    'Name': 'SessionId',
                    'Value': session_id
                })
            
            self.cloudwatch_client.put_metric_data(
                Namespace='TranslationPipeline/AudioBuffer',
                MetricData=[
                    {
                        'MetricName': 'BufferOverflow',
                        'Value': 1.0,
                        'Unit': 'Count',
                        'Dimensions': dimensions
                    }
                ]
            )
        except Exception as e:
            logger.error(
                f"Failed to emit overflow metric: {e}",
                extra={'session_id': session_id}
            )
    
    def emit_utilization_metrics(self, session_id: Optional[str] = None) -> None:
        """
        Emit CloudWatch metrics for buffer utilization across all connections.
        
        Args:
            session_id: Optional session ID for metric dimensions
        """
        if self.cloudwatch_client is None:
            return
        
        if not self.buffers:
            return
        
        # Calculate average utilization
        total_utilization = sum(
            self._calculate_utilization(conn_id)
            for conn_id in self.buffers.keys()
        )
        avg_utilization = total_utilization / len(self.buffers)
        
        # Calculate max utilization
        max_utilization = max(
            self._calculate_utilization(conn_id)
            for conn_id in self.buffers.keys()
        )
        
        try:
            dimensions = []
            if session_id:
                dimensions.append({
                    'Name': 'SessionId',
                    'Value': session_id
                })
            
            self.cloudwatch_client.put_metric_data(
                Namespace='TranslationPipeline/AudioBuffer',
                MetricData=[
                    {
                        'MetricName': 'AverageBufferUtilization',
                        'Value': avg_utilization,
                        'Unit': 'Percent',
                        'Dimensions': dimensions
                    },
                    {
                        'MetricName': 'MaxBufferUtilization',
                        'Value': max_utilization,
                        'Unit': 'Percent',
                        'Dimensions': dimensions
                    },
                    {
                        'MetricName': 'ActiveBuffers',
                        'Value': float(len(self.buffers)),
                        'Unit': 'Count',
                        'Dimensions': dimensions
                    }
                ]
            )
        except Exception as e:
            logger.error(
                f"Failed to emit utilization metrics: {e}",
                extra={'session_id': session_id}
            )
