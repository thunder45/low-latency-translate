"""
Audio quality utilities package.

This package provides utility functions for audio quality validation,
including error handling, graceful degradation, and helper functions.
"""

from audio_quality.utils.graceful_degradation import analyze_with_fallback
from audio_quality.utils.structured_logger import (
    log_quality_metrics,
    log_quality_issue,
    log_analysis_operation,
    log_notification_sent,
    log_metrics_emission,
    log_configuration_loaded,
)
from audio_quality.utils.xray_tracing import (
    trace_audio_analysis,
    trace_detector,
    XRayContext,
    is_xray_available,
)

__all__ = [
    'analyze_with_fallback',
    'log_quality_metrics',
    'log_quality_issue',
    'log_analysis_operation',
    'log_notification_sent',
    'log_metrics_emission',
    'log_configuration_loaded',
    'trace_audio_analysis',
    'trace_detector',
    'XRayContext',
    'is_xray_available',
]
