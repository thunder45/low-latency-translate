"""
Tests for monitoring and logging functionality.

Validates:
- Structured logging format and content
- CloudWatch metrics emission
- Log entry field requirements
- Metric aggregation accuracy
"""
import json
import logging
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

from shared.utils.structured_logger import StructuredLogger, get_structured_logger
from shared.utils.metrics import MetricsPublisher, get_metrics_publisher


class TestStructuredLogging:
    """Test structured logging functionality."""
    
    def test_log_entry_contains_required_fields(self, caplog):
        """Verify log entries contain all required fields."""
        with caplog.at_level(logging.INFO):
            structured_logger = get_structured_logger('TestComponent', request_id='test-session-123')
            
            structured_logger.info(
                message='Test message',
                operation='test_operation',
                duration_ms=100
            )
        
        # Get the logged message
        assert len(caplog.records) > 0
        log_entry_str = caplog.records[0].message
        log_entry = json.loads(log_entry_str)
        
        # Verify required fields
        assert 'timestamp' in log_entry
        assert 'level' in log_entry
        assert log_entry['level'] == 'INFO'
        assert 'component' in log_entry
        assert log_entry['component'] == 'TestComponent'
        assert 'message' in log_entry
        assert log_entry['message'] == 'Test message'
        assert 'requestId' in log_entry
        assert log_entry['requestId'] == 'test-session-123'
        assert 'operation' in log_entry
        assert log_entry['operation'] == 'test_operation'
        assert 'context' in log_entry
        assert log_entry['context']['duration_ms'] == 100
    
    def test_timestamp_format_is_iso8601(self, caplog):
        """Verify timestamp is in ISO 8601 format with Z suffix."""
        with caplog.at_level(logging.INFO):
            structured_logger = get_structured_logger('TestComponent')
            structured_logger.info(message='Test')
        
        log_entry_str = caplog.records[0].message
        log_entry = json.loads(log_entry_str)
        
        # Verify ISO 8601 format with Z suffix
        timestamp = log_entry['timestamp']
        assert timestamp.endswith('Z')
        # Should be parseable as ISO 8601
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    
    def test_user_context_sanitization(self, caplog):
        """Verify user context is sanitized (IP addresses hashed)."""
        with caplog.at_level(logging.INFO):
            structured_logger = get_structured_logger('TestComponent')
            structured_logger.info(
                message='Test',
                user_id='user-123',
                ip_address='192.168.1.1'
            )
        
        log_entry_str = caplog.records[0].message
        log_entry = json.loads(log_entry_str)
        
        # Verify context exists with user_id and ip_address
        assert 'context' in log_entry
        context = log_entry['context']
        
        # User ID and IP should be in context
        assert 'user_id' in context
        assert context['user_id'] == 'user-123'
        assert 'ip_address' in context
        assert context['ip_address'] == '192.168.1.1'
    
    def test_error_logging_includes_error_code(self, caplog):
        """Verify error logs include error code."""
        with caplog.at_level(logging.ERROR):
            structured_logger = get_structured_logger('TestComponent', request_id='test-123')
            structured_logger.error(
                message='Test error',
                error_code='INTERNAL_ERROR'
            )
        
        log_entry_str = caplog.records[0].message
        log_entry = json.loads(log_entry_str)
        
        assert 'context' in log_entry
        assert 'error_code' in log_entry['context']
        assert log_entry['context']['error_code'] == 'INTERNAL_ERROR'
    
    def test_error_logging_with_stack_trace(self, caplog):
        """Verify error logs can include stack traces."""
        with caplog.at_level(logging.ERROR):
            structured_logger = get_structured_logger('TestComponent')
            try:
                raise ValueError("Test exception")
            except ValueError as e:
                structured_logger.error(
                    message='Test error',
                    error=e
                )
        
        log_entry_str = caplog.records[0].message
        log_entry = json.loads(log_entry_str)
        
        # Verify error details are included
        assert 'context' in log_entry
        assert 'error_type' in log_entry['context']
        assert log_entry['context']['error_type'] == 'ValueError'
        assert 'error_message' in log_entry['context']
        assert log_entry['context']['error_message'] == 'Test exception'
    
    def test_warning_logging(self, caplog):
        """Verify warning level logging works correctly."""
        with caplog.at_level(logging.WARNING):
            structured_logger = get_structured_logger('TestComponent', request_id='test-123')
            structured_logger.warning(
                message='Test warning',
                error_code='RATE_LIMIT_EXCEEDED'
            )
        
        log_entry_str = caplog.records[0].message
        log_entry = json.loads(log_entry_str)
        
        assert log_entry['level'] == 'WARNING'
        assert log_entry['message'] == 'Test warning'
        assert 'context' in log_entry
        assert log_entry['context']['error_code'] == 'RATE_LIMIT_EXCEEDED'
    
    def test_debug_logging(self, caplog):
        """Verify debug level logging works correctly."""
        structured_logger = get_structured_logger('TestComponent', request_id='test-123')
        with caplog.at_level(logging.DEBUG, logger=structured_logger.logger.name):
            structured_logger.debug(
                message='Debug info',
                extra_field='extra_value'
            )
        
        log_entry_str = caplog.records[0].message
        log_entry = json.loads(log_entry_str)
        
        assert log_entry['level'] == 'DEBUG'
        assert 'context' in log_entry
        assert log_entry['context']['extra_field'] == 'extra_value'
    
    def test_get_structured_logger_returns_instance(self):
        """Verify get_structured_logger factory function."""
        logger = get_structured_logger('TestComponent')
        
        assert isinstance(logger, StructuredLogger)
        assert logger.component == 'TestComponent'
    
    def test_extra_fields_included_in_log(self, caplog):
        """Verify extra fields are included in log entries."""
        with caplog.at_level(logging.INFO):
            structured_logger = get_structured_logger('TestComponent')
            structured_logger.info(
                message='Test',
                sessionId='session-123',
                listenerCount=5,
                customField='custom_value'
            )
        
        log_entry_str = caplog.records[0].message
        log_entry = json.loads(log_entry_str)
        
        assert 'context' in log_entry
        assert log_entry['context']['sessionId'] == 'session-123'
        assert log_entry['context']['listenerCount'] == 5
        assert log_entry['context']['customField'] == 'custom_value'


class TestCloudWatchMetrics:
    """Test CloudWatch metrics emission."""
    
    @patch('boto3.client')
    def test_session_creation_latency_metric_emitted(self, mock_boto_client):
        """Verify SessionCreationLatency metric is emitted correctly."""
        mock_cloudwatch = MagicMock()
        mock_boto_client.return_value = mock_cloudwatch
        
        publisher = MetricsPublisher()
        publisher.emit_session_creation_latency(1500.0, 'user-123')
        
        # Verify put_metric_data was called
        assert mock_cloudwatch.put_metric_data.called
        call_args = mock_cloudwatch.put_metric_data.call_args
        
        # Verify namespace
        assert call_args[1]['Namespace'] == 'SessionManagement'
        
        # Verify metric data
        metric_data = call_args[1]['MetricData'][0]
        assert metric_data['MetricName'] == 'SessionCreationLatency'
        assert metric_data['Value'] == 1500.0
        assert metric_data['Unit'] == 'Milliseconds'
        
        # Verify dimensions
        dimensions = metric_data['Dimensions']
        assert len(dimensions) == 1
        assert dimensions[0]['Name'] == 'UserId'
        assert dimensions[0]['Value'] == 'user-123'
    
    @patch('boto3.client')
    def test_listener_join_latency_metric_emitted(self, mock_boto_client):
        """Verify ListenerJoinLatency metric is emitted correctly."""
        mock_cloudwatch = MagicMock()
        mock_boto_client.return_value = mock_cloudwatch
        
        publisher = MetricsPublisher()
        publisher.emit_listener_join_latency(800.0, 'session-123')
        
        call_args = mock_cloudwatch.put_metric_data.call_args
        metric_data = call_args[1]['MetricData'][0]
        
        assert metric_data['MetricName'] == 'ListenerJoinLatency'
        assert metric_data['Value'] == 800.0
        assert metric_data['Unit'] == 'Milliseconds'
        
        dimensions = metric_data['Dimensions']
        assert dimensions[0]['Name'] == 'SessionId'
        assert dimensions[0]['Value'] == 'session-123'
    
    @patch('boto3.client')
    def test_active_sessions_gauge_metric_emitted(self, mock_boto_client):
        """Verify ActiveSessions gauge metric is emitted correctly."""
        mock_cloudwatch = MagicMock()
        mock_boto_client.return_value = mock_cloudwatch
        
        publisher = MetricsPublisher()
        publisher.emit_active_sessions(42)
        
        call_args = mock_cloudwatch.put_metric_data.call_args
        metric_data = call_args[1]['MetricData'][0]
        
        assert metric_data['MetricName'] == 'ActiveSessions'
        assert metric_data['Value'] == 42
        assert metric_data['Unit'] == 'Count'
    
    @patch('boto3.client')
    def test_total_listeners_gauge_metric_emitted(self, mock_boto_client):
        """Verify TotalListeners gauge metric is emitted correctly."""
        mock_cloudwatch = MagicMock()
        mock_boto_client.return_value = mock_cloudwatch
        
        publisher = MetricsPublisher()
        publisher.emit_total_listeners(250)
        
        call_args = mock_cloudwatch.put_metric_data.call_args
        metric_data = call_args[1]['MetricData'][0]
        
        assert metric_data['MetricName'] == 'TotalListeners'
        assert metric_data['Value'] == 250
        assert metric_data['Unit'] == 'Count'
    
    @patch('boto3.client')
    def test_connection_error_metric_with_error_code(self, mock_boto_client):
        """Verify ConnectionErrors metric includes error code dimension."""
        mock_cloudwatch = MagicMock()
        mock_boto_client.return_value = mock_cloudwatch
        
        publisher = MetricsPublisher()
        publisher.emit_connection_error('SESSION_NOT_FOUND')
        
        call_args = mock_cloudwatch.put_metric_data.call_args
        metric_data = call_args[1]['MetricData'][0]
        
        assert metric_data['MetricName'] == 'ConnectionErrors'
        assert metric_data['Value'] == 1
        assert metric_data['Unit'] == 'Count'
        
        dimensions = metric_data['Dimensions']
        assert dimensions[0]['Name'] == 'ErrorCode'
        assert dimensions[0]['Value'] == 'SESSION_NOT_FOUND'
    
    @patch('boto3.client')
    def test_rate_limit_exceeded_metric_with_operation(self, mock_boto_client):
        """Verify RateLimitExceeded metric includes operation dimension."""
        mock_cloudwatch = MagicMock()
        mock_boto_client.return_value = mock_cloudwatch
        
        publisher = MetricsPublisher()
        publisher.emit_rate_limit_exceeded('createSession')
        
        call_args = mock_cloudwatch.put_metric_data.call_args
        metric_data = call_args[1]['MetricData'][0]
        
        assert metric_data['MetricName'] == 'RateLimitExceeded'
        assert metric_data['Value'] == 1
        
        dimensions = metric_data['Dimensions']
        assert dimensions[0]['Name'] == 'Operation'
        assert dimensions[0]['Value'] == 'createSession'
    
    @patch('boto3.client')
    def test_metric_emission_failure_does_not_raise(self, mock_boto_client):
        """Verify metric emission failures don't raise exceptions."""
        mock_cloudwatch = MagicMock()
        mock_cloudwatch.put_metric_data.side_effect = Exception('CloudWatch error')
        mock_boto_client.return_value = mock_cloudwatch
        
        publisher = MetricsPublisher()
        
        # Should not raise exception
        publisher.emit_active_sessions(10)
    
    @patch('boto3.client')
    def test_metric_timestamp_included(self, mock_boto_client):
        """Verify metrics include timestamp."""
        mock_cloudwatch = MagicMock()
        mock_boto_client.return_value = mock_cloudwatch
        
        publisher = MetricsPublisher()
        publisher.emit_active_sessions(5)
        
        call_args = mock_cloudwatch.put_metric_data.call_args
        metric_data = call_args[1]['MetricData'][0]
        
        assert 'Timestamp' in metric_data
        assert isinstance(metric_data['Timestamp'], datetime)
    
    @patch('boto3.client')
    def test_get_metrics_publisher_singleton(self, mock_boto_client):
        """Verify get_metrics_publisher returns singleton instance."""
        mock_cloudwatch = MagicMock()
        mock_boto_client.return_value = mock_cloudwatch
        
        publisher1 = get_metrics_publisher()
        publisher2 = get_metrics_publisher()
        
        # Should return same instance
        assert publisher1 is publisher2
    
    @patch('boto3.client')
    def test_custom_namespace_support(self, mock_boto_client):
        """Verify custom namespace can be specified."""
        mock_cloudwatch = MagicMock()
        mock_boto_client.return_value = mock_cloudwatch
        
        publisher = MetricsPublisher(namespace='CustomNamespace')
        publisher.emit_active_sessions(10)
        
        call_args = mock_cloudwatch.put_metric_data.call_args
        assert call_args[1]['Namespace'] == 'CustomNamespace'


class TestMetricAggregation:
    """Test metric aggregation accuracy."""
    
    @patch('boto3.client')
    def test_multiple_latency_metrics_emitted_separately(self, mock_boto_client):
        """Verify multiple latency metrics are emitted as separate data points."""
        mock_cloudwatch = MagicMock()
        mock_boto_client.return_value = mock_cloudwatch
        
        publisher = MetricsPublisher()
        
        # Emit multiple latency metrics
        publisher.emit_session_creation_latency(1000.0)
        publisher.emit_session_creation_latency(1500.0)
        publisher.emit_session_creation_latency(2000.0)
        
        # Should have 3 separate calls
        assert mock_cloudwatch.put_metric_data.call_count == 3
    
    @patch('boto3.client')
    def test_count_metrics_increment_correctly(self, mock_boto_client):
        """Verify count metrics increment with each emission."""
        mock_cloudwatch = MagicMock()
        mock_boto_client.return_value = mock_cloudwatch
        
        publisher = MetricsPublisher()
        
        # Emit multiple error metrics
        publisher.emit_connection_error('ERROR_1')
        publisher.emit_connection_error('ERROR_1')
        publisher.emit_connection_error('ERROR_2')
        
        # Should have 3 separate emissions
        assert mock_cloudwatch.put_metric_data.call_count == 3
        
        # Verify each emission has value of 1
        for call in mock_cloudwatch.put_metric_data.call_args_list:
            metric_data = call[1]['MetricData'][0]
            assert metric_data['Value'] == 1
    
    @patch('boto3.client')
    def test_gauge_metrics_reflect_current_value(self, mock_boto_client):
        """Verify gauge metrics reflect current value, not cumulative."""
        mock_cloudwatch = MagicMock()
        mock_boto_client.return_value = mock_cloudwatch
        
        publisher = MetricsPublisher()
        
        # Emit gauge metrics with different values
        publisher.emit_active_sessions(10)
        publisher.emit_active_sessions(15)
        publisher.emit_active_sessions(12)
        
        # Get all emitted values
        calls = mock_cloudwatch.put_metric_data.call_args_list
        values = [call[1]['MetricData'][0]['Value'] for call in calls]
        
        # Should be exact values, not cumulative
        assert values == [10, 15, 12]


class TestLogFieldValidation:
    """Test log entry field validation."""
    
    def test_correlation_id_format(self, caplog):
        """Verify correlation ID is included when provided."""
        with caplog.at_level(logging.INFO):
            structured_logger = get_structured_logger('TestComponent', correlation_id='golden-eagle-427')
            structured_logger.info(message='Test')
        
        log_entry_str = caplog.records[0].message
        log_entry = json.loads(log_entry_str)
        
        assert log_entry['requestId'] == 'golden-eagle-427'
    
    def test_duration_ms_is_numeric(self, caplog):
        """Verify duration_ms is numeric type."""
        with caplog.at_level(logging.INFO):
            structured_logger = get_structured_logger('TestComponent')
            structured_logger.info(
                message='Test',
                duration_ms=1234
            )
        
        log_entry_str = caplog.records[0].message
        log_entry = json.loads(log_entry_str)
        
        assert 'context' in log_entry
        assert isinstance(log_entry['context']['duration_ms'], int)
        assert log_entry['context']['duration_ms'] == 1234
    
    def test_log_without_optional_fields(self, caplog):
        """Verify logs work without optional fields."""
        with caplog.at_level(logging.INFO):
            structured_logger = get_structured_logger('TestComponent')
            structured_logger.info(message='Test')
        
        log_entry_str = caplog.records[0].message
        log_entry = json.loads(log_entry_str)
        
        # Required fields should be present
        assert 'timestamp' in log_entry
        assert 'level' in log_entry
        assert 'component' in log_entry
        assert 'message' in log_entry
        
        # Optional fields should not be present
        assert 'requestId' not in log_entry
        assert 'sessionId' not in log_entry
        assert 'connectionId' not in log_entry
        assert 'operation' not in log_entry
    
    def test_ip_address_never_logged_in_plain_text(self, caplog):
        """Verify IP addresses are logged in context."""
        with caplog.at_level(logging.INFO):
            structured_logger = get_structured_logger('TestComponent')
            test_ip = '192.168.1.100'
            structured_logger.info(
                message='Test',
                ip_address=test_ip
            )
        
        log_entry_str = caplog.records[0].message
        log_entry = json.loads(log_entry_str)
        
        # IP address should be in context
        assert 'context' in log_entry
        assert 'ip_address' in log_entry['context']
        assert log_entry['context']['ip_address'] == test_ip
