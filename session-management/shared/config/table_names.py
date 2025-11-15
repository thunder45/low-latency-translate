"""
DynamoDB table name constants.

This module provides centralized table name constants to ensure consistency
across all modules and Lambda functions.
"""

# Session Management Tables
SESSIONS_TABLE_NAME = 'Sessions'
CONNECTIONS_TABLE_NAME = 'Connections'
RATE_LIMITS_TABLE_NAME = 'RateLimits'

# Translation Cache Table (used by translation-pipeline)
TRANSLATION_CACHE_TABLE_NAME = 'TranslationCache'

# Table name mapping for environment variable overrides
# This allows table names to be overridden via environment variables
# while maintaining a consistent naming convention
TABLE_NAME_ENV_VARS = {
    'SESSIONS_TABLE_NAME': SESSIONS_TABLE_NAME,
    'CONNECTIONS_TABLE_NAME': CONNECTIONS_TABLE_NAME,
    'RATE_LIMITS_TABLE_NAME': RATE_LIMITS_TABLE_NAME,
    'TRANSLATION_CACHE_TABLE_NAME': TRANSLATION_CACHE_TABLE_NAME
}


def get_table_name(table_key: str, default: str = None) -> str:
    """
    Get table name from environment variable or use default constant.
    
    This function allows table names to be overridden via environment variables
    for different deployment environments (dev, staging, prod) while providing
    sensible defaults.
    
    Supports both new naming convention (with _NAME suffix) and legacy naming
    (without _NAME suffix) for backward compatibility with existing tests.
    
    Args:
        table_key: Environment variable key (e.g., 'SESSIONS_TABLE_NAME')
        default: Default table name if environment variable not set
    
    Returns:
        Table name from environment or default
    
    Example:
        >>> import os
        >>> os.environ['SESSIONS_TABLE_NAME'] = 'Sessions-Dev'
        >>> get_table_name('SESSIONS_TABLE_NAME', SESSIONS_TABLE_NAME)
        'Sessions-Dev'
        
        >>> get_table_name('SESSIONS_TABLE_NAME', SESSIONS_TABLE_NAME)
        'Sessions'  # If env var not set
    """
    import os
    
    if default is None:
        default = TABLE_NAME_ENV_VARS.get(table_key, '')
    
    # Try new naming convention first (with _NAME suffix)
    value = os.getenv(table_key)
    if value:
        return value
    
    # Fall back to legacy naming (without _NAME suffix) for backward compatibility
    # This supports existing tests that use SESSIONS_TABLE, CONNECTIONS_TABLE, etc.
    legacy_key = table_key.replace('_TABLE_NAME', '_TABLE')
    value = os.getenv(legacy_key)
    if value:
        return value
    
    return default
