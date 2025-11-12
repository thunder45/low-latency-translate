"""
Audio Quality Analyzer.

This module provides the AudioQualityAnalyzer class that aggregates all
quality detection components (SNR, clipping, echo, silence) and produces
comprehensive quality metrics for audio streams.
"""

import time
import numpy as np
from typing import Optional

from audio_quality.models.quality_config import QualityConfig
from audio_quality.models.quality_metrics import QualityMetrics
from audio_quality.analyzers.snr_calculator import SNRCalculator
from audio_quality.analyzers.clipping_detector import ClippingDetector
from audio_quality.analyzers.echo_detector import EchoDetector
from audio_quality.analyzers.silence_detector import SilenceDetector
from audio_quality.utils.structured_logger import (
    log_analysis_operation,
    log_quality_metrics,
    log_quality_issue,
)
from audio_quality.utils.xray_tracing import trace_audio_analysis, XRayContext


class AudioQualityAnalyzer:
    """
    Analyzes audio quality metrics in real-time.
    
    This class coordinates all quality detection components and aggregates
    their results into a single QualityMetrics object. It initializes and
    manages SNR calculation, clipping detection, echo detection, and silence
    detection.
    
    The analyzer is designed for real-time processing of audio streams,
    maintaining state across multiple audio chunks for temporal analysis
    (e.g., rolling SNR averages, silence duration tracking).
    
    Attributes:
        config: Quality configuration parameters
        snr_calculator: SNR calculation component
        clipping_detector: Clipping detection component
        echo_detector: Echo detection component
        silence_detector: Silence detection component
    """
    
    def __init__(self, config: Optional[QualityConfig] = None):
        """
        Initialize audio quality analyzer.
        
        Creates and configures all detector components based on the provided
        configuration. If no configuration is provided, uses default values.
        
        Args:
            config: Quality configuration parameters. If None, uses defaults.
            
        Raises:
            ValueError: If configuration validation fails
        """
        # Use default config if none provided
        self.config = config if config is not None else QualityConfig()
        
        # Validate configuration
        errors = self.config.validate()
        if errors:
            raise ValueError(f"Invalid configuration: {', '.join(errors)}")
        
        # Initialize all detector components
        self.snr_calculator = SNRCalculator(
            window_size=self.config.snr_window_size_s
        )
        
        self.clipping_detector = ClippingDetector(
            threshold_percent=self.config.clipping_amplitude_percent,
            window_ms=self.config.clipping_window_ms
        )
        
        self.echo_detector = EchoDetector(
            min_delay_ms=self.config.echo_min_delay_ms,
            max_delay_ms=self.config.echo_max_delay_ms,
            threshold_db=self.config.echo_threshold_db
        )
        
        self.silence_detector = SilenceDetector(
            silence_threshold_db=self.config.silence_threshold_db,
            duration_threshold_s=self.config.silence_duration_threshold_s
        )
    
    @trace_audio_analysis
    def analyze(
        self,
        audio_chunk: np.ndarray,
        sample_rate: int,
        stream_id: str = 'unknown',
        timestamp: Optional[float] = None
    ) -> QualityMetrics:
        """
        Analyzes audio chunk and returns comprehensive quality metrics.
        
        Runs all quality detectors (SNR, clipping, echo, silence) on the
        provided audio chunk and aggregates their results into a single
        QualityMetrics object.
        
        The method maintains state across calls for temporal analysis:
        - SNR rolling average over configured window
        - Silence duration tracking
        
        Algorithm:
        1. Calculate SNR and rolling average
        2. Detect clipping
        3. Detect echo patterns
        4. Detect extended silence
        5. Aggregate all results into QualityMetrics
        
        Args:
            audio_chunk: Audio samples as numpy array. Can be:
                        - int16 PCM samples (range: -32768 to 32767)
                        - Normalized float samples (range: -1.0 to 1.0)
            sample_rate: Sample rate in Hz (e.g., 8000, 16000, 24000, 48000)
            stream_id: Identifier for the audio stream (default: 'unknown')
            timestamp: Current timestamp in seconds. If None, uses current time.
            
        Returns:
            QualityMetrics containing all quality measurements:
                - SNR (current and rolling average)
                - Clipping (percentage, count, status)
                - Echo (level, delay, status)
                - Silence (status, duration, energy)
                
        Raises:
            ValueError: If audio_chunk is empty or invalid
            ValueError: If sample_rate is not positive
            
        Examples:
            >>> config = QualityConfig(snr_threshold_db=20.0)
            >>> analyzer = AudioQualityAnalyzer(config)
            >>> audio = np.random.randn(16000).astype(np.int16)
            >>> metrics = analyzer.analyze(audio, sample_rate=16000, stream_id='session-123')
            >>> print(f"SNR: {metrics.snr_db:.1f} dB")
            SNR: 18.5 dB
        """
        # Validate inputs
        if audio_chunk is None or len(audio_chunk) == 0:
            raise ValueError("audio_chunk cannot be empty")
        
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        
        # Use current time if timestamp not provided
        if timestamp is None:
            timestamp = time.time()
        
        # Track overall analysis time
        start_time = time.perf_counter()
        
        # Run all detectors
        
        # 1. Calculate SNR
        with XRayContext('calculate_snr', {'stream_id': stream_id}):
            snr_start = time.perf_counter()
            snr_db = self.snr_calculator.calculate_snr(audio_chunk)
            snr_rolling_avg = self.snr_calculator.get_rolling_average()
            snr_duration = (time.perf_counter() - snr_start) * 1000
            log_analysis_operation(stream_id, 'calculate_snr', snr_duration)
        
        # If no rolling average yet (first call), use current SNR
        if snr_rolling_avg is None:
            snr_rolling_avg = snr_db
        
        # 2. Detect clipping
        with XRayContext('detect_clipping', {'stream_id': stream_id}):
            clipping_start = time.perf_counter()
            clipping_result = self.clipping_detector.detect_clipping(
                audio_chunk,
                bit_depth=16,
                clipping_threshold_percent=self.config.clipping_threshold_percent
            )
            clipping_duration = (time.perf_counter() - clipping_start) * 1000
            log_analysis_operation(stream_id, 'detect_clipping', clipping_duration)
        
        # 3. Detect echo
        with XRayContext('detect_echo', {'stream_id': stream_id}):
            echo_start = time.perf_counter()
            echo_result = self.echo_detector.detect_echo(audio_chunk, sample_rate)
            echo_duration = (time.perf_counter() - echo_start) * 1000
            log_analysis_operation(stream_id, 'detect_echo', echo_duration)
        
        # 4. Detect silence
        with XRayContext('detect_silence', {'stream_id': stream_id}):
            silence_start = time.perf_counter()
            silence_result = self.silence_detector.detect_silence(audio_chunk, timestamp)
            silence_duration = (time.perf_counter() - silence_start) * 1000
            log_analysis_operation(stream_id, 'detect_silence', silence_duration)
        
        # 5. Aggregate results into QualityMetrics
        metrics = QualityMetrics(
            timestamp=timestamp,
            stream_id=stream_id,
            # SNR metrics
            snr_db=snr_db,
            snr_rolling_avg=snr_rolling_avg,
            # Clipping metrics
            clipping_percentage=clipping_result.percentage,
            clipped_sample_count=clipping_result.clipped_count,
            is_clipping=clipping_result.is_clipping,
            # Echo metrics
            echo_level_db=echo_result.echo_level_db,
            echo_delay_ms=echo_result.delay_ms,
            has_echo=echo_result.has_echo,
            # Silence metrics
            is_silent=silence_result.is_silent,
            silence_duration_s=silence_result.duration_s,
            energy_db=silence_result.energy_db
        )
        
        # Log overall analysis time
        total_duration = (time.perf_counter() - start_time) * 1000
        log_analysis_operation(stream_id, 'analyze_audio_quality', total_duration)
        
        # Log quality metrics
        log_quality_metrics(stream_id, metrics, level='DEBUG')
        
        # Log quality issues if thresholds violated
        if snr_db < self.config.snr_threshold_db:
            log_quality_issue(
                stream_id,
                'snr_low',
                {'snr': snr_db, 'threshold': self.config.snr_threshold_db},
                severity='warning'
            )
        
        if clipping_result.is_clipping:
            log_quality_issue(
                stream_id,
                'clipping',
                {
                    'percentage': clipping_result.percentage,
                    'threshold': self.config.clipping_threshold_percent
                },
                severity='warning'
            )
        
        if echo_result.has_echo:
            log_quality_issue(
                stream_id,
                'echo',
                {
                    'echo_db': echo_result.echo_level_db,
                    'delay_ms': echo_result.delay_ms,
                    'threshold': self.config.echo_threshold_db
                },
                severity='warning'
            )
        
        if silence_result.is_silent:
            log_quality_issue(
                stream_id,
                'silence',
                {
                    'duration': silence_result.duration_s,
                    'threshold': self.config.silence_duration_threshold_s
                },
                severity='warning'
            )
        
        return metrics
    
    def reset(self):
        """
        Reset all detector states.
        
        Clears all temporal state maintained by the detectors:
        - SNR rolling window history
        - Silence duration tracking
        
        This should be called when starting a new audio stream or after
        a known interruption to prevent stale state from affecting analysis.
        
        Examples:
            >>> analyzer = AudioQualityAnalyzer()
            >>> # Process some audio...
            >>> analyzer.reset()  # Start fresh for new stream
        """
        self.snr_calculator.reset()
        self.echo_detector.reset()
        self.silence_detector.reset()
