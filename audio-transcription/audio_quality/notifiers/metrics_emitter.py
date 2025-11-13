"""
Quality metrics emitter.

This module provides the QualityMetricsEmitter class for publishing
audio quality metrics to CloudWatch and quality events to EventBridge.
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
    """
    
    def __init__(
        self,
        cloudwatch_client,
        eventbridge_client
    ):
        """
        Initializes the metrics emitter.
        
        Args:
            cloudwatch_client: Boto3 CloudWatch client
            eventbridge_client: Boto3 EventBridge client
        """
        self.cloudwatch = cloudwatch_client
        self.eventbridge = eventbridge_client
    
    def emit_metrics(self, stream_id: str, metrics: QualityMetrics) -> None:
        """
        Emits quality metrics to CloudWatch.
        
        Metrics published:
        - AudioQuality.SNR
        - AudioQuality.ClippingPercentage
        - AudioQuality.EchoLevel
        - AudioQuality.SilenceDuration
        
        Args:
            stream_id: Audio stream identifier
            metrics: Quality metrics to emit
        """
        try:
            # Create metric data entries with timestamps
            from datetime import datetime
            timestamp = datetime.utcfromtimestamp(metrics.timestamp)
            
            metric_data = [
                {
                    'MetricName': 'SNR',
                    'Value': float(metrics.snr_db),
                    'Unit': 'None',
                    'Timestamp': timestamp,
                    'Dimensions': [{'Name': 'StreamId', 'Value': stream_id}]
                },
                {
                    'MetricName': 'ClippingPercentage',
                    'Value': float(metrics.clipping_percentage),
                    'Unit': 'Percent',
                    'Timestamp': timestamp,
                    'Dimensions': [{'Name': 'StreamId', 'Value': stream_id}]
                },
                {
                    'MetricName': 'EchoLevel',
                    'Value': float(metrics.echo_level_db),
                    'Unit': 'None',
                    'Timestamp': timestamp,
                    'Dimensions': [{'Name': 'StreamId', 'Value': stream_id}]
                },
                {
                    'MetricName': 'SilenceDuration',
                    'Value': float(metrics.silence_duration_s),
                    'Unit': 'Seconds',
                    'Timestamp': timestamp,
                    'Dimensions': [{'Name': 'StreamId', 'Value': stream_id}]
                }
            ]
            
            # Actually call CloudWatch
            self.cloudwatch.put_metric_data(
                Namespace='AudioQuality',
                MetricData=metric_data
            )
            
            logger.debug(
                f'Emitted {len(metric_data)} metrics to CloudWatch for stream {stream_id}'
            )
            
            # Log successful emission
            log_metrics_emission(stream_id, len(metric_data), success=True)
            
        except Exception as e:
            logger.error(
                f'Failed to emit metrics to CloudWatch: {e}',
                exc_info=True
            )
            
            # Log failed emission
            log_metrics_emission(stream_id, 0, success=False, error=str(e))
            # Don't raise - graceful degradation
    

    
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
    

