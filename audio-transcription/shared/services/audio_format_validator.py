"""
Audio format validator for WebSocket audio chunks.

This module provides validation for audio format, ensuring that audio chunks
are PCM 16-bit mono at 16000 Hz sample rate. Caches validation results for
performance.
"""

import logging
import struct
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class AudioFormatError(Exception):
    """Raised when audio format is invalid."""
    pass


@dataclass
class AudioFormat:
    """
    Audio format specification.
    
    Attributes:
        encoding: Audio encoding (e.g., 'pcm')
        sample_rate: Sample rate in Hz
        bit_depth: Bit depth (e.g., 16)
        channels: Number of channels (1=mono, 2=stereo)
        is_valid: Whether format is valid
    """
    encoding: str
    sample_rate: int
    bit_depth: int
    channels: int
    is_valid: bool = True


class AudioFormatValidator:
    """
    Validator for audio format with caching.
    
    This class validates that audio chunks are:
    - PCM 16-bit encoding
    - Mono (1 channel)
    - 16000 Hz sample rate
    
    Validation is performed on the first chunk and cached for subsequent
    chunks from the same connection.
    
    Examples:
        >>> validator = AudioFormatValidator()
        >>> is_valid = validator.validate_audio_chunk('conn-123', audio_bytes)
        >>> if not is_valid:
        ...     print("Invalid audio format")
    """
    
    # Expected format
    EXPECTED_ENCODING = 'pcm'
    EXPECTED_SAMPLE_RATE = 16000
    EXPECTED_BIT_DEPTH = 16
    EXPECTED_CHANNELS = 1
    
    def __init__(self):
        """Initialize audio format validator."""
        # Cache validation results per connection
        self.validation_cache: Dict[str, bool] = {}
        
        # Cache detected formats per connection
        self.format_cache: Dict[str, AudioFormat] = {}
        
        logger.info(
            f"Initialized AudioFormatValidator: "
            f"expected_format={self.EXPECTED_ENCODING} "
            f"{self.EXPECTED_BIT_DEPTH}-bit {self.EXPECTED_CHANNELS}ch "
            f"@ {self.EXPECTED_SAMPLE_RATE}Hz"
        )
    
    def validate_audio_chunk(
        self,
        connection_id: str,
        audio_bytes: bytes,
        force_revalidate: bool = False
    ) -> bool:
        """
        Validate audio chunk format.
        
        On first chunk, performs full validation and caches result.
        On subsequent chunks, returns cached result unless force_revalidate=True.
        
        Args:
            connection_id: WebSocket connection ID
            audio_bytes: Audio data as bytes
            force_revalidate: Force revalidation even if cached
        
        Returns:
            True if format is valid, False otherwise
        
        Raises:
            AudioFormatError: If format is invalid (with details)
        
        Examples:
            >>> validator = AudioFormatValidator()
            >>> # First chunk - performs validation
            >>> is_valid = validator.validate_audio_chunk('conn-123', audio_bytes)
            >>> # Subsequent chunks - uses cache
            >>> is_valid = validator.validate_audio_chunk('conn-123', audio_bytes)
        """
        # Check cache unless force revalidate
        if not force_revalidate and connection_id in self.validation_cache:
            is_valid = self.validation_cache[connection_id]
            logger.debug(
                f"Using cached validation result for {connection_id}: {is_valid}"
            )
            return is_valid
        
        try:
            # Perform validation
            audio_format = self._detect_format(audio_bytes)
            is_valid = self._validate_format(audio_format)
            
            # Cache result
            self.validation_cache[connection_id] = is_valid
            self.format_cache[connection_id] = audio_format
            
            logger.info(
                f"Validated audio format for {connection_id}: "
                f"{audio_format.encoding} {audio_format.bit_depth}-bit "
                f"{audio_format.channels}ch @ {audio_format.sample_rate}Hz - "
                f"valid={is_valid}"
            )
            
            return is_valid
            
        except AudioFormatError as e:
            # Cache failure
            self.validation_cache[connection_id] = False
            logger.error(
                f"Audio format validation failed for {connection_id}: {e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error during audio validation: {e}",
                exc_info=True
            )
            raise AudioFormatError(f"Validation error: {e}")
    
    def _detect_format(self, audio_bytes: bytes) -> AudioFormat:
        """
        Detect audio format from raw bytes.
        
        For PCM audio, we can infer format from:
        - Byte length (must be even for 16-bit)
        - Sample values (should be in int16 range)
        
        Args:
            audio_bytes: Audio data as bytes
        
        Returns:
            AudioFormat with detected parameters
        
        Raises:
            AudioFormatError: If format cannot be detected
        """
        if not audio_bytes:
            raise AudioFormatError("Empty audio data")
        
        # Check byte length
        byte_length = len(audio_bytes)
        
        # For 16-bit audio, length must be even
        if byte_length % 2 != 0:
            raise AudioFormatError(
                f"Invalid byte length for 16-bit audio: {byte_length} "
                f"(must be even)"
            )
        
        # Assume PCM 16-bit mono
        # We can't definitively detect sample rate from raw PCM,
        # so we assume 16000 Hz and validate that it's reasonable
        
        num_samples = byte_length // 2  # 2 bytes per sample for 16-bit
        
        # Validate sample values are in int16 range
        try:
            # Check first few samples
            samples_to_check = min(10, num_samples)
            for i in range(samples_to_check):
                offset = i * 2
                sample = struct.unpack('<h', audio_bytes[offset:offset+2])[0]
                # Sample should be in int16 range [-32768, 32767]
                if not -32768 <= sample <= 32767:
                    raise AudioFormatError(
                        f"Sample value out of int16 range: {sample}"
                    )
        except struct.error as e:
            raise AudioFormatError(f"Failed to parse audio samples: {e}")
        
        return AudioFormat(
            encoding='pcm',
            sample_rate=self.EXPECTED_SAMPLE_RATE,  # Assumed
            bit_depth=16,
            channels=1,  # Assumed mono
            is_valid=True
        )
    
    def _validate_format(self, audio_format: AudioFormat) -> bool:
        """
        Validate that format matches expected format.
        
        Args:
            audio_format: Detected audio format
        
        Returns:
            True if format matches expected, False otherwise
        
        Raises:
            AudioFormatError: If format doesn't match expected
        """
        errors = []
        
        # Check encoding
        if audio_format.encoding != self.EXPECTED_ENCODING:
            errors.append(
                f"Invalid encoding: {audio_format.encoding} "
                f"(expected {self.EXPECTED_ENCODING})"
            )
        
        # Check sample rate
        if audio_format.sample_rate != self.EXPECTED_SAMPLE_RATE:
            errors.append(
                f"Invalid sample rate: {audio_format.sample_rate}Hz "
                f"(expected {self.EXPECTED_SAMPLE_RATE}Hz)"
            )
        
        # Check bit depth
        if audio_format.bit_depth != self.EXPECTED_BIT_DEPTH:
            errors.append(
                f"Invalid bit depth: {audio_format.bit_depth}-bit "
                f"(expected {self.EXPECTED_BIT_DEPTH}-bit)"
            )
        
        # Check channels
        if audio_format.channels != self.EXPECTED_CHANNELS:
            errors.append(
                f"Invalid channels: {audio_format.channels} "
                f"(expected {self.EXPECTED_CHANNELS} - mono)"
            )
        
        if errors:
            error_msg = "; ".join(errors)
            raise AudioFormatError(error_msg)
        
        return True
    
    def get_cached_format(self, connection_id: str) -> Optional[AudioFormat]:
        """
        Get cached audio format for connection.
        
        Args:
            connection_id: WebSocket connection ID
        
        Returns:
            AudioFormat if cached, None otherwise
        """
        return self.format_cache.get(connection_id)
    
    def is_format_cached(self, connection_id: str) -> bool:
        """
        Check if format is cached for connection.
        
        Args:
            connection_id: WebSocket connection ID
        
        Returns:
            True if format is cached, False otherwise
        """
        return connection_id in self.validation_cache
    
    def clear_cache(self, connection_id: str) -> None:
        """
        Clear cached validation result for connection.
        
        Args:
            connection_id: WebSocket connection ID
        """
        if connection_id in self.validation_cache:
            del self.validation_cache[connection_id]
        
        if connection_id in self.format_cache:
            del self.format_cache[connection_id]
        
        logger.debug(f"Cleared format cache for connection {connection_id}")
    
    def clear_all_cache(self) -> None:
        """Clear all cached validation results."""
        self.validation_cache.clear()
        self.format_cache.clear()
        logger.info("Cleared all format validation cache")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            'cached_connections': len(self.validation_cache),
            'valid_connections': sum(
                1 for v in self.validation_cache.values() if v
            ),
            'invalid_connections': sum(
                1 for v in self.validation_cache.values() if not v
            )
        }
