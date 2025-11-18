# Requirements Document

## Introduction

Fix WebSocket connection failures that occur after successful Cognito authentication. The speaker app successfully authenticates and obtains valid JWT tokens, but the WebSocket connection to the API Gateway is being rejected by the Lambda authorizer.

## Glossary

- **Lambda Authorizer**: AWS Lambda function that validates JWT tokens for API Gateway WebSocket connections
- **JWT Token**: JSON Web Token containing user identity and claims, signed by Cognito
- **ID Token**: JWT token from Cognito containing user identity claims, used for WebSocket authentication
- **Token Validation**: Process of verifying JWT signature, expiration, issuer, and audience
- **API Gateway WebSocket**: AWS service managing persistent bidirectional connections
- **Connection Context**: Data passed from authorizer to WebSocket route handlers

## Requirements

### Requirement 1: WebSocket Connection Success

**User Story:** As a speaker, I want to successfully connect to the WebSocket after logging in, so that I can create and manage broadcast sessions

#### Acceptance Criteria

1. WHEN the speaker logs in successfully, THE Speaker App SHALL obtain valid JWT tokens from Cognito
2. WHEN the speaker attempts to create a session, THE Speaker App SHALL connect to the WebSocket with the ID token as a query parameter
3. WHEN the Lambda authorizer receives the connection request, THE Lambda Authorizer SHALL validate the JWT token signature
4. WHEN the token is valid, THE Lambda Authorizer SHALL allow the WebSocket connection
5. WHEN the token is invalid or expired, THE Lambda Authorizer SHALL reject the connection with a clear error message

### Requirement 2: JWT Token Validation

**User Story:** As a system, I want to properly validate JWT tokens from Cognito, so that only authenticated users can connect

#### Acceptance Criteria

1. THE Lambda Authorizer SHALL verify the JWT signature using Cognito's public keys (JWKS)
2. THE Lambda Authorizer SHALL verify the token issuer matches the Cognito User Pool
3. THE Lambda Authorizer SHALL verify the token audience (aud claim) matches the Cognito Client ID
4. THE Lambda Authorizer SHALL verify the token has not expired
5. THE Lambda Authorizer SHALL extract the user ID (sub claim) and pass it to connection handlers

### Requirement 3: Error Diagnosis and Logging

**User Story:** As a developer, I want detailed error logs when WebSocket connections fail, so that I can diagnose authentication issues

#### Acceptance Criteria

1. WHEN token validation fails, THE Lambda Authorizer SHALL log the specific validation failure reason
2. WHEN the JWT signature is invalid, THE Lambda Authorizer SHALL log "Invalid JWT signature"
3. WHEN the token is expired, THE Lambda Authorizer SHALL log "Token expired" with expiration time
4. WHEN the issuer is incorrect, THE Lambda Authorizer SHALL log "Invalid issuer" with expected and actual values
5. THE Lambda Authorizer SHALL NOT log the full token or sensitive data in production

### Requirement 4: Token Format Compatibility

**User Story:** As a system, I want to accept tokens in multiple formats, so that the authentication flow is flexible

#### Acceptance Criteria

1. THE Speaker App SHALL send the ID token as a query parameter named "token"
2. THE Lambda Authorizer SHALL accept tokens from the query string parameter "token"
3. THE Lambda Authorizer SHALL accept tokens from the Authorization header (Bearer format) as a fallback
4. WHEN no token is provided, THE Lambda Authorizer SHALL reject the connection with "Missing authentication token"
5. WHEN the token format is invalid, THE Lambda Authorizer SHALL reject the connection with "Invalid token format"

### Requirement 5: Cognito Configuration Validation

**User Story:** As a developer, I want to ensure Cognito is properly configured, so that authentication works correctly

#### Acceptance Criteria

1. THE Lambda Authorizer SHALL validate that COGNITO_USER_POOL_ID environment variable is set
2. THE Lambda Authorizer SHALL validate that COGNITO_CLIENT_ID environment variable is set
3. THE Lambda Authorizer SHALL validate that AWS_REGION environment variable is set
4. WHEN configuration is missing, THE Lambda Authorizer SHALL log "Missing Cognito configuration" and reject connections
5. THE Lambda Authorizer SHALL cache Cognito public keys (JWKS) for performance

### Requirement 6: Frontend Error Handling

**User Story:** As a speaker, I want clear error messages when WebSocket connection fails, so that I know what to do

#### Acceptance Criteria

1. WHEN the WebSocket connection is rejected, THE Speaker App SHALL display an error message
2. WHEN the error is due to expired token, THE Speaker App SHALL attempt to refresh the token and retry
3. WHEN token refresh fails, THE Speaker App SHALL redirect to the login page
4. WHEN the error is due to network issues, THE Speaker App SHALL display "Connection failed. Please check your network."
5. THE Speaker App SHALL log detailed error information to the console for debugging

