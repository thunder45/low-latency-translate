"""Unit tests for SilenceDetector."""

import numpy as np
import pytest
from audio_quality.analyzers.silence_detector import SilenceDetector


class TestSilenceDetector:
    """Test suite for SilenceDetector."""
    
    @pytest.fixture
    def detector(self):
        """Fixture for SilenceDetector instance."""
        return SilenceDetector(silence_threshold_db=-50.0, duration_threshold_s=5.0)
    
    def test_silence_detection_with_extended_silence(self, detector):
        """Test silence detection with extended silence (>5 seconds)."""
        # Generate extended silence (6 seconds)
        sample_rate = 16000
        duration = 6.0
        silence_segment = np.random.randn(int(sample_rate * duration)) * 0.0001  # Very quiet
        
        # Process silence
        result = detector.detect_silence(silence_segment, timestamp=0.0)
        
        assert result.is_silent, "Should detect extended silence"
        assert result.duration_s > 5.0, f"Silence duration should exceed 5 seconds, got {result.duration_s:.2f}s"
        assert result.energy_db < -50.0, f"Energy should be below threshold, got {result.energy_db:.2f} dB"
    
    def test_silence_detection_with_speech(self, detector):
        """Test silence detection with active speech."""
        # Generate speech-like signal
        sample_rate = 16000
        duration = 1.0
        speech_segment = np.random.randn(int(sample_rate * duration)) * 0.1  # Normal speech level
        
        result = detector.detect_silence(speech_segment, timestamp=0.0)
        
        assert not result.is_silent, "Should not detect silence during speech"
        assert result.duration_s == 0.0, f"Silence duration should be 0, got {result.duration_s:.2f}s"
        assert result.energy_db > -50.0, f"Energy should be above threshold, got {result.energy_db:.2f} dB"
    
    def test_silence_detection_differentiate_pauses_from_technical_issues(self, detector):
        """Test differentiation between speech pauses and technical issues."""
        sample_rate = 16000
        
        # Simulate speech with natural pauses (1-2 seconds)
        speech_segment = np.random.randn(sample_rate) * 0.1  # 1 second of speech
        pause_segment = np.random.randn(sample_rate * 2) * 0.001  # 2 seconds of quiet
        
        # Process speech
        result1 = detector.detect_silence(speech_segment, timestamp=0.0)
        assert not result1.is_silent, "Should not detect silence during speech"
        
        # Process pause (should reset timer)
        result2 = detector.detect_silence(pause_segment, timestamp=1.0)
        assert not result2.is_silent, "Should not detect silence during natural pause (<5s)"
        
        # Process extended silence (6 seconds total)
        extended_silence = np.random.randn(sample_rate * 6) * 0.0001
        result3 = detector.detect_silence(extended_silence, timestamp=3.0)
        assert result3.is_silent, "Should detect extended silence (>5s)"
        assert result3.duration_s > 5.0, f"Silence duration should exceed threshold, got {result3.duration_s:.2f}s"
    
    def test_silence_duration_tracking(self, detector):
        """Test silence duration tracking over multiple chunks."""
        sample_rate = 16000
        chunk_duration = 1.0  # 1 second chunks
        
        # Process 7 chunks of silence
        for i in range(7):
            silence_chunk = np.random.randn(int(sample_rate * chunk_duration)) * 0.0001
            result = detector.detect_silence(silence_chunk, timestamp=float(i))
            
            # At i=4: timestamp=4.0, chunk ends at 5.0, duration=5.0 (at threshold)
            # At i=5: timestamp=5.0, chunk ends at 6.0, duration=6.0 (above threshold)
            # Threshold is 5.0, so >= 5.0 should trigger
            if i < 4:
                assert not result.is_silent, f"Should not detect silence at {i}s (below threshold)"
            else:
                assert result.is_silent, f"Should detect silence at {i}s (at or above threshold)"
                assert result.duration_s >= 5.0, f"Duration should be at least 5s at {i}s"
    
    def test_silence_reset_on_audio_activity(self, detector):
        """Test that silence timer resets when audio energy returns."""
        sample_rate = 16000
        
        # Start with silence
        silence_segment = np.random.randn(sample_rate * 3) * 0.0001  # 3 seconds
        result1 = detector.detect_silence(silence_segment, timestamp=0.0)
        assert not result1.is_silent, "Should not detect silence yet (only 3s)"
        
        # Continue silence
        silence_segment2 = np.random.randn(sample_rate * 3) * 0.0001  # 3 more seconds
        result2 = detector.detect_silence(silence_segment2, timestamp=3.0)
        assert result2.is_silent, "Should detect silence (6s total)"
        
        # Audio returns (above -40 dB)
        speech_segment = np.random.randn(sample_rate) * 0.1
        result3 = detector.detect_silence(speech_segment, timestamp=6.0)
        assert not result3.is_silent, "Should reset silence detection"
        assert result3.duration_s == 0.0, "Duration should reset to 0"
    
    def test_silence_threshold_boundary(self, detector):
        """Test silence detection at threshold boundary (-50 dB)."""
        sample_rate = 16000
        duration = 6.0
        
        # Generate signal just above threshold
        # -50 dB corresponds to RMS amplitude of ~0.00316
        signal_above = np.random.randn(int(sample_rate * duration)) * 0.004
        result_above = detector.detect_silence(signal_above, timestamp=0.0)
        assert not result_above.is_silent, "Should not detect silence just above threshold"
        
        # Generate signal just below threshold
        signal_below = np.random.randn(int(sample_rate * duration)) * 0.0001
        result_below = detector.detect_silence(signal_below, timestamp=0.0)
        assert result_below.is_silent, "Should detect silence below threshold"
    
    def test_silence_detection_with_varying_energy_levels(self, detector):
        """Test silence detection with varying energy levels."""
        sample_rate = 16000
        duration = 1.0
        
        # Test different energy levels
        energy_levels = [0.0001, 0.001, 0.01, 0.1, 0.5]
        
        for energy in energy_levels:
            signal = np.random.randn(int(sample_rate * duration)) * energy
            result = detector.detect_silence(signal, timestamp=0.0)
            
            # Calculate expected energy in dB
            rms = np.sqrt(np.mean(signal ** 2))
            expected_db = 20 * np.log10(rms) if rms > 0 else -100
            
            # Verify energy calculation
            assert abs(result.energy_db - expected_db) < 1.0, \
                f"Energy calculation mismatch: expected {expected_db:.2f} dB, got {result.energy_db:.2f} dB"
    
    def test_silence_detection_zero_signal(self, detector):
        """Test silence detection with completely zero signal."""
        sample_rate = 16000
        duration = 6.0
        zero_signal = np.zeros(int(sample_rate * duration))
        
        result = detector.detect_silence(zero_signal, timestamp=0.0)
        
        assert result.is_silent, "Should detect silence in zero signal"
        assert result.energy_db < -50.0, "Energy should be very low"
    
    def test_silence_detection_short_duration(self, detector):
        """Test that short silence periods don't trigger detection."""
        sample_rate = 16000
        
        # Process 4 seconds of silence (below threshold)
        silence_segment = np.random.randn(sample_rate * 4) * 0.0001
        result = detector.detect_silence(silence_segment, timestamp=0.0)
        
        assert not result.is_silent, "Should not detect silence below duration threshold"
        assert result.duration_s < 5.0, f"Duration should be below threshold, got {result.duration_s:.2f}s"
    
    def test_silence_detection_exact_threshold_duration(self, detector):
        """Test silence detection at exact threshold duration (5.0 seconds)."""
        sample_rate = 16000
        
        # Process exactly 5 seconds of silence
        silence_segment = np.random.randn(sample_rate * 5) * 0.0001
        result = detector.detect_silence(silence_segment, timestamp=0.0)
        
        # At exactly 5 seconds, should trigger detection
        assert result.is_silent, "Should detect silence at exact threshold duration"
        assert result.duration_s >= 5.0, f"Duration should be at least 5s, got {result.duration_s:.2f}s"
    
    def test_silence_detection_multiple_silence_periods(self, detector):
        """Test detection of multiple separate silence periods."""
        sample_rate = 16000
        
        # First silence period (6 seconds)
        silence1 = np.random.randn(sample_rate * 6) * 0.0001
        result1 = detector.detect_silence(silence1, timestamp=0.0)
        assert result1.is_silent, "Should detect first silence period"
        
        # Speech breaks silence
        speech = np.random.randn(sample_rate) * 0.1
        result2 = detector.detect_silence(speech, timestamp=6.0)
        assert not result2.is_silent, "Silence should be broken by speech"
        
        # Second silence period (6 seconds)
        silence2 = np.random.randn(sample_rate * 6) * 0.0001
        result3 = detector.detect_silence(silence2, timestamp=7.0)
        assert result3.is_silent, "Should detect second silence period"
