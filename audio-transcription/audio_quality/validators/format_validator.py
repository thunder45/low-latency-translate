"""
Audio format validator.

This module provides the AudioFormatValidator class for validating
audio format specifications against supported configurations.
"""

from audio_quality.models.audio_format import AudioFormat
from audio_quality.models.validation_result import ValidationResult


class AudioFormatValidator:
    """
    Validates audio format specifications.
    
    This validator checks that audio format parameters (sample rate,
    bit depth, channel count, encoding) match the supported values
    required for audio quality analysis.
    
    Supported formats:
        - Sample rates: 8000, 16000, 24000, 48000 Hz
        - Bit depth: 16 bits
        - Channels: 1 (mono)
        - Encoding: pcm_s16le
    """
    
    # Supported values (class constants)
    SUPPORTED_SAMPLE_RATES = [8000, 16000, 24000, 48000]
    SUPPORTED_BIT_DEPTHS = [16]
    SUPPORTED_CHANNELS = [1]  # Mono only
    SUPPORTED_ENCODINGS = ['pcm_s16le']
    
    def validate(self, audio_format: AudioFormat) -> ValidationResult:
        """
        Validates audio format against supported specifications.
        
        Checks that the provided audio format has valid sample rate,
        bit depth, channel count, and encoding. Returns a ValidationResult
        with success status and detailed error messages for any invalid
        parameters.
        
        Args:
            audio_format: Audio format specification to validate.
            
        Returns:
            ValidationResult with success status and error details.
            - success=True with empty errors if format is valid
            - success=False with list of error messages if format is invalid
            
        Example:
            >>> validator = AudioFormatValidator()
            >>> format = AudioFormat(sample_rate=16000, bit_depth=16, 
            ...                      channels=1, encoding='pcm_s16le')
            >>> result = validator.validate(format)
            >>> result.success
            True
            
            >>> bad_format = AudioFormat(sample_rate=44100, bit_depth=24,
            ...                          channels=2, encoding='mp3')
            >>> result = validator.validate(bad_format)
            >>> result.success
            False
            >>> len(result.errors)
            4
        """
        errors = []
        
        # Validate sample rate
        if audio_format.sample_rate not in self.SUPPORTED_SAMPLE_RATES:
            errors.append(
                f'Sample rate {audio_format.sample_rate} Hz not supported. '
                f'Supported rates: {self.SUPPORTED_SAMPLE_RATES} Hz'
            )
        
        # Validate bit depth
        if audio_format.bit_depth not in self.SUPPORTED_BIT_DEPTHS:
            errors.append(
                f'Bit depth {audio_format.bit_depth} bits not supported. '
                f'Supported depths: {self.SUPPORTED_BIT_DEPTHS} bits'
            )
        
        # Validate channel count
        if audio_format.channels not in self.SUPPORTED_CHANNELS:
            errors.append(
                f'Channel count {audio_format.channels} not supported. '
                f'Supported channels: {self.SUPPORTED_CHANNELS} (mono only)'
            )
        
        # Validate encoding
        if audio_format.encoding not in self.SUPPORTED_ENCODINGS:
            errors.append(
                f'Encoding "{audio_format.encoding}" not supported. '
                f'Supported encodings: {self.SUPPORTED_ENCODINGS}'
            )
        
        # Return result
        if errors:
            return ValidationResult.failure_result(errors)
        else:
            return ValidationResult.success_result()
