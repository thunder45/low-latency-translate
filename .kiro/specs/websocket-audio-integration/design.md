# WebSocket Audio Integration Design

## Overview

This design document describes the architecture and implementation approach for integrating WebSocket audio reception with AWS Transcribe Streaming API. The system bridges the gap between speaker audio input and real-time transcription processing, enabling the complete audio-to-translation pipeline.

**IMPORTANT**: This design leverages extensive existing infrastructure. The system is 85-90% complete with sophisticated partial results processing, audio quality validation, and translation pipeline already implemented. This design focuses on the remaining integration gaps.

The design addresses four critical missing components:
1. Audio reception via WebSocket (`sendAudio` route and handler)
2. Real-time Transcribe streaming integration with event loop management
3. Speaker control message handlers (pause, mute, volume, state changes)
4. Session status queries for real-time listener statistics

## Existing Infrastructure (To Be Leveraged)

### Already Implemented Components

**Audio Processing (80% complete)**:
- `audio-transcription/lambda/audio_processor/handler.py` - Comprehensive audio processor
- `audio-transcription/shared/services/partial_result_processor.py` - Sophisticated partial results coordinator
- `audio-transcription/shared/services/transcribe_stream_handler.py` - Event processor for Transcribe
- `audio-transcription/shared/services/transcribe_client.py` - Client lifecycle management

**Translation Pipeline (100% complete)**:
- `translation-pipeline/lambda/translation_processor/handler.py` - Complete translation orchestration
- `translation-pipeline/shared/services/translation_pipeline_orchestrator.py` - Full pipeline logic

**Session Management (100% complete)**:
- `session-management/lambda/connection_handler/` - WebSocket connection management
- `session-management/lambda/disconnect_handler/` - Cleanup logic
- `session-management/shared/data_access/` - DynamoDB repositories

### Implementation Strategy: Extend Existing

Rather than creating 4 new Lambda handlers, we will:
1. **Extend `audio_processor`** to handle WebSocket `sendAudio` messages
2. **Extend `connection_handler`** to handle speaker control messages
3. **Create new `session_status_handler`** for status queries (minimal new code)
4. **Add 10 new WebSocket routes** to existing API Gateway configuration

## Architecture

### High-Level Architecture

```
┌─────────────┐
│   Speaker   │
│  (Browser)  │
└──────┬──────┘
       │ WSS (audio chunks + controls)
       ▼
┌─────────────────────────────────────┐
│   API Gateway WebSocket API         │
│  - sendAudio route                  │
│  - pauseBroadcast route             │
│  - getSessionStatus route           │
│  - (other control routes)           │
└──────┬──────────────────────────────┘
       │
       ├─────────────────┬──────────────────┬────────────────┐
       ▼                 ▼                  ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Audio        │  │ Speaker      │  │ Session      │  │ Listener     │
│ Processor    │  │ Control      │  │ Status       │  │ Control      │
│ Lambda       │  │ Lambda       │  │ Lambda       │  │ Lambda       │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────────────┘
       │                 │                  │
       │                 ▼                  ▼
       │          ┌──────────────────────────────┐
       │          │      DynamoDB Tables         │
       │          │  - Sessions                  │
       │          │  - Connections               │
       │          └──────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  Transcribe Stream Handler           │
│  - Initialize Transcribe stream      │
│  - Manage event loop                 │
│  - Forward audio chunks              │
│  - Process transcription events      │
└──────┬───────────────────────────────┘
       │
       ├─────────────────┬
       ▼                 ▼
┌──────────────┐  ┌──────────────────────┐
│ AWS Transcribe│  │ Translation Pipeline │
│ Streaming API │  │ Lambda               │
└───────────────┘  └──────────────────────┘
```

### Component Responsibilities (REVISED - Extend Existing)

**IMPORTANT**: The original design proposed 4 new Lambda handlers. After discovering extensive existing infrastructure, we will instead:
- **Extend 2 existing handlers** (audio_processor, connection_handler)
- **Create 1 new minimal handler** (session_status_handler)
- **Leverage existing services** (TranscribeStreamHandler, PartialResultProcessor, TranslationPipelineOrchestrator)

**Extended Audio Processor Lambda** (`audio-transcription/lambda/audio_processor/`)
- **NEW**: Receives audio chunks from WebSocket `sendAudio` route
- **NEW**: Validates connection and session state from WebSocket context
- **EXISTING**: Initializes and manages Transcribe streams (already implemented)
- **EXISTING**: Forwards audio to Transcribe (already implemented)
- Processes transcription events asynchronously
- Applies rate limiting and size validation

**Speaker Control Lambda**
- Handles pause/resume/mute/unmute/volume controls
- Updates session broadcast state in DynamoDB
- Notifies all listeners of state changes
- Validates speaker authorization

**Session Status Lambda**
- Queries session and connection data
- Aggregates listener statistics by language
- Returns real-time session metrics
- Sends periodic status updates

**Listener Control Lambda**
- Handles listener-specific controls (pause playback, change language)
- Updates connection records
- Does not affect speaker broadcast state

**Transcribe Stream Handler** (within Audio Processor)
- Manages AWS Transcribe Streaming API connections
- Runs asynchronous event loop for transcription events
- Handles stream lifecycle (init, reconnect, close)
- Forwards results to Translation Pipeline

## Components and Interfaces

### 1. Audio Processor Lambda

**Purpose**: Receive and process audio chunks from speakers

**Handler**: `lambda/audio_processor/handler.py`

**Configuration**:
- Memory: 1024 MB (for audio buffering and Transcribe SDK)
- Timeout: 60 seconds
- Concurrency: Reserved capacity of 10 per region

**Key Classes**:

```python
class AudioProcessor:
    """Main processor for audio chunks"""
    
    def __init__(self, transcribe_handler, session_repo, connection_repo):
        self.transcribe_handler = transcribe_handler
        self.session_repo = session_repo
        self.connection_repo = connection_repo
        self.rate_limiter = RateLimiter()
        
    async def process_audio_chunk(
        self, 
        connection_id: str, 
        audio_data: bytes
    ) -> Dict[str, Any]:
        """Process incoming audio chunk"""
        # 1. Validate connection and session
        # 2. Apply rate limiting
        # 3. Validate audio format
        # 4. Forward to Transcribe stream
        # 5. Return acknowledgment
```


```python
class TranscribeStreamHandler:
    """Manages AWS Transcribe Streaming API connections"""
    
    def __init__(self, session_id: str, source_language: str):
        self.session_id = session_id
        self.source_language = source_language
        self.stream = None
        self.event_loop_task = None
        self.audio_buffer = AudioBuffer(max_size_seconds=5)
        
    async def initialize_stream(self) -> bool:
        """Initialize Transcribe streaming connection"""
        
    async def send_audio_chunk(self, audio_data: bytes) -> None:
        """Send audio chunk to Transcribe stream"""
        
    async def process_events(self) -> None:
        """Event loop for processing Transcribe events"""
        
    async def close_stream(self) -> None:
        """Gracefully close Transcribe stream"""
```

**Message Flow**:

1. Speaker sends `sendAudio` message with binary audio data
2. API Gateway routes to Audio Processor Lambda
3. Lambda validates connection (role=speaker) and session (isActive=true)
4. Lambda forwards audio to Transcribe Stream Handler
5. Handler sends audio to AWS Transcribe Streaming API
6. Handler processes transcription events asynchronously
7. Handler forwards transcription to Translation Pipeline

**Error Handling**:
- Invalid connection: Return 403 Forbidden
- Invalid session: Return 404 Not Found
- Rate limit exceeded: Drop chunks, emit metric, warn speaker
- Transcribe error: Retry with backoff, notify speaker if persistent
- Audio format invalid: Return 400 Bad Request with details


### 2. Speaker Control Lambda

**Purpose**: Handle speaker broadcast control messages

**Handler**: `lambda/speaker_control/handler.py`

**Configuration**:
- Memory: 512 MB
- Timeout: 10 seconds
- Concurrency: Default (auto-scaling)

**Supported Actions**:
- `pauseBroadcast`: Pause audio broadcasting
- `resumeBroadcast`: Resume audio broadcasting
- `muteBroadcast`: Mute microphone
- `unmuteBroadcast`: Unmute microphone
- `setVolume`: Set broadcast volume (0.0-1.0)
- `speakerStateChange`: Update multiple state fields

**Key Classes**:

```python
class SpeakerControlHandler:
    """Handles speaker control messages"""
    
    def __init__(self, session_repo, connection_repo, api_gateway_client):
        self.session_repo = session_repo
        self.connection_repo = connection_repo
        self.api_gateway = api_gateway_client
        
    async def handle_pause(self, connection_id: str) -> Dict[str, Any]:
        """Handle pause broadcast request"""
        
    async def handle_resume(self, connection_id: str) -> Dict[str, Any]:
        """Handle resume broadcast request"""
        
    async def handle_mute(self, connection_id: str) -> Dict[str, Any]:
        """Handle mute broadcast request"""
        
    async def handle_volume(
        self, 
        connection_id: str, 
        volume_level: float
    ) -> Dict[str, Any]:
        """Handle volume change request"""
        
    async def notify_listeners(
        self, 
        session_id: str, 
        message: Dict[str, Any]
    ) -> None:
        """Send message to all listeners in session"""
```


**Message Flow**:

1. Speaker sends control message (e.g., `pauseBroadcast`)
2. API Gateway routes to Speaker Control Lambda
3. Lambda validates connection (role=speaker)
4. Lambda updates session broadcast state in DynamoDB
5. Lambda queries all listener connections for session
6. Lambda sends state change notification to each listener
7. Lambda returns acknowledgment to speaker

**State Management**:

Session record in DynamoDB includes:
```python
{
    'sessionId': 'golden-eagle-427',
    'broadcastState': {
        'isActive': True,
        'isPaused': False,
        'isMuted': False,
        'volume': 1.0,
        'lastStateChange': 1699500000
    }
}
```

**Error Handling**:
- Unauthorized (not speaker): Return 403 Forbidden
- Invalid volume (not 0.0-1.0): Return 400 Bad Request
- Session not found: Return 404 Not Found
- DynamoDB error: Retry with backoff, return 500 if persistent
- Listener notification failure: Log error, continue with other listeners


### 3. Session Status Lambda

**Purpose**: Provide real-time session statistics to speakers

**Handler**: `lambda/session_status/handler.py`

**Configuration**:
- Memory: 256 MB
- Timeout: 5 seconds
- Concurrency: Default (auto-scaling)

**Key Classes**:

```python
class SessionStatusHandler:
    """Handles session status queries"""
    
    def __init__(self, session_repo, connection_repo):
        self.session_repo = session_repo
        self.connection_repo = connection_repo
        
    async def get_session_status(
        self, 
        connection_id: str
    ) -> Dict[str, Any]:
        """Get current session status"""
        # 1. Get session from connection
        # 2. Query all listener connections
        # 3. Aggregate by target language
        # 4. Calculate session duration
        # 5. Return status object
        
    def aggregate_language_distribution(
        self, 
        connections: List[Dict]
    ) -> Dict[str, int]:
        """Aggregate listener count by language"""
```

**Response Format**:

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
    "volume": 1.0
  },
  "timestamp": 1699500000,
  "updateReason": "requested"
}
```


**Periodic Updates**:

The system sends automatic status updates:
- Every 30 seconds (periodic)
- When listener count changes by >10% (listenerCountChange)
- When new language appears (newLanguage)

Implementation uses EventBridge scheduled rule to trigger Lambda every 30 seconds, which queries active sessions and sends updates.

**Error Handling**:
- Unauthorized (not speaker): Return 403 Forbidden
- Session not found: Return 404 Not Found
- DynamoDB query timeout: Return cached status if available, else 503
- Query latency >500ms: Emit CloudWatch alarm

### 4. Listener Control Lambda

**Purpose**: Handle listener-specific control messages

**Handler**: `lambda/listener_control/handler.py`

**Configuration**:
- Memory: 256 MB
- Timeout: 5 seconds
- Concurrency: Default (auto-scaling)

**Supported Actions**:
- `pausePlayback`: Pause audio playback (client-side only)
- `changeLanguage`: Switch target language

**Key Classes**:

```python
class ListenerControlHandler:
    """Handles listener control messages"""
    
    def __init__(self, connection_repo):
        self.connection_repo = connection_repo
        
    async def handle_pause_playback(
        self, 
        connection_id: str
    ) -> Dict[str, Any]:
        """Acknowledge pause playback (client-side)"""
        
    async def handle_change_language(
        self, 
        connection_id: str, 
        new_language: str
    ) -> Dict[str, Any]:
        """Update listener target language"""
```


**Message Flow for Language Change**:

1. Listener sends `changeLanguage` with `targetLanguage`
2. API Gateway routes to Listener Control Lambda
3. Lambda validates connection (role=listener)
4. Lambda validates new language is supported
5. Lambda updates connection record in DynamoDB
6. Lambda returns acknowledgment with new language
7. Translation Pipeline picks up new language on next transcription

**Error Handling**:
- Unauthorized (not listener): Return 403 Forbidden
- Unsupported language: Return 400 Bad Request with supported languages list
- Connection not found: Return 404 Not Found
- DynamoDB error: Retry with backoff, return 500 if persistent

## Data Models

### Session Record (DynamoDB)

```python
@dataclass
class Session:
    sessionId: str  # PK: golden-eagle-427
    speakerConnectionId: str
    speakerUserId: str
    sourceLanguage: str  # ISO 639-1
    createdAt: int  # Unix timestamp
    expiresAt: int  # Unix timestamp (TTL)
    isActive: bool
    listenerCount: int
    qualityTier: str  # standard | premium
    broadcastState: BroadcastState
    
@dataclass
class BroadcastState:
    isActive: bool
    isPaused: bool
    isMuted: bool
    volume: float  # 0.0-1.0
    lastStateChange: int  # Unix timestamp
```

### Connection Record (DynamoDB)

```python
@dataclass
class Connection:
    connectionId: str  # PK: API Gateway connection ID
    sessionId: str  # GSI PK
    targetLanguage: str  # GSI SK (for listeners)
    role: str  # speaker | listener
    connectedAt: int  # Unix timestamp
    ttl: int  # Unix timestamp (TTL)
    userId: Optional[str]  # For speakers only
```


### Transcribe Stream State (In-Memory)

```python
@dataclass
class TranscribeStreamState:
    session_id: str
    source_language: str
    stream: Optional[TranscribeStreamingClient]
    event_loop_task: Optional[asyncio.Task]
    audio_buffer: AudioBuffer
    last_audio_timestamp: int
    is_active: bool
    retry_count: int
    
class AudioBuffer:
    """Circular buffer for audio chunks"""
    def __init__(self, max_size_seconds: int = 5):
        self.max_size_bytes = max_size_seconds * 16000 * 2  # 16kHz, 16-bit
        self.buffer = bytearray()
        
    def add_chunk(self, chunk: bytes) -> bool:
        """Add chunk, return False if buffer full"""
        
    def get_chunks(self, max_bytes: int) -> bytes:
        """Get and remove chunks from buffer"""
        
    def clear(self) -> None:
        """Clear buffer"""
```

## Error Handling

### Error Categories

**Client Errors (4xx)**:
- 400 Bad Request: Invalid parameters, unsupported language, invalid audio format
- 403 Forbidden: Unauthorized action (wrong role)
- 404 Not Found: Session or connection not found
- 413 Payload Too Large: Message or audio chunk exceeds size limit
- 429 Too Many Requests: Rate limit exceeded

**Server Errors (5xx)**:
- 500 Internal Server Error: Unexpected error, DynamoDB failure after retries
- 503 Service Unavailable: Transcribe unavailable, Translation Pipeline unavailable
- 504 Gateway Timeout: Lambda timeout, DynamoDB query timeout

### Retry Strategy

**Transient Errors** (retry with exponential backoff):
- DynamoDB throttling
- Transcribe throttling
- Network timeouts
- Temporary service unavailability

**Retry Configuration**:
```python
RETRY_CONFIG = {
    'max_attempts': 3,
    'base_delay_ms': 100,
    'max_delay_ms': 2000,
    'exponential_base': 2
}
```


**Permanent Errors** (no retry, return error to client):
- Invalid authentication
- Unsupported language
- Invalid audio format
- Unauthorized action
- Resource not found

### Circuit Breaker Pattern

For Transcribe stream connections:

```python
class CircuitBreaker:
    """Circuit breaker for Transcribe connections"""
    
    def __init__(
        self, 
        failure_threshold: int = 5,
        timeout_seconds: int = 60
    ):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.state = 'CLOSED'  # CLOSED | OPEN | HALF_OPEN
        self.last_failure_time = 0
        
    def record_success(self) -> None:
        """Record successful operation"""
        
    def record_failure(self) -> None:
        """Record failed operation"""
        
    def can_attempt(self) -> bool:
        """Check if operation can be attempted"""
```

States:
- **CLOSED**: Normal operation, all requests allowed
- **OPEN**: Too many failures, block requests for timeout period
- **HALF_OPEN**: Timeout expired, allow one test request

## Testing Strategy

### Unit Tests

**Audio Processor**:
- Test audio chunk validation (size, format)
- Test rate limiting logic
- Test Transcribe stream initialization
- Test error handling for invalid connections
- Test audio buffer overflow handling

**Speaker Control**:
- Test each control action (pause, resume, mute, volume)
- Test state updates in DynamoDB
- Test listener notification logic
- Test authorization validation
- Test concurrent state changes


**Session Status**:
- Test status query with various listener counts
- Test language distribution aggregation
- Test periodic update logic
- Test performance with 500 listeners
- Test error handling for missing sessions

**Transcribe Stream Handler**:
- Test stream initialization with various languages
- Test event loop processing
- Test reconnection logic after failures
- Test graceful shutdown
- Test audio buffer management

### Integration Tests

**End-to-End Audio Flow**:
1. Speaker connects and creates session
2. Speaker sends audio chunks
3. Verify Transcribe stream initialized
4. Verify transcription events processed
5. Verify results forwarded to Translation Pipeline
6. Verify no audio loss or duplication

**Control Flow**:
1. Speaker pauses broadcast
2. Verify session state updated
3. Verify listeners notified
4. Verify audio processing stopped
5. Speaker resumes
6. Verify audio processing resumed

**Session Status Flow**:
1. Multiple listeners join with different languages
2. Speaker queries status
3. Verify correct listener count
4. Verify correct language distribution
5. Verify response latency <500ms

### Load Tests

**Audio Processing**:
- 100 concurrent speakers sending audio
- 50 chunks/second per speaker
- Verify p95 latency <50ms
- Verify no dropped chunks
- Verify Transcribe stream stability

**Control Messages**:
- 100 speakers sending control messages
- 10 messages/second per speaker
- Verify p95 latency <100ms
- Verify all listeners notified
- Verify no state corruption


## Performance Considerations

### Latency Optimization

**Audio Processing Path**:
- WebSocket → Lambda: <10ms (API Gateway overhead)
- Lambda validation: <5ms (DynamoDB query with DAX cache)
- Audio → Transcribe: <20ms (SDK overhead)
- **Total target: <50ms p95**

**Optimization Techniques**:
1. Use DynamoDB DAX for connection/session lookups
2. Keep Transcribe streams warm (don't close immediately)
3. Use async I/O for all network operations
4. Minimize Lambda cold starts with provisioned concurrency
5. Batch listener notifications (send in parallel)

### Memory Management

**Audio Processor Lambda**:
- Base memory: 200 MB (Lambda runtime + SDK)
- Audio buffer: 160 KB (5 seconds at 16kHz 16-bit)
- Transcribe SDK: 100 MB
- **Total: 1024 MB allocated**

**Memory Optimization**:
- Use circular buffer to avoid memory growth
- Clear buffer on stream close
- Limit concurrent streams per Lambda instance
- Monitor memory usage with CloudWatch

### Concurrency Management

**Audio Processor**:
- Reserved concurrency: 10 per region
- Max concurrent streams: 10 (one per Lambda instance)
- Prevents runaway costs from audio spam
- Ensures predictable performance

**Other Lambdas**:
- Use default auto-scaling
- Monitor throttling metrics
- Increase reserved concurrency if needed


## Security

### Authentication and Authorization

**Speaker Actions** (require role=speaker):
- sendAudio
- pauseBroadcast, resumeBroadcast
- muteBroadcast, unmuteBroadcast
- setVolume
- speakerStateChange
- getSessionStatus

**Listener Actions** (require role=listener):
- pausePlayback (client-side only)
- changeLanguage

**Validation Flow**:
1. Extract connectionId from WebSocket event
2. Query Connections table for connection record
3. Verify role matches required role for action
4. If mismatch, return 403 Forbidden
5. If match, proceed with action

### Data Protection

**In Transit**:
- All WebSocket connections use WSS (TLS 1.2+)
- Audio data encrypted in transit
- No plaintext audio transmission

**At Rest**:
- Audio chunks not persisted (processed in memory only)
- Session/connection records in DynamoDB (no sensitive data)
- Transcription results not stored (forwarded immediately)

**Logging**:
- Never log audio data
- Never log full connection IDs (hash with SHA-256)
- Never log user identifiers
- Log only sanitized metadata

### Rate Limiting

**Audio Chunks**:
- 50 chunks/second per speaker (default)
- Sliding window of 1 second
- Drop excess chunks, emit metric
- Warn speaker after 5 seconds of violations
- Close connection after 30 seconds of violations

**Control Messages**:
- 10 messages/second per connection
- Sliding window of 1 second
- Return 429 Too Many Requests if exceeded

**Session Status Queries**:
- 2 queries/second per speaker
- Sliding window of 1 second
- Return 429 Too Many Requests if exceeded


## Monitoring and Observability

### CloudWatch Metrics

**Audio Processing**:
- `AudioChunksReceived` (Count, per session)
- `AudioProcessingLatency` (Milliseconds, p50/p95/p99)
- `AudioChunksDropped` (Count, per session)
- `AudioBufferOverflows` (Count, per session)
- `TranscribeStreamInitLatency` (Milliseconds, p50/p95/p99)
- `TranscribeStreamErrors` (Count, by error type)

**Control Messages**:
- `ControlMessagesReceived` (Count, by action type)
- `ControlMessageLatency` (Milliseconds, p50/p95/p99)
- `ListenerNotificationLatency` (Milliseconds, p50/p95/p99)
- `ListenerNotificationFailures` (Count, per session)

**Session Status**:
- `StatusQueriesReceived` (Count, per session)
- `StatusQueryLatency` (Milliseconds, p50/p95/p99)
- `PeriodicStatusUpdatesSent` (Count)

**Rate Limiting**:
- `RateLimitViolations` (Count, by message type)
- `ConnectionsClosedForRateLimit` (Count)

**Errors**:
- `LambdaErrors` (Count, by handler and error type)
- `DynamoDBErrors` (Count, by operation)
- `TranscribeErrors` (Count, by error code)

### CloudWatch Logs

**Log Groups**:
- `/aws/lambda/audio-processor`
- `/aws/lambda/speaker-control`
- `/aws/lambda/session-status`
- `/aws/lambda/listener-control`

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


**Log Levels**:
- DEBUG: Audio chunks received, transcription events, state changes
- INFO: Session operations, control actions, status queries
- WARN: Rate limit violations, retry attempts, degraded performance
- ERROR: Failures, exceptions, unrecoverable errors

### CloudWatch Alarms

**Critical Alarms** (page on-call):
- Audio processing latency p95 >100ms for 5 minutes
- Transcribe stream error rate >5% for 5 minutes
- Lambda error rate >1% for 5 minutes
- DynamoDB throttling >10 requests/minute

**Warning Alarms** (email):
- Audio processing latency p95 >75ms for 10 minutes
- Control message latency p95 >150ms for 10 minutes
- Rate limit violations >100/minute
- Audio buffer overflows >10/minute

### X-Ray Tracing

Enable X-Ray for:
- Audio Processor Lambda (trace audio → Transcribe → Translation)
- Speaker Control Lambda (trace control → DynamoDB → listeners)
- Session Status Lambda (trace query → aggregation → response)

Trace segments:
- WebSocket message receipt
- DynamoDB operations
- Transcribe API calls
- Translation Pipeline invocations
- Listener notifications

## Deployment Strategy

### Infrastructure as Code

**CDK Stack**: `WebSocketAudioIntegrationStack`

Resources:
- 4 Lambda functions (audio processor, speaker control, session status, listener control)
- 10 API Gateway WebSocket routes
- IAM roles and policies
- CloudWatch log groups
- CloudWatch alarms
- EventBridge rule for periodic status updates


### Deployment Phases

**Phase 1: Infrastructure**
1. Deploy Lambda functions (code stubs)
2. Deploy API Gateway routes
3. Configure IAM permissions
4. Deploy CloudWatch resources

**Phase 2: Audio Processing**
1. Implement Audio Processor Lambda
2. Implement Transcribe Stream Handler
3. Deploy and test with single speaker
4. Verify transcription forwarding

**Phase 3: Control Messages**
1. Implement Speaker Control Lambda
2. Implement Listener Control Lambda
3. Deploy and test control flows
4. Verify listener notifications

**Phase 4: Session Status**
1. Implement Session Status Lambda
2. Configure periodic updates
3. Deploy and test status queries
4. Verify performance

**Phase 5: Integration Testing**
1. End-to-end testing with multiple speakers
2. Load testing with 100 concurrent sessions
3. Failure scenario testing
4. Performance validation

**Phase 6: Production Rollout**
1. Deploy to staging environment
2. Run smoke tests
3. Monitor for 24 hours
4. Deploy to production with canary (10% traffic)
5. Monitor for 48 hours
6. Increase to 100% traffic

### Rollback Plan

**Immediate Rollback** (if critical issues):
1. Revert API Gateway route configurations
2. Route traffic to previous Lambda versions
3. Monitor for stability
4. Investigate issues in staging

**Partial Rollback** (if specific feature issues):
1. Disable problematic routes
2. Keep working routes active
3. Fix issues in staging
4. Redeploy fixed version


## Configuration

### Environment Variables

**Audio Processor Lambda**:
```python
SESSIONS_TABLE_NAME = 'Sessions'
CONNECTIONS_TABLE_NAME = 'Connections'
TRANSLATION_PIPELINE_FUNCTION_NAME = 'TranslationProcessor'
MAX_AUDIO_CHUNK_SIZE_BYTES = 32768  # 32 KB
RATE_LIMIT_AUDIO_CHUNKS_PER_SECOND = 50
AUDIO_BUFFER_MAX_SIZE_SECONDS = 5
TRANSCRIBE_STREAM_IDLE_TIMEOUT_SECONDS = 60
MAX_CONCURRENT_STREAMS_PER_SPEAKER = 1
```

**Speaker Control Lambda**:
```python
SESSIONS_TABLE_NAME = 'Sessions'
CONNECTIONS_TABLE_NAME = 'Connections'
API_GATEWAY_ENDPOINT = 'wss://abc123.execute-api.us-east-1.amazonaws.com/prod'
RATE_LIMIT_CONTROL_MESSAGES_PER_SECOND = 10
```

**Session Status Lambda**:
```python
SESSIONS_TABLE_NAME = 'Sessions'
CONNECTIONS_TABLE_NAME = 'Connections'
STATUS_QUERY_TIMEOUT_MS = 500
PERIODIC_UPDATE_INTERVAL_SECONDS = 30
LISTENER_COUNT_CHANGE_THRESHOLD_PERCENT = 10
```

**Listener Control Lambda**:
```python
CONNECTIONS_TABLE_NAME = 'Connections'
SUPPORTED_LANGUAGES = ['en', 'es', 'fr', 'de', 'pt', 'it', 'ja', 'ko', 'zh']
```

### Feature Flags

```python
ENABLE_PARTIAL_RESULTS = True  # Enable partial transcription results
ENABLE_PERIODIC_STATUS_UPDATES = True  # Enable automatic status updates
ENABLE_AUDIO_RATE_LIMITING = True  # Enable audio chunk rate limiting
ENABLE_CIRCUIT_BREAKER = True  # Enable circuit breaker for Transcribe
ENABLE_XRAY_TRACING = False  # Enable X-Ray tracing (dev/staging only)
```

## Dependencies

### Python Packages

**Audio Processor**:
```
boto3>=1.28.0
botocore>=1.31.0
amazon-transcribe>=0.6.0
asyncio>=3.4.3
```

**All Lambdas**:
```
boto3>=1.28.0
botocore>=1.31.0
```

### AWS Services

- AWS Lambda
- Amazon API Gateway (WebSocket API)
- Amazon DynamoDB
- AWS Transcribe Streaming API
- Amazon CloudWatch (Logs, Metrics, Alarms)
- AWS X-Ray (optional)
- Amazon EventBridge (for periodic updates)


## Migration and Compatibility

### Backward Compatibility

**Existing Components**:
- Session Management: No changes required (uses existing tables)
- Connection Handler: No changes required (continues to work)
- Disconnect Handler: No changes required (cleanup logic unchanged)
- Frontend: Requires updates to send audio and control messages

**API Compatibility**:
- All existing WebSocket routes remain functional
- New routes are additive (no breaking changes)
- Existing message formats unchanged

### Migration Steps

1. **Deploy Infrastructure**: Add new Lambda functions and routes
2. **Update Frontend**: Add audio sending and control logic
3. **Enable Routes**: Activate new routes in API Gateway
4. **Monitor**: Watch metrics for errors or performance issues
5. **Rollback if Needed**: Disable routes, revert frontend

### Frontend Changes Required

**Audio Sending**:
```typescript
// Capture audio from microphone
const audioContext = new AudioContext();
const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

// Send audio chunks via WebSocket
function sendAudioChunk(chunk: ArrayBuffer) {
  websocket.send(JSON.stringify({
    action: 'sendAudio',
    data: arrayBufferToBase64(chunk)
  }));
}
```

**Control Messages**:
```typescript
// Pause broadcast
function pauseBroadcast() {
  websocket.send(JSON.stringify({
    action: 'pauseBroadcast'
  }));
}

// Set volume
function setVolume(level: number) {
  websocket.send(JSON.stringify({
    action: 'setVolume',
    volumeLevel: level
  }));
}
```

**Session Status**:
```typescript
// Query status
function getSessionStatus() {
  websocket.send(JSON.stringify({
    action: 'getSessionStatus'
  }));
}

// Handle status updates
websocket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.type === 'sessionStatus') {
    updateUI(message);
  }
};
```


## Open Questions and Decisions

### Resolved Decisions

**Q: Should audio chunks be base64 encoded or sent as binary?**
A: Send as binary WebSocket frames for efficiency. API Gateway supports binary frames up to 128 KB.

**Q: Should Transcribe streams be pooled or created per session?**
A: Create per session. Pooling adds complexity and Transcribe doesn't charge for idle streams.

**Q: Should periodic status updates use polling or push?**
A: Use push with EventBridge scheduled rule. More efficient than client polling.

**Q: Should we support multiple concurrent Transcribe streams per speaker?**
A: No, limit to 1 stream per speaker to control costs and complexity.

**Q: Should listener notifications be sent synchronously or asynchronously?**
A: Send asynchronously in parallel to minimize latency for speaker.

### Open Questions

**Q: Should we implement audio chunk compression?**
Options:
1. No compression (current design) - Simple, low latency
2. Opus compression - Better bandwidth, adds latency
3. Let client decide - Flexible but complex

Recommendation: Start without compression, add if bandwidth becomes issue.

**Q: Should we cache Transcribe stream connections between sessions?**
Options:
1. No caching (current design) - Simple, clean lifecycle
2. Cache for 5 minutes - Faster reconnection, more complex
3. Pool of warm streams - Fastest, most complex

Recommendation: Start without caching, add if cold start latency is issue.

**Q: Should we support audio format conversion in Lambda?**
Options:
1. No conversion (current design) - Client must send PCM 16kHz
2. Support multiple formats - More flexible, adds processing overhead
3. Use MediaConvert - Offload conversion, adds cost

Recommendation: Require PCM 16kHz from client. Add conversion later if needed.


## Future Enhancements

### Phase 2 Features

**Audio Quality Monitoring**:
- Integrate with audio-quality module
- Send quality warnings to speaker
- Automatically adjust processing based on quality

**Advanced Controls**:
- Speed control (0.5x - 2.0x playback speed)
- Pitch adjustment
- Background noise suppression
- Echo cancellation

**Enhanced Status**:
- Per-listener connection quality
- Transcription accuracy metrics
- Translation cache hit rates
- Real-time latency measurements

### Phase 3 Features

**Multi-Speaker Support**:
- Multiple speakers in same session
- Speaker switching/handoff
- Concurrent speaker audio mixing

**Recording and Playback**:
- Record sessions to S3
- Playback recorded sessions
- Download transcripts

**Advanced Analytics**:
- Session engagement metrics
- Listener retention analysis
- Language preference trends
- Performance dashboards

## Summary

This design provides a comprehensive solution for integrating WebSocket audio reception with AWS Transcribe Streaming API. The architecture is:

- **Scalable**: Handles 100+ concurrent sessions with 500 listeners each
- **Performant**: Achieves <50ms audio processing latency
- **Resilient**: Includes retry logic, circuit breakers, and graceful degradation
- **Observable**: Comprehensive metrics, logs, and alarms
- **Secure**: Proper authentication, authorization, and data protection
- **Maintainable**: Clear separation of concerns, well-defined interfaces

The implementation follows AWS best practices and integrates seamlessly with existing session management and transcription components.
