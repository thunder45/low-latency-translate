"""
Speaking rate detection result data model.

Represents the output of speaking rate analysis including
classification and words-per-minute measurement.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


RateClassification = Literal['very_slow', 'slow', 'medium', 'fast', 'very_fast']


@dataclass
class RateResult:
    """
    Result of speaking rate detection analysis.
    
    Attributes:
        classification: Rate classification (very_slow, slow, medium, fast, very_fast)
        wpm: Words per minute calculated from onset detection
        onset_count: Number of detected speech onsets
        timestamp: When the detection was performed
    """
    
    classification: RateClassification
    wpm: float
    onset_count: int
    timestamp: datetime
    
    def __post_init__(self):
        """Validate rate result data."""
        valid_classifications = {'very_slow', 'slow', 'medium', 'fast', 'very_fast'}
        if self.classification not in valid_classifications:
            raise ValueError(
                f"Invalid rate classification: {self.classification}. "
                f"Must be one of {valid_classifications}"
            )
        
        if not isinstance(self.wpm, (int, float)) or self.wpm < 0:
            raise ValueError(f"wpm must be non-negative numeric, got {self.wpm}")
        
        if not isinstance(self.onset_count, int) or self.onset_count < 0:
            raise ValueError(f"onset_count must be non-negative integer, got {self.onset_count}")
    
    def to_ssml_attribute(self) -> str:
        """
        Convert rate classification to SSML prosody rate attribute.
        
        Returns:
            SSML rate attribute value (x-slow, slow, medium, fast, x-fast)
        """
        mapping = {
            'very_slow': 'x-slow',
            'slow': 'slow',
            'medium': 'medium',
            'fast': 'fast',
            'very_fast': 'x-fast'
        }
        return mapping[self.classification]
