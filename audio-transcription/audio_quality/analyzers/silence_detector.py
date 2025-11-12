"""
Silence Detector.

This module provides silence detection for audio quality validation.
Detects extended silence periods (>5 seconds below -50 dB) and differentiates
between natural speech pauses and technical issues.
"""

import numpy as np
from typing import Optional
from audio_quality.models.results import SilenceResult


class SilenceDetector:
    """
    Detects extended silence periods in audio streams.
    
    The detector tracks RMS energy in dB and monitors continuous silence
    duration. It differentiates between natural speech pauses (<5 seconds)
    and technical issues (>5 seconds) by analyzing energy patterns over
    5-second windows.
    
    The detector resets the silence timer when audio energy returns above
    the threshold, allowing it to distinguish between brief pauses and
    sustained silence.
    
    Attributes:
        silence_threshold_db: Energy threshold in dB below which audio is considered silent
        duration_threshold_s: Duration threshold in seconds for extended silence detection
        silence_start_time: Timestamp when current silence period started (None if not silent)
    """
    
    def __init__(
        self,
        silence_threshold_db: float = -50.0,
        duration_threshold_s: float = 5.0
    ):
        """
        Initialize silence detector.
        
        Args:
            silence_threshold_db: Energy threshold in dB (default: -50.0)
            duration_threshold_s: Duration threshold in seconds (default: 5.0)
        """
        self.silence_threshold_db = silence_threshold_db
        self.duration_threshold_s = duration_threshold_s
        self.silence_start_time: Optional[float] = None
        
    def detect_silence(
        self,
        audio_chunk: np.ndarray,
        timestamp: float
    ) -> SilenceResult:
        """
        Detect extended silence periods.
        
        Algorithm:
        1. Calculate RMS energy in dB
        2. Track continuous silence duration
        3. Emit warning if silence > 5 seconds
        4. Reset on audio activity (energy > -40 dB for quick reset)
        
        The detector uses two thresholds:
        - silence_threshold_db (-50 dB): Below this is considered silence
        - reset_threshold_db (-40 dB): Above this resets the silence timer
        
        This allows natural speech pauses (brief dips to -50 dB) to not
        trigger false positives, while sustained silence (>5s below -50 dB)
        is detected as a technical issue.
        
        Args:
            audio_chunk: Audio samples as numpy array (normalized -1.0 to 1.0 or int16)
            timestamp: Current timestamp in seconds
            
        Returns:
            SilenceResult with silence status, duration, and energy level
            
        Raises:
            ValueError: If audio_chunk is empty or invalid
        """
        if audio_chunk is None or len(audio_chunk) == 0:
            raise ValueError("Audio chunk cannot be empty")
            
        if timestamp < 0:
            raise ValueError("Timestamp must be non-negative")
            
        # Convert to float if needed
        if audio_chunk.dtype == np.int16:
            audio_chunk = audio_chunk.astype(np.float32) / 32768.0
            
        # Calculate RMS energy
        rms = np.sqrt(np.mean(audio_chunk ** 2))
        
        # Convert to dB
        if rms > 0:
            energy_db = 20 * np.log10(rms)
        else:
            # Completely silent signal
            energy_db = -100.0
            
        # Reset threshold is higher than silence threshold for hysteresis
        # This prevents flickering between silent/active states
        reset_threshold_db = -40.0
        
        # Track silence duration
        if energy_db < self.silence_threshold_db:
            # Audio is below silence threshold
            if self.silence_start_time is None:
                # Start tracking silence
                self.silence_start_time = timestamp
            
            # Calculate silence duration
            silence_duration = timestamp - self.silence_start_time
        else:
            # Audio energy is above silence threshold
            if energy_db > reset_threshold_db:
                # Strong audio signal - reset silence timer
                self.silence_start_time = None
                silence_duration = 0.0
            elif self.silence_start_time is not None:
                # Audio is between silence and reset thresholds
                # Continue tracking silence (natural pause)
                silence_duration = timestamp - self.silence_start_time
            else:
                # Not in silence period
                silence_duration = 0.0
                
        # Determine if extended silence is detected
        is_silent = silence_duration > self.duration_threshold_s
        
        return SilenceResult(
            is_silent=is_silent,
            duration_s=silence_duration,
            energy_db=energy_db
        )
    
    def reset(self):
        """
        Reset detector state.
        
        Clears the silence start time, effectively resetting the silence
        duration tracking. Useful when starting a new audio stream or
        after a known interruption.
        """
        self.silence_start_time = None
