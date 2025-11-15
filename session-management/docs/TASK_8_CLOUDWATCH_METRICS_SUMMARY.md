# Task 8: Add CloudWatch Metrics and Alarms

## Task Description
Implemented comprehensive CloudWatch metrics and alarms for monitoring WebSocket audio integration, including audio processing, control messages, session status, rate limiting, and error tracking.

## Task Instructions
Create CloudWatch metrics emitters for both audio-transcription and session-management components to track:
- Audio processing metrics (chunks received, latency, drops, buffer overflows)
- Transcribe stream metrics (initialization latency, errors)
- Control message metrics (received, latency, listener notifications)
- Session status metrics (queries, periodic updates)
- Rate limiting metrics (violations, connections closed)
- Error metrics (Lambda errors, DynamoDB errors)

Configure CloudWatch alarms for critical and warning thresholds to enable proactive monitoring and alerting.

## Task Tests
No unit tests required for this task as it involves metrics emission infrastructure. Metrics will be validated through:
- Manual testing with CloudWatch console
- Integration testing in Task 11
- Production monitoring after deployment

## Task Solution

### Files Created

**1. audio-transcription/shared/utils/metrics_emitter.py** (320 lines)
- `MetricsEmitter` class for audio processing metrics
- Methods for emitting audio chunk, latency, error, and Transcribe metrics
- `MetricsContext` context manager for automatic latency tracking
- Buffered metric emission for efficiency (batch size: 20)
- Namespace: `AudioTranscription/WebSocket`

**2. session-management/shared/utils/metrics_emitter.py** (280 lines)
- `MetricsEmitter` class for session management metrics
- Methods for emitting control message, status query, and error metrics
- `MetricsContext` context manager for latency tracking
- Buffered metric emission for efficiency
- Namespace: `SessionManagement/WebSocket`

**3. session-management/infrastructure/stacks/cloudwatch_alarms.py** (350 lines)
- `CloudWatchAlarms` CDK construct for alarm configuration
- Critical alarms:
  - Audio latency p95 >100ms for 5 minutes
  - Transcribe error rate >5% for 5 minutes
  - Lambda error rate >1% for 5 minutes
- Warning alarms:
  - Audio latency p95 >75ms for 10 minutes
  - Control latency p95 >150ms for 10 minutes
  - Rate limit violations >100/min
- Additional alarms for buffer overflows, notification failures, DynamoDB errors

### Key Implementation Decisions

**1. Buffered Metric Emission**
- Batch metrics in groups of 20 before sending to CloudWatch
- Reduces API calls and improves performance
- Automatic flush on buffer full or object destruction

**2. Namespace Organization**
- `AudioTranscription/WebSocket` for audio processing metrics
- `SessionManagement/WebSocket` for control and status metrics
- Clear separation enables targeted monitoring and cost optimization

**3. Metric Dimensions**
- SessionId dimension for per-session tracking
- ActionType dimension for control message breakdown
- ErrorType dimension for error categorization
- Enables detailed filtering and analysis in CloudWatch

**4. Alarm Thresholds**
- Based on requirements from design document
- Critical alarms for system-impacting issues (5-minute evaluation)
- Warning alarms for degraded performance (10-minute evaluation)
- Treat missing data as NOT_BREACHING to avoid false alarms

**5. Context Managers**
- `MetricsContext` for automatic latency tracking
- Simplifies instrumentation code
- Ensures metrics are emitted even if exceptions occur

### Integration Points

**Audio Processor Lambda**:
```python
from shared.utils.metrics_emitter import MetricsEmitter, MetricsContext

metrics = MetricsEmitter()

# Track audio chunk
metrics.emit_audio_chunk_received(session_id, chunk_size)

# Track latency with context manager
with MetricsContext(metrics, 'AudioProcessingLatency', session_id):
    process_audio_chunk(chunk)
```

**Connection Handler Lambda**:
```python
from shared.utils.metrics_emitter import MetricsEmitter, MetricsContext

metrics = MetricsEmitter()

# Track control message
metrics.emit_control_message_received(session_id, 'pauseBroadcast')

# Track latency
with MetricsContext(metrics, 'control', session_id, 'pauseBroadcast'):
    handle_pause_broadcast()
```

**Session Status Handler Lambda**:
```python
metrics.emit_status_query_received(session_id)

with MetricsContext(metrics, 'status', session_id):
    query_session_status()
```

### Metrics Summary

**Audio Processing Metrics**:
- AudioChunksReceived (Count, per session)
- AudioChunkSize (Bytes, per session)
- AudioProcessingLatency (Milliseconds, p50/p95/p99)
- AudioChunksDropped (Count, by reason)
- AudioBufferOverflows (Count, per session)
- TranscribeStreamInitLatency (Milliseconds)
- TranscribeStreamErrors (Count, by error type)

**Control Message Metrics**:
- ControlMessagesReceived (Count, by action type)
- ControlMessageLatency (Milliseconds, p50/p95/p99)
- ListenerNotificationLatency (Milliseconds)
- ListenersNotified (Count, per session)
- ListenerNotificationFailures (Count, by error type)

**Session Status Metrics**:
- StatusQueriesReceived (Count, per session)
- StatusQueryLatency (Milliseconds, p50/p95/p99)
- PeriodicStatusUpdatesSent (Count, per session)

**Rate Limiting Metrics**:
- RateLimitViolations (Count, by message type)
- ConnectionsClosedForRateLimit (Count)

**Error Metrics**:
- LambdaErrors (Count, by handler and error type)
- DynamoDBErrors (Count, by operation and error code)

### CloudWatch Alarms Summary

**Critical Alarms** (immediate action required):
1. Audio latency p95 >100ms for 5 minutes
2. Transcribe error rate >5% for 5 minutes
3. Lambda error rate >1% for 5 minutes

**Warning Alarms** (investigation needed):
1. Audio latency p95 >75ms for 10 minutes
2. Control latency p95 >150ms for 10 minutes
3. Rate limit violations >100/min
4. Audio buffer overflows >10 in 5 minutes
5. Listener notification failures >50 in 5 minutes
6. DynamoDB errors >10 in 5 minutes
7. Connections closed for rate limiting >10 in 5 minutes

### Next Steps

1. **Task 9**: Add structured logging to complement metrics
2. **Task 10.X**: Integrate CloudWatchAlarms construct into session_management_stack.py
3. **Task 11**: Integration testing to validate metrics emission
4. **Production**: Configure SNS topic for alarm notifications
5. **Production**: Create CloudWatch dashboard for visualization

### Notes

- Metrics emitters are designed to fail gracefully - errors in metric emission don't affect core functionality
- Buffering reduces CloudWatch API costs while maintaining near-real-time visibility
- Alarm thresholds may need tuning based on production traffic patterns
- Consider adding composite alarms for complex failure scenarios
- SNS topic for alarm notifications needs to be created and configured in CDK stack
