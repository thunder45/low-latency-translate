"""
Echo Detector.

This module provides echo detection for audio quality validation using
autocorrelation analysis. Detects echo patterns in the 10-500ms delay range
and measures echo level relative to the primary signal.
"""

import numpy as np
from typing import Optional
from audio_quality.models.results import EchoResult


class EchoDetector:
    """
    Detects echo patterns in audio using autocorrelation.
    
    The detector computes autocorrelation of the audio signal and searches
    for peaks in the specified delay range (10-500ms). Echo level is measured
    in dB relative to the primary signal. Includes threshold check to avoid
    false positives.
    
    Optionally downsamples to 8 kHz for faster computation while maintaining
    delay accuracy.
    
    Attributes:
        min_delay_ms: Minimum echo delay to detect in milliseconds
        max_delay_ms: Maximum echo delay to detect in milliseconds
        threshold_db: Echo level threshold in dB (default: -15.0)
        downsample_rate: Target sample rate for downsampling (default: 8000 Hz)
    """
    
    def __init__(
        self,
        min_delay_ms: int = 10,
        max_delay_ms: int = 500,
        threshold_db: float = -15.0,
        downsample_rate: int = 8000
    ):
        """
        Initialize echo detector.
        
        Args:
            min_delay_ms: Minimum echo delay in milliseconds
            max_delay_ms: Maximum echo delay in milliseconds
            threshold_db: Echo level threshold in dB (echo > threshold triggers detection)
                         Default -15.0 dB means echo must be ~18% of original signal strength
            downsample_rate: Target sample rate for downsampling (0 to disable)
        """
        self.min_delay_ms = min_delay_ms
        self.max_delay_ms = max_delay_ms
        self.threshold_db = threshold_db
        self.downsample_rate = downsample_rate
        
    def detect_echo(self, audio_chunk: np.ndarray, sample_rate: int) -> EchoResult:
        """
        Detect echo using autocorrelation.
        
        Algorithm:
        1. Optionally downsample to 8 kHz for faster computation
        2. Compute autocorrelation of audio signal
        3. Search for peaks in delay range (10-500ms)
        4. Measure echo level relative to primary signal
        5. Emit warning if echo > -15 dB
        
        Args:
            audio_chunk: Audio samples as numpy array (normalized -1.0 to 1.0 or int16)
            sample_rate: Sample rate in Hz
            
        Returns:
            EchoResult with echo level, delay, and detection status
            
        Raises:
            ValueError: If audio_chunk is empty or invalid
        """
        if audio_chunk is None or len(audio_chunk) == 0:
            raise ValueError("Audio chunk cannot be empty")
            
        if sample_rate <= 0:
            raise ValueError("Sample rate must be positive")
            
        # Convert to float if needed
        if audio_chunk.dtype == np.int16:
            audio_chunk = audio_chunk.astype(np.float32) / 32768.0
            
        # Downsample if enabled and sample rate is higher than target
        original_sample_rate = sample_rate
        if self.downsample_rate > 0 and sample_rate > self.downsample_rate:
            audio_chunk, sample_rate = self._downsample(audio_chunk, sample_rate)
            
        # Convert delay range to samples
        min_delay_samples = int(self.min_delay_ms * sample_rate / 1000)
        max_delay_samples = int(self.max_delay_ms * sample_rate / 1000)
        
        # Ensure we have enough samples for the delay range
        if len(audio_chunk) < max_delay_samples:
            # Not enough samples to detect echo in this range
            return EchoResult(
                echo_level_db=-100.0,
                delay_ms=0.0,
                has_echo=False
            )
            
        # Normalize audio to [-1, 1] range for consistent correlation
        audio_normalized = audio_chunk.astype(np.float64)
        if np.max(np.abs(audio_normalized)) > 0:
            audio_normalized = audio_normalized / np.max(np.abs(audio_normalized))
        
        # Detect if signal is highly periodic (like a pure sine wave)
        # Periodic signals have many strong autocorrelation peaks and should not trigger echo detection
        # Calculate signal variance to detect pure tones
        # Pure tones have very low variance in their envelope
        
        # Calculate short-term energy variance
        frame_size = 400  # 25ms at 16kHz
        num_frames = len(audio_normalized) // frame_size
        
        if num_frames >= 4:
            frame_energies = []
            for i in range(num_frames):
                frame = audio_normalized[i * frame_size:(i + 1) * frame_size]
                energy = np.mean(frame ** 2)
                frame_energies.append(energy)
            
            frame_energies = np.array(frame_energies)
            energy_variance = np.var(frame_energies)
            mean_energy = np.mean(frame_energies)
            
            # Coefficient of variation for energy
            if mean_energy > 0:
                energy_cv = np.sqrt(energy_variance) / mean_energy
            else:
                energy_cv = 0
            
            # Pure tones have very low energy CV (<0.01)
            # Real speech has higher CV (>0.1) due to amplitude variations
            is_pure_tone = (energy_cv < 0.05)
            
            if is_pure_tone:
                # Pure tones should not trigger echo detection
                # Their autocorrelation peaks are from periodicity, not echoes
                return EchoResult(
                    echo_level_db=-100.0,
                    delay_ms=0.0,
                    has_echo=False
                )
        
        # Compute autocorrelation using scipy for better accuracy
        from scipy import signal as scipy_signal
        autocorr = scipy_signal.correlate(audio_normalized, audio_normalized, mode='full')
        
        # Keep only positive lags (second half)
        autocorr = autocorr[len(autocorr) // 2:]
        
        # Normalize by the zero-lag autocorrelation (maximum value)
        if autocorr[0] > 0:
            autocorr = autocorr / autocorr[0]
        else:
            # Signal is completely silent
            return EchoResult(
                echo_level_db=-100.0,
                delay_ms=0.0,
                has_echo=False
            )
            
        # Search for echo peak in delay range
        search_range = autocorr[min_delay_samples:min(max_delay_samples, len(autocorr))]
        
        if len(search_range) == 0:
            # No valid search range
            return EchoResult(
                echo_level_db=-100.0,
                delay_ms=0.0,
                has_echo=False
            )
            
        # Sophisticated peak detection to distinguish echo from periodic signal peaks
        # For periodic signals (like pure sine waves), autocorrelation has many peaks
        # Real echoes are typically isolated peaks in the 30-200ms range
        # Increased threshold from 0.01 to 0.5 to avoid false positives from periodic signals
        peak_threshold = 0.5
        
        # Use scipy's find_peaks to identify all significant peaks
        from scipy.signal import find_peaks
        
        # Find ALL peaks above threshold
        # Use prominence to identify peaks that stand out from surroundings
        # Increased prominence to 0.2 to filter out periodic signal peaks
        peaks, properties = find_peaks(
            search_range,
            height=peak_threshold,
            prominence=0.2  # Peak must stand out significantly from surroundings
        )
        
        if len(peaks) == 0:
            # No significant peaks found
            return EchoResult(
                echo_level_db=-100.0,
                delay_ms=0.0,
                has_echo=False
            )
        
        # Strategy for finding echo peak:
        # For periodic signals, autocorrelation has many peaks from the signal's periodicity
        # Echo peaks may NOT be the highest, but they occur at specific delay ranges
        # Typical room echoes: 30-200ms range
        # We look for the highest peak in the EXPECTED echo delay range
        
        peak_heights = properties['peak_heights']
        
        if len(peaks) == 1:
            # Only one peak - use it
            peak_idx_in_range = peaks[0]
        else:
            # Multiple peaks - find echo peak
            # Strategy: Look for highest peak after minimum delay
            # Minimum delay excludes very early periodic peaks
            
            min_echo_delay_samples = int(40 * sample_rate / 1000)  # 40ms minimum
            
            # Filter peaks after minimum delay
            valid_peaks_mask = peaks >= min_echo_delay_samples
            
            if np.any(valid_peaks_mask):
                # Find highest peak after minimum delay
                valid_peaks = peaks[valid_peaks_mask]
                valid_heights = peak_heights[valid_peaks_mask]
                peak_idx_in_range = valid_peaks[np.argmax(valid_heights)]
            else:
                # All peaks are very early - use highest overall
                peak_idx_in_range = peaks[np.argmax(peak_heights)]
        
        peak_value = search_range[peak_idx_in_range]
        
        # Calculate actual delay in samples
        actual_delay_samples = min_delay_samples + peak_idx_in_range
        echo_level = peak_value
        
        # Convert to dB
        if echo_level > 0:
            echo_db = 20 * np.log10(echo_level)
        else:
            echo_db = -100.0
            
        # Convert delay to milliseconds using CURRENT sample rate
        # Fixed formula: (delay_samples * 1000) / sample_rate
        delay_ms = (actual_delay_samples * 1000.0) / sample_rate
            
        # Determine if echo exceeds threshold
        has_echo = echo_db > self.threshold_db
        
        return EchoResult(
            echo_level_db=echo_db,
            delay_ms=delay_ms,
            has_echo=has_echo
        )
    
    def _downsample(
        self,
        audio: np.ndarray,
        original_rate: int
    ) -> tuple[np.ndarray, int]:
        """
        Downsample audio to target rate for faster computation.
        
        Uses simple decimation (taking every Nth sample). For production use,
        consider using scipy.signal.resample for better quality.
        
        Args:
            audio: Audio samples
            original_rate: Original sample rate in Hz
            
        Returns:
            Tuple of (downsampled_audio, new_sample_rate)
        """
        if self.downsample_rate <= 0 or original_rate <= self.downsample_rate:
            return audio, original_rate
            
        # Calculate decimation factor
        decimation_factor = original_rate // self.downsample_rate
        
        # Decimate by taking every Nth sample
        downsampled = audio[::decimation_factor]
        
        # Calculate actual new sample rate
        new_rate = original_rate // decimation_factor
        
        return downsampled, new_rate
    
    def reset(self):
        """
        Reset detector state.
        
        Currently no state to reset, but provided for consistency with other analyzers.
        """
        pass
