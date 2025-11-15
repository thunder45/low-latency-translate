"""
CloudWatch metrics emitter for audio processing.

This module provides utilities for emitting CloudWatch metrics
for audio processing operations, including latency, throughput,
errors, and resource utilization.
"""

import time
from typing import Dict, List, Optional
import boto3
from botocore.exceptions import ClientError


class MetricsEmitter:
    """
    Emits CloudWatch metrics for audio processing operations.
    
    Provides methods for tracking audio chunks, latency, errors,
    and other operational metrics.
    """
    
    def __init__(self, namespace: str = 'AudioTranscription/WebSocket'):
        """
        Initialize metrics emitter.
        
        Args:
            namespace: CloudWatch namespace for metrics
        """
        self.namespace = namespace
        self.cloudwatch = boto3.client('cloudwatch')
        self._metric_buffer: List[Dict] = []
        self._buffer_size = 20  # Batch metrics for efficiency
    
    def emit_audio_chunk_received(
        self,
        session_id: str,
        chunk_size: int
    ) -> None:
        """
        Emit metric for audio chunk received.
        
        Args:
            session_id: Session identifier
            chunk_size: Size of audio chunk in bytes
        """
        self._add_metric(
            metric_name='AudioChunksReceived',
            value=1,
            unit='Count',
            dimensions=[
                {'Name': 'SessionId', 'Value': session_id}
            ]
        )
        
        self._add_metric(
            metric_name='AudioChunkSize',
            value=chunk_size,
            unit='Bytes',
            dimensions=[
                {'Name': 'SessionId', 'Value': session_id}
            ]
        )
    
    def emit_audio_processing_latency(
        self,
        session_id: str,
        latency_ms: float
    ) -> None:
        """
        Emit metric for audio processing latency.
        
        Args:
            session_id: Session identifier
            latency_ms: Processing latency in milliseconds
        """
        self._add_metric(
            metric_name='AudioProcessingLatency',
            value=latency_ms,
            unit='Milliseconds',
            dimensions=[
                {'Name': 'SessionId', 'Value': session_id}
            ]
        )
    
    def emit_audio_chunk_dropped(
        self,
        session_id: str,
        reason: str
    ) -> None:
        """
        Emit metric for dropped audio chunk.
        
        Args:
            session_id: Session identifier
            reason: Reason for dropping (rate_limit, buffer_full, etc.)
        """
        self._add_metric(
            metric_name='AudioChunksDropped',
            value=1,
            unit='Count',
            dimensions=[
                {'Name': 'SessionId', 'Value': session_id},
                {'Name': 'Reason', 'Value': reason}
            ]
        )
    
    def emit_audio_buffer_overflow(
        self,
        session_id: str
    ) -> None:
        """
        Emit metric for audio buffer overflow.
        
        Args:
            session_id: Session identifier
        """
        self._add_metric(
            metric_name='AudioBufferOverflows',
            value=1,
            unit='Count',
            dimensions=[
                {'Name': 'SessionId', 'Value': session_id}
            ]
        )
    
    def emit_transcribe_stream_init_latency(
        self,
        session_id: str,
        latency_ms: float
    ) -> None:
        """
        Emit metric for Transcribe stream initialization latency.
        
        Args:
            session_id: Session identifier
            latency_ms: Initialization latency in milliseconds
        """
        self._add_metric(
            metric_name='TranscribeStreamInitLatency',
            value=latency_ms,
            unit='Milliseconds',
            dimensions=[
                {'Name': 'SessionId', 'Value': session_id}
            ]
        )
    
    def emit_transcribe_stream_error(
        self,
        session_id: str,
        error_type: str
    ) -> None:
        """
        Emit metric for Transcribe stream error.
        
        Args:
            session_id: Session identifier
            error_type: Type of error (connection, timeout, etc.)
        """
        self._add_metric(
            metric_name='TranscribeStreamErrors',
            value=1,
            unit='Count',
            dimensions=[
                {'Name': 'SessionId', 'Value': session_id},
                {'Name': 'ErrorType', 'Value': error_type}
            ]
        )
    
    def emit_rate_limit_violation(
        self,
        session_id: str,
        connection_id: str,
        message_type: str
    ) -> None:
        """
        Emit metric for rate limit violation.
        
        Args:
            session_id: Session identifier
            connection_id: Connection identifier
            message_type: Type of message (audio, control, etc.)
        """
        self._add_metric(
            metric_name='RateLimitViolations',
            value=1,
            unit='Count',
            dimensions=[
                {'Name': 'SessionId', 'Value': session_id},
                {'Name': 'MessageType', 'Value': message_type}
            ]
        )
    
    def emit_connection_closed_for_rate_limit(
        self,
        session_id: str,
        connection_id: str
    ) -> None:
        """
        Emit metric for connection closed due to rate limiting.
        
        Args:
            session_id: Session identifier
            connection_id: Connection identifier
        """
        self._add_metric(
            metric_name='ConnectionsClosedForRateLimit',
            value=1,
            unit='Count',
            dimensions=[
                {'Name': 'SessionId', 'Value': session_id}
            ]
        )
    
    def _add_metric(
        self,
        metric_name: str,
        value: float,
        unit: str,
        dimensions: List[Dict]
    ) -> None:
        """
        Add metric to buffer and flush if needed.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Metric unit
            dimensions: Metric dimensions
        """
        self._metric_buffer.append({
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit,
            'Dimensions': dimensions,
            'Timestamp': time.time()
        })
        
        if len(self._metric_buffer) >= self._buffer_size:
            self.flush()
    
    def flush(self) -> None:
        """Flush buffered metrics to CloudWatch."""
        if not self._metric_buffer:
            return
        
        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=self._metric_buffer
            )
            self._metric_buffer = []
        except ClientError as e:
            # Log error but don't fail the operation
            print(f"Failed to emit metrics: {e}")
    
    def __del__(self):
        """Flush remaining metrics on cleanup."""
        self.flush()


class MetricsContext:
    """
    Context manager for tracking operation latency.
    
    Automatically emits latency metric when context exits.
    """
    
    def __init__(
        self,
        emitter: MetricsEmitter,
        metric_name: str,
        session_id: str
    ):
        """
        Initialize metrics context.
        
        Args:
            emitter: MetricsEmitter instance
            metric_name: Name of latency metric
            session_id: Session identifier
        """
        self.emitter = emitter
        self.metric_name = metric_name
        self.session_id = session_id
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        """Start timing."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Emit latency metric."""
        if self.start_time is not None:
            latency_ms = (time.time() - self.start_time) * 1000
            
            if self.metric_name == 'AudioProcessingLatency':
                self.emitter.emit_audio_processing_latency(
                    self.session_id,
                    latency_ms
                )
            elif self.metric_name == 'TranscribeStreamInitLatency':
                self.emitter.emit_transcribe_stream_init_latency(
                    self.session_id,
                    latency_ms
                )
