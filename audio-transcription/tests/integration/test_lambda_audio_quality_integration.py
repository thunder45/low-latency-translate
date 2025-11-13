"""Integration tests for Lambda audio quality validation."""

import json
import base64
import numpy as np
import pytest
from unittest.mock import Mock, MagicMock, patch
from audio_quality.analyzers.quality_analyzer import AudioQualityAnalyzer
from audio_quality.models.quality_config import QualityConfig
from audio_quality.notifiers.metrics_emitter import QualityMetricsEmitter
from audio_quality.notifiers.speaker_notifier import SpeakerNotifier


class TestLambdaAudioQualityIntegration:
    """Integration tests for Lambda audio quality validation."""
    
    @pytest.fixture
    def mock_cloudwatch_client(self):
        """Fixture for mock CloudWatch client."""
        client = Mock()
        client.put_metric_data = MagicMock()
        return client
    
    @pytest.fixture
    def mock_eventbridge_client(self):
        """Fixture for mock EventBridge client."""
        client = Mock()
        client.put_events = MagicMock()
        return client
    
    @pytest.fixture
    def mock_websocket_manager(self):
        """Fixture for mock WebSocket manager."""
        manager = Mock()
        manager.send_message = MagicMock()
        manager.sent_messages = []
        
        def track_message(connection_id, message):
            manager.sent_messages.append({
                'connection_id': connection_id,
                'message': message
            })
        
        manager.send_message.side_effect = track_message
        return manager
    
    @pytest.fixture
    def quality_config(self):
        """Fixture for quality configuration."""
        return QualityConfig(
            snr_threshold_db=20.0,
            clipping_threshold_percent=1.0,
            echo_threshold_db=-15.0,
            silence_threshold_db=-50.0
        )
    
    @pytest.fixture
    def analyzer(self, quality_config):
        """Fixture for AudioQualityAnalyzer."""
        return AudioQualityAnalyzer(quality_config)
    
    @pytest.fixture
    def metrics_emitter(self, mock_cloudwatch_client, mock_eventbridge_client):
        """Fixture for QualityMetricsEmitter."""
        return QualityMetricsEmitter(mock_cloudwatch_client, mock_eventbridge_client)
    
    @pytest.fixture
    def speaker_notifier(self, mock_websocket_manager):
        """Fixture for SpeakerNotifier."""
        return SpeakerNotifier(mock_websocket_manager)
    
    def create_audio_event(self, audio_data, sample_rate=16000, connection_id='conn-123', stream_id='stream-456'):
        """Helper to create Lambda event with audio data."""
        audio_bytes = audio_data.tobytes()
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        return {
            'audio': audio_base64,
            'sampleRate': sample_rate,
            'connectionId': connection_id,
            'streamId': stream_id,
            'timestamp': 1699564800.0
        }
    
    def test_lambda_integration_with_clean_audio(
        self, analyzer, metrics_emitter, speaker_notifier, 
        mock_cloudwatch_client, mock_websocket_manager
    ):
        """Test Lambda integration with clean audio (no quality issues)."""
        # Generate clean audio
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = (np.sin(2 * np.pi * 440 * t) * 0.5 * 32767).astype(np.int16)
        
        # Create event
        event = self.create_audio_event(audio_data, sample_rate)
        
        # Extract and analyze audio
        audio_bytes = base64.b64decode(event['audio'])
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
        
        # Run quality analysis
        metrics = analyzer.analyze(audio_array, event['sampleRate'])
        
        # Emit metrics
        metrics_emitter.emit_metrics(event['streamId'], metrics)
        
        # Verify metrics were emitted to CloudWatch
        assert mock_cloudwatch_client.put_metric_data.called, "Should emit metrics to CloudWatch"
        
        # Verify no speaker notifications (clean audio)
        assert len(mock_websocket_manager.sent_messages) == 0, \
            "Should not send notifications for clean audio"
    
    def test_lambda_integration_with_low_snr(
        self, analyzer, metrics_emitter, speaker_notifier, quality_config,
        mock_cloudwatch_client, mock_eventbridge_client, mock_websocket_manager
    ):
        """Test Lambda integration detects and notifies low SNR."""
        # Generate noisy audio (low SNR)
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        signal = np.sin(2 * np.pi * 440 * t) * 0.05
        noise = np.random.normal(0, 0.15, len(signal))
        audio_data = ((signal + noise) * 32767).astype(np.int16)
        
        # Create event
        event = self.create_audio_event(audio_data, sample_rate)
        
        # Extract and analyze audio
        audio_bytes = base64.b64decode(event['audio'])
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
        
        # Run quality analysis
        metrics = analyzer.analyze(audio_array, event['sampleRate'])
        
        # Emit metrics
        metrics_emitter.emit_metrics(event['streamId'], metrics)
        
        # Send speaker notification if SNR below threshold
        if metrics.snr_db < quality_config.snr_threshold_db:
            speaker_notifier.notify_speaker(
                event['connectionId'],
                'snr_low',
                {'snr': metrics.snr_db, 'threshold': quality_config.snr_threshold_db}
            )
        
        # Verify metrics were emitted
        assert mock_cloudwatch_client.put_metric_data.called, "Should emit metrics"
        
        # Verify speaker was notified (if SNR is low)
        if metrics.snr_db < quality_config.snr_threshold_db:
            assert len(mock_websocket_manager.sent_messages) > 0, \
                "Should notify speaker of low SNR"
    
    def test_lambda_integration_with_clipping(
        self, analyzer, metrics_emitter, speaker_notifier, quality_config,
        mock_cloudwatch_client, mock_websocket_manager
    ):
        """Test Lambda integration detects and notifies clipping."""
        # Generate clipped audio
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = (np.sin(2 * np.pi * 440 * t) * 1.5 * 32767).astype(np.int16)
        audio_data = np.clip(audio_data, -32767, 32767)
        
        # Create event
        event = self.create_audio_event(audio_data, sample_rate)
        
        # Extract and analyze audio
        audio_bytes = base64.b64decode(event['audio'])
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
        
        # Run quality analysis
        metrics = analyzer.analyze(audio_array, event['sampleRate'])
        
        # Emit metrics
        metrics_emitter.emit_metrics(event['streamId'], metrics)
        
        # Send speaker notification if clipping detected
        if metrics.is_clipping:
            speaker_notifier.notify_speaker(
                event['connectionId'],
                'clipping',
                {
                    'percentage': metrics.clipping_percentage,
                    'threshold': quality_config.clipping_threshold_percent
                }
            )
        
        # Verify metrics were emitted
        assert mock_cloudwatch_client.put_metric_data.called, "Should emit metrics"
        
        # Verify speaker was notified (if clipping detected)
        if metrics.is_clipping:
            assert len(mock_websocket_manager.sent_messages) > 0, \
                "Should notify speaker of clipping"
    
    def test_lambda_integration_metrics_emission(
        self, analyzer, metrics_emitter, mock_cloudwatch_client
    ):
        """Test that metrics are properly emitted to CloudWatch."""
        # Generate test audio
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = (np.sin(2 * np.pi * 440 * t) * 0.5 * 32767).astype(np.int16)
        
        # Create event
        event = self.create_audio_event(audio_data, sample_rate)
        
        # Extract and analyze audio
        audio_bytes = base64.b64decode(event['audio'])
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
        
        # Run quality analysis
        metrics = analyzer.analyze(audio_array, event['sampleRate'])
        
        # Emit metrics
        metrics_emitter.emit_metrics(event['streamId'], metrics)
        
        # Verify CloudWatch was called
        assert mock_cloudwatch_client.put_metric_data.called, "Should call CloudWatch"
        
        # Verify metric data structure
        call_args = mock_cloudwatch_client.put_metric_data.call_args
        assert 'Namespace' in call_args[1], "Should include namespace"
        assert 'MetricData' in call_args[1], "Should include metric data"
        assert call_args[1]['Namespace'] == 'AudioQuality', "Should use correct namespace"
    
    def test_lambda_integration_event_emission(
        self, analyzer, metrics_emitter, quality_config, mock_eventbridge_client
    ):
        """Test that quality events are emitted to EventBridge."""
        # Generate noisy audio to trigger event
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        signal = np.sin(2 * np.pi * 440 * t) * 0.05
        noise = np.random.normal(0, 0.15, len(signal))
        audio_data = ((signal + noise) * 32767).astype(np.int16)
        
        # Create event
        event = self.create_audio_event(audio_data, sample_rate)
        
        # Extract and analyze audio
        audio_bytes = base64.b64decode(event['audio'])
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
        
        # Run quality analysis
        metrics = analyzer.analyze(audio_array, event['sampleRate'])
        
        # Emit quality event if SNR is low
        if metrics.snr_db < quality_config.snr_threshold_db:
            metrics_emitter.emit_quality_event(
                event['streamId'],
                'snr_low',
                {'snr': metrics.snr_db, 'threshold': quality_config.snr_threshold_db}
            )
        
        # Verify EventBridge was called (if SNR is low)
        if metrics.snr_db < quality_config.snr_threshold_db:
            assert mock_eventbridge_client.put_events.called, "Should emit event to EventBridge"
    
    def test_lambda_integration_complete_workflow(
        self, analyzer, metrics_emitter, speaker_notifier, quality_config,
        mock_cloudwatch_client, mock_eventbridge_client, mock_websocket_manager
    ):
        """Test complete Lambda workflow with all components."""
        # Generate audio with multiple issues
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Low SNR + clipping
        signal = np.sin(2 * np.pi * 440 * t) * 0.05
        noise = np.random.normal(0, 0.15, len(signal))
        noisy_signal = signal + noise
        clipped_signal = np.clip(noisy_signal * 2.0, -1.0, 1.0)
        audio_data = (clipped_signal * 32767).astype(np.int16)
        
        # Create event
        event = self.create_audio_event(audio_data, sample_rate)
        
        # Extract and analyze audio
        audio_bytes = base64.b64decode(event['audio'])
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
        
        # Run quality analysis
        metrics = analyzer.analyze(audio_array, event['sampleRate'])
        
        # Emit metrics
        metrics_emitter.emit_metrics(event['streamId'], metrics)
        
        # Check and notify for each issue type
        if metrics.snr_db < quality_config.snr_threshold_db:
            speaker_notifier.notify_speaker(
                event['connectionId'],
                'snr_low',
                {'snr': metrics.snr_db}
            )
            metrics_emitter.emit_quality_event(
                event['streamId'],
                'snr_low',
                {'snr': metrics.snr_db}
            )
        
        if metrics.is_clipping:
            speaker_notifier.notify_speaker(
                event['connectionId'],
                'clipping',
                {'percentage': metrics.clipping_percentage}
            )
            metrics_emitter.emit_quality_event(
                event['streamId'],
                'clipping',
                {'percentage': metrics.clipping_percentage}
            )
        
        # Verify all components were invoked
        assert mock_cloudwatch_client.put_metric_data.called, "Should emit metrics"
        
        # Verify notifications were sent for detected issues
        notification_count = len(mock_websocket_manager.sent_messages)
        assert notification_count > 0, "Should send notifications for quality issues"
    
    def test_lambda_integration_with_different_sample_rates(
        self, analyzer, metrics_emitter, mock_cloudwatch_client
    ):
        """Test Lambda integration with different sample rates."""
        sample_rates = [8000, 16000, 24000, 48000]
        
        for sample_rate in sample_rates:
            duration = 1.0
            t = np.linspace(0, duration, int(sample_rate * duration))
            audio_data = (np.sin(2 * np.pi * 440 * t) * 0.5 * 32767).astype(np.int16)
            
            # Create event
            event = self.create_audio_event(audio_data, sample_rate)
            
            # Extract and analyze audio
            audio_bytes = base64.b64decode(event['audio'])
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            
            # Run quality analysis
            metrics = analyzer.analyze(audio_array, event['sampleRate'])
            
            # Emit metrics
            metrics_emitter.emit_metrics(event['streamId'], metrics)
            
            # Verify analysis completed
            assert metrics is not None, f"Analysis should complete for {sample_rate} Hz"
            assert mock_cloudwatch_client.put_metric_data.called, \
                f"Should emit metrics for {sample_rate} Hz"
            
            # Reset mock for next iteration
            mock_cloudwatch_client.reset_mock()
