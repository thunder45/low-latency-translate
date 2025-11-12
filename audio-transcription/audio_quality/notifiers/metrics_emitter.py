"""
Quality metrics emitter.

This module provides the QualityMetricsEmitter class for publishing
audio quality metrics to CloudWatch and quality events to EventBridge.
Implements metric batching to reduce API calls.
"""

import time
import logging
from typing import Dict, Any, List, Optional

from audio_quality.models.quality_metrics import QualityMetrics
from audio_quality.models.quality_event import QualityEvent
from audio_quality.utils.structured_logger import log_metrics_emission


logger = logging.getLogger(__name__)


class QualityMetricsEmitter:
    """
    Emits quality metrics to monitoring systems.
    
    Publishes metrics to CloudWatch and quality events to EventBridge.
    Implements batching to reduce API calls (batch size: 20, flush interval: 5s).
    """
    
    def __init__(
        self,
        cloudwatch_client,
        eventbridge_client,
        batch_size: int = 20,
        flush_interval_s: float = 5.0
    ):
        """
        Initializes the metrics emitter.
        
        Args:
            cloudwatch_client: Boto3 CloudWatch client
            eventbridge_client: Boto3 EventBridge client
            batch_size: Maximum metrics per batch (default: 20)
            flush_interval_s: Flush interval in seconds (default: 5.0)
        """
        self.cloudwatch = cloudwatch_client
        self.eventbridge = eventbridge_client
        self.batch_size = batch_size
        self.flush_interval_s = flush_interval_s
        
        # Metric buffer for batching
        self.metric_buffer: List[Dict[str, Any]] = []
        self.last_flush_time = time.time()
    
    def emit_metrics(self, stream_id: str, metrics: QualityMetrics) -> None:
        """
        Emits quality metrics to CloudWatch.
        
        Metrics published:
        - AudioQuality.SNR
        - AudioQuality.ClippingPercentage
        - AudioQuality.EchoLevel
        - AudioQuality.SilenceDuration
        
        Metrics are batched to reduce API calls. Batch is flushed when:
        - Batch size reaches configured limit (default: 20)
        - Flush interval is exceeded (default: 5s)
        
        Args:
            stream_id: Audio stream identifier
            metrics: Quality metrics to emit
        """
        # Create metric data entries
        metric_data = [
            {
                'MetricName': 'SNR',
                'Value': metrics.snr_db,
                'Unit': 'None',
                'Timestamp': metrics.timestamp,
                'Dimensions': [{'Name': 'StreamId', 'Value': stream_id}]
            },
            {
                'MetricName': 'ClippingPercentage',
                'Value': metrics.clipping_percentage,
                'Unit': 'Percent',
                'Timestamp': metrics.timestamp,
                'Dimensions': [{'Name': 'StreamId', 'Value': stream_id}]
            },
            {
                'MetricName': 'EchoLevel',
                'Value': metrics.echo_level_db,
                'Unit': 'None',
                'Timestamp': metrics.timestamp,
                'Dimensions': [{'Name': 'StreamId', 'Value': stream_id}]
            },
            {
                'MetricName': 'SilenceDuration',
                'Value': metrics.silence_duration_s,
                'Unit': 'Seconds',
                'Timestamp': metrics.timestamp,
                'Dimensions': [{'Name': 'StreamId', 'Value': stream_id}]
            }
        ]
        
        # Add to buffer
        self.metric_buffer.extend(metric_data)
        
        # Check if we should flush
        current_time = time.time()
        should_flush = (
            len(self.metric_buffer) >= self.batch_size or
            current_time - self.last_flush_time >= self.flush_interval_s
        )
        
        if should_flush:
            self.flush()
    
    def flush(self) -> None:
        """
        Flushes buffered metrics to CloudWatch.
        
        Publishes all buffered metrics in a single API call and clears the buffer.
        Handles errors gracefully to prevent metric loss from blocking operations.
        """
        if not self.metric_buffer:
            return
        
        metric_count = len(self.metric_buffer)
        stream_id = 'batch'  # Multiple streams in batch
        
        try:
            self.cloudwatch.put_metric_data(
                Namespace='AudioQuality',
                MetricData=self.metric_buffer
            )
            
            logger.debug(
                f'Flushed {metric_count} metrics to CloudWatch'
            )
            
            # Log successful emission
            log_metrics_emission(stream_id, metric_count, success=True)
            
            # Clear buffer and update flush time
            self.metric_buffer = []
            self.last_flush_time = time.time()
            
        except Exception as e:
            logger.error(
                f'Failed to flush metrics to CloudWatch: {e}',
                exc_info=True
            )
            
            # Log failed emission
            log_metrics_emission(stream_id, metric_count, success=False, error=str(e))
            
            # Clear buffer to prevent unbounded growth on repeated failures
            self.metric_buffer = []
    
    def emit_quality_event(
        self,
        stream_id: str,
        event_type: str,
        details: Dict[str, Any]
    ) -> None:
        """
        Emits quality degradation events to EventBridge.
        
        Event types:
        - audio.quality.snr_low
        - audio.quality.clipping_detected
        - audio.quality.echo_detected
        - audio.quality.silence_detected
        
        Args:
            stream_id: Audio stream identifier
            event_type: Type of quality event (snr_low, clipping, echo, silence)
            details: Event details including metrics and context
        """
        try:
            # Create quality event
            event = QualityEvent(
                event_type=event_type,
                stream_id=stream_id,
                timestamp=time.time(),
                severity=details.get('severity', 'warning'),
                metrics=details.get('metrics', {}),
                message=details.get('message', f'{event_type} detected')
            )
            
            # Publish to EventBridge
            self.eventbridge.put_events(
                Entries=[event.to_eventbridge_entry()]
            )
            
            logger.info(
                f'Emitted quality event: {event_type} for stream {stream_id}'
            )
            
        except Exception as e:
            logger.error(
                f'Failed to emit quality event to EventBridge: {e}',
                exc_info=True
            )
    
    def __del__(self):
        """Flushes any remaining metrics on cleanup."""
        if hasattr(self, 'metric_buffer') and self.metric_buffer:
            try:
                self.flush()
            except Exception:
                # Ignore errors during cleanup
                pass
