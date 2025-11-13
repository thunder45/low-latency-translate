"""Unit tests for ClippingDetector."""

import numpy as np
import pytest
from audio_quality.analyzers.clipping_detector import ClippingDetector


class TestClippingDetector:
    """Test suite for ClippingDetector."""
    
    @pytest.fixture
    def detector(self):
        """Fixture for ClippingDetector instance."""
        return ClippingDetector(threshold_percent=98.0, window_ms=100)
    
    def test_clipping_detection_with_clipped_signal(self, detector):
        """Test clipping detection with clipped signal."""
        # Generate clipped signal (samples at max amplitude)
        # For 16-bit PCM, max amplitude is 32767
        signal = np.array([32000, 32500, 32700, 100, 200, -32700, -32500], dtype=np.int16)
        
        result = detector.detect_clipping(signal, bit_depth=16)
        
        assert result.is_clipping, "Should detect clipping"
        assert result.clipped_count == 4, f"Should count 4 clipped samples, got {result.clipped_count}"
        assert result.percentage > 50.0, f"Clipping percentage should be high, got {result.percentage:.2f}%"
    
    def test_clipping_detection_no_clipping(self, detector):
        """Test clipping detection with clean signal (no clipping)."""
        # Generate clean signal well below clipping threshold
        signal = np.array([1000, 2000, -1500, 3000, -2500, 1800], dtype=np.int16)
        
        result = detector.detect_clipping(signal, bit_depth=16)
        
        assert not result.is_clipping, "Should not detect clipping in clean signal"
        assert result.clipped_count == 0, f"Should count 0 clipped samples, got {result.clipped_count}"
        assert result.percentage == 0.0, f"Clipping percentage should be 0%, got {result.percentage:.2f}%"
    
    def test_clipping_percentage_calculation(self, detector):
        """Test clipping percentage calculation accuracy."""
        # Create signal with exactly 10% clipping
        total_samples = 1000
        clipped_samples = 100
        
        signal = np.zeros(total_samples, dtype=np.int16)
        # Set 100 samples to clipping level (98% of max amplitude)
        clipping_threshold = int(32767 * 0.98)
        signal[:clipped_samples] = clipping_threshold
        
        result = detector.detect_clipping(signal, bit_depth=16)
        
        assert result.clipped_count == clipped_samples, f"Should count {clipped_samples} clipped samples"
        assert abs(result.percentage - 10.0) < 0.1, f"Clipping percentage should be ~10%, got {result.percentage:.2f}%"
    
    def test_clipping_threshold_boundary(self, detector):
        """Test clipping detection at threshold boundary."""
        # Test samples just below and at threshold
        max_amplitude = 32767
        threshold = int(max_amplitude * 0.98)
        
        # Just below threshold
        signal_below = np.array([threshold - 1, threshold - 2, threshold - 3], dtype=np.int16)
        result_below = detector.detect_clipping(signal_below, bit_depth=16)
        assert result_below.clipped_count == 0, "Should not detect clipping just below threshold"
        
        # At threshold
        signal_at = np.array([threshold, threshold, threshold], dtype=np.int16)
        result_at = detector.detect_clipping(signal_at, bit_depth=16)
        assert result_at.clipped_count == 3, "Should detect clipping at threshold"
    
    def test_clipping_with_negative_values(self, detector):
        """Test clipping detection with negative amplitude values."""
        # Generate signal with negative clipping
        signal = np.array([-32700, -32600, -32750, 100, 200], dtype=np.int16)
        
        result = detector.detect_clipping(signal, bit_depth=16)
        
        assert result.is_clipping, "Should detect negative clipping"
        assert result.clipped_count == 3, f"Should count 3 clipped samples, got {result.clipped_count}"
    
    def test_clipping_with_mixed_positive_negative(self, detector):
        """Test clipping detection with both positive and negative clipping."""
        # Generate signal with both positive and negative clipping
        signal = np.array([32700, -32700, 32650, -32650, 100, 200], dtype=np.int16)
        
        result = detector.detect_clipping(signal, bit_depth=16)
        
        assert result.is_clipping, "Should detect clipping"
        assert result.clipped_count == 4, f"Should count 4 clipped samples (2 positive, 2 negative), got {result.clipped_count}"
    
    def test_clipping_threshold_percent_configuration(self):
        """Test different clipping threshold percentages."""
        signal = np.array([32000, 32500, 32700, 100, 200], dtype=np.int16)
        
        # Test with 95% threshold (more sensitive)
        detector_95 = ClippingDetector(threshold_percent=95.0)
        result_95 = detector_95.detect_clipping(signal, bit_depth=16)
        
        # Test with 99% threshold (less sensitive)
        detector_99 = ClippingDetector(threshold_percent=99.0)
        result_99 = detector_99.detect_clipping(signal, bit_depth=16)
        
        # 95% threshold should detect more clipping than 99%
        assert result_95.clipped_count >= result_99.clipped_count, \
            "Lower threshold should detect more or equal clipping"
    
    def test_clipping_with_normalized_float_input(self, detector):
        """Test clipping detection with normalized float input (-1.0 to 1.0)."""
        # Generate normalized signal with clipping
        signal_float = np.array([0.99, 0.995, 1.0, 0.1, -0.99, -1.0], dtype=np.float32)
        
        # Convert to int16 for testing
        signal_int16 = (signal_float * 32767).astype(np.int16)
        
        result = detector.detect_clipping(signal_int16, bit_depth=16)
        
        assert result.is_clipping, "Should detect clipping in normalized signal"
        assert result.clipped_count > 0, "Should count clipped samples"
    
    def test_clipping_empty_signal(self, detector):
        """Test clipping detection with empty signal."""
        signal = np.array([], dtype=np.int16)
        
        result = detector.detect_clipping(signal, bit_depth=16)
        
        assert result.clipped_count == 0, "Empty signal should have 0 clipped samples"
        assert result.percentage == 0.0, "Empty signal should have 0% clipping"
        assert not result.is_clipping, "Empty signal should not be clipping"
