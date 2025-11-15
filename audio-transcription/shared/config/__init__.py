"""
Configuration module for audio transcription.
"""

from .table_names import (
    SESSIONS_TABLE_NAME,
    CONNECTIONS_TABLE_NAME,
    RATE_LIMITS_TABLE_NAME,
    TRANSLATION_CACHE_TABLE_NAME,
    get_table_name
)

__all__ = [
    'SESSIONS_TABLE_NAME',
    'CONNECTIONS_TABLE_NAME',
    'RATE_LIMITS_TABLE_NAME',
    'TRANSLATION_CACHE_TABLE_NAME',
    'get_table_name'
]
