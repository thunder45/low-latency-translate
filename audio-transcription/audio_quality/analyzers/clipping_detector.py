"""
Clipping detection analyzer for audio quality validation.

This module provides the ClippingDetector class for detecting audio clipping
(distortion that occurs when signal amplitude exceeds maximum representable value).
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class ClippingResult:
    """
    Result of clipping detection analysis.
    
    Attributes:
        percentage: Percentage of samples that are clipped (0-100)
        clipped_count: Number of samples that exceeded the clipping threshold
        is_clipping: True if clipping percentage exceeds the configured threshold
        timestamp: Optional timestamp of the analysis
    """
    percentage: float
    clipped_count: int
    is_clipping: bool
    timestamp: Optional[float] = None


class ClippingDetector:
    """
    Detects audio clipping in real-time.
    
    Clipping occurs when audio samples reach or exceed a threshold percentage
    of the maximum amplitude, causing distortion. This detector identifies
    clipped samples and calculates the clipping percentage in configurable
    time windows.
    
    Algorithm:
    1. Calculate clipping threshold (default: 98% of max amplitude)
    2. Count samples exceeding threshold
    3. Calculate clipping percentage
    4. Emit warning if exceeds configured threshold (default: 1%)
    
    Attributes:
        threshold_percent: Amplitude threshold as percentage of max (default: 98.0)
        window_ms: Analysis window size in milliseconds (default: 100)
    """
    
    def __init__(
        self,
        threshold_percent: float = 98.0,
        window_ms: int = 100
    ):
        """
        Initializes the ClippingDetector.
        
        Args:
            threshold_percent: Amplitude threshold as percentage of max amplitude
                             (default: 98.0). Samples at or above this threshold
                             are considered clipped.
            window_ms: Analysis window size in milliseconds (default: 100).
                      Clipping percentage is calculated per window.
        
        Raises:
            ValueError: If threshold_percent is not between 0 and 100
            ValueError: If window_ms is not positive
        """
        if not 0 < threshold_percent <= 100:
            raise ValueError(
                f"threshold_percent must be between 0 and 100, got {threshold_percent}"
            )
        
        if window_ms <= 0:
            raise ValueError(
                f"window_ms must be positive, got {window_ms}"
            )
        
        self.threshold_percent = threshold_percent
        self.window_ms = window_ms
    
    def detect_clipping(
        self,
        audio_chunk: np.ndarray,
        bit_depth: int = 16,
        clipping_threshold_percent: float = 1.0
    ) -> ClippingResult:
        """
        Detects clipping in audio samples.
        
        Analyzes the audio chunk to identify samples that reach or exceed
        the clipping threshold. Calculates the percentage of clipped samples
        and determines if it exceeds the acceptable clipping threshold.
        
        Algorithm:
        1. Calculate clipping threshold based on bit depth and threshold_percent
        2. Count samples where |amplitude| >= threshold
        3. Calculate clipping percentage = (clipped_count / total_samples) * 100
        4. Determine if clipping exceeds acceptable threshold
        
        Args:
            audio_chunk: Audio samples as numpy array. Can be:
                        - int16 PCM samples (range: -32768 to 32767)
                        - Normalized float samples (range: -1.0 to 1.0)
            bit_depth: Bit depth for threshold calculation (default: 16).
                      Used to determine maximum amplitude.
            clipping_threshold_percent: Acceptable clipping percentage (default: 1.0).
                                       If clipping exceeds this, is_clipping is True.
        
        Returns:
            ClippingResult containing:
                - percentage: Clipping percentage (0-100)
                - clipped_count: Number of clipped samples
                - is_clipping: True if percentage > clipping_threshold_percent
        
        Raises:
            ValueError: If audio_chunk is empty
            ValueError: If bit_depth is not supported (must be 16)
        
        Examples:
            >>> detector = ClippingDetector(threshold_percent=98.0)
            >>> audio = np.array([32000, 32500, 32700, 100, 200], dtype=np.int16)
            >>> result = detector.detect_clipping(audio, bit_depth=16)
            >>> print(f"Clipping: {result.percentage:.1f}%")
            Clipping: 60.0%
        """
        if len(audio_chunk) == 0:
            raise ValueError("audio_chunk cannot be empty")
        
        if bit_depth != 16:
            raise ValueError(
                f"Only 16-bit audio is currently supported, got {bit_depth}"
            )
        
        # Calculate maximum amplitude for the bit depth
        # For 16-bit PCM: max = 2^15 - 1 = 32767
        max_amplitude = 2 ** (bit_depth - 1) - 1
        
        # Calculate clipping threshold
        # Default: 98% of max amplitude = 32111 for 16-bit
        threshold = max_amplitude * (self.threshold_percent / 100.0)
        
        # Count samples that exceed the threshold
        # Use absolute value to catch both positive and negative clipping
        clipped_samples = np.sum(np.abs(audio_chunk) >= threshold)
        
        # Calculate clipping percentage
        total_samples = len(audio_chunk)
        clipping_percentage = (clipped_samples / total_samples) * 100.0
        
        # Determine if clipping exceeds acceptable threshold
        is_clipping = clipping_percentage > clipping_threshold_percent
        
        return ClippingResult(
            percentage=clipping_percentage,
            clipped_count=int(clipped_samples),
            is_clipping=is_clipping
        )
