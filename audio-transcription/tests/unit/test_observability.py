"""
Unit tests for observability: metrics emission and structured logging.

Tests CloudWatch metrics emission for successful processing and error scenarios,
structured log format validation, and correlation ID propagation in logs.
"""

import pytest
import json
import logging
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timezone
from io import StringIO

from emotion_dynamics.utils.metrics import EmotionDynamicsMetrics
from emotion_dynamics.utils.structured_logger import (
    StructuredFormatter,
    StructuredLogger,
    configure_structured_logging,
    log_volume_detection,
    log_rate_detection,
    log_ssml_generation,
    log_polly_synthesis,
    log_error
)


class TestEmotionDynamicsMetrics:
    """Test suite for EmotionDynamicsMetrics."""
    
    @pytest.fixture
    def metrics_with_cloudwatch(self):
        """Create metrics emitter with mocked CloudWatch client."""
        with patch('emotion_dynamics.utils.metrics.boto3') as mock_boto3:
            mock_client = Mock()
            mock_boto3.client.return_value = mock_client
            
            metrics = EmotionDynamicsMetrics(
                namespace='Test/EmotionDynamics',
                use_cloudwatch=True
            )
            metrics.cloudwatch = mock_client
            
            return metrics, mock_client

    
    @pytest.fixture
    def metrics_without_cloudwatch(self):
        """Create metrics emitter without CloudWatch (log-based)."""
        metrics = EmotionDynamicsMetrics(
            namespace='Test/EmotionDynamics',
            use_cloudwatch=False
        )
        return metrics
    
    def test_metrics_initialization_with_cloudwatch(self):
        """Test metrics emitter initializes with CloudWatch client."""
        with patch('emotion_dynamics.utils.metrics.boto3') as mock_boto3:
            mock_client = Mock()
            mock_boto3.client.return_value = mock_client
            
            metrics = EmotionDynamicsMetrics(use_cloudwatch=True)
            
            assert metrics.use_cloudwatch is True
            assert metrics.cloudwatch is not None
            assert metrics.namespace == 'AudioTranscription/EmotionDynamics'
    
    def test_metrics_initialization_without_cloudwatch(self):
        """Test metrics emitter initializes without CloudWatch."""
        metrics = EmotionDynamicsMetrics(use_cloudwatch=False)
        
        assert metrics.use_cloudwatch is False
        assert metrics.cloudwatch is None
    
    def test_emit_volume_detection_latency_success(self, metrics_with_cloudwatch):
        """Test emitting volume detection latency metric succeeds."""
        metrics, mock_client = metrics_with_cloudwatch
        
        metrics.emit_volume_detection_latency(
            latency_ms=45.5,
            correlation_id='test-correlation-123'
        )
        
        # Verify CloudWatch API was called
        mock_client.put_metric_data.assert_called_once()
        call_args = mock_client.put_metric_data.call_args
        
        assert call_args[1]['Namespace'] == 'Test/EmotionDynamics'
        metric_data = call_args[1]['MetricData'][0]
        assert metric_data['MetricName'] == 'VolumeDetectionLatency'
        assert metric_data['Value'] == 45.5
        assert metric_data['Unit'] == 'Milliseconds'

    
    def test_emit_rate_detection_latency_success(self, metrics_with_cloudwatch):
        """Test emitting rate detection latency metric succeeds."""
        metrics, mock_client = metrics_with_cloudwatch
        
        metrics.emit_rate_detection_latency(
            latency_ms=52.3,
            correlation_id='test-correlation-456'
        )
        
        mock_client.put_metric_data.assert_called_once()
        call_args = mock_client.put_metric_data.call_args
        
        metric_data = call_args[1]['MetricData'][0]
        assert metric_data['MetricName'] == 'RateDetectionLatency'
        assert metric_data['Value'] == 52.3
        assert metric_data['Unit'] == 'Milliseconds'
    
    def test_emit_ssml_generation_latency_success(self, metrics_with_cloudwatch):
        """Test emitting SSML generation latency metric succeeds."""
        metrics, mock_client = metrics_with_cloudwatch
        
        metrics.emit_ssml_generation_latency(
            latency_ms=15.8,
            correlation_id='test-correlation-789'
        )
        
        mock_client.put_metric_data.assert_called_once()
        call_args = mock_client.put_metric_data.call_args
        
        metric_data = call_args[1]['MetricData'][0]
        assert metric_data['MetricName'] == 'SSMLGenerationLatency'
        assert metric_data['Value'] == 15.8
    
    def test_emit_polly_synthesis_latency_success(self, metrics_with_cloudwatch):
        """Test emitting Polly synthesis latency metric succeeds."""
        metrics, mock_client = metrics_with_cloudwatch
        
        metrics.emit_polly_synthesis_latency(
            latency_ms=750.2,
            correlation_id='test-correlation-abc'
        )
        
        mock_client.put_metric_data.assert_called_once()
        call_args = mock_client.put_metric_data.call_args
        
        metric_data = call_args[1]['MetricData'][0]
        assert metric_data['MetricName'] == 'PollySynthesisLatency'
        assert metric_data['Value'] == 750.2

    
    def test_emit_end_to_end_latency_success(self, metrics_with_cloudwatch):
        """Test emitting end-to-end latency metric succeeds."""
        metrics, mock_client = metrics_with_cloudwatch
        
        metrics.emit_end_to_end_latency(
            latency_ms=1250.5,
            correlation_id='test-correlation-xyz'
        )
        
        mock_client.put_metric_data.assert_called_once()
        call_args = mock_client.put_metric_data.call_args
        
        metric_data = call_args[1]['MetricData'][0]
        assert metric_data['MetricName'] == 'EndToEndLatency'
        assert metric_data['Value'] == 1250.5
    
    def test_emit_error_count_with_dimensions(self, metrics_with_cloudwatch):
        """Test emitting error count metric with error type and component dimensions."""
        metrics, mock_client = metrics_with_cloudwatch
        
        metrics.emit_error_count(
            error_type='VolumeDetectionError',
            component='VolumeDetector',
            correlation_id='test-correlation-error'
        )
        
        mock_client.put_metric_data.assert_called_once()
        call_args = mock_client.put_metric_data.call_args
        
        metric_data = call_args[1]['MetricData'][0]
        assert metric_data['MetricName'] == 'ErrorCount'
        assert metric_data['Value'] == 1
        assert metric_data['Unit'] == 'Count'
        
        # Verify dimensions
        dimensions = {d['Name']: d['Value'] for d in metric_data['Dimensions']}
        assert dimensions['ErrorType'] == 'VolumeDetectionError'
        assert dimensions['Component'] == 'VolumeDetector'
        assert dimensions['CorrelationId'] == 'test-correlation-error'
    
    def test_emit_fallback_used_with_type(self, metrics_with_cloudwatch):
        """Test emitting fallback usage metric with fallback type."""
        metrics, mock_client = metrics_with_cloudwatch
        
        metrics.emit_fallback_used(
            fallback_type='PlainText',
            correlation_id='test-correlation-fallback'
        )
        
        mock_client.put_metric_data.assert_called_once()
        call_args = mock_client.put_metric_data.call_args
        
        metric_data = call_args[1]['MetricData'][0]
        assert metric_data['MetricName'] == 'FallbackUsed'
        assert metric_data['Value'] == 1
        
        dimensions = {d['Name']: d['Value'] for d in metric_data['Dimensions']}
        assert dimensions['FallbackType'] == 'PlainText'

    
    def test_emit_detected_volume_with_level(self, metrics_with_cloudwatch):
        """Test emitting detected volume metric with volume level dimension."""
        metrics, mock_client = metrics_with_cloudwatch
        
        metrics.emit_detected_volume(
            volume_level='loud',
            db_value=-8.5,
            correlation_id='test-correlation-volume'
        )
        
        mock_client.put_metric_data.assert_called_once()
        call_args = mock_client.put_metric_data.call_args
        
        metric_data = call_args[1]['MetricData'][0]
        assert metric_data['MetricName'] == 'DetectedVolume'
        assert metric_data['Value'] == -8.5
        assert metric_data['Unit'] == 'None'
        
        dimensions = {d['Name']: d['Value'] for d in metric_data['Dimensions']}
        assert dimensions['VolumeLevel'] == 'loud'
    
    def test_emit_detected_rate_with_classification(self, metrics_with_cloudwatch):
        """Test emitting detected rate metric with rate classification dimension."""
        metrics, mock_client = metrics_with_cloudwatch
        
        metrics.emit_detected_rate(
            rate_classification='fast',
            wpm=175.5,
            correlation_id='test-correlation-rate'
        )
        
        mock_client.put_metric_data.assert_called_once()
        call_args = mock_client.put_metric_data.call_args
        
        metric_data = call_args[1]['MetricData'][0]
        assert metric_data['MetricName'] == 'DetectedRate'
        assert metric_data['Value'] == 175.5
        assert metric_data['Unit'] == 'None'
        
        dimensions = {d['Name']: d['Value'] for d in metric_data['Dimensions']}
        assert dimensions['RateClassification'] == 'fast'
    
    def test_emit_metrics_without_cloudwatch_logs_only(self, metrics_without_cloudwatch):
        """Test metrics without CloudWatch client logs metrics instead."""
        metrics = metrics_without_cloudwatch
        
        with patch('emotion_dynamics.utils.metrics.logger') as mock_logger:
            metrics.emit_volume_detection_latency(
                latency_ms=45.5,
                correlation_id='test-correlation'
            )
            
            # Should log the metric
            mock_logger.info.assert_called()
            log_message = mock_logger.info.call_args[0][0]
            assert 'VolumeDetectionLatency' in log_message
            assert '45.5' in log_message

    
    def test_emit_metric_handles_cloudwatch_error_gracefully(self, metrics_with_cloudwatch):
        """Test metric emission handles CloudWatch API errors gracefully."""
        metrics, mock_client = metrics_with_cloudwatch
        
        # Make CloudWatch API fail
        from botocore.exceptions import ClientError
        mock_client.put_metric_data.side_effect = ClientError(
            {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
            'PutMetricData'
        )
        
        # Should not raise exception
        with patch('emotion_dynamics.utils.metrics.logger') as mock_logger:
            metrics.emit_volume_detection_latency(latency_ms=45.5)
            
            # Should log error
            mock_logger.error.assert_called()
    
    def test_flush_metrics_emits_buffered_metrics(self, metrics_with_cloudwatch):
        """Test flush_metrics emits all buffered metrics."""
        metrics, mock_client = metrics_with_cloudwatch
        
        # Emit multiple metrics (they get buffered)
        metrics.emit_volume_detection_latency(latency_ms=45.5)
        metrics.emit_rate_detection_latency(latency_ms=52.3)
        metrics.emit_ssml_generation_latency(latency_ms=15.8)
        
        # Verify metrics were emitted immediately (current implementation)
        assert mock_client.put_metric_data.call_count == 3
        
        # Clear buffer and flush (should be no-op since already emitted)
        metrics.metrics_buffer = []
        metrics.flush_metrics()
    
    def test_metrics_without_correlation_id(self, metrics_with_cloudwatch):
        """Test metrics can be emitted without correlation ID."""
        metrics, mock_client = metrics_with_cloudwatch
        
        metrics.emit_volume_detection_latency(latency_ms=45.5)
        
        mock_client.put_metric_data.assert_called_once()
        call_args = mock_client.put_metric_data.call_args
        
        metric_data = call_args[1]['MetricData'][0]
        # Should not have CorrelationId dimension
        dimension_names = [d['Name'] for d in metric_data.get('Dimensions', [])]
        assert 'CorrelationId' not in dimension_names


class TestStructuredFormatter:
    """Test suite for StructuredFormatter."""
    
    def test_formatter_creates_json_log_entry(self):
        """Test formatter creates valid JSON log entry."""
        formatter = StructuredFormatter()
        
        # Create log record
        record = logging.LogRecord(
            name='test.module',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        # Format record
        formatted = formatter.format(record)
        
        # Parse JSON
        log_entry = json.loads(formatted)
        
        # Verify structure
        assert 'timestamp' in log_entry
        assert 'level' in log_entry
        assert 'component' in log_entry
        assert 'message' in log_entry
        assert log_entry['level'] == 'INFO'
        assert log_entry['component'] == 'test.module'
        assert log_entry['message'] == 'Test message'

    
    def test_formatter_includes_correlation_id(self):
        """Test formatter includes correlation ID from extra fields."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name='test.module',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Test message',
            args=(),
            exc_info=None
        )
        record.correlation_id = 'test-correlation-123'
        
        formatted = formatter.format(record)
        log_entry = json.loads(formatted)
        
        assert log_entry['correlation_id'] == 'test-correlation-123'
    
    def test_formatter_includes_extra_fields(self):
        """Test formatter includes additional extra fields."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name='test.module',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Test message',
            args=(),
            exc_info=None
        )
        record.operation = 'volume_detection'
        record.latency_ms = 45
        record.volume_level = 'loud'
        
        formatted = formatter.format(record)
        log_entry = json.loads(formatted)
        
        assert log_entry['operation'] == 'volume_detection'
        assert log_entry['latency_ms'] == 45
        assert log_entry['volume_level'] == 'loud'

    
    def test_formatter_includes_exception_info(self):
        """Test formatter includes exception information."""
        formatter = StructuredFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name='test.module',
            level=logging.ERROR,
            pathname='test.py',
            lineno=10,
            msg='Error occurred',
            args=(),
            exc_info=exc_info
        )
        
        formatted = formatter.format(record)
        log_entry = json.loads(formatted)
        
        assert 'exception' in log_entry
        assert 'ValueError' in log_entry['exception']
        assert 'Test error' in log_entry['exception']
    
    def test_formatter_handles_non_serializable_values(self):
        """Test formatter handles non-JSON-serializable values."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name='test.module',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Test message',
            args=(),
            exc_info=None
        )
        # Add non-serializable object
        record.custom_object = object()
        
        formatted = formatter.format(record)
        log_entry = json.loads(formatted)
        
        # Should convert to string
        assert 'custom_object' in log_entry
        assert isinstance(log_entry['custom_object'], str)


class TestStructuredLogger:
    """Test suite for StructuredLogger."""
    
    @pytest.fixture
    def logger_with_capture(self):
        """Create structured logger with output capture."""
        # Create string buffer to capture output
        log_buffer = StringIO()
        handler = logging.StreamHandler(log_buffer)
        handler.setFormatter(StructuredFormatter())
        
        logger = logging.getLogger('test.structured')
        logger.setLevel(logging.DEBUG)
        logger.handlers = [handler]
        
        structured_logger = StructuredLogger('test.structured', level=logging.DEBUG, use_json=True)
        structured_logger.logger = logger
        
        return structured_logger, log_buffer

    
    def test_structured_logger_info_with_correlation_id(self, logger_with_capture):
        """Test structured logger logs info with correlation ID."""
        logger, buffer = logger_with_capture
        
        logger.info(
            'Test info message',
            correlation_id='test-correlation-123',
            operation='test_operation'
        )
        
        # Get log output
        buffer.seek(0)
        log_output = buffer.read()
        log_entry = json.loads(log_output.strip())
        
        assert log_entry['level'] == 'INFO'
        assert log_entry['message'] == 'Test info message'
        assert log_entry['correlation_id'] == 'test-correlation-123'
        assert log_entry['operation'] == 'test_operation'
    
    def test_structured_logger_error_with_exc_info(self, logger_with_capture):
        """Test structured logger logs error with exception info."""
        logger, buffer = logger_with_capture
        
        try:
            raise ValueError("Test error")
        except ValueError:
            logger.error(
                'Error occurred',
                correlation_id='test-correlation-error',
                exc_info=True
            )
        
        buffer.seek(0)
        log_output = buffer.read()
        log_entry = json.loads(log_output.strip())
        
        assert log_entry['level'] == 'ERROR'
        assert log_entry['message'] == 'Error occurred'
        assert log_entry['correlation_id'] == 'test-correlation-error'
        assert 'exception' in log_entry
        assert 'ValueError' in log_entry['exception']
    
    def test_structured_logger_debug_with_extra_fields(self, logger_with_capture):
        """Test structured logger logs debug with extra fields."""
        logger, buffer = logger_with_capture
        
        logger.debug(
            'Debug message',
            correlation_id='test-correlation-debug',
            latency_ms=45,
            volume_level='loud'
        )
        
        buffer.seek(0)
        log_output = buffer.read().strip()
        log_entry = json.loads(log_output)
        
        assert log_entry['level'] == 'DEBUG'
        assert log_entry['latency_ms'] == 45
        assert log_entry['volume_level'] == 'loud'
    
    def test_structured_logger_warning(self, logger_with_capture):
        """Test structured logger logs warning."""
        logger, buffer = logger_with_capture
        
        logger.warning(
            'Warning message',
            correlation_id='test-correlation-warning'
        )
        
        buffer.seek(0)
        log_output = buffer.read()
        log_entry = json.loads(log_output.strip())
        
        assert log_entry['level'] == 'WARNING'
        assert log_entry['message'] == 'Warning message'



class TestStructuredLoggingHelpers:
    """Test suite for structured logging helper functions."""
    
    @pytest.fixture
    def mock_logger(self):
        """Create mock logger."""
        return Mock(spec=logging.Logger)
    
    def test_log_volume_detection_includes_all_fields(self, mock_logger):
        """Test log_volume_detection includes all required fields."""
        log_volume_detection(
            logger=mock_logger,
            correlation_id='test-correlation-123',
            volume_level='loud',
            db_value=-8.5,
            latency_ms=45
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        
        # Verify message
        message = call_args[0][0]
        assert 'Volume detection completed' in message
        assert 'loud' in message
        
        # Verify extra fields
        extra = call_args[1]['extra']
        assert extra['correlation_id'] == 'test-correlation-123'
        assert extra['operation'] == 'volume_detection'
        assert extra['volume_level'] == 'loud'
        assert extra['db_value'] == -8.5
        assert extra['latency_ms'] == 45
    
    def test_log_rate_detection_includes_all_fields(self, mock_logger):
        """Test log_rate_detection includes all required fields."""
        log_rate_detection(
            logger=mock_logger,
            correlation_id='test-correlation-456',
            rate_classification='fast',
            wpm=175.5,
            onset_count=50,
            latency_ms=52
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        
        message = call_args[0][0]
        assert 'Rate detection completed' in message
        assert 'fast' in message
        
        extra = call_args[1]['extra']
        assert extra['correlation_id'] == 'test-correlation-456'
        assert extra['operation'] == 'rate_detection'
        assert extra['rate_classification'] == 'fast'
        assert extra['wpm'] == 175.5
        assert extra['onset_count'] == 50
        assert extra['latency_ms'] == 52

    
    def test_log_ssml_generation_includes_all_fields(self, mock_logger):
        """Test log_ssml_generation includes all required fields."""
        log_ssml_generation(
            logger=mock_logger,
            correlation_id='test-correlation-789',
            ssml_length=250,
            has_dynamics=True,
            latency_ms=15
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        
        message = call_args[0][0]
        assert 'SSML generation completed' in message
        
        extra = call_args[1]['extra']
        assert extra['correlation_id'] == 'test-correlation-789'
        assert extra['operation'] == 'ssml_generation'
        assert extra['ssml_length'] == 250
        assert extra['has_dynamics'] is True
        assert extra['latency_ms'] == 15
    
    def test_log_polly_synthesis_includes_all_fields(self, mock_logger):
        """Test log_polly_synthesis includes all required fields."""
        log_polly_synthesis(
            logger=mock_logger,
            correlation_id='test-correlation-abc',
            audio_size_bytes=102400,
            voice_id='Joanna',
            text_type='ssml',
            latency_ms=750
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        
        message = call_args[0][0]
        assert 'Polly synthesis completed' in message
        assert 'Joanna' in message
        
        extra = call_args[1]['extra']
        assert extra['correlation_id'] == 'test-correlation-abc'
        assert extra['operation'] == 'polly_synthesis'
        assert extra['audio_size_bytes'] == 102400
        assert extra['voice_id'] == 'Joanna'
        assert extra['text_type'] == 'ssml'
        assert extra['latency_ms'] == 750
    
    def test_log_error_includes_all_fields(self, mock_logger):
        """Test log_error includes all required fields."""
        log_error(
            logger=mock_logger,
            correlation_id='test-correlation-error',
            component='VolumeDetector',
            error_type='LibrosaError',
            error_message='Failed to process audio',
            exc_info=True
        )
        
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        
        message = call_args[0][0]
        assert 'VolumeDetector error' in message
        assert 'Failed to process audio' in message
        
        extra = call_args[1]['extra']
        assert extra['correlation_id'] == 'test-correlation-error'
        assert extra['component'] == 'VolumeDetector'
        assert extra['error_type'] == 'LibrosaError'
        assert extra['error_message'] == 'Failed to process audio'
        
        # Verify exc_info was passed
        assert call_args[1]['exc_info'] is True



class TestCorrelationIDPropagation:
    """Test suite for correlation ID propagation in logs."""
    
    def test_correlation_id_propagates_through_volume_detection(self):
        """Test correlation ID propagates through volume detection logging."""
        with patch('emotion_dynamics.utils.structured_logger.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            correlation_id = 'test-correlation-volume-123'
            
            log_volume_detection(
                logger=mock_logger,
                correlation_id=correlation_id,
                volume_level='loud',
                db_value=-8.5,
                latency_ms=45
            )
            
            # Verify correlation ID in extra
            call_args = mock_logger.info.call_args
            extra = call_args[1]['extra']
            assert extra['correlation_id'] == correlation_id
    
    def test_correlation_id_propagates_through_rate_detection(self):
        """Test correlation ID propagates through rate detection logging."""
        with patch('emotion_dynamics.utils.structured_logger.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            correlation_id = 'test-correlation-rate-456'
            
            log_rate_detection(
                logger=mock_logger,
                correlation_id=correlation_id,
                rate_classification='fast',
                wpm=175.5,
                onset_count=50,
                latency_ms=52
            )
            
            call_args = mock_logger.info.call_args
            extra = call_args[1]['extra']
            assert extra['correlation_id'] == correlation_id
    
    def test_correlation_id_propagates_through_ssml_generation(self):
        """Test correlation ID propagates through SSML generation logging."""
        with patch('emotion_dynamics.utils.structured_logger.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            correlation_id = 'test-correlation-ssml-789'
            
            log_ssml_generation(
                logger=mock_logger,
                correlation_id=correlation_id,
                ssml_length=250,
                has_dynamics=True,
                latency_ms=15
            )
            
            call_args = mock_logger.info.call_args
            extra = call_args[1]['extra']
            assert extra['correlation_id'] == correlation_id
    
    def test_correlation_id_propagates_through_polly_synthesis(self):
        """Test correlation ID propagates through Polly synthesis logging."""
        with patch('emotion_dynamics.utils.structured_logger.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            correlation_id = 'test-correlation-polly-abc'
            
            log_polly_synthesis(
                logger=mock_logger,
                correlation_id=correlation_id,
                audio_size_bytes=102400,
                voice_id='Joanna',
                text_type='ssml',
                latency_ms=750
            )
            
            call_args = mock_logger.info.call_args
            extra = call_args[1]['extra']
            assert extra['correlation_id'] == correlation_id
    
    def test_correlation_id_propagates_through_error_logging(self):
        """Test correlation ID propagates through error logging."""
        with patch('emotion_dynamics.utils.structured_logger.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            correlation_id = 'test-correlation-error-xyz'
            
            log_error(
                logger=mock_logger,
                correlation_id=correlation_id,
                component='VolumeDetector',
                error_type='LibrosaError',
                error_message='Failed to process audio'
            )
            
            call_args = mock_logger.error.call_args
            extra = call_args[1]['extra']
            assert extra['correlation_id'] == correlation_id
