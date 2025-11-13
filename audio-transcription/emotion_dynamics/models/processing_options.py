"""
Processing options configuration data model.

Defines configurable options for audio dynamics detection and speech synthesis.
"""

from dataclasses import dataclass, field


@dataclass
class ProcessingOptions:
    """
    Configuration options for audio dynamics processing and synthesis.
    
    Attributes:
        voice_id: Amazon Polly voice ID (default: Joanna)
        enable_ssml: Enable SSML generation (default: True)
        sample_rate: Audio sample rate for Polly output (default: 24000)
        output_format: Audio output format (default: mp3)
        enable_volume_detection: Enable volume detection (default: True)
        enable_rate_detection: Enable speaking rate detection (default: True)
    """
    
    voice_id: str = 'Joanna'
    enable_ssml: bool = True
    sample_rate: str = '24000'
    output_format: str = 'mp3'
    enable_volume_detection: bool = True
    enable_rate_detection: bool = True
    
    def __post_init__(self):
        """Validate processing options."""
        # Validate voice_id is non-empty
        if not self.voice_id or not isinstance(self.voice_id, str):
            raise ValueError("voice_id must be non-empty string")
        
        # Validate sample_rate
        valid_sample_rates = {'8000', '16000', '22050', '24000'}
        if self.sample_rate not in valid_sample_rates:
            raise ValueError(
                f"sample_rate must be one of {valid_sample_rates}, got {self.sample_rate}"
            )
        
        # Validate output_format
        valid_formats = {'mp3', 'ogg_vorbis', 'pcm'}
        if self.output_format not in valid_formats:
            raise ValueError(
                f"output_format must be one of {valid_formats}, got {self.output_format}"
            )
