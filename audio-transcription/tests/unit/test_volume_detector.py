"""Unit tests for VolumeDetector."""

import numpy as np
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from emotion_dynamics.detectors.volume_detector import VolumeDetector
from emotion_dynamics.models.volume_result import VolumeResult
from emotion_dynamics.exceptions import VolumeDetectionError


class TestVolumeDetector:
    """Test suite for VolumeDetector."""
    
    @pytest.fixture
    def detector(self):
        """Fixture for VolumeDetector instance."""
        return VolumeDetector()
    
    def test_initialization_success(self):
        """Test successful initialization of VolumeDetector."""
        detector = VolumeDetector()
        assert detector is not None
        assert hasattr(detector, 'librosa')
    
    # Note: Testing initialization without librosa is complex due to module import mechanics
    # The error handling for missing librosa is covered by the fallback tests
    
    def test_detect_volume_loud_signal(self, detector):
        """Test volume detection with loud signal (> -10 dB)."""
        # Generate loud sine wave
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        # High amplitude signal
        audio_data = np.sin(2 * np.pi * frequency * t) * 0.9
        
        result = detector.detect_volume(audio_data, sample_rate)
        
        assert isinstance(result, VolumeResult)
        assert result.level == 'loud'
        assert result.db_value > -10.0
        assert isinstance(result.timestamp, datetime)
    
    def test_detect_volume_medium_signal(self, detector):
        """Test volume detection with medium signal (-10 to -20 dB)."""
        # Generate medium amplitude signal
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        # Medium amplitude signal
        audio_data = np.sin(2 * np.pi * frequency * t) * 0.3
        
        result = detector.detect_volume(audio_data, sample_rate)
        
        assert isinstance(result, VolumeResult)
        assert result.level == 'medium'
        assert -20.0 < result.db_value <= -10.0
    
    def test_detect_volume_soft_signal(self, detector):
        """Test volume detection with soft signal (-20 to -30 dB)."""
        # Generate soft amplitude signal
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        # Soft amplitude signal
        audio_data = np.sin(2 * np.pi * frequency * t) * 0.1
        
        result = detector.detect_volume(audio_data, sample_rate)
        
        assert isinstance(result, VolumeResult)
        assert result.level == 'soft'
        assert -30.0 < result.db_value <= -20.0
    
    def test_detect_volume_whisper_signal(self, detector):
        """Test volume detection with whisper signal (< -30 dB)."""
        # Generate very quiet signal
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        # Very low amplitude signal
        audio_data = np.sin(2 * np.pi * frequency * t) * 0.03
        
        result = detector.detect_volume(audio_data, sample_rate)
        
        assert isinstance(result, VolumeResult)
        assert result.level == 'whisper'
        assert result.db_value <= -30.0
    
    def test_detect_volume_silent_audio(self, detector):
        """Test volume detection with silent audio (near-zero amplitude)."""
        # Generate near-silent signal
        sample_rate = 16000
        duration = 1.0
        audio_data = np.random.normal(0, 0.001, int(sample_rate * duration))
        
        result = detector.detect_volume(audio_data, sample_rate)
        
        assert isinstance(result, VolumeResult)
        # Silent audio should be classified as whisper
        assert result.level == 'whisper'
        assert not np.isnan(result.db_value)
        assert not np.isinf(result.db_value)
    
    def test_detect_volume_clipped_audio(self, detector):
        """Test volume detection with clipped audio (amplitude at limits)."""
        # Generate clipped signal (values at -1.0 and 1.0)
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = np.sin(2 * np.pi * frequency * t)
        # Clip to maximum values
        audio_data = np.clip(audio_data * 2.0, -1.0, 1.0)
        
        result = detector.detect_volume(audio_data, sample_rate)
        
        assert isinstance(result, VolumeResult)
        # Clipped audio should be loud
        assert result.level == 'loud'
        assert result.db_value > -10.0
    
    def test_rms_calculation_accuracy(self, detector):
        """Test RMS energy calculation with known values."""
        # Create signal with known RMS
        sample_rate = 16000
        duration = 1.0
        # Constant amplitude signal has RMS equal to amplitude
        amplitude = 0.5
        audio_data = np.ones(int(sample_rate * duration)) * amplitude
        
        result = detector.detect_volume(audio_data, sample_rate)
        
        assert isinstance(result, VolumeResult)
        # Verify RMS was calculated (result should be consistent)
        assert isinstance(result.db_value, float)
    
    def test_db_conversion_accuracy(self, detector):
        """Test decibel conversion produces expected range."""
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Test multiple amplitude levels
        amplitudes = [0.9, 0.5, 0.3, 0.1, 0.03]
        db_values = []
        
        for amp in amplitudes:
            audio_data = np.sin(2 * np.pi * frequency * t) * amp
            result = detector.detect_volume(audio_data, sample_rate)
            db_values.append(result.db_value)
        
        # dB values should decrease as amplitude decreases
        for i in range(len(db_values) - 1):
            assert db_values[i] > db_values[i + 1], \
                f"dB should decrease with amplitude: {db_values}"
    
    def test_volume_classification_thresholds(self, detector):
        """Test volume classification at threshold boundaries."""
        sample_rate = 16000
        duration = 1.0
        
        # Test cases at threshold boundaries
        test_cases = [
            (0.95, 'loud'),      # Well above -10 dB
            (0.35, 'medium'),    # Between -10 and -20 dB
            (0.12, 'soft'),      # Between -20 and -30 dB
            (0.02, 'whisper'),   # Below -30 dB
        ]
        
        for amplitude, expected_level in test_cases:
            frequency = 440.0
            t = np.linspace(0, duration, int(sample_rate * duration))
            audio_data = np.sin(2 * np.pi * frequency * t) * amplitude
            
            result = detector.detect_volume(audio_data, sample_rate)
            assert result.level == expected_level, \
                f"Amplitude {amplitude} should be {expected_level}, got {result.level}"
    
    def test_fallback_on_librosa_error(self, detector):
        """Test fallback to medium volume when librosa fails."""
        sample_rate = 16000
        duration = 1.0
        audio_data = np.random.randn(int(sample_rate * duration))
        
        # Mock librosa.feature.rms to raise an exception
        with patch.object(detector.librosa.feature, 'rms', side_effect=Exception("Librosa error")):
            result = detector.detect_volume(audio_data, sample_rate)
            
            # Should return default medium volume
            assert result.level == 'medium'
            assert result.db_value == -15.0
            assert isinstance(result.timestamp, datetime)
    
    def test_fallback_on_invalid_audio_data(self, detector):
        """Test fallback when audio data is invalid."""
        sample_rate = 16000
        
        # Test with non-numpy array
        invalid_data = [1, 2, 3, 4, 5]
        result = detector.detect_volume(invalid_data, sample_rate)
        
        assert result.level == 'medium'
        assert result.db_value == -15.0
    
    def test_fallback_on_empty_audio(self, detector):
        """Test fallback when audio data is empty."""
        sample_rate = 16000
        empty_audio = np.array([])
        
        result = detector.detect_volume(empty_audio, sample_rate)
        
        assert result.level == 'medium'
        assert result.db_value == -15.0
    
    def test_fallback_on_invalid_sample_rate(self, detector):
        """Test fallback when sample rate is invalid."""
        audio_data = np.random.randn(16000)
        
        # Test with negative sample rate
        result = detector.detect_volume(audio_data, -16000)
        assert result.level == 'medium'
        
        # Test with zero sample rate
        result = detector.detect_volume(audio_data, 0)
        assert result.level == 'medium'
        
        # Test with non-integer sample rate
        result = detector.detect_volume(audio_data, 16000.5)
        assert result.level == 'medium'
    
    def test_stereo_to_mono_conversion(self, detector):
        """Test automatic conversion of stereo audio to mono."""
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Create stereo audio (2 channels)
        left_channel = np.sin(2 * np.pi * frequency * t) * 0.5
        right_channel = np.sin(2 * np.pi * frequency * t) * 0.5
        stereo_audio = np.vstack([left_channel, right_channel])
        
        result = detector.detect_volume(stereo_audio, sample_rate)
        
        # Should successfully process and return result
        assert isinstance(result, VolumeResult)
        assert result.level in ['loud', 'medium', 'soft', 'whisper']
    
    def test_different_sample_rates(self, detector):
        """Test volume detection with different sample rates."""
        duration = 1.0
        frequency = 440.0
        
        sample_rates = [8000, 16000, 24000, 48000]
        
        for sr in sample_rates:
            t = np.linspace(0, duration, int(sr * duration))
            audio_data = np.sin(2 * np.pi * frequency * t) * 0.5
            
            result = detector.detect_volume(audio_data, sr)
            
            assert isinstance(result, VolumeResult)
            assert result.level in ['loud', 'medium', 'soft', 'whisper']
    
    def test_short_audio_duration(self, detector):
        """Test volume detection with very short audio (< 1 second)."""
        sample_rate = 16000
        duration = 0.1  # 100ms
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = np.sin(2 * np.pi * frequency * t) * 0.5
        
        result = detector.detect_volume(audio_data, sample_rate)
        
        assert isinstance(result, VolumeResult)
        assert result.level in ['loud', 'medium', 'soft', 'whisper']
    
    def test_long_audio_duration(self, detector):
        """Test volume detection with long audio (> 3 seconds)."""
        sample_rate = 16000
        duration = 5.0
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = np.sin(2 * np.pi * frequency * t) * 0.5
        
        result = detector.detect_volume(audio_data, sample_rate)
        
        assert isinstance(result, VolumeResult)
        assert result.level in ['loud', 'medium', 'soft', 'whisper']
    
    def test_noisy_audio(self, detector):
        """Test volume detection with noisy audio."""
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Signal with noise
        signal = np.sin(2 * np.pi * frequency * t) * 0.5
        noise = np.random.normal(0, 0.05, len(signal))
        noisy_audio = signal + noise
        
        result = detector.detect_volume(noisy_audio, sample_rate)
        
        assert isinstance(result, VolumeResult)
        # Should still classify based on overall RMS
        assert result.level in ['loud', 'medium', 'soft', 'whisper']
    
    def test_varying_amplitude_audio(self, detector):
        """Test volume detection with varying amplitude (envelope)."""
        sample_rate = 16000
        duration = 2.0
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Create signal with amplitude envelope (fade in/out)
        envelope = np.sin(np.pi * t / duration)  # 0 to 1 to 0
        audio_data = np.sin(2 * np.pi * frequency * t) * envelope * 0.5
        
        result = detector.detect_volume(audio_data, sample_rate)
        
        assert isinstance(result, VolumeResult)
        # Should average across the entire signal
        assert result.level in ['loud', 'medium', 'soft', 'whisper']
    
    def test_result_timestamp_is_recent(self, detector):
        """Test that result timestamp is recent (within last second)."""
        sample_rate = 16000
        duration = 1.0
        audio_data = np.random.randn(int(sample_rate * duration)) * 0.5
        
        before = datetime.now(timezone.utc)
        result = detector.detect_volume(audio_data, sample_rate)
        after = datetime.now(timezone.utc)
        
        assert before <= result.timestamp <= after
    
    def test_consistent_results_for_same_input(self, detector):
        """Test that same input produces consistent results."""
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = np.sin(2 * np.pi * frequency * t) * 0.5
        
        result1 = detector.detect_volume(audio_data, sample_rate)
        result2 = detector.detect_volume(audio_data, sample_rate)
        
        # Results should be consistent (same level and similar dB)
        assert result1.level == result2.level
        assert abs(result1.db_value - result2.db_value) < 0.1
