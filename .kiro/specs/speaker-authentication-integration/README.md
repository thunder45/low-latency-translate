# Speaker Authentication Integration Spec

## Overview

This spec implements AWS Cognito authentication for the speaker app to replace the placeholder JWT token with proper authentication. The speaker app currently fails to create sessions because it uses `'placeholder-jwt-token'` instead of a real JWT token from Cognito.

## Problem Statement

The speaker app's session creation is failing with WebSocket connection errors:

```
WebSocket connection to 'wss://vphqnkfxtf.execute-api.us-east-1.amazonaws.com/prod?token=placeholder-jwt-token' failed
```

**Root Cause**: The `SpeakerApp.tsx` component uses a hardcoded placeholder token instead of obtaining a real JWT token from AWS Cognito:

```typescript
const jwtToken = 'placeholder-jwt-token'; // TODO: Get from AuthService
```

The Lambda Authorizer rejects this invalid token, causing the WebSocket connection to fail.

## Solution

Implement a complete Cognito authentication flow:

1. **AuthService**: Manages Cognito authentication lifecycle
2. **TokenStorage**: Securely stores encrypted tokens in localStorage
3. **AuthGuard**: Protects routes requiring authentication
4. **OAuth Callback**: Handles Cognito Hosted UI callback
5. **SpeakerApp Integration**: Uses real JWT tokens for session creation

## Key Features

- **Cognito Hosted UI**: Leverages AWS-managed login page
- **Secure Token Storage**: Encrypts tokens before storing in localStorage
- **Automatic Token Refresh**: Refreshes tokens before expiration
- **Error Handling**: User-friendly error messages for auth failures
- **Seamless Integration**: Minimal changes to existing session creation flow

## Architecture

```
User → AuthGuard → AuthService → Cognito → JWT Token → SessionCreationOrchestrator → WebSocket
```

## Documents

- [requirements.md](./requirements.md) - User stories and acceptance criteria
- [design.md](./design.md) - Technical design and architecture
- [tasks.md](./tasks.md) - Implementation task list

## Implementation Status

- [ ] Requirements defined
- [ ] Design completed
- [ ] Tasks created
- [ ] Implementation in progress
- [ ] Testing completed
- [ ] Documentation updated
- [ ] Deployed to staging
- [ ] Deployed to production

## Dependencies

- AWS Cognito User Pool (already configured)
- Existing encryption utilities (`storage.ts`)
- Existing WebSocket client
- Existing session creation orchestrator

## Testing Strategy

1. **Unit Tests**: AuthService, TokenStorage, AuthGuard
2. **Integration Tests**: Complete authentication flow, session creation with auth
3. **Manual Tests**: Login, logout, token refresh, error scenarios

## Deployment Notes

- Requires Cognito redirect URIs to be configured
- Environment variables must be updated with OAuth URIs
- No backend changes required (Lambda Authorizer already validates JWT)

## Success Criteria

- [ ] Speaker can log in using Cognito Hosted UI
- [ ] JWT token is obtained and stored securely
- [ ] Session creation succeeds with valid JWT token
- [ ] WebSocket connection is authorized by Lambda Authorizer
- [ ] Token automatically refreshes before expiration
- [ ] User can log out and tokens are cleared
- [ ] All tests passing

## Related Specs

- [session-management](../session-management/) - WebSocket connection and Lambda Authorizer
- [frontend-client-apps](../frontend-client-apps/) - Speaker and listener applications
- [speaker-session-creation-fix](../speaker-session-creation-fix/) - Previous session creation improvements

## Timeline

**Estimated Duration**: 3-4 days

- Day 1: TokenStorage and AuthService implementation
- Day 2: AuthGuard, callback page, and SpeakerApp integration
- Day 3: Testing and error handling
- Day 4: Documentation and deployment

## Notes

- This spec focuses on speaker authentication only
- Listeners remain anonymous (no authentication required)
- Uses existing Cognito User Pool from staging deployment
- Leverages existing encryption utilities for token storage
- No changes to backend Lambda Authorizer required
