"""
SNR (Signal-to-Noise Ratio) Calculator.

This module provides SNR calculation for audio quality validation.
Maintains a rolling window of SNR values and updates at 500ms intervals.
"""

import numpy as np
from collections import deque
from typing import Optional


class SNRCalculator:
    """
    Calculates Signal-to-Noise Ratio for audio streams.
    
    The calculator estimates noise floor from silent frames and calculates
    signal RMS from active frames. Maintains a rolling window of SNR values
    for temporal analysis.
    
    Attributes:
        window_size: Rolling window size in seconds (default: 5.0)
        signal_history: Deque storing recent SNR measurements
    """
    
    def __init__(self, window_size: float = 5.0):
        """
        Initialize SNR calculator.
        
        Args:
            window_size: Size of rolling window in seconds for averaging
        """
        self.window_size = window_size
        # Store 10 measurements (5 seconds / 0.5 second intervals)
        self.signal_history = deque(maxlen=int(window_size * 2))
        
    def calculate_snr(self, audio_chunk: np.ndarray) -> float:
        """
        Calculate SNR in decibels.
        
        Algorithm:
        1. Estimate noise floor from silent frames (RMS < -40 dB)
        2. Calculate signal RMS from active frames
        3. SNR = 20 * log10(signal_rms / noise_rms)
        
        Args:
            audio_chunk: Audio samples as numpy array (normalized -1.0 to 1.0 or int16)
            
        Returns:
            SNR in decibels
            
        Raises:
            ValueError: If audio_chunk is empty or invalid
        """
        if audio_chunk is None or len(audio_chunk) == 0:
            raise ValueError("Audio chunk cannot be empty")
            
        # Convert to float if needed
        if audio_chunk.dtype == np.int16:
            audio_chunk = audio_chunk.astype(np.float32) / 32768.0
            
        # Calculate overall RMS
        rms = np.sqrt(np.mean(audio_chunk ** 2))
        
        # Estimate noise from low-energy frames
        # Threshold: -40 dB = 0.01 in normalized amplitude
        noise_threshold = 0.01
        noise_frames = audio_chunk[np.abs(audio_chunk) < noise_threshold]
        
        if len(noise_frames) > 0:
            noise_rms = np.sqrt(np.mean(noise_frames ** 2))
        else:
            # If no quiet frames, use very small value to avoid division by zero
            noise_rms = 1e-10
            
        # Avoid division by zero
        if noise_rms == 0:
            noise_rms = 1e-10
            
        # Calculate SNR in dB
        if rms > 0:
            snr_db = 20 * np.log10(rms / noise_rms)
        else:
            # If signal is completely silent, return very low SNR
            snr_db = -100.0
            
        # Cap at reasonable maximum to avoid infinity
        snr_db = min(snr_db, 100.0)
        
        # Add to rolling window
        self.signal_history.append(snr_db)
        
        return snr_db
    
    def get_rolling_average(self) -> Optional[float]:
        """
        Get rolling average of SNR values over the window.
        
        Returns:
            Average SNR in dB over the rolling window, or None if no history
        """
        if len(self.signal_history) == 0:
            return None
            
        return float(np.mean(self.signal_history))
    
    def reset(self):
        """Reset the rolling window history."""
        self.signal_history.clear()
