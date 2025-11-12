"""
Unit tests for QualityMetricsEmitter.

Tests metric batching, CloudWatch publishing, and EventBridge event emission.
"""

import time
from unittest.mock import Mock, call
import pytest

from audio_quality.notifiers.metrics_emitter import QualityMetricsEmitter
from audio_quality.models.quality_metrics import QualityMetrics


class TestQualityMetricsEmitter:
    """Test suite for QualityMetricsEmitter."""
    
    @pytest.fixture
    def mock_cloudwatch(self):
        """Creates mock CloudWatch client."""
        return Mock()
    
    @pytest.fixture
    def mock_eventbridge(self):
        """Creates mock EventBridge client."""
        return Mock()
    
    @pytest.fixture
    def emitter(self, mock_cloudwatch, mock_eventbridge):
        """Creates QualityMetricsEmitter instance."""
        return QualityMetricsEmitter(
            cloudwatch_client=mock_cloudwatch,
            eventbridge_client=mock_eventbridge,
            batch_size=20,
            flush_interval_s=5.0
        )
    
    @pytest.fixture
    def sample_metrics(self):
        """Creates sample quality metrics."""
        return QualityMetrics(
            timestamp=time.time(),
            stream_id='test-stream-123',
            snr_db=25.5,
            snr_rolling_avg=24.8,
            clipping_percentage=0.5,
            clipped_sample_count=80,
            is_clipping=False,
            echo_level_db=-25.0,
            echo_delay_ms=120.0,
            has_echo=False,
            is_silent=False,
            silence_duration_s=0.0,
            energy_db=-20.0
        )
    
    def test_emit_metrics_adds_to_buffer(self, emitter, sample_metrics):
        """Tests that emit_metrics adds metrics to buffer."""
        emitter.emit_metrics('test-stream-123', sample_metrics)
        
        # Should have 4 metrics in buffer (SNR, Clipping, Echo, Silence)
        assert len(emitter.metric_buffer) == 4
    
    def test_emit_metrics_includes_all_metric_types(
        self,
        emitter,
        sample_metrics
    ):
        """Tests that all metric types are included."""
        emitter.emit_metrics('test-stream-123', sample_metrics)
        
        metric_names = [m['MetricName'] for m in emitter.metric_buffer]
        
        assert 'SNR' in metric_names
        assert 'ClippingPercentage' in metric_names
        assert 'EchoLevel' in metric_names
        assert 'SilenceDuration' in metric_names
    
    def test_emit_metrics_includes_stream_dimension(
        self,
        emitter,
        sample_metrics
    ):
        """Tests that metrics include stream ID dimension."""
        emitter.emit_metrics('test-stream-123', sample_metrics)
        
        for metric in emitter.metric_buffer:
            dimensions = metric['Dimensions']
            assert len(dimensions) == 1
            assert dimensions[0]['Name'] == 'StreamId'
            assert dimensions[0]['Value'] == 'test-stream-123'
    
    def test_emit_metrics_includes_correct_units(
        self,
        emitter,
        sample_metrics
    ):
        """Tests that metrics have correct units."""
        emitter.emit_metrics('test-stream-123', sample_metrics)
        
        metric_units = {m['MetricName']: m['Unit'] for m in emitter.metric_buffer}
        
        assert metric_units['SNR'] == 'None'
        assert metric_units['ClippingPercentage'] == 'Percent'
        assert metric_units['EchoLevel'] == 'None'
        assert metric_units['SilenceDuration'] == 'Seconds'
    
    def test_flush_publishes_to_cloudwatch(
        self,
        emitter,
        mock_cloudwatch,
        sample_metrics
    ):
        """Tests that flush publishes metrics to CloudWatch."""
        emitter.emit_metrics('test-stream-123', sample_metrics)
        emitter.flush()
        
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args
        
        assert call_args[1]['Namespace'] == 'AudioQuality'
        assert len(call_args[1]['MetricData']) == 4
    
    def test_flush_clears_buffer(self, emitter, sample_metrics):
        """Tests that flush clears the metric buffer."""
        emitter.emit_metrics('test-stream-123', sample_metrics)
        assert len(emitter.metric_buffer) == 4
        
        emitter.flush()
        
        assert len(emitter.metric_buffer) == 0
    
    def test_flush_updates_last_flush_time(self, emitter, sample_metrics):
        """Tests that flush updates the last flush time."""
        initial_time = emitter.last_flush_time
        time.sleep(0.1)
        
        emitter.emit_metrics('test-stream-123', sample_metrics)
        emitter.flush()
        
        assert emitter.last_flush_time > initial_time
    
    def test_auto_flush_on_batch_size(
        self,
        emitter,
        mock_cloudwatch,
        sample_metrics
    ):
        """Tests that metrics auto-flush when batch size is reached."""
        # Set small batch size
        emitter.batch_size = 4
        
        # Emit metrics (adds 4 metrics)
        emitter.emit_metrics('test-stream-123', sample_metrics)
        
        # Should auto-flush
        mock_cloudwatch.put_metric_data.assert_called_once()
    
    def test_auto_flush_on_time_interval(
        self,
        emitter,
        mock_cloudwatch,
        sample_metrics
    ):
        """Tests that metrics auto-flush after time interval."""
        # Set short flush interval
        emitter.flush_interval_s = 0.1
        
        # Emit metrics
        emitter.emit_metrics('test-stream-123', sample_metrics)
        
        # Wait for interval
        time.sleep(0.15)
        
        # Emit more metrics (should trigger flush)
        emitter.emit_metrics('test-stream-456', sample_metrics)
        
        # Should have flushed
        assert mock_cloudwatch.put_metric_data.call_count >= 1
    
    def test_flush_handles_cloudwatch_errors(
        self,
        emitter,
        mock_cloudwatch,
        sample_metrics
    ):
        """Tests that flush handles CloudWatch errors gracefully."""
        mock_cloudwatch.put_metric_data.side_effect = Exception('API Error')
        
        emitter.emit_metrics('test-stream-123', sample_metrics)
        
        # Should not raise exception
        emitter.flush()
        
        # Buffer should be cleared to prevent unbounded growth
        assert len(emitter.metric_buffer) == 0
    
    def test_emit_quality_event_publishes_to_eventbridge(
        self,
        emitter,
        mock_eventbridge
    ):
        """Tests that emit_quality_event publishes to EventBridge."""
        emitter.emit_quality_event(
            stream_id='test-stream-123',
            event_type='snr_low',
            details={
                'severity': 'warning',
                'metrics': {'snr': 15.2, 'threshold': 20.0},
                'message': 'SNR below threshold'
            }
        )
        
        mock_eventbridge.put_events.assert_called_once()
        call_args = mock_eventbridge.put_events.call_args
        
        entries = call_args[1]['Entries']
        assert len(entries) == 1
        assert entries[0]['Source'] == 'audio.quality.validator'
        assert entries[0]['DetailType'] == 'audio.quality.snr_low'
    
    def test_emit_quality_event_includes_details(
        self,
        emitter,
        mock_eventbridge
    ):
        """Tests that quality event includes all details."""
        emitter.emit_quality_event(
            stream_id='test-stream-123',
            event_type='clipping',
            details={
                'severity': 'error',
                'metrics': {'percentage': 5.2},
                'message': 'High clipping detected'
            }
        )
        
        call_args = mock_eventbridge.put_events.call_args
        entry = call_args[1]['Entries'][0]
        
        import json
        detail = json.loads(entry['Detail'])
        
        assert detail['streamId'] == 'test-stream-123'
        assert detail['severity'] == 'error'
        assert detail['metrics']['percentage'] == 5.2
        assert detail['message'] == 'High clipping detected'
    
    def test_emit_quality_event_handles_eventbridge_errors(
        self,
        emitter,
        mock_eventbridge
    ):
        """Tests that emit_quality_event handles EventBridge errors."""
        mock_eventbridge.put_events.side_effect = Exception('API Error')
        
        # Should not raise exception
        emitter.emit_quality_event(
            stream_id='test-stream-123',
            event_type='echo',
            details={'severity': 'warning', 'metrics': {}, 'message': 'Echo'}
        )
    
    def test_emit_quality_event_validates_event_type(
        self,
        emitter,
        mock_eventbridge
    ):
        """Tests that invalid event types are rejected."""
        # Should handle validation error gracefully
        emitter.emit_quality_event(
            stream_id='test-stream-123',
            event_type='invalid_type',
            details={'severity': 'warning', 'metrics': {}, 'message': 'Test'}
        )
        
        # Should not call EventBridge with invalid event
        mock_eventbridge.put_events.assert_not_called()
    
    def test_batching_reduces_api_calls(
        self,
        emitter,
        mock_cloudwatch,
        sample_metrics
    ):
        """Tests that batching reduces CloudWatch API calls."""
        # Emit 5 sets of metrics (20 total metrics)
        for i in range(5):
            emitter.emit_metrics(f'stream-{i}', sample_metrics)
        
        # Should only call API once (batched)
        assert mock_cloudwatch.put_metric_data.call_count <= 1
    
    def test_destructor_flushes_remaining_metrics(
        self,
        mock_cloudwatch,
        mock_eventbridge,
        sample_metrics
    ):
        """Tests that destructor flushes remaining metrics."""
        emitter = QualityMetricsEmitter(
            cloudwatch_client=mock_cloudwatch,
            eventbridge_client=mock_eventbridge,
            batch_size=100,  # Large batch to prevent auto-flush
            flush_interval_s=1000.0
        )
        
        emitter.emit_metrics('test-stream-123', sample_metrics)
        
        # Delete emitter (triggers __del__)
        del emitter
        
        # Should have flushed metrics
        assert mock_cloudwatch.put_metric_data.call_count >= 1
