# Remaining Tasks Implementation Guide

## Overview

This guide provides detailed implementation instructions for the remaining 11 tasks in the WebSocket Audio Integration spec. It includes code analysis, implementation patterns, and specific guidance for each task.

**Last Updated**: November 14, 2025  
**Status**: Ready for Implementation  
**Completed Tasks**: 1/12 (Task 5: BroadcastState model)

## Existing Infrastructure Analysis

### Lambda Handlers Review

**session-management/lambda/connection_handler/handler.py**:
- **Size**: ~500 lines
- **Purpose**: Handles $connect events (createSession, joinSession)
- **Structure**: Main handler + 2 helper functions
- **Patterns**: Structured logging, metrics emission, comprehensive error handling
- **Dependencies**: SessionsRepository, ConnectionsRepository, RateLimitService
- **Key Features**: Rate limiting, language validation, atomic counter operations

**audio-transcription/lambda/audio_processor/handler.py**:
- **Size**: ~700 lines
- **Purpose**: Processes audio with partial results and quality validation
- **Structure**: Async/sync bridging, singleton pattern for processors
- **Patterns**: Fallback mode, health monitoring, graceful degradation
- **Dependencies**: PartialResultProcessor, AudioQualityAnalyzer
- **Key Features**: Audio quality validation, Transcribe integration, CloudWatch metrics

### Key Findings

1. **No WebSocket Message Parsing**: Current handlers expect Lambda events, not WebSocket events
2. **No Message Size Validation**: Not implemented in either handler
3. **No Control Message Routing**: Connection handler only handles $connect
4. **No Session Status Handler**: Needs to be created from scratch
5. **Comprehensive Error Handling**: Both handlers have excellent error handling patterns to follow


## Implementation Phases

### Phase 1: Validation & Utilities (Tasks 6-7)
**Estimated Effort**: 15,000-20,000 tokens  
**Priority**: High (foundational)  
**Dependencies**: None

### Phase 2: Core Lambda Extensions (Tasks 2-3)
**Estimated Effort**: 35,000-40,000 tokens  
**Priority**: Critical (core functionality)  
**Dependencies**: Phase 1 complete

### Phase 3: New Components & Infrastructure (Tasks 1, 4, 10)
**Estimated Effort**: 25,000-30,000 tokens  
**Priority**: High (enables deployment)  
**Dependencies**: Phase 2 complete

### Phase 4: Observability & Testing (Tasks 8-9, 11-12)
**Estimated Effort**: 25,000-30,000 tokens  
**Priority**: Medium (quality assurance)  
**Dependencies**: Phase 3 complete

## Task-by-Task Implementation Guide

### Task 6: Implement Message Size Validation

**Complexity**: Low  
**Estimated Effort**: 5,000-7,000 tokens  
**Files to Modify**: 
- `session-management/shared/utils/validators.py` (add validation functions)
- `session-management/lambda/connection_handler/handler.py` (add validation calls)
- `audio-transcription/lambda/audio_processor/handler.py` (add validation calls)

**Implementation Steps**:

1. Create validation utility in `shared/utils/validators.py`:
```python
def validate_message_size(message_body: str, max_size_bytes: int = 131072) -> None:
    """Validate WebSocket message size (default 128 KB)"""
    
def validate_audio_chunk_size(audio_data: bytes, max_size_bytes: int = 32768) -> None:
    """Validate audio chunk size (default 32 KB)"""
    
def validate_control_message_size(payload: dict, max_size_bytes: int = 4096) -> None:
    """Validate control message payload size (default 4 KB)"""
```

2. Add validation to connection_handler at entry point
3. Add validation to audio_processor for audio chunks
4. Add appropriate error responses (413 Payload Too Large)
5. Add CloudWatch metrics for size violations
6. Write unit tests for validation functions

**Testing**: 
- Test with messages at boundary (128 KB)
- Test with oversized messages (>128 KB)
- Test with various audio chunk sizes
- Verify error responses


### Task 7: Implement Connection Timeout Handling

**Complexity**: Low  
**Estimated Effort**: 8,000-10,000 tokens  
**Files to Create**:
- `session-management/lambda/timeout_handler/handler.py` (new Lambda)
- `session-management/lambda/timeout_handler/requirements.txt`

**Files to Modify**:
- `session-management/infrastructure/stacks/` (add EventBridge rule)

**Implementation Steps**:

1. Create timeout_handler Lambda:
```python
def lambda_handler(event, context):
    """Periodic check for idle connections (runs every 60 seconds)"""
    # 1. Query all connections
    # 2. Check lastActivityTime
    # 3. Close connections idle > 120 seconds
    # 4. Send connectionTimeout message before closing
    # 5. Trigger disconnect handler for cleanup
```

2. Add EventBridge scheduled rule (every 60 seconds)
3. Add IAM permissions for API Gateway Management API
4. Add CloudWatch metrics for timeouts
5. Write unit tests

**Testing**:
- Test with idle connections
- Test with active connections
- Verify disconnect handler is triggered
- Verify CloudWatch metrics

### Task 2: Extend audio_processor Lambda

**Complexity**: High  
**Estimated Effort**: 20,000-25,000 tokens  
**Files to Modify**:
- `audio-transcription/lambda/audio_processor/handler.py` (major extension)
- `audio-transcription/shared/services/transcribe_stream_handler.py` (minor updates)

**Implementation Steps**:

1. Add WebSocket event parsing:
```python
def parse_websocket_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Extract connectionId, audio data, and metadata from WebSocket event"""
    connection_id = event['requestContext']['connectionId']
    body = event.get('body', '')
    # Handle base64 or binary audio data
    # Return parsed data
```

2. Add connection/session validation:
```python
async def validate_connection_and_session(connection_id: str) -> Tuple[str, Dict]:
    """Query connection, verify role=speaker, get session"""
    # Query Connections table
    # Verify role=speaker
    # Get sessionId
    # Query Sessions table
    # Verify isActive=true
    # Return (session_id, session_record)
```

3. Add rate limiting for audio chunks:
```python
class AudioRateLimiter:
    """Sliding window rate limiter for audio chunks"""
    def __init__(self, max_chunks_per_second: int = 50):
        self.max_chunks = max_chunks_per_second
        self.window = deque()  # (timestamp, connection_id)
```

4. Integrate with existing TranscribeStreamHandler
5. Add audio format validation
6. Add error handling for all scenarios
7. Write comprehensive unit tests

**Testing**:
- Test WebSocket event parsing
- Test connection/session validation
- Test rate limiting
- Test Transcribe integration
- Test error scenarios


### Task 3: Extend connection_handler Lambda

**Complexity**: High  
**Estimated Effort**: 15,000-18,000 tokens  
**Files to Modify**:
- `session-management/lambda/connection_handler/handler.py` (add routing and handlers)

**Implementation Steps**:

1. Add action routing for control messages:
```python
def lambda_handler(event, context):
    # Existing: createSession, joinSession
    # Add: pauseBroadcast, resumeBroadcast, muteBroadcast, unmuteBroadcast
    # Add: setVolume, speakerStateChange
    # Add: pausePlayback, changeLanguage
```

2. Implement speaker control handlers:
```python
def handle_pause_broadcast(connection_id: str) -> Dict:
    """Pause broadcast, update session, notify listeners"""
    
def handle_resume_broadcast(connection_id: str) -> Dict:
    """Resume broadcast, update session, notify listeners"""
    
def handle_mute_broadcast(connection_id: str) -> Dict:
    """Mute broadcast, update session, notify listeners"""
    
def handle_set_volume(connection_id: str, volume_level: float) -> Dict:
    """Set volume, update session, notify listeners"""
```

3. Implement listener notification logic:
```python
async def notify_listeners(session_id: str, message: Dict) -> None:
    """Send message to all listeners in parallel"""
    # Query connections by sessionId
    # Use API Gateway Management API
    # Send in parallel with asyncio.gather
    # Log failures but continue
```

4. Implement listener control handlers:
```python
def handle_pause_playback(connection_id: str) -> Dict:
    """Acknowledge pause (client-side only)"""
    
def handle_change_language(connection_id: str, new_language: str) -> Dict:
    """Update connection targetLanguage"""
```

5. Add authorization validation for each action
6. Write comprehensive unit tests

**Testing**:
- Test each control action
- Test state updates
- Test listener notifications
- Test authorization
- Test concurrent state changes


### Task 4: Create session_status_handler Lambda

**Complexity**: Medium  
**Estimated Effort**: 10,000-12,000 tokens  
**Files to Create**:
- `session-management/lambda/session_status_handler/` (new directory)
- `session-management/lambda/session_status_handler/handler.py`
- `session-management/lambda/session_status_handler/requirements.txt`

**Implementation Steps**:

1. Create handler structure:
```python
def lambda_handler(event, context):
    """Handle getSessionStatus requests and periodic updates"""
    # Check if triggered by EventBridge or WebSocket
    # Route accordingly
```

2. Implement status query:
```python
async def get_session_status(connection_id: str) -> Dict:
    """Query session and aggregate listener stats"""
    # Get session from connection
    # Query all listener connections
    # Aggregate by targetLanguage
    # Calculate session duration
    # Return status object
```

3. Implement periodic updates:
```python
async def send_periodic_updates():
    """Send status to all active speakers (EventBridge trigger)"""
    # Query all active sessions
    # For each session, get speaker connection
    # Send status update
```

4. Add language distribution aggregation
5. Add CloudWatch metrics
6. Write unit tests

**Testing**:
- Test status query
- Test language aggregation
- Test periodic updates
- Test performance with 500 listeners

### Tasks 1 & 10: CDK Infrastructure Updates

**Complexity**: Medium  
**Estimated Effort**: 15,000-18,000 tokens  
**Files to Modify**:
- `session-management/infrastructure/stacks/session_management_stack.py`

**Implementation Steps**:

1. Add WebSocket routes:
```python
# Add 10 custom routes
sendAudio_route = apigatewayv2.CfnRoute(...)
pauseBroadcast_route = apigatewayv2.CfnRoute(...)
# ... etc
```

2. Add session_status_handler Lambda
3. Add timeout_handler Lambda
4. Update IAM roles with new permissions
5. Add EventBridge rules
6. Deploy and test

**Testing**:
- Deploy to dev environment
- Test each route
- Verify IAM permissions
- Verify EventBridge triggers


### Tasks 8-9: Monitoring and Logging

**Complexity**: Medium  
**Estimated Effort**: 12,000-15,000 tokens  
**Files to Modify**:
- All Lambda handlers (add metrics and logging)
- `session-management/shared/utils/metrics.py` (extend)
- `session-management/infrastructure/stacks/` (add alarms)

**Implementation Steps**:

1. Add CloudWatch metrics to all handlers
2. Add structured logging with correlation IDs
3. Configure CloudWatch alarms
4. Add X-Ray tracing (optional)
5. Write monitoring documentation

### Tasks 11-12: Testing and Documentation

**Complexity**: Medium  
**Estimated Effort**: 15,000-18,000 tokens  
**Files to Create**:
- Integration tests
- Load tests (optional)
- Documentation updates

**Implementation Steps**:

1. Write integration tests for end-to-end flows
2. Write load tests (optional)
3. Update component READMEs
4. Create integration guide
5. Update deployment documentation

## Implementation Patterns to Follow

### Error Handling Pattern

```python
try:
    # Operation
    result = perform_operation()
except ValidationError as e:
    logger.warning(f"Validation error: {e}")
    metrics_publisher.emit_error('VALIDATION_ERROR')
    return error_response(400, 'INVALID_PARAMETERS', str(e))
except RateLimitExceededError as e:
    logger.warning(f"Rate limit exceeded: {e}")
    metrics_publisher.emit_rate_limit_exceeded()
    return rate_limit_error_response(e.retry_after)
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    metrics_publisher.emit_error('INTERNAL_ERROR')
    return error_response(500, 'INTERNAL_ERROR', 'An unexpected error occurred')
```

### Logging Pattern

```python
logger.info(
    message="Operation completed",
    correlation_id=session_id,
    operation='operation_name',
    duration_ms=duration,
    key_metric=value
)
```

### Metrics Pattern

```python
metrics_publisher.emit_metric(
    metric_name='OperationLatency',
    value=duration_ms,
    unit='Milliseconds',
    dimensions={'Operation': 'operation_name'}
)
```

## Next Steps

1. **Start with Phase 1** (Tasks 6-7): Simple validation utilities
2. **Move to Phase 2** (Tasks 2-3): Core Lambda extensions
3. **Complete Phase 3** (Tasks 1, 4, 10): Infrastructure and new components
4. **Finish with Phase 4** (Tasks 8-9, 11-12): Observability and testing

Each phase should be completed in a separate session to manage token budget effectively.

