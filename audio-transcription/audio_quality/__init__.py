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
from audio_quality.analyzers.snr_calculator import SNRCalculator
from audio_quality.analyzers.clipping_detector import ClippingDetector
from audio_quality.analyzers.echo_detector import EchoDetector
from audio_quality.analyzers.silence_detector import SilenceDetector
from audio_quality.analyzers.quality_analyzer import AudioQualityAnalyzer
from audio_quality.notifiers.metrics_emitter import QualityMetricsEmitter
from audio_quality.notifiers.speaker_notifier import SpeakerNotifier
from audio_quality.processors.audio_processor import AudioProcessor

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
    'SNRCalculator',
    'ClippingDetector',
    'EchoDetector',
    'SilenceDetector',
    'AudioQualityAnalyzer',
    'QualityMetricsEmitter',
    'SpeakerNotifier',
    'AudioProcessor',
]
