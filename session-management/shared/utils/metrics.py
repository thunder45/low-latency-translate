"""
CloudWatch metrics utility for emitting custom metrics.

Provides methods for emitting:
- Latency metrics (p50, p95, p99)
- Gauge metrics (active sessions, total listeners)
- Count metrics (errors, rate limits)
"""
import boto3
import os
from typing import List, Dict, Optional
from datetime import datetime, timezone


class MetricsPublisher:
    """
    CloudWatch metrics publisher for session management metrics.
    """
    
    def __init__(self, namespace: str = 'SessionManagement'):
        """
        Initialize metrics publisher.
        
        Args:
            namespace: CloudWatch metrics namespace
        """
        self.namespace = namespace
        self.cloudwatch = boto3.client('cloudwatch', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
    
    def put_latency_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = 'Milliseconds',
        dimensions: Optional[List[Dict[str, str]]] = None
    ):
        """
        Emit latency metric.
        
        Args:
            metric_name: Metric name (e.g., 'SessionCreationLatency')
            value: Latency value in milliseconds
            unit: Metric unit (default: Milliseconds)
            dimensions: Metric dimensions
        """
        self._put_metric(
            metric_name=metric_name,
            value=value,
            unit=unit,
            dimensions=dimensions or []
        )
    
    def put_count_metric(
        self,
        metric_name: str,
        value: int = 1,
        dimensions: Optional[List[Dict[str, str]]] = None
    ):
        """
        Emit count metric.
        
        Args:
            metric_name: Metric name (e.g., 'ConnectionErrors')
            value: Count value (default: 1)
            dimensions: Metric dimensions
        """
        self._put_metric(
            metric_name=metric_name,
            value=value,
            unit='Count',
            dimensions=dimensions or []
        )
    
    def put_gauge_metric(
        self,
        metric_name: str,
        value: int,
        dimensions: Optional[List[Dict[str, str]]] = None
    ):
        """
        Emit gauge metric.
        
        Args:
            metric_name: Metric name (e.g., 'ActiveSessions')
            value: Gauge value
            dimensions: Metric dimensions
        """
        self._put_metric(
            metric_name=metric_name,
            value=value,
            unit='Count',
            dimensions=dimensions or []
        )
    
    def _put_metric(
        self,
        metric_name: str,
        value: float,
        unit: str,
        dimensions: List[Dict[str, str]]
    ):
        """
        Put metric to CloudWatch.
        
        Args:
            metric_name: Metric name
            value: Metric value
            unit: Metric unit
            dimensions: Metric dimensions
        """
        try:
            metric_data = {
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit,
                'Timestamp': datetime.now(timezone.utc)
            }
            
            if dimensions:
                metric_data['Dimensions'] = dimensions
            
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[metric_data]
            )
        except Exception as e:
            # Log error but don't fail the operation
            print(f"Failed to emit metric {metric_name}: {e}")
    
    def emit_session_creation_latency(self, duration_ms: float, user_id: Optional[str] = None):
        """
        Emit session creation latency metric.
        
        Args:
            duration_ms: Duration in milliseconds
            user_id: User ID (optional dimension)
        """
        dimensions = []
        if user_id:
            dimensions.append({'Name': 'UserId', 'Value': user_id})
        
        self.put_latency_metric(
            metric_name='SessionCreationLatency',
            value=duration_ms,
            dimensions=dimensions
        )
    
    def emit_listener_join_latency(self, duration_ms: float, session_id: Optional[str] = None):
        """
        Emit listener join latency metric.
        
        Args:
            duration_ms: Duration in milliseconds
            session_id: Session ID (optional dimension)
        """
        dimensions = []
        if session_id:
            dimensions.append({'Name': 'SessionId', 'Value': session_id})
        
        self.put_latency_metric(
            metric_name='ListenerJoinLatency',
            value=duration_ms,
            dimensions=dimensions
        )
    
    def emit_active_sessions(self, count: int):
        """
        Emit active sessions gauge metric.
        
        Args:
            count: Number of active sessions
        """
        self.put_gauge_metric(
            metric_name='ActiveSessions',
            value=count
        )
    
    def emit_total_listeners(self, count: int):
        """
        Emit total listeners gauge metric.
        
        Args:
            count: Total number of listeners across all sessions
        """
        self.put_gauge_metric(
            metric_name='TotalListeners',
            value=count
        )
    
    def emit_connection_error(self, error_code: str):
        """
        Emit connection error count metric.
        
        Args:
            error_code: Error code
        """
        self.put_count_metric(
            metric_name='ConnectionErrors',
            value=1,
            dimensions=[{'Name': 'ErrorCode', 'Value': error_code}]
        )
    
    def emit_rate_limit_exceeded(self, operation: str):
        """
        Emit rate limit exceeded count metric.
        
        Args:
            operation: Operation that was rate limited
        """
        self.put_count_metric(
            metric_name='RateLimitExceeded',
            value=1,
            dimensions=[{'Name': 'Operation', 'Value': operation}]
        )


# Global metrics publisher instance (reused across Lambda invocations)
_metrics_publisher = None


def get_metrics_publisher() -> MetricsPublisher:
    """
    Get global metrics publisher instance.
    
    Returns:
        MetricsPublisher instance
    """
    global _metrics_publisher
    if _metrics_publisher is None:
        _metrics_publisher = MetricsPublisher()
    return _metrics_publisher
