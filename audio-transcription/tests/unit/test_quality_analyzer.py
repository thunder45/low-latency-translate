"""
Unit tests for AudioQualityAnalyzer.

Tests the aggregation of all quality detection components (SNR, clipping,
echo, silence) into comprehensive quality metrics.
"""

import pytest
import numpy as np
import time

from audio_quality.analyzers.quality_analyzer import AudioQualityAnalyzer
from audio_quality.models.quality_config import QualityConfig
from audio_quality.models.quality_metrics import QualityMetrics


class TestAudioQualityAnalyzer:
    """Test suite for AudioQualityAnalyzer class."""
    
    @pytest.fixture
    def default_analyzer(self):
        """Fixture providing AudioQualityAnalyzer with default config."""
        return AudioQualityAnalyzer()
    
    @pytest.fixture
    def custom_analyzer(self):
        """Fixture providing AudioQualityAnalyzer with custom config."""
        config = QualityConfig(
            snr_threshold_db=25.0,
            clipping_threshold_percent=2.0,
            echo_threshold_db=-20.0,
            silence_threshold_db=-45.0
        )
        return AudioQualityAnalyzer(config)
    
    @pytest.fixture
    def clean_audio(self):
        """Fixture providing clean audio signal (high SNR, no issues)."""
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        # Clean sine wave at moderate amplitude
        signal = np.sin(2 * np.pi * frequency * t) * 0.3
        return (signal * 32767).astype(np.int16)
    
    @pytest.fixture
    def noisy_audio(self):
        """Fixture providing noisy audio signal (low SNR)."""
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        # Weak signal with strong noise
        signal = np.sin(2 * np.pi * frequency * t) * 0.05
        noise = np.random.normal(0, 0.1, len(signal))
        noisy_signal = signal + noise
        return (noisy_signal * 32767).astype(np.int16)
    
    @pytest.fixture
    def clipped_audio(self):
        """Fixture providing clipped audio signal."""
        sample_rate = 16000
        duration = 1.0
        # Generate signal that clips
        signal = np.random.randn(int(sample_rate * duration))
        signal = signal * 2.0  # Amplify to cause clipping
        signal = np.clip(signal, -1.0, 1.0)
        return (signal * 32767).astype(np.int16)
    
    def test_initialization_with_default_config(self):
        """Test analyzer initializes with default configuration."""
        analyzer = AudioQualityAnalyzer()
        
        assert analyzer.config is not None
        assert analyzer.snr_calculator is not None
        assert analyzer.clipping_detector is not None
        assert analyzer.echo_detector is not None
        assert analyzer.silence_detector is not None
    
    def test_initialization_with_custom_config(self, custom_analyzer):
        """Test analyzer initializes with custom configuration."""
        assert custom_analyzer.config.snr_threshold_db == 25.0
        assert custom_analyzer.config.clipping_threshold_percent == 2.0
        assert custom_analyzer.config.echo_threshold_db == -20.0
        assert custom_analyzer.config.silence_threshold_db == -45.0
    
    def test_initialization_with_invalid_config_fails(self):
        """Test analyzer rejects invalid configuration."""
        invalid_config = QualityConfig(snr_threshold_db=5.0)  # Too low
        
        with pytest.raises(ValueError, match='Invalid configuration'):
            AudioQualityAnalyzer(invalid_config)
    
    def test_analyze_returns_quality_metrics(self, default_analyzer, clean_audio):
        """Test analyze returns QualityMetrics object."""
        metrics = default_analyzer.analyze(
            clean_audio,
            sample_rate=16000,
            stream_id='test-stream'
        )
        
        assert isinstance(metrics, QualityMetrics)
        assert metrics.stream_id == 'test-stream'
        assert metrics.timestamp > 0
    
    def test_analyze_with_clean_audio(self, default_analyzer, clean_audio):
        """Test analyze detects high quality in clean audio."""
        metrics = default_analyzer.analyze(
            clean_audio,
            sample_rate=16000,
            stream_id='test-stream'
        )
        
        # Clean audio should have high SNR
        assert metrics.snr_db > 20.0
        # Should not be clipping
        assert not metrics.is_clipping
        assert metrics.clipping_percentage < 1.0
        # Should not be silent
        assert not metrics.is_silent
    
    def test_analyze_with_noisy_audio(self, default_analyzer, noisy_audio):
        """Test analyze detects low SNR in noisy audio."""
        metrics = default_analyzer.analyze(
            noisy_audio,
            sample_rate=16000,
            stream_id='test-stream'
        )
        
        # Noisy audio should have lower SNR
        assert metrics.snr_db < 30.0
        # SNR should be positive (not completely silent)
        assert metrics.snr_db > 0
    
    def test_analyze_with_clipped_audio(self, default_analyzer, clipped_audio):
        """Test analyze detects clipping in distorted audio."""
        metrics = default_analyzer.analyze(
            clipped_audio,
            sample_rate=16000,
            stream_id='test-stream'
        )
        
        # Clipped audio should show clipping
        assert metrics.clipping_percentage > 0
        # May or may not exceed threshold depending on clipping amount
        assert metrics.clipped_sample_count > 0
    
    def test_analyze_aggregates_all_metrics(self, default_analyzer, clean_audio):
        """Test analyze includes all metric types."""
        metrics = default_analyzer.analyze(
            clean_audio,
            sample_rate=16000,
            stream_id='test-stream'
        )
        
        # SNR metrics
        assert hasattr(metrics, 'snr_db')
        assert hasattr(metrics, 'snr_rolling_avg')
        
        # Clipping metrics
        assert hasattr(metrics, 'clipping_percentage')
        assert hasattr(metrics, 'clipped_sample_count')
        assert hasattr(metrics, 'is_clipping')
        
        # Echo metrics
        assert hasattr(metrics, 'echo_level_db')
        assert hasattr(metrics, 'echo_delay_ms')
        assert hasattr(metrics, 'has_echo')
        
        # Silence metrics
        assert hasattr(metrics, 'is_silent')
        assert hasattr(metrics, 'silence_duration_s')
        assert hasattr(metrics, 'energy_db')
    
    def test_analyze_with_custom_timestamp(self, default_analyzer, clean_audio):
        """Test analyze uses provided timestamp."""
        custom_timestamp = 1234567890.0
        
        metrics = default_analyzer.analyze(
            clean_audio,
            sample_rate=16000,
            stream_id='test-stream',
            timestamp=custom_timestamp
        )
        
        assert metrics.timestamp == custom_timestamp
    
    def test_analyze_uses_current_time_when_no_timestamp(self, default_analyzer, clean_audio):
        """Test analyze uses current time when timestamp not provided."""
        before = time.time()
        
        metrics = default_analyzer.analyze(
            clean_audio,
            sample_rate=16000,
            stream_id='test-stream'
        )
        
        after = time.time()
        
        assert before <= metrics.timestamp <= after
    
    def test_analyze_maintains_rolling_snr_average(self, default_analyzer, clean_audio):
        """Test analyze maintains rolling SNR average across calls."""
        # First call
        metrics1 = default_analyzer.analyze(
            clean_audio,
            sample_rate=16000,
            stream_id='test-stream'
        )
        
        # Rolling average should equal current SNR on first call
        assert metrics1.snr_rolling_avg == metrics1.snr_db
        
        # Second call
        metrics2 = default_analyzer.analyze(
            clean_audio,
            sample_rate=16000,
            stream_id='test-stream'
        )
        
        # Rolling average should be average of both measurements
        expected_avg = (metrics1.snr_db + metrics2.snr_db) / 2
        assert abs(metrics2.snr_rolling_avg - expected_avg) < 0.1
    
    def test_analyze_tracks_silence_duration(self, default_analyzer):
        """Test analyze tracks silence duration across calls."""
        # Generate very quiet audio (silence)
        silent_audio = (np.random.randn(16000) * 0.0001 * 32767).astype(np.int16)
        
        # First call at t=0
        metrics1 = default_analyzer.analyze(
            silent_audio,
            sample_rate=16000,
            stream_id='test-stream',
            timestamp=0.0
        )
        
        # Should not be silent yet (< 5 seconds)
        assert metrics1.is_silent is False
        
        # Second call at t=6 (6 seconds of silence)
        metrics2 = default_analyzer.analyze(
            silent_audio,
            sample_rate=16000,
            stream_id='test-stream',
            timestamp=6.0
        )
        
        # Should now detect extended silence
        assert metrics2.is_silent is True
        assert metrics2.silence_duration_s > 5.0
    
    def test_analyze_with_empty_audio_fails(self, default_analyzer):
        """Test analyze raises error with empty audio."""
        empty_audio = np.array([], dtype=np.int16)
        
        with pytest.raises(ValueError, match='cannot be empty'):
            default_analyzer.analyze(
                empty_audio,
                sample_rate=16000,
                stream_id='test-stream'
            )
    
    def test_analyze_with_invalid_sample_rate_fails(self, default_analyzer, clean_audio):
        """Test analyze raises error with invalid sample rate."""
        with pytest.raises(ValueError, match='must be positive'):
            default_analyzer.analyze(
                clean_audio,
                sample_rate=0,
                stream_id='test-stream'
            )
    
    def test_reset_clears_detector_state(self, default_analyzer, clean_audio):
        """Test reset clears all detector state."""
        # Analyze some audio to build up state
        default_analyzer.analyze(
            clean_audio,
            sample_rate=16000,
            stream_id='test-stream'
        )
        
        # Reset
        default_analyzer.reset()
        
        # After reset, rolling average should be None (no history)
        # We can't directly check this, but we can verify behavior
        metrics = default_analyzer.analyze(
            clean_audio,
            sample_rate=16000,
            stream_id='test-stream'
        )
        
        # After reset, rolling average should equal current SNR (first measurement)
        assert metrics.snr_rolling_avg == metrics.snr_db
    
    def test_analyze_with_different_sample_rates(self, default_analyzer):
        """Test analyze works with different sample rates."""
        sample_rates = [8000, 16000, 24000, 48000]
        
        for sample_rate in sample_rates:
            # Generate audio at this sample rate
            duration = 1.0
            audio = (np.random.randn(int(sample_rate * duration)) * 0.3 * 32767).astype(np.int16)
            
            metrics = default_analyzer.analyze(
                audio,
                sample_rate=sample_rate,
                stream_id='test-stream'
            )
            
            # Should successfully analyze at any supported sample rate
            assert metrics is not None
            assert isinstance(metrics, QualityMetrics)
    
    def test_analyze_with_float_audio(self, default_analyzer):
        """Test analyze works with normalized float audio."""
        # Generate normalized float audio (-1.0 to 1.0)
        sample_rate = 16000
        duration = 1.0
        audio = np.random.randn(int(sample_rate * duration)) * 0.3
        
        metrics = default_analyzer.analyze(
            audio,
            sample_rate=sample_rate,
            stream_id='test-stream'
        )
        
        # Should successfully analyze float audio
        assert metrics is not None
        assert isinstance(metrics, QualityMetrics)
    
    def test_multiple_streams_independent(self):
        """Test multiple analyzer instances maintain independent state."""
        analyzer1 = AudioQualityAnalyzer()
        analyzer2 = AudioQualityAnalyzer()
        
        # Generate different audio for each
        audio1 = (np.random.randn(16000) * 0.5 * 32767).astype(np.int16)
        audio2 = (np.random.randn(16000) * 0.2 * 32767).astype(np.int16)
        
        # Analyze with both
        metrics1 = analyzer1.analyze(audio1, 16000, 'stream-1')
        metrics2 = analyzer2.analyze(audio2, 16000, 'stream-2')
        
        # Metrics should be different (different audio)
        assert metrics1.snr_db != metrics2.snr_db
        assert metrics1.stream_id != metrics2.stream_id
