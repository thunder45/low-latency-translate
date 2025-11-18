# Implementation Plan

Convert the authentication cleanup design into actionable implementation tasks. Each task builds incrementally and ends with integration. Tasks are organized by priority (P0 must complete before production).

## Recommended Execution Sequence

For optimal implementation flow, consider executing tasks in these phases:

### Phase 1: Setup & Quick Fixes (1-2 hours)
- Task 1: Remove OAuth2 code
- Task 2: Create constants (all sub-tasks)
- Task 5: Fix token expiry bug
- Task 6: Add WebSocket state validation
- Task 7: Remove dynamic imports
- Task 7.5: Centralize TokenStorage initialization
- Task 8: Use close code enum

### Phase 2: Security Implementation (2-3 hours)
- Task 3: Implement PBKDF2 (all sub-tasks)
- Task 4: Add concurrent refresh protection (all sub-tasks)

### Phase 3: Test Security Changes (4-5 hours)
- Task 10: Write TokenStorage tests (validates Phase 2 changes)

### Phase 4: Test Route Protection (3-4 hours)
- Task 11: Write AuthGuard tests (validates Phase 2 changes)

### Phase 5: Test Error Handling (2-3 hours)
- Task 12: Write AuthError tests
- Task 13: Add bug fix tests to SessionCreationOrchestrator

### Phase 6: Validation (2 hours)
- Task 14: Validate test coverage >90%
- Task 15: E2E authentication testing
- Task 16: Performance validation

### Phase 7: Observability (2-3 hours)
- Task 9: Improve Lambda logging
- Task 18: Configure CloudWatch monitoring

### Phase 8: Documentation (1 hour)
- Task 17: Update all documentation

**Total Estimated Effort**: 18-23 hours

**Benefits of This Sequence**:
- Quick wins first (bug fixes, constants)
- Related changes grouped together
- Tests written immediately after code changes
- Clear phase boundaries for progress tracking
- Validation at end confirms everything works

## Task List

- [x] 1. Remove orphaned OAuth2 code
  - Delete AuthService.ts file with zero references
  - Verify no import errors remain
  - Run all existing tests to confirm no breakage
  - _Requirements: 1.1, 1.2, 1.3_
  - _Priority: P0_
  - _Effort: 30 minutes_

- [x] 2. Create centralized constants configuration
- [x] 2.1 Create constants file with authentication values
  - Create `frontend-client-apps/shared/config/constants.ts`
  - Define TOKEN_REFRESH_THRESHOLD_MS = 5 * 60 * 1000
  - Define SESSION_CREATION_TIMEOUT_MS = 10 * 1000
  - _Requirements: 5.4, 6.1_

- [x] 2.2 Add encryption constants
  - Define PBKDF2_ITERATIONS = 100000
  - Define ENCRYPTION_KEY_LENGTH = 32
  - Define ENCRYPTION_IV_LENGTH = 12
  - Define APPLICATION_SALT with SALT_VERSION = 'v1'
  - _Requirements: 5.1, 5.2_

- [x] 2.3 Create WebSocket close code enum
  - Create WebSocketCloseCode enum
  - Define NORMAL_CLOSURE = 1000
  - Define ABNORMAL_CLOSURE = 1006
  - Define POLICY_VIOLATION = 1008
  - Define INTERNAL_ERROR = 1011
  - _Requirements: 5.6, 8.4_

- [x] 2.4 Document required environment variables
  - Document backend env vars: USER_POOL_ID, CLIENT_ID, REGION
  - Document frontend env vars: VITE_COGNITO_USER_POOL_ID, VITE_COGNITO_CLIENT_ID, VITE_AWS_REGION
  - Create REQUIRED_ENV_VARS constant with both lists
  - _Requirements: 8.5_

- [x] 2.5 Create .env.example file
  - Create .env.example in frontend-client-apps root
  - Add all required VITE_ variables with placeholder values
  - Add comments explaining each variable
  - _Requirements: 8.5_

- [x] 2.6 Verify Lambda authorizer environment variable consistency
  - Check Lambda authorizer uses USER_POOL_ID (not COGNITO_USER_POOL_ID)
  - Check Lambda authorizer uses CLIENT_ID (not COGNITO_CLIENT_ID)
  - Update CDK stack if variable names are inconsistent
  - _Requirements: 8.5, 6.8_
  - _Priority: P0_
  - _Effort: 45 minutes total_

- [x] 3. Implement PBKDF2 key derivation in TokenStorage
- [x] 3.1 Add PBKDF2 deriveKey method to TokenStorage
  - Implement deriveKey() using Web Crypto API
  - Use PBKDF2 with 100,000 iterations and SHA-256
  - Use fixed application salt with version tracking
  - Return CryptoKey for AES-GCM operations
  - _Requirements: 2.7, 5.1, 5.2, 5.8_

- [x] 3.2 Update encryption to use PBKDF2-derived key
  - Modify encrypt() to use deriveKey()
  - Generate unique IV for each encryption (12 bytes)
  - Validate encryption key is at least 32 characters
  - Store IV separately in localStorage
  - _Requirements: 2.1, 2.8, 5.8_

- [x] 3.3 Update decryption to use PBKDF2-derived key
  - Modify decrypt() to use deriveKey()
  - Retrieve IV from localStorage
  - Handle decryption failures gracefully
  - _Requirements: 2.2, 2.3_

- [x] 3.4 Add token validation before storage
  - Validate expiresAt is absolute timestamp (not duration)
  - Reject tokens with expiresAt in the past
  - Throw descriptive error for invalid tokens
  - _Requirements: 2.9, 5.9_

- [x] 3.5 Add localStorage unavailability handling
  - Wrap localStorage operations in try-catch
  - Provide user-friendly error message
  - Suggest enabling cookies/storage
  - _Requirements: 2.10_

- [x] 4. Add concurrent refresh protection to AuthGuard
- [x] 4.1 Replace useState with useRef for refresh tracking
  - Create refreshPromiseRef using useRef
  - Return existing promise if refresh in progress
  - Clear ref when refresh completes
  - _Requirements: 3.6, 5.3_

- [x] 4.2 Implement timer cleanup on unmount
  - Clear refreshTimerRef in useEffect cleanup
  - Prevent memory leaks from orphaned timers
  - _Requirements: 3.8_

- [x] 4.3 Schedule refresh 5 minutes before expiry
  - Calculate delay as (expiresAt - now - 5min)
  - Schedule refresh timer with calculated delay
  - Clear existing timer before scheduling new one
  - _Requirements: 3.10_

- [x] 4.4 Attempt refresh before showing login
  - Check if token is expired in checkAuth()
  - Call handleTokenRefresh() before redirecting
  - Only redirect if refresh fails
  - _Requirements: 3.9_

- [x] 5. Fix token expiry calculation bug
  - Update SessionCreationOrchestrator to use tokens.expiresAt directly
  - Remove recalculation from expiresIn duration
  - Add comment explaining the fix
  - _Requirements: 8.1_
  - _Priority: P0_
  - _Effort: 15 minutes_

- [x] 6. Add WebSocket state validation
  - Add isConnected() check before wsClient.send()
  - Wrap send in try-catch in sendCreationRequest()
  - Throw descriptive error if not connected
  - Clear timeout and reject promise on error
  - _Requirements: 6.6, 8.2_
  - _Priority: P0_
  - _Effort: 15 minutes_

- [x] 7. Remove dynamic imports from authentication flow
  - Replace dynamic imports in LoginForm.tsx with static imports
  - Move imports to top of file
  - Verify no dynamic imports remain in auth path
  - _Requirements: 5.5, 6.3_
  - _Priority: P1_
  - _Effort: 15 minutes_

- [x] 7.5 Centralize TokenStorage initialization
  - Create async initializeApp() function in main.tsx
  - Initialize TokenStorage singleton once before app render
  - Derive encryption key and cache it
  - Import pre-initialized TokenStorage in LoginForm.tsx
  - Import pre-initialized TokenStorage in AuthGuard.tsx
  - Keep one safety check in AuthGuard.tsx (verify initialized)
  - Remove duplicate initialization calls from components
  - _Requirements: 6.2, 6.8_
  - _Priority: P1_
  - _Effort: 30 minutes_

- [x] 8. Update WebSocketClient to use close code enum
  - Import WebSocketCloseCode from constants
  - Replace magic numbers with enum values
  - Update disconnect() method signature
  - _Requirements: 5.6, 8.4_
  - _Priority: P1_
  - _Effort: 15 minutes_

- [ ] 9. Improve Lambda authorizer error logging
- [ ] 9.1 Add structured logging to Lambda authorizer
  - Import logging and configure logger
  - Add extra parameter with error_type, method_arn, has_token, request_id
  - Log at appropriate levels (INFO for success, ERROR for failures)
  - Never log actual token values
  - _Requirements: 8.3, 9.1, 9.2, 9.3, 9.4_

- [ ] 9.2 Add Lambda authorizer logging tests
  - Test structured logging format
  - Verify CloudWatch Insights compatibility
  - Test that tokens are never logged
  - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 10. Write comprehensive TokenStorage tests
  - **Depends on**: Tasks 2 (constants), 3 (PBKDF2 implementation)
  - **Tests**: TokenStorage encryption, PBKDF2, token validation
  - _Priority: P0_
  - _Effort: 4-5 hours_

- [x] 10.1 Create TokenStorage.test.ts file
  - Set up test file with Vitest
  - Mock Web Crypto API
  - Mock localStorage
  - Create test fixtures for tokens
  - _Requirements: 2.1-2.10_

- [x] 10.2 Write encryption/decryption tests
  - Test encryption produces different output than input
  - Test decryption returns original plaintext
  - Test round-trip encryption/decryption
  - Test unique IV generation for each encryption
  - _Requirements: 2.1, 2.2, 2.8_

- [x] 10.3 Write PBKDF2 key derivation tests
  - Test key derivation with correct parameters
  - Test key length is 256 bits
  - Test iterations count is 100,000
  - Test salt is correctly applied
  - _Requirements: 2.7, 5.1, 5.2_

- [x] 10.4 Write token validation tests
  - Test storing valid tokens succeeds
  - Test storing expired tokens fails
  - Test expiresAt validation (absolute timestamp)
  - Test retrieving stored tokens
  - _Requirements: 2.4, 2.9, 5.9_

- [x] 10.5 Write error handling tests
  - Test invalid encrypted data throws error
  - Test error messages don't expose sensitive data
  - Test localStorage unavailable handling
  - Test concurrent operations maintain integrity
  - _Requirements: 2.3, 2.6, 2.10_

- [x] 10.6 Write token clearing tests
  - Test clearTokens() removes all data
  - Test no tokens retrievable after clear
  - Test clear works even if no tokens stored
  - _Requirements: 2.5_

- [x] 11. Write comprehensive AuthGuard tests
  - **Depends on**: Tasks 2 (constants), 4 (concurrent refresh protection)
  - **Tests**: Route protection, token refresh, concurrent refresh prevention
  - _Priority: P0_
  - _Effort: 3-4 hours_

- [x] 11.1 Create AuthGuard.test.tsx file
  - Set up test file with Vitest and React Testing Library
  - Mock TokenStorage
  - Mock CognitoAuthService
  - Mock React Router Navigate component
  - _Requirements: 3.1-3.10_

- [x] 11.2 Write authentication state tests
  - Test unauthenticated user redirects to login
  - Test authenticated user renders children
  - Test loading state displays spinner
  - Test token validation on initialization
  - _Requirements: 3.1, 3.2, 3.7_

- [x] 11.3 Write token refresh tests
  - Test refresh triggered when token expires
  - Test refresh triggered when close to expiry
  - Test successful refresh maintains session
  - Test failed refresh redirects to login
  - _Requirements: 3.3, 3.4, 3.5, 3.9_

- [x] 11.4 Write concurrent refresh protection tests
  - Test multiple rapid refresh calls use same promise
  - Test only one refresh operation executes
  - Test subsequent calls wait for first to complete
  - _Requirements: 3.6, 5.3_

- [x] 11.5 Write timer management tests
  - Test refresh scheduled 5 minutes before expiry
  - Test timer cleanup on component unmount
  - Test timer cleared before scheduling new one
  - _Requirements: 3.8, 3.10_

- [ ] 12. Write comprehensive AuthError tests
  - **Depends on**: None (AuthError unchanged)
  - **Tests**: Error creation, Cognito mapping, user messages
  - _Priority: P1_
  - _Effort: 2-3 hours_

- [ ] 12.1 Create AuthError.test.ts file
  - Set up test file with Vitest
  - Create test fixtures for various error types
  - _Requirements: 4.1-4.5_

- [ ] 12.2 Write error creation tests
  - Test creating AuthError with all error codes
  - Test error includes code, message, userMessage
  - Test error with and without originalError
  - _Requirements: 4.1, 4.2_

- [ ] 12.3 Write Cognito error mapping tests
  - Test fromCognitoError() maps all Cognito error codes
  - Test NotAuthorizedException maps to AUTH_INVALID_CREDENTIALS
  - Test UserNotFoundException maps to AUTH_USER_NOT_FOUND
  - Test TooManyRequestsException maps to AUTH_RATE_LIMIT
  - Test unknown errors map to AUTH_UNKNOWN_ERROR
  - _Requirements: 4.3_

- [ ] 12.4 Write user message generation tests
  - Test getUserMessage() returns friendly messages
  - Test all error codes have user messages
  - Test unknown codes return generic message
  - _Requirements: 4.4_

- [ ] 12.5 Write error serialization tests
  - Test toJSON() includes all error properties
  - Test JSON output is valid
  - Test network error handling
  - _Requirements: 4.5_

- [ ] 13. Add bug fix tests to SessionCreationOrchestrator
  - **Depends on**: Tasks 5 (token expiry fix), 6 (WebSocket validation)
  - **Tests**: Token expiry calculation, WebSocket state validation
  - _Priority: P0_
  - _Effort: 30 minutes_

- [ ] 13.1 Test token expiry calculation fix
  - Test uses tokens.expiresAt directly
  - Test doesn't recalculate from expiresIn
  - Test correct timing for refresh trigger
  - _Requirements: 8.1_

- [ ] 13.2 Test WebSocket state validation
  - Test send validates connection state
  - Test throws error if not connected
  - Test error is caught and promise rejected
  - _Requirements: 8.2, 6.6_

- [ ] 14. Validate test coverage meets requirements
  - Run `npm test -- --coverage` for all auth components
  - Verify TokenStorage.ts has 100% coverage
  - Verify AuthGuard.tsx has 100% coverage
  - Verify AuthError.ts has >80% coverage
  - Verify overall auth component coverage >90%
  - _Requirements: 7.1, 7.2_
  - _Priority: P0_
  - _Effort: 30 minutes_

- [ ] 15. Perform end-to-end authentication testing
  - Test complete login flow (username/password)
  - Test token refresh during active session
  - Test session persistence across page reload
  - Test logout and token clearing
  - Test error scenarios (invalid credentials, network errors)
  - _Requirements: 7.3, 7.4_
  - _Priority: P0_
  - _Effort: 1 hour_

- [ ] 16. Validate performance requirements
  - Measure first-time authentication duration (target <2s p95)
  - Measure token refresh duration (target <500ms p95)
  - Measure WebSocket connection duration (target <1s p95)
  - Measure PBKDF2 key derivation time (expected 50-100ms)
  - _Requirements: 7.5, 7.6, 7.7_
  - _Priority: P0_
  - _Effort: 30 minutes_

- [ ] 17. Update documentation
  - Update README.md to remove OAuth2 references
  - Document direct authentication flow
  - Update AUTHENTICATION_CLEANUP_GUIDE.md as completed
  - Update CLEANUP_ACTION_PLAN.md tasks as done
  - Document PBKDF2 configuration in SECURITY.md
  - _Requirements: 1.4, 6.5_
  - _Priority: P1_
  - _Effort: 1 hour_

- [ ] 18. Configure CloudWatch monitoring
- [ ] 18.1 Add CloudWatch metrics
  - Add AuthenticationDuration metric
  - Add TokenRefreshDuration metric
  - Add WebSocketConnectionDuration metric
  - Add TokenStorageErrors metric
  - Add ConcurrentRefreshAttempts metric
  - _Requirements: 9.5_

- [ ] 18.2 Create CloudWatch dashboard
  - Create dashboard for authentication metrics
  - Add widgets for latency (p50, p95, p99)
  - Add widgets for error rates
  - Add widgets for throughput
  - _Requirements: 9.5_

- [ ] 18.3 Configure CloudWatch alerts
  - Alert if auth success rate <95% (critical)
  - Alert if token refresh failure rate >5% (critical)
  - Alert if WebSocket connection failure >5% (critical)
  - Alert if auth duration p95 >2s (warning)
  - Alert if token refresh p95 >500ms (warning)
  - _Requirements: 9.5_

## Parallel Execution Opportunities

These tasks can be executed in parallel by different developers:

**Parallel Set 1** (Phase 2):
- Task 3: PBKDF2 implementation (Frontend developer)
- Task 9: Lambda logging improvements (Backend developer)

**Parallel Set 2** (Phase 3-4):
- Task 10: TokenStorage tests (Developer A)
- Task 11: AuthGuard tests (Developer B)

**Parallel Set 3** (Phase 7-8):
- Task 17: Documentation (Developer A)
- Task 18: CloudWatch monitoring (Developer B)

## Task Execution Tips

### Before Starting
1. Read the design document for code examples
2. Set up test coverage tracking: `npm test -- --coverage`
3. Create feature branch: `git checkout -b feature/auth-cleanup`

### During Implementation
1. **Test-Driven Development**: Write tests first when possible
2. **Incremental Commits**: Commit after each completed task
3. **Coverage Tracking**: Run `npm test -- --coverage` frequently
4. **Code Review**: Self-review before marking task complete

### Testing Commands
```bash
# Run all tests with coverage
npm test -- --coverage

# Run specific test file
npm test TokenStorage.test.ts

# Watch mode during development
npm test -- --watch TokenStorage.test.ts

# Run tests for specific component
npm test -- AuthGuard
```

### Validation Checklist
After completing all tasks, verify:
- [ ] All tests passing
- [ ] Coverage >90% for auth components
- [ ] No TypeScript errors
- [ ] No ESLint warnings
- [ ] E2E authentication flow works
- [ ] Performance targets met
- [ ] Documentation updated

## Critical Path Analysis

**Minimum time to complete** (with parallelization):
- Day 1: Phase 1 (Setup & Quick Fixes) - 2 hours
- Day 2: Phase 2 (Security Implementation) - 3 hours
- Day 3: Phase 3 (TokenStorage Tests) - 5 hours
- Day 4: Phase 4 (AuthGuard Tests) - 4 hours
- Day 5: Phase 5 (Error Tests) + Phase 6 (Validation) - 5 hours
- Day 6: Phase 7 (Observability) + Phase 8 (Docs) - 3 hours

**Total**: 5-6 days with some parallelization, or 3-4 weeks part-time

## Success Criteria

Implementation is complete when:
- ✅ All P0 tasks completed
- ✅ Test coverage >90% for authentication components
- ✅ All tests passing
- ✅ Performance targets met (auth <2s, refresh <500ms, WebSocket <1s)
- ✅ No orphaned code
- ✅ Security best practices implemented
- ✅ Documentation updated
- ✅ Monitoring configured
