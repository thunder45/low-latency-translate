"""
Audio processor for applying lightweight audio enhancements.

This module provides the AudioProcessor class for applying optional
audio processing such as high-pass filtering and noise gating.
"""

import numpy as np
from scipy.signal import butter, filtfilt

from audio_quality.models.quality_config import QualityConfig


class AudioProcessor:
    """
    Applies lightweight audio processing.
    
    This processor applies optional audio enhancements including:
    - High-pass filter to remove low-frequency noise
    - Noise gate to suppress background noise
    
    Processing is designed to be lightweight with minimal latency impact.
    """
    
    def __init__(self, config: QualityConfig):
        """
        Initializes the AudioProcessor.
        
        Args:
            config: Quality configuration with processing options
        """
        self.config = config
        self.high_pass_filter = None
        self.noise_gate = None
        
    def process(self, audio_chunk: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Applies optional audio enhancements.
        
        Processing steps:
        1. High-pass filter (remove low-frequency noise < 80 Hz)
        2. Noise gate (suppress background noise below threshold)
        
        Args:
            audio_chunk: Input audio samples as numpy array
            sample_rate: Sample rate in Hz
            
        Returns:
            Processed audio samples as numpy array
        """
        processed = audio_chunk.copy()
        
        # Apply high-pass filter if enabled
        if self.config.enable_high_pass:
            processed = self._apply_high_pass(processed, sample_rate)
            
        # Apply noise gate if enabled
        if self.config.enable_noise_gate:
            processed = self._apply_noise_gate(processed)
            
        return processed
        
    def _apply_high_pass(
        self, 
        audio: np.ndarray, 
        sample_rate: int, 
        cutoff: float = 80.0
    ) -> np.ndarray:
        """
        Applies high-pass filter to remove low-frequency noise.
        
        Uses a 4th-order Butterworth filter with 80 Hz cutoff frequency
        to remove low-frequency rumble and noise while preserving speech.
        
        Args:
            audio: Input audio samples
            sample_rate: Sample rate in Hz
            cutoff: Cutoff frequency in Hz (default: 80.0)
            
        Returns:
            Filtered audio samples
        """
        # Calculate normalized cutoff frequency
        nyquist = sample_rate / 2.0
        normalized_cutoff = cutoff / nyquist
        
        # Design 4th-order Butterworth high-pass filter
        b, a = butter(4, normalized_cutoff, btype='high')
        
        # Apply filter using zero-phase filtering
        filtered = filtfilt(b, a, audio)
        
        return filtered
        
    def _apply_noise_gate(
        self, 
        audio: np.ndarray, 
        threshold_db: float = -40.0
    ) -> np.ndarray:
        """
        Applies noise gate to suppress background noise.
        
        When audio energy falls below the threshold, the signal is
        attenuated by 20 dB to suppress background noise.
        
        Args:
            audio: Input audio samples
            threshold_db: Energy threshold in dB (default: -40.0)
            
        Returns:
            Gated audio samples
        """
        # Calculate RMS energy
        rms = np.sqrt(np.mean(audio ** 2))
        
        # Convert to dB
        energy_db = 20 * np.log10(rms) if rms > 0 else -100.0
        
        # Apply gate
        if energy_db < threshold_db:
            # Attenuate by 20 dB (multiply by 0.1)
            return audio * 0.1
        
        return audio

