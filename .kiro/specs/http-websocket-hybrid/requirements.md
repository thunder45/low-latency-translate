# Requirements Document

## Introduction

This specification addresses the architectural improvement of session management by implementing an HTTP + WebSocket hybrid architecture. The current implementation uses WebSocket for both session creation and real-time communication, which creates architectural mismatches with API Gateway's connection lifecycle. This hybrid approach separates stateless session management (HTTP) from stateful real-time communication (WebSocket), following AWS best practices and improving reliability, scalability, and maintainability.

## Glossary

- **HTTP API**: REST API Gateway for stateless session management operations (CRUD)
- **WebSocket API**: API Gateway WebSocket API for real-time bidirectional audio streaming
- **Session**: A broadcasting session with a unique human-readable ID
- **SessionHttpService**: Frontend service for HTTP-based session management
- **SessionManagementStack**: CDK infrastructure stack for HTTP API resources
- **Connection Handler**: Lambda function handling WebSocket connection lifecycle
- **Session Handler**: Lambda function handling HTTP session CRUD operations
- **DynamoDB Sessions Table**: Database table storing session state
- **JWT Token**: JSON Web Token for authentication (Cognito-issued)
- **Session ID**: Human-readable session identifier (format: adjective-noun-number)

## Requirements

### Requirement 1: HTTP Session Creation

**User Story:** As a speaker, I want to create a session via HTTP API so that session creation is reliable and follows standard REST patterns.

#### Acceptance Criteria

1. WHEN a speaker requests session creation, THE System SHALL accept HTTP POST requests to /sessions endpoint
2. WHEN the request includes valid JWT token, THE System SHALL validate the token using Cognito
3. WHEN the request includes sourceLanguage and qualityTier, THE System SHALL create a session record in DynamoDB
4. WHEN the session is created, THE System SHALL generate a unique human-readable session ID
5. WHEN the session is created, THE System SHALL return the session ID and metadata in JSON format within 2 seconds
6. WHEN the request is invalid, THE System SHALL return appropriate HTTP error codes (400, 401, 500)

### Requirement 2: HTTP Session Retrieval

**User Story:** As a speaker or listener, I want to retrieve session details via HTTP API so that I can verify session state before connecting.

#### Acceptance Criteria

1. WHEN a user requests session details, THE System SHALL accept HTTP GET requests to /sessions/{sessionId} endpoint
2. WHEN the session exists, THE System SHALL return session metadata including status, language, and listener count
3. WHEN the session does not exist, THE System SHALL return HTTP 404 with descriptive error message
4. WHEN the request completes, THE System SHALL respond within 500 milliseconds


### Requirement 3: HTTP Session Update

**User Story:** As a speaker, I want to update session state via HTTP API so that I can pause, resume, or modify session settings without maintaining a WebSocket connection.

#### Acceptance Criteria

1. WHEN a speaker requests session update, THE System SHALL accept HTTP PATCH requests to /sessions/{sessionId} endpoint
2. WHEN the request includes valid JWT token, THE System SHALL verify the speaker owns the session
3. WHEN the request includes status update, THE System SHALL update the session status (active, paused, ended)
4. WHEN the request includes settings update, THE System SHALL update session settings (sourceLanguage, qualityTier)
5. WHEN the update succeeds, THE System SHALL return updated session metadata within 1 second
6. WHEN the speaker does not own the session, THE System SHALL return HTTP 403 Forbidden

### Requirement 4: HTTP Session Deletion

**User Story:** As a speaker, I want to end a session via HTTP API so that I can cleanly terminate the session and release resources.

#### Acceptance Criteria

1. WHEN a speaker requests session deletion, THE System SHALL accept HTTP DELETE requests to /sessions/{sessionId} endpoint
2. WHEN the request includes valid JWT token, THE System SHALL verify the speaker owns the session
3. WHEN the deletion is authorized, THE System SHALL mark the session as ended in DynamoDB
4. WHEN the deletion is authorized, THE System SHALL disconnect all active WebSocket connections for that session
5. WHEN the deletion completes, THE System SHALL return HTTP 204 No Content within 1 second
6. WHEN the speaker does not own the session, THE System SHALL return HTTP 403 Forbidden

### Requirement 5: WebSocket Connection with Existing Session

**User Story:** As a speaker, I want to connect WebSocket with an existing session ID so that I can stream audio after creating the session via HTTP.

#### Acceptance Criteria

1. WHEN a speaker connects to WebSocket, THE System SHALL require sessionId in the connection query parameters
2. WHEN the sessionId is provided, THE System SHALL verify the session exists in DynamoDB
3. WHEN the session exists, THE System SHALL verify the session is in active status
4. WHEN the session is valid, THE System SHALL establish the WebSocket connection and store the connection ID
5. WHEN the session does not exist, THE System SHALL reject the connection with close code 1008 (Policy Violation)
6. WHEN the session is ended, THE System SHALL reject the connection with close code 1008 (Policy Violation)

### Requirement 6: WebSocket Audio Streaming

**User Story:** As a speaker, I want to stream audio over WebSocket so that listeners can receive real-time translated audio.

#### Acceptance Criteria

1. WHEN a speaker sends audio data, THE System SHALL accept binary WebSocket messages
2. WHEN audio data is received, THE System SHALL validate the session is active
3. WHEN the session is active, THE System SHALL forward audio data to the transcription pipeline
4. WHEN the session is paused, THE System SHALL buffer audio data for up to 30 seconds
5. WHEN the session is ended, THE System SHALL reject audio data with error message
6. WHEN audio data exceeds 1MB per message, THE System SHALL reject the message with error


### Requirement 7: Frontend HTTP Service Integration

**User Story:** As a frontend developer, I want a SessionHttpService that handles all HTTP session operations so that I can manage sessions independently of WebSocket connections.

#### Acceptance Criteria

1. WHEN SessionHttpService is initialized, THE System SHALL configure the HTTP API base URL from environment variables
2. WHEN createSession is called, THE System SHALL send HTTP POST request with authentication headers
3. WHEN getSession is called, THE System SHALL send HTTP GET request and return session metadata
4. WHEN updateSession is called, THE System SHALL send HTTP PATCH request with updated fields
5. WHEN deleteSession is called, THE System SHALL send HTTP DELETE request
6. WHEN any HTTP request fails, THE System SHALL throw descriptive errors with HTTP status codes
7. WHEN authentication token is expired, THE System SHALL trigger token refresh before retrying

### Requirement 8: Frontend WebSocket Service Separation

**User Story:** As a frontend developer, I want WebSocket connections to be used only for real-time audio streaming so that connection management is simpler and more reliable.

#### Acceptance Criteria

1. WHEN WebSocketClient connects, THE System SHALL require an existing sessionId parameter
2. WHEN WebSocketClient connects, THE System SHALL not create a new session
3. WHEN WebSocketClient sends messages, THE System SHALL only send audio data and control messages
4. WHEN WebSocketClient receives messages, THE System SHALL only handle real-time audio and status updates
5. WHEN WebSocketClient disconnects, THE System SHALL not delete the session (session persists)
6. WHEN WebSocketClient reconnects, THE System SHALL use the same sessionId

### Requirement 9: Backward Compatibility

**User Story:** As a developer, I want the new architecture to be backward compatible so that existing functionality continues to work during migration.

#### Acceptance Criteria

1. WHEN the HTTP API is deployed, THE System SHALL maintain the existing WebSocket session creation endpoint
2. WHEN a client uses the old WebSocket session creation, THE System SHALL continue to work as before
3. WHEN a client uses the new HTTP session creation, THE System SHALL work with the new architecture
4. WHEN both APIs are available, THE System SHALL support both patterns simultaneously
5. WHEN the migration is complete, THE System SHALL allow deprecation of the old WebSocket session creation

### Requirement 10: Error Handling and Resilience

**User Story:** As a user, I want clear error messages and automatic retries so that temporary failures don't disrupt my session.

#### Acceptance Criteria

1. WHEN an HTTP request fails with 5xx error, THE System SHALL retry up to 3 times with exponential backoff
2. WHEN an HTTP request fails with 4xx error, THE System SHALL not retry and return error immediately
3. WHEN a WebSocket connection fails, THE System SHALL attempt reconnection with existing sessionId
4. WHEN session creation fails, THE System SHALL provide user-friendly error messages
5. WHEN network connectivity is lost, THE System SHALL queue operations and retry when connectivity returns
6. WHEN errors occur, THE System SHALL log structured error information for debugging


### Requirement 11: Performance Requirements

**User Story:** As a user, I want fast session operations so that I can start broadcasting quickly.

#### Acceptance Criteria

1. WHEN a session is created via HTTP, THE System SHALL complete within 2 seconds (p95)
2. WHEN a session is retrieved via HTTP, THE System SHALL complete within 500 milliseconds (p95)
3. WHEN a session is updated via HTTP, THE System SHALL complete within 1 second (p95)
4. WHEN a WebSocket connection is established, THE System SHALL complete within 1 second (p95)
5. WHEN audio data is sent, THE System SHALL process with latency under 100 milliseconds (p95)

### Requirement 12: Security Requirements

**User Story:** As a security engineer, I want all session operations to be authenticated and authorized so that only authorized users can manage sessions.

#### Acceptance Criteria

1. WHEN any HTTP request is received, THE System SHALL validate the JWT token signature
2. WHEN any HTTP request is received, THE System SHALL verify the token is not expired
3. WHEN a session update is requested, THE System SHALL verify the user owns the session
4. WHEN a session deletion is requested, THE System SHALL verify the user owns the session
5. WHEN a WebSocket connection is established, THE System SHALL validate the JWT token via Lambda authorizer
6. WHEN authentication fails, THE System SHALL return HTTP 401 Unauthorized with no sensitive information

### Requirement 13: Infrastructure Requirements

**User Story:** As a DevOps engineer, I want infrastructure defined as code so that I can deploy and manage the hybrid architecture reliably.

#### Acceptance Criteria

1. WHEN infrastructure is deployed, THE System SHALL create HTTP API Gateway with REST API
2. WHEN infrastructure is deployed, THE System SHALL create Lambda functions for session CRUD operations
3. WHEN infrastructure is deployed, THE System SHALL configure IAM roles with least privilege access
4. WHEN infrastructure is deployed, THE System SHALL configure CORS for frontend access
5. WHEN infrastructure is deployed, THE System SHALL maintain existing WebSocket API infrastructure
6. WHEN infrastructure is deployed, THE System SHALL use the same DynamoDB table for both APIs

### Requirement 14: Monitoring and Observability

**User Story:** As a DevOps engineer, I want comprehensive monitoring so that I can track system health and debug issues.

#### Acceptance Criteria

1. WHEN HTTP requests are processed, THE System SHALL log request/response with correlation IDs
2. WHEN errors occur, THE System SHALL log structured error information with context
3. WHEN sessions are created, THE System SHALL emit CloudWatch metrics for session creation rate
4. WHEN sessions are deleted, THE System SHALL emit CloudWatch metrics for session duration
5. WHEN API latency exceeds thresholds, THE System SHALL emit CloudWatch alarms
6. WHEN error rates exceed 5 percent, THE System SHALL emit CloudWatch alarms


## Requirements Priority Matrix

| Requirement | Priority | Blocks Production? | Estimated Effort |
|-------------|----------|-------------------|------------------|
| Req 1: HTTP Session Creation | P0 | Yes | 3-4 hours |
| Req 2: HTTP Session Retrieval | P0 | Yes | 1-2 hours |
| Req 3: HTTP Session Update | P1 | No | 2-3 hours |
| Req 4: HTTP Session Deletion | P1 | No | 2-3 hours |
| Req 5: WebSocket with Existing Session | P0 | Yes | 2-3 hours |
| Req 6: WebSocket Audio Streaming | P0 | Yes | 1-2 hours |
| Req 7: Frontend HTTP Service | P0 | Yes | 3-4 hours |
| Req 8: Frontend WebSocket Separation | P0 | Yes | 2-3 hours |
| Req 9: Backward Compatibility | P1 | No | 2-3 hours |
| Req 10: Error Handling | P0 | Yes | 2-3 hours |
| Req 11: Performance Requirements | P0 | Yes | Validation only |
| Req 12: Security Requirements | P0 | Yes | 1-2 hours |
| Req 13: Infrastructure | P0 | Yes | 3-4 hours |
| Req 14: Monitoring | P1 | No | 2-3 hours |

**Total Estimated Effort**: 26-38 hours

**Priority Definitions**:
- **P0**: Must complete for hybrid architecture to function
- **P1**: Should complete for production readiness, can be addressed post-launch if needed

## Success Metrics

After implementation, the hybrid architecture SHALL meet these criteria:

**Functional**:
- [ ] Sessions can be created via HTTP POST /sessions
- [ ] Sessions can be retrieved via HTTP GET /sessions/{sessionId}
- [ ] Sessions can be updated via HTTP PATCH /sessions/{sessionId}
- [ ] Sessions can be deleted via HTTP DELETE /sessions/{sessionId}
- [ ] WebSocket connections require existing sessionId
- [ ] Audio streaming works over WebSocket
- [ ] Old WebSocket session creation still works (backward compatibility)

**Performance**:
- [ ] HTTP session creation: <2 seconds (p95)
- [ ] HTTP session retrieval: <500ms (p95)
- [ ] HTTP session update: <1 second (p95)
- [ ] WebSocket connection: <1 second (p95)
- [ ] Audio streaming latency: <100ms (p95)

**Security**:
- [ ] All HTTP endpoints require JWT authentication
- [ ] Session ownership verified for update/delete operations
- [ ] WebSocket connections validated via Lambda authorizer
- [ ] No sensitive information in error messages

**Reliability**:
- [ ] HTTP requests retry on 5xx errors
- [ ] WebSocket reconnects with existing sessionId
- [ ] Sessions persist across WebSocket disconnections
- [ ] Error handling provides clear user feedback

**Observability**:
- [ ] All operations logged with correlation IDs
- [ ] CloudWatch metrics for session operations
- [ ] CloudWatch alarms for latency and errors
- [ ] Structured logging for debugging

## Risk Assessment

| Requirement | Risk if Not Implemented | Mitigation Strategy |
|-------------|------------------------|---------------------|
| Req 1: HTTP Session Creation | **HIGH** - Cannot create sessions reliably | MUST complete before production |
| Req 5: WebSocket with Existing Session | **HIGH** - Audio streaming won't work | MUST complete before production |
| Req 7: Frontend HTTP Service | **HIGH** - Frontend cannot use new architecture | MUST complete before production |
| Req 10: Error Handling | **MEDIUM** - Poor user experience on failures | Should complete before production |
| Req 9: Backward Compatibility | **MEDIUM** - Breaking change for existing clients | Can phase migration gradually |
| Req 3: HTTP Session Update | **LOW** - Can use WebSocket for updates temporarily | Can defer if time-constrained |
| Req 4: HTTP Session Deletion | **LOW** - Sessions can expire via TTL | Can defer if time-constrained |
| Req 14: Monitoring | **LOW** - Harder to debug production issues | Can address post-launch |

## Benefits of Hybrid Architecture

### Separation of Concerns
- **HTTP**: Stateless session management (CRUD operations)
- **WebSocket**: Stateful real-time communication (audio streaming)

### Improved Reliability
- Sessions persist across WebSocket disconnections
- No dependency on WebSocket for session creation
- Clearer error handling and retry logic

### Better Scalability
- HTTP API can scale independently of WebSocket API
- Session state managed in DynamoDB, not connection state
- Easier to implement caching and load balancing

### AWS Best Practices
- REST API for CRUD operations (standard pattern)
- WebSocket for real-time bidirectional communication
- Proper separation of stateless and stateful operations

### Simplified Development
- Frontend developers can test session management without WebSocket
- Backend developers can test session logic independently
- Clearer API contracts and documentation

## Migration Strategy

### Phase 1: Add HTTP API (Parallel Deployment)
1. Deploy HTTP API alongside existing WebSocket API
2. Both APIs work simultaneously
3. No breaking changes to existing clients

### Phase 2: Update Frontend (Gradual Migration)
1. Update SessionCreationOrchestrator to use HTTP API
2. Keep WebSocket for audio streaming only
3. Test thoroughly in dev/staging

### Phase 3: Deprecation (Optional)
1. Monitor usage of old WebSocket session creation
2. Communicate deprecation timeline to clients
3. Remove old WebSocket session creation endpoint

### Rollback Plan
- HTTP API can be disabled without affecting WebSocket audio streaming
- Existing WebSocket session creation remains functional
- No data migration required (same DynamoDB table)
