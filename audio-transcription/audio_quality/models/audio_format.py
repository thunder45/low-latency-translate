"""
Audio format specification data model.

This module defines the AudioFormat dataclass for specifying
and validating audio format parameters.
"""

from dataclasses import dataclass
from typing import List, ClassVar


@dataclass
class AudioFormat:
    """Audio format specification."""
    
    sample_rate: int  # Hz (8000, 16000, 24000, 48000)
    bit_depth: int    # Bits (16)
    channels: int     # Channel count (1 for mono)
    encoding: str     # 'pcm_s16le'
    
    # Supported values (class variables)
    SUPPORTED_SAMPLE_RATES: ClassVar[List[int]] = [8000, 16000, 24000, 48000]
    SUPPORTED_BIT_DEPTHS: ClassVar[List[int]] = [16]
    SUPPORTED_CHANNELS: ClassVar[List[int]] = [1]
    SUPPORTED_ENCODINGS: ClassVar[List[str]] = ['pcm_s16le']
    
    def is_valid(self) -> bool:
        """
        Checks if format is supported.
        
        Returns:
            True if format is valid and supported, False otherwise.
        """
        return (
            self.sample_rate in self.SUPPORTED_SAMPLE_RATES and
            self.bit_depth in self.SUPPORTED_BIT_DEPTHS and
            self.channels in self.SUPPORTED_CHANNELS and
            self.encoding in self.SUPPORTED_ENCODINGS
        )
    
    def get_validation_errors(self) -> List[str]:
        """
        Gets detailed validation error messages.
        
        Returns:
            List of error messages. Empty if format is valid.
        """
        errors = []
        
        if self.sample_rate not in self.SUPPORTED_SAMPLE_RATES:
            errors.append(
                f'Sample rate {self.sample_rate} Hz not supported. '
                f'Supported rates: {self.SUPPORTED_SAMPLE_RATES}'
            )
        
        if self.bit_depth not in self.SUPPORTED_BIT_DEPTHS:
            errors.append(
                f'Bit depth {self.bit_depth} not supported. '
                f'Supported depths: {self.SUPPORTED_BIT_DEPTHS}'
            )
        
        if self.channels not in self.SUPPORTED_CHANNELS:
            errors.append(
                f'Channel count {self.channels} not supported. '
                f'Supported channels: {self.SUPPORTED_CHANNELS}'
            )
        
        if self.encoding not in self.SUPPORTED_ENCODINGS:
            errors.append(
                f'Encoding {self.encoding} not supported. '
                f'Supported encodings: {self.SUPPORTED_ENCODINGS}'
            )
        
        return errors
