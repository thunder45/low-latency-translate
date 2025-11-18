# Requirements Document

## Introduction

This specification addresses the cleanup and hardening of the authentication system following the migration from OAuth2 Hosted UI to direct username/password authentication. The cleanup focuses on removing orphaned code, adding comprehensive test coverage to security-critical components, and implementing security best practices.

## Glossary

- **AuthService**: The original OAuth2 Hosted UI implementation service (orphaned)
- **CognitoAuthService**: The current direct authentication service using USER_PASSWORD_AUTH
- **TokenStorage**: Service responsible for secure token storage using AES-256-GCM encryption
- **AuthGuard**: React component that protects routes and manages token refresh
- **Lambda Authorizer**: Backend JWT validation service for WebSocket connections
- **PBKDF2**: Password-Based Key Derivation Function 2, used for secure key derivation
- **JWK**: JSON Web Key, used for JWT signature verification

## Definition of Done

A requirement is considered complete when:

1. ✅ All acceptance criteria pass
2. ✅ Unit tests written and passing (>90% coverage for that requirement)
3. ✅ Code reviewed by peer or self-reviewed
4. ✅ Documentation updated to reflect changes
5. ✅ Manual testing completed for affected functionality
6. ✅ No regressions in existing tests
7. ✅ Performance criteria met (where applicable)
8. ✅ Security review passed (for security-related requirements)

## Requirements

### Requirement 1: Remove Orphaned OAuth2 Code

**User Story:** As a developer, I want orphaned OAuth2 code removed so that the codebase only contains the active authentication implementation and reduces maintenance burden.

**Affected Files**:
- `frontend-client-apps/shared/services/AuthService.ts` (to be deleted)
- Documentation files referencing OAuth2 Hosted UI

**Related Requirements**: None (independent)

#### Acceptance Criteria

1. WHEN the codebase is analyzed, THE System SHALL identify all files with zero references in the active codebase
2. WHEN AuthService.ts is removed, THE System SHALL verify no import statements reference this file
3. WHEN the removal is complete, THE System SHALL confirm all tests pass without the removed file
4. WHEN documentation is updated, THE System SHALL remove all references to OAuth2 Hosted UI flow

### Requirement 2: Add Comprehensive Test Coverage for TokenStorage

**User Story:** As a security engineer, I want comprehensive test coverage for TokenStorage so that encryption, decryption, and token management logic is verified to work correctly.

**Affected Files**:
- Implementation: `frontend-client-apps/shared/services/TokenStorage.ts`
- Tests: `frontend-client-apps/shared/__tests__/TokenStorage.test.ts` (to be created)
- Related: `frontend-client-apps/shared/types/auth.ts` (types)

**Related Requirements**: Req 5 (Security Best Practices), Req 6 (Code Quality)

#### Acceptance Criteria

1. WHEN TokenStorage encrypts a token, THE System SHALL verify the encrypted output differs from the plaintext input
2. WHEN TokenStorage decrypts a token, THE System SHALL verify the decrypted output matches the original plaintext
3. WHEN TokenStorage handles invalid encrypted data, THE System SHALL throw appropriate errors without exposing sensitive information
4. WHEN TokenStorage stores tokens, THE System SHALL verify tokens are retrievable and valid
5. WHEN TokenStorage clears tokens, THE System SHALL verify all token data is removed from storage
6. WHEN TokenStorage handles concurrent operations, THE System SHALL maintain data integrity
7. WHEN TokenStorage encryption key is derived, THE System SHALL use PBKDF2 with at least 100,000 iterations
8. WHEN TokenStorage generates initialization vectors, THE System SHALL create unique values for each encryption operation
9. WHEN TokenStorage validates tokens before storage, THE System SHALL reject tokens with expiresAt in the past
10. WHEN localStorage is unavailable, THE System SHALL handle gracefully and inform the user

### Requirement 3: Add Comprehensive Test Coverage for AuthGuard

**User Story:** As a security engineer, I want comprehensive test coverage for AuthGuard so that route protection and token refresh logic is verified to prevent unauthorized access.

**Affected Files**:
- Implementation: `frontend-client-apps/shared/components/AuthGuard.tsx`
- Tests: `frontend-client-apps/shared/__tests__/AuthGuard.test.tsx` (to be created)
- Related: `frontend-client-apps/shared/services/TokenStorage.ts`, `frontend-client-apps/shared/services/CognitoAuthService.ts`

**Related Requirements**: Req 2 (TokenStorage Tests), Req 5 (Security - concurrent refresh)

#### Acceptance Criteria

1. WHEN an unauthenticated user accesses a protected route, THE AuthGuard SHALL redirect to the login page
2. WHEN an authenticated user accesses a protected route, THE AuthGuard SHALL render the protected component
3. WHEN a token expires during a session, THE AuthGuard SHALL attempt automatic refresh
4. WHEN token refresh succeeds, THE AuthGuard SHALL maintain the user session without interruption
5. WHEN token refresh fails, THE AuthGuard SHALL redirect to login and clear stored tokens
6. WHEN multiple refresh attempts occur concurrently, THE AuthGuard SHALL execute only one refresh operation
7. WHEN AuthGuard initializes, THE AuthGuard SHALL validate stored tokens before granting access
8. WHEN AuthGuard schedules token refresh, THE AuthGuard SHALL clean up timers on component unmount
9. WHEN AuthGuard detects token expiry, THE AuthGuard SHALL attempt refresh before showing login
10. WHEN refresh is scheduled, THE AuthGuard SHALL schedule it 5 minutes before actual token expiry

### Requirement 4: Add Comprehensive Test Coverage for AuthError

**User Story:** As a developer, I want comprehensive test coverage for AuthError so that error handling and user-facing messages are consistent and helpful.

**Affected Files**:
- Implementation: `frontend-client-apps/shared/errors/AuthError.ts`
- Tests: `frontend-client-apps/shared/__tests__/AuthError.test.ts` (to be created)

**Related Requirements**: None (independent)

#### Acceptance Criteria

1. WHEN an authentication error occurs, THE AuthError SHALL provide a user-friendly message
2. WHEN an authentication error occurs, THE AuthError SHALL include the original error code
3. WHEN AuthError creates an error from Cognito response, THE AuthError SHALL map Cognito error codes to user messages
4. WHEN AuthError creates an error from network failure, THE AuthError SHALL provide appropriate network error messages
5. WHEN AuthError is serialized, THE AuthError SHALL include all relevant debugging information

### Requirement 5: Implement Security Best Practices

**User Story:** As a security engineer, I want security best practices implemented so that the authentication system is hardened against common vulnerabilities.

**Affected Files**:
- `frontend-client-apps/shared/services/TokenStorage.ts` (PBKDF2, salt, key validation)
- `frontend-client-apps/shared/components/AuthGuard.tsx` (concurrent refresh protection)
- `frontend-client-apps/shared/websocket/WebSocketClient.ts` (close code enum)
- `frontend-client-apps/shared/config/constants.ts` (to be created for magic numbers)

**Related Requirements**: Req 2 (TokenStorage Tests), Req 3 (AuthGuard Tests), Req 6 (Code Quality)

#### Acceptance Criteria

1. WHEN TokenStorage derives an encryption key, THE System SHALL use PBKDF2 with at least 100,000 iterations
2. WHEN TokenStorage generates a salt, THE System SHALL use a fixed application salt for consistent key derivation
3. WHEN AuthGuard handles concurrent refresh requests, THE System SHALL prevent race conditions using a mutex or flag
4. WHEN magic numbers are used in code, THE System SHALL replace them with named constants in a centralized configuration file
5. WHEN dynamic imports are used in the authentication flow, THE System SHALL replace them with static imports to reduce latency
6. WHEN WebSocket close codes are used, THE System SHALL use WebSocketCloseCode enum values
7. WHEN concurrent operations access TokenStorage, THE System SHALL not corrupt stored data
8. WHEN encryption key is validated, THE System SHALL verify it is at least 32 characters before derivation
9. WHEN TokenStorage validates tokens, THE System SHALL verify expiresAt is an absolute timestamp not a duration

### Requirement 6: Improve Code Quality

**User Story:** As a developer, I want improved code quality so that the authentication system is maintainable and follows best practices.

**Affected Files**:
- `frontend-client-apps/shared/config/constants.ts` (centralized constants)
- `frontend-client-apps/shared/services/TokenStorage.ts` (singleton initialization)
- `frontend-client-apps/shared/utils/SessionCreationOrchestrator.ts` (static imports, WebSocket validation)
- `frontend-client-apps/speaker-app/src/components/LoginForm.tsx` (static imports)

**Related Requirements**: Req 5 (Security Best Practices), Req 8 (Fix Bugs)

#### Acceptance Criteria

1. WHEN configuration values are needed, THE System SHALL reference centralized constants rather than inline magic numbers
2. WHEN TokenStorage is initialized, THE System SHALL initialize the singleton once at application startup
3. WHEN imports are used in critical paths, THE System SHALL use static imports at module level to avoid dynamic loading overhead
4. WHEN code is formatted, THE System SHALL follow the project's TypeScript style guide
5. WHEN documentation is updated, THE System SHALL reflect the current direct authentication implementation
6. WHEN WebSocket send operations are performed, THE System SHALL validate connection state before sending
7. WHEN error messages reference operations, THE System SHALL use consistent terminology
8. WHEN components need TokenStorage, THE System SHALL use the pre-initialized singleton instance

### Requirement 7: Validate Production Readiness

**User Story:** As a product owner, I want validation that the authentication system is production-ready so that we can deploy with confidence.

**Affected Files**:
- All test files created in Req 2, 3, 4
- All implementation files modified in Req 5, 6, 8

**Related Requirements**: All requirements (validation phase)

#### Acceptance Criteria

1. WHEN all tests are executed, THE System SHALL achieve at least 90% code coverage for authentication components
2. WHEN security-critical code is reviewed, THE System SHALL have zero untested security functions
3. WHEN the authentication flow is tested end-to-end, THE System SHALL successfully authenticate users and maintain sessions
4. WHEN error scenarios are tested, THE System SHALL handle all error cases gracefully with appropriate user feedback
5. WHEN first-time authentication is measured, THE System SHALL complete within 2 seconds (p95)
6. WHEN token refresh is measured, THE System SHALL complete within 500 milliseconds (p95)
7. WHEN WebSocket connection is measured, THE System SHALL complete within 1 second (p95)

### Requirement 8: Fix Known Implementation Bugs

**User Story:** As a developer, I want known bugs fixed so that the authentication system operates correctly in all scenarios.

**Affected Files**:
- `frontend-client-apps/shared/utils/SessionCreationOrchestrator.ts` (token expiry bug, WebSocket validation)
- `session-management/lambda/authorizer/handler.py` (error logging)
- `frontend-client-apps/shared/websocket/WebSocketClient.ts` (close code enum)
- `session-management/infrastructure/stacks/session_management_stack.py` (environment variables)

**Related Requirements**: Req 6 (Code Quality), Req 9 (Observability)

#### Acceptance Criteria

1. WHEN SessionCreationOrchestrator checks token expiry, THE System SHALL use the stored expiresAt timestamp directly without recalculating from expiresIn duration
2. WHEN SessionCreationOrchestrator sends WebSocket messages, THE System SHALL verify the connection is open before sending
3. WHEN the Lambda authorizer logs errors, THE System SHALL include structured context with error_type, method_arn, and request_id
4. WHEN code references WebSocket close codes, THE System SHALL use WebSocketCloseCode enum values (1000, 1006, 1008, 1011)
5. WHEN environment variables are referenced, THE System SHALL use consistent naming (USER_POOL_ID, CLIENT_ID, REGION)

## Requirements Priority Matrix

| Requirement | Priority | Blocks Production? | Estimated Effort |
|-------------|----------|-------------------|------------------|
| Req 1: Remove OAuth2 Code | P0 | No | 30 minutes |
| Req 2: TokenStorage Tests | P0 | Yes | 4-5 hours |
| Req 3: AuthGuard Tests | P0 | Yes | 3-4 hours |
| Req 4: AuthError Tests | P1 | No | 2-3 hours |
| Req 5: Security Best Practices | P0 | Yes | 2-3 hours |
| Req 6: Code Quality | P1 | No | 2-3 hours |
| Req 7: Production Readiness | P0 | Yes | Validation only |
| Req 8: Fix Known Bugs | P0 | Yes | 1-2 hours |
| Req 9: Improve Observability | P1 | No | 1-2 hours |

**Total Estimated Effort**: 16-23 hours

**Priority Definitions**:
- **P0**: Must complete before production deployment
- **P1**: Should complete before production, can be addressed post-launch if needed

## Success Metrics

After implementation, the authentication system SHALL meet these criteria:

**Test Coverage**:
- [ ] Overall test coverage >90% for authentication components
- [ ] TokenStorage.ts: 100% coverage (security-critical)
- [ ] AuthGuard.tsx: 100% coverage (security-critical)
- [ ] AuthError.ts: >80% coverage
- [ ] Zero untested security-critical functions

**Code Quality**:
- [ ] Zero orphaned code files
- [ ] Zero magic numbers in authentication code
- [ ] All imports are static (no dynamic imports in auth flow)
- [ ] All WebSocket operations validate connection state

**Security**:
- [ ] PBKDF2 key derivation with 100,000+ iterations
- [ ] Concurrent refresh protection implemented
- [ ] Token expiry calculation uses absolute timestamps
- [ ] All error logs exclude sensitive data

**Performance**:
- [ ] First-time authentication: <2 seconds (p95)
- [ ] Token refresh: <500ms (p95)
- [ ] WebSocket connection: <1 second (p95)

**Production Readiness**:
- [ ] All P0 requirements completed
- [ ] Zero authentication-related bugs in staging
- [ ] End-to-end authentication flow tested and passing
- [ ] All error scenarios handled gracefully

## Risk Assessment

| Requirement | Risk if Not Implemented | Mitigation Strategy |
|-------------|------------------------|---------------------|
| Req 2: TokenStorage Tests | **HIGH** - Encryption bugs could expose tokens in production | MUST complete before production |
| Req 3: AuthGuard Tests | **HIGH** - Unauthorized access to protected routes | MUST complete before production |
| Req 5: Security Practices | **HIGH** - Weak encryption, race conditions | MUST complete before production |
| Req 8: Fix Known Bugs | **MEDIUM** - Token refresh timing issues, WebSocket failures | Should fix before production |
| Req 1: Remove OAuth2 | **LOW** - Dead code increases maintenance burden | Can defer if time-constrained |
| Req 4: AuthError Tests | **LOW** - Error handling may have edge cases | Can address post-launch |
| Req 6: Code Quality | **LOW** - Maintainability issues | Can address post-launch |
| Req 9: Observability | **LOW** - Harder to debug production issues | Can address post-launch |

### Requirement 9: Improve Observability

**User Story:** As a DevOps engineer, I want enhanced observability so that authentication failures can be debugged effectively in production.

**Affected Files**:
- `session-management/lambda/authorizer/handler.py` (structured logging)
- `frontend-client-apps/shared/services/CognitoAuthService.ts` (performance metrics)
- `frontend-client-apps/shared/components/AuthGuard.tsx` (performance metrics)

**Related Requirements**: Req 8 (Fix Bugs - Lambda logging)

#### Acceptance Criteria

1. WHEN an authorization error occurs in Lambda, THE System SHALL log the error type and error name
2. WHEN logging authorization errors, THE System SHALL include methodArn for request correlation
3. WHEN logging authorization errors, THE System SHALL indicate whether a token was present without logging the token value
4. WHEN using structured logging, THE System SHALL use the extra parameter for CloudWatch Insights compatibility
5. WHEN performance metrics are collected, THE System SHALL track separate metrics for first-time authentication and token refresh
