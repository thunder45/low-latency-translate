"""
Result buffer for storing partial results awaiting finalization.

This module provides a buffer implementation that stores partial results
with capacity management, orphan detection, and timestamp-based ordering.
"""

import time
import logging
from typing import Dict, List, Optional
from shared.models import BufferedResult, PartialResult

logger = logging.getLogger(__name__)


class ResultBuffer:
    """
    Buffer for storing partial results awaiting finalization.
    
    This buffer stores partial results with automatic capacity management,
    orphan detection, and timestamp-based ordering. It ensures that the
    buffer doesn't grow unbounded and handles cases where final results
    never arrive.
    
    Attributes:
        buffer: Dictionary mapping result_id to BufferedResult
        max_capacity_seconds: Maximum buffer capacity in seconds of text (default: 10)
        words_per_second: Estimated words per second for capacity calculation (default: 30)
    """
    
    def __init__(self, max_capacity_seconds: int = 10):
        """
        Initialize result buffer.
        
        Args:
            max_capacity_seconds: Maximum buffer capacity in seconds of text
        """
        self.buffer: Dict[str, BufferedResult] = {}
        self.max_capacity_seconds = max_capacity_seconds
        self.words_per_second = 30  # Estimated words per second
        
        logger.info(
            f"ResultBuffer initialized with max_capacity={max_capacity_seconds}s "
            f"(~{max_capacity_seconds * self.words_per_second} words)"
        )
    
    def add(self, result: PartialResult) -> None:
        """
        Add partial result to buffer.
        
        This method converts a PartialResult to a BufferedResult and stores
        it in the buffer. If the buffer is at capacity, it flushes the oldest
        stable results first.
        
        Args:
            result: PartialResult to add to buffer
            
        Examples:
            >>> buffer = ResultBuffer()
            >>> result = PartialResult(...)
            >>> buffer.add(result)
        """
        # Check capacity before adding
        if self._is_at_capacity():
            logger.warning(
                f"Buffer at capacity ({self.size()} entries), "
                "flushing oldest stable results"
            )
            self._flush_oldest_stable()
        
        # Convert to BufferedResult
        buffered = BufferedResult(
            result_id=result.result_id,
            text=result.text,
            stability_score=result.stability_score,
            timestamp=result.timestamp,
            added_at=time.time(),
            forwarded=False,
            session_id=result.session_id
        )
        
        # Add to buffer
        self.buffer[result.result_id] = buffered
        
        logger.debug(
            f"Added to buffer: {result.result_id} "
            f"(buffer size: {self.size()}, text: {result.text[:50]}...)"
        )
    
    def remove_by_id(self, result_id: str) -> Optional[BufferedResult]:
        """
        Remove specific result from buffer by ID.
        
        Args:
            result_id: ID of result to remove
            
        Returns:
            Removed BufferedResult if found, None otherwise
            
        Examples:
            >>> buffer = ResultBuffer()
            >>> buffer.add(result)
            >>> removed = buffer.remove_by_id('result-123')
        """
        if result_id in self.buffer:
            removed = self.buffer.pop(result_id)
            logger.debug(f"Removed from buffer: {result_id}")
            return removed
        
        logger.debug(f"Result not found in buffer: {result_id}")
        return None
    
    def get_all(self) -> List[BufferedResult]:
        """
        Get all buffered results.
        
        Returns:
            List of all BufferedResult objects in buffer
            
        Examples:
            >>> buffer = ResultBuffer()
            >>> all_results = buffer.get_all()
        """
        return list(self.buffer.values())
    
    def get_orphaned_results(self, timeout_seconds: float = 15.0) -> List[BufferedResult]:
        """
        Get results older than timeout without final result.
        
        Orphaned results are partial results that have been in the buffer
        longer than the timeout period, indicating that a final result
        may never arrive.
        
        Args:
            timeout_seconds: Age threshold for orphaned results (default: 15.0)
            
        Returns:
            List of BufferedResult objects older than timeout
            
        Examples:
            >>> buffer = ResultBuffer()
            >>> orphaned = buffer.get_orphaned_results(timeout_seconds=15.0)
        """
        current_time = time.time()
        orphaned = []
        
        for result in self.buffer.values():
            age = current_time - result.added_at
            if age > timeout_seconds:
                orphaned.append(result)
        
        if orphaned:
            logger.debug(
                f"Found {len(orphaned)} orphaned results "
                f"(older than {timeout_seconds}s)"
            )
        
        return orphaned
    
    def sort_by_timestamp(self) -> List[BufferedResult]:
        """
        Get all results sorted by timestamp (oldest first).
        
        This method is used to process results in chronological order,
        which is important for handling out-of-order results.
        
        Returns:
            List of BufferedResult objects sorted by timestamp
            
        Examples:
            >>> buffer = ResultBuffer()
            >>> sorted_results = buffer.sort_by_timestamp()
        """
        return sorted(self.buffer.values(), key=lambda r: r.timestamp)
    
    def size(self) -> int:
        """
        Get current buffer size (number of entries).
        
        Returns:
            Number of results in buffer
        """
        return len(self.buffer)
    
    def clear(self) -> None:
        """
        Clear all entries from buffer.
        
        This method removes all entries. Useful for testing or
        manual buffer management.
        """
        self.buffer.clear()
        logger.info("Buffer cleared")
    
    def _is_at_capacity(self) -> bool:
        """
        Check if buffer is at capacity.
        
        Capacity is calculated based on total word count in buffer
        compared to maximum capacity (words_per_second * max_capacity_seconds).
        
        Returns:
            True if buffer is at or over capacity
        """
        total_words = sum(len(r.text.split()) for r in self.buffer.values())
        max_words = self.words_per_second * self.max_capacity_seconds
        
        return total_words >= max_words
    
    def _flush_oldest_stable(self, count: int = 5) -> List[BufferedResult]:
        """
        Flush oldest stable results when capacity exceeded.
        
        This method removes the oldest results with high stability scores
        to make room for new results. Results are considered stable if they
        have a stability score >= 0.85 or if stability is unavailable.
        
        Args:
            count: Number of results to flush (default: 5)
            
        Returns:
            List of flushed BufferedResult objects
        """
        # Get stable results (stability >= 0.85 or None)
        stable_results = [
            r for r in self.buffer.values()
            if r.stability_score is None or r.stability_score >= 0.85
        ]
        
        # Sort by timestamp (oldest first)
        stable_results.sort(key=lambda r: r.timestamp)
        
        # Take oldest N results
        to_flush = stable_results[:count]
        
        # Remove from buffer
        for result in to_flush:
            self.buffer.pop(result.result_id)
        
        if to_flush:
            logger.warning(
                f"Flushed {len(to_flush)} oldest stable results "
                f"(buffer capacity exceeded)"
            )
        
        return to_flush
    
    def mark_as_forwarded(self, result_id: str) -> bool:
        """
        Mark a result as forwarded to translation.
        
        This method updates the forwarded flag to track which results
        have already been sent to the translation pipeline.
        
        Args:
            result_id: ID of result to mark as forwarded
            
        Returns:
            True if result was found and marked, False otherwise
        """
        if result_id in self.buffer:
            self.buffer[result_id].forwarded = True
            logger.debug(f"Marked as forwarded: {result_id}")
            return True
        
        return False
    
    def get_by_id(self, result_id: str) -> Optional[BufferedResult]:
        """
        Get a specific result by ID without removing it.
        
        Args:
            result_id: ID of result to retrieve
            
        Returns:
            BufferedResult if found, None otherwise
        """
        return self.buffer.get(result_id)
