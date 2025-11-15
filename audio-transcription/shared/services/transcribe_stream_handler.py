"""
Async stream handler for AWS Transcribe Streaming API events.

This module provides the TranscribeStreamHandler class that extends
TranscriptResultStreamHandler to process transcription events asynchronously
and route them to the PartialResultProcessor.
"""

import time
import logging
from typing import Optional
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent
from shared.models.transcription_results import PartialResult, FinalResult
from shared.services.partial_result_processor import PartialResultProcessor

logger = logging.getLogger(__name__)


class TranscribeStreamHandler(TranscriptResultStreamHandler):
    """
    Async stream handler for AWS Transcribe transcription events.
    
    This class extends TranscriptResultStreamHandler to process transcription
    events from AWS Transcribe Streaming API. It extracts stability scores
    with null safety, creates PartialResult or FinalResult objects, and
    routes them to the PartialResultProcessor.
    
    The handler implements defensive null checks for all event fields to
    handle malformed or incomplete events gracefully.
    
    Attributes:
        processor: PartialResultProcessor instance for processing results
        session_id: Session ID for this transcription stream
        source_language: Source language code (ISO 639-1)
        translation_pipeline: Optional LambdaTranslationPipeline for forwarding
        emotion_cache: Optional dict for cached emotion data
    
    Examples:
        >>> processor = PartialResultProcessor(...)
        >>> handler = TranscribeStreamHandler(
        ...     output_stream=stream,
        ...     processor=processor,
        ...     session_id="golden-eagle-427",
        ...     source_language="en"
        ... )
        >>> # Handler is used with AWS Transcribe streaming client
        >>> await client.start_stream_transcription(
        ...     ...,
        ...     handler=handler
        ... )
    """
    
    def __init__(
        self,
        output_stream,
        processor: PartialResultProcessor,
        session_id: str,
        source_language: str
    ):
        """
        Initialize Transcribe stream handler.
        
        Args:
            output_stream: Output stream for TranscriptResultStreamHandler
            processor: PartialResultProcessor instance
            session_id: Session ID for this transcription stream
            source_language: Source language code (ISO 639-1)
        """
        super().__init__(output_stream)
        self.processor = processor
        self.session_id = session_id
        self.source_language = source_language
        self.translation_pipeline = None  # Injected after creation
        self.emotion_cache = {}  # For storing emotion data by timestamp
        
        logger.info(
            f"Initialized TranscribeStreamHandler for session {session_id}, "
            f"language {source_language}"
        )
    
    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        """
        Handle transcription event from AWS Transcribe asynchronously.
        
        This method processes transcription events, extracting metadata with
        defensive null checks and routing to the appropriate handler based on
        the IsPartial flag.
        
        Event structure (AWS Transcribe):
        {
            'Transcript': {
                'Results': [{
                    'ResultId': 'result-123',
                    'IsPartial': True/False,
                    'Alternatives': [{
                        'Transcript': 'hello everyone',
                        'Items': [
                            {'Stability': 0.92, 'Content': 'hello'},
                            {'Stability': 0.90, 'Content': 'everyone'}
                        ]
                    }]
                }]
            }
        }
        
        Args:
            transcript_event: TranscriptEvent from AWS Transcribe
        
        Examples:
            >>> # Called automatically by AWS Transcribe streaming client
            >>> # when transcription events arrive
        """
        try:
            # Extract results with null safety
            if not hasattr(transcript_event, 'transcript'):
                logger.warning("Transcript event missing 'transcript' attribute")
                return
            
            transcript = transcript_event.transcript
            if not hasattr(transcript, 'results') or not transcript.results:
                logger.debug("Transcript has no results, skipping")
                return
            
            # Process each result in the event
            for result in transcript.results:
                await self._process_result(result)
                
        except Exception as e:
            logger.error(
                f"Error handling transcript event: {e}",
                exc_info=True
            )
            # Don't re-raise - log and continue processing
    
    async def _process_result(self, result) -> None:
        """
        Process a single transcription result.
        
        This method extracts metadata from the result with defensive null
        checks, creates the appropriate result object (PartialResult or
        FinalResult), and routes it to the processor.
        
        Args:
            result: Transcription result from AWS Transcribe
        """
        try:
            # Extract result ID with null safety
            result_id = getattr(result, 'result_id', None)
            if not result_id:
                result_id = f"result-{int(time.time() * 1000)}"
                logger.warning(f"Result missing result_id, generated: {result_id}")
            
            # Extract IsPartial flag
            is_partial = getattr(result, 'is_partial', False)
            
            # Extract alternatives with null safety
            alternatives = getattr(result, 'alternatives', None)
            if not alternatives or len(alternatives) == 0:
                logger.warning(f"Result {result_id} has no alternatives, skipping")
                return
            
            # Get first alternative (highest confidence)
            alternative = alternatives[0]
            
            # Extract transcript text
            text = getattr(alternative, 'transcript', '')
            if not text or not text.strip():
                logger.debug(f"Result {result_id} has empty text, skipping")
                return
            
            # Extract stability score with null safety (partial results only)
            stability_score = None
            if is_partial:
                stability_score = self._extract_stability_score(alternative)
            
            # Create timestamp
            timestamp = time.time()
            
            # Route to appropriate handler
            if is_partial:
                # Create PartialResult
                partial = PartialResult(
                    result_id=result_id,
                    text=text,
                    stability_score=stability_score,
                    timestamp=timestamp,
                    session_id=self.session_id,
                    source_language=self.source_language
                )
                
                logger.debug(
                    f"Routing partial result {result_id} to processor: "
                    f"text='{text[:50]}...', stability={stability_score}"
                )
                
                # Process partial result
                await self.processor.process_partial(partial)
                
                # Forward to Translation Pipeline if available
                if self.translation_pipeline:
                    await self._forward_to_translation(
                        text=text,
                        is_partial=True,
                        stability_score=stability_score,
                        timestamp=timestamp
                    )
                
            else:
                # Create FinalResult
                final = FinalResult(
                    result_id=result_id,
                    text=text,
                    timestamp=timestamp,
                    session_id=self.session_id,
                    source_language=self.source_language
                )
                
                logger.debug(
                    f"Routing final result {result_id} to processor: "
                    f"text='{text[:50]}...'"
                )
                
                # Process final result
                await self.processor.process_final(final)
                
                # Forward to Translation Pipeline if available
                if self.translation_pipeline:
                    await self._forward_to_translation(
                        text=text,
                        is_partial=False,
                        stability_score=1.0,
                        timestamp=timestamp
                    )
                
        except Exception as e:
            logger.error(
                f"Error processing result: {e}",
                exc_info=True
            )
            # Don't re-raise - log and continue processing
    
    def _extract_stability_score(self, alternative) -> Optional[float]:
        """
        Extract stability score from alternative with null safety.
        
        AWS Transcribe provides stability scores in the Items array of each
        alternative. This method extracts the stability score from the first
        item with defensive null checks.
        
        Stability scores may be unavailable for some languages. In this case,
        the method returns None and the processor will fall back to time-based
        buffering.
        
        Args:
            alternative: Alternative from transcription result
        
        Returns:
            Stability score (0.0-1.0) or None if unavailable
        
        Examples:
            >>> # Alternative with stability
            >>> alternative = {
            ...     'Items': [{'Stability': 0.92, 'Content': 'hello'}]
            ... }
            >>> score = handler._extract_stability_score(alternative)
            >>> assert score == 0.92
            
            >>> # Alternative without stability
            >>> alternative = {'Items': [{'Content': 'hello'}]}
            >>> score = handler._extract_stability_score(alternative)
            >>> assert score is None
        """
        try:
            # Check if items exist
            items = getattr(alternative, 'items', None)
            if not items or len(items) == 0:
                logger.debug("Alternative has no items, stability unavailable")
                return None
            
            # Get first item (usually most representative)
            first_item = items[0]
            
            # Extract stability with null safety
            stability = getattr(first_item, 'stability', None)
            
            if stability is None:
                logger.debug(
                    "Stability score unavailable for this language, "
                    "will use time-based fallback"
                )
                return None
            
            # Validate stability range
            if not isinstance(stability, (int, float)):
                logger.warning(
                    f"Invalid stability type: {type(stability)}, "
                    f"expected float"
                )
                return None
            
            if not 0.0 <= stability <= 1.0:
                logger.warning(
                    f"Stability score {stability} out of range [0.0, 1.0], "
                    f"clamping"
                )
                stability = max(0.0, min(1.0, stability))
            
            return float(stability)
            
        except Exception as e:
            logger.warning(
                f"Error extracting stability score: {e}, "
                f"returning None"
            )
            return None
    
    async def _forward_to_translation(
        self,
        text: str,
        is_partial: bool,
        stability_score: float,
        timestamp: float
    ) -> None:
        """
        Forward transcription to Translation Pipeline.
        
        This method forwards the transcription result to the Translation Pipeline
        Lambda function for translation and broadcasting to listeners.
        
        Args:
            text: Transcribed text
            is_partial: Whether this is a partial result
            stability_score: Stability score (0.0-1.0)
            timestamp: Unix timestamp
        """
        try:
            # Get cached emotion data if available
            emotion_data = self._get_cached_emotion_data()
            
            # Forward to Translation Pipeline
            success = self.translation_pipeline.process(
                text=text,
                session_id=self.session_id,
                source_language=self.source_language,
                is_partial=is_partial,
                stability_score=stability_score,
                timestamp=int(timestamp * 1000),  # Convert to milliseconds
                emotion_dynamics=emotion_data
            )
            
            if success:
                logger.debug(
                    f"Forwarded transcription to Translation Pipeline: "
                    f"session={self.session_id}, text='{text[:50]}...', "
                    f"is_partial={is_partial}"
                )
            else:
                logger.warning(
                    f"Failed to forward transcription to Translation Pipeline: "
                    f"session={self.session_id}"
                )
                
        except Exception as e:
            logger.error(
                f"Error forwarding to Translation Pipeline: {e}",
                exc_info=True
            )
            # Don't re-raise - continue processing
    
    def _get_cached_emotion_data(self) -> dict:
        """
        Get cached emotion data for current session.
        
        Returns emotion data from the session cache, or default
        neutral values if no data is available.
        
        Returns:
            Dict with emotion dynamics (volume, rate, energy)
        """
        try:
            if not self.emotion_cache:
                return self._get_default_emotion()
            
            # Get emotion data for this session
            # emotion_cache is now a dict mapping session_id -> emotion_data
            if isinstance(self.emotion_cache, dict):
                # Check if this is a session-based cache (session_id -> data)
                if self.session_id in self.emotion_cache:
                    emotion_data = self.emotion_cache[self.session_id]
                    # Extract only the fields needed for translation
                    return {
                        'volume': emotion_data.get('volume', 0.5),
                        'rate': emotion_data.get('rate', 1.0),
                        'energy': emotion_data.get('energy', 0.5)
                    }
                # Otherwise, try timestamp-based cache (backward compatibility)
                elif len(self.emotion_cache) > 0:
                    # Get most recent emotion data
                    latest_timestamp = max(self.emotion_cache.keys())
                    emotion_data = self.emotion_cache[latest_timestamp]
                    return emotion_data
            
            return self._get_default_emotion()
            
        except Exception as e:
            logger.warning(f"Error getting cached emotion data: {e}")
            return self._get_default_emotion()
    
    def _get_default_emotion(self) -> dict:
        """
        Get default neutral emotion values.
        
        Returns:
            Dict with neutral emotion dynamics
        """
        return {
            'volume': 0.5,
            'rate': 1.0,
            'energy': 0.5
        }
    
    def cache_emotion_data(self, timestamp: float, emotion_data: dict) -> None:
        """
        Cache emotion data for correlation with transcripts.
        
        Args:
            timestamp: Unix timestamp
            emotion_data: Dict with emotion dynamics
        """
        self.emotion_cache[timestamp] = emotion_data
        
        # Keep only last 10 seconds of emotion data
        cutoff_time = timestamp - 10.0
        self.emotion_cache = {
            ts: data for ts, data in self.emotion_cache.items()
            if ts >= cutoff_time
        }

