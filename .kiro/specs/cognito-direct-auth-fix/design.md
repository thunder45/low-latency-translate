# Design Document

## Overview

Implement direct username/password authentication using AWS Cognito USER_PASSWORD_AUTH flow. This approach eliminates OAuth2 complexity and matches the proven working implementation in service-translate.

## Architecture

### High-Level Flow

```
┌─────────────┐
│ Speaker App │
│   Loads     │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ Check Stored    │
│ Tokens          │
└────┬────────┬───┘
     │        │
     │ Valid  │ Invalid/Missing
     │        │
     ▼        ▼
┌─────────┐  ┌──────────────┐
│  Main   │  │ Login Form   │
│  App    │  │              │
└─────────┘  └──────┬───────┘
                    │
                    │ Submit
                    ▼
             ┌──────────────────┐
             │ CognitoAuthService│
             │ InitiateAuth     │
             │ USER_PASSWORD    │
             └────────┬─────────┘
                      │
                      ▼
             ┌──────────────────┐
             │ AWS Cognito      │
             │ User Pool        │
             └────────┬─────────┘
                      │
                      ▼
             ┌──────────────────┐
             │ Return Tokens    │
             │ - Access Token   │
             │ - ID Token       │
             │ - Refresh Token  │
             └────────┬─────────┘
                      │
                      ▼
             ┌──────────────────┐
             │ TokenStorage     │
             │ (Encrypted)      │
             └────────┬─────────┘
                      │
                      ▼
             ┌──────────────────┐
             │ Navigate to      │
             │ Main App         │
             └──────────────────┘
```

## Components and Interfaces

### 1. CognitoAuthService

**Purpose**: Handle direct Cognito authentication using AWS SDK

**Location**: `frontend-client-apps/shared/services/CognitoAuthService.ts`

**Interface**:
```typescript
interface CognitoAuthService {
  login(username: string, password: string): Promise<AuthTokens>;
  refreshTokens(refreshToken: string): Promise<AuthTokens>;
  logout(): Promise<void>;
}

interface AuthTokens {
  accessToken: string;
  idToken: string;
  refreshToken: string;
  expiresIn: number;
}
```

**Dependencies**:
- `@aws-sdk/client-cognito-identity-provider`
- `TokenStorage` (existing)
- `config` (existing)

**Key Methods**:

1. **login(username, password)**
   - Creates `CognitoIdentityProviderClient`
   - Sends `InitiateAuthCommand` with `USER_PASSWORD_AUTH`
   - Handles `NEW_PASSWORD_REQUIRED` challenge
   - Returns tokens or throws `AuthError`

2. **refreshTokens(refreshToken)**
   - Sends `InitiateAuthCommand` with `REFRESH_TOKEN_AUTH`
   - Returns new access and ID tokens
   - Throws `AuthError` if refresh fails

3. **logout()**
   - Clears stored tokens
   - Resets authentication state

### 2. LoginForm Component

**Purpose**: UI for username/password input

**Location**: `frontend-client-apps/speaker-app/src/components/LoginForm.tsx`

**Interface**:
```typescript
interface LoginFormProps {
  onLoginSuccess: () => void;
}
```

**Features**:
- Username input field
- Password input field (type="password")
- Login button with loading state
- Error message display
- Enter key submission
- Accessibility labels and ARIA attributes

### 3. AuthGuard Component (Update)

**Purpose**: Protect routes and manage authentication state

**Location**: `frontend-client-apps/speaker-app/src/components/AuthGuard.tsx` (existing)

**Changes**:
- Remove OAuth2 redirect logic
- Check for stored tokens on mount
- Show LoginForm if not authenticated
- Auto-refresh tokens when close to expiry

### 4. Remove OAuth2 Components

**Components to Remove**:
- `CallbackPage.tsx` - No longer needed
- OAuth2-specific code in `AuthService.ts`

**Routes to Remove**:
- `/callback` route

## Data Models

### AuthTokens

```typescript
interface AuthTokens {
  accessToken: string;      // JWT for API access
  idToken: string;          // JWT for user identity
  refreshToken: string;     // Long-lived token for refresh
  expiresIn: number;        // Seconds until expiry
}
```

### StoredTokens (Existing)

```typescript
interface StoredTokens {
  accessToken: string;
  idToken: string;
  refreshToken: string;
  expiresAt: Date;
}
```

### LoginFormState

```typescript
interface LoginFormState {
  username: string;
  password: string;
  isLoading: boolean;
  error: string | null;
}
```

## Error Handling

### Error Types

1. **NotAuthorizedException**
   - User message: "Invalid username or password"
   - Action: Allow retry

2. **UserNotFoundException**
   - User message: "Invalid username or password" (same as above for security)
   - Action: Allow retry

3. **NEW_PASSWORD_REQUIRED**
   - User message: "Password change required. Please contact administrator."
   - Action: Show contact info

4. **NetworkError**
   - User message: "Network error. Please check your connection."
   - Action: Allow retry

5. **ConfigurationError**
   - User message: "Authentication not configured"
   - Action: Show configuration instructions

### Error Handling Flow

```typescript
try {
  const tokens = await cognitoAuthService.login(username, password);
  await tokenStorage.storeTokens(tokens);
  onLoginSuccess();
} catch (error) {
  if (error instanceof AuthError) {
    setError(error.userMessage);
  } else {
    setError('An unexpected error occurred. Please try again.');
    console.error('Login error:', error);
  }
}
```

## Testing Strategy

### Unit Tests

1. **CognitoAuthService**
   - Mock `CognitoIdentityProviderClient`
   - Test successful login
   - Test invalid credentials
   - Test token refresh
   - Test error handling

2. **LoginForm**
   - Test form submission
   - Test Enter key handling
   - Test loading states
   - Test error display
   - Test accessibility

3. **AuthGuard**
   - Test with valid tokens
   - Test with expired tokens
   - Test with no tokens
   - Test auto-refresh

### Integration Tests

1. **End-to-End Login Flow**
   - Load app → See login form
   - Enter credentials → Authenticate
   - Store tokens → Navigate to main app
   - Refresh page → Stay authenticated

2. **Token Refresh Flow**
   - Login → Wait for near-expiry
   - Auto-refresh → Continue using app

3. **Logout Flow**
   - Logout → Clear tokens
   - Redirect to login form

## Configuration

### Environment Variables

Update `.env` to remove OAuth2 config:

```env
# AWS Cognito Configuration
VITE_COGNITO_USER_POOL_ID=us-east-1_WoaXmyQLQ
VITE_COGNITO_CLIENT_ID=38t8057tbi0o6873qt441kuo3n
VITE_AWS_REGION=us-east-1

# WebSocket API Endpoint
VITE_WEBSOCKET_URL=wss://vphqnkfxtf.execute-api.us-east-1.amazonaws.com/prod

# Security
VITE_ENCRYPTION_KEY=dev-encryption-key-for-local-testing-only-32chars
```

**Removed**:
- `VITE_COGNITO_DOMAIN`
- `VITE_COGNITO_REDIRECT_URI`
- `VITE_COGNITO_LOGOUT_URI`

### Config Utility Update

```typescript
// frontend-client-apps/shared/utils/config.ts
export const config = {
  cognito: {
    userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID,
    clientId: import.meta.env.VITE_COGNITO_CLIENT_ID,
    region: import.meta.env.VITE_AWS_REGION,
  },
  websocket: {
    url: import.meta.env.VITE_WEBSOCKET_URL,
  },
  encryption: {
    key: import.meta.env.VITE_ENCRYPTION_KEY,
  },
};
```

## Security Considerations

### Token Storage

- Use existing `TokenStorage` with AES-256-GCM encryption
- Store in localStorage (encrypted)
- Clear on logout

### Password Handling

- Never log passwords
- Use `type="password"` input
- Clear password from memory after use
- Use HTTPS in production

### Token Refresh

- Refresh 5 minutes before expiry
- Use refresh token (not stored in URL)
- Handle refresh failures gracefully

### HTTPS Requirement

- All production deployments MUST use HTTPS
- Development can use HTTP localhost

## Performance Considerations

### Initial Load

- Check stored tokens synchronously
- Validate expiry client-side (no API call)
- Only call Cognito if tokens missing/expired

### Token Refresh

- Set timer for auto-refresh
- Refresh in background (no UI blocking)
- Cancel timer on logout

### Bundle Size

- AWS SDK is tree-shakeable
- Only import needed commands
- Estimated addition: ~50KB gzipped

## Migration from OAuth2

### Steps

1. Install AWS SDK package
2. Create `CognitoAuthService`
3. Create `LoginForm` component
4. Update `AuthGuard` to use new service
5. Remove `CallbackPage` and OAuth2 code
6. Update `.env` files
7. Update tests
8. Test end-to-end flow

### Backward Compatibility

- Existing `TokenStorage` works as-is
- No changes to WebSocket authentication
- No changes to session management

## Dependencies

### New Dependencies

```json
{
  "@aws-sdk/client-cognito-identity-provider": "^3.0.0"
}
```

### Existing Dependencies (Reused)

- `TokenStorage` - Token encryption and storage
- `AuthError` - Error handling utilities
- `config` - Configuration management

## API Reference

### CognitoAuthService

```typescript
class CognitoAuthService {
  constructor(config: CognitoConfig);
  
  async login(username: string, password: string): Promise<AuthTokens>;
  async refreshTokens(refreshToken: string): Promise<AuthTokens>;
  async logout(): Promise<void>;
}
```

### LoginForm

```typescript
interface LoginFormProps {
  onLoginSuccess: () => void;
}

function LoginForm({ onLoginSuccess }: LoginFormProps): JSX.Element;
```

### AuthGuard (Updated)

```typescript
interface AuthGuardProps {
  children: React.ReactNode;
}

function AuthGuard({ children }: AuthGuardProps): JSX.Element;
```

## Deployment Considerations

### Environment-Specific Config

- **Development**: Use localhost, HTTP allowed
- **Staging**: Use staging Cognito, HTTPS required
- **Production**: Use production Cognito, HTTPS required

### Rollback Plan

If issues arise:
1. Revert to previous OAuth2 implementation
2. Re-enable Cognito Hosted UI
3. Restore callback URLs

### Monitoring

- Log authentication attempts (success/failure)
- Monitor token refresh failures
- Track login errors by type

## Future Enhancements

### Phase 2 (Optional)

1. **Password Reset Flow**
   - Add "Forgot Password" link
   - Implement custom password reset UI
   - Use Cognito ForgotPassword API

2. **MFA Support**
   - Handle MFA challenges
   - Add MFA setup UI

3. **Remember Me**
   - Extend token validity
   - Persistent login option

4. **Social Login**
   - Add Google/Facebook login
   - Federated identity support

## Success Criteria

1. ✅ User can log in with username/password
2. ✅ Tokens are stored securely
3. ✅ Session persists across page refreshes
4. ✅ Tokens auto-refresh before expiry
5. ✅ Clear error messages for all failure cases
6. ✅ No OAuth2 complexity or redirects
7. ✅ All tests passing
8. ✅ Matches service-translate implementation pattern
