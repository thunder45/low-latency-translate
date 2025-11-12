"""
Utility for building standardized API Gateway responses.
"""
import json
import time
from typing import Dict, Any, Optional


def success_response(
    status_code: int = 200,
    body: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build success response.

    Args:
        status_code: HTTP status code
        body: Response body dict

    Returns:
        API Gateway response dict
    """
    return {
        'statusCode': status_code,
        'body': json.dumps(body or {})
    }


def error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build error response.

    Args:
        status_code: HTTP status code
        error_code: Application error code
        message: Human-readable error message
        details: Optional additional error details

    Returns:
        API Gateway response dict
    """
    body = {
        'type': 'error',
        'code': error_code,
        'message': message,
        'timestamp': int(time.time() * 1000)
    }

    if details:
        body['details'] = details

    return {
        'statusCode': status_code,
        'body': json.dumps(body)
    }


def rate_limit_error_response(retry_after: int) -> Dict[str, Any]:
    """
    Build rate limit exceeded error response.

    Args:
        retry_after: Seconds until rate limit resets

    Returns:
        API Gateway response dict with 429 status
    """
    return error_response(
        status_code=429,
        error_code='RATE_LIMIT_EXCEEDED',
        message=f'Rate limit exceeded. Retry after {retry_after} seconds.',
        details={'retryAfter': retry_after}
    )

