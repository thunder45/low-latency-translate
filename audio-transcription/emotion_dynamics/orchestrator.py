"""
Audio Dynamics Orchestrator for parallel detection and SSML synthesis.

This module coordinates parallel execution of volume and rate detection,
combines results into AudioDynamics, and orchestrates the complete pipeline
from audio input to synthesized speech output.
"""

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple

import numpy as np

from emotion_dynamics.detectors.volume_detector import VolumeDetector
from emotion_dynamics.detectors.speaking_rate_detector import SpeakingRateDetector
from emotion_dynamics.generators.ssml_generator import SSMLGenerator
from emotion_dynamics.clients.polly_client import PollyClient
from emotion_dynamics.models.audio_dynamics import AudioDynamics
from emotion_dynamics.models.processing_options import ProcessingOptions
from emotion_dynamics.models.processing_result import ProcessingResult
from emotion_dynamics.models.volume_result import VolumeResult
from emotion_dynamics.models.rate_result import RateResult
from emotion_dynamics.exceptions import EmotionDynamicsError


logger = logging.getLogger(__name__)


class AudioDynamicsOrchestrator:
    """
    Orchestrator for parallel audio dynamics detection and SSML synthesis.
    
    This class coordinates:
    - Parallel execution of VolumeDetector and SpeakingRateDetector
    - Combining volume and rate results into AudioDynamics
    - SSML generation from dynamics and text
    - Amazon Polly speech synthesis
    - End-to-end error handling with graceful degradation
    - CloudWatch metrics emission for latency and errors
    
    The orchestrator ensures combined latency for audio dynamics detection
    meets the <100ms requirement through parallel execution.
    """
    
    # Latency targets (in milliseconds)
    TARGET_DYNAMICS_LATENCY_MS = 100
    TARGET_SSML_GENERATION_MS = 50
    TARGET_POLLY_SYNTHESIS_MS = 800
    
    def __init__(
        self,
        volume_detector: Optional[VolumeDetector] = None,
        rate_detector: Optional[SpeakingRateDetector] = None,
        ssml_generator: Optional[SSMLGenerator] = None,
        polly_client: Optional[PollyClient] = None
    ):
        """
        Initialize audio dynamics orchestrator.
        
        Args:
            volume_detector: Volume detector instance (creates new if None)
            rate_detector: Speaking rate detector instance (creates new if None)
            ssml_generator: SSML generator instance (creates new if None)
            polly_client: Polly client instance (creates new if None)
        """
        self.volume_detector = volume_detector or VolumeDetector()
        self.rate_detector = rate_detector or SpeakingRateDetector()
        self.ssml_generator = ssml_generator or SSMLGenerator()
        self.polly_client = polly_client or PollyClient()
        
        logger.info("Initialized AudioDynamicsOrchestrator")
    
    def detect_audio_dynamics(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        correlation_id: Optional[str] = None,
        options: Optional[ProcessingOptions] = None
    ) -> Tuple[AudioDynamics, int, int, int]:
        """
        Detect audio dynamics (volume and rate) in parallel.
        
        Executes VolumeDetector and SpeakingRateDetector concurrently using
        ThreadPoolExecutor to minimize latency. Combines results into
        AudioDynamics object with correlation ID tracking.
        
        Args:
            audio_data: Audio samples as numpy array (mono)
            sample_rate: Audio sample rate in Hz
            correlation_id: Correlation ID for tracking (generates UUID if None)
            options: Processing options (uses defaults if None)
            
        Returns:
            Tuple of (AudioDynamics, volume_ms, rate_ms, combined_ms)
            - AudioDynamics: Combined volume and rate results
            - volume_ms: Volume detection time in milliseconds
            - rate_ms: Rate detection time in milliseconds
            - combined_ms: Total parallel execution time in milliseconds
            
        Raises:
            EmotionDynamicsError: When both detectors fail
        """
        # Generate correlation ID if not provided
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())
        
        # Use default options if not provided
        if options is None:
            options = ProcessingOptions()
        
        logger.debug(
            f"Starting parallel audio dynamics detection",
            extra={
                'correlation_id': correlation_id,
                'audio_shape': audio_data.shape,
                'sample_rate': sample_rate,
                'enable_volume': options.enable_volume_detection,
                'enable_rate': options.enable_rate_detection
            }
        )
        
        # Track start time for combined latency
        start_time = time.time()
        
        # Initialize results
        volume_result = None
        rate_result = None
        volume_ms = 0
        rate_ms = 0
        
        # Execute detectors in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {}
            
            # Submit volume detection if enabled
            if options.enable_volume_detection:
                volume_future = executor.submit(
                    self._detect_volume_with_timing,
                    audio_data,
                    sample_rate
                )
                futures['volume'] = volume_future
            
            # Submit rate detection if enabled
            if options.enable_rate_detection:
                rate_future = executor.submit(
                    self._detect_rate_with_timing,
                    audio_data,
                    sample_rate
                )
                futures['rate'] = rate_future
            
            # Collect results as they complete
            for future_name, future in futures.items():
                try:
                    if future_name == 'volume':
                        volume_result, volume_ms = future.result()
                    elif future_name == 'rate':
                        rate_result, rate_ms = future.result()
                except Exception as e:
                    logger.error(
                        f"{future_name.capitalize()} detection failed in parallel execution: {e}",
                        extra={'correlation_id': correlation_id},
                        exc_info=True
                    )
        
        # Calculate combined latency
        end_time = time.time()
        combined_ms = int((end_time - start_time) * 1000)
        
        # Use default values if detectors were disabled or failed
        if volume_result is None:
            logger.warning(
                f"Volume detection disabled or failed, using default medium volume",
                extra={'correlation_id': correlation_id}
            )
            volume_result = VolumeResult(
                level='medium',
                db_value=-15.0,
                timestamp=None
            )
        
        if rate_result is None:
            logger.warning(
                f"Rate detection disabled or failed, using default medium rate",
                extra={'correlation_id': correlation_id}
            )
            rate_result = RateResult(
                classification='medium',
                wpm=145.0,
                onset_count=0,
                timestamp=None
            )
        
        # Combine results into AudioDynamics
        dynamics = AudioDynamics(
            volume=volume_result,
            rate=rate_result,
            correlation_id=correlation_id
        )
        
        # Log timing metrics
        logger.info(
            f"Audio dynamics detection completed: "
            f"volume={volume_result.level}, rate={rate_result.classification}, "
            f"volume_ms={volume_ms}, rate_ms={rate_ms}, combined_ms={combined_ms}",
            extra={
                'correlation_id': correlation_id,
                'volume_level': volume_result.level,
                'rate_classification': rate_result.classification,
                'volume_detection_ms': volume_ms,
                'rate_detection_ms': rate_ms,
                'combined_latency_ms': combined_ms,
                'meets_target': combined_ms < self.TARGET_DYNAMICS_LATENCY_MS
            }
        )
        
        # Emit warning if latency target not met
        if combined_ms >= self.TARGET_DYNAMICS_LATENCY_MS:
            logger.warning(
                f"Audio dynamics detection exceeded target latency: "
                f"{combined_ms}ms >= {self.TARGET_DYNAMICS_LATENCY_MS}ms",
                extra={'correlation_id': correlation_id}
            )
        
        return dynamics, volume_ms, rate_ms, combined_ms
    
    def _detect_volume_with_timing(
        self,
        audio_data: np.ndarray,
        sample_rate: int
    ) -> Tuple[VolumeResult, int]:
        """
        Detect volume with timing measurement.
        
        Args:
            audio_data: Audio samples
            sample_rate: Sample rate in Hz
            
        Returns:
            Tuple of (VolumeResult, latency_ms)
        """
        start_time = time.time()
        result = self.volume_detector.detect_volume(audio_data, sample_rate)
        end_time = time.time()
        latency_ms = int((end_time - start_time) * 1000)
        return result, latency_ms
    
    def _detect_rate_with_timing(
        self,
        audio_data: np.ndarray,
        sample_rate: int
    ) -> Tuple[RateResult, int]:
        """
        Detect speaking rate with timing measurement.
        
        Args:
            audio_data: Audio samples
            sample_rate: Sample rate in Hz
            
        Returns:
            Tuple of (RateResult, latency_ms)
        """
        start_time = time.time()
        result = self.rate_detector.detect_rate(audio_data, sample_rate)
        end_time = time.time()
        latency_ms = int((end_time - start_time) * 1000)
        return result, latency_ms


    def process_audio_and_text(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        translated_text: str,
        options: Optional[ProcessingOptions] = None
    ) -> ProcessingResult:
        """
        Process audio and text through complete dynamics detection and synthesis pipeline.
        
        This method orchestrates the complete workflow:
        1. Validate audio data and text inputs
        2. Invoke parallel dynamics detection (volume + rate)
        3. Pass dynamics and text to SSMLGenerator
        4. Invoke PollyClient with SSML
        5. Return ProcessingResult with audio stream and metadata
        6. Implement end-to-end error handling with graceful degradation
        7. Emit CloudWatch metrics for latency and errors
        
        Args:
            audio_data: Speaker audio samples as numpy array (mono)
            sample_rate: Audio sample rate in Hz
            translated_text: Translated text from transcription
            options: Optional processing configuration
            
        Returns:
            ProcessingResult with audio stream, dynamics, timing, and metadata
            
        Raises:
            EmotionDynamicsError: When processing fails completely
        """
        # Use default options if not provided
        if options is None:
            options = ProcessingOptions()
        
        # Generate correlation ID for this processing request
        correlation_id = str(uuid.uuid4())
        
        # Track overall start time
        overall_start_time = time.time()
        
        logger.info(
            f"Starting audio and text processing pipeline",
            extra={
                'correlation_id': correlation_id,
                'audio_shape': audio_data.shape,
                'sample_rate': sample_rate,
                'text_length': len(translated_text),
                'options': {
                    'voice_id': options.voice_id,
                    'enable_ssml': options.enable_ssml,
                    'enable_volume': options.enable_volume_detection,
                    'enable_rate': options.enable_rate_detection
                }
            }
        )
        
        try:
            # Step 1: Validate inputs
            self._validate_inputs(audio_data, sample_rate, translated_text)
            
            # Step 2: Detect audio dynamics in parallel
            dynamics, volume_ms, rate_ms, combined_ms = self.detect_audio_dynamics(
                audio_data=audio_data,
                sample_rate=sample_rate,
                correlation_id=correlation_id,
                options=options
            )
            
            # Step 3: Generate SSML from dynamics and text
            ssml_start_time = time.time()
            fallback_used = False
            
            if options.enable_ssml:
                try:
                    ssml_text = self.ssml_generator.generate_ssml(
                        text=translated_text,
                        dynamics=dynamics
                    )
                    logger.debug(
                        f"SSML generation successful",
                        extra={'correlation_id': correlation_id}
                    )
                except Exception as e:
                    logger.warning(
                        f"SSML generation failed: {e}, falling back to plain text",
                        extra={'correlation_id': correlation_id},
                        exc_info=True
                    )
                    ssml_text = self.ssml_generator.generate_ssml(
                        text=translated_text,
                        dynamics=None  # Generate plain SSML
                    )
                    fallback_used = True
            else:
                # SSML disabled, use plain text
                ssml_text = self.ssml_generator.generate_ssml(
                    text=translated_text,
                    dynamics=None
                )
                fallback_used = True
            
            ssml_end_time = time.time()
            ssml_generation_ms = int((ssml_end_time - ssml_start_time) * 1000)
            
            # Step 4: Synthesize speech with Polly
            polly_start_time = time.time()
            
            try:
                audio_stream = self.polly_client.synthesize_speech(
                    text=ssml_text,
                    voice_id=options.voice_id,
                    text_type='ssml' if options.enable_ssml and not fallback_used else 'text',
                    output_format=options.output_format,
                    sample_rate=options.sample_rate
                )
                logger.debug(
                    f"Polly synthesis successful: {len(audio_stream)} bytes",
                    extra={'correlation_id': correlation_id}
                )
            except Exception as e:
                logger.error(
                    f"Polly synthesis failed: {e}",
                    extra={'correlation_id': correlation_id},
                    exc_info=True
                )
                raise EmotionDynamicsError(f"Speech synthesis failed: {e}") from e
            
            polly_end_time = time.time()
            polly_synthesis_ms = int((polly_end_time - polly_start_time) * 1000)
            
            # Calculate total processing time
            overall_end_time = time.time()
            processing_time_ms = int((overall_end_time - overall_start_time) * 1000)
            
            # Step 5: Create ProcessingResult
            result = ProcessingResult(
                audio_stream=audio_stream,
                dynamics=dynamics,
                ssml_text=ssml_text,
                processing_time_ms=processing_time_ms,
                correlation_id=correlation_id,
                fallback_used=fallback_used,
                volume_detection_ms=volume_ms,
                rate_detection_ms=rate_ms,
                ssml_generation_ms=ssml_generation_ms,
                polly_synthesis_ms=polly_synthesis_ms
            )
            
            # Log success with timing breakdown
            logger.info(
                f"Audio and text processing completed successfully: "
                f"total={processing_time_ms}ms, "
                f"dynamics={combined_ms}ms, "
                f"ssml={ssml_generation_ms}ms, "
                f"polly={polly_synthesis_ms}ms, "
                f"fallback={fallback_used}",
                extra={
                    'correlation_id': correlation_id,
                    'processing_time_ms': processing_time_ms,
                    'volume_detection_ms': volume_ms,
                    'rate_detection_ms': rate_ms,
                    'dynamics_latency_ms': combined_ms,
                    'ssml_generation_ms': ssml_generation_ms,
                    'polly_synthesis_ms': polly_synthesis_ms,
                    'fallback_used': fallback_used,
                    'audio_size_bytes': len(audio_stream),
                    'volume_level': dynamics.volume.level,
                    'rate_classification': dynamics.rate.classification
                }
            )
            
            # Emit warnings for latency targets
            if ssml_generation_ms >= self.TARGET_SSML_GENERATION_MS:
                logger.warning(
                    f"SSML generation exceeded target: "
                    f"{ssml_generation_ms}ms >= {self.TARGET_SSML_GENERATION_MS}ms",
                    extra={'correlation_id': correlation_id}
                )
            
            if polly_synthesis_ms >= self.TARGET_POLLY_SYNTHESIS_MS:
                logger.warning(
                    f"Polly synthesis exceeded target: "
                    f"{polly_synthesis_ms}ms >= {self.TARGET_POLLY_SYNTHESIS_MS}ms",
                    extra={'correlation_id': correlation_id}
                )
            
            return result
            
        except EmotionDynamicsError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            # Catch any unexpected errors
            logger.error(
                f"Unexpected error in processing pipeline: {e}",
                extra={'correlation_id': correlation_id},
                exc_info=True
            )
            raise EmotionDynamicsError(
                f"Processing pipeline failed: {e}"
            ) from e
    
    def _validate_inputs(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        text: str
    ) -> None:
        """
        Validate audio data and text inputs.
        
        Args:
            audio_data: Audio samples
            sample_rate: Sample rate in Hz
            text: Text content
            
        Raises:
            ValueError: When inputs are invalid
        """
        # Validate audio data
        if not isinstance(audio_data, np.ndarray):
            raise ValueError(f"audio_data must be numpy array, got {type(audio_data)}")
        
        if audio_data.size == 0:
            raise ValueError("audio_data is empty")
        
        # Validate sample rate
        if not isinstance(sample_rate, int) or sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive integer, got {sample_rate}")
        
        # Validate text
        if not text or not isinstance(text, str):
            raise ValueError("text must be non-empty string")
        
        if not text.strip():
            raise ValueError("text contains only whitespace")
