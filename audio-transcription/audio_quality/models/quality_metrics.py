"""
Quality metrics data model.

This module defines the QualityMetrics dataclass for aggregating
all audio quality measurements for a single analysis window.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass
class QualityMetrics:
    """Audio quality metrics for a single analysis window."""
    
    timestamp: float
    stream_id: str
    
    # SNR metrics
    snr_db: float
    snr_rolling_avg: float
    
    # Clipping metrics
    clipping_percentage: float
    clipped_sample_count: int
    is_clipping: bool
    
    # Echo metrics
    echo_level_db: float
    echo_delay_ms: float
    has_echo: bool
    
    # Silence metrics
    is_silent: bool
    silence_duration_s: float
    energy_db: float
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Converts metrics to dictionary for serialization.
        
        Returns:
            Dictionary representation of metrics.
        """
        return asdict(self)
    
    def __post_init__(self):
        """Validates metric values."""
        if self.timestamp < 0:
            raise ValueError('Timestamp must be non-negative')
        
        if not self.stream_id:
            raise ValueError('Stream ID must not be empty')
        
        if self.clipping_percentage < 0 or self.clipping_percentage > 100:
            raise ValueError('Clipping percentage must be between 0 and 100')
        
        if self.clipped_sample_count < 0:
            raise ValueError('Clipped sample count must be non-negative')
        
        if self.echo_delay_ms < 0:
            raise ValueError('Echo delay must be non-negative')
        
        if self.silence_duration_s < 0:
            raise ValueError('Silence duration must be non-negative')
