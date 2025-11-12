"""
Echo Detector.

This module provides echo detection for audio quality validation using
autocorrelation analysis. Detects echo patterns in the 10-500ms delay range
and measures echo level relative to the primary signal.
"""

import numpy as np
from typing import Optional
from audio_quality.models.results import EchoResult


class EchoDetector:
    """
    Detects echo patterns in audio using autocorrelation.
    
    The detector computes autocorrelation of the audio signal and searches
    for peaks in the specified delay range (10-500ms). Echo level is measured
    in dB relative to the primary signal. Includes threshold check to avoid
    false positives.
    
    Optionally downsamples to 8 kHz for faster computation while maintaining
    delay accuracy.
    
    Attributes:
        min_delay_ms: Minimum echo delay to detect in milliseconds
        max_delay_ms: Maximum echo delay to detect in milliseconds
        threshold_db: Echo level threshold in dB (default: -15.0)
        downsample_rate: Target sample rate for downsampling (default: 8000 Hz)
    """
    
    def __init__(
        self,
        min_delay_ms: int = 10,
        max_delay_ms: int = 500,
        threshold_db: float = -15.0,
        downsample_rate: int = 8000
    ):
        """
        Initialize echo detector.
        
        Args:
            min_delay_ms: Minimum echo delay in milliseconds
            max_delay_ms: Maximum echo delay in milliseconds
            threshold_db: Echo level threshold in dB (echo > threshold triggers detection)
            downsample_rate: Target sample rate for downsampling (0 to disable)
        """
        self.min_delay_ms = min_delay_ms
        self.max_delay_ms = max_delay_ms
        self.threshold_db = threshold_db
        self.downsample_rate = downsample_rate
        
    def detect_echo(self, audio_chunk: np.ndarray, sample_rate: int) -> EchoResult:
        """
        Detect echo using autocorrelation.
        
        Algorithm:
        1. Optionally downsample to 8 kHz for faster computation
        2. Compute autocorrelation of audio signal
        3. Search for peaks in delay range (10-500ms)
        4. Measure echo level relative to primary signal
        5. Emit warning if echo > -15 dB
        
        Args:
            audio_chunk: Audio samples as numpy array (normalized -1.0 to 1.0 or int16)
            sample_rate: Sample rate in Hz
            
        Returns:
            EchoResult with echo level, delay, and detection status
            
        Raises:
            ValueError: If audio_chunk is empty or invalid
        """
        if audio_chunk is None or len(audio_chunk) == 0:
            raise ValueError("Audio chunk cannot be empty")
            
        if sample_rate <= 0:
            raise ValueError("Sample rate must be positive")
            
        # Convert to float if needed
        if audio_chunk.dtype == np.int16:
            audio_chunk = audio_chunk.astype(np.float32) / 32768.0
            
        # Downsample if enabled and sample rate is higher than target
        original_sample_rate = sample_rate
        if self.downsample_rate > 0 and sample_rate > self.downsample_rate:
            audio_chunk, sample_rate = self._downsample(audio_chunk, sample_rate)
            
        # Convert delay range to samples
        min_delay_samples = int(self.min_delay_ms * sample_rate / 1000)
        max_delay_samples = int(self.max_delay_ms * sample_rate / 1000)
        
        # Ensure we have enough samples for the delay range
        if len(audio_chunk) < max_delay_samples:
            # Not enough samples to detect echo in this range
            return EchoResult(
                echo_level_db=-100.0,
                delay_ms=0.0,
                has_echo=False
            )
            
        # Compute autocorrelation
        autocorr = np.correlate(audio_chunk, audio_chunk, mode='full')
        
        # Keep only positive lags (second half)
        autocorr = autocorr[len(autocorr) // 2:]
        
        # Normalize by the zero-lag autocorrelation (maximum value)
        if autocorr[0] > 0:
            autocorr = autocorr / autocorr[0]
        else:
            # Signal is completely silent
            return EchoResult(
                echo_level_db=-100.0,
                delay_ms=0.0,
                has_echo=False
            )
            
        # Search for echo peak in delay range
        search_range = autocorr[min_delay_samples:min(max_delay_samples, len(autocorr))]
        
        if len(search_range) == 0:
            # No valid search range
            return EchoResult(
                echo_level_db=-100.0,
                delay_ms=0.0,
                has_echo=False
            )
            
        # Find peak in search range
        # Use threshold to avoid false positives from noise
        peak_threshold = 0.01  # Minimum correlation value to consider
        
        if np.max(search_range) > peak_threshold:
            peak_idx = np.argmax(search_range) + min_delay_samples
            echo_level = autocorr[peak_idx]
            
            # Convert to dB
            if echo_level > 0:
                echo_db = 20 * np.log10(echo_level)
            else:
                echo_db = -100.0
                
            # Convert delay back to milliseconds using original sample rate
            # This ensures delay accuracy even with downsampling
            delay_ms = (peak_idx * 1000.0) / sample_rate
            
            # Adjust delay if we downsampled
            if self.downsample_rate > 0 and original_sample_rate > self.downsample_rate:
                # Delay is already in ms, no adjustment needed
                pass
                
        else:
            # No significant peak found
            echo_db = -100.0
            delay_ms = 0.0
            
        # Determine if echo exceeds threshold
        has_echo = echo_db > self.threshold_db
        
        return EchoResult(
            echo_level_db=echo_db,
            delay_ms=delay_ms,
            has_echo=has_echo
        )
    
    def _downsample(
        self,
        audio: np.ndarray,
        original_rate: int
    ) -> tuple[np.ndarray, int]:
        """
        Downsample audio to target rate for faster computation.
        
        Uses simple decimation (taking every Nth sample). For production use,
        consider using scipy.signal.resample for better quality.
        
        Args:
            audio: Audio samples
            original_rate: Original sample rate in Hz
            
        Returns:
            Tuple of (downsampled_audio, new_sample_rate)
        """
        if self.downsample_rate <= 0 or original_rate <= self.downsample_rate:
            return audio, original_rate
            
        # Calculate decimation factor
        decimation_factor = original_rate // self.downsample_rate
        
        # Decimate by taking every Nth sample
        downsampled = audio[::decimation_factor]
        
        # Calculate actual new sample rate
        new_rate = original_rate // decimation_factor
        
        return downsampled, new_rate
    
    def reset(self):
        """
        Reset detector state.
        
        Currently no state to reset, but provided for consistency with other analyzers.
        """
        pass
