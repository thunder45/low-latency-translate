"""
Quality analysis result data models.

This module defines dataclasses for individual quality analysis results
including clipping, echo, and silence detection.
"""

from dataclasses import dataclass


@dataclass
class ClippingResult:
    """Result of clipping detection analysis."""
    
    percentage: float  # Percentage of clipped samples
    clipped_count: int  # Number of clipped samples
    is_clipping: bool  # Whether clipping exceeds threshold
    
    def __post_init__(self):
        """Validates result values."""
        if self.percentage < 0 or self.percentage > 100:
            raise ValueError('Clipping percentage must be between 0 and 100')
        if self.clipped_count < 0:
            raise ValueError('Clipped count must be non-negative')


@dataclass
class EchoResult:
    """Result of echo detection analysis."""
    
    echo_level_db: float  # Echo level in dB relative to primary signal
    delay_ms: float  # Echo delay in milliseconds
    has_echo: bool  # Whether echo exceeds threshold
    
    def __post_init__(self):
        """Validates result values."""
        if self.delay_ms < 0:
            raise ValueError('Echo delay must be non-negative')


@dataclass
class SilenceResult:
    """Result of silence detection analysis."""
    
    is_silent: bool  # Whether extended silence is detected
    duration_s: float  # Duration of current silence period in seconds
    energy_db: float  # Current audio energy level in dB
    
    def __post_init__(self):
        """Validates result values."""
        if self.duration_s < 0:
            raise ValueError('Silence duration must be non-negative')
