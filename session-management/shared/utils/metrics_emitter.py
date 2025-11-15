"""
CloudWatch metrics emitter for session management.

This module provides utilities for emitting CloudWatch metrics
for control messages, session status, and connection management.
"""

import time
from typing import Dict, List, Optional
import boto3
from botocore.exceptions import ClientError


class MetricsEmitter:
    """
    Emits CloudWatch metrics for session management operations.
    
    Provides methods for tracking control messages, session status,
    listener notifications, and errors.
    """
    
    def __init__(self, namespace: str = 'SessionManagement/WebSocket'):
        """
        Initialize metrics emitter.
        
        Args:
            namespace: CloudWatch namespace for metrics
        """
        self.namespace = namespace
        self.cloudwatch = boto3.client('cloudwatch')
        self._metric_buffer: List[Dict] = []
        self._buffer_size = 20  # Batch metrics for efficiency
    
    def emit_control_message_received(
        self,
        session_id: str,
        action_type: str
    ) -> None:
        """
        Emit metric for control message received.
        
        Args:
            session_id: Session identifier
            action_type: Type of control action (pause, resume, mute, etc.)
        """
        self._add_metric(
            metric_name='ControlMessagesReceived',
            value=1,
            unit='Count',
            dimensions=[
                {'Name': 'SessionId', 'Value': session_id},
                {'Name': 'ActionType', 'Value': action_type}
            ]
        )
    
    def emit_control_message_latency(
        self,
        session_id: str,
        action_type: str,
        latency_ms: float
    ) -> None:
        """
        Emit metric for control message processing latency.
        
        Args:
            session_id: Session identifier
            action_type: Type of control action
            latency_ms: Processing latency in milliseconds
        """
        self._add_metric(
            metric_name='ControlMessageLatency',
            value=latency_ms,
            unit='Milliseconds',
            dimensions=[
                {'Name': 'SessionId', 'Value': session_id},
                {'Name': 'ActionType', 'Value': action_type}
            ]
        )
    
    def emit_listener_notification_latency(
        self,
        session_id: str,
        listener_count: int,
        latency_ms: float
    ) -> None:
        """
        Emit metric for listener notification latency.
        
        Args:
            session_id: Session identifier
            listener_count: Number of listeners notified
            latency_ms: Notification latency in milliseconds
        """
        self._add_metric(
            metric_name='ListenerNotificationLatency',
            value=latency_ms,
            unit='Milliseconds',
            dimensions=[
                {'Name': 'SessionId', 'Value': session_id}
            ]
        )
        
        self._add_metric(
            metric_name='ListenersNotified',
            value=listener_count,
            unit='Count',
            dimensions=[
                {'Name': 'SessionId', 'Value': session_id}
            ]
        )
    
    def emit_listener_notification_failure(
        self,
        session_id: str,
        connection_id: str,
        error_type: str
    ) -> None:
        """
        Emit metric for listener notification failure.
        
        Args:
            session_id: Session identifier
            connection_id: Connection identifier
            error_type: Type of error (gone, timeout, etc.)
        """
        self._add_metric(
            metric_name='ListenerNotificationFailures',
            value=1,
            unit='Count',
            dimensions=[
                {'Name': 'SessionId', 'Value': session_id},
                {'Name': 'ErrorType', 'Value': error_type}
            ]
        )
    
    def emit_status_query_received(
        self,
        session_id: str
    ) -> None:
        """
        Emit metric for status query received.
        
        Args:
            session_id: Session identifier
        """
        self._add_metric(
            metric_name='StatusQueriesReceived',
            value=1,
            unit='Count',
            dimensions=[
                {'Name': 'SessionId', 'Value': session_id}
            ]
        )
    
    def emit_status_query_latency(
        self,
        session_id: str,
        latency_ms: float
    ) -> None:
        """
        Emit metric for status query processing latency.
        
        Args:
            session_id: Session identifier
            latency_ms: Query latency in milliseconds
        """
        self._add_metric(
            metric_name='StatusQueryLatency',
            value=latency_ms,
            unit='Milliseconds',
            dimensions=[
                {'Name': 'SessionId', 'Value': session_id}
            ]
        )
    
    def emit_periodic_status_update_sent(
        self,
        session_id: str
    ) -> None:
        """
        Emit metric for periodic status update sent.
        
        Args:
            session_id: Session identifier
        """
        self._add_metric(
            metric_name='PeriodicStatusUpdatesSent',
            value=1,
            unit='Count',
            dimensions=[
                {'Name': 'SessionId', 'Value': session_id}
            ]
        )
    
    def emit_lambda_error(
        self,
        handler_name: str,
        error_type: str
    ) -> None:
        """
        Emit metric for Lambda error.
        
        Args:
            handler_name: Name of Lambda handler
            error_type: Type of error
        """
        self._add_metric(
            metric_name='LambdaErrors',
            value=1,
            unit='Count',
            dimensions=[
                {'Name': 'Handler', 'Value': handler_name},
                {'Name': 'ErrorType', 'Value': error_type}
            ]
        )
    
    def emit_dynamodb_error(
        self,
        operation: str,
        error_code: str
    ) -> None:
        """
        Emit metric for DynamoDB error.
        
        Args:
            operation: DynamoDB operation (GetItem, UpdateItem, etc.)
            error_code: Error code from DynamoDB
        """
        self._add_metric(
            metric_name='DynamoDBErrors',
            value=1,
            unit='Count',
            dimensions=[
                {'Name': 'Operation', 'Value': operation},
                {'Name': 'ErrorCode', 'Value': error_code}
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
        metric_type: str,
        session_id: str,
        action_type: Optional[str] = None
    ):
        """
        Initialize metrics context.
        
        Args:
            emitter: MetricsEmitter instance
            metric_type: Type of metric (control, status)
            session_id: Session identifier
            action_type: Action type for control messages
        """
        self.emitter = emitter
        self.metric_type = metric_type
        self.session_id = session_id
        self.action_type = action_type
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        """Start timing."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Emit latency metric."""
        if self.start_time is not None:
            latency_ms = (time.time() - self.start_time) * 1000
            
            if self.metric_type == 'control' and self.action_type:
                self.emitter.emit_control_message_latency(
                    self.session_id,
                    self.action_type,
                    latency_ms
                )
            elif self.metric_type == 'status':
                self.emitter.emit_status_query_latency(
                    self.session_id,
                    latency_ms
                )
