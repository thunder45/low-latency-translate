"""Unit tests for SNRCalculator."""

import numpy as np
import pytest
from audio_quality.analyzers.snr_calculator import SNRCalculator


class TestSNRCalculator:
    """Test suite for SNRCalculator."""
    
    @pytest.fixture
    def calculator(self):
        """Fixture for SNRCalculator instance."""
        return SNRCalculator(window_size=5.0)
    
    def test_snr_calculation_clean_signal(self, calculator):
        """Test SNR calculation with clean signal (expected: >40 dB)."""
        # Generate clean sine wave (high SNR)
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        signal = np.sin(2 * np.pi * frequency * t) * 0.5
        
        snr = calculator.calculate_snr(signal)
        
        assert snr > 40.0, f"Clean signal should have high SNR, got {snr:.2f} dB"
    
    def test_snr_calculation_noisy_signal(self, calculator):
        """Test SNR calculation with noisy signal (expected: 0-20 dB)."""
        # Generate signal with noise (low SNR)
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        signal = np.sin(2 * np.pi * frequency * t) * 0.1
        noise = np.random.normal(0, 0.1, len(signal))
        noisy_signal = signal + noise
        
        snr = calculator.calculate_snr(noisy_signal)
        
        assert 0 < snr < 20.0, f"Noisy signal should have low SNR (0-20 dB), got {snr:.2f} dB"
    
    def test_snr_calculation_very_noisy_signal(self, calculator):
        """Test SNR calculation with very noisy signal."""
        # Generate signal with high noise level
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        signal = np.sin(2 * np.pi * frequency * t) * 0.05
        noise = np.random.normal(0, 0.2, len(signal))
        very_noisy_signal = signal + noise
        
        snr = calculator.calculate_snr(very_noisy_signal)
        
        assert snr < 10.0, f"Very noisy signal should have very low SNR (<10 dB), got {snr:.2f} dB"
    
    def test_snr_calculation_silent_signal(self, calculator):
        """Test SNR calculation with near-silent signal."""
        # Generate very quiet signal
        sample_rate = 16000
        duration = 1.0
        signal = np.random.normal(0, 0.001, int(sample_rate * duration))
        
        snr = calculator.calculate_snr(signal)
        
        # Should handle near-zero signals gracefully
        assert isinstance(snr, float), "SNR should be a float"
        assert not np.isnan(snr), "SNR should not be NaN"
        assert not np.isinf(snr), "SNR should not be infinite"
    
    def test_snr_rolling_average(self, calculator):
        """Test that rolling average is maintained."""
        sample_rate = 16000
        duration = 0.5  # 500ms chunks
        
        # Process multiple chunks
        for i in range(12):  # 6 seconds total
            t = np.linspace(0, duration, int(sample_rate * duration))
            signal = np.sin(2 * np.pi * 440 * t) * 0.5
            snr = calculator.calculate_snr(signal)
        
        # After 6 seconds, rolling average should be populated
        assert len(calculator.signal_history) > 0, "Signal history should be populated"
        assert len(calculator.signal_history) <= 10, "Signal history should not exceed window size"
    
    def test_snr_with_different_amplitudes(self, calculator):
        """Test SNR calculation with different signal amplitudes."""
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Test with different amplitudes
        amplitudes = [0.1, 0.3, 0.5, 0.7, 0.9]
        snr_values = []
        
        for amplitude in amplitudes:
            signal = np.sin(2 * np.pi * frequency * t) * amplitude
            snr = calculator.calculate_snr(signal)
            snr_values.append(snr)
        
        # Higher amplitude should generally result in higher SNR
        assert all(isinstance(snr, float) for snr in snr_values), "All SNR values should be floats"
        assert all(snr > 0 for snr in snr_values), "All SNR values should be positive"
