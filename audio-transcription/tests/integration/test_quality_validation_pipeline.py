"""Integration tests for complete quality validation pipeline."""

import numpy as np
import pytest
from audio_quality.analyzers.quality_analyzer import AudioQualityAnalyzer
from audio_quality.models.quality_config import QualityConfig


class TestQualityValidationPipeline:
    """Integration test suite for complete quality validation pipeline."""
    
    @pytest.fixture
    def config(self):
        """Fixture for quality configuration."""
        return QualityConfig(
            snr_threshold_db=20.0,
            clipping_threshold_percent=1.0,
            echo_threshold_db=-15.0,
            silence_threshold_db=-50.0,
            silence_duration_threshold_s=5.0
        )
    
    @pytest.fixture
    def analyzer(self, config):
        """Fixture for AudioQualityAnalyzer instance."""
        return AudioQualityAnalyzer(config)
    
    def test_quality_validation_pipeline_with_clean_audio(self, analyzer):
        """Test complete pipeline with clean, high-quality audio."""
        # Generate clean audio
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = np.sin(2 * np.pi * 440 * t) * 0.5
        
        # Run complete analysis
        metrics = analyzer.analyze(audio_data, sample_rate)
        
        # Verify all metrics are calculated
        assert metrics.snr_db > 0, "SNR should be calculated"
        assert 0 <= metrics.clipping_percentage <= 100, "Clipping percentage should be in valid range"
        assert metrics.echo_level_db < 0, "Echo level should be calculated"
        assert isinstance(metrics.is_silent, bool), "Silence detection should return boolean"
        
        # Verify high quality audio passes thresholds
        assert metrics.snr_db >= 20.0, f"Clean audio should have high SNR, got {metrics.snr_db:.2f} dB"
        assert not metrics.is_clipping, "Clean audio should not be clipping"
        assert not metrics.has_echo, "Clean audio should not have echo"
        assert not metrics.is_silent, "Active audio should not be silent"
    
    def test_quality_validation_pipeline_with_low_snr(self, analyzer):
        """Test pipeline detects low SNR audio."""
        # Generate noisy audio (low SNR)
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        signal = np.sin(2 * np.pi * 440 * t) * 0.05
        noise = np.random.normal(0, 0.15, len(signal))
        audio_data = signal + noise
        
        # Run analysis
        metrics = analyzer.analyze(audio_data, sample_rate)
        
        # Verify low SNR is detected
        assert metrics.snr_db < 20.0, f"Should detect low SNR, got {metrics.snr_db:.2f} dB"
    
    def test_quality_validation_pipeline_with_clipping(self, analyzer):
        """Test pipeline detects clipping."""
        # Generate clipped audio
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = np.sin(2 * np.pi * 440 * t) * 1.5  # Exceeds [-1, 1] range
        audio_data = np.clip(audio_data, -1.0, 1.0)  # Clip to valid range
        audio_data = (audio_data * 32767).astype(np.int16)  # Convert to int16
        
        # Run analysis
        metrics = analyzer.analyze(audio_data, sample_rate)
        
        # Verify clipping is detected
        assert metrics.clipping_percentage > 0, "Should detect clipping"
    
    def test_quality_validation_pipeline_with_echo(self, analyzer):
        """Test pipeline detects echo."""
        # Generate audio with echo
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        signal = np.sin(2 * np.pi * 440 * t)
        
        # Add echo at 100ms delay
        delay_samples = int(0.1 * sample_rate)
        echo = np.zeros_like(signal)
        echo[delay_samples:] = signal[:-delay_samples] * 0.4
        audio_data = signal + echo
        
        # Run analysis
        metrics = analyzer.analyze(audio_data, sample_rate)
        
        # Verify echo is detected
        assert metrics.has_echo, "Should detect echo"
        assert metrics.echo_level_db > -15.0, f"Echo level should be above threshold, got {metrics.echo_level_db:.2f} dB"
    
    def test_quality_validation_pipeline_with_silence(self, analyzer):
        """Test pipeline detects extended silence."""
        # Generate silence
        sample_rate = 16000
        duration = 6.0  # 6 seconds of silence
        audio_data = np.random.randn(int(sample_rate * duration)) * 0.0001
        
        # Run analysis
        metrics = analyzer.analyze(audio_data, sample_rate)
        
        # Verify silence is detected
        assert metrics.is_silent, "Should detect extended silence"
        assert metrics.duration_s > 5.0, f"Silence duration should exceed threshold, got {metrics.duration_s:.2f}s"
    
    def test_quality_validation_pipeline_with_multiple_issues(self, analyzer):
        """Test pipeline detects multiple quality issues simultaneously."""
        # Generate audio with multiple issues: low SNR + clipping
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Low SNR signal
        signal = np.sin(2 * np.pi * 440 * t) * 0.05
        noise = np.random.normal(0, 0.15, len(signal))
        noisy_signal = signal + noise
        
        # Add clipping
        clipped_signal = np.clip(noisy_signal * 2.0, -1.0, 1.0)
        audio_data = (clipped_signal * 32767).astype(np.int16)
        
        # Run analysis
        metrics = analyzer.analyze(audio_data, sample_rate)
        
        # Verify multiple issues are detected
        assert metrics.snr_db < 20.0, "Should detect low SNR"
        assert metrics.clipping_percentage > 0, "Should detect clipping"
    
    def test_quality_validation_pipeline_metrics_structure(self, analyzer):
        """Test that pipeline returns complete metrics structure."""
        # Generate test audio
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = np.sin(2 * np.pi * 440 * t) * 0.5
        
        # Run analysis
        metrics = analyzer.analyze(audio_data, sample_rate)
        
        # Verify all required fields are present
        assert hasattr(metrics, 'timestamp'), "Metrics should have timestamp"
        assert hasattr(metrics, 'stream_id'), "Metrics should have stream_id"
        assert hasattr(metrics, 'snr_db'), "Metrics should have snr_db"
        assert hasattr(metrics, 'snr_rolling_avg'), "Metrics should have snr_rolling_avg"
        assert hasattr(metrics, 'clipping_percentage'), "Metrics should have clipping_percentage"
        assert hasattr(metrics, 'clipped_sample_count'), "Metrics should have clipped_sample_count"
        assert hasattr(metrics, 'is_clipping'), "Metrics should have is_clipping"
        assert hasattr(metrics, 'echo_level_db'), "Metrics should have echo_level_db"
        assert hasattr(metrics, 'echo_delay_ms'), "Metrics should have echo_delay_ms"
        assert hasattr(metrics, 'has_echo'), "Metrics should have has_echo"
        assert hasattr(metrics, 'is_silent'), "Metrics should have is_silent"
        assert hasattr(metrics, 'duration_s'), "Metrics should have duration_s"
        assert hasattr(metrics, 'energy_db'), "Metrics should have energy_db"
    
    def test_quality_validation_pipeline_with_different_sample_rates(self, analyzer):
        """Test pipeline works with different sample rates."""
        sample_rates = [8000, 16000, 24000, 48000]
        
        for sample_rate in sample_rates:
            duration = 1.0
            t = np.linspace(0, duration, int(sample_rate * duration))
            audio_data = np.sin(2 * np.pi * 440 * t) * 0.5
            
            # Run analysis
            metrics = analyzer.analyze(audio_data, sample_rate)
            
            # Verify analysis completes successfully
            assert metrics is not None, f"Analysis should complete for {sample_rate} Hz"
            assert metrics.snr_db > 0, f"SNR should be calculated for {sample_rate} Hz"
    
    def test_quality_validation_pipeline_performance(self, analyzer):
        """Test that pipeline completes within performance budget."""
        import time
        
        # Generate 1 second of audio
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = np.sin(2 * np.pi * 440 * t) * 0.5
        
        # Measure processing time
        start = time.perf_counter()
        for _ in range(10):
            analyzer.analyze(audio_data, sample_rate)
        end = time.perf_counter()
        
        avg_processing_time = (end - start) / 10
        audio_duration = len(audio_data) / sample_rate
        overhead_percent = (avg_processing_time / audio_duration) * 100
        
        # Verify processing overhead is reasonable (allow up to 10% for integration test)
        assert overhead_percent < 10.0, \
            f"Processing overhead {overhead_percent:.2f}% exceeds 10% budget"
    
    def test_quality_validation_pipeline_with_real_world_audio(self, analyzer):
        """Test pipeline with realistic audio patterns."""
        sample_rate = 16000
        duration = 2.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Simulate speech-like audio with varying amplitude
        audio_data = np.zeros(len(t))
        for i in range(5):
            freq = 200 + i * 100
            amplitude = 0.3 + np.random.rand() * 0.2
            audio_data += np.sin(2 * np.pi * freq * t) * amplitude
        
        # Add some noise
        audio_data += np.random.normal(0, 0.02, len(audio_data))
        
        # Run analysis
        metrics = analyzer.analyze(audio_data, sample_rate)
        
        # Verify analysis completes and returns reasonable values
        assert metrics is not None, "Analysis should complete"
        assert -10 < metrics.snr_db < 50, f"SNR should be in reasonable range, got {metrics.snr_db:.2f} dB"
        assert 0 <= metrics.clipping_percentage <= 100, "Clipping percentage should be valid"
        assert not metrics.is_silent, "Speech-like audio should not be silent"
