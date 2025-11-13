"""
CloudWatch metrics utilities for emotion dynamics detection.

This module provides utilities for emitting custom CloudWatch metrics
to track emotion dynamics detection performance, errors, and fallback usage.
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class EmotionDynamicsMetrics:
    """
    Emits CloudWatch metrics for emotion dynamics detection.
    
    In production, this would use boto3 CloudWatch client. For now,
    it logs metrics that can be parsed by CloudWatch Logs Insights.
    """
    
    def __init__(self, namespace: str = 'AudioTranscription/EmotionDynamics'):
        """
        Initialize metrics emitter.
        
        Args:
            namespace: CloudWatch namespace for metrics
        """
        self.namespace = namespace
        self.metrics_buffer = []
    
    def emit_volume_detection_latency(
        self,
        latency_ms: float,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Emit metric for volume detection latency.
        
        Args:
            latency_ms: Detection latency in milliseconds
            correlation_id: Optional correlation ID for tracking
        """
        dimensions = {}
        if correlation_id:
            dimensions['CorrelationId'] = correlation_id
        
        metric = {
            'namespace': self.namespace,
            'metric_name': 'VolumeDetectionLatency',
            'value': latency_ms,
            'unit': 'Milliseconds',
            'dimensions': dimensions
        }
        self._emit_metric(metric)
    
    def emit_rate_detection_latency(
        self,
        latency_ms: float,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Emit metric for rate detection latency.
        
        Args:
            latency_ms: Detection latency in milliseconds
            correlation_id: Optional correlation ID for tracking
        """
        dimensions = {}
        if correlation_id:
            dimensions['CorrelationId'] = correlation_id
        
        metric = {
            'namespace': self.namespace,
            'metric_name': 'RateDetectionLatency',
            'value': latency_ms,
            'unit': 'Milliseconds',
            'dimensions': dimensions
        }
        self._emit_metric(metric)
    
    def emit_ssml_generation_latency(
        self,
        latency_ms: float,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Emit metric for SSML generation latency.
        
        Args:
            latency_ms: Generation latency in milliseconds
            correlation_id: Optional correlation ID for tracking
        """
        dimensions = {}
        if correlation_id:
            dimensions['CorrelationId'] = correlation_id
        
        metric = {
            'namespace': self.namespace,
            'metric_name': 'SSMLGenerationLatency',
            'value': latency_ms,
            'unit': 'Milliseconds',
            'dimensions': dimensions
        }
        self._emit_metric(metric)
    
    def emit_polly_synthesis_latency(
        self,
        latency_ms: float,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Emit metric for Polly synthesis latency.
        
        Args:
            latency_ms: Synthesis latency in milliseconds
            correlation_id: Optional correlation ID for tracking
        """
        dimensions = {}
        if correlation_id:
            dimensions['CorrelationId'] = correlation_id
        
        metric = {
            'namespace': self.namespace,
            'metric_name': 'PollySynthesisLatency',
            'value': latency_ms,
            'unit': 'Milliseconds',
            'dimensions': dimensions
        }
        self._emit_metric(metric)
    
    def emit_end_to_end_latency(
        self,
        latency_ms: float,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Emit metric for end-to-end processing latency.
        
        Args:
            latency_ms: Total latency in milliseconds
            correlation_id: Optional correlation ID for tracking
        """
        dimensions = {}
        if correlation_id:
            dimensions['CorrelationId'] = correlation_id
        
        metric = {
            'namespace': self.namespace,
            'metric_name': 'EndToEndLatency',
            'value': latency_ms,
            'unit': 'Milliseconds',
            'dimensions': dimensions
        }
        self._emit_metric(metric)
    
    def emit_error_count(
        self,
        error_type: str,
        component: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Emit metric for error count by type and component.
        
        Args:
            error_type: Type of error (e.g., 'VolumeDetectionError', 'LibrosaError')
            component: Component where error occurred (e.g., 'VolumeDetector', 'PollyClient')
            correlation_id: Optional correlation ID for tracking
        """
        dimensions = {
            'ErrorType': error_type,
            'Component': component
        }
        if correlation_id:
            dimensions['CorrelationId'] = correlation_id
        
        metric = {
            'namespace': self.namespace,
            'metric_name': 'ErrorCount',
            'value': 1,
            'unit': 'Count',
            'dimensions': dimensions
        }
        self._emit_metric(metric)
    
    def emit_fallback_used(
        self,
        fallback_type: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Emit metric for fallback usage.
        
        Args:
            fallback_type: Type of fallback (e.g., 'DefaultVolume', 'PlainText', 'DefaultRate')
            correlation_id: Optional correlation ID for tracking
        """
        dimensions = {
            'FallbackType': fallback_type
        }
        if correlation_id:
            dimensions['CorrelationId'] = correlation_id
        
        metric = {
            'namespace': self.namespace,
            'metric_name': 'FallbackUsed',
            'value': 1,
            'unit': 'Count',
            'dimensions': dimensions
        }
        self._emit_metric(metric)
    
    def emit_detected_volume(
        self,
        volume_level: str,
        db_value: float,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Emit metric for detected volume level.
        
        Args:
            volume_level: Detected volume level (loud, medium, soft, whisper)
            db_value: Decibel value
            correlation_id: Optional correlation ID for tracking
        """
        dimensions = {
            'VolumeLevel': volume_level
        }
        if correlation_id:
            dimensions['CorrelationId'] = correlation_id
        
        metric = {
            'namespace': self.namespace,
            'metric_name': 'DetectedVolume',
            'value': db_value,
            'unit': 'None',
            'dimensions': dimensions
        }
        self._emit_metric(metric)
    
    def emit_detected_rate(
        self,
        rate_classification: str,
        wpm: float,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Emit metric for detected speaking rate.
        
        Args:
            rate_classification: Rate classification (very_slow, slow, medium, fast, very_fast)
            wpm: Words per minute
            correlation_id: Optional correlation ID for tracking
        """
        dimensions = {
            'RateClassification': rate_classification
        }
        if correlation_id:
            dimensions['CorrelationId'] = correlation_id
        
        metric = {
            'namespace': self.namespace,
            'metric_name': 'DetectedRate',
            'value': wpm,
            'unit': 'None',
            'dimensions': dimensions
        }
        self._emit_metric(metric)
    
    def _emit_metric(self, metric: dict) -> None:
        """
        Emit metric to CloudWatch.
        
        In production, this would use boto3 CloudWatch client:
        
        cloudwatch = boto3.client('cloudwatch')
        cloudwatch.put_metric_data(
            Namespace=metric['namespace'],
            MetricData=[{
                'MetricName': metric['metric_name'],
                'Value': metric['value'],
                'Unit': metric['unit'],
                'Dimensions': [
                    {'Name': k, 'Value': v}
                    for k, v in metric['dimensions'].items()
                ]
            }]
        )
        
        For now, log in structured format for CloudWatch Logs Insights parsing.
        
        Args:
            metric: Metric dictionary
        """
        logger.info(
            f"METRIC {metric['metric_name']}={metric['value']} "
            f"unit={metric['unit']} "
            f"dimensions={metric['dimensions']}"
        )
        
        # Buffer for batch emission (optional optimization)
        self.metrics_buffer.append(metric)
    
    def flush_metrics(self) -> None:
        """
        Flush buffered metrics to CloudWatch.
        
        This can be called periodically to batch emit metrics for efficiency.
        """
        if not self.metrics_buffer:
            return
        
        # In production, batch emit all buffered metrics
        logger.debug(f"Flushing {len(self.metrics_buffer)} metrics")
        
        # Clear buffer
        self.metrics_buffer = []
