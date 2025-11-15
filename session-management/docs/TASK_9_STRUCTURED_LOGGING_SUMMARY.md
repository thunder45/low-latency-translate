# Task 9: Add Structured Logging

## Task Description
Implemented structured JSON logging for all Lambda handlers to enable efficient CloudWatch Logs Insights queries, correlation tracking, and operational visibility.

## Task Instructions
Implement JSON log format for all handlers with:
- Correlation IDs (sessionId, connectionId, requestId)
- Log all WebSocket messages at DEBUG level
- Log all Transcribe events at DEBUG level
- Log all errors at ERROR level with context
- Configure log retention (12 hours)

## Task Tests
No unit tests required for logging infrastructure. Logging will be validated through:
- Manual testing with CloudWatch Logs console
- CloudWatch Logs Insights queries
- Integration testing in Task 11

## Task Solution

### Files Created

**1. session-management/shared/utils/structured_logger.py** (350 lines)
- `StructuredLogger` class for JSON-formatted logging
- Correlation ID tracking (sessionId, connectionId, requestId)
- Specialized logging methods:
  - `log_websocket_message()` - WebSocket message logging
  - `log_state_change()` - State transition logging
  - `log_performance()` - Performance metric logging
- `LoggingContext` context manager for operation duration tracking
- `configure_lambda_logging()` - Lambda environment setup

**2. audio-transcription/shared/utils/structured_logger.py** (350 lines)
- Same implementation as session-management
- Additional method: `log_transcribe_event()` for Transcribe events
- Supports audio processing specific logging

### Key Implementation Decisions

**1. JSON Format**
- All logs output as single-line JSON for CloudWatch Logs Insights
- Standardized fields: timestamp, level, component, message, operation
- Context fields in nested `context` object
- ISO 8601 timestamps with UTC timezone

**2. Correlation IDs**
- sessionId: Links all logs for a session
- connectionId: Links all logs for a connection
- requestId: Links all logs for a Lambda invocation
- Enables end-to-end request tracing

**3. Log Levels**
- DEBUG: WebSocket messages, Transcribe events, performance metrics
- INFO: State changes, successful operations
- WARNING: Unexpected but handled conditions
- ERROR: Errors requiring attention with full context

**4. Context Manager**
- `LoggingContext` for automatic operation timing
- Logs operation start, end, duration, and errors
- Simplifies instrumentation code

**5. Environment Configuration**
- LOG_LEVEL environment variable (default: INFO)
- Suppresses boto3/botocore debug logs unless explicitly enabled
- Configurable per Lambda function

### Usage Examples

**Basic Logging**:
```python
from shared.utils.structured_logger import StructuredLogger, configure_lambda_logging

# Configure at module level
configure_lambda_logging()

# Initialize logger
logger = StructuredLogger(
    component='ConnectionHandler',
    session_id=session_id,
    connection_id=connection_id,
    request_id=context.request_id
)

# Log messages
logger.info('Connection established', operation='connect')
logger.error('Failed to update session', operation='update_session', error=e)
```

**WebSocket Message Logging**:
```python
logger.log_websocket_message(
    direction='inbound',
    message_type='sendAudio',
    message_size=len(message_body)
)
```

**Transcribe Event Logging**:
```python
logger.log_transcribe_event(
    event_type='partial',
    stability=0.85,
    text_length=len(text),
    is_final=False
)
```

**State Change Logging**:
```python
logger.log_state_change(
    state_type='broadcastState.isPaused',
    old_value=False,
    new_value=True
)
```

**Operation Duration Tracking**:
```python
from shared.utils.structured_logger import LoggingContext

with LoggingContext(logger, 'process_audio_chunk', chunk_size=chunk_size):
    # Operation code here
    process_chunk(chunk)
    # Automatically logs start, end, duration
```

### Log Format Example

```json
{
  "timestamp": "2025-11-15T10:30:45.123Z",
  "level": "INFO",
  "component": "ConnectionHandler",
  "message": "Connection established",
  "sessionId": "golden-eagle-427",
  "connectionId": "abc123xyz",
  "requestId": "req-456",
  "operation": "connect",
  "context": {
    "role": "speaker",
    "sourceLanguage": "en"
  }
}
```

### CloudWatch Logs Insights Queries

**Find all logs for a session**:
```
fields @timestamp, level, operation, message
| filter sessionId = "golden-eagle-427"
| sort @timestamp asc
```

**Find errors in last hour**:
```
fields @timestamp, component, operation, message, context.error_type
| filter level = "ERROR"
| sort @timestamp desc
```

**Track operation latency**:
```
fields @timestamp, operation, context.duration_ms
| filter operation = "process_audio_chunk"
| stats avg(context.duration_ms), max(context.duration_ms), p99(context.duration_ms)
```

**WebSocket message volume**:
```
fields @timestamp
| filter operation = "websocket_message"
| stats count() by context.message_type
```

### Integration with Existing Code

**Connection Handler**:
```python
# At module level
from shared.utils.structured_logger import StructuredLogger, configure_lambda_logging
configure_lambda_logging()

def lambda_handler(event, context):
    logger = StructuredLogger(
        component='ConnectionHandler',
        connection_id=event['requestContext']['connectionId'],
        request_id=context.request_id
    )
    
    logger.info('Processing connection event', operation='handler_entry')
    # ... handler code ...
```

**Audio Processor**:
```python
from shared.utils.structured_logger import StructuredLogger, LoggingContext
configure_lambda_logging()

def lambda_handler(event, context):
    logger = StructuredLogger(
        component='AudioProcessor',
        connection_id=event['requestContext']['connectionId'],
        request_id=context.request_id
    )
    
    with LoggingContext(logger, 'process_audio'):
        # ... processing code ...
        logger.log_transcribe_event('partial', stability=0.85)
```

### Log Retention Configuration

Log retention should be configured in CDK:
```python
logs.LogGroup(
    self,
    'ConnectionHandlerLogs',
    log_group_name=f'/aws/lambda/{function_name}',
    retention=logs.RetentionDays.TWELVE_HOURS,
    removal_policy=RemovalPolicy.DESTROY
)
```

### Benefits

1. **Efficient Querying**: JSON format enables powerful CloudWatch Logs Insights queries
2. **Correlation**: Correlation IDs link related logs across Lambda invocations
3. **Debugging**: Detailed context in error logs speeds troubleshooting
4. **Performance**: Operation duration tracking identifies bottlenecks
5. **Cost**: 12-hour retention reduces storage costs while maintaining operational visibility
6. **Compliance**: Structured format supports audit and compliance requirements

### Next Steps

1. **Task 10.X**: Configure log retention in CDK stacks
2. **Task 11**: Integration testing to validate logging
3. **Production**: Create CloudWatch Logs Insights saved queries
4. **Production**: Set up log-based metrics for additional monitoring
5. **Production**: Configure log export to S3 for long-term retention (if needed)

### Notes

- Logging is designed to fail gracefully - errors in logging don't affect core functionality
- DEBUG level logs provide detailed visibility but increase CloudWatch costs
- Consider using INFO level in production and DEBUG only for troubleshooting
- Correlation IDs enable distributed tracing without X-Ray overhead
- JSON format is compatible with log aggregation tools (Splunk, ELK, etc.)
