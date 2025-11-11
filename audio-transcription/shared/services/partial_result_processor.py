"""
Partial result processor for coordinating transcription processing.

This module provides the PartialResultProcessor class that coordinates all
sub-components for processing partial and final transcription results. It
serves as the main entry point for the partial results processing pipeline.
"""

import json
import time
import logging
import os
from typing import Optional
from shared.models.configuration import PartialResultConfig
from shared.models.transcription_results import PartialResult, FinalResult
from shared.services.partial_result_handler import PartialResultHandler
from shared.services.final_result_handler import FinalResultHandler
from shared.services.transcription_event_handler import TranscriptionEventHandler
from shared.services.result_buffer import ResultBuffer
from shared.services.deduplication_cache import DeduplicationCache
from shared.services.rate_limiter import RateLimiter
from shared.services.sentence_boundary_detector import SentenceBoundaryDetector
from shared.services.translation_forwarder import TranslationForwarder
from shared.utils.metrics import MetricsEmitter

logger = logging.getLogger(__name__)


class PartialResultProcessor:
    """
    Main processor for coordinating partial result processing.
    
    This class initializes and coordinates all sub-components:
    - TranscriptionEventHandler: Routes events to handlers
    - PartialResultHandler: Processes partial results
    - FinalResultHandler: Processes final results
    - ResultBuffer: Stores partial results
    - DeduplicationCache: Prevents duplicate synthesis
    - RateLimiter: Limits processing rate
    - SentenceBoundaryDetector: Detects sentence boundaries
    - TranslationForwarder: Forwards to translation pipeline
    
    The processor also implements opportunistic orphan cleanup that runs
    every 5 seconds to flush results that haven't received a final result
    within 15 seconds.
    
    Attributes:
        config: Configuration for partial result processing
        event_handler: Handler for transcription events
        partial_handler: Handler for partial results
        final_handler: Handler for final results
        result_buffer: Buffer for storing partial results
        dedup_cache: Cache for preventing duplicates
        rate_limiter: Rate limiter for controlling processing
        sentence_detector: Detector for sentence boundaries
        translation_forwarder: Forwarder for translation pipeline
        last_cleanup: Timestamp of last orphan cleanup
    """
    
    def __init__(
        self,
        config: Optional[PartialResultConfig] = None,
        session_id: str = "",
        source_language: str = "",
        translation_pipeline: Optional[object] = None
    ):
        """
        Initialize partial result processor with all sub-components.
        
        This method initializes all components in the correct order,
        ensuring dependencies are satisfied. Configuration can be provided
        directly or loaded from environment variables.
        
        Args:
            config: Configuration for partial result processing (optional)
            session_id: Session ID for this processor
            source_language: Source language code (ISO 639-1)
            translation_pipeline: Translation pipeline instance (optional)
        
        Examples:
            >>> # Initialize with explicit config
            >>> config = PartialResultConfig(min_stability_threshold=0.85)
            >>> processor = PartialResultProcessor(
            ...     config=config,
            ...     session_id="golden-eagle-427",
            ...     source_language="en"
            ... )
            
            >>> # Initialize with environment variables
            >>> processor = PartialResultProcessor(
            ...     session_id="golden-eagle-427",
            ...     source_language="en"
            ... )
        """
        # Load configuration from environment or use provided config
        self.config = config or self._load_config_from_environment()
        
        # Validate configuration
        self.config.validate()
        
        logger.info(
            f"Initializing PartialResultProcessor for session {session_id}, "
            f"language {source_language}"
        )
        
        # Initialize sub-components in dependency order
        
        # 0. Metrics emitter (no dependencies)
        self.metrics = MetricsEmitter()
        
        # 1. Result buffer (no dependencies)
        self.result_buffer = ResultBuffer(
            max_capacity_seconds=10  # 10 seconds of text
        )
        
        # 2. Deduplication cache (no dependencies)
        self.dedup_cache = DeduplicationCache(
            ttl_seconds=self.config.dedup_cache_ttl_seconds
        )
        
        # 3. Rate limiter (depends on metrics)
        self.rate_limiter = RateLimiter(
            max_rate=self.config.max_rate_per_second,
            window_ms=200,  # 200ms window
            metrics_emitter=self.metrics
        )
        
        # 4. Sentence boundary detector (no dependencies)
        self.sentence_detector = SentenceBoundaryDetector(
            pause_threshold_seconds=self.config.pause_threshold_seconds,
            buffer_timeout_seconds=self.config.max_buffer_timeout_seconds
        )
        
        # 5. Translation forwarder (depends on dedup_cache and metrics)
        self.translation_forwarder = TranslationForwarder(
            dedup_cache=self.dedup_cache,
            translation_pipeline=translation_pipeline,
            metrics_emitter=self.metrics
        )
        
        # 6. Partial result handler (depends on multiple components)
        self.partial_handler = PartialResultHandler(
            config=self.config,
            rate_limiter=self.rate_limiter,
            result_buffer=self.result_buffer,
            sentence_detector=self.sentence_detector,
            translation_forwarder=self.translation_forwarder
        )
        
        # 7. Final result handler (depends on buffer, cache, forwarder)
        self.final_handler = FinalResultHandler(
            result_buffer=self.result_buffer,
            dedup_cache=self.dedup_cache,
            translation_forwarder=self.translation_forwarder,
            discrepancy_threshold=20.0  # 20% threshold
        )
        
        # 8. Transcription event handler (depends on partial and final handlers)
        self.event_handler = TranscriptionEventHandler(
            partial_handler=self.partial_handler,
            final_handler=self.final_handler,
            session_id=session_id,
            source_language=source_language
        )
        
        # Initialize orphan cleanup tracking
        self.last_cleanup = time.time()
        
        # Initialize counters for partial-to-final ratio
        self.partial_count = 0
        self.final_count = 0
        self.session_id = session_id
        
        logger.info(
            f"PartialResultProcessor initialized successfully with "
            f"config: enabled={self.config.enabled}, "
            f"min_stability={self.config.min_stability_threshold}, "
            f"max_buffer_timeout={self.config.max_buffer_timeout_seconds}s"
        )
    
    def _load_config_from_environment(self) -> PartialResultConfig:
        """
        Load configuration from environment variables.
        
        This method reads configuration from Lambda environment variables,
        providing sensible defaults for all parameters.
        
        Environment variables:
        - PARTIAL_RESULTS_ENABLED: Enable/disable partial processing (default: true)
        - MIN_STABILITY_THRESHOLD: Minimum stability threshold (default: 0.85)
        - MAX_BUFFER_TIMEOUT: Maximum buffer timeout in seconds (default: 5.0)
        - PAUSE_THRESHOLD: Pause threshold in seconds (default: 2.0)
        - ORPHAN_TIMEOUT: Orphan timeout in seconds (default: 15.0)
        - MAX_RATE_PER_SECOND: Maximum rate per second (default: 5)
        - DEDUP_CACHE_TTL: Deduplication cache TTL in seconds (default: 10)
        
        Returns:
            PartialResultConfig with values from environment or defaults
        """
        return PartialResultConfig(
            enabled=os.getenv('PARTIAL_RESULTS_ENABLED', 'true').lower() == 'true',
            min_stability_threshold=float(os.getenv('MIN_STABILITY_THRESHOLD', '0.85')),
            max_buffer_timeout_seconds=float(os.getenv('MAX_BUFFER_TIMEOUT', '5.0')),
            pause_threshold_seconds=float(os.getenv('PAUSE_THRESHOLD', '2.0')),
            orphan_timeout_seconds=float(os.getenv('ORPHAN_TIMEOUT', '15.0')),
            max_rate_per_second=int(os.getenv('MAX_RATE_PER_SECOND', '5')),
            dedup_cache_ttl_seconds=int(os.getenv('DEDUP_CACHE_TTL', '10'))
        )
    
    async def process_partial(self, result: PartialResult) -> None:
        """
        Process partial transcription result asynchronously.
        
        This method handles partial results with error handling and logging.
        It also triggers opportunistic orphan cleanup if 5+ seconds have
        elapsed since the last cleanup.
        
        Args:
            result: Partial result to process
        
        Examples:
            >>> processor = PartialResultProcessor(...)
            >>> partial = PartialResult(...)
            >>> await processor.process_partial(partial)
        """
        start_time = time.time()
        
        try:
            logger.debug(
                f"Processing partial result {result.result_id} for "
                f"session {result.session_id}"
            )
            
            # Increment partial count
            self.partial_count += 1
            
            # Process the partial result
            self.partial_handler.process(result)
            
            # Emit processing latency metric
            latency_ms = (time.time() - start_time) * 1000
            self.metrics.emit_processing_latency(result.session_id, latency_ms)
            
            # Emit partial-to-final ratio metric (every 10 results)
            if (self.partial_count + self.final_count) % 10 == 0:
                self.metrics.emit_partial_to_final_ratio(
                    result.session_id,
                    self.partial_count,
                    self.final_count
                )
            
            # Opportunistic orphan cleanup
            await self._cleanup_orphans_if_needed()
            
        except Exception as e:
            logger.error(
                f"Error processing partial result {result.result_id}: {e}",
                exc_info=True
            )
            # Don't re-raise - log and continue processing
    
    async def process_final(self, result: FinalResult) -> None:
        """
        Process final transcription result asynchronously.
        
        This method handles final results with error handling and logging.
        It also triggers opportunistic orphan cleanup if 5+ seconds have
        elapsed since the last cleanup.
        
        Args:
            result: Final result to process
        
        Examples:
            >>> processor = PartialResultProcessor(...)
            >>> final = FinalResult(...)
            >>> await processor.process_final(final)
        """
        try:
            logger.debug(
                f"Processing final result {result.result_id} for "
                f"session {result.session_id}"
            )
            
            # Increment final count
            self.final_count += 1
            
            # Process the final result
            self.final_handler.process(result)
            
            # Emit partial-to-final ratio metric (every 10 results)
            if (self.partial_count + self.final_count) % 10 == 0:
                self.metrics.emit_partial_to_final_ratio(
                    result.session_id,
                    self.partial_count,
                    self.final_count
                )
            
            # Opportunistic orphan cleanup
            await self._cleanup_orphans_if_needed()
            
        except Exception as e:
            logger.error(
                f"Error processing final result {result.result_id}: {e}",
                exc_info=True
            )
            # Don't re-raise - log and continue processing
    
    async def _cleanup_orphans_if_needed(self) -> None:
        """
        Perform opportunistic orphan cleanup if 5+ seconds have elapsed.
        
        This method checks if 5 or more seconds have elapsed since the last
        cleanup. If so, it retrieves orphaned results from the buffer (results
        older than 15 seconds without a final result) and flushes them to
        translation as complete segments.
        
        This is called opportunistically during event processing rather than
        as a separate background task, which is appropriate for Lambda's
        event-driven architecture.
        """
        current_time = time.time()
        time_since_last_cleanup = current_time - self.last_cleanup
        
        # Check if 5+ seconds have elapsed
        if time_since_last_cleanup >= 5.0:
            logger.debug(
                f"Running opportunistic orphan cleanup "
                f"({time_since_last_cleanup:.1f}s since last cleanup)"
            )
            
            # Get orphaned results (older than configured timeout)
            orphaned = self.result_buffer.get_orphaned_results(
                timeout_seconds=self.config.orphan_timeout_seconds
            )
            
            if orphaned:
                logger.warning(json.dumps({
                    'event': 'orphaned_results_found',
                    'orphaned_count': len(orphaned),
                    'timeout_seconds': self.config.orphan_timeout_seconds,
                    'action': 'flushing_to_translation'
                }))
                
                # Emit metric for orphaned results
                # Use first result's session_id for metric
                if orphaned:
                    self.metrics.emit_orphaned_results_flushed(
                        orphaned[0].session_id,
                        len(orphaned)
                    )
                
                # Flush each orphaned result to translation
                for result in orphaned:
                    logger.warning(json.dumps({
                        'event': 'orphaned_result_flushed',
                        'result_id': result.result_id,
                        'session_id': result.session_id,
                        'text_preview': result.text[:50],
                        'age_seconds': round(current_time - result.added_at, 1)
                    }))
                    
                    # Forward to translation as complete segment
                    self.translation_forwarder.forward(
                        text=result.text,
                        session_id=result.session_id,
                        source_language=""  # Use empty string if not available
                    )
                    
                    # Remove from buffer
                    self.result_buffer.remove_by_id(result.result_id)
            else:
                logger.debug("No orphaned results found")
            
            # Update last cleanup timestamp
            self.last_cleanup = current_time
