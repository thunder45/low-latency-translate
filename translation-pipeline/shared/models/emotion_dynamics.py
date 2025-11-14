"""Emotion dynamics data model."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class EmotionDynamics:
    """
    Represents detected emotion and speaking dynamics from audio analysis.
    
    Attributes:
        emotion: Detected emotion type (e.g., "happy", "angry", "sad", "neutral")
        intensity: Emotion intensity from 0.0 to 1.0
        rate_wpm: Speaking rate in words per minute
        volume_level: Volume level ("whisper", "soft", "normal", "loud")
    """
    emotion: str
    intensity: float
    rate_wpm: int
    volume_level: str
    
    def __post_init__(self):
        """Validate emotion dynamics values."""
        if not 0.0 <= self.intensity <= 1.0:
            raise ValueError(f"Intensity must be between 0.0 and 1.0, got {self.intensity}")
        
        if self.rate_wpm < 0:
            raise ValueError(f"Rate WPM must be positive, got {self.rate_wpm}")
        
        valid_volumes = ["whisper", "soft", "normal", "loud"]
        if self.volume_level not in valid_volumes:
            raise ValueError(
                f"Volume level must be one of {valid_volumes}, got {self.volume_level}"
            )
