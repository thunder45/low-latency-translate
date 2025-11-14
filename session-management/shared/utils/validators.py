"""
Input validation utilities for WebSocket connection parameters.
"""
import re
from typing import Optional


class ValidationError(Exception):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None):
        """
        Initialize validation error.
        
        Args:
            message: Error message
            field: Field name that failed validation
        """
        super().__init__(message)
        self.field = field
        self.message = message


def validate_language_code(language_code: str, field_name: str = 'language') -> None:
    """
    Validate ISO 639-1 language code format.
    
    Args:
        language_code: Language code to validate
        field_name: Name of the field for error messages
    
    Raises:
        ValidationError: If language code format is invalid
    """
    if not language_code:
        raise ValidationError(
            f'{field_name} is required',
            field=field_name
        )
    
    # ISO 639-1: 2 lowercase letters
    pattern = r'^[a-z]{2}$'
    if not re.match(pattern, language_code):
        raise ValidationError(
            f'{field_name} must be a 2-letter ISO 639-1 code (e.g., "en", "es")',
            field=field_name
        )


def validate_session_id_format(session_id: str) -> None:
    """
    Validate session ID format (adjective-noun-number).
    
    Args:
        session_id: Session ID to validate
    
    Raises:
        ValidationError: If session ID format is invalid
    """
    if not session_id:
        raise ValidationError(
            'sessionId is required',
            field='sessionId'
        )
    
    # Format: {adjective}-{noun}-{3-digit-number}
    pattern = r'^[a-z]+-[a-z]+-\d{3}$'
    if not re.match(pattern, session_id):
        raise ValidationError(
            'sessionId must be in format: adjective-noun-number (e.g., "golden-eagle-427")',
            field='sessionId'
        )


def validate_quality_tier(quality_tier: str) -> None:
    """
    Validate quality tier value.
    
    Args:
        quality_tier: Quality tier to validate
    
    Raises:
        ValidationError: If quality tier is invalid
    """
    if not quality_tier:
        raise ValidationError(
            'qualityTier is required',
            field='qualityTier'
        )
    
    valid_tiers = ['standard', 'premium']
    if quality_tier not in valid_tiers:
        raise ValidationError(
            f'qualityTier must be one of: {", ".join(valid_tiers)}',
            field='qualityTier'
        )


def validate_action(action: str) -> None:
    """
    Validate action parameter.
    
    Args:
        action: Action to validate
    
    Raises:
        ValidationError: If action is invalid
    """
    if not action:
        raise ValidationError(
            'action is required',
            field='action'
        )
    
    valid_actions = ['createSession', 'joinSession', 'refreshConnection']
    if action not in valid_actions:
        raise ValidationError(
            f'action must be one of: {", ".join(valid_actions)}',
            field='action'
        )


def validate_message_size(
    message_body: str,
    max_size_bytes: int = 131072  # 128 KB default (API Gateway limit is 1 MB)
) -> None:
    """
    Validate WebSocket message size.
    
    API Gateway WebSocket has a 1 MB message size limit, but we enforce
    a more conservative 128 KB limit by default to prevent abuse.
    
    Args:
        message_body: Message body to validate (string or bytes)
        max_size_bytes: Maximum allowed size in bytes (default: 128 KB)
    
    Raises:
        ValidationError: If message size exceeds limit
    """
    if isinstance(message_body, str):
        size_bytes = len(message_body.encode('utf-8'))
    else:
        size_bytes = len(message_body)
    
    if size_bytes > max_size_bytes:
        raise ValidationError(
            f'Message size ({size_bytes} bytes) exceeds maximum allowed size ({max_size_bytes} bytes)',
            field='messageSize'
        )


def validate_audio_chunk_size(
    audio_data: bytes,
    max_size_bytes: int = 32768  # 32 KB default
) -> None:
    """
    Validate audio chunk size.
    
    Audio chunks should be reasonably sized to prevent memory issues
    and ensure smooth processing. Typical audio chunks are 100-200ms
    of audio, which at 16kHz 16-bit mono is 3.2-6.4 KB.
    
    Args:
        audio_data: Audio data bytes to validate
        max_size_bytes: Maximum allowed size in bytes (default: 32 KB)
    
    Raises:
        ValidationError: If audio chunk size exceeds limit
    """
    if not isinstance(audio_data, bytes):
        raise ValidationError(
            'Audio data must be bytes',
            field='audioData'
        )
    
    size_bytes = len(audio_data)
    
    if size_bytes > max_size_bytes:
        raise ValidationError(
            f'Audio chunk size ({size_bytes} bytes) exceeds maximum allowed size ({max_size_bytes} bytes)',
            field='audioChunkSize'
        )
    
    # Also validate minimum size (at least 100 bytes)
    if size_bytes < 100:
        raise ValidationError(
            f'Audio chunk size ({size_bytes} bytes) is too small (minimum: 100 bytes)',
            field='audioChunkSize'
        )


def validate_control_message_size(
    payload: dict,
    max_size_bytes: int = 4096  # 4 KB default
) -> None:
    """
    Validate control message payload size.
    
    Control messages (pause, mute, volume, etc.) should be small.
    This prevents abuse and ensures fast processing.
    
    Args:
        payload: Control message payload dictionary
        max_size_bytes: Maximum allowed size in bytes (default: 4 KB)
    
    Raises:
        ValidationError: If payload size exceeds limit
    """
    import json
    
    try:
        payload_str = json.dumps(payload)
        size_bytes = len(payload_str.encode('utf-8'))
    except (TypeError, ValueError) as e:
        raise ValidationError(
            f'Invalid control message payload: {str(e)}',
            field='payload'
        )
    
    if size_bytes > max_size_bytes:
        raise ValidationError(
            f'Control message payload size ({size_bytes} bytes) exceeds maximum allowed size ({max_size_bytes} bytes)',
            field='payloadSize'
        )
