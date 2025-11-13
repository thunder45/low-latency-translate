"""
Speaking rate detection from audio using onset detection.

This module provides speaking rate detection using librosa's onset
detection to identify speech events and calculate words per minute (WPM).
Rate is classified into five levels based on WPM thresholds.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from emotion_dynamics.models.rate_result import RateResult, RateClassification
from emotion_dynamics.exceptions import RateDetectionError
from emotion_dynamics.utils.metrics import EmotionDynamicsMetrics


logger = logging.getLogger(__name__)


class SpeakingRateDetector:
    """
    Detects speaking rate from audio using onset detection.
    
    Uses librosa to detect speech event boundaries (onsets), calculates
    words per minute from onset count and audio duration, and classifies
    rate based on WPM thresholds:
    - Very Slow: < 100 WPM
    - Slow: 100-130 WPM
    - Medium: 130-160 WPM
    - Fast: 160-190 WPM
    - Very Fast: > 190 WPM
    
    Falls back to medium rate on any processing errors.
    """
    
    # Rate classification thresholds (in WPM)
    VERY_SLOW_MAX = 100.0
    SLOW_MAX = 130.0
    MEDIUM_MAX = 160.0
    FAST_MAX = 190.0
    
    # Default fallback rate
    DEFAULT_RATE = 'medium'
    DEFAULT_WPM = 145.0
    DEFAULT_ONSET_COUNT = 0
    
    def __init__(self, metrics: Optional['EmotionDynamicsMetrics'] = None):
        """
        Initialize speaking rate detector.
        
        Args:
            metrics: Optional metrics emitter for CloudWatch metrics
        """
        # Import librosa here to avoid import errors if not installed
        try:
            import librosa
            self.librosa = librosa
        except ImportError as e:
            logger.error("Failed to import librosa: %s", e)
            raise RateDetectionError("librosa is required for rate detection") from e
        
        # Initialize metrics emitter
        self.metrics = metrics or EmotionDynamicsMetrics()
    
    def detect_rate(
        self,
        audio_data: np.ndarray,
        sample_rate: int
    ) -> RateResult:
        """
        Detect speaking rate from audio using onset detection.
        
        Performs onset detection to identify speech event boundaries,
        calculates words per minute from onset count and audio duration,
        and classifies rate based on WPM thresholds. Returns medium
        rate as fallback on any errors.
        
        Args:
            audio_data: Audio samples as numpy array (mono)
            sample_rate: Audio sample rate in Hz
            
        Returns:
            RateResult with rate classification, WPM, and onset count
            
        Raises:
            RateDetectionError: When detection fails and fallback is used
        """
        try:
            # Validate inputs
            if not isinstance(audio_data, np.ndarray):
                raise ValueError(f"audio_data must be numpy array, got {type(audio_data)}")
            
            if audio_data.size == 0:
                raise ValueError("audio_data is empty")
            
            if not isinstance(sample_rate, int) or sample_rate <= 0:
                raise ValueError(f"sample_rate must be positive integer, got {sample_rate}")
            
            # Ensure audio is 1D (mono)
            if audio_data.ndim > 1:
                logger.warning("Audio has %d dimensions, converting to mono", audio_data.ndim)
                audio_data = np.mean(audio_data, axis=0)
            
            # Detect onsets (speech events) using librosa
            onset_frames = self.librosa.onset.onset_detect(
                y=audio_data,
                sr=sample_rate,
                units='frames',
                hop_length=512,
                backtrack=False
            )
            
            # Count detected onsets
            onset_count = len(onset_frames)
            
            # Calculate audio duration in minutes
            duration_seconds = len(audio_data) / sample_rate
            duration_minutes = duration_seconds / 60.0
            
            # Calculate WPM from onset count and duration
            # Avoid division by zero for very short audio
            if duration_minutes > 0:
                wpm = onset_count / duration_minutes
            else:
                wpm = 0.0
            
            # Classify rate based on WPM thresholds
            rate_classification = self._classify_rate(wpm)
            
            logger.debug(
                "Rate detection completed: classification=%s, wpm=%.2f, onsets=%d, duration=%.2fs",
                rate_classification,
                wpm,
                onset_count,
                duration_seconds
            )
            
            return RateResult(
                classification=rate_classification,
                wpm=wpm,
                onset_count=onset_count,
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            # Log error with audio metadata
            logger.error(
                "Rate detection failed: %s. Falling back to %s rate",
                str(e),
                self.DEFAULT_RATE,
                exc_info=True,
                extra={
                    'audio_shape': audio_data.shape if isinstance(audio_data, np.ndarray) else None,
                    'sample_rate': sample_rate,
                    'error_type': type(e).__name__
                }
            )
            
            # Emit error metric
            self.metrics.emit_error_count(
                error_type=type(e).__name__,
                component='SpeakingRateDetector'
            )
            
            # Emit fallback metric
            self.metrics.emit_fallback_used(
                fallback_type='DefaultRate'
            )
            
            # Return default medium rate as fallback
            return RateResult(
                classification=self.DEFAULT_RATE,
                wpm=self.DEFAULT_WPM,
                onset_count=self.DEFAULT_ONSET_COUNT,
                timestamp=datetime.now(timezone.utc)
            )
    
    def _classify_rate(self, wpm: float) -> RateClassification:
        """
        Classify speaking rate based on WPM value.
        
        Thresholds:
        - Very Slow: < 100 WPM
        - Slow: 100-130 WPM
        - Medium: 130-160 WPM
        - Fast: 160-190 WPM
        - Very Fast: > 190 WPM
        
        Args:
            wpm: Words per minute from onset detection
            
        Returns:
            Rate classification
        """
        if wpm < self.VERY_SLOW_MAX:
            return 'very_slow'
        elif wpm < self.SLOW_MAX:
            return 'slow'
        elif wpm < self.MEDIUM_MAX:
            return 'medium'
        elif wpm < self.FAST_MAX:
            return 'fast'
        else:
            return 'very_fast'
