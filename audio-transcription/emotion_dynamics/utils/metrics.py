"""
CloudWatch metrics utilities for emotion dynamics detection.

This module provides utilities for emitting custom CloudWatch metrics
to track emotion dynamics detection performance, errors, and fallback usage.
"""

import logging
import os
from typing import Optional, Dict, Any, List

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

logger = logging.getLogger(__name__)


class EmotionDynamicsMetrics:
    """
    Emits CloudWatch metrics for emotion dynamics detection.
    
    Uses boto3 CloudWatch client when available, otherwise logs metrics
    in structured format for CloudWatch Logs Insights parsing.
    """
    
    def __init__(
        self,
        namespace: str = 'AudioTranscription/EmotionDynamics',
        use_cloudwatch: Optional[bool] = None
    ):
        """
        Initialize metrics emitter.
        
        Args:
            namespace: CloudWatch namespace for metrics
            use_cloudwatch: Whether to use CloudWatch client (auto-detects if None)
        """
        self.namespace = namespace
        self.metrics_buffer: List[Dict[str, Any]] = []
        
        # Auto-detect CloudWatch usage if not specified
        if use_cloudwatch is None:
            # Use CloudWatch if boto3 available and not in test environment
            use_cloudwatch = BOTO3_AVAILABLE and os.getenv('PYTEST_CURRENT_TEST') is None
        
        self.use_cloudwatch = use_cloudwatch
        
        # Initialize CloudWatch client if enabled
        if self.use_cloudwatch and BOTO3_AVAILABLE:
            try:
                self.cloudwatch = boto3.client('cloudwatch')
                logger.info(f"Initialized CloudWatch metrics client for namespace: {namespace}")
            except Exception as e:
                logger.warning(f"Failed to initialize CloudWatch client: {e}, falling back to logging")
                self.use_cloudwatch = False
                self.cloudwatch = None
        else:
            self.cloudwatch = None
            if not BOTO3_AVAILABLE:
                logger.info("boto3 not available, using log-based metrics")
            else:
                logger.info("CloudWatch metrics disabled, using log-based metrics")
    
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
        Emit metric to CloudWatch or log.
        
        If CloudWatch client is available and enabled, emits directly to CloudWatch.
        Otherwise, logs in structured format for CloudWatch Logs Insights parsing.
        
        Args:
            metric: Metric dictionary with keys: namespace, metric_name, value, unit, dimensions
        """
        # Always log for debugging
        logger.info(
            f"METRIC {metric['metric_name']}={metric['value']} "
            f"unit={metric['unit']} "
            f"dimensions={metric['dimensions']}"
        )
        
        # Buffer for batch emission
        self.metrics_buffer.append(metric)
        
        # Emit immediately if CloudWatch is enabled (can be optimized to batch)
        if self.use_cloudwatch and self.cloudwatch:
            try:
                self._emit_to_cloudwatch([metric])
            except Exception as e:
                logger.error(f"Failed to emit metric to CloudWatch: {e}", exc_info=True)
    
    def _emit_to_cloudwatch(self, metrics: List[Dict[str, Any]]) -> None:
        """
        Emit metrics to CloudWatch using boto3 client.
        
        Args:
            metrics: List of metric dictionaries
        """
        if not self.cloudwatch:
            return
        
        try:
            # Convert metrics to CloudWatch format
            metric_data = []
            for metric in metrics:
                metric_datum = {
                    'MetricName': metric['metric_name'],
                    'Value': metric['value'],
                    'Unit': metric['unit']
                }
                
                # Add dimensions if present
                if metric['dimensions']:
                    metric_datum['Dimensions'] = [
                        {'Name': k, 'Value': str(v)}
                        for k, v in metric['dimensions'].items()
                    ]
                
                metric_data.append(metric_datum)
            
            # Emit to CloudWatch (max 20 metrics per call)
            for i in range(0, len(metric_data), 20):
                batch = metric_data[i:i+20]
                self.cloudwatch.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=batch
                )
            
            logger.debug(f"Emitted {len(metric_data)} metrics to CloudWatch")
            
        except ClientError as e:
            logger.error(f"CloudWatch API error: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error emitting to CloudWatch: {e}", exc_info=True)
            raise
    
    def flush_metrics(self) -> None:
        """
        Flush buffered metrics to CloudWatch.
        
        This can be called periodically to batch emit metrics for efficiency.
        Useful for reducing API calls when emitting many metrics.
        """
        if not self.metrics_buffer:
            return
        
        logger.debug(f"Flushing {len(self.metrics_buffer)} buffered metrics")
        
        if self.use_cloudwatch and self.cloudwatch:
            try:
                self._emit_to_cloudwatch(self.metrics_buffer)
            except Exception as e:
                logger.error(f"Failed to flush metrics to CloudWatch: {e}", exc_info=True)
        
        # Clear buffer
        self.metrics_buffer = []
