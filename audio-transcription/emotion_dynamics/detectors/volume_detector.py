"""
Volume detection from audio using RMS energy analysis.

This module provides volume level detection using librosa's RMS energy
calculation and decibel conversion. Volume is classified into four levels
based on dB thresholds.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from emotion_dynamics.models.volume_result import VolumeResult, VolumeLevel
from emotion_dynamics.exceptions import VolumeDetectionError
from emotion_dynamics.utils.metrics import EmotionDynamicsMetrics


logger = logging.getLogger(__name__)


class VolumeDetector:
    """
    Detects volume levels from audio using RMS energy analysis.
    
    Uses librosa to compute RMS energy across audio frames, converts to
    decibels, and classifies volume based on dB thresholds:
    - Loud: > -10 dB
    - Medium: -10 to -20 dB
    - Soft: -20 to -30 dB
    - Whisper: < -30 dB
    
    Falls back to medium volume on any processing errors.
    """
    
    # Volume classification thresholds (in dB)
    LOUD_THRESHOLD = -10.0
    MEDIUM_THRESHOLD = -20.0
    SOFT_THRESHOLD = -30.0
    
    # Default fallback volume
    DEFAULT_VOLUME = 'medium'
    DEFAULT_DB = -15.0
    
    def __init__(self, metrics: Optional['EmotionDynamicsMetrics'] = None):
        """
        Initialize volume detector.
        
        Args:
            metrics: Optional metrics emitter for CloudWatch metrics
        """
        # Import librosa here to avoid import errors if not installed
        try:
            import librosa
            self.librosa = librosa
        except ImportError as e:
            logger.error("Failed to import librosa: %s", e)
            raise VolumeDetectionError("librosa is required for volume detection") from e
        
        # Initialize metrics emitter
        self.metrics = metrics or EmotionDynamicsMetrics()
    
    def detect_volume(
        self,
        audio_data: np.ndarray,
        sample_rate: int
    ) -> VolumeResult:
        """
        Detect volume level from audio using RMS energy.
        
        Computes RMS energy across audio frames, converts to decibels,
        and classifies volume based on dB thresholds. Returns medium
        volume as fallback on any errors.
        
        Args:
            audio_data: Audio samples as numpy array (mono)
            sample_rate: Audio sample rate in Hz
            
        Returns:
            VolumeResult with level classification and dB value
            
        Raises:
            VolumeDetectionError: When detection fails and fallback is used
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
            
            # Compute RMS energy using librosa
            rms = self.librosa.feature.rms(y=audio_data)[0]
            
            if rms.size == 0:
                raise ValueError("RMS calculation returned empty array")
            
            # Average RMS across frames
            avg_rms = float(np.mean(rms))
            
            # Convert RMS to decibels using fixed reference (1.0 for full scale)
            # This gives us absolute dB values relative to full scale
            if avg_rms > 0:
                avg_db = 20 * np.log10(avg_rms)
            else:
                # Handle zero RMS (silent audio)
                avg_db = -100.0  # Very low dB for silence
            
            # Classify volume based on dB thresholds
            volume_level = self._classify_volume(avg_db)
            
            logger.debug(
                "Volume detection completed: level=%s, db=%.2f",
                volume_level,
                avg_db
            )
            
            return VolumeResult(
                level=volume_level,
                db_value=avg_db,
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            # Log error with audio metadata
            logger.error(
                "Volume detection failed: %s. Falling back to %s volume",
                str(e),
                self.DEFAULT_VOLUME,
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
                component='VolumeDetector'
            )
            
            # Emit fallback metric
            self.metrics.emit_fallback_used(
                fallback_type='DefaultVolume'
            )
            
            # Return default medium volume as fallback
            return VolumeResult(
                level=self.DEFAULT_VOLUME,
                db_value=self.DEFAULT_DB,
                timestamp=datetime.now(timezone.utc)
            )
    
    def _classify_volume(self, db_value: float) -> VolumeLevel:
        """
        Classify volume level based on dB value.
        
        Thresholds:
        - Loud: > -10 dB
        - Medium: -10 to -20 dB
        - Soft: -20 to -30 dB
        - Whisper: < -30 dB
        
        Args:
            db_value: Decibel value from RMS energy
            
        Returns:
            Volume level classification
        """
        if db_value > self.LOUD_THRESHOLD:
            return 'loud'
        elif db_value > self.MEDIUM_THRESHOLD:
            return 'medium'
        elif db_value > self.SOFT_THRESHOLD:
            return 'soft'
        else:
            return 'whisper'
