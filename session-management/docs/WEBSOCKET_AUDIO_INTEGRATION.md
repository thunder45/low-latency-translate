# WebSocket Audio Integration Documentation

## Overview

This document describes the WebSocket audio integration feature that enables real-time audio broadcasting from speakers to listeners with transcription and translation. The integration connects WebSocket audio reception with AWS Transcribe Streaming API and the Translation Pipeline.

## Architecture

### High-Level Flow

```
Speaker (Browser)
    │
    ├─ WSS: sendAudio (binary audio chunks)
    ├─ WSS: pauseBroadcast, resumeBroadcast
    ├─ WSS: muteBroadcast, unmuteBroadcast
    ├─ WSS: setVolume
    └─ WSS: getSessionStatus
    │
    ▼
API Gateway WebSocket API
    │
    ├─ Route: sendAudio → Audio Processor Lambda
    ├─ Route: pauseBroadcast → Connection Handler Lambda
    ├─ Route: resumeBroadcast → Connection Handler Lambda
    ├─ Route: muteBroadcast → Connection Handler Lambda
    ├─ Route: unmuteBroadcast → Connection Handler Lambda
    ├─ Route: setVolume → Connection Handler Lambda
    └─ Route: getSessionStatus → Session Status Handler Lambda
    │
    ▼
Lambda Handlers
    │
    ├─ Audio Processor
    │   ├─ Validates connection & session
    │   ├─ Applies rate limiting
    │   ├─ Validates audio format
    │   ├─ Forwards to Transcribe Stream
    │   └─ Processes transcription events
    │
    ├─ Connection Handler (Extended)
    │   ├─ Handles pause/resume
    │   ├─ Handles mute/unmute
    │   ├─ Handles volume changes
    │   ├─ Updates broadcast state
    │   └─ Notifies all listeners
    │
    └─ Session Status Handler
        ├─ Queries session data
        ├─ Aggregates listener stats
        ├─ Returns language distribution
        └─ Sends periodic updates
    │
    ▼
AWS Services
    ├─ DynamoDB (Sessions, Connections)
    ├─ AWS Transcribe Streaming API
    └─ Translation Pipeline Lambda
```

## WebSocket Routes

### Audio Routes

#### sendAudio

**Purpose**: Receive audio chunks from speaker

**Direction**: Client → Server

**Message Format**:
```json
{
  "action": "sendAudio",
  "audioData": "<base64-encoded PCM audio>"
}
```

**Audio Requirements**:
- Format: PCM 16-bit mono
- Sample Rate: 16000 Hz
- Chunk Size: 100-200ms (1600-3200 bytes)
- Max Chunk Size: 32 KB
- Rate Limit: 50 chunks/second

**Response**:
```json
{
  "type": "audioReceived",
  "sessionId": "golden-eagle-427",
  "timestamp": 1699500000
}
```

**Error Responses**:
- `400 INVALID_AUDIO_FORMAT`: Audio format invalid
- `403 UNAUTHORIZED`: Not a speaker
- `404 SESSION_NOT_FOUND`: Session doesn't exist
- `413 PAYLOAD_TOO_LARGE`: Chunk exceeds 32 KB
- `429 RATE_LIMIT_EXCEEDED`: Too many chunks

### Control Routes

#### pauseBroadcast

**Purpose**: Pause audio broadcasting

**Direction**: Client → Server

**Message Format**:
```json
{
  "action": "pauseBroadcast"
}
```

**Response**:
```json
{
  "type": "broadcastPaused",
  "sessionId": "golden-eagle-427",
  "timestamp": 1699500000
}
```

**Listener Notification**:
```json
{
  "type": "broadcastPaused",
  "sessionId": "golden-eagle-427",
  "timestamp": 1699500000
}
```

#### resumeBroadcast

**Purpose**: Resume audio broadcasting

**Direction**: Client → Server

**Message Format**:
```json
{
  "action": "resumeBroadcast"
}
```

**Response**:
```json
{
  "type": "broadcastResumed",
  "sessionId": "golden-eagle-427",
  "timestamp": 1699500000
}
```

**Listener Notification**:
```json
{
  "type": "broadcastResumed",
  "sessionId": "golden-eagle-427",
  "timestamp": 1699500000
}
```

#### muteBroadcast

**Purpose**: Mute microphone

**Direction**: Client → Server

**Message Format**:
```json
{
  "action": "muteBroadcast"
}
```

**Response**:
```json
{
  "type": "broadcastMuted",
  "sessionId": "golden-eagle-427",
  "timestamp": 1699500000
}
```

**Listener Notification**:
```json
{
  "type": "broadcastMuted",
  "sessionId": "golden-eagle-427",
  "timestamp": 1699500000
}
```

#### unmuteBroadcast

**Purpose**: Unmute microphone

**Direction**: Client → Server

**Message Format**:
```json
{
  "action": "unmuteBroadcast"
}
```

**Response**:
```json
{
  "type": "broadcastUnmuted",
  "sessionId": "golden-eagle-427",
  "timestamp": 1699500000
}
```

**Listener Notification**:
```json
{
  "type": "broadcastUnmuted",
  "sessionId": "golden-eagle-427",
  "timestamp": 1699500000
}
```

#### setVolume

**Purpose**: Set broadcast volume

**Direction**: Client → Server

**Message Format**:
```json
{
  "action": "setVolume",
  "volumeLevel": 0.8
}
```

**Parameters**:
- `volumeLevel`: Float between 0.0 and 1.0
- `0.0` = muted
- `1.0` = full volume

**Response**:
```json
{
  "type": "volumeChanged",
  "sessionId": "golden-eagle-427",
  "volumeLevel": 0.8,
  "timestamp": 1699500000
}
```

**Listener Notification**:
```json
{
  "type": "volumeChanged",
  "sessionId": "golden-eagle-427",
  "volumeLevel": 0.8,
  "timestamp": 1699500000
}
```

#### speakerStateChange

**Purpose**: Update multiple broadcast state fields

**Direction**: Client → Server

**Message Format**:
```json
{
  "action": "speakerStateChange",
  "state": {
    "isPaused": false,
    "isMuted": false,
    "volume": 1.0
  }
}
```

**Response**:
```json
{
  "type": "speakerStateChanged",
  "sessionId": "golden-eagle-427",
  "state": {
    "isActive": true,
    "isPaused": false,
    "isMuted": false,
    "volume": 1.0,
    "lastStateChange": 1699500000
  },
  "timestamp": 1699500000
}
```

**Listener Notification**:
```json
{
  "type": "speakerStateChanged",
  "sessionId": "golden-eagle-427",
  "state": {
    "isActive": true,
    "isPaused": false,
    "isMuted": false,
    "volume": 1.0,
    "lastStateChange": 1699500000
  },
  "timestamp": 1699500000
}
```

### Status Routes

#### getSessionStatus

**Purpose**: Query current session statistics

**Direction**: Client → Server

**Message Format**:
```json
{
  "action": "getSessionStatus"
}
```

**Response**:
```json
{
  "type": "sessionStatus",
  "sessionId": "golden-eagle-427",
  "listenerCount": 42,
  "languageDistribution": {
    "es": 15,
    "fr": 12,
    "de": 8,
    "pt": 7
  },
  "sessionDuration": 1847,
  "broadcastState": {
    "isActive": true,
    "isPaused": false,
    "isMuted": false,
    "volume": 1.0,
    "lastStateChange": 1699500000
  },
  "timestamp": 1699500000,
  "updateReason": "requested"
}
```

**Periodic Updates**:

The system automatically sends `sessionStatus` messages:
- Every 30 seconds (updateReason: "periodic")
- When listener count changes >10% (updateReason: "listenerCountChange")
- When new language appears (updateReason: "newLanguage")

### Listener Routes

#### pausePlayback

**Purpose**: Pause audio playback (client-side only)

**Direction**: Client → Server

**Message Format**:
```json
{
  "action": "pausePlayback"
}
```

**Response**:
```json
{
  "type": "playbackPaused",
  "timestamp": 1699500000
}
```

**Note**: This is client-side only. The server acknowledges but doesn't affect broadcast.

#### changeLanguage

**Purpose**: Switch target language

**Direction**: Client → Server

**Message Format**:
```json
{
  "action": "changeLanguage",
  "targetLanguage": "es"
}
```

**Parameters**:
- `targetLanguage`: ISO 639-1 language code (e.g., "es", "fr", "de")

**Response**:
```json
{
  "type": "languageChanged",
  "targetLanguage": "es",
  "timestamp": 1699500000
}
```

**Error Responses**:
- `400 UNSUPPORTED_LANGUAGE`: Language not supported
- `403 UNAUTHORIZED`: Not a listener

## Broadcast State Model

### BroadcastState Structure

```python
{
  "isActive": bool,        # Session is active
  "isPaused": bool,        # Broadcast is paused
  "isMuted": bool,         # Microphone is muted
  "volume": float,         # Volume level (0.0-1.0)
  "lastStateChange": int   # Unix timestamp
}
```

### State Transitions

**Initial State** (session created):
```json
{
  "isActive": true,
  "isPaused": false,
  "isMuted": false,
  "volume": 1.0,
  "lastStateChange": <timestamp>
}
```

**Paused State**:
```json
{
  "isActive": true,
  "isPaused": true,
  "isMuted": false,
  "volume": 1.0,
  "lastStateChange": <timestamp>
}
```

**Muted State**:
```json
{
  "isActive": true,
  "isPaused": false,
  "isMuted": true,
  "volume": 1.0,
  "lastStateChange": <timestamp>
}
```

**Volume Adjusted**:
```json
{
  "isActive": true,
  "isPaused": false,
  "isMuted": false,
  "volume": 0.5,
  "lastStateChange": <timestamp>
}
```

### State Management

**DynamoDB Storage**:
- Stored in Sessions table
- Field: `broadcastState`
- Updated atomically with conditional checks

**Repository Methods**:
```python
# Get current state
state = sessions_repo.get_broadcast_state(session_id)

# Update state
sessions_repo.update_broadcast_state(session_id, new_state)

# Convenience methods
sessions_repo.pause_broadcast(session_id)
sessions_repo.resume_broadcast(session_id)
sessions_repo.mute_broadcast(session_id)
sessions_repo.unmute_broadcast(session_id)
sessions_repo.set_broadcast_volume(session_id, volume_level)
```

## Audio Processing Flow

### 1. Audio Reception

```
Speaker sends audio chunk
    ↓
API Gateway receives binary WebSocket frame
    ↓
Routes to Audio Processor Lambda
    ↓
Lambda extracts connectionId from event
```

### 2. Validation

```
Query Connections table by connectionId
    ↓
Verify role = "speaker"
    ↓
Extract sessionId from connection
    ↓
Query Sessions table by sessionId
    ↓
Verify isActive = true
    ↓
Check broadcastState.isPaused = false
    ↓
Check broadcastState.isMuted = false
```

### 3. Rate Limiting

```
Check chunks per second for connectionId
    ↓
If > 50/sec: Drop chunk, emit metric
    ↓
If violations > 5 sec: Send warning
    ↓
If violations > 30 sec: Close connection
```

### 4. Format Validation

```
First chunk: Validate PCM 16-bit mono, 16kHz
    ↓
Cache validation result
    ↓
Subsequent chunks: Use cached result
```

### 5. Transcribe Stream

```
Initialize Transcribe stream (first chunk)
    ↓
Configure: sourceLanguage, partial results, stability
    ↓
Start async event loop
    ↓
Send audio chunk to stream
    ↓
Process transcription events asynchronously
```

### 6. Event Processing

```
Transcribe emits TranscriptEvent
    ↓
Extract text and stability score
    ↓
If partial: Check stability >= 0.85
    ↓
If final: Always forward
    ↓
Forward to Translation Pipeline
```

## Error Handling

### Client Errors (4xx)

**400 Bad Request**:
- Invalid audio format
- Invalid volume level (not 0.0-1.0)
- Unsupported language
- Invalid message format

**403 Forbidden**:
- Wrong role for action (listener trying speaker action)
- Unauthorized connection

**404 Not Found**:
- Session doesn't exist
- Connection doesn't exist

**413 Payload Too Large**:
- Audio chunk > 32 KB
- Control message > 4 KB
- Total message > 128 KB

**429 Too Many Requests**:
- Rate limit exceeded (audio or control messages)

### Server Errors (5xx)

**500 Internal Server Error**:
- DynamoDB operation failed after retries
- Unexpected error

**503 Service Unavailable**:
- Transcribe API unavailable
- Translation Pipeline unavailable

**504 Gateway Timeout**:
- Lambda timeout
- DynamoDB query timeout

### Retry Strategy

**Transient Errors** (retry with exponential backoff):
- DynamoDB throttling
- Transcribe throttling
- Network timeouts
- Temporary service unavailability

**Retry Configuration**:
```python
{
  'max_attempts': 3,
  'base_delay_ms': 100,
  'max_delay_ms': 2000,
  'exponential_base': 2
}
```

**Permanent Errors** (no retry):
- Invalid authentication
- Unsupported language
- Invalid audio format
- Unauthorized action
- Resource not found

## Performance Characteristics

### Latency Targets

| Operation | Target | Maximum |
|-----------|--------|---------|
| Audio chunk processing | <50ms p95 | 100ms |
| Control message | <100ms p95 | 200ms |
| Session status query | <500ms p95 | 1000ms |
| Listener notification | <150ms p95 | 300ms |

### Throughput

| Metric | Target | Maximum |
|--------|--------|---------|
| Audio chunks/sec per speaker | 50 | 100 |
| Control messages/sec per connection | 10 | 20 |
| Status queries/sec per speaker | 2 | 5 |
| Concurrent sessions | 100 | 500 |
| Listeners per session | 50 | 500 |

### Resource Limits

**Audio Processor Lambda**:
- Memory: 1024 MB
- Timeout: 60 seconds
- Reserved Concurrency: 10

**Connection Handler Lambda**:
- Memory: 512 MB
- Timeout: 10 seconds
- Concurrency: Auto-scaling

**Session Status Handler Lambda**:
- Memory: 256 MB
- Timeout: 5 seconds
- Concurrency: Auto-scaling

## Monitoring

### CloudWatch Metrics

**Audio Processing**:
- `AudioChunksReceived` (Count)
- `AudioProcessingLatency` (Milliseconds, p50/p95/p99)
- `AudioChunksDropped` (Count)
- `AudioBufferOverflows` (Count)
- `TranscribeStreamInitLatency` (Milliseconds)
- `TranscribeStreamErrors` (Count)

**Control Messages**:
- `ControlMessagesReceived` (Count, by action)
- `ControlMessageLatency` (Milliseconds, p50/p95/p99)
- `ListenerNotificationLatency` (Milliseconds)
- `ListenerNotificationFailures` (Count)

**Session Status**:
- `StatusQueriesReceived` (Count)
- `StatusQueryLatency` (Milliseconds, p50/p95/p99)
- `PeriodicStatusUpdatesSent` (Count)

**Rate Limiting**:
- `RateLimitViolations` (Count, by message type)
- `ConnectionsClosedForRateLimit` (Count)

**Errors**:
- `LambdaErrors` (Count, by handler and error type)
- `DynamoDBErrors` (Count, by operation)
- `TranscribeErrors` (Count, by error code)

### CloudWatch Alarms

**Critical** (page on-call):
- Audio latency p95 >100ms for 5 minutes
- Transcribe error rate >5% for 5 minutes
- Lambda error rate >1% for 5 minutes

**Warning** (email):
- Audio latency p95 >75ms for 10 minutes
- Control latency p95 >150ms for 10 minutes
- Rate limit violations >100/minute

### CloudWatch Logs

**Log Format** (JSON):
```json
{
  "timestamp": "2025-11-14T12:34:56.789Z",
  "level": "INFO",
  "correlationId": "golden-eagle-427",
  "component": "AudioProcessor",
  "operation": "process_audio_chunk",
  "message": "Audio chunk processed successfully",
  "metadata": {
    "chunkSize": 3200,
    "processingLatencyMs": 23,
    "transcribeStreamActive": true
  }
}
```

## Security

### Authentication

**Speaker Actions** (require role=speaker):
- sendAudio
- pauseBroadcast, resumeBroadcast
- muteBroadcast, unmuteBroadcast
- setVolume
- speakerStateChange
- getSessionStatus

**Listener Actions** (require role=listener):
- pausePlayback (client-side)
- changeLanguage

### Authorization Flow

```
1. Extract connectionId from WebSocket event
2. Query Connections table
3. Verify role matches required role
4. If mismatch: Return 403 Forbidden
5. If match: Proceed with action
```

### Data Protection

**In Transit**:
- All WebSocket connections use WSS (TLS 1.2+)
- Audio data encrypted in transit

**At Rest**:
- Audio chunks not persisted (processed in memory only)
- Session/connection records in DynamoDB
- Transcription results not stored (forwarded immediately)

**Logging**:
- Never log audio data
- Never log full connection IDs (hash with SHA-256)
- Never log user identifiers
- Log only sanitized metadata

### Rate Limiting

**Audio Chunks**:
- 50 chunks/second per speaker
- Sliding window of 1 second
- Drop excess chunks, emit metric
- Warn after 5 seconds of violations
- Close connection after 30 seconds

**Control Messages**:
- 10 messages/second per connection
- Sliding window of 1 second
- Return 429 if exceeded

**Session Status Queries**:
- 2 queries/second per speaker
- Sliding window of 1 second
- Return 429 if exceeded

## Testing

### Unit Tests

**Audio Processor**:
- `test_audio_chunk_validation.py`
- `test_rate_limiting.py`
- `test_transcribe_stream_initialization.py`
- `test_error_handling.py`

**Connection Handler**:
- `test_pause_resume.py`
- `test_mute_unmute.py`
- `test_volume_control.py`
- `test_listener_notification.py`

**Session Status Handler**:
- `test_status_query.py`
- `test_language_aggregation.py`
- `test_periodic_updates.py`

### Integration Tests

**End-to-End Flow**:
- `test_websocket_audio_e2e.py`
- Tests complete audio flow
- Tests control message flow
- Tests session status queries
- Tests error scenarios
- Tests performance

### Load Tests

**Audio Processing**:
- 100 concurrent speakers
- 50 chunks/second per speaker
- Verify p95 latency <50ms
- Verify no dropped chunks

**Control Messages**:
- 100 speakers sending controls
- 10 messages/second per speaker
- Verify p95 latency <100ms
- Verify all listeners notified

## Troubleshooting

### Common Issues

**Audio Not Processing**:
1. Check session isActive = true
2. Check broadcastState.isPaused = false
3. Check broadcastState.isMuted = false
4. Check Transcribe stream initialized
5. Check CloudWatch logs for errors

**Listeners Not Notified**:
1. Check listener connections exist
2. Check API Gateway Management API permissions
3. Check CloudWatch logs for notification failures
4. Verify listener connectionIds are valid

**High Latency**:
1. Check DynamoDB query latency
2. Check Transcribe stream latency
3. Check Lambda cold starts
4. Check network latency
5. Review CloudWatch metrics

**Rate Limit Violations**:
1. Check audio chunk rate
2. Check control message rate
3. Review rate limiter configuration
4. Check for client bugs
5. Monitor CloudWatch metrics

### Debug Commands

**Check Session State**:
```bash
aws dynamodb get-item \
  --table-name Sessions \
  --key '{"sessionId": {"S": "golden-eagle-427"}}'
```

**Check Connection**:
```bash
aws dynamodb get-item \
  --table-name Connections \
  --key '{"connectionId": {"S": "abc123"}}'
```

**Query Listeners**:
```bash
aws dynamodb query \
  --table-name Connections \
  --index-name sessionId-targetLanguage-index \
  --key-condition-expression 'sessionId = :sid' \
  --expression-attribute-values '{":sid": {"S": "golden-eagle-427"}}'
```

**Check Lambda Logs**:
```bash
aws logs tail /aws/lambda/audio-processor --follow
```

**Check Metrics**:
```bash
aws cloudwatch get-metric-statistics \
  --namespace WebSocketAudio \
  --metric-name AudioProcessingLatency \
  --start-time 2025-11-14T00:00:00Z \
  --end-time 2025-11-14T23:59:59Z \
  --period 300 \
  --statistics Average,Maximum
```

## References

- [Requirements Document](../../.kiro/specs/websocket-audio-integration/requirements.md)
- [Design Document](../../.kiro/specs/websocket-audio-integration/design.md)
- [Implementation Tasks](../../.kiro/specs/websocket-audio-integration/tasks.md)
- [Session Management README](../README.md)
- [Audio Transcription README](../../audio-transcription/README.md)
- [Translation Pipeline README](../../translation-pipeline/README.md)
