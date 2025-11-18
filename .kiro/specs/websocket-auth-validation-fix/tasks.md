# Implementation Plan

- [x] 1. Update Lambda authorizer dependencies
  - Add PyJWT[crypto]==2.8.0 to session-management/lambda/authorizer/requirements.txt
  - Add cryptography==41.0.0 to session-management/lambda/authorizer/requirements.txt
  - Rebuild Lambda layer with new dependencies
  - Verify dependencies are installed correctly
  - _Requirements: 2.1, 5.5_

- [x] 2. Implement JWT token validation in Lambda authorizer
  - Update session-management/lambda/authorizer/handler.py
  - Add get_jwks_client() function to fetch and cache Cognito public keys
  - Add extract_token() function to get token from query string or Authorization header
  - Add validate_token() function with full JWT validation (signature, issuer, audience, expiration, token_use)
  - Update lambda_handler() to use new validation functions
  - Add detailed error logging for each validation failure
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4_

- [x] 3. Add configuration validation
  - Validate COGNITO_USER_POOL_ID environment variable is set
  - Validate COGNITO_CLIENT_ID environment variable is set
  - Validate AWS_REGION environment variable is set
  - Log "Missing Cognito configuration" if any are missing
  - Reject connections with clear error when configuration is invalid
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 4. Update IAM policy generation
  - Update generate_policy() function to include user context
  - Pass userId (from sub claim) in policy context
  - Pass email in policy context
  - Ensure context is available to connection handlers
  - _Requirements: 2.5_

- [x] 5. Enhance WebSocket client error handling
  - Update frontend-client-apps/shared/websocket/WebSocketClient.ts
  - Add handleConnectionError() method
  - Add handleConnectionClose() method with close code detection
  - Emit 'auth_error' event for code 1008 (authentication failure)
  - Emit 'connection_failed' event for code 1006 (abnormal closure)
  - Add reconnection logic for non-auth failures
  - _Requirements: 6.1, 6.4_

- [x] 6. Implement token refresh and retry in SessionCreationOrchestrator
  - Update frontend-client-apps/shared/services/SessionCreationOrchestrator.ts
  - Check token expiry before connecting (refresh if < 5 minutes)
  - Add waitForConnection() method with timeout and error handling
  - Implement retry logic on auth failure (refresh token + retry once)
  - Add clear error messages for different failure scenarios
  - _Requirements: 6.2, 6.3, 6.5_

- [x] 7. Update Lambda authorizer environment variables
  - Verify COGNITO_USER_POOL_ID is set in CDK stack
  - Verify COGNITO_CLIENT_ID is set in CDK stack
  - Verify AWS_REGION is set in CDK stack
  - Deploy updated Lambda function
  - _Requirements: 5.1, 5.2, 5.3_

- [x] 8. Write unit tests for Lambda authorizer
  - Create session-management/tests/unit/test_authorizer.py
  - Mock PyJWKClient and jwt.decode
  - Test extract_token() from query string
  - Test extract_token() from Authorization header
  - Test extract_token() with no token
  - Test validate_token() with valid token
  - Test validate_token() with expired token
  - Test validate_token() with invalid signature
  - Test validate_token() with invalid issuer
  - Test validate_token() with invalid audience
  - Test validate_token() with wrong token_use
  - Test lambda_handler() success case
  - Test lambda_handler() with missing configuration
  - Test generate_policy() with context
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 5.1, 5.2, 5.3, 5.4_

- [x] 9. Write unit tests for WebSocket client enhancements
  - Update frontend-client-apps/shared/__tests__/WebSocketClient.test.ts
  - Test handleConnectionError() event emission
  - Test handleConnectionClose() with code 1008 (auth error)
  - Test handleConnectionClose() with code 1006 (connection failed)
  - Test handleConnectionClose() with code 1000 (normal closure)
  - Test reconnection logic
  - _Requirements: 6.1, 6.4_

- [x] 10. Write unit tests for SessionCreationOrchestrator enhancements
  - Update frontend-client-apps/shared/__tests__/SessionCreationOrchestrator.test.ts
  - Test token expiry check and refresh before connection
  - Test waitForConnection() success
  - Test waitForConnection() timeout
  - Test waitForConnection() auth error
  - Test retry logic on auth failure
  - Test error propagation
  - _Requirements: 6.2, 6.3, 6.5_

- [x] 11. Integration testing
  - Deploy updated Lambda authorizer to dev environment
  - Test WebSocket connection with valid ID token
  - Test WebSocket connection with expired token (should refresh and retry)
  - Test WebSocket connection with invalid token (should show error)
  - Test WebSocket connection with no token (should show error)
  - Verify detailed error logs in CloudWatch
  - Verify session creation works end-to-end
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 3.5_

- [x] 12. Update documentation
  - Create session-management/docs/WEBSOCKET_AUTH_FIX_SUMMARY.md
  - Document the root cause and solution
  - Document JWT validation process
  - Document error handling improvements
  - Add troubleshooting section for common auth issues
  - Update session-management/README.md with auth flow details
  - _Requirements: N/A (documentation)_

