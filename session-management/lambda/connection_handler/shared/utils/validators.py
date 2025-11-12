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
