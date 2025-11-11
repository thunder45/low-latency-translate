"""
Unit tests for TranscribeClientConfig and TranscribeClientManager.

This module tests the configuration and management of AWS Transcribe Streaming
clients with partial results enabled.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from shared.services.transcribe_client import (
    TranscribeClientConfig,
    TranscribeClientManager,
    create_transcribe_client_for_session
)


class TestTranscribeClientConfig:
    """Test suite for TranscribeClientConfig."""
    
    def test_config_initialization_with_defaults(self):
        """Test config initialization with default values."""
        config = TranscribeClientConfig(language_code='en-US')
        
        assert config.language_code == 'en-US'
        assert config.media_sample_rate_hz == 16000
        assert config.media_encoding == 'pcm'
        assert config.enable_partial_results_stabilization is True
        assert config.partial_results_stability == 'high'
        assert config.region == 'us-east-1'
    
    def test_config_initialization_with_custom_values(self):
        """Test config initialization with custom values."""
        config = TranscribeClientConfig(
            language_code='es-ES',
            media_sample_rate_hz=24000,
            media_encoding='ogg-opus',
            enable_partial_results_stabilization=False,
            partial_results_stability='medium',
            region='eu-west-1'
        )
        
        assert config.language_code == 'es-ES'
        assert config.media_sample_rate_hz == 24000
        assert config.media_encoding == 'ogg-opus'
        assert config.enable_partial_results_stabilization is False
        assert config.partial_results_stability == 'medium'
        assert config.region == 'eu-west-1'
    
    def test_config_validation_invalid_language_code(self):
        """Test config validation with invalid language code."""
        with pytest.raises(ValueError, match='Invalid language_code'):
            TranscribeClientConfig(language_code='')
    
    def test_config_validation_invalid_sample_rate(self):
        """Test config validation with invalid sample rate."""
        with pytest.raises(ValueError, match='Invalid media_sample_rate_hz'):
            TranscribeClientConfig(
                language_code='en-US',
                media_sample_rate_hz=12000  # Invalid
            )
    
    def test_config_validation_invalid_encoding(self):
        """Test config validation with invalid encoding."""
        with pytest.raises(ValueError, match='Invalid media_encoding'):
            TranscribeClientConfig(
                language_code='en-US',
                media_encoding='mp3'  # Invalid
            )
    
    def test_config_validation_invalid_stability_level(self):
        """Test config validation with invalid stability level."""
        with pytest.raises(ValueError, match='Invalid partial_results_stability'):
            TranscribeClientConfig(
                language_code='en-US',
                partial_results_stability='ultra'  # Invalid
            )
    
    def test_config_validation_valid_sample_rates(self):
        """Test config validation with all valid sample rates."""
        valid_rates = [8000, 16000, 24000, 48000]
        
        for rate in valid_rates:
            config = TranscribeClientConfig(
                language_code='en-US',
                media_sample_rate_hz=rate
            )
            assert config.media_sample_rate_hz == rate
    
    def test_config_validation_valid_encodings(self):
        """Test config validation with all valid encodings."""
        valid_encodings = ['pcm', 'ogg-opus', 'flac']
        
        for encoding in valid_encodings:
            config = TranscribeClientConfig(
                language_code='en-US',
                media_encoding=encoding
            )
            assert config.media_encoding == encoding
    
    def test_config_validation_valid_stability_levels(self):
        """Test config validation with all valid stability levels."""
        valid_levels = ['low', 'medium', 'high']
        
        for level in valid_levels:
            config = TranscribeClientConfig(
                language_code='en-US',
                partial_results_stability=level
            )
            assert config.partial_results_stability == level


class TestTranscribeClientManager:
    """Test suite for TranscribeClientManager."""
    
    @pytest.fixture
    def config(self):
        """Create TranscribeClientConfig instance."""
        return TranscribeClientConfig(language_code='en-US')
    
    @pytest.fixture
    def manager(self, config):
        """Create TranscribeClientManager instance."""
        return TranscribeClientManager(config)
    
    def test_manager_initialization(self, config):
        """Test manager initialization."""
        manager = TranscribeClientManager(config)
        assert manager.config == config
    
    @patch('shared.services.transcribe_client.TranscribeStreamingClient')
    def test_create_client(self, mock_client_class, manager):
        """Test creating Transcribe client."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        client = manager.create_client()
        
        assert client == mock_client
        mock_client_class.assert_called_once_with(region='us-east-1')
    
    @pytest.mark.asyncio
    async def test_start_stream(self, manager):
        """Test starting transcription stream."""
        mock_client = Mock()
        mock_stream = Mock()
        mock_client.start_stream_transcription = AsyncMock(return_value=mock_stream)
        mock_handler = Mock()
        
        stream = await manager.start_stream(mock_client, mock_handler)
        
        assert stream == mock_stream
        mock_client.start_stream_transcription.assert_called_once()
        call_kwargs = mock_client.start_stream_transcription.call_args[1]
        assert call_kwargs['language_code'] == 'en-US'
        assert call_kwargs['media_sample_rate_hz'] == 16000
        assert call_kwargs['media_encoding'] == 'pcm'
        assert call_kwargs['enable_partial_results_stabilization'] is True
        assert call_kwargs['partial_results_stability'] == 'high'
    
    def test_get_stream_request(self, manager):
        """Test getting stream request parameters."""
        params = manager.get_stream_request()
        
        assert params['language_code'] == 'en-US'
        assert params['media_sample_rate_hz'] == 16000
        assert params['media_encoding'] == 'pcm'
        assert params['enable_partial_results_stabilization'] is True
        assert params['partial_results_stability'] == 'high'


class TestCreateTranscribeClientForSession:
    """Test suite for create_transcribe_client_for_session convenience function."""
    
    @patch('shared.services.transcribe_client.TranscribeStreamingClient')
    def test_create_client_for_session_with_defaults(self, mock_client_class):
        """Test creating client for session with default parameters."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        client, manager = create_transcribe_client_for_session('en-US')
        
        assert client == mock_client
        assert isinstance(manager, TranscribeClientManager)
        assert manager.config.language_code == 'en-US'
        assert manager.config.media_sample_rate_hz == 16000
        assert manager.config.media_encoding == 'pcm'
        assert manager.config.enable_partial_results_stabilization is True
        assert manager.config.partial_results_stability == 'high'
    
    @patch('shared.services.transcribe_client.TranscribeStreamingClient')
    def test_create_client_for_session_with_custom_params(self, mock_client_class):
        """Test creating client for session with custom parameters."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        client, manager = create_transcribe_client_for_session(
            language_code='es-ES',
            sample_rate_hz=24000,
            encoding='ogg-opus',
            region='eu-west-1'
        )
        
        assert client == mock_client
        assert manager.config.language_code == 'es-ES'
        assert manager.config.media_sample_rate_hz == 24000
        assert manager.config.media_encoding == 'ogg-opus'
        assert manager.config.region == 'eu-west-1'

