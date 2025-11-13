"""
Audio dynamics data model combining volume and rate results.

Represents the complete audio dynamics profile extracted from speaker audio.
"""

from dataclasses import dataclass
from typing import Dict

from .volume_result import VolumeResult
from .rate_result import RateResult


@dataclass
class AudioDynamics:
    """
    Combined audio dynamics from volume and rate detection.
    
    Attributes:
        volume: Volume detection result
        rate: Speaking rate detection result
        correlation_id: Identifier linking dynamics to audio/text
    """
    
    volume: VolumeResult
    rate: RateResult
    correlation_id: str
    
    def __post_init__(self):
        """Validate audio dynamics data."""
        if not isinstance(self.volume, VolumeResult):
            raise ValueError(f"volume must be VolumeResult, got {type(self.volume)}")
        
        if not isinstance(self.rate, RateResult):
            raise ValueError(f"rate must be RateResult, got {type(self.rate)}")
        
        if not self.correlation_id or not isinstance(self.correlation_id, str):
            raise ValueError("correlation_id must be non-empty string")
    
    def to_ssml_attributes(self) -> Dict[str, str]:
        """
        Convert audio dynamics to SSML prosody attributes.
        
        Returns:
            Dictionary with 'volume' and 'rate' SSML attribute values
        """
        return {
            'volume': self.volume.to_ssml_attribute(),
            'rate': self.rate.to_ssml_attribute()
        }
