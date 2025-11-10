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
    
    def test_log_entry_contains_required_fields(self):
        """Verify log entries contain all required fields."""
        mock_logger = Mock(spec=logging.Logger)
        structured_logger = StructuredLogger(mock_logger, 'TestComponent')
        
        structured_logger.info(
            message='Test message',
            correlation_id='test-session-123',
            operation='test_operation',
            duration_ms=100
        )
        
        # Get the logged message
        assert mock_logger.info.called
        log_entry_str = mock_logger.info.call_args[0][0]
        log_entry = json.loads(log_entry_str)
        
        # Verify required fields
        assert 'timestamp' in log_entry
        assert 'level' in log_entry
        assert log_entry['level'] == 'INFO'
        assert 'component' in log_entry
        assert log_entry['component'] == 'TestComponent'
        assert 'message' in log_entry
        assert log_entry['message'] == 'Test message'
        assert 'correlationId' in log_entry
        assert log_entry['correlationId'] == 'test-session-123'
        assert 'operation' in log_entry
        assert log_entry['operation'] == 'test_operation'
        assert 'durationMs' in log_entry
        assert log_entry['durationMs'] == 100
    
    def test_timestamp_format_is_iso8601(self):
        """Verify timestamp is in ISO 8601 format with Z suffix."""
        mock_logger = Mock(spec=logging.Logger)
        structured_logger = StructuredLogger(mock_logger, 'TestComponent')
        
        structured_logger.info(message='Test')
        
        log_entry_str = mock_logger.info.call_args[0][0]
        log_entry = json.loads(log_entry_str)
        
        # Verify ISO 8601 format with Z suffix
        timestamp = log_entry['timestamp']
        assert timestamp.endswith('Z')
        # Should be parseable as ISO 8601
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    
    def test_user_context_sanitization(self):
        """Verify user context is sanitized (IP addresses hashed)."""
        mock_logger = Mock(spec=logging.Logger)
        structured_logger = StructuredLogger(mock_logger, 'TestComponent')
        
        structured_logger.info(
            message='Test',
            user_id='user-123',
            ip_address='192.168.1.1'
        )
        
        log_entry_str = mock_logger.info.call_args[0][0]
        log_entry = json.loads(log_entry_str)
        
        # Verify user context exists
        assert 'userContext' in log_entry
        user_context = log_entry['userContext']
        
        # User ID should be included as-is
        assert 'userId' in user_context
        assert user_context['userId'] == 'user-123'
        
        # IP address should be hashed
        assert 'ipAddressHash' in user_context
        assert user_context['ipAddressHash'] != '192.168.1.1'
        assert len(user_context['ipAddressHash']) == 16  # SHA256 truncated to 16 chars
    
    def test_error_logging_includes_error_code(self):
        """Verify error logs include error code."""
        mock_logger = Mock(spec=logging.Logger)
        structured_logger = StructuredLogger(mock_logger, 'TestComponent')
        
        structured_logger.error(
            message='Test error',
            correlation_id='test-123',
            error_code='INTERNAL_ERROR'
        )
        
        log_entry_str = mock_logger.error.call_args[0][0]
        log_entry = json.loads(log_entry_str)
        
        assert 'errorCode' in log_entry
        assert log_entry['errorCode'] == 'INTERNAL_ERROR'
    
    def test_error_logging_with_stack_trace(self):
        """Verify error logs can include stack traces."""
        mock_logger = Mock(spec=logging.Logger)
        structured_logger = StructuredLogger(mock_logger, 'TestComponent')
        
        structured_logger.error(
            message='Test error',
            exc_info=True
        )
        
        # Verify exc_info parameter was passed to logger
        assert mock_logger.error.called
        call_kwargs = mock_logger.error.call_args[1]
        assert 'exc_info' in call_kwargs
        assert call_kwargs['exc_info'] is True
    
    def test_warning_logging(self):
        """Verify warning level logging works correctly."""
        mock_logger = Mock(spec=logging.Logger)
        structured_logger = StructuredLogger(mock_logger, 'TestComponent')
        
        structured_logger.warning(
            message='Test warning',
            correlation_id='test-123',
            error_code='RATE_LIMIT_EXCEEDED'
        )
        
        log_entry_str = mock_logger.warning.call_args[0][0]
        log_entry = json.loads(log_entry_str)
        
        assert log_entry['level'] == 'WARNING'
        assert log_entry['message'] == 'Test warning'
        assert log_entry['errorCode'] == 'RATE_LIMIT_EXCEEDED'
    
    def test_debug_logging(self):
        """Verify debug level logging works correctly."""
        mock_logger = Mock(spec=logging.Logger)
        structured_logger = StructuredLogger(mock_logger, 'TestComponent')
        
        structured_logger.debug(
            message='Debug info',
            correlation_id='test-123',
            extra_field='extra_value'
        )
        
        log_entry_str = mock_logger.debug.call_args[0][0]
        log_entry = json.loads(log_entry_str)
        
        assert log_entry['level'] == 'DEBUG'
        assert log_entry['extra_field'] == 'extra_value'
    
    def test_get_structured_logger_returns_instance(self):
        """Verify get_structured_logger factory function."""
        logger = get_structured_logger('TestComponent')
        
        assert isinstance(logger, StructuredLogger)
        assert logger.component == 'TestComponent'
    
    def test_extra_fields_included_in_log(self):
        """Verify extra fields are included in log entries."""
        mock_logger = Mock(spec=logging.Logger)
        structured_logger = StructuredLogger(mock_logger, 'TestComponent')
        
        structured_logger.info(
            message='Test',
            sessionId='session-123',
            listenerCount=5,
            customField='custom_value'
        )
        
        log_entry_str = mock_logger.info.call_args[0][0]
        log_entry = json.loads(log_entry_str)
        
        assert log_entry['sessionId'] == 'session-123'
        assert log_entry['listenerCount'] == 5
        assert log_entry['customField'] == 'custom_value'


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
    
    def test_correlation_id_format(self):
        """Verify correlation ID is included when provided."""
        mock_logger = Mock(spec=logging.Logger)
        structured_logger = StructuredLogger(mock_logger, 'TestComponent')
        
        # Test with session ID
        structured_logger.info(
            message='Test',
            correlation_id='golden-eagle-427'
        )
        
        log_entry_str = mock_logger.info.call_args[0][0]
        log_entry = json.loads(log_entry_str)
        
        assert log_entry['correlationId'] == 'golden-eagle-427'
    
    def test_duration_ms_is_numeric(self):
        """Verify duration_ms is numeric type."""
        mock_logger = Mock(spec=logging.Logger)
        structured_logger = StructuredLogger(mock_logger, 'TestComponent')
        
        structured_logger.info(
            message='Test',
            duration_ms=1234
        )
        
        log_entry_str = mock_logger.info.call_args[0][0]
        log_entry = json.loads(log_entry_str)
        
        assert isinstance(log_entry['durationMs'], int)
        assert log_entry['durationMs'] == 1234
    
    def test_log_without_optional_fields(self):
        """Verify logs work without optional fields."""
        mock_logger = Mock(spec=logging.Logger)
        structured_logger = StructuredLogger(mock_logger, 'TestComponent')
        
        # Minimal log entry
        structured_logger.info(message='Test')
        
        log_entry_str = mock_logger.info.call_args[0][0]
        log_entry = json.loads(log_entry_str)
        
        # Required fields should be present
        assert 'timestamp' in log_entry
        assert 'level' in log_entry
        assert 'component' in log_entry
        assert 'message' in log_entry
        
        # Optional fields should not be present
        assert 'correlationId' not in log_entry
        assert 'operation' not in log_entry
        assert 'durationMs' not in log_entry
    
    def test_ip_address_never_logged_in_plain_text(self):
        """Verify IP addresses are never logged in plain text."""
        mock_logger = Mock(spec=logging.Logger)
        structured_logger = StructuredLogger(mock_logger, 'TestComponent')
        
        test_ip = '192.168.1.100'
        structured_logger.info(
            message='Test',
            ip_address=test_ip
        )
        
        log_entry_str = mock_logger.info.call_args[0][0]
        
        # Plain text IP should not appear anywhere in log
        assert test_ip not in log_entry_str
        
        # But hashed version should be present
        log_entry = json.loads(log_entry_str)
        assert 'userContext' in log_entry
        assert 'ipAddressHash' in log_entry['userContext']
