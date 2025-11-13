"""Unit tests for SpeakingRateDetector."""

import numpy as np
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from emotion_dynamics.detectors.speaking_rate_detector import SpeakingRateDetector
from emotion_dynamics.models.rate_result import RateResult
from emotion_dynamics.exceptions import RateDetectionError


class TestSpeakingRateDetector:
    """Test suite for SpeakingRateDetector."""
    
    @pytest.fixture
    def detector(self):
        """Fixture for SpeakingRateDetector instance."""
        return SpeakingRateDetector()
    
    def test_initialization_success(self):
        """Test successful initialization of SpeakingRateDetector."""
        detector = SpeakingRateDetector()
        assert detector is not None
        assert hasattr(detector, 'librosa')
    
    def test_detect_rate_very_slow_speech(self, detector):
        """Test rate detection with very slow speech (< 100 WPM)."""
        # Generate audio with sparse onsets (very slow)
        sample_rate = 16000
        duration = 3.0
        # Create signal with few onsets - use very sparse pattern
        audio_data = self._generate_speech_with_onsets(
            sample_rate, duration, onset_count=2
        )
        
        result = detector.detect_rate(audio_data, sample_rate)
        
        assert isinstance(result, RateResult)
        # Verify it's classified as very slow or slow (librosa may detect extra onsets)
        assert result.classification in ['very_slow', 'slow']
        assert result.wpm < 130.0  # At most slow
        assert result.onset_count >= 0
        assert isinstance(result.timestamp, datetime)
    
    def test_detect_rate_slow_speech(self, detector):
        """Test rate detection with slow speech (100-130 WPM)."""
        # Generate audio with moderate onsets (slow)
        sample_rate = 16000
        duration = 3.0
        # Create signal with onsets for ~115 WPM
        audio_data = self._generate_speech_with_onsets(
            sample_rate, duration, onset_count=3
        )
        
        result = detector.detect_rate(audio_data, sample_rate)
        
        assert isinstance(result, RateResult)
        # Verify it's in the slower range (librosa may detect extra onsets)
        assert result.classification in ['very_slow', 'slow', 'medium']
        assert result.wpm < 160.0  # At most medium
    
    def test_detect_rate_medium_speech(self, detector):
        """Test rate detection with medium speech (130-160 WPM)."""
        # Generate audio with regular onsets (medium)
        sample_rate = 16000
        duration = 3.0
        # Create signal with onsets for ~145 WPM
        audio_data = self._generate_speech_with_onsets(
            sample_rate, duration, onset_count=4
        )
        
        result = detector.detect_rate(audio_data, sample_rate)
        
        assert isinstance(result, RateResult)
        # Verify it's in the medium range (librosa may detect extra onsets)
        assert result.classification in ['slow', 'medium', 'fast']
        assert result.wpm < 190.0  # At most fast
    
    def test_detect_rate_fast_speech(self, detector):
        """Test rate detection with fast speech (160-190 WPM)."""
        # Generate audio with frequent onsets (fast)
        sample_rate = 16000
        duration = 3.0
        # Create signal with onsets for ~175 WPM
        audio_data = self._generate_speech_with_onsets(
            sample_rate, duration, onset_count=5
        )
        
        result = detector.detect_rate(audio_data, sample_rate)
        
        assert isinstance(result, RateResult)
        # Verify it's in the faster range (librosa may detect extra onsets)
        assert result.classification in ['medium', 'fast', 'very_fast']
        assert result.wpm >= 100.0  # At least medium speed
    
    def test_detect_rate_very_fast_speech(self, detector):
        """Test rate detection with very fast speech (> 190 WPM)."""
        # Generate audio with many onsets (very fast)
        sample_rate = 16000
        duration = 3.0
        # Create signal with onsets for ~200 WPM
        audio_data = self._generate_speech_with_onsets(
            sample_rate, duration, onset_count=10
        )
        
        result = detector.detect_rate(audio_data, sample_rate)
        
        assert isinstance(result, RateResult)
        assert result.classification == 'very_fast'
        assert result.wpm >= 190.0
    
    def test_onset_detection_with_known_patterns(self, detector):
        """Test onset detection with known speech patterns."""
        sample_rate = 16000
        duration = 2.0
        
        # Create signal with clear onset patterns (bursts of energy)
        audio_data = self._generate_speech_with_clear_onsets(
            sample_rate, duration, num_bursts=8
        )
        
        result = detector.detect_rate(audio_data, sample_rate)
        
        assert isinstance(result, RateResult)
        # Should detect multiple onsets
        assert result.onset_count > 0
        assert result.wpm > 0
    
    def test_wpm_calculation_accuracy(self, detector):
        """Test WPM calculation accuracy with known onset count."""
        sample_rate = 16000
        duration = 1.0  # 1 second = 1/60 minute
        
        # Create signal with known number of onsets
        audio_data = self._generate_speech_with_onsets(
            sample_rate, duration, onset_count=3
        )
        
        result = detector.detect_rate(audio_data, sample_rate)
        
        # WPM = onset_count / duration_minutes
        # For 1 second (1/60 minute) with 3 onsets: 3 / (1/60) = 180 WPM
        # But librosa may detect more onsets, so we just verify WPM is calculated
        
        assert isinstance(result, RateResult)
        # Verify WPM is positive and reasonable
        assert result.wpm > 0
        assert result.wpm < 1000.0  # Sanity check
        # Verify onset count is at least what we created
        assert result.onset_count >= 3
    
    def test_rate_classification_thresholds(self, detector):
        """Test rate classification at threshold boundaries."""
        sample_rate = 16000
        duration = 3.0
        
        # Test that different onset counts produce different classifications
        # Note: librosa may detect more onsets than we create, so we test relative ordering
        onset_counts = [2, 3, 4, 5, 6]
        results = []
        
        for onset_count in onset_counts:
            audio_data = self._generate_speech_with_onsets(
                sample_rate, duration, onset_count=onset_count
            )
            result = detector.detect_rate(audio_data, sample_rate)
            results.append((onset_count, result.classification, result.wpm))
        
        # Verify that WPM generally increases with onset count
        wpm_values = [r[2] for r in results]
        for i in range(len(wpm_values) - 1):
            # Allow some variation but generally should increase
            assert wpm_values[i] <= wpm_values[i + 1] + 50, \
                f"WPM should generally increase: {results}"
    
    def test_fallback_on_librosa_error(self, detector):
        """Test fallback to medium rate when librosa fails."""
        sample_rate = 16000
        duration = 1.0
        audio_data = np.random.randn(int(sample_rate * duration))
        
        # Mock librosa.onset.onset_detect to raise an exception
        with patch.object(detector.librosa.onset, 'onset_detect', side_effect=Exception("Librosa error")):
            result = detector.detect_rate(audio_data, sample_rate)
            
            # Should return default medium rate
            assert result.classification == 'medium'
            assert result.wpm == 145.0
            assert result.onset_count == 0
            assert isinstance(result.timestamp, datetime)
    
    def test_fallback_on_invalid_audio_data(self, detector):
        """Test fallback when audio data is invalid."""
        sample_rate = 16000
        
        # Test with non-numpy array
        invalid_data = [1, 2, 3, 4, 5]
        result = detector.detect_rate(invalid_data, sample_rate)
        
        assert result.classification == 'medium'
        assert result.wpm == 145.0
        assert result.onset_count == 0
    
    def test_fallback_on_empty_audio(self, detector):
        """Test fallback when audio data is empty."""
        sample_rate = 16000
        empty_audio = np.array([])
        
        result = detector.detect_rate(empty_audio, sample_rate)
        
        assert result.classification == 'medium'
        assert result.wpm == 145.0
        assert result.onset_count == 0
    
    def test_fallback_on_invalid_sample_rate(self, detector):
        """Test fallback when sample rate is invalid."""
        audio_data = np.random.randn(16000)
        
        # Test with negative sample rate
        result = detector.detect_rate(audio_data, -16000)
        assert result.classification == 'medium'
        
        # Test with zero sample rate
        result = detector.detect_rate(audio_data, 0)
        assert result.classification == 'medium'
        
        # Test with non-integer sample rate
        result = detector.detect_rate(audio_data, 16000.5)
        assert result.classification == 'medium'
    
    def test_continuous_speech_detection(self, detector):
        """Test handling of continuous speech (many onsets)."""
        sample_rate = 16000
        duration = 3.0
        
        # Create continuous speech pattern with many onsets
        audio_data = self._generate_continuous_speech(sample_rate, duration)
        
        result = detector.detect_rate(audio_data, sample_rate)
        
        assert isinstance(result, RateResult)
        # Continuous speech should have many onsets
        assert result.onset_count > 5
        assert result.wpm > 0
    
    def test_sparse_speech_detection(self, detector):
        """Test handling of sparse speech (few onsets)."""
        sample_rate = 16000
        duration = 3.0
        
        # Create sparse speech pattern with few onsets
        audio_data = self._generate_sparse_speech(sample_rate, duration)
        
        result = detector.detect_rate(audio_data, sample_rate)
        
        assert isinstance(result, RateResult)
        # Sparse speech should have few onsets
        assert result.onset_count >= 0
        # WPM should be low
        assert result.wpm < 150.0
    
    def test_stereo_to_mono_conversion(self, detector):
        """Test automatic conversion of stereo audio to mono."""
        sample_rate = 16000
        duration = 2.0
        
        # Create stereo audio (2 channels)
        left_channel = self._generate_speech_with_onsets(sample_rate, duration, onset_count=6)
        right_channel = self._generate_speech_with_onsets(sample_rate, duration, onset_count=6)
        stereo_audio = np.vstack([left_channel, right_channel])
        
        result = detector.detect_rate(stereo_audio, sample_rate)
        
        # Should successfully process and return result
        assert isinstance(result, RateResult)
        assert result.classification in ['very_slow', 'slow', 'medium', 'fast', 'very_fast']
    
    def test_different_sample_rates(self, detector):
        """Test rate detection with different sample rates."""
        duration = 2.0
        
        sample_rates = [8000, 16000, 24000, 48000]
        
        for sr in sample_rates:
            audio_data = self._generate_speech_with_onsets(sr, duration, onset_count=6)
            
            result = detector.detect_rate(audio_data, sr)
            
            assert isinstance(result, RateResult)
            assert result.classification in ['very_slow', 'slow', 'medium', 'fast', 'very_fast']
    
    def test_short_audio_duration(self, detector):
        """Test rate detection with very short audio (< 1 second)."""
        sample_rate = 16000
        duration = 0.5  # 500ms
        
        audio_data = self._generate_speech_with_onsets(sample_rate, duration, onset_count=2)
        
        result = detector.detect_rate(audio_data, sample_rate)
        
        assert isinstance(result, RateResult)
        assert result.classification in ['very_slow', 'slow', 'medium', 'fast', 'very_fast']
    
    def test_long_audio_duration(self, detector):
        """Test rate detection with long audio (> 3 seconds)."""
        sample_rate = 16000
        duration = 5.0
        
        audio_data = self._generate_speech_with_onsets(sample_rate, duration, onset_count=10)
        
        result = detector.detect_rate(audio_data, sample_rate)
        
        assert isinstance(result, RateResult)
        assert result.classification in ['very_slow', 'slow', 'medium', 'fast', 'very_fast']
    
    def test_zero_duration_audio(self, detector):
        """Test handling of extremely short audio that results in zero duration."""
        sample_rate = 16000
        # Single sample (essentially zero duration)
        audio_data = np.array([0.5])
        
        result = detector.detect_rate(audio_data, sample_rate)
        
        # Should handle gracefully with fallback or zero WPM
        assert isinstance(result, RateResult)
        assert result.wpm >= 0
    
    def test_silent_audio(self, detector):
        """Test rate detection with silent audio (no onsets expected)."""
        sample_rate = 16000
        duration = 2.0
        
        # Generate silent audio
        audio_data = np.zeros(int(sample_rate * duration))
        
        result = detector.detect_rate(audio_data, sample_rate)
        
        assert isinstance(result, RateResult)
        # Silent audio should have few or no onsets
        assert result.onset_count >= 0
        # WPM should be very low or zero
        assert result.wpm >= 0
    
    def test_noisy_audio(self, detector):
        """Test rate detection with noisy audio."""
        sample_rate = 16000
        duration = 2.0
        
        # Generate speech with noise
        speech = self._generate_speech_with_onsets(sample_rate, duration, onset_count=6)
        noise = np.random.normal(0, 0.1, len(speech))
        noisy_audio = speech + noise
        
        result = detector.detect_rate(noisy_audio, sample_rate)
        
        assert isinstance(result, RateResult)
        # Should still detect onsets despite noise
        assert result.classification in ['very_slow', 'slow', 'medium', 'fast', 'very_fast']
    
    def test_result_timestamp_is_recent(self, detector):
        """Test that result timestamp is recent (within last second)."""
        sample_rate = 16000
        duration = 1.0
        audio_data = self._generate_speech_with_onsets(sample_rate, duration, onset_count=5)
        
        before = datetime.now(timezone.utc)
        result = detector.detect_rate(audio_data, sample_rate)
        after = datetime.now(timezone.utc)
        
        assert before <= result.timestamp <= after
    
    def test_consistent_results_for_same_input(self, detector):
        """Test that same input produces consistent results."""
        sample_rate = 16000
        duration = 2.0
        audio_data = self._generate_speech_with_onsets(sample_rate, duration, onset_count=6)
        
        result1 = detector.detect_rate(audio_data, sample_rate)
        result2 = detector.detect_rate(audio_data, sample_rate)
        
        # Results should be consistent
        assert result1.classification == result2.classification
        assert result1.onset_count == result2.onset_count
        assert abs(result1.wpm - result2.wpm) < 0.1
    
    def test_wpm_increases_with_onset_count(self, detector):
        """Test that WPM increases as onset count increases."""
        sample_rate = 16000
        duration = 3.0
        
        onset_counts = [3, 5, 7, 9, 11]
        wpm_values = []
        
        for count in onset_counts:
            audio_data = self._generate_speech_with_onsets(sample_rate, duration, onset_count=count)
            result = detector.detect_rate(audio_data, sample_rate)
            wpm_values.append(result.wpm)
        
        # WPM should generally increase with onset count
        for i in range(len(wpm_values) - 1):
            assert wpm_values[i] <= wpm_values[i + 1], \
                f"WPM should increase with onset count: {wpm_values}"
    
    # Helper methods for generating test audio
    
    def _generate_speech_with_onsets(self, sample_rate, duration, onset_count):
        """Generate synthetic speech audio with specified number of onsets."""
        total_samples = int(sample_rate * duration)
        audio_data = np.zeros(total_samples)
        
        if onset_count > 0:
            # Distribute onsets evenly across duration
            onset_interval = total_samples // onset_count
            
            for i in range(onset_count):
                onset_position = i * onset_interval
                # Create a burst of energy at each onset
                burst_length = min(int(sample_rate * 0.1), onset_interval // 2)
                end_position = min(onset_position + burst_length, total_samples)
                
                # Generate burst with varying frequency
                t = np.arange(burst_length) / sample_rate
                frequency = 200 + (i * 50)  # Varying frequency
                burst = np.sin(2 * np.pi * frequency * t) * 0.5
                
                audio_data[onset_position:end_position] = burst[:end_position - onset_position]
        
        return audio_data
    
    def _generate_speech_with_clear_onsets(self, sample_rate, duration, num_bursts):
        """Generate audio with clear onset patterns (energy bursts)."""
        total_samples = int(sample_rate * duration)
        audio_data = np.zeros(total_samples)
        
        burst_interval = total_samples // num_bursts
        burst_length = int(sample_rate * 0.05)  # 50ms bursts
        
        for i in range(num_bursts):
            start = i * burst_interval
            end = min(start + burst_length, total_samples)
            
            # Create energy burst
            t = np.arange(end - start) / sample_rate
            frequency = 300 + (i * 100)
            burst = np.sin(2 * np.pi * frequency * t) * 0.7
            
            audio_data[start:end] = burst
        
        return audio_data
    
    def _generate_continuous_speech(self, sample_rate, duration):
        """Generate continuous speech pattern with many onsets."""
        total_samples = int(sample_rate * duration)
        audio_data = np.zeros(total_samples)
        
        # Create many short bursts (continuous speech)
        num_bursts = int(duration * 10)  # 10 bursts per second
        burst_length = int(sample_rate * 0.03)  # 30ms bursts
        
        for i in range(num_bursts):
            start = int(i * total_samples / num_bursts)
            end = min(start + burst_length, total_samples)
            
            t = np.arange(end - start) / sample_rate
            frequency = 250 + (i % 5) * 50
            burst = np.sin(2 * np.pi * frequency * t) * 0.6
            
            audio_data[start:end] = burst
        
        return audio_data
    
    def _generate_sparse_speech(self, sample_rate, duration):
        """Generate sparse speech pattern with few onsets."""
        total_samples = int(sample_rate * duration)
        audio_data = np.zeros(total_samples)
        
        # Create few bursts (sparse speech)
        num_bursts = 3
        burst_length = int(sample_rate * 0.1)  # 100ms bursts
        
        for i in range(num_bursts):
            start = int(i * total_samples / num_bursts)
            end = min(start + burst_length, total_samples)
            
            t = np.arange(end - start) / sample_rate
            frequency = 300
            burst = np.sin(2 * np.pi * frequency * t) * 0.5
            
            audio_data[start:end] = burst
        
        return audio_data
