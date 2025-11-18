# Implementation Plan

Convert the HTTP + WebSocket hybrid architecture design into actionable implementation tasks. Each task builds incrementally toward a complete separation of session management (HTTP) from real-time communication (WebSocket). Tasks are organized by priority (P0 must complete for hybrid architecture to function).

## Recommended Execution Sequence

For optimal implementation flow, consider executing tasks in these phases:

### Phase 1: Backend HTTP API (8-10 hours)
- Task 1: Create HTTP API infrastructure (CDK)
- Task 2: Implement Session Handler Lambda
- Task 3: Add HTTP session CRUD operations
- Task 4: Configure JWT authorizer

### Phase 2: Backend WebSocket Updates (6-8 hours)
- Task 5: Update Connection Handler for existing sessions
- Task 6: Add session validation on WebSocket connect
- Task 7: Update audio streaming handler
- Task 8: Implement session disconnection on delete (moved from Task 22)

### Phase 3: Frontend HTTP Service (6-8 hours)
- Task 9: Create SessionHttpService
- Task 10: Add error handling and retry logic
- Task 11: Integrate with authentication

### Phase 4: Frontend Integration (4-6 hours)
- Task 12: Update SessionCreationOrchestrator
- Task 13: Update SpeakerService
- Task 14: Add feature flag for gradual rollout

### Phase 5: Testing (6-8 hours)
- Task 15: Write unit tests for SessionHttpService
- Task 16: Write unit tests for Session Handler Lambda
- Task 17: Write integration tests
- Task 18: Write performance tests

### Phase 6: Deployment & Monitoring (4-6 hours)
- Task 19: Deploy to dev environment
- Task 20: Configure CloudWatch monitoring
- Task 21: Deploy to staging and validate
- Task 22: Create API documentation
- Task 23: Update project documentation

**Total Estimated Effort**: 44-58 hours (26 tasks, all required)

**Benefits of This Sequence**:
- Backend infrastructure first (enables frontend development)
- Related changes grouped together
- Tests written after implementation
- Clear phase boundaries for progress tracking
- Gradual rollout with feature flags

## Task List

- [x] 1. Create HTTP API infrastructure with CDK
  - Create new CDK stack `HttpApiStack` in session-management/infrastructure
  - Define HTTP API Gateway with REST API
  - Configure CORS for frontend access
  - Add JWT authorizer using Cognito User Pool
  - Output API endpoint URL
  - _Requirements: 13.1, 13.2, 13.4_
  - _Priority: P0_
  - _Effort: 2-3 hours_

- [x] 2. Implement Session Handler Lambda function
  - Create lambda/http_session_handler directory
  - Implement lambda_handler with HTTP method routing
  - Add request parsing and validation
  - Add error response helper function
  - Configure environment variables (SESSIONS_TABLE_NAME, USER_POOL_ID)
  - _Requirements: 13.2, 13.3_
  - _Priority: P0_
  - _Effort: 2-3 hours_

- [x] 3. Add HTTP session CRUD operations
- [x] 3.1 Implement create_session endpoint
  - Parse POST /sessions request body
  - Validate sourceLanguage and qualityTier
  - Generate unique session ID
  - Create session record in DynamoDB
  - Return 201 Created with session metadata
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 3.2 Implement get_session endpoint
  - Parse GET /sessions/{sessionId} request
  - Retrieve session from DynamoDB
  - Return 200 OK with session metadata
  - Return 404 Not Found if session doesn't exist
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 3.3 Implement update_session endpoint
  - Parse PATCH /sessions/{sessionId} request
  - Verify session ownership (speakerId matches JWT user)
  - Validate update fields (status, sourceLanguage, qualityTier)
  - Update session in DynamoDB
  - Return 200 OK with updated metadata
  - Return 403 Forbidden if not owner
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 3.4 Implement delete_session endpoint
  - Parse DELETE /sessions/{sessionId} request
  - Verify session ownership
  - Mark session as ended in DynamoDB
  - Return 204 No Content
  - Return 403 Forbidden if not owner
  - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6_

- [x] 3.5 Implement health check endpoint
  - Add GET /health endpoint (no authentication required)
  - Check DynamoDB connectivity with test query
  - Return service status and version
  - Return 200 OK if healthy, 503 Service Unavailable if unhealthy
  - Include response time in health check
  - _Requirements: 14.1_
  - Mark session as ended in DynamoDB
  - Return 204 No Content
  - Return 403 Forbidden if not owner
  - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6_
  - _Priority: P0 (3.1, 3.2), P1 (3.3, 3.4)_
  - _Effort: 4-5 hours total_


- [x] 4. Configure JWT authorizer for HTTP API
  - Add HttpJwtAuthorizer to CDK stack
  - Configure Cognito User Pool as identity source
  - Set Authorization header as identity source
  - Apply authorizer to POST, PATCH, DELETE routes
  - Leave GET route public (listeners need access)
  - _Requirements: 12.1, 12.2, 12.6_
  - _Priority: P0_
  - _Effort: 1 hour_

- [ ] 5. Update Connection Handler for existing sessions
  - Modify handle_connect to require sessionId query parameter
  - Add session existence validation
  - Add session status validation (must be 'active')
  - Store sessionId reference in connection record
  - Return 400 if sessionId missing
  - Return 404 if session not found
  - Return 403 if session not active
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_
  - _Priority: P0_
  - _Effort: 2-3 hours_

- [ ] 6. Add session validation on WebSocket connect
  - Query DynamoDB for session by sessionId
  - Verify session exists
  - Verify session status is 'active'
  - Log connection with session context
  - Reject connection with appropriate close code if invalid
  - _Requirements: 5.2, 5.3, 5.5, 5.6_
  - _Priority: P0_
  - _Effort: 1-2 hours_

- [ ] 7. Update audio streaming handler
  - Verify session is active before processing audio
  - Add session status check in sendAudio handler
  - Buffer audio if session is paused (up to 30 seconds)
  - Reject audio if session is ended
  - Validate message size (<1MB)
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_
  - _Priority: P0_
  - _Effort: 1-2 hours_

- [ ] 8. Implement session disconnection on delete (MOVED FROM TASK 22)
  - When session is deleted via HTTP, disconnect all WebSocket connections
  - Query connections table by sessionId using GSI
  - Send disconnect message to each active connection
  - Close connections gracefully with close code 1000 (Normal Closure)
  - Log disconnection events with session context
  - Handle errors if connections already closed
  - _Requirements: 4.4_
  - _Priority: P0_
  - _Effort: 2-3 hours_
  - _Note: Moved to Phase 2 to prevent resource leaks_

- [ ] 9. Create SessionHttpService frontend class
  - Create frontend-client-apps/shared/services/SessionHttpService.ts
  - Implement constructor with apiBaseUrl and authService
  - Define SessionConfig, SessionMetadata, SessionUpdateRequest interfaces
  - Add private getValidToken() method with token refresh
  - Add private handleHttpError() method with status code mapping
  - _Requirements: 7.1, 7.6, 7.7_
  - _Priority: P0_
  - _Effort: 2-3 hours_

- [ ] 9. Implement SessionHttpService CRUD methods
- [ ] 9.1 Implement createSession method
  - Accept SessionConfig parameter
  - Get valid JWT token
  - Send POST request to /sessions
  - Include Authorization header
  - Parse and return SessionMetadata
  - Throw descriptive error on failure
  - _Requirements: 7.2_

- [ ] 9.2 Implement getSession method
  - Accept sessionId parameter
  - Send GET request to /sessions/{sessionId}
  - No authentication required (public endpoint)
  - Parse and return SessionMetadata
  - Throw descriptive error on failure
  - _Requirements: 7.3_

- [ ] 9.3 Implement updateSession method
  - Accept sessionId and SessionUpdateRequest parameters
  - Get valid JWT token
  - Send PATCH request to /sessions/{sessionId}
  - Include Authorization header
  - Parse and return updated SessionMetadata
  - Throw descriptive error on failure
  - _Requirements: 7.4_

- [ ] 9.4 Implement deleteSession method
  - Accept sessionId parameter
  - Get valid JWT token
  - Send DELETE request to /sessions/{sessionId}
  - Include Authorization header
  - Return void on success
  - Throw descriptive error on failure
  - _Requirements: 7.5_
  - _Priority: P0 (9.1, 9.2), P1 (9.3, 9.4)_
  - _Effort: 2-3 hours total_

- [ ] 10. Add error handling and retry logic
  - Implement exponential backoff for 5xx errors (3 retries)
  - No retry for 4xx errors (immediate failure)
  - Add timeout handling (10 second timeout)
  - Add network error detection and retry
  - Map HTTP status codes to user-friendly messages
  - Log errors with correlation IDs
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_
  - _Priority: P0_
  - _Effort: 2-3 hours_


- [ ] 11. Update SessionCreationOrchestrator to use HTTP
  - Import SessionHttpService
  - Replace WebSocket session creation with HTTP createSession
  - Keep WebSocket connection for audio streaming
  - Pass sessionId to WebSocket connect
  - Update error handling for HTTP errors
  - Maintain backward compatibility with feature flag
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 9.1, 9.2, 9.3, 9.4_
  - _Priority: P0_
  - _Effort: 2-3 hours_

- [ ] 12. Update SpeakerService for HTTP sessions
  - Remove WebSocket session creation logic
  - Accept sessionId from SessionCreationOrchestrator
  - Initialize with existing sessionId
  - Update UI state management
  - Remove connection requirement check (already done)
  - _Requirements: 8.5, 8.6_
  - _Priority: P0_
  - _Effort: 1-2 hours_

- [ ] 13. Add feature flag for gradual rollout
  - Add VITE_USE_HTTP_SESSION_CREATION environment variable
  - Create feature flag check in SessionCreationOrchestrator
  - Support both HTTP and WebSocket session creation
  - Default to WebSocket (false) for backward compatibility
  - Add logging to track which method is used
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  - _Priority: P1_
  - _Effort: 1 hour_

- [ ] 14. Write unit tests for SessionHttpService
- [ ] 14.1 Test createSession with valid config
  - Mock fetch API
  - Verify POST request to /sessions
  - Verify Authorization header included
  - Verify request body contains config
  - Verify response parsed correctly
  - _Requirements: 7.2_

- [ ] 14.2 Test createSession with invalid config
  - Test missing sourceLanguage
  - Test invalid qualityTier
  - Verify 400 error thrown
  - Verify error message descriptive
  - _Requirements: 7.6_

- [ ] 14.3 Test getSession with existing session
  - Mock fetch API
  - Verify GET request to /sessions/{sessionId}
  - Verify no Authorization header (public)
  - Verify response parsed correctly
  - _Requirements: 7.3_

- [ ] 14.4 Test getSession with non-existent session
  - Mock 404 response
  - Verify error thrown
  - Verify error message includes "not found"
  - _Requirements: 7.6_

- [ ] 14.5 Test updateSession with ownership
  - Mock fetch API
  - Verify PATCH request to /sessions/{sessionId}
  - Verify Authorization header included
  - Verify request body contains updates
  - Verify response parsed correctly
  - _Requirements: 7.4_

- [ ] 14.6 Test updateSession without ownership
  - Mock 403 response
  - Verify error thrown
  - Verify error message includes "not authorized"
  - _Requirements: 7.6_

- [ ] 14.7 Test deleteSession with ownership
  - Mock fetch API
  - Verify DELETE request to /sessions/{sessionId}
  - Verify Authorization header included
  - Verify void return on success
  - _Requirements: 7.5_

- [ ] 14.8 Test token refresh before requests
  - Mock expired token
  - Verify refreshTokens called
  - Verify new token used in request
  - _Requirements: 7.7_

- [ ] 14.9 Test error handling for all status codes
  - Test 400, 401, 403, 404, 500, 503 responses
  - Verify appropriate errors thrown
  - Verify error messages user-friendly
  - _Requirements: 7.6_

- [ ] 14.10 Test retry logic for 5xx errors
  - Mock 500 response, then success
  - Verify 3 retry attempts
  - Verify exponential backoff
  - _Requirements: 10.1_
  - _Priority: P0_
  - _Effort: 4-5 hours total_


- [ ] 15. Write unit tests for Session Handler Lambda
- [ ] 15.1 Test create_session with valid input
  - Mock DynamoDB put_item
  - Verify session ID generated
  - Verify session record created
  - Verify 201 response returned
  - Verify response contains session metadata
  - _Requirements: 1.3, 1.4, 1.5_

- [ ] 15.2 Test create_session with invalid language
  - Test invalid language code
  - Verify 400 response returned
  - Verify error message descriptive
  - _Requirements: 1.6_

- [ ] 15.3 Test create_session with missing fields
  - Test missing sourceLanguage
  - Verify 400 response returned
  - _Requirements: 1.6_

- [ ] 15.4 Test get_session with existing session
  - Mock DynamoDB get_item
  - Verify session retrieved
  - Verify 200 response returned
  - _Requirements: 2.2_

- [ ] 15.5 Test get_session with non-existent session
  - Mock DynamoDB get_item returning None
  - Verify 404 response returned
  - _Requirements: 2.3_

- [ ] 15.6 Test update_session with ownership
  - Mock DynamoDB get_item and update_item
  - Verify ownership checked
  - Verify session updated
  - Verify 200 response returned
  - _Requirements: 3.2, 3.3, 3.4, 3.5_

- [ ] 15.7 Test update_session without ownership
  - Mock session with different speakerId
  - Verify 403 response returned
  - _Requirements: 3.6_

- [ ] 15.8 Test delete_session with ownership
  - Mock DynamoDB get_item and update_item
  - Verify ownership checked
  - Verify session marked as ended
  - Verify 204 response returned
  - _Requirements: 4.2, 4.3, 4.5_

- [ ] 15.9 Test delete_session without ownership
  - Mock session with different speakerId
  - Verify 403 response returned
  - _Requirements: 4.6_

- [ ] 15.10 Test DynamoDB error handling
  - Mock ClientError from DynamoDB
  - Verify 500 response returned
  - Verify error logged
  - _Requirements: 10.6_
  - _Priority: P0_
  - _Effort: 4-5 hours total_

- [ ] 16. Write integration tests for HTTP + WebSocket
- [ ] 16.1 Test end-to-end session creation and connection
  - Create session via HTTP POST
  - Verify session created in DynamoDB
  - Connect WebSocket with sessionId
  - Verify connection established
  - Send audio data
  - Verify audio processed
  - _Requirements: 1.1-1.5, 5.1-5.4, 6.1-6.3_

- [ ] 16.2 Test WebSocket connection with non-existent session
  - Attempt WebSocket connection with invalid sessionId
  - Verify connection rejected with 404
  - _Requirements: 5.5_

- [ ] 16.3 Test WebSocket connection with ended session
  - Create session via HTTP
  - Delete session via HTTP
  - Attempt WebSocket connection
  - Verify connection rejected with 403
  - _Requirements: 5.6_

- [ ] 16.4 Test session update while WebSocket connected
  - Create session and connect WebSocket
  - Update session status to paused via HTTP
  - Send audio data
  - Verify audio buffered (not processed immediately)
  - _Requirements: 3.1-3.5, 6.4_

- [ ] 16.5 Test JWT authentication and authorization
  - Test HTTP requests without token (401)
  - Test HTTP requests with expired token (401)
  - Test HTTP requests with valid token (200/201)
  - Test update/delete with wrong user (403)
  - _Requirements: 12.1, 12.2, 12.6_
  - _Priority: P0_
  - _Effort: 3-4 hours total_

- [ ] 17. Write performance tests
- [ ] 17.1 Test HTTP session creation latency
  - Create 100 sessions concurrently
  - Measure p50, p95, p99 latency
  - Verify p95 <2 seconds
  - _Requirements: 11.1_

- [ ] 17.2 Test HTTP session retrieval latency
  - Retrieve 1000 sessions concurrently
  - Measure p50, p95, p99 latency
  - Verify p95 <500 milliseconds
  - _Requirements: 11.2_

- [ ] 17.3 Test HTTP session update latency
  - Update 100 sessions concurrently
  - Measure p50, p95, p99 latency
  - Verify p95 <1 second
  - _Requirements: 11.3_

- [ ] 17.4 Test WebSocket connection latency
  - Connect 100 WebSockets concurrently
  - Measure p50, p95, p99 latency
  - Verify p95 <1 second
  - _Requirements: 11.4_

- [ ] 17.5 Test audio streaming latency
  - Send audio data over WebSocket
  - Measure processing latency
  - Verify p95 <100 milliseconds
  - _Requirements: 11.5_
  - _Priority: P0_
  - _Effort: 2-3 hours total_


- [ ] 18. Deploy HTTP API to dev environment
  - Update session-management/infrastructure/app.py to include HttpApiStack
  - Configure environment variables for dev
  - Deploy CDK stack to dev
  - Verify HTTP API endpoint accessible
  - Verify JWT authorizer working
  - Test session CRUD operations manually
  - _Requirements: 13.1-13.6_
  - _Priority: P0_
  - _Effort: 1-2 hours_

- [ ] 19. Configure CloudWatch monitoring
- [ ] 19.1 Add CloudWatch metrics
  - Add SessionCreationCount metric
  - Add SessionCreationDuration metric
  - Add SessionRetrievalDuration metric
  - Add SessionUpdateDuration metric
  - Add SessionDeletionCount metric
  - Add WebSocketConnectionCount metric
  - Add WebSocketConnectionDuration metric
  - Configure dimensions (Environment, Region, SourceLanguage)
  - _Requirements: 14.3_

- [ ] 19.2 Create CloudWatch dashboard
  - Create dashboard for HTTP API metrics
  - Add widgets for latency (p50, p95, p99)
  - Add widgets for error rates
  - Add widgets for throughput
  - Add widgets for WebSocket connections
  - _Requirements: 14.3_

- [ ] 19.3 Configure CloudWatch alarms
  - Alarm: HTTP API error rate >5% (critical)
  - Alarm: HTTP API latency p95 >2s (critical)
  - Alarm: WebSocket connection failure >5% (critical)
  - Alarm: Lambda function errors >10 (critical)
  - Alarm: HTTP API latency p95 >1s (warning)
  - Alarm: Session creation rate spike (warning)
  - _Requirements: 14.5_
  - _Priority: P1_
  - _Effort: 2-3 hours total_

- [ ] 20. Deploy to staging and validate
  - Deploy HTTP API to staging environment
  - Run all integration tests in staging
  - Run performance tests in staging
  - Monitor for 24 hours
  - Verify no errors in logs
  - Verify metrics look healthy
  - Verify performance targets met
  - _Requirements: 11.1-11.5_
  - _Priority: P0_
  - _Effort: 2-3 hours (plus 24-hour monitoring)_

- [ ] 21. Deploy to staging and validate
  - Deploy HTTP API to staging environment
  - Run all integration tests in staging
  - Run performance tests in staging
  - Monitor for 24 hours
  - Verify no errors in logs
  - Verify metrics look healthy
  - Verify performance targets met
  - _Requirements: 11.1-11.5_
  - _Priority: P0_
  - _Effort: 2-3 hours (plus 24-hour monitoring)_

- [ ] 22. Create OpenAPI/Swagger documentation
  - Create openapi.yaml in session-management/docs/
  - Document all HTTP endpoints (POST, GET, PATCH, DELETE /sessions)
  - Include request/response schemas with examples
  - Document authentication requirements (JWT Bearer token)
  - Document error responses (400, 401, 403, 404, 500)
  - Add health check endpoint documentation
  - Generate interactive API docs (Swagger UI or similar)
  - _Requirements: 1.1-1.6, 2.1-2.4, 3.1-3.6, 4.1-4.6_
  - _Priority: P1_
  - _Effort: 2-3 hours_

- [ ] 23. Update project documentation
  - Update session-management/README.md with HTTP API details
  - Document HTTP API endpoints and request/response formats
  - Update WEBSOCKET_CURRENT_IMPLEMENTATION.md with hybrid architecture
  - Update WEBSOCKET_ARCHITECTURAL_PROPOSAL.md as implemented
  - Create API documentation for HTTP endpoints
  - Document feature flag usage
  - Document migration path for existing clients
  - _Requirements: 9.1-9.5_
  - _Priority: P1_
  - _Effort: 1-2 hours_

- [ ] 24. Add rate limiting for session creation
  - Implement per-user rate limit (e.g., 10 sessions per minute)
  - Use DynamoDB to track creation rate
  - Return 429 Too Many Requests when limit exceeded
  - Add Retry-After header
  - _Requirements: 10.1_
  - _Priority: P1_
  - _Effort: 2-3 hours_

- [ ] 25. Implement session listing endpoint
  - Add GET /sessions endpoint
  - Filter by speakerId (from JWT)
  - Support pagination with limit and nextToken
  - Return list of user's sessions
  - _Priority: P1_
  - _Effort: 2-3 hours_

- [ ] 26. Add session analytics
  - Track session duration
  - Track listener count over time
  - Track audio data volume
  - Emit custom CloudWatch metrics
  - _Priority: P1_
  - _Effort: 2-3 hours_

## Parallel Execution Opportunities

These tasks can be executed in parallel by different developers:

**Parallel Set 1** (Phase 1-2):
- Tasks 1-4: Backend HTTP API (Developer A)
- Tasks 5-7: Backend WebSocket updates (Developer B)

**Parallel Set 2** (Phase 3):
- Tasks 8-10: Frontend HTTP service (Developer A)
- Tasks 11-13: Frontend integration (Developer B)

**Parallel Set 3** (Phase 5):
- Tasks 14: Frontend tests (Developer A)
- Tasks 15: Backend tests (Developer B)
- Tasks 16-17: Integration/performance tests (Developer C)

## Task Execution Tips

### Before Starting
1. Read the design document for implementation details
2. Review current WebSocket implementation
3. Set up dev environment with HTTP API endpoint
4. Create feature branch: `git checkout -b feature/http-websocket-hybrid`

### During Implementation
1. **Incremental Development**: Complete one task at a time
2. **Test as You Go**: Write tests immediately after implementation
3. **Feature Flag**: Use feature flag to test both old and new flows
4. **Logging**: Add comprehensive logging for debugging

### Testing Commands
```bash
# Backend tests
cd session-management
pytest tests/unit/test_http_session_handler.py
pytest tests/integration/test_http_websocket_integration.py

# Frontend tests
cd frontend-client-apps
npm test SessionHttpService.test.ts
npm test SessionCreationOrchestrator.test.ts

# Performance tests
npm run test:performance

# Deploy to dev
cd session-management
make deploy-dev
```

### Validation Checklist
After completing all tasks, verify:
- [ ] All tests passing
- [ ] HTTP API accessible in dev
- [ ] Session CRUD operations work
- [ ] WebSocket connects with sessionId
- [ ] Audio streaming works
- [ ] Performance targets met
- [ ] Monitoring configured
- [ ] Documentation updated

## Critical Path Analysis

**Minimum time to complete** (with parallelization):
- Week 1: Phase 1-2 (Backend) - 14-18 hours (includes session disconnection)
- Week 2: Phase 3-4 (Frontend) - 10-14 hours
- Week 3: Phase 5 (Testing) - 6-8 hours
- Week 4: Phase 6 (Deployment & Docs) - 5-8 hours (includes API docs)
- Week 5: Additional features (Tasks 24-26) - 8-12 hours

**Total**: 4-5 weeks with parallelization, or 6-7 weeks single developer

## Success Criteria

Implementation is complete when:
- ✅ All P0 tasks completed
- ✅ HTTP API deployed to staging
- ✅ All tests passing (unit, integration, performance)
- ✅ Performance targets met (HTTP <2s, WebSocket <1s, audio <100ms)
- ✅ Feature flag working (both old and new flows)
- ✅ Monitoring configured and tested
- ✅ Documentation updated
- ✅ Zero critical bugs in staging
- ✅ 24-hour monitoring period successful

## Rollback Plan

If issues occur:
1. Disable feature flag (revert to WebSocket session creation)
2. HTTP API can remain deployed (no impact if not used)
3. No data migration needed (same DynamoDB table)
4. WebSocket audio streaming unaffected

## Post-Implementation

After successful deployment:
1. Monitor HTTP API usage and performance
2. Gradually increase feature flag percentage (10% → 50% → 100%)
3. Collect feedback from users
4. Optimize based on metrics
5. Consider deprecating old WebSocket session creation (Month 3+)
