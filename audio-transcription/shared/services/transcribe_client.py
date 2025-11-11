"""
AWS Transcribe Streaming client configuration and management.

This module provides utilities for configuring and managing AWS Transcribe
Streaming API clients with partial results enabled. It handles client
initialization, stream configuration, and connection management.
"""

import logging
from typing import Optional
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.model import StartStreamTranscriptionRequest

logger = logging.getLogger(__name__)


class TranscribeClientConfig:
    """
    Configuration for AWS Transcribe Streaming client.
    
    This class encapsulates all configuration parameters for the Transcribe
    Streaming API, including partial results settings, language configuration,
    and media parameters.
    
    Attributes:
        language_code: ISO 639-1 language code (e.g., 'en-US', 'es-ES')
        media_sample_rate_hz: Audio sample rate in Hz (8000, 16000, 24000, 48000)
        media_encoding: Audio encoding format ('pcm', 'ogg-opus', 'flac')
        enable_partial_results_stabilization: Enable stability scores
        partial_results_stability: Stability level ('low', 'medium', 'high')
        region: AWS region for Transcribe service
    
    Examples:
        >>> config = TranscribeClientConfig(
        ...     language_code='en-US',
        ...     media_sample_rate_hz=16000,
        ...     media_encoding='pcm'
        ... )
        >>> assert config.enable_partial_results_stabilization == True
        >>> assert config.partial_results_stability == 'high'
    """
    
    def __init__(
        self,
        language_code: str,
        media_sample_rate_hz: int = 16000,
        media_encoding: str = 'pcm',
        enable_partial_results_stabilization: bool = True,
        partial_results_stability: str = 'high',
        region: str = 'us-east-1'
    ):
        """
        Initialize Transcribe client configuration.
        
        Args:
            language_code: ISO 639-1 language code (e.g., 'en-US')
            media_sample_rate_hz: Audio sample rate in Hz (default: 16000)
            media_encoding: Audio encoding format (default: 'pcm')
            enable_partial_results_stabilization: Enable stability scores (default: True)
            partial_results_stability: Stability level (default: 'high')
            region: AWS region (default: 'us-east-1')
        
        Raises:
            ValueError: If configuration parameters are invalid
        """
        self.language_code = language_code
        self.media_sample_rate_hz = media_sample_rate_hz
        self.media_encoding = media_encoding
        self.enable_partial_results_stabilization = enable_partial_results_stabilization
        self.partial_results_stability = partial_results_stability
        self.region = region
        
        # Validate configuration
        self._validate()
        
        logger.info(
            f"Initialized TranscribeClientConfig: "
            f"language={language_code}, "
            f"sample_rate={media_sample_rate_hz}Hz, "
            f"encoding={media_encoding}, "
            f"partial_stabilization={enable_partial_results_stabilization}, "
            f"stability_level={partial_results_stability}"
        )
    
    def _validate(self) -> None:
        """
        Validate configuration parameters.
        
        Raises:
            ValueError: If any parameter is invalid
        """
        # Validate language code format (basic check)
        if not self.language_code or len(self.language_code) < 2:
            raise ValueError(
                f"Invalid language_code: {self.language_code}. "
                f"Expected format: 'en-US', 'es-ES', etc."
            )
        
        # Validate sample rate
        valid_sample_rates = [8000, 16000, 24000, 48000]
        if self.media_sample_rate_hz not in valid_sample_rates:
            raise ValueError(
                f"Invalid media_sample_rate_hz: {self.media_sample_rate_hz}. "
                f"Must be one of {valid_sample_rates}"
            )
        
        # Validate encoding
        valid_encodings = ['pcm', 'ogg-opus', 'flac']
        if self.media_encoding not in valid_encodings:
            raise ValueError(
                f"Invalid media_encoding: {self.media_encoding}. "
                f"Must be one of {valid_encodings}"
            )
        
        # Validate stability level
        valid_stability_levels = ['low', 'medium', 'high']
        if self.partial_results_stability not in valid_stability_levels:
            raise ValueError(
                f"Invalid partial_results_stability: {self.partial_results_stability}. "
                f"Must be one of {valid_stability_levels}"
            )


class TranscribeClientManager:
    """
    Manager for AWS Transcribe Streaming client lifecycle.
    
    This class manages the creation and configuration of Transcribe Streaming
    clients with partial results enabled. It provides a high-level interface
    for starting transcription streams with the correct configuration.
    
    Examples:
        >>> config = TranscribeClientConfig(language_code='en-US')
        >>> manager = TranscribeClientManager(config)
        >>> client = manager.create_client()
        >>> stream = await manager.start_stream(client, handler)
    """
    
    def __init__(self, config: TranscribeClientConfig):
        """
        Initialize Transcribe client manager.
        
        Args:
            config: Configuration for Transcribe client
        """
        self.config = config
        
        logger.info(
            f"Initialized TranscribeClientManager for "
            f"language {config.language_code}"
        )
    
    def create_client(self) -> TranscribeStreamingClient:
        """
        Create AWS Transcribe Streaming client.
        
        This method creates a new TranscribeStreamingClient instance
        configured for the specified region.
        
        Returns:
            TranscribeStreamingClient instance
        
        Examples:
            >>> manager = TranscribeClientManager(config)
            >>> client = manager.create_client()
            >>> assert isinstance(client, TranscribeStreamingClient)
        """
        logger.info(f"Creating Transcribe client for region {self.config.region}")
        
        client = TranscribeStreamingClient(region=self.config.region)
        
        logger.info("Transcribe client created successfully")
        return client
    
    async def start_stream(
        self,
        client: TranscribeStreamingClient,
        handler
    ):
        """
        Start transcription stream with partial results enabled.
        
        This method starts a streaming transcription session with the
        configured parameters, including partial results stabilization.
        
        The stream is configured with:
        - Partial results enabled
        - Stability scores enabled (if supported by language)
        - Configured stability level ('high' by default)
        - Specified language, sample rate, and encoding
        
        Args:
            client: TranscribeStreamingClient instance
            handler: TranscribeStreamHandler for processing events
        
        Returns:
            Transcription stream object
        
        Examples:
            >>> manager = TranscribeClientManager(config)
            >>> client = manager.create_client()
            >>> handler = TranscribeStreamHandler(...)
            >>> stream = await manager.start_stream(client, handler)
        """
        logger.info(
            f"Starting transcription stream: "
            f"language={self.config.language_code}, "
            f"sample_rate={self.config.media_sample_rate_hz}Hz, "
            f"encoding={self.config.media_encoding}"
        )
        
        # Create stream request with partial results configuration
        stream = await client.start_stream_transcription(
            language_code=self.config.language_code,
            media_sample_rate_hz=self.config.media_sample_rate_hz,
            media_encoding=self.config.media_encoding,
            enable_partial_results_stabilization=self.config.enable_partial_results_stabilization,
            partial_results_stability=self.config.partial_results_stability
        )
        
        logger.info(
            f"Transcription stream started successfully with "
            f"partial_results_stabilization={self.config.enable_partial_results_stabilization}, "
            f"stability_level={self.config.partial_results_stability}"
        )
        
        return stream
    
    def get_stream_request(self) -> dict:
        """
        Get stream request parameters as dictionary.
        
        This method returns the stream configuration as a dictionary,
        useful for logging or debugging.
        
        Returns:
            Dictionary with stream request parameters
        
        Examples:
            >>> manager = TranscribeClientManager(config)
            >>> params = manager.get_stream_request()
            >>> assert params['language_code'] == 'en-US'
            >>> assert params['enable_partial_results_stabilization'] == True
        """
        return {
            'language_code': self.config.language_code,
            'media_sample_rate_hz': self.config.media_sample_rate_hz,
            'media_encoding': self.config.media_encoding,
            'enable_partial_results_stabilization': self.config.enable_partial_results_stabilization,
            'partial_results_stability': self.config.partial_results_stability
        }


def create_transcribe_client_for_session(
    language_code: str,
    sample_rate_hz: int = 16000,
    encoding: str = 'pcm',
    region: str = 'us-east-1'
) -> tuple[TranscribeStreamingClient, TranscribeClientManager]:
    """
    Convenience function to create Transcribe client and manager for a session.
    
    This function provides a simple interface for creating a configured
    Transcribe client and manager with sensible defaults for partial results
    processing.
    
    Args:
        language_code: ISO 639-1 language code (e.g., 'en-US')
        sample_rate_hz: Audio sample rate in Hz (default: 16000)
        encoding: Audio encoding format (default: 'pcm')
        region: AWS region (default: 'us-east-1')
    
    Returns:
        Tuple of (TranscribeStreamingClient, TranscribeClientManager)
    
    Examples:
        >>> client, manager = create_transcribe_client_for_session('en-US')
        >>> handler = TranscribeStreamHandler(...)
        >>> stream = await manager.start_stream(client, handler)
    """
    # Create configuration with partial results enabled
    config = TranscribeClientConfig(
        language_code=language_code,
        media_sample_rate_hz=sample_rate_hz,
        media_encoding=encoding,
        enable_partial_results_stabilization=True,
        partial_results_stability='high',
        region=region
    )
    
    # Create manager and client
    manager = TranscribeClientManager(config)
    client = manager.create_client()
    
    logger.info(
        f"Created Transcribe client and manager for session: "
        f"language={language_code}, region={region}"
    )
    
    return client, manager

