"""
Audio Quality Validation & Processing Package.

This package provides real-time audio quality analysis and validation
for audio streams, including SNR calculation, clipping detection,
echo detection, and silence detection.
"""

__version__ = '1.0.0'

# Import main classes for convenient access
from audio_quality.models.quality_config import QualityConfig
from audio_quality.models.quality_metrics import QualityMetrics
from audio_quality.models.audio_format import AudioFormat
from audio_quality.models.quality_event import QualityEvent
from audio_quality.models.results import ClippingResult, EchoResult, SilenceResult
from audio_quality.models.validation_result import ValidationResult
from audio_quality.validators.format_validator import AudioFormatValidator

__all__ = [
    'QualityConfig',
    'QualityMetrics',
    'AudioFormat',
    'QualityEvent',
    'ClippingResult',
    'EchoResult',
    'SilenceResult',
    'ValidationResult',
    'AudioFormatValidator',
]
