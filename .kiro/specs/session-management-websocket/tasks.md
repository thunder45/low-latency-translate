# Implementation Plan

- [x] 1. Set up project structure and core infrastructure
  - Create directory structure for Lambda functions, shared libraries, and infrastructure code
  - Set up AWS CDK or CloudFormation project for infrastructure as code
  - Configure environment-specific parameter files (dev, staging, prod)
  - _Requirements: All requirements depend on proper project structure_

- [x] 2. Implement DynamoDB tables and data access layer
- [x] 2.1 Create DynamoDB table definitions
  - Define Sessions table with sessionId primary key and TTL configuration
  - Define Connections table with connectionId primary key and GSI for sessionId-targetLanguage
  - Define RateLimits table with identifier primary key and TTL configuration
  - Configure on-demand capacity mode for all tables
  - _Requirements: 9, 20_

- [x] 2.2 Implement data access layer
  - Create Python module for DynamoDB operations with boto3
  - Implement atomic counter operations for listenerCount (ADD operation)
  - Implement conditional updates for race condition prevention
  - Implement batch operations for connection cleanup
  - Add error handling with retry logic for transient failures
  - _Requirements: 9, 16_

- [x] 2.3 Write unit tests for data access layer
  - Test atomic counter operations with concurrent updates
  - Test conditional update race condition handling
  - Test batch operation error handling
  - Test TTL attribute setting
  - _Requirements: 9, 16_

- [x] 3. Implement Session ID generation
- [x] 3.1 Create word list files
  - Create adjectives.txt with 100+ Christian/Bible-themed adjectives
  - Create nouns.txt with 100+ Christian/Bible-themed nouns
  - Create blacklist.txt with profanity filter words
  - Store word lists in shared configuration directory
  - _Requirements: 3_

- [x] 3.2 Create session ID generator
  - Load word lists from files at Lambda initialization
  - Implement profanity blacklist filtering
  - Implement random selection algorithm with uniqueness check
  - Add configuration for max retry attempts (default 10)
  - _Requirements: 3_

- [x] 3.3 Implement uniqueness validation
  - Query DynamoDB Sessions table to check for existing session ID
  - Implement retry logic with exponential backoff if collision occurs
  - Add logging for generation attempts and collisions
  - _Requirements: 3_

- [x] 3.4 Write unit tests for session ID generation
  - Test format validation (adjective-noun-number pattern)
  - Test blacklist filtering
  - Test uniqueness collision handling
  - Test max retry limit behavior
  - _Requirements: 3_

- [x] 4. Implement Lambda Authorizer
- [x] 4.1 Create JWT validation logic
  - Fetch Cognito public keys from JWKS endpoint with caching
  - Decode JWT header to extract key ID (kid)
  - Verify JWT signature using public key
  - Validate token expiration, audience, and issuer claims
  - _Requirements: 7, 19_

- [x] 4.2 Generate IAM policy
  - Create Allow policy for valid tokens with speaker permissions
  - Include userId and email in policy context
  - Return Deny policy for invalid tokens
  - Add comprehensive error logging for authentication failures
  - _Requirements: 7, 17_

- [x] 4.3 Write unit tests for Lambda Authorizer
  - Test valid JWT token acceptance
  - Test expired token rejection
  - Test invalid signature rejection
  - Test wrong audience rejection
  - Test missing token handling
  - _Requirements: 7, 19_

- [x] 5. Implement rate limiting
- [x] 5.1 Create rate limiter module
  - Implement token bucket algorithm using DynamoDB
  - Support configurable limits per operation type
  - Handle window expiration and counter reset
  - Add TTL-based automatic cleanup
  - _Requirements: 13_

- [x] 5.2 Integrate rate limiting checks
  - Add rate limit check for session creation (RATE_LIMIT_SESSIONS_PER_HOUR per userId)
  - Add rate limit check for listener joins (RATE_LIMIT_LISTENER_JOINS_PER_MIN per IP)
  - Add rate limit check for connection attempts (RATE_LIMIT_CONNECTION_ATTEMPTS_PER_MIN per IP)
  - Add rate limit check for heartbeat messages (RATE_LIMIT_HEARTBEATS_PER_MIN per connection)
  - Return 429 status with retryAfter value when limit exceeded
  - Log rate limit violations for monitoring
  - _Requirements: 12, 13, 17_

- [x] 5.3 Write unit tests for rate limiting
  - Test within-limit request acceptance
  - Test limit-exceeded rejection with 429 status
  - Test window reset behavior
  - Test concurrent request handling
  - Test TTL-based cleanup
  - _Requirements: 13_

- [x] 6. Implement Connection Handler Lambda
- [x] 6.1 Create speaker session creation flow
  - Extract and validate query parameters (action, sourceLanguage, qualityTier)
  - Validate JWT token context from authorizer
  - Check rate limit for session creation
  - Generate unique session ID
  - Create session record in DynamoDB with all required attributes
  - Return sessionCreated message with session details
  - _Requirements: 1, 7, 15_

- [x] 6.2 Create listener join flow
  - Extract and validate query parameters (sessionId, targetLanguage)
  - Validate session exists and isActive=true in DynamoDB
  - Validate language support using AWS Translate and Polly APIs
  - Check session capacity limit (MAX_LISTENERS_PER_SESSION)
  - Create connection record in DynamoDB
  - Atomically increment listenerCount
  - Return sessionJoined message with connection details
  - _Requirements: 2, 8, 14, 15_

- [x] 6.2.1 Implement language support validation
  - Query AWS Polly DescribeVoices API for neural voice availability
  - Query AWS Translate ListLanguages API for translation support
  - Cache supported languages for performance (Lambda container reuse)
  - Return UNSUPPORTED_LANGUAGE error if target language not available
  - _Requirements: 2_

- [x] 6.3 Implement input validation
  - Validate ISO 639-1 language codes (2 lowercase letters)
  - Validate session ID format (adjective-noun-number pattern)
  - Validate qualityTier enum (standard or premium)
  - Return 400 Bad Request with specific error messages for invalid inputs
  - _Requirements: 15_

- [x] 6.4 Add error handling
  - Handle SESSION_NOT_FOUND for invalid session IDs
  - Handle SESSION_FULL when capacity reached
  - Handle RATE_LIMIT_EXCEEDED with retry information
  - Handle DynamoDB errors with retry logic
  - Log all errors with correlation IDs
  - _Requirements: 7, 8, 17_

- [x] 6.5 Write integration tests for Connection Handler
  - Test complete speaker session creation flow
  - Test complete listener join flow
  - Test session not found error handling
  - Test capacity limit enforcement
  - Test rate limit enforcement
  - Test language validation
  - _Requirements: 1, 2, 7, 8, 13, 14, 15_

- [x] 7. Implement Connection Refresh Handler Lambda
- [x] 7.1 Create connection refresh logic for speakers
  - Extract sessionId and validate session exists and isActive
  - Validate speaker userId matches session speakerUserId
  - Atomically update speakerConnectionId in Sessions table
  - Send connectionRefreshComplete message to new connection
  - Log connection refresh with old and new connection IDs
  - _Requirements: 11_

- [x] 7.2 Create connection refresh logic for listeners
  - Extract sessionId and targetLanguage parameters
  - Validate session exists and isActive
  - Create new connection record in Connections table
  - Atomically increment listenerCount
  - Send connectionRefreshComplete message
  - _Requirements: 11_

- [x] 7.3 Add connection refresh route to API Gateway
  - Configure refreshConnection custom route
  - Integrate with Connection Refresh Handler Lambda
  - Configure Lambda Authorizer for speaker refresh requests
  - _Requirements: 11_

- [x] 7.4 Write integration tests for connection refresh
  - Test speaker connection refresh with identity validation
  - Test listener connection refresh with count management
  - Test refresh with invalid session ID
  - Test refresh with mismatched speaker identity
  - Test temporary listenerCount spike tolerance
  - _Requirements: 11_

- [x] 8. Implement Heartbeat Handler Lambda
- [x] 8.1 Create heartbeat response logic with refresh detection
  - Extract connectionId from request context
  - Query connection record to check duration
  - Send connectionRefreshRequired at CONNECTION_REFRESH_MINUTES (100 min)
  - Send connectionWarning if approaching CONNECTION_WARNING_MINUTES (105 min)
  - Send heartbeatAck message via API Gateway Management API
  - Handle GoneException for disconnected clients
  - Log heartbeat activity for monitoring
  - _Requirements: 10, 11, 12_

- [x] 8.2 Write unit tests for heartbeat handler
  - Test heartbeatAck response within 100ms
  - Test connectionRefreshRequired at 100-minute threshold
  - Test connectionWarning at 105-minute threshold
  - Test GoneException handling
  - Test rate limiting for heartbeat messages
  - _Requirements: 10, 11, 12_

- [ ] 9. Implement Disconnect Handler Lambda
- [ ] 9.1 Create connection cleanup logic
  - Query connection record from DynamoDB by connectionId
  - Determine role (speaker or listener) from connection record
  - Delete connection record from DynamoDB
  - Handle idempotent operations (safe to retry)
  - _Requirements: 4, 5, 16_

- [ ] 9.2 Implement speaker disconnect handling
  - Mark session as inactive (isActive=false) in DynamoDB
  - Query all listener connections for the session using GSI
  - Send sessionEnded message to all listeners via API Gateway Management API
  - Delete all connection records for the session
  - Log session termination with session ID and duration
  - _Requirements: 4_

- [ ] 9.3 Implement listener disconnect handling
  - Atomically decrement listenerCount in Sessions table
  - Handle negative count edge case (set to 0 if negative)
  - Log listener disconnection with session ID and connection ID
  - _Requirements: 5_

- [ ]* 9.4 Write integration tests for disconnect handler
  - Test speaker disconnect with session termination
  - Test listener disconnect with count decrement
  - Test idempotent disconnect operations
  - Test notification to all listeners on speaker disconnect
  - Test negative count prevention
  - _Requirements: 4, 5, 16_

- [ ] 10. Implement API Gateway WebSocket API
- [ ] 10.1 Create API Gateway configuration
  - Define WebSocket API with route selection expression
  - Configure $connect route with Lambda Authorizer for speakers
  - Configure $disconnect route
  - Configure heartbeat custom route
  - Set connection timeout to 10 minutes idle, 2 hours maximum (API Gateway hard limit)
  - _Requirements: 10_

- [ ] 10.2 Configure Lambda integrations
  - Integrate Connection Handler with $connect route
  - Integrate Disconnect Handler with $disconnect route
  - Integrate Heartbeat Handler with heartbeat route
  - Integrate Connection Refresh Handler with refreshConnection route
  - Configure Lambda permissions for API Gateway invocation
  - _Requirements: All connection-related requirements_

- [ ]* 10.3 Write end-to-end integration tests
  - Test complete speaker session lifecycle (create, heartbeat, disconnect)
  - Test complete listener lifecycle (join, receive messages, disconnect)
  - Test multi-listener scenario with 100 concurrent listeners
  - Test connection refresh for long sessions (>2 hours simulation)
  - Test speaker disconnect notifying all listeners
  - _Requirements: 1, 2, 4, 5, 10, 11_

- [ ] 11. Implement monitoring and logging
- [ ] 11.1 Add structured logging
  - Implement JSON-formatted log entries with timestamp, level, correlationId
  - Log all operations with appropriate severity levels
  - Include sanitized user context (userId or hashed IP)
  - Add stack traces for 500-level errors
  - Configure CloudWatch Logs with 12-hour retention
  - _Requirements: 17_

- [ ] 11.2 Add CloudWatch metrics
  - Emit SessionCreationLatency metric (p50, p95, p99)
  - Emit ListenerJoinLatency metric (p50, p95, p99)
  - Emit ActiveSessions gauge metric
  - Emit TotalListeners gauge metric
  - Emit ConnectionErrors count metric by error code
  - Emit RateLimitExceeded count metric
  - _Requirements: 18_

- [ ] 11.3 Configure CloudWatch alarms
  - Create alarm for SessionCreationLatency p95 > 2000ms
  - Create alarm for ConnectionErrors > 100 per 5 minutes
  - Create alarm for ActiveSessions approaching limit
  - Configure SNS notifications for alarm triggers
  - _Requirements: 18_

- [ ]* 11.4 Write monitoring validation tests
  - Verify metrics are emitted correctly
  - Verify log entries contain required fields
  - Verify alarm thresholds trigger appropriately
  - Test metric aggregation accuracy
  - _Requirements: 17, 18_

- [ ] 12. Implement error handling and resilience
- [ ] 12.1 Add retry logic with exponential backoff
  - Implement retry decorator for DynamoDB operations
  - Configure max retries (3) and base delay (1s)
  - Add jitter to prevent thundering herd
  - Log retry attempts with attempt number
  - _Requirements: 21_

- [ ] 12.2 Implement circuit breaker
  - Create circuit breaker for DynamoDB operations
  - Configure failure threshold (5 failures) and timeout (30s)
  - Implement state transitions (CLOSED, OPEN, HALF_OPEN)
  - Log circuit breaker state changes
  - _Requirements: 21_

- [ ] 12.3 Add graceful degradation
  - Handle DynamoDB unavailability with 503 responses
  - Handle Cognito unavailability (reject speakers, allow listeners)
  - Temporarily disable rate limiting if RateLimits table unavailable
  - Log degraded mode operations
  - _Requirements: 21_

- [ ]* 12.4 Write resilience tests
  - Test retry logic with transient DynamoDB errors
  - Test circuit breaker state transitions
  - Test graceful degradation with service unavailability
  - Test exponential backoff behavior
  - _Requirements: 21_

- [ ] 13. Deploy infrastructure
- [ ] 13.1 Deploy DynamoDB tables
  - Deploy Sessions, Connections, and RateLimits tables to us-east-1 region
  - Enable TTL on appropriate attributes (expiresAt for Sessions, ttl for Connections)
  - Verify GSI creation for Connections table (sessionId-targetLanguage-index)
  - Configure on-demand billing mode for all tables
  - _Requirements: 9, 20_

- [ ] 13.2 Deploy Lambda functions
  - Package Lambda functions with dependencies
  - Deploy Authorizer, Connection Handler, Connection Refresh Handler, Heartbeat Handler, Disconnect Handler
  - Configure environment variables with all configurable parameters including CONNECTION_REFRESH_MINUTES
  - Set appropriate memory and timeout values
  - _Requirements: All_

- [ ] 13.3 Deploy API Gateway
  - Deploy WebSocket API with all routes
  - Configure Lambda Authorizer
  - Set up custom domain (optional)
  - Test WebSocket connectivity
  - _Requirements: All connection-related requirements_

- [ ]* 13.4 Run load tests
  - Test 100 concurrent session creations
  - Test 500 listeners joining single session (max capacity)
  - Test sustained load: 50 sessions with 50 listeners for 2 hours
  - Test 500 simultaneous disconnections
  - Verify performance targets (session creation <2s p95, listener join <1s p95)
  - _Requirements: 14, 18_

- [ ] 14. Create deployment documentation
  - Document environment variable configuration
  - Document deployment steps for each environment
  - Document rollback procedures
  - Document monitoring and alerting setup
  - _Requirements: All_

- [ ]* 14.1 Create client implementation examples
  - Create JavaScript/TypeScript client example with connection refresh
  - Create Python client example for testing
  - Document error handling patterns
  - Document audio buffer management during refresh
  - _Requirements: 11_
