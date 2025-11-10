# Rate Limiting Integration Guide

This document describes how to integrate rate limiting into Lambda handlers.

## Overview

Rate limiting is implemented using the token bucket algorithm with DynamoDB as the backing store. Each operation type has configurable limits:

- **Session Creation**: 50 per hour per user
- **Listener Joins**: 10 per minute per IP
- **Connection Attempts**: 20 per minute per IP
- **Heartbeat Messages**: 2 per minute per connection

## Usage in Lambda Handlers

### Connection Handler (Session Creation)

```python
import os
from shared.services import RateLimitService
from shared.data_access import RateLimitExceededError
from shared.utils import rate_limit_error_response, error_response

# Initialize at module level for Lambda container reuse
rate_limit_service = RateLimitService()

def lambda_handler(event, context):
    """Handle WebSocket $connect event."""
    
    # Extract user ID from authorizer context (for speakers)
    authorizer_context = event.get('requestContext', {}).get('authorizer', {})
    user_id = authorizer_context.get('userId')
    
    # Extract IP address
    request_context = event.get('requestContext', {})
    ip_address = request_context.get('identity', {}).get('sourceIp', 'unknown')
    
    try:
        # Check connection attempt rate limit (for all connections)
        rate_limit_service.check_connection_attempt_limit(ip_address)
        
        # For speaker session creation
        if user_id:
            rate_limit_service.check_session_creation_limit(user_id)
            # ... create session logic
        else:
            # For listener joins
            rate_limit_service.check_listener_join_limit(ip_address)
            # ... join session logic
            
    except RateLimitExceededError as e:
        return rate_limit_error_response(e.retry_after)
    except Exception as e:
        logger.error(f"Error: {e}")
        return error_response(500, 'INTERNAL_ERROR', 'Internal server error')
```

### Heartbeat Handler

```python
from shared.services import RateLimitService
from shared.data_access import RateLimitExceededError
from shared.utils import rate_limit_error_response

rate_limit_service = RateLimitService()

def lambda_handler(event, context):
    """Handle heartbeat messages."""
    
    connection_id = event['requestContext']['connectionId']
    
    try:
        # Check heartbeat rate limit
        rate_limit_service.check_heartbeat_limit(connection_id)
        
        # Send heartbeat acknowledgment
        # ... heartbeat logic
        
        return {'statusCode': 200}
        
    except RateLimitExceededError as e:
        return rate_limit_error_response(e.retry_after)
```

## Error Response Format

When rate limit is exceeded, the response follows this format:

```json
{
  "statusCode": 429,
  "body": {
    "type": "error",
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Retry after 45 seconds.",
    "timestamp": 1699500123456,
    "details": {
      "retryAfter": 45
    }
  }
}
```

## Monitoring Rate Limits

You can check the current rate limit status for debugging:

```python
from shared.services import RateLimitService
from shared.data_access import RateLimitOperation

rate_limit_service = RateLimitService()

status = rate_limit_service.get_rate_limit_status(
    operation=RateLimitOperation.SESSION_CREATE,
    identifier_type='user',
    identifier_value='user-123'
)

# Returns:
# {
#   'count': 15,
#   'limit': 50,
#   'reset_in_seconds': 1800,
#   'window_duration': 3600
# }
```

## Configuration

Rate limits are configured via environment variables:

```bash
RATE_LIMIT_SESSIONS_PER_HOUR=50
RATE_LIMIT_LISTENER_JOINS_PER_MIN=10
RATE_LIMIT_CONNECTION_ATTEMPTS_PER_MIN=20
RATE_LIMIT_HEARTBEATS_PER_MIN=2
```

These can be adjusted per environment (dev, staging, prod) in the CDK stack configuration.

## Graceful Degradation

If the RateLimits table is unavailable, the rate limiting service will:

1. Log a warning
2. Allow the request (fail open)
3. Continue normal operation

This ensures availability even when rate limiting is temporarily unavailable.

## Testing

See `tests/unit/test_rate_limit_service.py` for unit tests and `tests/integration/test_rate_limiting_integration.py` for integration tests.

