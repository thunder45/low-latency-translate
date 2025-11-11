"""
Final result handler for transcription processing.

This module provides the FinalResultHandler class that processes final
transcription results, removes corresponding partial results from the buffer,
and forwards to translation with deduplication and discrepancy tracking.
"""

import json
import logging
import Levenshtein
from typing import List, Optional
from shared.models import FinalResult, BufferedResult
from shared.services.result_buffer import ResultBuffer
from shared.services.deduplication_cache import DeduplicationCache
from shared.services.translation_forwarder import TranslationForwarder

logger = logging.getLogger(__name__)


class FinalResultHandler:
    """
    Handler for processing final transcription results.
    
    This class processes final results from AWS Transcribe by:
    1. Removing corresponding partial results from the buffer
    2. Checking deduplication cache to avoid re-processing
    3. Forwarding to translation pipeline if not duplicate
    4. Logging discrepancies between partial and final results
    
    Attributes:
        result_buffer: Buffer storing partial results
        dedup_cache: Cache for preventing duplicate synthesis
        translation_forwarder: Forwarder for translation pipeline
        discrepancy_threshold: Percentage threshold for logging discrepancies (default: 20%)
    """
    
    def __init__(
        self,
        result_buffer: ResultBuffer,
        dedup_cache: DeduplicationCache,
        translation_forwarder: TranslationForwarder,
        discrepancy_threshold: float = 20.0
    ):
        """
        Initialize final result handler.
        
        Args:
            result_buffer: Result buffer instance
            dedup_cache: Deduplication cache instance
            translation_forwarder: Translation forwarder instance
            discrepancy_threshold: Percentage threshold for logging discrepancies
        """
        self.result_buffer = result_buffer
        self.dedup_cache = dedup_cache
        self.translation_forwarder = translation_forwarder
        self.discrepancy_threshold = discrepancy_threshold
        
        logger.info(
            f"FinalResultHandler initialized with "
            f"discrepancy_threshold={discrepancy_threshold}%"
        )
    
    def process(self, result: FinalResult) -> None:
        """
        Process final transcription result.
        
        This method:
        1. Removes corresponding partial results from buffer
        2. Checks deduplication cache
        3. Forwards to translation if not duplicate
        4. Logs discrepancies if partial was forwarded
        
        Args:
            result: Final result to process
            
        Examples:
            >>> handler = FinalResultHandler(buffer, cache, forwarder)
            >>> final = FinalResult(...)
            >>> handler.process(final)
        """
        # Structured logging for final result received
        logger.info(json.dumps({
            'event': 'final_result_received',
            'result_id': result.result_id,
            'session_id': result.session_id,
            'text_length': len(result.text),
            'text_preview': result.text[:50],
            'timestamp': result.timestamp
        }))
        
        # Remove corresponding partial results from buffer
        removed_partials = self._remove_corresponding_partials(result)
        
        logger.debug(json.dumps({
            'event': 'partials_removed',
            'result_id': result.result_id,
            'session_id': result.session_id,
            'partials_removed_count': len(removed_partials)
        }))
        
        # Check for discrepancies with forwarded partials
        if removed_partials:
            self._check_discrepancies(result, removed_partials)
        
        # Check deduplication cache to avoid re-processing
        if self.dedup_cache.contains(result.text):
            logger.info(json.dumps({
                'event': 'final_result_duplicate_skipped',
                'result_id': result.result_id,
                'session_id': result.session_id,
                'reason': 'already_processed'
            }))
            return
        
        # Forward to translation pipeline
        forwarded = self.translation_forwarder.forward(
            text=result.text,
            session_id=result.session_id,
            source_language=result.source_language
        )
        
        if forwarded:
            logger.info(json.dumps({
                'event': 'final_result_forwarded',
                'result_id': result.result_id,
                'session_id': result.session_id,
                'text_length': len(result.text)
            }))
        else:
            logger.debug(json.dumps({
                'event': 'final_result_not_forwarded',
                'result_id': result.result_id,
                'session_id': result.session_id,
                'reason': 'duplicate'
            }))
    
    def _remove_corresponding_partials(
        self,
        result: FinalResult
    ) -> List[BufferedResult]:
        """
        Remove partial results that correspond to this final result.
        
        This method attempts to match partial results by:
        1. Exact result_id match (if available in replaces_result_ids)
        2. Timestamp range match (within 5 seconds before final)
        
        Args:
            result: Final result to match against
            
        Returns:
            List of removed BufferedResult objects
        """
        removed = []
        
        # Strategy 1: Remove by explicit result_id if available
        if result.replaces_result_ids:
            for partial_id in result.replaces_result_ids:
                partial = self.result_buffer.remove_by_id(partial_id)
                if partial:
                    removed.append(partial)
                    logger.debug(
                        f"Removed partial {partial_id} by explicit ID match"
                    )
        
        # Strategy 2: Remove by timestamp range (within 5 seconds before final)
        # This handles cases where replaces_result_ids is not available
        if not removed:
            timestamp_window = 5.0  # seconds
            all_results = self.result_buffer.get_all()
            
            for partial in all_results:
                time_diff = result.timestamp - partial.timestamp
                if 0 <= time_diff <= timestamp_window:
                    self.result_buffer.remove_by_id(partial.result_id)
                    removed.append(partial)
                    logger.debug(
                        f"Removed partial {partial.result_id} by timestamp match "
                        f"(time_diff={time_diff:.2f}s)"
                    )
        
        return removed
    
    def _check_discrepancies(
        self,
        final: FinalResult,
        partials: List[BufferedResult]
    ) -> None:
        """
        Check and log discrepancies between final and forwarded partials.
        
        This method calculates the Levenshtein distance between the final
        result and any forwarded partial results, logging a warning if the
        difference exceeds the configured threshold.
        
        Args:
            final: Final result
            partials: List of removed partial results
        """
        # Only check partials that were forwarded
        forwarded_partials = [p for p in partials if p.forwarded]
        
        if not forwarded_partials:
            return
        
        for partial in forwarded_partials:
            # Calculate discrepancy percentage
            discrepancy_pct = self._calculate_discrepancy(
                partial.text,
                final.text
            )
            
            if discrepancy_pct > self.discrepancy_threshold:
                logger.warning(json.dumps({
                    'event': 'significant_discrepancy_detected',
                    'result_id': final.result_id,
                    'session_id': final.session_id,
                    'discrepancy_percentage': round(discrepancy_pct, 1),
                    'threshold': self.discrepancy_threshold,
                    'partial_text_preview': partial.text[:100],
                    'final_text_preview': final.text[:100]
                }))
            else:
                logger.debug(json.dumps({
                    'event': 'discrepancy_within_threshold',
                    'result_id': final.result_id,
                    'session_id': final.session_id,
                    'discrepancy_percentage': round(discrepancy_pct, 1),
                    'threshold': self.discrepancy_threshold
                }))
    
    def _calculate_discrepancy(
        self,
        partial_text: str,
        final_text: str
    ) -> float:
        """
        Calculate discrepancy percentage using Levenshtein distance.
        
        The discrepancy is calculated as:
        (edit_distance / max_length) * 100
        
        Args:
            partial_text: Text from partial result
            final_text: Text from final result
            
        Returns:
            Discrepancy percentage (0-100)
            
        Examples:
            >>> handler._calculate_discrepancy("hello world", "hello world")
            0.0
            >>> handler._calculate_discrepancy("hello", "hello world")
            54.5  # 6 edits / 11 chars * 100
        """
        # Calculate Levenshtein distance
        distance = Levenshtein.distance(partial_text, final_text)
        
        # Calculate max length for normalization
        max_length = max(len(partial_text), len(final_text))
        
        # Avoid division by zero
        if max_length == 0:
            return 0.0
        
        # Calculate percentage difference
        discrepancy_pct = (distance / max_length) * 100
        
        return discrepancy_pct

