"""
Transcription event handler for AWS Transcribe events.

This module provides the TranscriptionEventHandler class that receives and
parses transcription events from AWS Transcribe Streaming API, extracts
metadata, and routes events to appropriate handlers (partial or final).
"""

import time
import logging
from typing import Dict, Any, Optional
from shared.models.transcription_results import (
    PartialResult,
    FinalResult,
    ResultMetadata
)
from shared.services.partial_result_handler import PartialResultHandler
from shared.services.final_result_handler import FinalResultHandler

logger = logging.getLogger(__name__)


class TranscriptionEventHandler:
    """
    Handler for AWS Transcribe transcription events.
    
    This class receives events from AWS Transcribe Streaming API, parses
    the event structure, extracts metadata (IsPartial flag, stability score,
    text, result_id, timestamp), and routes to the appropriate handler
    (PartialResultHandler or FinalResultHandler).
    
    The handler implements defensive parsing with null checks to handle
    missing or malformed fields gracefully.
    
    Attributes:
        partial_handler: Handler for partial results
        final_handler: Handler for final results
        session_id: Session ID for this transcription stream
        source_language: Source language code (ISO 639-1)
    """
    
    def __init__(
        self,
        partial_handler: PartialResultHandler,
        final_handler: FinalResultHandler,
        session_id: str = "",
        source_language: str = ""
    ):
        """
        Initialize transcription event handler.
        
        Args:
            partial_handler: Handler for partial results
            final_handler: Handler for final results
            session_id: Session ID for this transcription stream
            source_language: Source language code (e.g., 'en', 'es')
        
        Examples:
            >>> partial_handler = PartialResultHandler(...)
            >>> final_handler = FinalResultHandler(...)
            >>> handler = TranscriptionEventHandler(
            ...     partial_handler,
            ...     final_handler,
            ...     session_id="golden-eagle-427",
            ...     source_language="en"
            ... )
        """
        self.partial_handler = partial_handler
        self.final_handler = final_handler
        self.session_id = session_id
        self.source_language = source_language
        
        logger.info(
            f"TranscriptionEventHandler initialized for session {session_id}, "
            f"language {source_language}"
        )
    
    def handle_event(self, event: Dict[str, Any]) -> None:
        """
        Process transcription event from AWS Transcribe.
        
        This method parses the AWS Transcribe event structure, extracts
        metadata, and routes to the appropriate handler based on the
        IsPartial flag.
        
        Event structure (AWS Transcribe):
        {
            'Transcript': {
                'Results': [{
                    'IsPartial': True/False,
                    'ResultId': 'result-123',
                    'StartTime': 1.23,
                    'EndTime': 2.45,
                    'Alternatives': [{
                        'Transcript': 'hello everyone',
                        'Items': [
                            {'Stability': 0.92, 'Content': 'hello'},
                            {'Stability': 0.89, 'Content': 'everyone'}
                        ]
                    }]
                }]
            }
        }
        
        Args:
            event: Transcribe event containing transcript results
        
        Raises:
            ValueError: If event structure is invalid or missing required fields
        
        Examples:
            >>> event = {
            ...     'Transcript': {
            ...         'Results': [{
            ...             'IsPartial': True,
            ...             'ResultId': 'result-123',
            ...             'Alternatives': [{
            ...                 'Transcript': 'hello everyone',
            ...                 'Items': [{'Stability': 0.92}]
            ...             }]
            ...         }]
            ...     }
            ... }
            >>> handler.handle_event(event)
        """
        try:
            # Extract metadata from event
            metadata = self._extract_result_metadata(event)
            
            logger.debug(
                f"Received transcription event: is_partial={metadata.is_partial}, "
                f"result_id={metadata.result_id}, "
                f"stability={metadata.stability_score}, "
                f"text={metadata.text[:50]}..."
            )
            
            # Route to appropriate handler
            if metadata.is_partial:
                self._handle_partial_result(metadata)
            else:
                self._handle_final_result(metadata)
                
        except Exception as e:
            logger.error(
                f"Error handling transcription event: {e}",
                exc_info=True
            )
            # Don't re-raise - log and continue processing other events
    
    def _extract_result_metadata(self, event: Dict[str, Any]) -> ResultMetadata:
        """
        Extract metadata from transcription event.
        
        This method implements defensive parsing with null checks to handle
        missing or malformed fields gracefully. It extracts:
        - IsPartial flag
        - Stability score (from first item, may be None)
        - Text (from first alternative)
        - Result ID
        - Timestamp (current time if not in event)
        
        Args:
            event: Transcribe event dictionary
        
        Returns:
            ResultMetadata with extracted information
        
        Raises:
            ValueError: If required fields are missing or event structure is invalid
        """
        # Validate event structure
        if not event or 'Transcript' not in event:
            raise ValueError("Invalid event: missing 'Transcript' field")
        
        transcript = event['Transcript']
        if 'Results' not in transcript or not transcript['Results']:
            raise ValueError("Invalid event: missing or empty 'Results' field")
        
        # Get first result
        result = transcript['Results'][0]
        
        # Extract IsPartial flag (required)
        if 'IsPartial' not in result:
            raise ValueError("Invalid event: missing 'IsPartial' field")
        is_partial = result['IsPartial']
        
        # Extract ResultId (required)
        if 'ResultId' not in result:
            raise ValueError("Invalid event: missing 'ResultId' field")
        result_id = result['ResultId']
        
        # Extract alternatives (required)
        if 'Alternatives' not in result or not result['Alternatives']:
            raise ValueError("Invalid event: missing or empty 'Alternatives' field")
        
        alternative = result['Alternatives'][0]
        
        # Extract text (required)
        if 'Transcript' not in alternative:
            raise ValueError("Invalid event: missing 'Transcript' in alternative")
        text = alternative['Transcript']
        
        # Validate text is not empty
        if not text or not text.strip():
            raise ValueError("Invalid event: empty transcript text")
        
        # Extract stability score (optional, with defensive null checks)
        stability_score = self._extract_stability_score(alternative)
        
        # Extract timestamp (use current time if not in event)
        timestamp = time.time()
        if 'StartTime' in result:
            # Use StartTime if available (more accurate)
            timestamp = result['StartTime']
        
        # Extract alternative transcriptions (optional)
        alternatives = []
        if len(result['Alternatives']) > 1:
            alternatives = [
                alt['Transcript']
                for alt in result['Alternatives'][1:]
                if 'Transcript' in alt
            ]
        
        return ResultMetadata(
            is_partial=is_partial,
            stability_score=stability_score,
            text=text,
            result_id=result_id,
            timestamp=timestamp,
            alternatives=alternatives
        )
    
    def _extract_stability_score(
        self,
        alternative: Dict[str, Any]
    ) -> Optional[float]:
        """
        Extract stability score from alternative with defensive null checks.
        
        The stability score is extracted from the first item in the Items
        array. If Items is missing, empty, or the first item doesn't have
        a Stability field, returns None.
        
        This handles the case where some languages don't provide stability
        scores, which is expected behavior.
        
        Args:
            alternative: Alternative dictionary from Transcribe event
        
        Returns:
            Stability score (0.0-1.0) or None if unavailable
        """
        # Check if Items array exists and is not empty
        if 'Items' not in alternative:
            logger.debug("No 'Items' field in alternative, stability unavailable")
            return None
        
        items = alternative['Items']
        if not items or len(items) == 0:
            logger.debug("Empty 'Items' array, stability unavailable")
            return None
        
        # Get first item
        first_item = items[0]
        
        # Check if Stability field exists
        if 'Stability' not in first_item:
            logger.debug("No 'Stability' field in first item, stability unavailable")
            return None
        
        stability = first_item['Stability']
        
        # Validate stability is a number
        if not isinstance(stability, (int, float)):
            logger.warning(
                f"Invalid stability type: {type(stability)}, expected float"
            )
            return None
        
        # Validate stability is in valid range
        if not 0.0 <= stability <= 1.0:
            logger.warning(
                f"Invalid stability value: {stability}, expected 0.0-1.0"
            )
            return None
        
        return float(stability)
    
    def _handle_partial_result(self, metadata: ResultMetadata) -> None:
        """
        Handle partial transcription result.
        
        Creates a PartialResult object from metadata and routes to
        PartialResultHandler for processing.
        
        Args:
            metadata: Extracted result metadata
        """
        partial = PartialResult(
            result_id=metadata.result_id,
            text=metadata.text,
            stability_score=metadata.stability_score,
            timestamp=metadata.timestamp,
            is_partial=True,
            session_id=self.session_id,
            source_language=self.source_language
        )
        
        self.partial_handler.process(partial)
    
    def _handle_final_result(self, metadata: ResultMetadata) -> None:
        """
        Handle final transcription result.
        
        Creates a FinalResult object from metadata and routes to
        FinalResultHandler for processing.
        
        Args:
            metadata: Extracted result metadata
        """
        final = FinalResult(
            result_id=metadata.result_id,
            text=metadata.text,
            timestamp=metadata.timestamp,
            is_partial=False,
            session_id=self.session_id,
            source_language=self.source_language
        )
        
        self.final_handler.process(final)
