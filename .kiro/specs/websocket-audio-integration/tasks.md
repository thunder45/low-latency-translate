# Implementation Plan

## Overview

This implementation plan converts the WebSocket Audio Integration design into actionable coding tasks. The plan leverages extensive existing infrastructure (85-90% complete) and focuses on integration rather than building from scratch.

**Key Strategy**: Extend existing handlers rather than creating new ones.

## Task List

- [x] 1. Configure WebSocket API routes and integrate with existing handlers
  - Add 10 new custom routes to existing API Gateway WebSocket API
  - Configure route selection expressions
  - Map routes to existing and new Lambda handlers
  - Update IAM permissions for new routes
  - _Requirements: 19, 20_

- [x] 1.1 Add sendAudio route configuration
  - Configure `sendAudio` custom route in API Gateway
  - Map to extended audio_processor Lambda
  - Set integration timeout to 60 seconds
  - Configure binary WebSocket frame support (not JSON messages)
  - Set content handling to CONVERT_TO_BINARY for audio chunks
  - _Requirements: 1, 19_

- [x] 1.2 Add speaker control routes
  - Configure `pauseBroadcast`, `resumeBroadcast`, `muteBroadcast`, `unmuteBroadcast` routes
  - Configure `setVolume` and `speakerStateChange` routes
  - Map to extended connection_handler Lambda
  - Set integration timeout to 10 seconds
  - _Requirements: 6-10, 19_

- [x] 1.3 Add session status route
  - Configure `getSessionStatus` custom route
  - Map to new session_status_handler Lambda
  - Set integration timeout to 5 seconds
  - _Requirements: 11, 19_

- [x] 1.4 Add listener control routes
  - Configure `pausePlayback` and `changeLanguage` routes
  - Map to extended connection_handler Lambda
  - Set integration timeout to 5 seconds
  - _Requirements: 18, 19_


- [x] 2. Extend audio_processor Lambda to handle WebSocket audio messages
  - Modify existing `audio-transcription/lambda/audio_processor/handler.py`
  - Add WebSocket event parsing and validation
  - Extract audio data from WebSocket message
  - Integrate with existing TranscribeStreamHandler
  - Add rate limiting for audio chunks
  - _Requirements: 1-5, 13, 26_

- [x] 2.1 Add WebSocket message parsing
  - Parse WebSocket event structure from API Gateway
  - Extract connectionId from event context
  - Extract audio data from message body (base64 or binary)
  - Validate message format and required fields
  - _Requirements: 1, 27_

- [x] 2.2 Add connection and session validation
  - Query Connections table using connectionId
  - Verify role=speaker
  - Extract sessionId from connection record
  - Query Sessions table to verify isActive=true
  - Return 403 if unauthorized, 404 if session not found
  - _Requirements: 1, 24_

- [x] 2.3 Implement audio chunk rate limiting
  - Create RateLimiter class with sliding window (1 second)
  - Track chunks per second per connectionId
  - Drop excess chunks beyond limit (default 50/sec)
  - Emit CloudWatch metric for rate limit violations
  - Send warning message after 5 seconds of violations
  - Close connection after 30 seconds of violations
  - _Requirements: 26_

- [x] 2.4 Add audio format validation
  - Validate first chunk is PCM 16-bit mono
  - Verify sample rate is 16000 Hz
  - Cache validation result for subsequent chunks
  - Return 400 Bad Request if format invalid
  - Log validation failures with connection details
  - _Requirements: 13_

- [x] 2.5 Integrate with existing TranscribeStreamHandler
  - Initialize TranscribeStreamHandler on first audio chunk
  - Pass sessionId and sourceLanguage from session record
  - Forward audio chunks to handler's send_audio_chunk() method
  - Handle initialization errors with retry logic
  - Maintain stream state in Lambda memory
  - _Requirements: 2-5_


- [x] 2.6 Add Transcribe stream lifecycle management
  - Initialize stream on first audio chunk
  - Keep stream active during broadcasting
  - Close stream on speaker disconnect or 60-second idle
  - Implement reconnection logic for transient errors
  - Track stream state per session in memory
  - _Requirements: 5, 14_

- [x] 2.7 Implement audio buffer management
  - Create AudioBuffer class with 5-second capacity
  - Handle backpressure from Transcribe stream
  - Drop oldest chunks if buffer full
  - Emit metric for buffer overflows
  - Clear buffer on stream close
  - _Requirements: 3, 16_

- [x] 2.8 Add unit tests for audio processing
  - Test WebSocket message parsing
  - Test connection/session validation
  - Test rate limiting logic
  - Test audio format validation
  - Test Transcribe stream integration
  - Test error handling scenarios
  - _Requirements: All in Requirement 2_

- [x] 3. Extend connection_handler Lambda for speaker controls
  - Modify existing `session-management/lambda/connection_handler/handler.py`
  - Add routing logic for control message actions
  - Implement pause/resume/mute/unmute handlers
  - Implement volume and state change handlers
  - Add listener notification logic
  - _Requirements: 6-10, 18_

- [x] 3.1 Add control message routing
  - Parse action field from WebSocket message
  - Route to appropriate handler method
  - Validate connection role for each action
  - Return 403 if unauthorized
  - Log all control actions
  - _Requirements: 24_

- [x] 3.2 Implement pause/resume broadcast handlers
  - Update session broadcastState.isPaused in DynamoDB
  - Query all listener connections for session
  - Send broadcastPaused/broadcastResumed to listeners
  - Return acknowledgment to speaker
  - Handle DynamoDB errors with retry
  - _Requirements: 6, 7_


- [x] 3.3 Implement mute/unmute broadcast handlers
  - Update session broadcastState.isMuted in DynamoDB
  - Send broadcastMuted/broadcastUnmuted to listeners
  - Stop/resume audio forwarding to Transcribe
  - Return acknowledgment to speaker
  - _Requirements: 8_

- [x] 3.4 Implement volume control handler
  - Validate volumeLevel is between 0.0 and 1.0
  - Update session broadcastState.volume in DynamoDB
  - Send volumeChanged message to listeners
  - Apply volume multiplier to audio chunks
  - Treat volume=0.0 as mute
  - _Requirements: 9_

- [x] 3.5 Implement speaker state change handler
  - Validate state object contains valid fields
  - Update multiple broadcastState fields atomically
  - Send speakerStateChanged to listeners
  - Trigger appropriate actions (pause, mute) if needed
  - _Requirements: 10_

- [x] 3.6 Implement listener notification logic
  - Query connections by sessionId using GSI
  - Send message to each listener in parallel
  - Use API Gateway Management API
  - Log failures but continue with other listeners
  - Emit metric for notification latency
  - _Requirements: 6-10_

- [x] 3.7 Add listener control handlers
  - Implement pausePlayback handler (acknowledgment only)
  - Implement changeLanguage handler
  - Validate new language is supported
  - Update connection targetLanguage in DynamoDB
  - Return acknowledgment with new language
  - _Requirements: 18_

- [x] 3.8 Add unit tests for control handlers
  - Test each control action handler
  - Test state updates in DynamoDB
  - Test listener notification logic
  - Test authorization validation
  - Test concurrent state changes
  - Test error handling
  - _Requirements: All in Requirements 6-10, 18_


- [x] 4. Create session_status_handler Lambda for status queries
  - Create new `session-management/lambda/session_status_handler/`
  - Implement handler.py with status query logic
  - Add language distribution aggregation
  - Implement periodic status updates
  - Configure EventBridge rule for periodic triggers
  - _Requirements: 11, 12_

- [x] 4.1 Implement session status query handler
  - Extract connectionId from WebSocket event
  - Query connection to get sessionId
  - Query session record from DynamoDB
  - Query all listener connections for session
  - Aggregate listener count by targetLanguage
  - Calculate session duration
  - Return sessionStatus message
  - _Requirements: 11_

- [x] 4.2 Add language distribution aggregation
  - Group connections by targetLanguage
  - Count listeners per language
  - Return as map of language to count
  - Handle empty language gracefully
  - _Requirements: 11_

- [x] 4.3 Implement periodic status updates
  - Create EventBridge scheduled rule (every 30 seconds)
  - Query all active sessions
  - Send status update to each speaker
  - Include updateReason=periodic
  - Handle speaker disconnections gracefully
  - _Requirements: 12_

- [x] 4.4 Add triggered status updates
  - Detect listener count changes >10%
  - Detect new languages appearing
  - Send immediate status update
  - Include appropriate updateReason
  - Reset periodic timer on explicit query
  - _Requirements: 12_

- [x] 4.5 Add unit tests for session status
  - Test status query with various listener counts
  - Test language distribution aggregation
  - Test periodic update logic
  - Test performance with 500 listeners
  - Test error handling for missing sessions
  - _Requirements: All in Requirements 11-12_


- [x] 5. Add broadcast state to Session data model ✅ VERIFIED
  - Update `session-management/shared/models/session.py`
  - Add BroadcastState dataclass
  - Update Sessions table schema documentation
  - Add migration notes for existing sessions
  - _Requirements: 6-10_
  - **Status**: Complete - BroadcastState model fully implemented and integrated
  - **Tests**: 14 unit tests passing
  - **Documentation**: session-management/docs/WEBSOCKET_AUDIO_INTEGRATION_FOUNDATION.md

- [x] 5.1 Create BroadcastState dataclass ✅ VERIFIED
  - Add fields: isActive, isPaused, isMuted, volume, lastStateChange
  - Add validation methods
  - Add default values
  - Add serialization/deserialization methods
  - _Requirements: 6-10_
  - **File**: session-management/shared/models/broadcast_state.py (180 lines)

- [x] 5.2 Update Session model ✅ VERIFIED
  - Add broadcastState field to Session dataclass
  - Update to_dynamodb_item() method
  - Update from_dynamodb_item() method
  - Add backward compatibility for existing sessions
  - _Requirements: 6-10_
  - **File**: session-management/shared/data_access/sessions_repository.py
  - **Methods**: get_broadcast_state(), update_broadcast_state(), pause_broadcast(), resume_broadcast(), mute_broadcast(), unmute_broadcast(), set_broadcast_volume()

- [x] 6. Implement message size validation ✅ VERIFIED
  - Add validation to all Lambda handlers
  - Check total message size <128 KB
  - Check audio chunk size <32 KB
  - Check control message payload <4 KB
  - Return 413 Payload Too Large if exceeded
  - Log violations with connection details
  - _Requirements: 27_
  - **Status**: Complete - All validation functions implemented
  - **Tests**: 31 unit tests passing (including 16 message size tests)
  - **File**: session-management/shared/utils/validators.py
  - **Functions**: validate_message_size(), validate_audio_chunk_size(), validate_control_message_size()

- [x] 7. Implement connection timeout handling ✅ VERIFIED
  - Add timeout detection to connection_handler
  - Close connections idle for >120 seconds
  - Send connectionTimeout message before closing
  - Trigger disconnect handler for cleanup
  - Emit CloudWatch metrics for timeouts
  - _Requirements: 28_
  - **Status**: Complete - Full timeout handler Lambda implemented
  - **Tests**: 15 unit tests passing
  - **File**: session-management/lambda/timeout_handler/handler.py (300+ lines)
  - **Trigger**: EventBridge scheduled rule (every 60 seconds) - to be added in Task 10

- [ ] 8. Add CloudWatch metrics and alarms
  - Implement metrics for audio processing
  - Implement metrics for control messages
  - Implement metrics for session status
  - Implement metrics for rate limiting
  - Implement metrics for errors
  - Configure CloudWatch alarms
  - _Requirements: 21, 23_


- [ ] 8.1 Add audio processing metrics
  - AudioChunksReceived (Count, per session)
  - AudioProcessingLatency (Milliseconds, p50/p95/p99)
  - AudioChunksDropped (Count, per session)
  - AudioBufferOverflows (Count, per session)
  - TranscribeStreamInitLatency (Milliseconds)
  - TranscribeStreamErrors (Count, by error type)
  - _Requirements: 23_

- [ ] 8.2 Add control message metrics
  - ControlMessagesReceived (Count, by action type)
  - ControlMessageLatency (Milliseconds, p50/p95/p99)
  - ListenerNotificationLatency (Milliseconds)
  - ListenerNotificationFailures (Count)
  - _Requirements: 23_

- [ ] 8.3 Add session status metrics
  - StatusQueriesReceived (Count, per session)
  - StatusQueryLatency (Milliseconds, p50/p95/p99)
  - PeriodicStatusUpdatesSent (Count)
  - _Requirements: 23_

- [ ] 8.4 Add rate limiting metrics
  - RateLimitViolations (Count, by message type)
  - ConnectionsClosedForRateLimit (Count)
  - _Requirements: 23_

- [ ] 8.5 Add error metrics
  - LambdaErrors (Count, by handler and error type)
  - DynamoDBErrors (Count, by operation)
  - TranscribeErrors (Count, by error code)
  - _Requirements: 23_

- [ ] 8.6 Configure CloudWatch alarms
  - Critical: Audio latency p95 >100ms for 5 min
  - Critical: Transcribe error rate >5% for 5 min
  - Critical: Lambda error rate >1% for 5 min
  - Warning: Audio latency p95 >75ms for 10 min
  - Warning: Control latency p95 >150ms for 10 min
  - Warning: Rate limit violations >100/min
  - _Requirements: 23_


- [ ] 9. Add structured logging
  - Implement JSON log format for all handlers
  - Add correlation IDs (sessionId, connectionId)
  - Log all WebSocket messages at DEBUG level
  - Log all Transcribe events at DEBUG level
  - Log all errors at ERROR level with context
  - Configure log retention (12 hours)
  - _Requirements: 23_

- [x] 10. Update CDK infrastructure ✅ COMPLETE
  - Update `session-management/infrastructure/stacks/` with new routes
  - Add session_status_handler Lambda to CDK
  - Update IAM roles with new permissions
  - Add EventBridge rule for periodic updates
  - Configure Lambda memory and timeout settings
  - Deploy infrastructure changes
  - _Requirements: 20_

- [x] 10.1 Add WebSocket routes to CDK ✅ COMPLETE
  - Add sendAudio route configuration
  - Add speaker control routes (pause, resume, mute, volume, state)
  - Add session status route
  - Add listener control routes (pausePlayback, changeLanguage)
  - Configure route selection expressions
  - Map routes to Lambda integrations
  - _Requirements: 19, 20_

- [x] 10.2 Add session_status_handler Lambda to CDK ✅ COMPLETE
  - Create Lambda function resource
  - Configure memory (256 MB) and timeout (5 seconds)
  - Add IAM role with DynamoDB read permissions
  - Add environment variables
  - Configure log group
  - _Requirements: 20_

- [x] 10.3 Update IAM permissions ✅ COMPLETE
  - Add Transcribe permissions to audio_processor role:
    - `transcribe:StartStreamTranscription`
    - `transcribe:StartStreamTranscriptionWebSocket`
  - Add API Gateway Management API permissions to connection_handler:
    - `execute-api:ManageConnections` (for sending messages to WebSocket connections)
    - `execute-api:Invoke` (for API Gateway Management API)
  - Add DynamoDB permissions for broadcast state updates:
    - `dynamodb:UpdateItem` on Sessions table
    - `dynamodb:GetItem` on Sessions table
  - Add session_status_handler permissions:
    - `dynamodb:Query` on Sessions table
    - `dynamodb:Query` on Connections table with GSI sessionId-targetLanguage-index
    - `dynamodb:GetItem` on both tables
  - Add Lambda invoke permissions for Translation Pipeline:
    - `lambda:InvokeFunction` on TranslationProcessor Lambda
  - _Requirements: 20_
  - **Note**: Translation Pipeline Lambda invoke permission needs to be added to audio-transcription stack separately

- [x] 10.4 Add EventBridge rule for periodic updates ✅ COMPLETE
  - Create scheduled rule (every 30 seconds)
  - Target session_status_handler Lambda
  - Configure input transformer
  - Add IAM permissions
  - _Requirements: 12_


- [ ] 11. Integration testing
  - Test end-to-end audio flow
  - Test control message flow
  - Test session status queries
  - Test error scenarios
  - Test performance under load
  - _Requirements: All_

- [ ] 11.1 Test end-to-end audio flow
  - Speaker connects and creates session
  - Speaker sends audio chunks
  - Verify Transcribe stream initialized
  - Verify transcription events processed
  - Verify results forwarded to Translation Pipeline
  - Verify no audio loss or duplication
  - _Requirements: 1-5, 25_

- [ ] 11.2 Test control message flow
  - Speaker pauses broadcast
  - Verify session state updated
  - Verify listeners notified
  - Verify audio processing stopped
  - Speaker resumes
  - Verify audio processing resumed
  - Test mute, volume, state changes
  - _Requirements: 6-10_

- [ ] 11.3 Test session status queries
  - Multiple listeners join with different languages
  - Speaker queries status
  - Verify correct listener count
  - Verify correct language distribution
  - Verify response latency <500ms
  - Test periodic updates
  - _Requirements: 11-12_

- [ ] 11.4 Test error scenarios
  - Test invalid audio format
  - Test rate limit violations
  - Test Transcribe stream failures
  - Test DynamoDB errors
  - Test unauthorized actions
  - Test connection timeouts
  - _Requirements: 14, 22, 24, 26-28_

- [ ]* 11.5 Load testing
  - 100 concurrent speakers sending audio
  - 50 chunks/second per speaker
  - Verify p95 latency <50ms
  - Verify no dropped chunks
  - Test control messages under load
  - Test session status queries under load
  - _Requirements: 21_


- [ ] 12. Update documentation
  - Update session-management README with new routes
  - Update audio-transcription README with WebSocket integration
  - Document broadcast state model
  - Document control message formats
  - Document session status response format
  - Create deployment guide
  - _Requirements: All_

- [ ] 12.1 Update session-management documentation
  - Document new WebSocket routes
  - Document control message formats
  - Document broadcast state management
  - Update API documentation
  - _Requirements: 6-12, 18-19_

- [ ] 12.2 Update audio-transcription documentation
  - Document WebSocket audio reception
  - Document Transcribe stream integration
  - Document rate limiting
  - Document error handling
  - _Requirements: 1-5, 13-14, 26_

- [ ] 12.3 Create integration guide
  - Document end-to-end flow
  - Document frontend integration requirements
  - Document message formats
  - Provide code examples
  - _Requirements: All_

## Notes

### Leveraging Existing Infrastructure

This implementation plan is designed to maximize reuse of existing, well-tested components:

**Existing Components to Reuse**:
- `TranscribeStreamHandler` - Complete Transcribe stream management
- `PartialResultProcessor` - Sophisticated partial results processing
- `TranslationPipelineOrchestrator` - Complete translation pipeline
- `SessionsRepository` - DynamoDB session management
- `ConnectionsRepository` - DynamoDB connection management

**New Components to Create**:
- WebSocket message parsing and routing
- Audio chunk rate limiting
- Broadcast state management
- Session status aggregation
- Listener notification logic

### Testing Strategy

- All unit tests are required for comprehensive coverage
- Integration tests are critical for validating end-to-end flow
- Load testing (Task 11.5) is optional - marked with `*` for faster MVP delivery
- Performance testing can be done in staging before production rollout
- Focus testing on new integration code, not existing components
- Existing components (TranscribeStreamHandler, PartialResultProcessor) already have comprehensive tests

### Deployment Strategy

1. Deploy infrastructure changes (routes, Lambda, IAM)
2. Deploy code changes to existing Lambdas
3. Deploy new session_status_handler Lambda
4. Run integration tests in staging
5. Monitor metrics for 24 hours
6. Deploy to production with canary (10% traffic)
7. Monitor for 48 hours before full rollout
