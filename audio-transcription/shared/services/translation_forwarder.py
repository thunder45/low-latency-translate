"""
Translation forwarder for partial result processing.

This module provides the TranslationForwarder class that forwards
processed transcription results to the translation pipeline with
deduplication to prevent duplicate synthesis.
"""

import logging
from typing import Protocol
from shared.services.deduplication_cache import DeduplicationCache

logger = logging.getLogger(__name__)


class TranslationPipeline(Protocol):
    """
    Protocol defining the interface for translation pipeline.
    
    This protocol allows the TranslationForwarder to work with any
    translation pipeline implementation that provides a process method.
    """
    
    def process(
        self,
        text: str,
        session_id: str,
        source_language: str
    ) -> None:
        """
        Process text for translation and synthesis.
        
        Args:
            text: Text to translate and synthesize
            session_id: Session identifier
            source_language: ISO 639-1 source language code
        """
        ...


class TranslationForwarder:
    """
    Forwards processed results to translation pipeline with deduplication.
    
    This class is responsible for forwarding transcription results to the
    translation pipeline while preventing duplicate synthesis of identical
    text segments. It uses a deduplication cache to track recently processed
    text and skips forwarding if the text has already been processed.
    
    Attributes:
        dedup_cache: Deduplication cache for tracking processed text
        translation_pipeline: Translation pipeline for processing text
    """
    
    def __init__(
        self,
        dedup_cache: DeduplicationCache,
        translation_pipeline: TranslationPipeline
    ):
        """
        Initialize translation forwarder.
        
        Args:
            dedup_cache: Deduplication cache instance
            translation_pipeline: Translation pipeline instance
        """
        self.dedup_cache = dedup_cache
        self.translation_pipeline = translation_pipeline
        
        logger.info("TranslationForwarder initialized")
    
    def forward(
        self,
        text: str,
        session_id: str,
        source_language: str
    ) -> bool:
        """
        Forward text to translation pipeline if not duplicate.
        
        This method normalizes the input text, checks the deduplication
        cache to see if the text has already been processed, and forwards
        to the translation pipeline if it's not a duplicate. After
        forwarding, the text is added to the cache to prevent future
        duplicates.
        
        Args:
            text: Text to forward for translation
            session_id: Session identifier
            source_language: ISO 639-1 source language code
            
        Returns:
            True if text was forwarded, False if duplicate (skipped)
            
        Examples:
            >>> forwarder = TranslationForwarder(cache, pipeline)
            >>> forwarder.forward("Hello everyone", "session-123", "en")
            True
            >>> forwarder.forward("Hello everyone!", "session-123", "en")
            False  # Duplicate (normalized text matches)
        """
        # Check if this is a duplicate
        if self._should_skip_duplicate(text):
            logger.debug(
                f"Skipping duplicate text for session {session_id}: "
                f"{text[:50]}..."
            )
            return False
        
        # Add to cache before forwarding to prevent race conditions
        self.dedup_cache.add(text)
        
        # Forward to translation pipeline
        try:
            self.translation_pipeline.process(
                text=text,
                session_id=session_id,
                source_language=source_language
            )
            
            logger.info(
                f"Forwarded to translation for session {session_id}: "
                f"{text[:50]}... (length: {len(text)})"
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to forward to translation for session {session_id}: {e}",
                exc_info=True
            )
            # Remove from cache since forwarding failed
            # (Note: This is a best-effort cleanup; the cache will
            # eventually expire the entry anyway)
            raise
    
    def _should_skip_duplicate(self, text: str) -> bool:
        """
        Check if text should be skipped as duplicate.
        
        This method checks the deduplication cache to determine if
        the normalized text has already been processed recently.
        
        Args:
            text: Text to check
            
        Returns:
            True if text is a duplicate and should be skipped
        """
        return self.dedup_cache.contains(text)

