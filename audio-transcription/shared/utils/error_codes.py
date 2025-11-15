"""
Standardized error codes for WebSocket Audio Integration.

This module provides a centralized enumeration of all error codes used
across the system to ensure consistency in error handling and reporting.
"""

from enum import Enum


class ErrorCode(str, Enum):
    """
    Enumeration of all error codes used in the system.
    
    Error codes are organized by category:
    - Authentication & Authorization (AUTH_*)
    - Session Management (SESSION_*)
    - Connection Management (CONNECTION_*)
    - Audio Processing (AUDIO_*)
    - Validation (VALIDATION_*)
    - Rate Limiting (RATE_LIMIT_*)
    - Internal Errors (INTERNAL_*)
    """
    
    # Authentication & Authorization Errors
    AUTH_UNAUTHORIZED = 'AUTH_UNAUTHORIZED'
    AUTH_TOKEN_INVALID = 'AUTH_TOKEN_INVALID'
    AUTH_TOKEN_EXPIRED = 'AUTH_TOKEN_EXPIRED'
    AUTH_MISSING_TOKEN = 'AUTH_MISSING_TOKEN'
    AUTH_INVALID_ROLE = 'AUTH_INVALID_ROLE'
    
    # Session Management Errors
    SESSION_NOT_FOUND = 'SESSION_NOT_FOUND'
    SESSION_INACTIVE = 'SESSION_INACTIVE'
    SESSION_EXPIRED = 'SESSION_EXPIRED'
    SESSION_ALREADY_EXISTS = 'SESSION_ALREADY_EXISTS'
    SESSION_CREATION_FAILED = 'SESSION_CREATION_FAILED'
    SESSION_MAX_LISTENERS_REACHED = 'SESSION_MAX_LISTENERS_REACHED'
    SESSION_INVALID_ID_FORMAT = 'SESSION_INVALID_ID_FORMAT'
    
    # Connection Management Errors
    CONNECTION_NOT_FOUND = 'CONNECTION_NOT_FOUND'
    CONNECTION_TIMEOUT = 'CONNECTION_TIMEOUT'
    CONNECTION_CLOSED = 'CONNECTION_CLOSED'
    CONNECTION_INVALID = 'CONNECTION_INVALID'
    CONNECTION_REFRESH_REQUIRED = 'CONNECTION_REFRESH_REQUIRED'
    
    # Audio Processing Errors
    AUDIO_INVALID_FORMAT = 'AUDIO_INVALID_FORMAT'
    AUDIO_CHUNK_TOO_LARGE = 'AUDIO_CHUNK_TOO_LARGE'
    AUDIO_CHUNK_TOO_SMALL = 'AUDIO_CHUNK_TOO_SMALL'
    AUDIO_INVALID_SAMPLE_RATE = 'AUDIO_INVALID_SAMPLE_RATE'
    AUDIO_INVALID_ENCODING = 'AUDIO_INVALID_ENCODING'
    AUDIO_QUALITY_LOW = 'AUDIO_QUALITY_LOW'
    AUDIO_CLIPPING_DETECTED = 'AUDIO_CLIPPING_DETECTED'
    AUDIO_ECHO_DETECTED = 'AUDIO_ECHO_DETECTED'
    AUDIO_SILENCE_DETECTED = 'AUDIO_SILENCE_DETECTED'
    AUDIO_PROCESSING_FAILED = 'AUDIO_PROCESSING_FAILED'
    
    # Validation Errors
    VALIDATION_INVALID_LANGUAGE = 'VALIDATION_INVALID_LANGUAGE'
    VALIDATION_INVALID_QUALITY_TIER = 'VALIDATION_INVALID_QUALITY_TIER'
    VALIDATION_INVALID_ACTION = 'VALIDATION_INVALID_ACTION'
    VALIDATION_MISSING_PARAMETER = 'VALIDATION_MISSING_PARAMETER'
    VALIDATION_INVALID_PARAMETER = 'VALIDATION_INVALID_PARAMETER'
    VALIDATION_MESSAGE_TOO_LARGE = 'VALIDATION_MESSAGE_TOO_LARGE'
    VALIDATION_INVALID_MESSAGE_FORMAT = 'VALIDATION_INVALID_MESSAGE_FORMAT'
    
    # Rate Limiting Errors
    RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED'
    RATE_LIMIT_AUDIO_CHUNKS = 'RATE_LIMIT_AUDIO_CHUNKS'
    RATE_LIMIT_CONTROL_MESSAGES = 'RATE_LIMIT_CONTROL_MESSAGES'
    RATE_LIMIT_SESSION_CREATION = 'RATE_LIMIT_SESSION_CREATION'
    
    # Internal Errors
    INTERNAL_SERVER_ERROR = 'INTERNAL_SERVER_ERROR'
    INTERNAL_DATABASE_ERROR = 'INTERNAL_DATABASE_ERROR'
    INTERNAL_TRANSCRIBE_ERROR = 'INTERNAL_TRANSCRIBE_ERROR'
    INTERNAL_TRANSLATION_ERROR = 'INTERNAL_TRANSLATION_ERROR'
    INTERNAL_POLLY_ERROR = 'INTERNAL_POLLY_ERROR'
    INTERNAL_EMOTION_DETECTION_ERROR = 'INTERNAL_EMOTION_DETECTION_ERROR'
    INTERNAL_CONFIGURATION_ERROR = 'INTERNAL_CONFIGURATION_ERROR'


# Error code to HTTP status code mapping
ERROR_CODE_TO_HTTP_STATUS = {
    # Authentication & Authorization (401, 403)
    ErrorCode.AUTH_UNAUTHORIZED: 403,
    ErrorCode.AUTH_TOKEN_INVALID: 401,
    ErrorCode.AUTH_TOKEN_EXPIRED: 401,
    ErrorCode.AUTH_MISSING_TOKEN: 401,
    ErrorCode.AUTH_INVALID_ROLE: 403,
    
    # Session Management (404, 410, 409)
    ErrorCode.SESSION_NOT_FOUND: 404,
    ErrorCode.SESSION_INACTIVE: 410,
    ErrorCode.SESSION_EXPIRED: 410,
    ErrorCode.SESSION_ALREADY_EXISTS: 409,
    ErrorCode.SESSION_CREATION_FAILED: 500,
    ErrorCode.SESSION_MAX_LISTENERS_REACHED: 429,
    ErrorCode.SESSION_INVALID_ID_FORMAT: 400,
    
    # Connection Management (404, 408, 410)
    ErrorCode.CONNECTION_NOT_FOUND: 404,
    ErrorCode.CONNECTION_TIMEOUT: 408,
    ErrorCode.CONNECTION_CLOSED: 410,
    ErrorCode.CONNECTION_INVALID: 400,
    ErrorCode.CONNECTION_REFRESH_REQUIRED: 426,
    
    # Audio Processing (400, 413, 422)
    ErrorCode.AUDIO_INVALID_FORMAT: 400,
    ErrorCode.AUDIO_CHUNK_TOO_LARGE: 413,
    ErrorCode.AUDIO_CHUNK_TOO_SMALL: 400,
    ErrorCode.AUDIO_INVALID_SAMPLE_RATE: 400,
    ErrorCode.AUDIO_INVALID_ENCODING: 400,
    ErrorCode.AUDIO_QUALITY_LOW: 422,
    ErrorCode.AUDIO_CLIPPING_DETECTED: 422,
    ErrorCode.AUDIO_ECHO_DETECTED: 422,
    ErrorCode.AUDIO_SILENCE_DETECTED: 422,
    ErrorCode.AUDIO_PROCESSING_FAILED: 500,
    
    # Validation (400)
    ErrorCode.VALIDATION_INVALID_LANGUAGE: 400,
    ErrorCode.VALIDATION_INVALID_QUALITY_TIER: 400,
    ErrorCode.VALIDATION_INVALID_ACTION: 400,
    ErrorCode.VALIDATION_MISSING_PARAMETER: 400,
    ErrorCode.VALIDATION_INVALID_PARAMETER: 400,
    ErrorCode.VALIDATION_MESSAGE_TOO_LARGE: 413,
    ErrorCode.VALIDATION_INVALID_MESSAGE_FORMAT: 400,
    
    # Rate Limiting (429)
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,
    ErrorCode.RATE_LIMIT_AUDIO_CHUNKS: 429,
    ErrorCode.RATE_LIMIT_CONTROL_MESSAGES: 429,
    ErrorCode.RATE_LIMIT_SESSION_CREATION: 429,
    
    # Internal Errors (500)
    ErrorCode.INTERNAL_SERVER_ERROR: 500,
    ErrorCode.INTERNAL_DATABASE_ERROR: 500,
    ErrorCode.INTERNAL_TRANSCRIBE_ERROR: 500,
    ErrorCode.INTERNAL_TRANSLATION_ERROR: 500,
    ErrorCode.INTERNAL_POLLY_ERROR: 500,
    ErrorCode.INTERNAL_EMOTION_DETECTION_ERROR: 500,
    ErrorCode.INTERNAL_CONFIGURATION_ERROR: 500,
}


# Error code to user-friendly message mapping
ERROR_CODE_TO_MESSAGE = {
    # Authentication & Authorization
    ErrorCode.AUTH_UNAUTHORIZED: 'Unauthorized access',
    ErrorCode.AUTH_TOKEN_INVALID: 'Invalid authentication token',
    ErrorCode.AUTH_TOKEN_EXPIRED: 'Authentication token expired',
    ErrorCode.AUTH_MISSING_TOKEN: 'Authentication token required',
    ErrorCode.AUTH_INVALID_ROLE: 'Invalid role for this operation',
    
    # Session Management
    ErrorCode.SESSION_NOT_FOUND: 'Session not found',
    ErrorCode.SESSION_INACTIVE: 'Session is no longer active',
    ErrorCode.SESSION_EXPIRED: 'Session has expired',
    ErrorCode.SESSION_ALREADY_EXISTS: 'Session already exists',
    ErrorCode.SESSION_CREATION_FAILED: 'Failed to create session',
    ErrorCode.SESSION_MAX_LISTENERS_REACHED: 'Maximum number of listeners reached',
    ErrorCode.SESSION_INVALID_ID_FORMAT: 'Invalid session ID format',
    
    # Connection Management
    ErrorCode.CONNECTION_NOT_FOUND: 'Connection not found',
    ErrorCode.CONNECTION_TIMEOUT: 'Connection timed out due to inactivity',
    ErrorCode.CONNECTION_CLOSED: 'Connection has been closed',
    ErrorCode.CONNECTION_INVALID: 'Invalid connection',
    ErrorCode.CONNECTION_REFRESH_REQUIRED: 'Connection refresh required',
    
    # Audio Processing
    ErrorCode.AUDIO_INVALID_FORMAT: 'Invalid audio format',
    ErrorCode.AUDIO_CHUNK_TOO_LARGE: 'Audio chunk exceeds maximum size',
    ErrorCode.AUDIO_CHUNK_TOO_SMALL: 'Audio chunk below minimum size',
    ErrorCode.AUDIO_INVALID_SAMPLE_RATE: 'Invalid audio sample rate',
    ErrorCode.AUDIO_INVALID_ENCODING: 'Invalid audio encoding',
    ErrorCode.AUDIO_QUALITY_LOW: 'Audio quality below acceptable threshold',
    ErrorCode.AUDIO_CLIPPING_DETECTED: 'Audio clipping detected - reduce microphone volume',
    ErrorCode.AUDIO_ECHO_DETECTED: 'Echo detected - check audio setup',
    ErrorCode.AUDIO_SILENCE_DETECTED: 'No audio detected - check microphone',
    ErrorCode.AUDIO_PROCESSING_FAILED: 'Audio processing failed',
    
    # Validation
    ErrorCode.VALIDATION_INVALID_LANGUAGE: 'Invalid or unsupported language code',
    ErrorCode.VALIDATION_INVALID_QUALITY_TIER: 'Invalid quality tier',
    ErrorCode.VALIDATION_INVALID_ACTION: 'Invalid action',
    ErrorCode.VALIDATION_MISSING_PARAMETER: 'Required parameter missing',
    ErrorCode.VALIDATION_INVALID_PARAMETER: 'Invalid parameter value',
    ErrorCode.VALIDATION_MESSAGE_TOO_LARGE: 'Message exceeds maximum size',
    ErrorCode.VALIDATION_INVALID_MESSAGE_FORMAT: 'Invalid message format',
    
    # Rate Limiting
    ErrorCode.RATE_LIMIT_EXCEEDED: 'Rate limit exceeded',
    ErrorCode.RATE_LIMIT_AUDIO_CHUNKS: 'Audio chunk rate limit exceeded',
    ErrorCode.RATE_LIMIT_CONTROL_MESSAGES: 'Control message rate limit exceeded',
    ErrorCode.RATE_LIMIT_SESSION_CREATION: 'Session creation rate limit exceeded',
    
    # Internal Errors
    ErrorCode.INTERNAL_SERVER_ERROR: 'Internal server error',
    ErrorCode.INTERNAL_DATABASE_ERROR: 'Database error',
    ErrorCode.INTERNAL_TRANSCRIBE_ERROR: 'Transcription service error',
    ErrorCode.INTERNAL_TRANSLATION_ERROR: 'Translation service error',
    ErrorCode.INTERNAL_POLLY_ERROR: 'Text-to-speech service error',
    ErrorCode.INTERNAL_EMOTION_DETECTION_ERROR: 'Emotion detection error',
    ErrorCode.INTERNAL_CONFIGURATION_ERROR: 'Configuration error',
}


def get_http_status(error_code: ErrorCode) -> int:
    """
    Get HTTP status code for error code.
    
    Args:
        error_code: Error code enum value
    
    Returns:
        HTTP status code (default: 500)
    """
    return ERROR_CODE_TO_HTTP_STATUS.get(error_code, 500)


def get_error_message(error_code: ErrorCode) -> str:
    """
    Get user-friendly error message for error code.
    
    Args:
        error_code: Error code enum value
    
    Returns:
        User-friendly error message
    """
    return ERROR_CODE_TO_MESSAGE.get(error_code, 'An error occurred')


def format_error_response(
    error_code: ErrorCode,
    details: str = None,
    correlation_id: str = None
) -> dict:
    """
    Format standardized error response.
    
    Args:
        error_code: Error code enum value
        details: Optional additional error details
        correlation_id: Optional correlation ID for tracing
    
    Returns:
        Formatted error response dictionary
    
    Example:
        >>> format_error_response(
        ...     ErrorCode.SESSION_NOT_FOUND,
        ...     details='Session ID: golden-eagle-427',
        ...     correlation_id='abc-123'
        ... )
        {
            'type': 'error',
            'code': 'SESSION_NOT_FOUND',
            'message': 'Session not found',
            'details': 'Session ID: golden-eagle-427',
            'correlationId': 'abc-123',
            'timestamp': 1699500000000
        }
    """
    import time
    
    response = {
        'type': 'error',
        'code': error_code.value,
        'message': get_error_message(error_code),
        'timestamp': int(time.time() * 1000)
    }
    
    if details:
        response['details'] = details
    
    if correlation_id:
        response['correlationId'] = correlation_id
    
    return response
