# Requirements Document

## Introduction

Implement direct username/password authentication for the speaker app using AWS Cognito USER_PASSWORD_AUTH flow, matching the proven working implementation in service-translate.

## Glossary

- **USER_PASSWORD_AUTH**: AWS Cognito authentication flow that allows direct username/password authentication without hosted UI
- **InitiateAuthCommand**: AWS SDK command for initiating Cognito authentication
- **ID Token**: JWT token containing user identity claims, used for AWS service authentication
- **Access Token**: JWT token for accessing Cognito User Pool resources
- **Refresh Token**: Long-lived token for obtaining new access/ID tokens
- **CognitoIdentityProviderClient**: AWS SDK client for Cognito User Pool operations

## Requirements

### Requirement 1: Direct Username/Password Authentication

**User Story:** As a speaker, I want to log in with my username and password directly in the app, so that I can authenticate without being redirected to external pages

#### Acceptance Criteria

1. WHEN the speaker app loads, THE Speaker App SHALL display a login form with username and password fields
2. WHEN the speaker enters valid credentials and clicks login, THE Speaker App SHALL authenticate using AWS Cognito USER_PASSWORD_AUTH flow
3. WHEN authentication succeeds, THE Speaker App SHALL store the access token, ID token, and refresh token securely
4. WHEN authentication fails, THE Speaker App SHALL display a clear error message to the user
5. WHEN the speaker is already authenticated, THE Speaker App SHALL skip the login form and show the main application

### Requirement 2: AWS SDK Integration

**User Story:** As a developer, I want to use the AWS Cognito Identity Provider SDK directly, so that I can authenticate users without the hosted UI

#### Acceptance Criteria

1. THE Speaker App SHALL use @aws-sdk/client-cognito-identity-provider package
2. WHEN authenticating, THE Speaker App SHALL use InitiateAuthCommand with USER_PASSWORD_AUTH flow
3. WHEN tokens expire, THE Speaker App SHALL use InitiateAuthCommand with REFRESH_TOKEN_AUTH flow
4. THE Speaker App SHALL handle NEW_PASSWORD_REQUIRED challenge by displaying an appropriate error
5. THE Speaker App SHALL handle NotAuthorizedException by displaying "Invalid username or password"

### Requirement 3: Token Management

**User Story:** As a speaker, I want my session to persist across browser refreshes, so that I don't have to log in repeatedly

#### Acceptance Criteria

1. WHEN authentication succeeds, THE Speaker App SHALL store tokens in encrypted localStorage
2. WHEN the app loads, THE Speaker App SHALL check for stored tokens and validate them
3. WHEN tokens are close to expiry (within 5 minutes), THE Speaker App SHALL automatically refresh them using the refresh token
4. WHEN the speaker logs out, THE Speaker App SHALL clear all stored tokens
5. WHEN token refresh fails, THE Speaker App SHALL log the user out and show the login form

### Requirement 4: Login UI

**User Story:** As a speaker, I want a clean and accessible login interface, so that I can easily authenticate

#### Acceptance Criteria

1. THE Speaker App SHALL display a login form with username and password input fields
2. WHEN the speaker presses Enter in either field, THE Speaker App SHALL submit the login form
3. WHEN authentication is in progress, THE Speaker App SHALL disable the login button and show a loading indicator
4. THE Speaker App SHALL display authentication errors below the login form
5. THE Speaker App SHALL follow accessibility best practices for form inputs and labels

### Requirement 5: Error Handling

**User Story:** As a speaker, I want clear error messages when authentication fails, so that I know what went wrong

#### Acceptance Criteria

1. WHEN credentials are invalid, THE Speaker App SHALL display "Invalid username or password"
2. WHEN network errors occur, THE Speaker App SHALL display "Network error. Please check your connection."
3. WHEN password change is required, THE Speaker App SHALL display "Password change required. Please contact administrator."
4. WHEN Cognito is not configured, THE Speaker App SHALL display "Authentication not configured"
5. THE Speaker App SHALL log detailed errors to console for debugging

### Requirement 6: Security

**User Story:** As a developer, I want to implement authentication securely, so that user credentials are protected

#### Acceptance Criteria

1. THE Speaker App SHALL use HTTPS for all production deployments
2. THE Speaker App SHALL encrypt tokens before storing in localStorage
3. THE Speaker App SHALL never log passwords or tokens in production
4. THE Speaker App SHALL clear sensitive data from memory after use
5. THE Speaker App SHALL validate token expiry before using stored tokens
