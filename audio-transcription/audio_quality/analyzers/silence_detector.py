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
        last_timestamp: Timestamp of last detect_silence call
    """
    
    def __init__(
        self,
        silence_threshold_db: float = -50.0,
        duration_threshold_s: float = 5.0,
        sample_rate: int = 16000
    ):
        """
        Initialize silence detector.
        
        Args:
            silence_threshold_db: Energy threshold in dB (default: -50.0)
            duration_threshold_s: Duration threshold in seconds (default: 5.0)
            sample_rate: Audio sample rate in Hz (default: 16000)
        """
        self.silence_threshold_db = silence_threshold_db
        self.duration_threshold_s = duration_threshold_s
        self.sample_rate = sample_rate
        self.silence_start_time: Optional[float] = None
        self.last_timestamp: Optional[float] = None
        
    def detect_silence(
        self,
        audio_chunk: np.ndarray,
        timestamp: float
    ) -> SilenceResult:
        """
        Detect extended silence periods.
        
        Algorithm:
        1. Calculate RMS energy in dB
        2. Track continuous silence duration across calls
        3. Emit warning if silence > 5 seconds
        4. Reset on audio activity
        
        Key fix: Properly maintain silence_start_time across calls.
        The timestamp parameter represents when this chunk was received,
        and we calculate duration by tracking when silence started.
        
        Args:
            audio_chunk: Audio samples as numpy array (normalized -1.0 to 1.0 or int16)
            timestamp: Current timestamp in seconds (when this chunk was received)
            
        Returns:
            SilenceResult with silence status, duration, and energy level
            
        Raises:
            ValueError: If audio_chunk is empty or invalid
        """
        if audio_chunk is None or len(audio_chunk) == 0:
            raise ValueError("Audio chunk cannot be empty")
            
        if timestamp < 0:
            raise ValueError("Timestamp must be non-negative")
            
        # Normalize to [-1, 1] if int16
        if audio_chunk.dtype == np.int16:
            audio_normalized = audio_chunk.astype(np.float64) / 32768.0
        else:
            audio_normalized = audio_chunk.astype(np.float64)
            
        # Calculate chunk duration from audio length
        chunk_duration_s = len(audio_normalized) / self.sample_rate
            
        # Calculate RMS energy
        rms = np.sqrt(np.mean(audio_normalized ** 2))
        
        # Convert to dB
        if rms > 1e-10:
            energy_db = 20 * np.log10(rms)
        else:
            # Completely silent signal
            energy_db = -100.0
            
        # Check if current chunk is silent
        is_chunk_silent = energy_db < self.silence_threshold_db
        
        if is_chunk_silent:
            # Silent chunk
            if self.silence_start_time is None:
                # Start tracking silence
                self.silence_start_time = timestamp
            
            # Calculate duration
            # For streaming chunks: timestamp represents the start of the chunk
            # For single long chunks: we add chunk_duration_s to account for the full duration
            # We use the end of the chunk (timestamp + chunk_duration_s) to get accurate duration
            silence_duration = (timestamp + chunk_duration_s) - self.silence_start_time
        else:
            # Not silent - reset tracking
            self.silence_start_time = None
            silence_duration = 0.0
        
        # Update last timestamp
        self.last_timestamp = timestamp + chunk_duration_s
        
        # Determine if silence exceeds threshold
        # Use >= to trigger at or above threshold
        # This allows detection at exactly the threshold duration
        is_silent = silence_duration >= self.duration_threshold_s
        
        return SilenceResult(
            is_silent=bool(is_silent),
            duration_s=float(silence_duration),
            energy_db=float(energy_db)
        )
    
    def reset(self):
        """
        Reset detector state.
        
        Clears the silence start time and last timestamp, effectively 
        resetting the silence duration tracking. Useful when starting 
        a new audio stream or after a known interruption.
        """
        self.silence_start_time = None
        self.last_timestamp = None
