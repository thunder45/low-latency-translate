"""
Quality configuration data model.

This module defines the QualityConfig dataclass for configuring
audio quality validation parameters.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class QualityConfig:
    """Configuration for audio quality validation."""
    
    # SNR thresholds
    snr_threshold_db: float = 20.0  # Minimum acceptable SNR
    snr_update_interval_ms: int = 500
    snr_window_size_s: float = 5.0
    
    # Clipping thresholds
    clipping_threshold_percent: float = 1.0  # Max acceptable clipping
    clipping_amplitude_percent: float = 98.0  # Amplitude threshold
    clipping_window_ms: int = 100
    
    # Echo detection
    echo_threshold_db: float = -15.0  # Echo level threshold
    echo_min_delay_ms: int = 10
    echo_max_delay_ms: int = 500
    echo_update_interval_s: float = 1.0
    
    # Silence detection
    silence_threshold_db: float = -50.0
    silence_duration_threshold_s: float = 5.0
    
    # Processing options
    enable_high_pass: bool = False
    enable_noise_gate: bool = False
    
    def validate(self) -> List[str]:
        """
        Validates configuration parameters.
        
        Returns:
            List of error messages. Empty list if configuration is valid.
        """
        errors = []
        
        if not (10.0 <= self.snr_threshold_db <= 40.0):
            errors.append('SNR threshold must be between 10 and 40 dB')
            
        if not (0.1 <= self.clipping_threshold_percent <= 10.0):
            errors.append('Clipping threshold must be between 0.1% and 10%')
            
        if self.snr_update_interval_ms <= 0:
            errors.append('SNR update interval must be positive')
            
        if self.snr_window_size_s <= 0:
            errors.append('SNR window size must be positive')
            
        if not (90.0 <= self.clipping_amplitude_percent <= 100.0):
            errors.append('Clipping amplitude threshold must be between 90% and 100%')
            
        if self.clipping_window_ms <= 0:
            errors.append('Clipping window must be positive')
            
        if not (-30.0 <= self.echo_threshold_db <= 0.0):
            errors.append('Echo threshold must be between -30 and 0 dB')
            
        if self.echo_min_delay_ms <= 0 or self.echo_max_delay_ms <= 0:
            errors.append('Echo delay range must be positive')
            
        if self.echo_min_delay_ms >= self.echo_max_delay_ms:
            errors.append('Echo min delay must be less than max delay')
            
        if self.echo_update_interval_s <= 0:
            errors.append('Echo update interval must be positive')
            
        if not (-60.0 <= self.silence_threshold_db <= -30.0):
            errors.append('Silence threshold must be between -60 and -30 dB')
            
        if self.silence_duration_threshold_s <= 0:
            errors.append('Silence duration threshold must be positive')
            
        return errors
