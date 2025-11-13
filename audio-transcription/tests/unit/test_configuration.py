"""
Unit tests for configuration management.

Tests configuration loading, validation, and feature flag integration.
"""

import os
import pytest
from unittest.mock import patch

from emotion_dynamics.config.settings import Settings, get_settings
from emotion_dynamics.orchestrator import AudioDynamicsOrchestrator
from emotion_dynamics.models.processing_options import ProcessingOptions


class TestSettings:
    """Test suite for Settings configuration class."""
    
    def test_settings_initialization_with_defaults(self):
        """Test settings initialization with default values."""
        settings = Settings()
        
        # AWS Configuration
        assert settings.aws_region == 'us-east-1'
        
        # Polly Configuration
        assert settings.voice_id == 'Joanna'
        assert settings.sample_rate == '24000'
        assert settings.output_format == 'mp3'
        
        # Feature Flags
        assert settings.enable_ssml is True
        assert settings.enable_volume_detection is True
        assert settings.enable_rate_detection is True
        
        # Retry Configuration
        assert settings.max_retries == 3
        assert settings.retry_base_delay == 0.1
        assert settings.retry_max_delay == 2.0
        
        # Logging Configuration
        assert settings.log_level == 'INFO'
        
        # Audio Processing Configuration
        assert settings.audio_sample_rate == 16000
    
    @patch.dict(os.environ, {
        'AWS_REGION': 'us-west-2',
        'VOICE_ID': 'Matthew',
        'SAMPLE_RATE': '16000',
        'OUTPUT_FORMAT': 'ogg_vorbis',
        'ENABLE_SSML': 'false',
        'ENABLE_VOLUME_DETECTION': 'false',
        'ENABLE_RATE_DETECTION': 'false',
        'MAX_RETRIES': '5',
        'RETRY_BASE_DELAY': '0.2',
        'RETRY_MAX_DELAY': '3.0',
        'LOG_LEVEL': 'DEBUG',
        'AUDIO_SAMPLE_RATE': '24000'
    })
    def test_settings_initialization_from_environment(self):
        """Test settings initialization from environment variables."""
        settings = Settings()
        
        # AWS Configuration
        assert settings.aws_region == 'us-west-2'
        
        # Polly Configuration
        assert settings.voice_id == 'Matthew'
        assert settings.sample_rate == '16000'
        assert settings.output_format == 'ogg_vorbis'
        
        # Feature Flags
        assert settings.enable_ssml is False
        assert settings.enable_volume_detection is False
        assert settings.enable_rate_detection is False
        
        # Retry Configuration
        assert settings.max_retries == 5
        assert settings.retry_base_delay == 0.2
        assert settings.retry_max_delay == 3.0
        
        # Logging Configuration
        assert settings.log_level == 'DEBUG'
        
        # Audio Processing Configuration
        assert settings.audio_sample_rate == 24000
    
    def test_parse_bool_with_various_values(self):
        """Test boolean parsing from string values."""
        settings = Settings()
        
        # True values
        assert settings._parse_bool('true') is True
        assert settings._parse_bool('True') is True
        assert settings._parse_bool('TRUE') is True
        assert settings._parse_bool('1') is True
        assert settings._parse_bool('yes') is True
        assert settings._parse_bool('on') is True
        
        # False values
        assert settings._parse_bool('false') is False
        assert settings._parse_bool('False') is False
        assert settings._parse_bool('FALSE') is False
        assert settings._parse_bool('0') is False
        assert settings._parse_bool('no') is False
        assert settings._parse_bool('off') is False
    
    @patch.dict(os.environ, {'SAMPLE_RATE': 'invalid'})
    def test_settings_validation_invalid_sample_rate(self):
        """Test settings validation with invalid sample rate."""
        with pytest.raises(ValueError, match="Invalid SAMPLE_RATE"):
            Settings()
    
    @patch.dict(os.environ, {'OUTPUT_FORMAT': 'invalid'})
    def test_settings_validation_invalid_output_format(self):
        """Test settings validation with invalid output format."""
        with pytest.raises(ValueError, match="Invalid OUTPUT_FORMAT"):
            Settings()
    
    @patch.dict(os.environ, {'MAX_RETRIES': '-1'})
    def test_settings_validation_negative_max_retries(self):
        """Test settings validation with negative max retries."""
        with pytest.raises(ValueError, match="MAX_RETRIES must be non-negative"):
            Settings()
    
    @patch.dict(os.environ, {'RETRY_BASE_DELAY': '0'})
    def test_settings_validation_zero_base_delay(self):
        """Test settings validation with zero base delay."""
        with pytest.raises(ValueError, match="RETRY_BASE_DELAY must be positive"):
            Settings()
    
    @patch.dict(os.environ, {'RETRY_MAX_DELAY': '-1'})
    def test_settings_validation_negative_max_delay(self):
        """Test settings validation with negative max delay."""
        with pytest.raises(ValueError, match="RETRY_MAX_DELAY must be positive"):
            Settings()
    
    @patch.dict(os.environ, {'LOG_LEVEL': 'INVALID'})
    def test_settings_validation_invalid_log_level(self):
        """Test settings validation with invalid log level."""
        with pytest.raises(ValueError, match="Invalid LOG_LEVEL"):
            Settings()
    
    def test_get_settings_singleton(self):
        """Test get_settings returns singleton instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        
        # Should return same instance
        assert settings1 is settings2


class TestOrchestratorConfigurationIntegration:
    """Test suite for orchestrator configuration integration."""
    
    @patch.dict(os.environ, {
        'ENABLE_VOLUME_DETECTION': 'false',
        'ENABLE_RATE_DETECTION': 'false',
        'ENABLE_SSML': 'false'
    })
    def test_orchestrator_uses_settings_for_defaults(self):
        """Test orchestrator uses settings for default options."""
        # Create new settings instance with environment variables
        from emotion_dynamics.config.settings import Settings
        settings = Settings()
        
        # Create orchestrator with settings
        orchestrator = AudioDynamicsOrchestrator(settings=settings)
        
        # Verify settings are used
        assert orchestrator.settings.enable_volume_detection is False
        assert orchestrator.settings.enable_rate_detection is False
        assert orchestrator.settings.enable_ssml is False
    
    @patch.dict(os.environ, {
        'VOICE_ID': 'Matthew',
        'SAMPLE_RATE': '16000',
        'OUTPUT_FORMAT': 'ogg_vorbis'
    })
    def test_orchestrator_polly_client_uses_settings(self):
        """Test orchestrator configures Polly client from settings."""
        from emotion_dynamics.config.settings import Settings
        settings = Settings()
        
        orchestrator = AudioDynamicsOrchestrator(settings=settings)
        
        # Verify Polly client configuration
        assert orchestrator.polly_client.max_retries == settings.max_retries
        assert orchestrator.polly_client.base_delay == settings.retry_base_delay
        assert orchestrator.polly_client.max_delay == settings.retry_max_delay
    
    def test_processing_options_override_settings(self):
        """Test ProcessingOptions can override settings."""
        from emotion_dynamics.config.settings import Settings
        settings = Settings()
        
        orchestrator = AudioDynamicsOrchestrator(settings=settings)
        
        # Create custom options that override settings
        custom_options = ProcessingOptions(
            voice_id='Matthew',
            enable_ssml=False,
            enable_volume_detection=False,
            enable_rate_detection=False
        )
        
        # Options should override settings
        assert custom_options.voice_id == 'Matthew'
        assert custom_options.enable_ssml is False
        assert custom_options.enable_volume_detection is False
        assert custom_options.enable_rate_detection is False
    
    @patch.dict(os.environ, {
        'ENABLE_VOLUME_DETECTION': 'false'
    })
    def test_orchestrator_respects_disabled_volume_detection(self, sample_audio):
        """Test orchestrator respects disabled volume detection flag."""
        from emotion_dynamics.config.settings import Settings
        settings = Settings()
        
        orchestrator = AudioDynamicsOrchestrator(settings=settings)
        
        # Process audio with settings (volume detection disabled)
        dynamics, volume_ms, rate_ms, combined_ms = orchestrator.detect_audio_dynamics(
            audio_data=sample_audio,
            sample_rate=16000
        )
        
        # Volume should be default medium (not detected)
        assert dynamics.volume.level == 'medium'
        assert dynamics.volume.db_value == -15.0
        
        # Rate should still be detected
        assert dynamics.rate.classification in ['very_slow', 'slow', 'medium', 'fast', 'very_fast']
    
    @patch.dict(os.environ, {
        'ENABLE_RATE_DETECTION': 'false'
    })
    def test_orchestrator_respects_disabled_rate_detection(self, sample_audio):
        """Test orchestrator respects disabled rate detection flag."""
        from emotion_dynamics.config.settings import Settings
        settings = Settings()
        
        orchestrator = AudioDynamicsOrchestrator(settings=settings)
        
        # Process audio with settings (rate detection disabled)
        dynamics, volume_ms, rate_ms, combined_ms = orchestrator.detect_audio_dynamics(
            audio_data=sample_audio,
            sample_rate=16000
        )
        
        # Rate should be default medium (not detected)
        assert dynamics.rate.classification == 'medium'
        assert dynamics.rate.wpm == 145.0
        assert dynamics.rate.onset_count == 0
        
        # Volume should still be detected
        assert dynamics.volume.level in ['loud', 'medium', 'soft', 'whisper']
    
    @patch.dict(os.environ, {
        'ENABLE_SSML': 'false'
    })
    def test_orchestrator_respects_disabled_ssml(self, sample_audio):
        """Test orchestrator respects disabled SSML flag."""
        from emotion_dynamics.config.settings import Settings
        from unittest.mock import Mock
        
        settings = Settings()
        
        # Mock Polly client to avoid actual API calls
        mock_polly = Mock()
        mock_polly.synthesize_speech.return_value = b'mock_audio_data'
        
        orchestrator = AudioDynamicsOrchestrator(
            settings=settings,
            polly_client=mock_polly
        )
        
        # Process audio and text with settings (SSML disabled)
        result = orchestrator.process_audio_and_text(
            audio_data=sample_audio,
            sample_rate=16000,
            translated_text="Hello world"
        )
        
        # SSML should be plain (no prosody tags)
        assert '<prosody' not in result.ssml_text
        assert '<speak>' in result.ssml_text
        assert 'Hello world' in result.ssml_text
        
        # Fallback should be marked as used
        assert result.fallback_used is True


@pytest.fixture
def sample_audio():
    """Fixture providing sample audio data."""
    import numpy as np
    
    # Generate 1 second of sample audio at 16kHz
    sample_rate = 16000
    duration = 1.0
    frequency = 440.0  # A4 note
    
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = 0.5 * np.sin(2 * np.pi * frequency * t)
    
    return audio
