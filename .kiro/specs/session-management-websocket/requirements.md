# Session Management & WebSocket Infrastructure
## Requirements Document v1.0

## Introduction

This feature implements the core session management and WebSocket infrastructure for the real-time multilingual audio broadcasting system. It provides the foundation for speaker authentication, session creation with human-readable IDs, listener joining, and connection lifecycle management.

The system enables one authenticated speaker to create a broadcasting session and multiple anonymous listeners to join that session for receiving translated audio. All communication occurs over WebSocket connections managed by AWS API Gateway.

## Glossary

- **System**: The Session Management and WebSocket Infrastructure component
- **Speaker**: Authenticated user who creates and broadcasts in a session
- **Listener**: Anonymous user who joins a session to receive audio
- **Session**: A broadcasting instance with one speaker and multiple listeners
- **WebSocket Connection**: Persistent bidirectional communication channel using WSS protocol
- **Connection Handler**: AWS Lambda function managing WebSocket lifecycle events ($connect, $disconnect)
- **Session ID**: Human-readable identifier in format {adjective}-{noun}-{3-digit-number} (e.g., "golden-eagle-427")
- **API Gateway**: AWS service managing WebSocket connections and routing
- **DynamoDB**: NoSQL database storing session and connection state with TTL-based cleanup
- **JWT Token**: JSON Web Token issued by AWS Cognito for speaker authentication
- **Lambda Authorizer**: AWS Lambda function validating JWT tokens for speaker connections
- **Connection ID**: Unique identifier assigned by API Gateway for each WebSocket connection
- **Heartbeat**: Periodic message sent by client to maintain connection and detect timeouts
- **Rate Limiter**: Component enforcing request limits to prevent abuse
- **TTL**: Time-To-Live attribute for automatic DynamoDB record expiration
- **GSI**: Global Secondary Index for efficient DynamoDB queries by non-primary key attributes

## Requirements

### Requirement 1: Speaker Session Creation

**User Story:** As a Speaker, I want to create a new broadcasting session with a memorable session ID, so that I can easily share it with my audience

#### Acceptance Criteria

1. WHEN THE Speaker initiates a WebSocket connection with valid JWT token and action=createSession, THE System SHALL authenticate the token using Lambda Authorizer
2. WHEN THE authentication succeeds, THE System SHALL generate a unique human-readable Session ID in format {adjective}-{noun}-{3-digit-number}
3. WHEN THE Session ID is generated, THE System SHALL verify uniqueness against active sessions in DynamoDB Sessions table
4. WHEN THE Session ID is unique, THE System SHALL create a session record in DynamoDB with sessionId, speakerConnectionId, sourceLanguage, createdAt, isActive=true, listenerCount=0, qualityTier, and expiresAt
5. WHEN THE session is created, THE System SHALL return a sessionCreated message to the Speaker containing sessionId, sourceLanguage, qualityTier, and connectionId within 2 seconds

### Requirement 2: Anonymous Listener Joining

**User Story:** As a Listener, I want to join an existing session without authentication, so that I can quickly access the translated audio stream

#### Acceptance Criteria

1. WHEN THE Listener initiates a WebSocket connection with sessionId and targetLanguage parameters, THE System SHALL validate the session exists and isActive=true in DynamoDB Sessions table
2. WHEN THE session is valid, THE System SHALL validate that targetLanguage is supported by both AWS Translate for source-to-target translation and AWS Polly for neural voice availability
3. WHEN THE language validation passes, THE System SHALL create a connection record in DynamoDB Connections table with connectionId, sessionId, targetLanguage, role=listener, connectedAt, and ttl
4. WHEN THE connection record is created, THE System SHALL atomically increment the listenerCount in the Sessions table using ADD operation
5. WHEN THE listener count is updated, THE System SHALL return a sessionJoined message containing sessionId, targetLanguage, connectionId, and sourceLanguage
6. IF THE session does not exist or isActive=false, THEN THE System SHALL return an error message with code SESSION_NOT_FOUND and HTTP status 404
7. IF THE targetLanguage is not supported by AWS Translate or AWS Polly neural voices, THEN THE System SHALL return an error message with code UNSUPPORTED_LANGUAGE and HTTP status 400

### Requirement 3: Human-Readable Session ID Generation

**User Story:** As a system administrator, I want session IDs to be human-readable and memorable using Christian/Bible vocabulary, so that speakers can easily communicate them to their audience

#### Acceptance Criteria

1. THE System SHALL maintain a word list of minimum 100 Christian/Bible-themed adjectives (e.g., faithful, blessed, gracious, righteous)
2. THE System SHALL maintain a word list of minimum 100 Christian/Bible-themed nouns (e.g., shepherd, covenant, temple, prophet)
3. WHEN THE System generates a Session ID, THE System SHALL randomly select one adjective, one noun, and a 3-digit number between 100 and 999
4. WHEN THE words are selected, THE System SHALL verify neither word appears in the profanity blacklist
5. IF THE generated Session ID already exists in active sessions, THEN THE System SHALL regenerate until a unique ID is found with maximum 10 attempts

### Requirement 4: Speaker Disconnection and Session Termination

**User Story:** As a Speaker, I want my session to automatically end when I disconnect, so that resources are cleaned up and listeners are notified

#### Acceptance Criteria

1. WHEN THE Speaker WebSocket connection closes, THE System SHALL detect the disconnect event via $disconnect route
2. WHEN THE disconnect is detected, THE System SHALL update the session isActive status to false in DynamoDB Sessions table
3. WHEN THE session is marked inactive, THE System SHALL query all listener connections for that sessionId using GSI sessionId-targetLanguage-index
4. WHEN THE listener connections are retrieved, THE System SHALL send a sessionEnded message to each listener Connection ID using API Gateway Management API
5. WHEN THE messages are sent, THE System SHALL delete all connection records for that sessionId from DynamoDB Connections table

### Requirement 5: Listener Disconnection and Count Management

**User Story:** As a Listener, I want my connection to be properly cleaned up when I disconnect, so that the system accurately tracks active listeners

#### Acceptance Criteria

1. WHEN THE Listener WebSocket connection closes, THE System SHALL detect the disconnect event via $disconnect route
2. WHEN THE disconnect is detected, THE System SHALL delete the connection record from DynamoDB Connections table
3. WHEN THE connection record is deleted, THE System SHALL atomically decrement the listenerCount in the Sessions table using ADD operation with value -1
4. IF THE listenerCount becomes negative due to race conditions, THEN THE System SHALL set listenerCount to 0
5. WHEN THE cleanup is complete, THE System SHALL log the disconnection with sessionId, connectionId, and timestamp

### Requirement 6: Automatic Session Expiration

**User Story:** As a system administrator, I want sessions to automatically expire after a configurable duration, so that abandoned sessions don't consume resources indefinitely

#### Acceptance Criteria

1. WHEN THE System creates a session, THE System SHALL set expiresAt to current Unix timestamp plus SESSION_MAX_DURATION_HOURS (default 2 hours, configurable up to 2 hours maximum per API Gateway WebSocket limits)
2. THE System SHALL enable DynamoDB TTL on the expiresAt attribute for Sessions table
3. WHEN THE session expires via TTL, THE DynamoDB SHALL automatically delete the session record
4. WHEN THE session TTL is set, THE System SHALL also set ttl on all connection records to SESSION_MAX_DURATION_HOURS plus 1 hour for cleanup buffer
5. THE System SHALL support sessions lasting up to SESSION_MAX_DURATION_HOURS or until Speaker disconnects, whichever comes first

### Requirement 7: Speaker Authentication Error Handling

**User Story:** As a Speaker, I want to receive clear error messages when authentication fails, so that I can troubleshoot connection issues

#### Acceptance Criteria

1. WHEN THE Speaker provides an invalid JWT token, THE System SHALL return a 401 Unauthorized response with message "Invalid token"
2. WHEN THE Speaker provides an expired JWT token, THE System SHALL return a 401 Unauthorized response with message "Token expired"
3. WHEN THE Speaker provides a valid token but missing required parameters, THE System SHALL return a 400 Bad Request response with message specifying the missing parameter name
4. WHEN THE Speaker provides an unsupported source language code, THE System SHALL return a 400 Bad Request response with code INVALID_LANGUAGE
5. WHEN THE authentication fails, THE System SHALL log the failure reason with timestamp, IP address, and connection attempt details

### Requirement 8: Listener Join Error Handling

**User Story:** As a Listener, I want to receive clear error messages when joining fails, so that I can understand what went wrong

#### Acceptance Criteria

1. WHEN THE Listener provides a non-existent sessionId, THE System SHALL return an error with code SESSION_NOT_FOUND and HTTP status 404
2. WHEN THE Listener provides a sessionId where isActive=false, THE System SHALL return an error with code SESSION_NOT_FOUND and HTTP status 404
3. WHEN THE Listener provides an unsupported target language code, THE System SHALL return an error with code UNSUPPORTED_LANGUAGE and HTTP status 400
4. WHEN THE Listener provides a malformed sessionId not matching pattern {adjective}-{noun}-{3-digit-number}, THE System SHALL return an error with code INVALID_SESSION_ID and HTTP status 400
5. WHEN THE join fails, THE System SHALL include the sessionId in the error response for debugging purposes

### Requirement 9: Connection State Tracking

**User Story:** As a system administrator, I want connection state to be tracked accurately in real-time, so that the system can make correct processing decisions

#### Acceptance Criteria

1. THE System SHALL store all active connections in the Connections DynamoDB table with connectionId as partition key
2. THE System SHALL maintain a Global Secondary Index named sessionId-targetLanguage-index with sessionId as partition key and targetLanguage as sort key
3. WHEN THE System updates listenerCount, THE System SHALL use atomic ADD operations to prevent race conditions
4. WHEN THE System queries connections by sessionId and targetLanguage, THE System SHALL complete queries within 50ms at p99 percentile
5. WHEN THE connection state changes, THE System SHALL ensure eventual consistency between Sessions and Connections tables

### Requirement 10: Connection Resilience and Timeouts

**User Story:** As a system administrator, I want WebSocket connections to handle network interruptions gracefully, so that temporary issues don't break the user experience

#### Acceptance Criteria

1. WHEN THE WebSocket connection experiences a network interruption, THE System SHALL maintain the connection for up to 10 minutes idle timeout per API Gateway limits
2. WHEN THE connection is idle for more than 10 minutes, THE System SHALL trigger the $disconnect handler
3. WHEN THE connection is restored within the timeout period, THE System SHALL resume normal operation without requiring reconnection
4. THE System SHALL enforce a maximum connection duration of CONNECTION_MAX_DURATION_HOURS (default 2 hours, configurable up to 2 hours maximum) per API Gateway WebSocket hard limit
5. WHEN THE Speaker connection duration reaches CONNECTION_WARNING_MINUTES (default 105 minutes, configurable), THE System SHALL send a connectionWarning message to the Speaker with remaining time
6. WHEN THE maximum duration is reached, THE System SHALL gracefully close the connection and trigger cleanup via $disconnect handler

### Requirement 11: Seamless Connection Refresh for Long Sessions

**User Story:** As a Speaker or Listener, I want to participate in sessions longer than 2 hours without interruption, so that I can complete long broadcasts without reconnection disruption

#### Acceptance Criteria

1. WHEN THE Speaker connection duration reaches CONNECTION_REFRESH_MINUTES (default 100 minutes, configurable), THE System SHALL send a connectionRefreshRequired message to the Speaker with new connection parameters
2. WHEN THE Speaker receives connectionRefreshRequired, THE Speaker client SHALL establish a new WebSocket connection while maintaining the existing connection
3. WHEN THE new Speaker connection is established with action=refreshConnection and existing sessionId, THE System SHALL validate the session exists and Speaker userId matches
4. WHEN THE validation succeeds, THE System SHALL update the session speakerConnectionId to the new connectionId atomically
5. WHEN THE speakerConnectionId is updated, THE System SHALL send a connectionRefreshComplete message to the new connection and allow the old connection to close gracefully
6. WHEN THE Listener connection duration reaches CONNECTION_REFRESH_MINUTES, THE System SHALL send a connectionRefreshRequired message to the Listener
7. WHEN THE Listener receives connectionRefreshRequired, THE Listener client SHALL establish a new WebSocket connection with the same sessionId and targetLanguage
8. WHEN THE new Listener connection is established, THE System SHALL create a new connection record and increment listenerCount, then delete the old connection record and decrement listenerCount atomically
9. THE System SHALL ensure session state persists across connection refreshes with no audio loss or state corruption
10. THE System SHALL support unlimited session duration through periodic connection refresh every CONNECTION_REFRESH_MINUTES
11. WHEN THE System processes Listener connection refresh, THE System SHALL tolerate temporary listenerCount spikes above MAX_LISTENERS_PER_SESSION during the transition period when both old and new connections exist simultaneously

### Requirement 12: Heartbeat Mechanism

**User Story:** As a Speaker or Listener, I want my connection to remain active during periods of silence, so that I don't get disconnected unexpectedly

#### Acceptance Criteria

1. THE System SHALL accept heartbeat messages with action=heartbeat from connected clients
2. WHEN THE System receives a heartbeat message, THE System SHALL respond with a heartbeatAck message within 100ms
3. WHEN THE System does not receive a heartbeat from a client for HEARTBEAT_TIMEOUT_SECONDS (default 90, configurable), THE System SHALL close the connection
4. THE System SHALL expect clients to send heartbeat messages every HEARTBEAT_INTERVAL_SECONDS (default 30, configurable)
5. THE System SHALL limit heartbeat messages to RATE_LIMIT_HEARTBEATS_PER_MIN (default 2, configurable) per minute per connection
6. WHEN THE connection is closed due to heartbeat timeout, THE System SHALL trigger the $disconnect handler for cleanup

### Requirement 13: Rate Limiting for Abuse Prevention

**User Story:** As a system administrator, I want to prevent abuse through configurable rate limiting, so that the system remains available for legitimate users

#### Acceptance Criteria

1. THE System SHALL limit Speaker session creation to RATE_LIMIT_SESSIONS_PER_HOUR (default 50, configurable) sessions per hour per userId
2. THE System SHALL limit Listener join attempts to RATE_LIMIT_LISTENER_JOINS_PER_MIN (default 10, configurable) joins per minute per IP address
3. THE System SHALL limit WebSocket connection attempts to RATE_LIMIT_CONNECTION_ATTEMPTS_PER_MIN (default 20, configurable) per minute per IP address
4. WHEN THE rate limit is exceeded, THE System SHALL return HTTP status 429 Too Many Requests with retryAfter value in seconds
5. THE System SHALL store rate limit counters in DynamoDB RateLimits table with TTL-based expiration
6. WHEN THE rate limit window expires, THE System SHALL reset the counter to allow new requests

### Requirement 14: Maximum Listener Capacity

**User Story:** As a system administrator, I want to limit the maximum number of listeners per session through configuration, so that system performance remains stable

#### Acceptance Criteria

1. THE System SHALL enforce a maximum of MAX_LISTENERS_PER_SESSION (default 500, configurable) listeners per session
2. WHEN THE listenerCount reaches MAX_LISTENERS_PER_SESSION, THE System SHALL reject new listener join attempts
3. WHEN THE capacity limit is reached, THE System SHALL return an error with code SESSION_FULL and HTTP status 503
4. WHEN THE listenerCount drops below MAX_LISTENERS_PER_SESSION, THE System SHALL allow new listeners to join
5. THE System SHALL log capacity limit events with sessionId and timestamp for monitoring

### Requirement 15: Connection Metadata Validation

**User Story:** As a system administrator, I want all connection parameters to be validated, so that invalid data doesn't cause system errors

#### Acceptance Criteria

1. WHEN THE System receives a sourceLanguage parameter, THE System SHALL validate it matches ISO 639-1 format (2 lowercase letters)
2. WHEN THE System receives a targetLanguage parameter, THE System SHALL validate it matches ISO 639-1 format (2 lowercase letters)
3. WHEN THE System receives a qualityTier parameter, THE System SHALL validate it is either "standard" or "premium"
4. WHEN THE System receives a sessionId parameter, THE System SHALL validate it matches pattern {adjective}-{noun}-{3-digit-number}
5. IF THE validation fails for any parameter, THEN THE System SHALL return HTTP status 400 with specific validation error message

### Requirement 16: Idempotent Connection Operations

**User Story:** As a system administrator, I want connection operations to be idempotent, so that retries don't cause duplicate state

#### Acceptance Criteria

1. WHEN THE System receives duplicate $connect requests with same connectionId, THE System SHALL process only the first request
2. WHEN THE System receives duplicate $disconnect requests with same connectionId, THE System SHALL safely handle the duplicate without errors
3. WHEN THE System updates listenerCount, THE System SHALL use conditional updates to prevent race conditions
4. WHEN THE System deletes connection records, THE System SHALL use idempotent delete operations
5. THE System SHALL log duplicate operation attempts for monitoring and debugging

### Requirement 17: Comprehensive Error Logging

**User Story:** As a system administrator, I want comprehensive error logging, so that I can troubleshoot issues effectively

#### Acceptance Criteria

1. WHEN THE System encounters an error, THE System SHALL log the error with severity level (ERROR, WARN, INFO)
2. WHEN THE error is logged, THE System SHALL include correlationId (sessionId or connectionId), errorCode, errorMessage, and timestamp
3. WHEN THE error involves a user action, THE System SHALL include sanitized user context (userId or IP address)
4. WHEN THE error is a 500-level error, THE System SHALL include full stack trace
5. THE System SHALL send error logs to CloudWatch Logs with DATA_RETENTION_HOURS (default 12 hours, configurable) retention period

### Requirement 18: Performance Monitoring Metrics

**User Story:** As a system administrator, I want performance metrics to be tracked, so that I can monitor system health

#### Acceptance Criteria

1. THE System SHALL emit CloudWatch metrics for session creation latency with p50, p95, and p99 percentiles
2. THE System SHALL emit CloudWatch metrics for listener join latency with p50, p95, and p99 percentiles
3. THE System SHALL emit CloudWatch metrics for active session count
4. THE System SHALL emit CloudWatch metrics for total listener count across all sessions
5. THE System SHALL emit CloudWatch metrics for connection error rate by error code

### Requirement 19: Security Compliance

**User Story:** As a security administrator, I want the system to follow security best practices, so that user data is protected

#### Acceptance Criteria

1. THE System SHALL use TLS 1.2 or higher for all WebSocket connections (WSS protocol)
2. THE System SHALL validate JWT token signature using Cognito public keys from JWKS endpoint
3. THE System SHALL not log sensitive data including JWT tokens, full IP addresses, or email addresses
4. THE System SHALL hash connectionId values in logs using SHA-256
5. THE System SHALL not require DynamoDB encryption at rest since no sensitive configuration is stored

### Requirement 20: Data Retention and Cleanup

**User Story:** As a compliance administrator, I want data to be automatically cleaned up with configurable retention, so that we comply with data retention policies

#### Acceptance Criteria

1. THE System SHALL automatically delete session records after SESSION_MAX_DURATION_HOURS plus 1 hour cleanup buffer using DynamoDB TTL
2. THE System SHALL automatically delete connection records after SESSION_MAX_DURATION_HOURS plus 1 hour cleanup buffer using DynamoDB TTL
3. THE System SHALL automatically delete rate limit records after 1 hour using DynamoDB TTL
4. THE System SHALL retain CloudWatch Logs for DATA_RETENTION_HOURS (default 12 hours, configurable) before automatic deletion
5. THE System SHALL not persist any audio data or transcripts beyond processing time

### Requirement 21: Graceful Degradation

**User Story:** As a system administrator, I want the system to degrade gracefully when dependencies fail, so that partial functionality remains available

#### Acceptance Criteria

1. WHEN THE DynamoDB is unavailable, THE System SHALL return HTTP status 503 Service Unavailable
2. WHEN THE Cognito is unavailable, THE System SHALL reject Speaker connections but allow Listener connections to existing sessions
3. WHEN THE rate limiting table is unavailable, THE System SHALL temporarily disable rate limiting and log a warning
4. WHEN THE System encounters transient errors, THE System SHALL retry with exponential backoff up to 3 attempts
5. WHEN THE System cannot recover after retries, THE System SHALL return appropriate error response and log the failure
