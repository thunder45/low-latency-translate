"""
DynamoDB table name constants for audio transcription.

This module imports table name constants from session-management to ensure
consistency across all modules.
"""

import os
import sys

# Add session-management to path to import shared constants
session_mgmt_path = os.path.join(
    os.path.dirname(__file__),
    '../../../session-management'
)
if os.path.exists(session_mgmt_path):
    sys.path.insert(0, session_mgmt_path)

try:
    from shared.config.table_names import (
        SESSIONS_TABLE_NAME,
        CONNECTIONS_TABLE_NAME,
        RATE_LIMITS_TABLE_NAME,
        TRANSLATION_CACHE_TABLE_NAME,
        get_table_name
    )
except ImportError:
    # Fallback to local constants if session-management not available
    SESSIONS_TABLE_NAME = 'Sessions'
    CONNECTIONS_TABLE_NAME = 'Connections'
    RATE_LIMITS_TABLE_NAME = 'RateLimits'
    TRANSLATION_CACHE_TABLE_NAME = 'TranslationCache'
    
    def get_table_name(table_key: str, default: str = None) -> str:
        """Fallback implementation of get_table_name with backward compatibility."""
        if default is None:
            default = {
                'SESSIONS_TABLE_NAME': SESSIONS_TABLE_NAME,
                'CONNECTIONS_TABLE_NAME': CONNECTIONS_TABLE_NAME,
                'RATE_LIMITS_TABLE_NAME': RATE_LIMITS_TABLE_NAME,
                'TRANSLATION_CACHE_TABLE_NAME': TRANSLATION_CACHE_TABLE_NAME
            }.get(table_key, '')
        
        # Try new naming convention first (with _NAME suffix)
        value = os.getenv(table_key)
        if value:
            return value
        
        # Fall back to legacy naming (without _NAME suffix) for backward compatibility
        legacy_key = table_key.replace('_TABLE_NAME', '_TABLE')
        value = os.getenv(legacy_key)
        if value:
            return value
        
        return default

__all__ = [
    'SESSIONS_TABLE_NAME',
    'CONNECTIONS_TABLE_NAME',
    'RATE_LIMITS_TABLE_NAME',
    'TRANSLATION_CACHE_TABLE_NAME',
    'get_table_name'
]
