# Error Codes Reference

This document provides a comprehensive reference for all error codes used in the WebSocket Audio Integration system.

## Overview

Error codes are standardized across all modules to ensure consistent error handling and reporting. Each error code maps to:
- An HTTP status code
- A user-friendly error message
- A specific error category

## Error Code Format

Error codes follow the pattern: `{CATEGORY}_{SPECIFIC_ERROR}`

Example: `SESSION_NOT_FOUND`, `AUDIO_INVALID_FORMAT`

## Error Categories

### Authentication & Authorization (AUTH_*)

| Error Code | HTTP Status | Message | Description |
|------------|-------------|---------|-------------|
| `AUTH_UNAUTHORIZED` | 403 | Unauthorized access | User does not have permission for this operation |
| `AUTH_TOKEN_INVALID` | 401 | Invalid authentication token | JWT token is malformed or invalid |
| `AUTH_TOKEN_EXPIRED` | 401 | Authentication token expired | JWT token has expired |
| `AUTH_MISSING_TOKEN` | 401 | Authentication token required | No authentication token provided |
| `AUTH_INVALID_ROLE` | 403 | Invalid role for this operation | User role does not match required role |

### Session Management (SESSION_*)

| Error Code | HTTP Status | Message | Description |
|------------|-------------|---------|-------------|
| `SESSION_NOT_FOUND` | 404 | Session not found | Session ID does not exist |
| `SESSION_INACTIVE` | 410 | Session is no longer active | Session has been ended by speaker |
| `SESSION_EXPIRED` | 410 | Session has expired | Session exceeded maximum duration |
| `SESSION_ALREADY_EXISTS` | 409 | Session already exists | Attempted to create duplicate session |
| `SESSION_CREATION_FAILED` | 500 | Failed to create session | Internal error during session creation |
| `SESSION_MAX_LISTENERS_REACHED` | 429 | Maximum number of listeners reached | Session has reached listener limit (500) |
| `SESSION_INVALID_ID_FORMAT` | 400 | Invalid session ID format | Session ID does not match expected format |

### Connection Management (CONNECTION_*)

| Error Code | HTTP Status | Message | Description |
|------------|-------------|---------|-------------|
| `CONNECTION_NOT_FOUND` | 404 | Connection not found | Connection ID does not exist |
| `CONNECTION_TIMEOUT` | 408 | Connection timed out due to inactivity | Connection idle for >2 minutes |
| `CONNECTION_CLOSED` | 410 | Connection has been closed | Connection was closed by client or server |
| `CONNECTION_INVALID` | 400 | Invalid connection | Connection is in invalid state |
| `CONNECTION_REFRESH_REQUIRED` | 426 | Connection refresh required | Connection approaching 2-hour limit |

### Audio Processing (AUDIO_*)

| Error Code | HTTP Status | Message | Description |
|------------|-------------|---------|-------------|
| `AUDIO_INVALID_FORMAT` | 400 | Invalid audio format | Audio format not supported (must be PCM 16-bit) |
| `AUDIO_CHUNK_TOO_LARGE` | 413 | Audio chunk exceeds maximum size | Audio chunk >32KB |
| `AUDIO_CHUNK_TOO_SMALL` | 400 | Audio chunk below minimum size | Audio chunk <100 bytes |
| `AUDIO_INVALID_SAMPLE_RATE` | 400 | Invalid audio sample rate | Sample rate not 16kHz |
| `AUDIO_INVALID_ENCODING` | 400 | Invalid audio encoding | Encoding not PCM |
| `AUDIO_QUALITY_LOW` | 422 | Audio quality below acceptable threshold | SNR <10dB |
| `AUDIO_CLIPPING_DETECTED` | 422 | Audio clipping detected - reduce microphone volume | Audio distortion detected |
| `AUDIO_ECHO_DETECTED` | 422 | Echo detected - check audio setup | Echo/feedback detected |
| `AUDIO_SILENCE_DETECTED` | 422 | No audio detected - check microphone | Microphone may be muted |
| `AUDIO_PROCESSING_FAILED` | 500 | Audio processing failed | Internal error during audio processing |

### Validation (VALIDATION_*)

| Error Code | HTTP Status | Message | Description |
|------------|-------------|---------|-------------|
| `VALIDATION_INVALID_LANGUAGE` | 400 | Invalid or unsupported language code | Language code not in supported list |
| `VALIDATION_INVALID_QUALITY_TIER` | 400 | Invalid quality tier | Quality tier not 'standard' or 'premium' |
| `VALIDATION_INVALID_ACTION` | 400 | Invalid action | Action not recognized |
| `VALIDATION_MISSING_PARAMETER` | 400 | Required parameter missing | Required field not provided |
| `VALIDATION_INVALID_PARAMETER` | 400 | Invalid parameter value | Parameter value out of range or invalid |
| `VALIDATION_MESSAGE_TOO_LARGE` | 413 | Message exceeds maximum size | Message >1MB |
| `VALIDATION_INVALID_MESSAGE_FORMAT` | 400 | Invalid message format | Message not valid JSON or binary |

### Rate Limiting (RATE_LIMIT_*)

| Error Code | HTTP Status | Message | Description |
|------------|-------------|---------|-------------|
| `RATE_LIMIT_EXCEEDED` | 429 | Rate limit exceeded | Generic rate limit exceeded |
| `RATE_LIMIT_AUDIO_CHUNKS` | 429 | Audio chunk rate limit exceeded | >50 chunks/second |
| `RATE_LIMIT_CONTROL_MESSAGES` | 429 | Control message rate limit exceeded | >10 messages/second |
| `RATE_LIMIT_SESSION_CREATION` | 429 | Session creation rate limit exceeded | >5 sessions/minute per IP |

### Internal Errors (INTERNAL_*)

| Error Code | HTTP Status | Message | Description |
|------------|-------------|---------|-------------|
| `INTERNAL_SERVER_ERROR` | 500 | Internal server error | Generic internal error |
| `INTERNAL_DATABASE_ERROR` | 500 | Database error | DynamoDB operation failed |
| `INTERNAL_TRANSCRIBE_ERROR` | 500 | Transcription service error | AWS Transcribe error |
| `INTERNAL_TRANSLATION_ERROR` | 500 | Translation service error | AWS Translate error |
| `INTERNAL_POLLY_ERROR` | 500 | Text-to-speech service error | AWS Polly error |
| `INTERNAL_EMOTION_DETECTION_ERROR` | 500 | Emotion detection error | Emotion detection failed |
| `INTERNAL_CONFIGURATION_ERROR` | 500 | Configuration error | Invalid configuration |

## Usage Examples

### Python

```python
from shared.utils.error_codes import ErrorCode, format_error_response, get_http_status

# Format error response
error_response = format_error_response(
    ErrorCode.SESSION_NOT_FOUND,
    details='Session ID: golden-eagle-427',
    correlation_id='abc-123'
)

# Get HTTP status code
status_code = get_http_status(ErrorCode.SESSION_NOT_FOUND)  # Returns 404

# Return error from Lambda
return {
    'statusCode': status_code,
    'body': json.dumps(error_response)
}
```

### Error Response Format

All error responses follow this standard format:

```json
{
  "type": "error",
  "code": "SESSION_NOT_FOUND",
  "message": "Session not found",
  "details": "Session ID: golden-eagle-427",
  "correlationId": "abc-123",
  "timestamp": 1699500000000
}
```

## Adding New Error Codes

To add a new error code:

1. Add enum value to `ErrorCode` in `shared/utils/error_codes.py`
2. Add HTTP status mapping to `ERROR_CODE_TO_HTTP_STATUS`
3. Add user message to `ERROR_CODE_TO_MESSAGE`
4. Document in this reference file
5. Update tests

## Best Practices

1. **Use specific error codes**: Prefer `SESSION_NOT_FOUND` over generic `INTERNAL_SERVER_ERROR`
2. **Include details**: Provide additional context in the `details` field
3. **Include correlation IDs**: Always include correlation ID for tracing
4. **Log errors**: Log errors with error code and correlation ID
5. **Don't expose internals**: User messages should not expose internal implementation details

## Error Handling Guidelines

### For Developers

- Always use error codes from the `ErrorCode` enum
- Never hardcode error messages
- Always include correlation IDs in error responses
- Log errors with appropriate severity level
- Include stack traces for internal errors (in logs, not responses)

### For Frontend

- Display user-friendly messages from error responses
- Show correlation ID for support purposes
- Provide actionable guidance when possible (e.g., "reduce microphone volume")
- Handle specific error codes with appropriate UI feedback

## Monitoring & Alerting

Error codes are emitted as CloudWatch metrics:

- Metric Name: `ErrorCount`
- Dimensions: `ErrorCode`, `Component`
- Unit: Count

Critical errors trigger CloudWatch alarms:
- `AUTH_*` errors: Security alert
- `INTERNAL_*` errors: Operational alert
- `RATE_LIMIT_*` errors: Capacity alert

## Related Documentation

- [WebSocket Audio Integration](WEBSOCKET_AUDIO_INTEGRATION.md)
- [API Reference](../README.md#api-reference)
- [Troubleshooting Guide](../README.md#troubleshooting)
