"""
CloudWatch metrics utilities for partial result processing.

This module provides utilities for emitting custom CloudWatch metrics
to track partial result processing performance and behavior.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MetricsEmitter:
    """
    Emits CloudWatch metrics for partial result processing.
    
    In production, this would use boto3 CloudWatch client. For now,
    it logs metrics that can be parsed by CloudWatch Logs Insights.
    """
    
    def __init__(self, namespace: str = 'AudioTranscription/PartialResults'):
        """
        Initialize metrics emitter.
        
        Args:
            namespace: CloudWatch namespace for metrics
        """
        self.namespace = namespace
        self.metrics_buffer = []
    
    def emit_dropped_results(self, session_id: str, count: int) -> None:
        """
        Emit metric for dropped partial results.
        
        Args:
            session_id: Session identifier
            count: Number of results dropped
        """
        if count > 0:
            metric = {
                'namespace': self.namespace,
                'metric_name': 'PartialResultsDropped',
                'value': count,
                'unit': 'Count',
                'dimensions': {
                    'SessionId': session_id
                }
            }
            self._emit_metric(metric)
    
    def emit_processing_latency(self, session_id: str, latency_ms: float) -> None:
        """
        Emit metric for partial result processing latency.
        
        Args:
            session_id: Session identifier
            latency_ms: Processing latency in milliseconds
        """
        metric = {
            'namespace': self.namespace,
            'metric_name': 'PartialResultProcessingLatency',
            'value': latency_ms,
            'unit': 'Milliseconds',
            'dimensions': {
                'SessionId': session_id
            }
        }
        self._emit_metric(metric)
    
    def emit_partial_to_final_ratio(self, session_id: str, partial_count: int, final_count: int) -> None:
        """
        Emit metric for ratio of partial to final results.
        
        Args:
            session_id: Session identifier
            partial_count: Number of partial results processed
            final_count: Number of final results processed
        """
        if final_count > 0:
            ratio = partial_count / final_count
            metric = {
                'namespace': self.namespace,
                'metric_name': 'PartialToFinalRatio',
                'value': ratio,
                'unit': 'None',
                'dimensions': {
                    'SessionId': session_id
                }
            }
            self._emit_metric(metric)
    
    def emit_duplicates_detected(self, session_id: str, count: int) -> None:
        """
        Emit metric for duplicate results detected.
        
        Args:
            session_id: Session identifier
            count: Number of duplicates detected
        """
        if count > 0:
            metric = {
                'namespace': self.namespace,
                'metric_name': 'DuplicatesDetected',
                'value': count,
                'unit': 'Count',
                'dimensions': {
                    'SessionId': session_id
                }
            }
            self._emit_metric(metric)
    
    def emit_orphaned_results_flushed(self, session_id: str, count: int) -> None:
        """
        Emit metric for orphaned results flushed.
        
        Args:
            session_id: Session identifier
            count: Number of orphaned results flushed
        """
        if count > 0:
            metric = {
                'namespace': self.namespace,
                'metric_name': 'OrphanedResultsFlushed',
                'value': count,
                'unit': 'Count',
                'dimensions': {
                    'SessionId': session_id
                }
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
