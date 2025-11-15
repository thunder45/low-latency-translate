"""
Unit tests for MetricsEmitter.

Tests metric emission, CloudWatch publishing, and batching.
"""

import time
from unittest.mock import Mock, patch, call
import pytest

from shared.utils.metrics_emitter import MetricsEmitter


class TestMetricsEmitter:
    """Test suite for MetricsEmitter."""
    
    @pytest.fixture
    def mock_cloudwatch(self):
        """Creates mock CloudWatch client."""
        return Mock()
    
    @pytest.fixture
    def emitter(self, mock_cloudwatch):
        """Creates MetricsEmitter instance."""
        with patch('shared.utils.metrics_emitter.boto3.client', return_value=mock_cloudwatch):
            emitter = MetricsEmitter(namespace='AudioTranscription/WebSocket')
            emitter.cloudwatch = mock_cloudwatch
            return emitter
    
    def test_emit_audio_chunk_received(self, emitter, mock_cloudwatch):
        """Test emitting audio chunk received metric."""
        emitter.emit_audio_chunk_received('test-session-123', 3200)
        
        # Should add 2 metrics to buffer (count + size)
        assert len(emitter._metric_buffer) == 2
        
        # Check count metric
        count_metric = emitter._metric_buffer[0]
        assert count_metric['MetricName'] == 'AudioChunksReceived'
        assert count_metric['Value'] == 1
        assert count_metric['Unit'] == 'Count'
        
        # Check size metric
        size_metric = emitter._metric_buffer[1]
        assert size_metric['MetricName'] == 'AudioChunkSize'
        assert size_metric['Value'] == 3200
        assert size_metric['Unit'] == 'Bytes'
    
    def test_emit_audio_processing_latency(self, emitter, mock_cloudwatch):
        """Test emitting audio processing latency metric."""
        emitter.emit_audio_processing_latency('test-session-123', 25.5)
        
        assert len(emitter._metric_buffer) == 1
        metric = emitter._metric_buffer[0]
        assert metric['MetricName'] == 'AudioProcessingLatency'
        assert metric['Value'] == 25.5
        assert metric['Unit'] == 'Milliseconds'
    
    def test_emit_audio_chunk_dropped(self, emitter, mock_cloudwatch):
        """Test emitting audio chunk dropped metric."""
        emitter.emit_audio_chunk_dropped('test-session-123', 'rate_limit')
        
        assert len(emitter._metric_buffer) == 1
        metric = emitter._metric_buffer[0]
        assert metric['MetricName'] == 'AudioChunksDropped'
        assert metric['Value'] == 1
        assert metric['Unit'] == 'Count'
    
    def test_emit_rate_limit_violation(self, emitter, mock_cloudwatch):
        """Test emitting rate limit violation metric."""
        emitter.emit_rate_limit_violation('test-session-123', 'test-conn-123', 'audio')
        
        assert len(emitter._metric_buffer) == 1
        metric = emitter._metric_buffer[0]
        assert metric['MetricName'] == 'RateLimitViolations'
        assert metric['Value'] == 1
        assert metric['Unit'] == 'Count'
    
    def test_emit_transcribe_stream_error(self, emitter, mock_cloudwatch):
        """Test emitting Transcribe stream error metric."""
        emitter.emit_transcribe_stream_error('test-session-123', 'ThrottlingException')
        
        assert len(emitter._metric_buffer) == 1
        metric = emitter._metric_buffer[0]
        assert metric['MetricName'] == 'TranscribeStreamErrors'
        assert metric['Value'] == 1
        assert metric['Unit'] == 'Count'
    
    def test_metrics_include_dimensions(self, emitter, mock_cloudwatch):
        """Test that metrics include proper dimensions."""
        emitter.emit_audio_chunk_received('test-session-123', 3200)
        
        # Check both metrics have dimensions
        for metric in emitter._metric_buffer:
            assert 'Dimensions' in metric
            dimensions = {d['Name']: d['Value'] for d in metric['Dimensions']}
            assert 'SessionId' in dimensions
            assert dimensions['SessionId'] == 'test-session-123'
    
    def test_auto_flush_on_buffer_size(self, emitter, mock_cloudwatch):
        """Test that metrics auto-flush when buffer is full."""
        # Fill buffer to capacity (each call adds 2 metrics, so 10 calls = 20 metrics)
        for i in range(10):
            emitter.emit_audio_chunk_received(f'session-{i}', 3200)
        
        # Should auto-flush once
        assert mock_cloudwatch.put_metric_data.call_count == 1
        
        # Buffer should be cleared
        assert len(emitter._metric_buffer) == 0
    
    def test_flush_publishes_to_cloudwatch(self, emitter, mock_cloudwatch):
        """Test that flush publishes metrics to CloudWatch."""
        emitter.emit_audio_chunk_received('test-session-123', 3200)  # Adds 2 metrics
        emitter.emit_audio_processing_latency('test-session-123', 25.5)  # Adds 1 metric
        
        emitter.flush()
        
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args
        
        assert call_args[1]['Namespace'] == 'AudioTranscription/WebSocket'
        assert len(call_args[1]['MetricData']) == 3  # 2 + 1 = 3 metrics
    
    def test_flush_clears_buffer(self, emitter, mock_cloudwatch):
        """Test that flush clears the metric buffer."""
        emitter.emit_audio_chunk_received('test-session-123', 3200)
        assert len(emitter._metric_buffer) == 2  # Adds 2 metrics
        
        emitter.flush()
        
        assert len(emitter._metric_buffer) == 0
    
    def test_flush_handles_cloudwatch_errors(self, emitter, mock_cloudwatch):
        """Test that flush handles CloudWatch errors gracefully."""
        from botocore.exceptions import ClientError
        mock_cloudwatch.put_metric_data.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'PutMetricData'
        )
        
        emitter.emit_audio_chunk_received('test-session-123', 3200)
        
        # Should not raise exception
        emitter.flush()
        
        # Buffer should NOT be cleared on error (metrics retained for retry)
        # This is the actual behavior - buffer is only cleared on success
        assert len(emitter._metric_buffer) == 2
    
    def test_multiple_metrics_batched(self, emitter, mock_cloudwatch):
        """Test that multiple metrics are batched together."""
        emitter.emit_audio_chunk_received('test-session-123', 3200)  # 2 metrics
        emitter.emit_audio_processing_latency('test-session-123', 25.5)  # 1 metric
        emitter.emit_audio_chunk_dropped('test-session-123', 'rate_limit')  # 1 metric
        
        assert len(emitter._metric_buffer) == 4  # 2 + 1 + 1 = 4
        
        emitter.flush()
        
        call_args = mock_cloudwatch.put_metric_data.call_args
        assert len(call_args[1]['MetricData']) == 4
    


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
