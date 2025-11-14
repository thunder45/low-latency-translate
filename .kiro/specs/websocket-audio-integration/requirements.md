# WebSocket Audio Integration Requirements

## Introduction

This feature bridges the gap between WebSocket audio reception and real-time transcription processing. It implements the critical missing components that enable speakers to send audio through WebSocket connections and have that audio processed through AWS Transcribe Streaming API, with proper state management and control message handling.

Currently, the system has session management (connection/disconnection) and transcription processing components, but lacks the integration layer that connects them. This spec addresses four critical missing implementations:
1. `sendAudio` WebSocket route and handler for receiving audio chunks
2. Real-time Transcribe streaming integration with event loop management
3. Speaker control message handlers (pause, mute, volume, state changes)
4. Session status route for real-time listener statistics

## Glossary

- **System**: The WebSocket Audio Integration component
- **Speaker**: Authenticated user broadcasting audio through WebSocket
- **Listener**: Anonymous user receiving translated audio
- **Audio Chunk**: Binary audio data segment (typically 100-200ms of audio)
- **Transcribe Stream**: AWS Transcribe Streaming API connection for real-time transcription
- **Event Loop**: Asynchronous processing loop managing Transcribe stream events
- **Control Message**: WebSocket message from speaker to control broadcast state
- **Session Status**: Real-time statistics about active listeners and languages
- **Audio Processor Lambda**: Lambda function handling sendAudio WebSocket route
- **Connection Handler**: Existing Lambda managing WebSocket lifecycle
- **Broadcast State**: Current state of speaker broadcast (active, paused, muted)
- **Audio Buffer**: Temporary storage for audio chunks awaiting processing
- **Stream Handler**: Component managing bidirectional Transcribe stream communication
- **Partial Result**: Intermediate transcription from AWS Transcribe
- **Final Result**: Completed transcription segment from AWS Transcribe
- **Translation Pipeline**: Downstream component processing transcribed text
- **API Gateway Management API**: AWS service for sending messages to WebSocket connections

## Requirements

### Requirement 1: Audio Reception via WebSocket

**User Story:** As a Speaker, I want to send audio chunks through my WebSocket connection, so that my speech can be transcribed and translated in real-time

#### Acceptance Criteria

1. WHEN THE Speaker sends a message with action=sendAudio and binary audio data, THE System SHALL route the message to the Audio Processor Lambda via custom WebSocket route
2. WHEN THE Audio Processor Lambda receives audio data, THE System SHALL validate the connection exists and role=speaker in DynamoDB Connections table
3. WHEN THE connection is validated, THE System SHALL extract sessionId from the connection record
4. WHEN THE sessionId is retrieved, THE System SHALL verify the session isActive=true in DynamoDB Sessions table
5. WHEN THE session is active, THE System SHALL forward the audio chunk to the Transcribe Stream Handler for processing within 50 milliseconds

### Requirement 2: Transcribe Stream Initialization

**User Story:** As a system operator, I want Transcribe streams to be initialized when speakers start broadcasting, so that audio can be processed immediately

#### Acceptance Criteria

1. WHEN THE first audio chunk arrives for a session, THE System SHALL initialize an AWS Transcribe Streaming API connection with sourceLanguage from session record
2. WHEN THE Transcribe stream is initialized, THE System SHALL configure partial results enabled with stability scores
3. WHEN THE stream configuration is set, THE System SHALL set media encoding to PCM, sample rate to 16000 Hz, and enable channel identification if supported
4. WHEN THE stream is ready, THE System SHALL start an asynchronous event loop to process Transcribe events
5. WHEN THE stream initialization fails, THE System SHALL retry up to 3 times with exponential backoff before returning error to speaker

### Requirement 3: Audio Chunk Processing

**User Story:** As a Speaker, I want my audio to be processed efficiently, so that transcription latency remains minimal

#### Acceptance Criteria

1. WHEN THE System receives an audio chunk, THE System SHALL validate the chunk size is between 100 bytes and 32 KB
2. WHEN THE chunk size is valid, THE System SHALL send the audio chunk to the active Transcribe stream within 20 milliseconds
3. WHEN THE audio is sent to Transcribe, THE System SHALL maintain an audio buffer of maximum 5 seconds for handling backpressure
4. IF THE audio buffer exceeds capacity, THEN THE System SHALL drop the oldest chunks and emit a CloudWatch metric for buffer overflow
5. WHEN THE audio chunk is processed, THE System SHALL emit CloudWatch metrics for audio processing latency (p50, p95, p99)

### Requirement 4: Transcribe Event Loop Management

**User Story:** As a system operator, I want Transcribe events to be processed asynchronously, so that audio reception is not blocked by transcription processing

#### Acceptance Criteria

1. WHEN THE Transcribe stream emits a TranscriptEvent, THE System SHALL process the event in an asynchronous event loop separate from audio reception
2. WHEN THE event contains partial results with IsPartial=true, THE System SHALL extract the transcript text and stability score
3. WHEN THE event contains final results with IsPartial=false, THE System SHALL extract the transcript text and mark as final
4. WHEN THE transcript is extracted, THE System SHALL forward it to the Translation Pipeline with sessionId, text, isPartial, stability score, and timestamp
5. WHEN THE event loop encounters an error, THE System SHALL log the error, attempt to reconnect the Transcribe stream, and notify the speaker via WebSocket

### Requirement 5: Transcribe Stream Lifecycle Management

**User Story:** As a system operator, I want Transcribe streams to be properly managed throughout the session lifecycle, so that resources are not leaked

#### Acceptance Criteria

1. WHEN THE Speaker connection is established, THE System SHALL NOT initialize a Transcribe stream until the first audio chunk arrives
2. WHEN THE Speaker pauses broadcasting, THE System SHALL keep the Transcribe stream active but stop sending audio chunks
3. WHEN THE Speaker resumes broadcasting, THE System SHALL resume sending audio chunks to the existing Transcribe stream
4. WHEN THE Speaker disconnects, THE System SHALL gracefully close the Transcribe stream within 5 seconds
5. WHEN THE Transcribe stream is idle for more than 60 seconds, THE System SHALL close the stream and reinitialize on next audio chunk

### Requirement 6: Speaker Pause Control

**User Story:** As a Speaker, I want to pause my broadcast, so that I can take breaks without ending the session

#### Acceptance Criteria

1. WHEN THE Speaker sends a message with action=pauseBroadcast, THE System SHALL update the session broadcast state to paused in DynamoDB Sessions table
2. WHEN THE broadcast state is updated, THE System SHALL stop forwarding audio chunks to the Transcribe stream
3. WHEN THE pause is processed, THE System SHALL send a broadcastPaused message to all listener connections for that sessionId
4. WHEN THE listeners receive broadcastPaused, THE System SHALL include timestamp and estimated pause duration if provided
5. WHEN THE broadcast is paused, THE System SHALL maintain the Transcribe stream connection for up to 60 seconds before closing

### Requirement 7: Speaker Resume Control

**User Story:** As a Speaker, I want to resume my broadcast after pausing, so that I can continue without reconnecting

#### Acceptance Criteria

1. WHEN THE Speaker sends a message with action=resumeBroadcast, THE System SHALL update the session broadcast state to active in DynamoDB Sessions table
2. WHEN THE broadcast state is updated, THE System SHALL resume forwarding audio chunks to the Transcribe stream
3. IF THE Transcribe stream was closed during pause, THEN THE System SHALL reinitialize the stream before resuming
4. WHEN THE resume is processed, THE System SHALL send a broadcastResumed message to all listener connections for that sessionId
5. WHEN THE broadcast resumes, THE System SHALL emit a CloudWatch metric for pause duration

### Requirement 8: Speaker Mute Control

**User Story:** As a Speaker, I want to mute my microphone temporarily, so that background noise is not broadcast

#### Acceptance Criteria

1. WHEN THE Speaker sends a message with action=muteBroadcast, THE System SHALL update the session broadcast state to muted in DynamoDB Sessions table
2. WHEN THE broadcast state is muted, THE System SHALL stop forwarding audio chunks to the Transcribe stream
3. WHEN THE mute is processed, THE System SHALL send a broadcastMuted message to all listener connections for that sessionId
4. WHEN THE Speaker sends action=unmuteBroadcast, THE System SHALL update broadcast state to active and resume audio forwarding
5. WHEN THE unmute is processed, THE System SHALL send a broadcastUnmuted message to all listener connections

### Requirement 9: Speaker Volume Control

**User Story:** As a Speaker, I want to adjust my broadcast volume, so that listeners receive audio at appropriate levels

#### Acceptance Criteria

1. WHEN THE Speaker sends a message with action=setVolume and volumeLevel (0.0-1.0), THE System SHALL validate volumeLevel is between 0.0 and 1.0
2. WHEN THE volume level is valid, THE System SHALL store the volumeLevel in the session record in DynamoDB Sessions table
3. WHEN THE volume is updated, THE System SHALL send a volumeChanged message to all listener connections with new volumeLevel
4. WHEN THE audio chunks are processed, THE System SHALL apply the volumeLevel multiplier to audio amplitude before sending to Transcribe
5. WHEN THE volume is set to 0.0, THE System SHALL treat it as mute and stop forwarding audio

### Requirement 10: Speaker State Change Notifications

**User Story:** As a Speaker, I want to notify listeners of my broadcast state changes, so that they understand what's happening

#### Acceptance Criteria

1. WHEN THE Speaker sends a message with action=speakerStateChange and state object, THE System SHALL validate the state contains valid fields (isPaused, isMuted, volume)
2. WHEN THE state is valid, THE System SHALL update the corresponding fields in the session record in DynamoDB Sessions table
3. WHEN THE state is updated, THE System SHALL send a speakerStateChanged message to all listener connections with complete state object
4. WHEN THE state change includes isPaused=true, THE System SHALL also trigger pause broadcast logic
5. WHEN THE state change includes isMuted=true, THE System SHALL also trigger mute broadcast logic

### Requirement 11: Session Status Query

**User Story:** As a Speaker, I want to see real-time statistics about my session, so that I know how many listeners are connected and what languages they're using

#### Acceptance Criteria

1. WHEN THE Speaker sends a message with action=getSessionStatus, THE System SHALL query the session record from DynamoDB Sessions table
2. WHEN THE session is retrieved, THE System SHALL query all listener connections for that sessionId using GSI sessionId-targetLanguage-index
3. WHEN THE connections are retrieved, THE System SHALL aggregate listener count by targetLanguage
4. WHEN THE aggregation is complete, THE System SHALL return a sessionStatus message containing listenerCount, languageDistribution (map of language to count), sessionDuration, and broadcastState
5. WHEN THE status query completes, THE System SHALL respond within 500 milliseconds

### Requirement 12: Periodic Session Status Updates

**User Story:** As a Speaker, I want to receive periodic updates about my session status, so that I can monitor listener engagement without polling

#### Acceptance Criteria

1. WHEN THE Speaker connection is established, THE System SHALL automatically send sessionStatus messages every 30 seconds
2. WHEN THE listener count changes by more than 10%, THE System SHALL send an immediate sessionStatus update to the speaker
3. WHEN THE new listener joins with a previously unseen targetLanguage, THE System SHALL send an immediate sessionStatus update
4. WHEN THE periodic update is sent, THE System SHALL include timestamp and updateReason (periodic, listenerCountChange, newLanguage)
5. WHEN THE speaker explicitly requests status via getSessionStatus, THE System SHALL reset the 30-second periodic timer

### Requirement 13: Audio Format Validation

**User Story:** As a system operator, I want audio format to be validated, so that incompatible audio doesn't cause processing errors

#### Acceptance Criteria

1. WHEN THE System receives the first audio chunk, THE System SHALL validate the audio format is PCM 16-bit mono
2. WHEN THE audio format is validated, THE System SHALL verify the sample rate is 16000 Hz
3. IF THE audio format is invalid, THEN THE System SHALL return an error message with code INVALID_AUDIO_FORMAT to the speaker
4. WHEN THE audio format validation fails, THE System SHALL log the failure with connection details and audio metadata
5. WHEN THE audio format is valid, THE System SHALL cache the validation result for subsequent chunks from the same connection

### Requirement 14: Transcribe Error Handling

**User Story:** As a Speaker, I want to be notified when transcription fails, so that I can take corrective action

#### Acceptance Criteria

1. WHEN THE Transcribe stream returns an error, THE System SHALL log the error with sessionId, error code, and error message
2. WHEN THE error is transient (throttling, temporary unavailability), THE System SHALL retry with exponential backoff up to 3 attempts
3. WHEN THE error is permanent (invalid language, quota exceeded), THE System SHALL send a transcriptionError message to the speaker with error details
4. WHEN THE Transcribe stream fails after retries, THE System SHALL close the stream and require speaker to restart broadcasting
5. WHEN THE transcription error occurs, THE System SHALL emit CloudWatch metrics for error type and frequency

### Requirement 15: Concurrent Session Limits

**User Story:** As a system operator, I want to limit concurrent Transcribe streams per speaker, so that costs remain predictable

#### Acceptance Criteria

1. THE System SHALL enforce a maximum of MAX_CONCURRENT_STREAMS_PER_SPEAKER (default 1, configurable) active Transcribe streams per speaker userId
2. WHEN THE speaker attempts to create a second session while one is active, THE System SHALL return an error with code MAX_SESSIONS_EXCEEDED
3. WHEN THE speaker's active session ends, THE System SHALL decrement the concurrent stream counter
4. WHEN THE concurrent stream limit is reached, THE System SHALL log the event with speaker userId and timestamp
5. WHEN THE speaker disconnects abnormally, THE System SHALL ensure the stream counter is decremented within 60 seconds

### Requirement 16: Audio Chunk Ordering

**User Story:** As a system operator, I want audio chunks to be processed in order, so that transcription is accurate

#### Acceptance Criteria

1. WHEN THE System receives audio chunks, THE System SHALL process them in the order received
2. WHEN THE audio chunks arrive out of order due to network issues, THE System SHALL buffer and reorder based on sequence numbers if provided
3. IF THE sequence numbers are not provided, THEN THE System SHALL process chunks in arrival order
4. WHEN THE audio chunk ordering is violated, THE System SHALL log a warning with sessionId and chunk metadata
5. WHEN THE reordering buffer exceeds 2 seconds of audio, THE System SHALL flush the buffer in current order to prevent excessive latency

### Requirement 17: Broadcast State Persistence

**User Story:** As a Speaker, I want my broadcast state to persist across connection refreshes, so that my settings are maintained

#### Acceptance Criteria

1. WHEN THE Speaker connection is refreshed, THE System SHALL retrieve the broadcast state from the session record in DynamoDB
2. WHEN THE broadcast state is retrieved, THE System SHALL send a stateRestored message to the new connection with isPaused, isMuted, and volume
3. WHEN THE connection refresh completes, THE System SHALL resume audio processing with the restored state
4. IF THE broadcast was paused before refresh, THEN THE System SHALL remain paused after refresh
5. WHEN THE state is restored, THE System SHALL emit a CloudWatch metric for successful state restoration

### Requirement 18: Listener Control Message Routing

**User Story:** As a Listener, I want my control messages to be routed correctly, so that my preferences are applied

#### Acceptance Criteria

1. WHEN THE Listener sends a message with action=pausePlayback, THE System SHALL validate the connection exists and role=listener
2. WHEN THE listener control is validated, THE System SHALL NOT affect the speaker's broadcast state
3. WHEN THE listener pauses playback, THE System SHALL send acknowledgment to that listener connection only
4. WHEN THE listener changes language via action=changeLanguage, THE System SHALL update the connection record targetLanguage in DynamoDB
5. WHEN THE language is changed, THE System SHALL send a languageChanged acknowledgment to the listener with new targetLanguage

### Requirement 19: WebSocket Route Configuration

**User Story:** As a system administrator, I want WebSocket routes to be properly configured, so that messages are routed to correct handlers

#### Acceptance Criteria

1. THE System SHALL configure a custom route named sendAudio in API Gateway WebSocket API
2. THE System SHALL configure a custom route named pauseBroadcast in API Gateway WebSocket API
3. THE System SHALL configure a custom route named resumeBroadcast in API Gateway WebSocket API
4. THE System SHALL configure a custom route named muteBroadcast in API Gateway WebSocket API
5. THE System SHALL configure a custom route named unmuteBroadcast in API Gateway WebSocket API
6. THE System SHALL configure a custom route named setVolume in API Gateway WebSocket API
7. THE System SHALL configure a custom route named speakerStateChange in API Gateway WebSocket API
8. THE System SHALL configure a custom route named getSessionStatus in API Gateway WebSocket API
9. THE System SHALL configure a custom route named pausePlayback in API Gateway WebSocket API
10. THE System SHALL configure a custom route named changeLanguage in API Gateway WebSocket API

### Requirement 20: Lambda Handler Implementation

**User Story:** As a system administrator, I want Lambda handlers to be implemented for all WebSocket routes, so that messages are processed correctly

#### Acceptance Criteria

1. THE System SHALL implement an Audio Processor Lambda handler for sendAudio route with 1024 MB memory and 60 second timeout
2. THE System SHALL implement a Speaker Control Lambda handler for pauseBroadcast, resumeBroadcast, muteBroadcast, unmuteBroadcast, setVolume, and speakerStateChange routes with 512 MB memory and 10 second timeout
3. THE System SHALL implement a Session Status Lambda handler for getSessionStatus route with 256 MB memory and 5 second timeout
4. THE System SHALL implement a Listener Control Lambda handler for pausePlayback and changeLanguage routes with 256 MB memory and 5 second timeout
5. WHEN THE Lambda handlers are deployed, THE System SHALL configure appropriate IAM roles with permissions for DynamoDB, Transcribe, and API Gateway Management API

### Requirement 21: Performance Optimization

**User Story:** As a system operator, I want the audio processing pipeline to be optimized, so that latency targets are met

#### Acceptance Criteria

1. WHEN THE System processes audio chunks, THE System SHALL achieve p95 latency of less than 50 milliseconds from WebSocket receipt to Transcribe stream send
2. WHEN THE System processes control messages, THE System SHALL achieve p95 latency of less than 100 milliseconds from receipt to acknowledgment
3. WHEN THE System queries session status, THE System SHALL achieve p95 latency of less than 500 milliseconds from request to response
4. WHEN THE System forwards transcription results to Translation Pipeline, THE System SHALL achieve p95 latency of less than 100 milliseconds
5. WHEN THE performance targets are not met, THE System SHALL emit CloudWatch alarms for investigation

### Requirement 22: Error Recovery and Resilience

**User Story:** As a Speaker, I want the system to recover gracefully from errors, so that temporary issues don't end my session

#### Acceptance Criteria

1. WHEN THE Transcribe stream encounters a transient error, THE System SHALL automatically reconnect within 5 seconds
2. WHEN THE DynamoDB query fails, THE System SHALL retry with exponential backoff up to 3 attempts
3. WHEN THE API Gateway Management API call fails to send message to listener, THE System SHALL log the failure but continue processing other listeners
4. WHEN THE Lambda function times out, THE System SHALL log the timeout and return appropriate error to client
5. WHEN THE system recovers from error, THE System SHALL send a systemRecovered message to affected connections

### Requirement 23: Monitoring and Observability

**User Story:** As a system operator, I want comprehensive monitoring, so that I can detect and resolve issues quickly

#### Acceptance Criteria

1. THE System SHALL emit CloudWatch metrics for audio chunks received per second per session
2. THE System SHALL emit CloudWatch metrics for Transcribe stream initialization latency
3. THE System SHALL emit CloudWatch metrics for control message processing latency by message type
4. THE System SHALL emit CloudWatch metrics for session status query latency
5. THE System SHALL emit CloudWatch metrics for error rates by error type and handler
6. THE System SHALL log all WebSocket messages at DEBUG level with sanitized content (no audio data)
7. THE System SHALL log all Transcribe events at DEBUG level with transcript text and metadata
8. THE System SHALL log all errors at ERROR level with full context including sessionId, connectionId, and stack trace

### Requirement 24: Security and Access Control

**User Story:** As a security administrator, I want proper access control on WebSocket routes, so that users can only perform authorized actions

#### Acceptance Criteria

1. WHEN THE System receives sendAudio message, THE System SHALL verify the connection role is speaker
2. WHEN THE System receives speaker control messages (pause, mute, volume), THE System SHALL verify the connection role is speaker
3. WHEN THE System receives listener control messages (pausePlayback, changeLanguage), THE System SHALL verify the connection role is listener
4. WHEN THE role verification fails, THE System SHALL return HTTP status 403 Forbidden with error code UNAUTHORIZED_ACTION
5. WHEN THE System processes messages, THE System SHALL not log sensitive data including audio content or user identifiers

### Requirement 25: Integration with Translation Pipeline

**User Story:** As a system operator, I want transcription results to be forwarded to the Translation Pipeline, so that end-to-end flow is complete

#### Acceptance Criteria

1. WHEN THE System receives a transcription result from Transcribe, THE System SHALL forward it to the Translation Pipeline Lambda via direct invocation
2. WHEN THE transcription is forwarded, THE System SHALL include sessionId, text, isPartial, stabilityScore, timestamp, and sourceLanguage
3. WHEN THE Translation Pipeline processes the transcription, THE System SHALL receive acknowledgment within 200 milliseconds
4. IF THE Translation Pipeline invocation fails, THEN THE System SHALL retry up to 2 times with 100ms delay between attempts
5. WHEN THE Translation Pipeline is unavailable after retries, THE System SHALL log the failure and continue processing subsequent transcriptions

### Requirement 26: Audio Message Rate Limiting

**User Story:** As a system operator, I want to prevent audio spam through rate limiting, so that malicious speakers cannot overwhelm the system

#### Acceptance Criteria

1. THE System SHALL limit sendAudio messages to RATE_LIMIT_AUDIO_CHUNKS_PER_SECOND (default 50, configurable) chunks per second per speaker connection
2. WHEN THE audio chunk rate exceeds the limit, THE System SHALL drop excess chunks and emit a CloudWatch metric for rate limit violations
3. WHEN THE rate limit is exceeded for more than 5 consecutive seconds, THE System SHALL send a rateLimitWarning message to the speaker
4. WHEN THE rate limit violations persist for more than 30 seconds, THE System SHALL close the speaker connection and mark session as inactive
5. THE System SHALL track audio chunk rate using a sliding window of 1 second duration

### Requirement 27: Message Size Validation

**User Story:** As a system operator, I want all WebSocket messages to be size-validated, so that oversized messages don't cause processing issues

#### Acceptance Criteria

1. WHEN THE System receives any WebSocket message, THE System SHALL validate the total message size is less than MAX_MESSAGE_SIZE_BYTES (default 128 KB, configurable up to 1 MB per API Gateway limit)
2. WHEN THE message size exceeds the limit, THE System SHALL return an error with code MESSAGE_TOO_LARGE and HTTP status 413
3. WHEN THE audio chunk size exceeds 32 KB, THE System SHALL return an error with code AUDIO_CHUNK_TOO_LARGE
4. WHEN THE control message payload exceeds 4 KB, THE System SHALL return an error with code CONTROL_MESSAGE_TOO_LARGE
5. WHEN THE message size validation fails, THE System SHALL log the violation with connection details and message type

### Requirement 28: Connection Timeout Handling

**User Story:** As a system operator, I want inactive connections to be detected and cleaned up, so that resources are not wasted on dead connections

#### Acceptance Criteria

1. WHEN THE Speaker connection has not sent any message (audio or heartbeat) for CONNECTION_IDLE_TIMEOUT_SECONDS (default 120, configurable), THE System SHALL close the connection
2. WHEN THE connection is closed due to timeout, THE System SHALL trigger the disconnect handler to clean up session state
3. WHEN THE Listener connection has not sent any message for CONNECTION_IDLE_TIMEOUT_SECONDS, THE System SHALL close the connection and decrement listener count
4. WHEN THE connection timeout occurs, THE System SHALL send a connectionTimeout message to the client before closing
5. THE System SHALL emit CloudWatch metrics for connection timeouts by role (speaker, listener) and reason (idle, no heartbeat)
