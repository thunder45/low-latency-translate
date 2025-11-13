"""
Processing result data model.

Represents the complete output of audio dynamics processing and speech synthesis.
"""

from dataclasses import dataclass
from typing import Optional

from .audio_dynamics import AudioDynamics


@dataclass
class ProcessingResult:
    """
    Result of complete audio dynamics processing and synthesis pipeline.
    
    Attributes:
        audio_stream: Synthesized audio data in bytes
        dynamics: Detected audio dynamics (volume and rate)
        ssml_text: Generated SSML markup (or plain text if fallback used)
        processing_time_ms: Total processing time in milliseconds
        correlation_id: Identifier linking this result to input
        fallback_used: True if plain text fallback was used instead of SSML
        volume_detection_ms: Time spent on volume detection
        rate_detection_ms: Time spent on rate detection
        ssml_generation_ms: Time spent on SSML generation
        polly_synthesis_ms: Time spent on Polly synthesis
    """
    
    audio_stream: bytes
    dynamics: AudioDynamics
    ssml_text: str
    processing_time_ms: int
    correlation_id: str
    fallback_used: bool
    
    # Timing breakdown
    volume_detection_ms: int
    rate_detection_ms: int
    ssml_generation_ms: int
    polly_synthesis_ms: int
    
    def __post_init__(self):
        """Validate processing result data."""
        if not isinstance(self.audio_stream, bytes):
            raise ValueError(f"audio_stream must be bytes, got {type(self.audio_stream)}")
        
        if not isinstance(self.dynamics, AudioDynamics):
            raise ValueError(f"dynamics must be AudioDynamics, got {type(self.dynamics)}")
        
        if not self.ssml_text or not isinstance(self.ssml_text, str):
            raise ValueError("ssml_text must be non-empty string")
        
        if not self.correlation_id or not isinstance(self.correlation_id, str):
            raise ValueError("correlation_id must be non-empty string")
        
        # Validate timing values are non-negative
        timing_fields = [
            'processing_time_ms',
            'volume_detection_ms',
            'rate_detection_ms',
            'ssml_generation_ms',
            'polly_synthesis_ms'
        ]
        for field_name in timing_fields:
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be non-negative integer, got {value}")
