# Cognito Direct Authentication Implementation

## Overview

This spec implements direct username/password authentication for the speaker app using AWS Cognito USER_PASSWORD_AUTH flow, replacing the non-functional OAuth2 Hosted UI approach.

## Problem Statement

The current OAuth2 implementation has multiple issues:
1. Cognito Hosted UI returns "Login pages unavailable" error
2. Complex configuration with domains, callbacks, and redirects
3. Difficult to debug and troubleshoot
4. Doesn't match the proven working implementation in service-translate

## Solution

Implement direct authentication using AWS SDK:
- Username/password login form in the app
- Direct API calls to Cognito using `InitiateAuthCommand`
- No redirects or external pages
- Simpler configuration and debugging
- Matches proven working pattern

## Benefits

✅ **Simpler**: No OAuth2 complexity, domains, or callbacks  
✅ **Proven**: Matches working service-translate implementation  
✅ **Better UX**: No redirects, stays in app  
✅ **Easier to Debug**: Direct API calls, clear error messages  
✅ **Faster**: Works immediately with current Cognito setup  

## Key Components

1. **CognitoAuthService** - AWS SDK integration for authentication
2. **LoginForm** - Username/password UI component
3. **AuthGuard** - Updated to use direct auth (no OAuth2)
4. **TokenStorage** - Reused existing encrypted storage

## Implementation Tasks

12 tasks total:
- 7 core implementation tasks
- 3 testing tasks
- 1 documentation task
- 1 end-to-end verification task

## Configuration Changes

**Removed** (OAuth2-specific):
- `VITE_COGNITO_DOMAIN`
- `VITE_COGNITO_REDIRECT_URI`
- `VITE_COGNITO_LOGOUT_URI`

**Kept** (still needed):
- `VITE_COGNITO_USER_POOL_ID`
- `VITE_COGNITO_CLIENT_ID`
- `VITE_AWS_REGION`

## Dependencies

**New**:
- `@aws-sdk/client-cognito-identity-provider` (~50KB gzipped)

**Reused**:
- Existing `TokenStorage` with encryption
- Existing `AuthError` utilities
- Existing `config` management

## Testing Strategy

- Unit tests for `CognitoAuthService`
- Unit tests for `LoginForm`
- Integration tests for full auth flow
- End-to-end manual testing

## Success Criteria

1. User can log in with username/password
2. Tokens stored securely and persist across refreshes
3. Auto-refresh works before token expiry
4. Clear error messages for all failure cases
5. All tests passing
6. No OAuth2 code remaining

## Timeline

Estimated: 2-3 hours for complete implementation and testing

## Files

- `requirements.md` - Detailed requirements with EARS format
- `design.md` - Technical design and architecture
- `tasks.md` - Step-by-step implementation tasks
- `README.md` - This file

## Next Steps

Ready to start implementation! Begin with Task 1: Install AWS SDK.
