"""
Shared utilities Lambda Layer.

This module provides shared utilities for all Lambda functions in the
WebSocket Audio Integration system.
"""

# Import key utilities for easy access
from .structured_logger import get_structured_logger, StructuredLogger
from .error_codes import (
    ErrorCode,
    format_error_response,
    get_http_status,
    get_error_message
)
from .table_names import (
    SESSIONS_TABLE_NAME,
    CONNECTIONS_TABLE_NAME,
    RATE_LIMITS_TABLE_NAME,
    TRANSLATION_CACHE_TABLE_NAME,
    get_table_name
)

__all__ = [
    # Logging
    'get_structured_logger',
    'StructuredLogger',
    
    # Error handling
    'ErrorCode',
    'format_error_response',
    'get_http_status',
    'get_error_message',
    
    # Table names
    'SESSIONS_TABLE_NAME',
    'CONNECTIONS_TABLE_NAME',
    'RATE_LIMITS_TABLE_NAME',
    'TRANSLATION_CACHE_TABLE_NAME',
    'get_table_name',
]
