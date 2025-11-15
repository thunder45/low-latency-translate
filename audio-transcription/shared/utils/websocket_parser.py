"""
WebSocket message parser for audio processor Lambda.

This module provides utilities for parsing WebSocket events from API Gateway,
extracting connection metadata, and validating message structure.
"""

import json
import base64
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class WebSocketParseError(Exception):
    """Raised when WebSocket message parsing fails."""
    pass


class WebSocketMessageParser:
    """
    Parser for WebSocket messages from API Gateway.
    
    This class handles parsing of WebSocket events from API Gateway,
    extracting connection metadata, and decoding audio data.
    
    Examples:
        >>> parser = WebSocketMessageParser()
        >>> connection_id, audio_data = parser.parse_audio_message(event)
    """
    
    def __init__(self):
        """Initialize WebSocket message parser."""
        logger.debug("Initialized WebSocketMessageParser")
    
    def parse_audio_message(self, event: Dict[str, Any]) -> Tuple[str, bytes]:
        """
        Parse audio message from WebSocket event.
        
        Extracts connectionId from request context and audio data from
        message body. Supports both base64-encoded and binary audio data.
        
        Args:
            event: Lambda event from API Gateway WebSocket
        
        Returns:
            Tuple of (connection_id, audio_bytes)
        
        Raises:
            WebSocketParseError: If message structure is invalid
        
        Examples:
            >>> event = {
            ...     'requestContext': {'connectionId': 'conn-123'},
            ...     'body': '{"data": "base64_audio..."}'
            ... }
            >>> connection_id, audio = parser.parse_audio_message(event)
        """
        try:
            # Extract connection ID from request context
            connection_id = self._extract_connection_id(event)
            
            # Extract and decode audio data from body
            audio_data = self._extract_audio_data(event)
            
            logger.debug(
                f"Parsed audio message: connection={connection_id}, "
                f"audio_size={len(audio_data)} bytes"
            )
            
            return connection_id, audio_data
            
        except Exception as e:
            logger.error(f"Failed to parse audio message: {e}", exc_info=True)
            raise WebSocketParseError(f"Invalid message structure: {e}")
    
    def _extract_connection_id(self, event: Dict[str, Any]) -> str:
        """
        Extract connection ID from WebSocket event.
        
        Args:
            event: Lambda event from API Gateway
        
        Returns:
            Connection ID string
        
        Raises:
            WebSocketParseError: If connectionId not found
        """
        try:
            request_context = event.get('requestContext', {})
            connection_id = request_context.get('connectionId')
            
            if not connection_id:
                raise WebSocketParseError(
                    "Missing connectionId in requestContext"
                )
            
            return connection_id
            
        except Exception as e:
            raise WebSocketParseError(f"Failed to extract connectionId: {e}")
    
    def _extract_audio_data(self, event: Dict[str, Any]) -> bytes:
        """
        Extract and decode audio data from WebSocket message body.
        
        Supports two formats:
        1. JSON body with 'data' field containing base64-encoded audio
        2. Binary body (isBase64Encoded=true in event)
        
        Args:
            event: Lambda event from API Gateway
        
        Returns:
            Audio data as bytes
        
        Raises:
            WebSocketParseError: If audio data not found or invalid
        """
        try:
            body = event.get('body')
            if not body:
                raise WebSocketParseError("Missing message body")
            
            # Check if body is base64-encoded binary
            is_base64_encoded = event.get('isBase64Encoded', False)
            
            if is_base64_encoded:
                # Body is base64-encoded binary data
                logger.debug("Decoding base64-encoded binary body")
                audio_bytes = base64.b64decode(body)
            else:
                # Body is JSON with 'data' field
                try:
                    body_json = json.loads(body)
                    audio_b64 = body_json.get('data')
                    
                    if not audio_b64:
                        raise WebSocketParseError(
                            "Missing 'data' field in message body"
                        )
                    
                    logger.debug("Decoding base64 audio from JSON body")
                    audio_bytes = base64.b64decode(audio_b64)
                    
                except json.JSONDecodeError as e:
                    raise WebSocketParseError(f"Invalid JSON body: {e}")
            
            if not audio_bytes:
                raise WebSocketParseError("Empty audio data")
            
            return audio_bytes
            
        except base64.binascii.Error as e:
            raise WebSocketParseError(f"Invalid base64 encoding: {e}")
        except Exception as e:
            raise WebSocketParseError(f"Failed to extract audio data: {e}")
    
    def validate_message_format(self, event: Dict[str, Any]) -> bool:
        """
        Validate WebSocket message format without parsing.
        
        Checks that required fields are present without decoding data.
        Useful for quick validation before processing.
        
        Args:
            event: Lambda event from API Gateway
        
        Returns:
            True if format is valid, False otherwise
        """
        try:
            # Check for required top-level fields
            if 'requestContext' not in event:
                logger.warning("Missing requestContext in event")
                return False
            
            if 'connectionId' not in event.get('requestContext', {}):
                logger.warning("Missing connectionId in requestContext")
                return False
            
            if 'body' not in event:
                logger.warning("Missing body in event")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating message format: {e}")
            return False


def parse_websocket_audio_event(event: Dict[str, Any]) -> Tuple[str, bytes]:
    """
    Convenience function to parse WebSocket audio event.
    
    Args:
        event: Lambda event from API Gateway WebSocket
    
    Returns:
        Tuple of (connection_id, audio_bytes)
    
    Raises:
        WebSocketParseError: If parsing fails
    
    Examples:
        >>> connection_id, audio = parse_websocket_audio_event(event)
    """
    parser = WebSocketMessageParser()
    return parser.parse_audio_message(event)
