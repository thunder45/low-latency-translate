# Design Document

## Overview

This design implements AWS Cognito authentication for the speaker app, replacing the placeholder JWT token with a proper authentication flow. The solution uses Cognito Hosted UI for login, secure token storage with encryption, automatic token refresh, and seamless integration with the existing session creation flow.

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        SpeakerApp                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. Check Authentication Status                      │  │
│  │  2. Redirect to Login if needed                      │  │
│  │  3. Get JWT Token from AuthService                   │  │
│  │  4. Create Session with Valid Token                  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      AuthService                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  • Initialize Cognito Client                         │  │
│  │  • Handle OAuth2 Flow                                │  │
│  │  • Store/Retrieve Encrypted Tokens                   │  │
│  │  • Refresh Tokens Automatically                      │  │
│  │  • Validate Token Expiration                         │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Cognito User Pool                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  • Hosted UI for Login                               │  │
│  │  • OAuth2 Authorization Code Flow                    │  │
│  │  • Issue JWT Tokens (ID, Access, Refresh)           │  │
│  │  • Token Refresh Endpoint                            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              SessionCreationOrchestrator                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  • Connect WebSocket with JWT Token                  │  │
│  │  • Token included in query parameter                 │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  Lambda Authorizer                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  • Validate JWT Signature                            │  │
│  │  • Check Token Expiration                            │  │
│  │  • Extract User Identity                             │  │
│  │  • Allow/Deny Connection                             │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Authentication Flow

```
┌──────────┐                                    ┌──────────┐
│  User    │                                    │ Cognito  │
└────┬─────┘                                    └────┬─────┘
     │                                                │
     │  1. Open Speaker App                          │
     │ ──────────────────────────────────────────>   │
     │                                                │
     │  2. Check for Valid Token                     │
     │ <──────────────────────────────────────────   │
     │                                                │
     │  3. No Valid Token - Redirect to Login        │
     │ ──────────────────────────────────────────>   │
     │                                                │
     │  4. Display Hosted UI                         │
     │ <──────────────────────────────────────────   │
     │                                                │
     │  5. Enter Credentials                         │
     │ ──────────────────────────────────────────>   │
     │                                                │
     │  6. Validate & Issue Tokens                   │
     │ <──────────────────────────────────────────   │
     │                                                │
     │  7. Redirect with Auth Code                   │
     │ <──────────────────────────────────────────   │
     │                                                │
     │  8. Exchange Code for Tokens                  │
     │ ──────────────────────────────────────────>   │
     │                                                │
     │  9. Return JWT Tokens                         │
     │ <──────────────────────────────────────────   │
     │                                                │
     │  10. Store Encrypted Tokens                   │
     │                                                │
     │  11. Create Session with JWT                  │
     │                                                │
```

## Components and Interfaces

### AuthService

**Purpose**: Manages Cognito authentication lifecycle

**Location**: `frontend-client-apps/shared/services/AuthService.ts`

**Interface**:
```typescript
interface AuthService {
  // Initialize service with Cognito config
  initialize(config: CognitoConfig): Promise<void>;
  
  // Check if user is authenticated
  isAuthenticated(): Promise<boolean>;
  
  // Get current valid JWT token (refreshes if needed)
  getIdToken(): Promise<string>;
  
  // Initiate login flow (redirects to Cognito Hosted UI)
  login(): Promise<void>;
  
  // Handle OAuth callback after login
  handleCallback(): Promise<AuthResult>;
  
  // Logout and clear tokens
  logout(): Promise<void>;
  
  // Manually refresh tokens
  refreshTokens(): Promise<void>;
  
  // Get user info
  getUserInfo(): Promise<UserInfo | null>;
}

interface CognitoConfig {
  userPoolId: string;
  clientId: string;
  region: string;
  redirectUri: string;
  logoutUri: string;
}

interface AuthResult {
  success: boolean;
  idToken?: string;
  accessToken?: string;
  refreshToken?: string;
  error?: string;
}

interface UserInfo {
  sub: string;
  email: string;
  email_verified: boolean;
  name?: string;
}
```

**Key Methods**:

1. **initialize()**: Sets up Cognito client with configuration
2. **isAuthenticated()**: Checks for valid stored tokens
3. **getIdToken()**: Returns valid ID token, refreshing if needed
4. **login()**: Redirects to Cognito Hosted UI
5. **handleCallback()**: Processes OAuth callback and exchanges code for tokens
6. **logout()**: Clears tokens and revokes Cognito session
7. **refreshTokens()**: Uses refresh token to get new ID/access tokens

### TokenStorage

**Purpose**: Securely store and retrieve encrypted tokens

**Location**: `frontend-client-apps/shared/services/TokenStorage.ts`

**Interface**:
```typescript
interface TokenStorage {
  // Store encrypted tokens
  storeTokens(tokens: Tokens): Promise<void>;
  
  // Retrieve and decrypt tokens
  getTokens(): Promise<Tokens | null>;
  
  // Clear all tokens
  clearTokens(): Promise<void>;
  
  // Check if tokens exist
  hasTokens(): boolean;
}

interface Tokens {
  idToken: string;
  accessToken: string;
  refreshToken: string;
  expiresAt: number; // Unix timestamp
}
```

**Implementation Details**:
- Uses existing `storage.ts` utility for encryption
- Stores tokens under key `cognito_tokens`
- Encrypts entire token object as JSON
- Validates encryption key on initialization

### AuthGuard Component

**Purpose**: Protect routes requiring authentication

**Location**: `frontend-client-apps/speaker-app/src/components/AuthGuard.tsx`

**Interface**:
```typescript
interface AuthGuardProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

const AuthGuard: React.FC<AuthGuardProps> = ({ children, fallback }) => {
  // Check authentication status
  // Show loading while checking
  // Redirect to login if not authenticated
  // Render children if authenticated
};
```

### Updated SpeakerApp Integration

**Changes to SpeakerApp.tsx**:

```typescript
// Before session creation
const handleCreateSession = async (config: SessionConfig): Promise<void> => {
  setIsCreatingSession(true);
  setCreationError(null);

  try {
    // Get AuthService instance
    const authService = AuthService.getInstance();
    
    // Check authentication
    const isAuth = await authService.isAuthenticated();
    if (!isAuth) {
      setCreationError('Please log in to create a session');
      await authService.login(); // Redirect to login
      return;
    }
    
    // Get valid JWT token (auto-refreshes if needed)
    const jwtToken = await authService.getIdToken();
    
    // Create orchestrator with real token
    const newOrchestrator = new SessionCreationOrchestrator({
      wsUrl: appConfig.websocketUrl,
      jwtToken, // Real JWT token from Cognito
      sourceLanguage: config.sourceLanguage,
      qualityTier: config.qualityTier,
      timeout: 5000,
      retryAttempts: 3,
    });
    
    // Continue with session creation...
  } catch (error) {
    // Handle auth errors
    if (error instanceof AuthError) {
      setCreationError('Authentication failed. Please log in again.');
      await authService.login();
    } else {
      setCreationError(error.message);
    }
  } finally {
    setIsCreatingSession(false);
  }
};
```

## Data Models

### Token Structure

```typescript
interface CognitoTokens {
  idToken: string;        // JWT for authentication
  accessToken: string;    // JWT for API access
  refreshToken: string;   // Long-lived token for refresh
  expiresAt: number;      // Unix timestamp when tokens expire
}
```

### Encrypted Storage Format

```typescript
// Stored in localStorage under key 'cognito_tokens'
{
  encrypted: "base64-encoded-encrypted-json",
  iv: "initialization-vector"
}
```

### JWT Token Claims

```typescript
interface IdTokenClaims {
  sub: string;              // User ID
  email: string;            // User email
  email_verified: boolean;  // Email verification status
  cognito:username: string; // Cognito username
  aud: string;              // Client ID
  iss: string;              // Issuer (Cognito User Pool)
  iat: number;              // Issued at
  exp: number;              // Expiration
}
```

## Error Handling

### Error Types

```typescript
class AuthError extends Error {
  code: string;
  
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
    this.name = 'AuthError';
  }
}

// Error codes
const AUTH_ERROR_CODES = {
  NOT_AUTHENTICATED: 'NOT_AUTHENTICATED',
  TOKEN_EXPIRED: 'TOKEN_EXPIRED',
  REFRESH_FAILED: 'REFRESH_FAILED',
  INVALID_TOKEN: 'INVALID_TOKEN',
  NETWORK_ERROR: 'NETWORK_ERROR',
  COGNITO_ERROR: 'COGNITO_ERROR',
  STORAGE_ERROR: 'STORAGE_ERROR',
};
```

### Error Handling Strategy

1. **Token Expired**: Automatically refresh using refresh token
2. **Refresh Failed**: Clear tokens and redirect to login
3. **Network Error**: Retry with exponential backoff (3 attempts)
4. **Invalid Token**: Clear tokens and redirect to login
5. **Storage Error**: Log error and treat as not authenticated

### User-Facing Error Messages

```typescript
const ERROR_MESSAGES = {
  NOT_AUTHENTICATED: 'Please log in to create a session',
  TOKEN_EXPIRED: 'Your session has expired. Please log in again.',
  REFRESH_FAILED: 'Failed to refresh authentication. Please log in again.',
  NETWORK_ERROR: 'Network error. Please check your connection and try again.',
  COGNITO_ERROR: 'Authentication service error. Please try again later.',
  UNKNOWN_ERROR: 'An unexpected error occurred. Please try again.',
};
```

## Testing Strategy

### Unit Tests

1. **AuthService Tests**:
   - Token storage and retrieval
   - Token expiration detection
   - Token refresh logic
   - Error handling for each scenario
   - Logout clears all tokens

2. **TokenStorage Tests**:
   - Encryption/decryption
   - Storage and retrieval
   - Clear tokens
   - Handle corrupted data

3. **AuthGuard Tests**:
   - Renders children when authenticated
   - Redirects when not authenticated
   - Shows loading state during check

### Integration Tests

1. **Authentication Flow**:
   - Complete login flow (mocked Cognito)
   - Token refresh flow
   - Logout flow
   - Session creation with valid token

2. **Error Scenarios**:
   - Expired token triggers refresh
   - Failed refresh triggers login
   - Network errors are retried
   - Invalid tokens are cleared

### Manual Testing

1. **Happy Path**:
   - First-time login
   - Create session with authenticated token
   - Token persists across page refresh
   - Automatic token refresh

2. **Error Cases**:
   - Login cancellation
   - Network disconnection during auth
   - Token expiration during session
   - Logout and re-login

## Security Considerations

### Token Storage

- Tokens encrypted using AES-256-GCM
- Encryption key from environment variable (min 32 chars)
- Tokens stored in localStorage (encrypted)
- Tokens cleared on logout or error

### Token Transmission

- JWT token sent in WebSocket URL query parameter
- Connection uses WSS (TLS encryption)
- Lambda Authorizer validates token signature
- Token not logged or exposed in console

### Token Lifecycle

- ID token expires after 1 hour (Cognito default)
- Refresh token expires after 30 days (Cognito default)
- Automatic refresh when token within 5 minutes of expiration
- Proactive refresh prevents connection failures

### Best Practices

1. Never log tokens or token contents
2. Clear tokens on any authentication error
3. Use HTTPS/WSS for all communication
4. Validate token expiration before use
5. Implement token refresh before expiration

## Configuration

### Environment Variables

```bash
# Cognito Configuration
VITE_COGNITO_USER_POOL_ID=us-east-1_WoaXmyQLQ
VITE_COGNITO_CLIENT_ID=38t8057tbi0o6873qt441kuo3n
VITE_AWS_REGION=us-east-1

# OAuth Redirect URIs
VITE_COGNITO_REDIRECT_URI=http://localhost:3000/callback
VITE_COGNITO_LOGOUT_URI=http://localhost:3000/

# Encryption Key (32+ characters)
VITE_ENCRYPTION_KEY=your-secure-32-character-key-here
```

### Cognito User Pool Settings

**App Client Settings**:
- Enabled Identity Providers: Cognito User Pool
- Callback URLs: `http://localhost:3000/callback`, `https://your-domain.com/callback`
- Sign out URLs: `http://localhost:3000/`, `https://your-domain.com/`
- OAuth 2.0 Flows: Authorization code grant
- OAuth Scopes: openid, email, profile

**Domain**:
- Use Cognito domain or custom domain
- Format: `https://{domain}.auth.{region}.amazoncognito.com`

## Performance Considerations

### Token Refresh Strategy

- Proactive refresh at 5 minutes before expiration
- Prevents connection failures during session creation
- Background refresh doesn't block user actions

### Caching

- AuthService singleton pattern
- Tokens cached in memory after decryption
- Reduces localStorage access overhead

### Lazy Loading

- AuthService loaded only when needed
- Cognito SDK loaded on-demand
- Reduces initial bundle size

## Deployment Considerations

### Environment-Specific Configuration

**Development**:
- Redirect URI: `http://localhost:3000/callback`
- Logout URI: `http://localhost:3000/`

**Staging**:
- Redirect URI: `https://staging.your-domain.com/callback`
- Logout URI: `https://staging.your-domain.com/`

**Production**:
- Redirect URI: `https://your-domain.com/callback`
- Logout URI: `https://your-domain.com/`

### Migration Strategy

1. Deploy AuthService and TokenStorage
2. Update SpeakerApp to use AuthService
3. Test authentication flow in staging
4. Deploy to production
5. Monitor authentication success rate

## Alternatives Considered

### Alternative 1: Custom Login UI

**Pros**:
- Full control over UI/UX
- Branded experience
- Custom validation

**Cons**:
- More development effort
- Need to handle password security
- Need to implement MFA
- Need to handle password reset

**Decision**: Use Cognito Hosted UI for faster implementation and better security

### Alternative 2: Store Tokens Unencrypted

**Pros**:
- Simpler implementation
- Faster access

**Cons**:
- Security risk if XSS vulnerability exists
- Doesn't follow security best practices

**Decision**: Encrypt tokens for defense in depth

### Alternative 3: Session Storage Instead of Local Storage

**Pros**:
- Cleared on tab close
- More secure for shared computers

**Cons**:
- User must log in every time
- Poor user experience

**Decision**: Use localStorage with encryption for better UX

## Open Questions

1. **MFA Support**: Should we enable MFA for speakers?
   - Recommendation: Enable as optional in v1.1

2. **Social Login**: Should we support Google/Facebook login?
   - Recommendation: Add in v2.0 if user feedback requests it

3. **Remember Me**: Should we extend refresh token lifetime?
   - Recommendation: Keep default 30 days for security

4. **Password Policy**: What password requirements should we enforce?
   - Recommendation: Use Cognito defaults (8+ chars, uppercase, lowercase, number)
