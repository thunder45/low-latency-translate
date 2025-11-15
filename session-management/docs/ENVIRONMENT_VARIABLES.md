# Environment Variables Reference

This document defines the standard environment variables used across all Lambda functions in the WebSocket Audio Integration system.

## Naming Convention

Environment variables follow these conventions:

- **UPPERCASE_SNAKE_CASE**: All environment variables use uppercase with underscores
- **Descriptive names**: Names clearly indicate purpose
- **Consistent suffixes**: 
  - `_TABLE_NAME` for DynamoDB tables
  - `_FUNCTION_NAME` for Lambda functions
  - `_ENDPOINT` for API endpoints
  - `_TIMEOUT_*` for timeout values
  - `_MAX_*` for maximum limits
  - `_ENABLE_*` for feature flags

## Standard Environment Variables

### DynamoDB Tables

| Variable | Default | Description | Used By |
|----------|---------|-------------|---------|
| `SESSIONS_TABLE_NAME` | `Sessions` | Sessions table name | All handlers |
| `CONNECTIONS_TABLE_NAME` | `Connections` | Connections table name | All handlers |
| `RATE_LIMITS_TABLE_NAME` | `RateLimits` | Rate limits table name | Rate limit service |
| `TRANSLATION_CACHE_TABLE_NAME` | `TranslationCache` | Translation cache table | Translation pipeline |

### AWS Service Configuration

| Variable | Default | Description | Used By |
|----------|---------|-------------|---------|
| `AWS_REGION` | `us-east-1` | AWS region | All functions |
| `API_GATEWAY_ENDPOINT` | - | API Gateway endpoint URL | Connection handlers |

### Lambda Functions

| Variable | Default | Description | Used By |
|----------|---------|-------------|---------|
| `TRANSLATION_PIPELINE_FUNCTION_NAME` | `TranslationProcessor` | Translation Lambda | Audio processor |
| `EMOTION_PROCESSOR_FUNCTION_NAME` | `EmotionProcessor` | Emotion Lambda | Audio processor |

### Session Configuration

| Variable | Default | Description | Used By |
|----------|---------|-------------|---------|
| `SESSION_MAX_DURATION_HOURS` | `2` | Maximum session duration | Session handlers |
| `MAX_LISTENERS_PER_SESSION` | `500` | Maximum listeners per session | Connection handler |
| `SUPPORTED_LANGUAGES` | `en,es,fr,de,pt,it,ja,ko,zh` | Supported language codes | Language validator |

### Connection Configuration

| Variable | Default | Description | Used By |
|----------|---------|-------------|---------|
| `CONNECTION_IDLE_TIMEOUT_SECONDS` | `120` | Idle timeout (2 minutes) | Timeout handler |
| `CONNECTION_REFRESH_MINUTES` | `100` | Refresh warning time | Heartbeat handler |
| `CONNECTION_WARNING_MINUTES` | `110` | Final warning time | Heartbeat handler |

### Audio Processing

| Variable | Default | Description | Used By |
|----------|---------|-------------|---------|
| `AUDIO_RATE_LIMIT` | `50` | Max audio chunks/second | Audio processor |
| `AUDIO_CHUNK_MAX_SIZE_BYTES` | `32768` | Max audio chunk size (32KB) | Audio processor |
| `AUDIO_CHUNK_MIN_SIZE_BYTES` | `100` | Min audio chunk size | Audio processor |
| `AUDIO_SAMPLE_RATE_HZ` | `16000` | Expected sample rate | Audio processor |

### Feature Flags

| Variable | Default | Description | Used By |
|----------|---------|-------------|---------|
| `ENABLE_EMOTION_DETECTION` | `true` | Enable emotion detection | Audio processor |
| `ENABLE_AUDIO_QUALITY_VALIDATION` | `true` | Enable quality checks | Audio processor |
| `ENABLE_PARTIAL_RESULTS` | `true` | Enable partial transcription | Audio processor |
| `ENABLE_TRANSLATION_CACHING` | `true` | Enable translation cache | Translation pipeline |

### Transcription Configuration

| Variable | Default | Description | Used By |
|----------|---------|-------------|---------|
| `MIN_STABILITY_THRESHOLD` | `0.85` | Min stability for forwarding | Audio processor |
| `MAX_BUFFER_TIMEOUT_SECONDS` | `5.0` | Max buffer timeout | Audio processor |
| `TRANSCRIBE_STREAM_TIMEOUT_SECONDS` | `60` | Stream idle timeout | Audio processor |

### Logging & Monitoring

| Variable | Default | Description | Used By |
|----------|---------|-------------|---------|
| `LOG_LEVEL` | `INFO` | Logging level | All functions |
| `ENABLE_XRAY_TRACING` | `false` | Enable X-Ray tracing | All functions |
| `METRICS_NAMESPACE` | `WebSocketAudio` | CloudWatch namespace | All functions |

### Rate Limiting

| Variable | Default | Description | Used By |
|----------|---------|-------------|---------|
| `RATE_LIMIT_AUDIO_CHUNKS` | `50` | Audio chunks/second | Rate limiter |
| `RATE_LIMIT_CONTROL_MESSAGES` | `10` | Control messages/second | Rate limiter |
| `RATE_LIMIT_SESSION_CREATION` | `5` | Sessions/minute per IP | Rate limiter |
| `RATE_LIMIT_WARNING_THRESHOLD` | `3` | Warnings before close | Rate limiter |

## Environment-Specific Values

### Development

```bash
# DynamoDB tables
export SESSIONS_TABLE_NAME='Sessions-Dev'
export CONNECTIONS_TABLE_NAME='Connections-Dev'

# Feature flags
export ENABLE_EMOTION_DETECTION='true'
export ENABLE_AUDIO_QUALITY_VALIDATION='true'

# Logging
export LOG_LEVEL='DEBUG'
export ENABLE_XRAY_TRACING='true'
```

### Staging

```bash
# DynamoDB tables
export SESSIONS_TABLE_NAME='Sessions-Staging'
export CONNECTIONS_TABLE_NAME='Connections-Staging'

# Feature flags
export ENABLE_EMOTION_DETECTION='true'
export ENABLE_AUDIO_QUALITY_VALIDATION='true'

# Logging
export LOG_LEVEL='INFO'
export ENABLE_XRAY_TRACING='true'
```

### Production

```bash
# DynamoDB tables
export SESSIONS_TABLE_NAME='Sessions-Prod'
export CONNECTIONS_TABLE_NAME='Connections-Prod'

# Feature flags
export ENABLE_EMOTION_DETECTION='true'
export ENABLE_AUDIO_QUALITY_VALIDATION='true'

# Logging
export LOG_LEVEL='INFO'
export ENABLE_XRAY_TRACING='false'
```

## CDK Configuration

Environment variables are set in CDK stacks:

```python
# session-management/infrastructure/stacks/session_management_stack.py

connection_handler = lambda_.Function(
    self, 'ConnectionHandler',
    runtime=lambda_.Runtime.PYTHON_3_11,
    handler='handler.lambda_handler',
    code=lambda_.Code.from_asset('lambda/connection_handler'),
    environment={
        # DynamoDB tables
        'SESSIONS_TABLE_NAME': sessions_table.table_name,
        'CONNECTIONS_TABLE_NAME': connections_table.table_name,
        
        # Configuration
        'SESSION_MAX_DURATION_HOURS': '2',
        'MAX_LISTENERS_PER_SESSION': '500',
        'SUPPORTED_LANGUAGES': 'en,es,fr,de,pt,it,ja,ko,zh',
        
        # API Gateway
        'API_GATEWAY_ENDPOINT': api.attr_api_endpoint,
        
        # Logging
        'LOG_LEVEL': 'INFO',
    }
)
```

## Accessing Environment Variables

### Python

```python
import os
from shared.config.table_names import get_table_name, SESSIONS_TABLE_NAME

# Using helper function (recommended)
sessions_table = get_table_name('SESSIONS_TABLE_NAME', SESSIONS_TABLE_NAME)

# Direct access
log_level = os.getenv('LOG_LEVEL', 'INFO')
max_listeners = int(os.getenv('MAX_LISTENERS_PER_SESSION', '500'))

# Feature flags
enable_emotion = os.getenv('ENABLE_EMOTION_DETECTION', 'true').lower() == 'true'
```

## Validation

All environment variables should be validated on Lambda cold start:

```python
def validate_environment():
    """Validate required environment variables."""
    required_vars = [
        'SESSIONS_TABLE_NAME',
        'CONNECTIONS_TABLE_NAME',
        'API_GATEWAY_ENDPOINT'
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        raise ValueError(f"Missing required environment variables: {missing}")
```

## Best Practices

1. **Use constants**: Import from `shared.config.table_names` instead of hardcoding
2. **Provide defaults**: Always provide sensible defaults for optional variables
3. **Validate on startup**: Validate required variables on Lambda cold start
4. **Document changes**: Update this document when adding new variables
5. **Use feature flags**: Use `ENABLE_*` variables for gradual rollouts
6. **Type conversion**: Convert string values to appropriate types (int, bool, etc.)
7. **Consistent naming**: Follow naming conventions for new variables

## Troubleshooting

**Missing environment variable errors:**
- Check CDK stack configuration
- Verify variable name matches exactly (case-sensitive)
- Ensure variable set in correct environment (dev/staging/prod)

**Type conversion errors:**
- Verify default values match expected type
- Use appropriate conversion (int(), float(), .lower() == 'true')

**Feature flag not working:**
- Check boolean conversion: `os.getenv('FLAG', 'true').lower() == 'true'`
- Verify CDK sets variable correctly

## Related Documentation

- [Table Names Configuration](../shared/config/table_names.py)
- [CDK Stack Configuration](../infrastructure/stacks/session_management_stack.py)
- [Error Codes Reference](ERROR_CODES_REFERENCE.md)
