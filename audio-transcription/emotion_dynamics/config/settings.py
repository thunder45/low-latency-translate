"""
Configuration settings for emotion dynamics module.

Loads configuration from environment variables with sensible defaults.
"""

import os
from typing import Optional


class Settings:
    """
    Configuration settings for emotion dynamics detection and SSML generation.
    
    All settings are loaded from environment variables with defaults.
    """
    
    def __init__(self):
        """Initialize settings from environment variables."""
        # AWS Configuration
        self.aws_region: str = os.getenv('AWS_REGION', 'us-east-1')
        
        # Polly Configuration
        self.voice_id: str = os.getenv('VOICE_ID', 'Joanna')
        self.sample_rate: str = os.getenv('SAMPLE_RATE', '24000')
        self.output_format: str = os.getenv('OUTPUT_FORMAT', 'mp3')
        
        # Feature Flags
        self.enable_ssml: bool = self._parse_bool(os.getenv('ENABLE_SSML', 'true'))
        self.enable_volume_detection: bool = self._parse_bool(
            os.getenv('ENABLE_VOLUME_DETECTION', 'true')
        )
        self.enable_rate_detection: bool = self._parse_bool(
            os.getenv('ENABLE_RATE_DETECTION', 'true')
        )
        
        # Retry Configuration
        self.max_retries: int = int(os.getenv('MAX_RETRIES', '3'))
        self.retry_base_delay: float = float(os.getenv('RETRY_BASE_DELAY', '0.1'))
        self.retry_max_delay: float = float(os.getenv('RETRY_MAX_DELAY', '2.0'))
        
        # Logging Configuration
        self.log_level: str = os.getenv('LOG_LEVEL', 'INFO')
        
        # Audio Processing Configuration
        self.audio_sample_rate: int = int(os.getenv('AUDIO_SAMPLE_RATE', '16000'))
        
        # Volume Detection Thresholds (in dB)
        self.volume_loud_threshold: float = float(
            os.getenv('VOLUME_LOUD_THRESHOLD', '-10.0')
        )
        self.volume_medium_threshold: float = float(
            os.getenv('VOLUME_MEDIUM_THRESHOLD', '-20.0')
        )
        self.volume_soft_threshold: float = float(
            os.getenv('VOLUME_SOFT_THRESHOLD', '-30.0')
        )
        
        # Speaking Rate Thresholds (in WPM)
        self.rate_very_slow_threshold: int = int(
            os.getenv('RATE_VERY_SLOW_THRESHOLD', '100')
        )
        self.rate_slow_threshold: int = int(
            os.getenv('RATE_SLOW_THRESHOLD', '130')
        )
        self.rate_medium_threshold: int = int(
            os.getenv('RATE_MEDIUM_THRESHOLD', '160')
        )
        self.rate_fast_threshold: int = int(
            os.getenv('RATE_FAST_THRESHOLD', '190')
        )
        
        # Validate configuration
        self._validate()
    
    def _parse_bool(self, value: str) -> bool:
        """
        Parse boolean value from string.
        
        Args:
            value: String value to parse
            
        Returns:
            Boolean value
        """
        return value.lower() in ('true', '1', 'yes', 'on')
    
    def _validate(self):
        """Validate configuration values."""
        # Validate sample rate
        valid_sample_rates = {'8000', '16000', '22050', '24000'}
        if self.sample_rate not in valid_sample_rates:
            raise ValueError(
                f"Invalid SAMPLE_RATE: {self.sample_rate}. "
                f"Must be one of {valid_sample_rates}"
            )
        
        # Validate output format
        valid_formats = {'mp3', 'ogg_vorbis', 'pcm'}
        if self.output_format not in valid_formats:
            raise ValueError(
                f"Invalid OUTPUT_FORMAT: {self.output_format}. "
                f"Must be one of {valid_formats}"
            )
        
        # Validate retry configuration
        if self.max_retries < 0:
            raise ValueError(f"MAX_RETRIES must be non-negative, got {self.max_retries}")
        
        if self.retry_base_delay <= 0:
            raise ValueError(
                f"RETRY_BASE_DELAY must be positive, got {self.retry_base_delay}"
            )
        
        if self.retry_max_delay <= 0:
            raise ValueError(
                f"RETRY_MAX_DELAY must be positive, got {self.retry_max_delay}"
            )
        
        # Validate log level
        valid_log_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(
                f"Invalid LOG_LEVEL: {self.log_level}. "
                f"Must be one of {valid_log_levels}"
            )


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get global settings instance (singleton pattern).
    
    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
