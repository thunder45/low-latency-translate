"""
Volume detection result data model.

Represents the output of volume detection analysis including
classification level and decibel measurement.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


VolumeLevel = Literal['loud', 'medium', 'soft', 'whisper']


@dataclass
class VolumeResult:
    """
    Result of volume detection analysis.
    
    Attributes:
        level: Volume classification (loud, medium, soft, whisper)
        db_value: Decibel value from RMS energy calculation
        timestamp: When the detection was performed
    """
    
    level: VolumeLevel
    db_value: float
    timestamp: datetime
    
    def __post_init__(self):
        """Validate volume result data."""
        valid_levels = {'loud', 'medium', 'soft', 'whisper'}
        if self.level not in valid_levels:
            raise ValueError(f"Invalid volume level: {self.level}. Must be one of {valid_levels}")
        
        if not isinstance(self.db_value, (int, float)):
            raise ValueError(f"db_value must be numeric, got {type(self.db_value)}")
    
    def to_ssml_attribute(self) -> str:
        """
        Convert volume level to SSML prosody volume attribute.
        
        Returns:
            SSML volume attribute value (x-loud, medium, soft, x-soft)
        """
        mapping = {
            'loud': 'x-loud',
            'medium': 'medium',
            'soft': 'soft',
            'whisper': 'x-soft'
        }
        return mapping[self.level]
