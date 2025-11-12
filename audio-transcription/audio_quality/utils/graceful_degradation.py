"""
Graceful degradation utilities for audio quality validation.

This module provides functions for handling errors gracefully and
returning default metrics when analysis fails, ensuring the system
continues to operate even when quality validation encounters issues.
"""

import logging
import time
import numpy as np
from typing import Optional

from audio_quality.models.quality_metrics import QualityMetrics
from audio_quality.analyzers.quality_analyzer import AudioQualityAnalyzer
from audio_quality.exceptions import (
    AudioQualityError,
    AudioFormatError,
    QualityAnalysisError
)

logger = logging.getLogger(__name__)


def analyze_with_fallback(
    analyzer: AudioQualityAnalyzer,
    audio_chunk: np.ndarray,
    sample_rate: int,
    stream_id: str = 'unknown',
    timestamp: Optional[float] = None
) -> QualityMetrics:
    """
    Analyzes audio quality with graceful degradation on failure.
    
    This function wraps the AudioQualityAnalyzer.analyze() method with
    comprehensive error handling. If analysis fails for any reason, it
    returns default metrics that indicate "unknown" quality status,
    allowing the audio processing pipeline to continue operating.
    
    The function handles different types of errors:
    - AudioFormatError: Invalid audio format
    - QualityAnalysisError: Analysis operation failed
    - ValueError: Invalid input parameters
    - Any other Exception: Unexpected errors
    
    All errors are logged with appropriate severity levels, and a
    CloudWatch metric is emitted to track fallback occurrences.
    
    Algorithm:
    1. Validate inputs (audio_chunk, sample_rate)
    2. Attempt quality analysis
    3. On success: Return actual metrics
    4. On failure:
       a. Log error with details
       b. Emit CloudWatch metric
       c. Return default "unknown" metrics
    
    Args:
        analyzer: AudioQualityAnalyzer instance to use for analysis
        audio_chunk: Audio samples as numpy array
        sample_rate: Sample rate in Hz
        stream_id: Identifier for the audio stream (default: 'unknown')
        timestamp: Current timestamp in seconds. If None, uses current time.
    
    Returns:
        QualityMetrics containing either:
        - Actual quality measurements (if analysis succeeds)
        - Default "unknown" metrics (if analysis fails)
        
        Default metrics indicate:
        - SNR: 0.0 dB (unknown)
        - Clipping: 0.0% (no clipping detected)
        - Echo: -100.0 dB (no echo detected)
        - Silence: False (not silent)
        - Energy: 0.0 dB (unknown)
    
    Examples:
        >>> analyzer = AudioQualityAnalyzer()
        >>> audio = np.random.randn(16000).astype(np.int16)
        >>> 
        >>> # Normal case - analysis succeeds
        >>> metrics = analyze_with_fallback(analyzer, audio, 16000, 'session-123')
        >>> print(f"SNR: {metrics.snr_db:.1f} dB")
        SNR: 18.5 dB
        >>> 
        >>> # Error case - analysis fails, returns defaults
        >>> invalid_audio = np.array([])
        >>> metrics = analyze_with_fallback(analyzer, invalid_audio, 16000, 'session-123')
        >>> print(f"SNR: {metrics.snr_db:.1f} dB (fallback)")
        SNR: 0.0 dB (fallback)
    
    Notes:
        - This function never raises exceptions; it always returns metrics
        - Errors are logged but do not interrupt audio processing
        - CloudWatch metrics track fallback frequency for monitoring
        - Default metrics are safe values that won't trigger false alarms
    """
    # Use current time if timestamp not provided
    if timestamp is None:
        timestamp = time.time()
    
    try:
        # Validate inputs before attempting analysis
        if audio_chunk is None or len(audio_chunk) == 0:
            logger.warning(
                f"Empty audio chunk for stream {stream_id}. "
                f"Returning default metrics."
            )
            return _get_default_metrics(stream_id, timestamp)
        
        if sample_rate <= 0:
            logger.warning(
                f"Invalid sample rate {sample_rate} for stream {stream_id}. "
                f"Returning default metrics."
            )
            return _get_default_metrics(stream_id, timestamp)
        
        # Attempt quality analysis
        metrics = analyzer.analyze(
            audio_chunk=audio_chunk,
            sample_rate=sample_rate,
            stream_id=stream_id,
            timestamp=timestamp
        )
        
        return metrics
        
    except AudioFormatError as e:
        # Audio format validation failed
        logger.error(
            f"Audio format error for stream {stream_id}: {e}. "
            f"Returning default metrics.",
            exc_info=True
        )
        _emit_fallback_metric(stream_id, 'format_error')
        return _get_default_metrics(stream_id, timestamp)
        
    except QualityAnalysisError as e:
        # Quality analysis operation failed
        logger.error(
            f"Quality analysis error for stream {stream_id}: {e}. "
            f"Returning default metrics.",
            exc_info=True
        )
        _emit_fallback_metric(stream_id, 'analysis_error')
        return _get_default_metrics(stream_id, timestamp)
        
    except ValueError as e:
        # Invalid input parameters
        logger.error(
            f"Invalid input for stream {stream_id}: {e}. "
            f"Returning default metrics.",
            exc_info=True
        )
        _emit_fallback_metric(stream_id, 'invalid_input')
        return _get_default_metrics(stream_id, timestamp)
        
    except Exception as e:
        # Unexpected error - catch all to ensure graceful degradation
        logger.error(
            f"Unexpected error during quality analysis for stream {stream_id}: {e}. "
            f"Returning default metrics.",
            exc_info=True
        )
        _emit_fallback_metric(stream_id, 'unexpected_error')
        return _get_default_metrics(stream_id, timestamp)


def _get_default_metrics(stream_id: str, timestamp: float) -> QualityMetrics:
    """
    Returns default quality metrics for fallback scenarios.
    
    These metrics indicate "unknown" or "safe" quality status that won't
    trigger false alarms or interrupt audio processing. The values are
    chosen to be neutral and not indicate quality issues.
    
    Default values:
    - SNR: 0.0 dB (unknown, but not triggering low SNR alarm)
    - Clipping: 0.0% (no clipping)
    - Echo: -100.0 dB (no echo)
    - Silence: False (not silent)
    - Energy: 0.0 dB (unknown)
    
    Args:
        stream_id: Stream identifier
        timestamp: Current timestamp
    
    Returns:
        QualityMetrics with default values
    """
    return QualityMetrics(
        timestamp=timestamp,
        stream_id=stream_id,
        # SNR metrics - unknown but safe
        snr_db=0.0,
        snr_rolling_avg=0.0,
        # Clipping metrics - no clipping
        clipping_percentage=0.0,
        clipped_sample_count=0,
        is_clipping=False,
        # Echo metrics - no echo
        echo_level_db=-100.0,
        echo_delay_ms=0.0,
        has_echo=False,
        # Silence metrics - not silent
        is_silent=False,
        silence_duration_s=0.0,
        energy_db=0.0
    )


def _emit_fallback_metric(stream_id: str, error_type: str) -> None:
    """
    Emits CloudWatch metric for quality analysis fallback.
    
    This metric tracks how often quality analysis fails and falls back
    to default metrics, allowing monitoring of system health.
    
    Args:
        stream_id: Stream identifier
        error_type: Type of error that triggered fallback
                   (e.g., 'format_error', 'analysis_error', 'invalid_input')
    """
    try:
        import boto3
        
        cloudwatch = boto3.client('cloudwatch')
        cloudwatch.put_metric_data(
            Namespace='AudioQuality',
            MetricData=[
                {
                    'MetricName': 'AnalysisFallback',
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'StreamId', 'Value': stream_id},
                        {'Name': 'ErrorType', 'Value': error_type}
                    ]
                }
            ]
        )
        
        logger.debug(
            f"Emitted fallback metric for stream {stream_id}, "
            f"error_type={error_type}"
        )
        
    except Exception as e:
        # Don't let metric emission failure affect processing
        logger.warning(f"Failed to emit fallback metric: {e}")
