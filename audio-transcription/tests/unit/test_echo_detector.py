"""Unit tests for EchoDetector."""

import numpy as np
import pytest
from audio_quality.analyzers.echo_detector import EchoDetector


def generate_speech_like_signal(duration: float, sample_rate: int) -> np.ndarray:
    """
    Generate a more realistic speech-like signal instead of pure sine wave.
    
    Uses filtered noise with amplitude modulation to simulate speech characteristics
    while avoiding the strong periodicity of pure tones.
    
    Args:
        duration: Duration in seconds
        sample_rate: Sample rate in Hz
        
    Returns:
        Speech-like audio signal
    """
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Start with white noise (no periodicity)
    signal = np.random.normal(0, 0.5, len(t))
    
    # Add tonal components (balanced with noise)
    signal += 0.6 * np.sin(2 * np.pi * 220 * t)  # A3 note
    signal += 0.4 * np.sin(2 * np.pi * 440 * t)  # A4 note
    signal += 0.2 * np.sin(2 * np.pi * 660 * t)  # E5 note
    
    # Add amplitude modulation to simulate speech envelope
    envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 3 * t)  # 3 Hz modulation
    signal = signal * envelope
    
    # Normalize to prevent clipping
    signal = signal / np.max(np.abs(signal)) * 0.8
    
    return signal


class TestEchoDetector:
    """Test suite for EchoDetector."""
    
    @pytest.fixture
    def detector(self):
        """Fixture for EchoDetector instance with realistic delay range."""
        # Use 40ms minimum to avoid detecting harmonic peaks as echoes
        # Real-world echoes are typically 40ms+ (corresponding to ~13 feet distance)
        return EchoDetector(min_delay_ms=40, max_delay_ms=500)
    
    def test_echo_detection_no_echo(self, detector):
        """Test echo detection with clean signal (no echo)."""
        # Generate clean speech-like signal without echo
        sample_rate = 16000
        duration = 1.0
        signal = generate_speech_like_signal(duration, sample_rate)
        
        result = detector.detect_echo(signal, sample_rate)
        
        assert not result.has_echo, "Should not detect echo in clean signal"
    
    def test_echo_detection_moderate_room_echo(self, detector):
        """Test detection of moderate room echo (100ms delay, 40% amplitude)."""
        # Realistic scenario: Room with moderate echo (hard surfaces, no treatment)
        sample_rate = 16000
        duration = 1.0
        signal = generate_speech_like_signal(duration, sample_rate)
        
        # Add echo at 100ms delay with 40% amplitude
        delay_samples = int(0.1 * sample_rate)  # 100ms
        echo = np.zeros_like(signal)
        echo[delay_samples:] = signal[:-delay_samples] * 0.4
        signal_with_echo = signal + echo
        
        result = detector.detect_echo(signal_with_echo, sample_rate)
        
        assert result.has_echo, "Should detect moderate room echo"
        # Allow wider tolerance for delay measurement (±30ms)
        assert 70 < result.delay_ms < 130, f"Should detect ~100ms delay, got {result.delay_ms:.2f}ms"
    
    def test_echo_detection_weak_echo(self, detector):
        """Test detection of weak echo from well-treated room (5% amplitude)."""
        # Realistic scenario: Room with acoustic treatment or distant echo
        sample_rate = 16000
        duration = 1.0
        signal = generate_speech_like_signal(duration, sample_rate)
        
        delay_samples = int(0.1 * sample_rate)
        echo = np.zeros_like(signal)
        echo[delay_samples:] = signal[:-delay_samples] * 0.05  # Very weak echo
        signal_with_echo = signal + echo
        
        result = detector.detect_echo(signal_with_echo, sample_rate)
        
        # Weak echo should not trigger detection (below threshold)
        assert not result.has_echo, "Should not detect very weak echo"
    
    def test_echo_detection_strong_feedback(self, detector):
        """Test detection of strong echo from speaker feedback (50% amplitude)."""
        # Realistic scenario: Microphone picking up speaker output (feedback loop)
        sample_rate = 16000
        duration = 1.0
        signal = generate_speech_like_signal(duration, sample_rate)
        
        delay_samples = int(0.15 * sample_rate)  # 150ms (typical speaker-to-mic delay)
        echo = np.zeros_like(signal)
        echo[delay_samples:] = signal[:-delay_samples] * 0.5  # Strong echo
        signal_with_echo = signal + echo
        
        result = detector.detect_echo(signal_with_echo, sample_rate)
        
        assert result.has_echo, "Should detect strong feedback echo"
        assert result.echo_level_db > -10.0, f"Strong echo should have high level, got {result.echo_level_db:.2f} dB"
