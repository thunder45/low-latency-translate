# Requirements Document

## Introduction

The speaker app currently uses a placeholder JWT token (`'placeholder-jwt-token'`) when creating WebSocket connections, causing authentication failures. This spec addresses the integration of AWS Cognito authentication to obtain valid JWT tokens for authenticated speaker sessions.

## Glossary

- **Cognito User Pool**: AWS service for user authentication and management
- **JWT Token**: JSON Web Token used for authenticating WebSocket connections
- **AuthService**: Service responsible for managing Cognito authentication flow
- **SpeakerApp**: React component that orchestrates speaker session creation
- **SessionCreationOrchestrator**: Utility that manages WebSocket connection and session creation
- **Lambda Authorizer**: AWS Lambda function that validates JWT tokens on WebSocket $connect

## Requirements

### Requirement 1: Cognito Authentication Service

**User Story:** As a speaker, I want to authenticate with my credentials so that I can create secure broadcast sessions

#### Acceptance Criteria

1. WHEN THE SpeakerApp initializes, THE AuthService SHALL check for existing valid authentication
2. WHEN no valid authentication exists, THE AuthService SHALL redirect to Cognito hosted UI for login
3. WHEN authentication succeeds, THE AuthService SHALL store JWT tokens securely in encrypted localStorage
4. WHEN JWT token expires, THE AuthService SHALL automatically refresh using refresh token
5. WHEN refresh fails, THE AuthService SHALL redirect to login

### Requirement 2: Token Management

**User Story:** As a speaker, I want my authentication to persist across sessions so that I don't have to log in repeatedly

#### Acceptance Criteria

1. WHEN THE AuthService stores tokens, THE System SHALL encrypt tokens using configured encryption key
2. WHEN THE AuthService retrieves tokens, THE System SHALL decrypt and validate token expiration
3. WHEN token is within 5 minutes of expiration, THE AuthService SHALL proactively refresh
4. WHEN user logs out, THE AuthService SHALL clear all stored tokens and revoke Cognito session
5. WHEN token validation fails, THE AuthService SHALL clear invalid tokens and require re-authentication

### Requirement 3: Session Creation Integration

**User Story:** As a speaker, I want session creation to use my authenticated token so that my WebSocket connection is authorized

#### Acceptance Criteria

1. WHEN THE SpeakerApp creates session, THE System SHALL obtain valid JWT token from AuthService
2. WHEN JWT token is unavailable, THE System SHALL prevent session creation and show authentication error
3. WHEN JWT token is expired, THE AuthService SHALL refresh before session creation
4. WHEN SessionCreationOrchestrator connects WebSocket, THE System SHALL include JWT token in connection URL
5. WHEN Lambda Authorizer validates token, THE WebSocket connection SHALL succeed

### Requirement 4: Error Handling

**User Story:** As a speaker, I want clear error messages when authentication fails so that I know how to resolve the issue

#### Acceptance Criteria

1. WHEN authentication fails, THE System SHALL display user-friendly error message
2. WHEN token refresh fails, THE System SHALL prompt user to log in again
3. WHEN network error occurs during auth, THE System SHALL retry with exponential backoff
4. WHEN Cognito service is unavailable, THE System SHALL display service unavailable message
5. WHEN user cancels login, THE System SHALL return to session creator with cancellation message

### Requirement 5: Security

**User Story:** As a system administrator, I want authentication tokens to be stored securely so that user credentials are protected

#### Acceptance Criteria

1. THE AuthService SHALL encrypt all tokens before storing in localStorage
2. THE AuthService SHALL use configured encryption key from environment variables
3. THE AuthService SHALL validate encryption key length is at least 32 characters
4. THE AuthService SHALL clear tokens on logout or authentication failure
5. THE AuthService SHALL NOT log or expose tokens in console or error messages
