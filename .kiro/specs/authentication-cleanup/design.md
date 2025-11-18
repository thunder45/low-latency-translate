# Authentication Cleanup - Design Document

## Overview

This design document outlines the technical approach for cleaning up and hardening the authentication system following the migration from OAuth2 Hosted UI to direct username/password authentication. The cleanup addresses orphaned code, test coverage gaps, security vulnerabilities, and code quality issues.

### Goals

1. Remove all orphaned OAuth2 code to reduce maintenance burden
2. Achieve 90%+ test coverage for security-critical authentication components
3. Implement security best practices (PBKDF2, concurrent refresh protection)
4. Fix known bugs in token expiry calculation and WebSocket state management
5. Improve code quality through constants extraction and static imports
6. Enhance observability with structured logging

### Non-Goals

1. Changing the authentication flow (already migrated to direct auth)
2. Adding new authentication features
3. Modifying the Lambda authorizer's JWT validation logic (already correct)
4. Changing the UI/UX of login components

## Architecture

### Current Authentication Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Speaker Application                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐      ┌─────────────────┐                 │
│  │  LoginForm   │─────▶│ CognitoAuth     │                 │
│  │              │      │ Service         │                 │
│  └──────────────┘      └────────┬────────┘                 │
│                                  │                           │
│                                  ▼                           │
│                         ┌────────────────┐                  │
│                         │ TokenStorage   │                  │
│                         │ (AES-256-GCM)  │                  │
│                         └────────┬───────┘                  │
│                                  │                           │
│  ┌──────────────┐               │                           │
│  │  AuthGuard   │◀──────────────┘                           │
│  │              │                                            │
│  └──────┬───────┘                                            │
│         │                                                     │
└─────────┼─────────────────────────────────────────────────────┘
          │
          │ WebSocket + JWT
          ▼
┌─────────────────────────────────────────────────────────────┐
│              AWS API Gateway WebSocket API                   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  $connect ──▶ Lambda Authorizer                             │
│               │                                               │
│               ├─ Extract JWT from query string              │
│               ├─ Validate JWT signature (JWKS)              │
│               ├─ Check expiration                            │
│               └─ Return IAM policy                           │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Components Overview

| Component | Purpose | Current State | Cleanup Action |
|-----------|---------|---------------|----------------|
| **AuthService.ts** | OAuth2 Hosted UI | Orphaned (0 refs) | DELETE |
| **CognitoAuthService.ts** | Direct auth | Active, tested | Keep as-is |
| **TokenStorage.ts** | Token encryption | Active, UNTESTED | Add tests |
| **AuthGuard.tsx** | Route protection | Active, UNTESTED | Add tests |
| **AuthError.ts** | Error handling | Active, UNTESTED | Add tests |
| **Lambda Authorizer** | JWT validation | Active, tested | Improve logging |
| **SessionCreationOrchestrator.ts** | Session setup | Active, has bugs | Fix bugs |

## Sequence Diagrams

### Token Refresh Flow

```
┌──────────┐         ┌──────────────┐         ┌────────────────────┐
│AuthGuard │         │TokenStorage  │         │CognitoAuthService  │
└────┬─────┘         └──────┬───────┘         └─────────┬──────────┘
     │                      │                           │
     │ checkAuth()          │                           │
     ├─────────────────────>│                           │
     │                      │                           │
     │ tokens.expiresAt     │                           │
     │<─────────────────────┤                           │
     │                      │                           │
     │ timeUntilExpiry < 5min                           │
     │                      │                           │
     │ refreshTokens()                                  │
     ├──────────────────────────────────────────────────>│
     │                      │                           │
     │                      │ newTokens                 │
     │<──────────────────────────────────────────────────┤
     │                      │                           │
     │ storeTokens(new)     │                           │
     ├─────────────────────>│                           │
     │                      │                           │
     │ success              │                           │
     │<─────────────────────┤                           │
     │                      │                           │
     │ scheduleNextRefresh()│                           │
     │                      │                           │
```

### Authentication Error Flow

```
┌──────────┐    ┌──────────────┐    ┌────────────────────┐    ┌──────────┐
│LoginForm │    │CognitoAuth   │    │TokenStorage        │    │User      │
│          │    │Service       │    │                    │    │          │
└────┬─────┘    └──────┬───────┘    └─────────┬──────────┘    └────┬─────┘
     │                 │                       │                    │
     │ login(user,pwd) │                       │                    │
     ├────────────────>│                       │                    │
     │                 │                       │                    │
     │                 ├─ Cognito API Call    │                    │
     │                 │                       │                    │
     │                 ├─ Success?            │                    │
     │                 │   │                   │                    │
     │                 │   ├─ YES: tokens     │                    │
     │                 │   │   ├──────────────>│                    │
     │                 │   │   │               │                    │
     │                 │   │   │ stored        │                    │
     │                 │   │   │<──────────────┤                    │
     │                 │   │   │               │                    │
     │ success         │   │   │               │                    │
     │<────────────────┤   │   │               │                    │
     │                 │   │   │               │                    │
     │ Navigate to App │   │   │               │                    │
     │                 │   │   │               │                    │
     │                 │   │                   │                    │
     │                 │   └─ NO: error        │                    │
     │                 │       │               │                    │
     │                 │       ├─ InvalidCredentials               │
     │                 │       │   │           │                    │
     │ AuthError       │       │   │           │                    │
     │<────────────────┤       │   │           │                    │
     │                 │       │   │           │                    │
     │ Show "Invalid username/password"        │                    │
     ├─────────────────────────────────────────────────────────────>│
     │                 │       │   │           │                    │
     │                 │       │   │           │                    │
     │                 │       ├─ NetworkError │                    │
     │                 │       │   │           │                    │
     │ AuthError       │       │   │           │                    │
     │<────────────────┤       │   │           │                    │
     │                 │       │   │           │                    │
     │ Show "Check connection" + Retry Button  │                    │
     ├─────────────────────────────────────────────────────────────>│
     │                 │       │   │           │                    │
     │                 │       │   │           │                    │
     │                 │       └─ RateLimit    │                    │
     │                 │           │           │                    │
     │ AuthError       │           │           │                    │
     │<────────────────┤           │           │                    │
     │                 │           │           │                    │
     │ Show "Too many attempts. Wait 5 minutes"                     │
     ├─────────────────────────────────────────────────────────────>│
```

### Token Encryption Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Token Encryption Flow                         │
└─────────────────────────────────────────────────────────────────┘

AuthTokens (plaintext)
  { idToken, accessToken, refreshToken, expiresAt }
                    │
                    ▼
          JSON.stringify()
                    │
                    ▼
        ┌───────────────────────┐
        │  PBKDF2 Key Derivation │
        ├───────────────────────┤
        │ Input: passphrase     │
        │ Salt: "llt-v1"        │
        │ Iterations: 100,000   │
        │ Hash: SHA-256         │
        │ Output: 256-bit key   │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  AES-GCM Encryption   │
        ├───────────────────────┤
        │ Generate random IV    │
        │ (12 bytes, unique)    │
        │                       │
        │ Encrypt with:         │
        │  - CryptoKey (256-bit)│
        │  - IV (12 bytes)      │
        │  - Plaintext          │
        │                       │
        │ Output:               │
        │  - Ciphertext         │
        │  - Authentication tag │
        └───────────┬───────────┘
                    │
                    ▼
          Base64 Encode
          (ciphertext + IV)
                    │
                    ▼
    localStorage.setItem('auth_tokens', encrypted)
    localStorage.setItem('auth_iv', iv)


┌─────────────────────────────────────────────────────────────────┐
│                    Token Decryption Flow                         │
└─────────────────────────────────────────────────────────────────┘

    localStorage.getItem('auth_tokens')
    localStorage.getItem('auth_iv')
                    │
                    ▼
          Base64 Decode
                    │
                    ▼
        ┌───────────────────────┐
        │  PBKDF2 Key Derivation │
        │  (same as encryption)  │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  AES-GCM Decryption   │
        ├───────────────────────┤
        │ Decrypt with:         │
        │  - CryptoKey          │
        │  - IV (from storage)  │
        │  - Ciphertext         │
        │                       │
        │ Verify auth tag       │
        │                       │
        │ Output: Plaintext     │
        └───────────┬───────────┘
                    │
                    ▼
          JSON.parse()
                    │
                    ▼
        AuthTokens (plaintext)
          { idToken, accessToken, refreshToken, expiresAt }
```

## Components and Interfaces

### 1. TokenStorage Service

**Purpose**: Securely store and retrieve authentication tokens using AES-256-GCM encryption.

**Current Implementation Issues**:
- No test coverage (350 lines untested)
- Weak key derivation (simple hash instead of PBKDF2)
- No validation of token expiry before storage
- Magic numbers for encryption parameters
- No unique IV verification per encryption (should be tested)
- No salt version tracking (for future rotation)

**Design Changes**:


```typescript
// Enhanced TokenStorage with PBKDF2
class TokenStorage {
  private static instance: TokenStorage;
  private readonly PBKDF2_ITERATIONS = 100000; // From constants
  private readonly KEY_LENGTH = 32; // From constants
  private readonly SALT_VERSION = 'v1'; // For future rotation
  private readonly SALT = `low-latency-translate-${this.SALT_VERSION}`; // Fixed app salt with version
  
  private constructor() {
    // Initialize crypto key on construction
    this.initializeKey();
  }
  
  static getInstance(): TokenStorage {
    if (!TokenStorage.instance) {
      TokenStorage.instance = new TokenStorage();
    }
    return TokenStorage.instance;
  }
  
  private async deriveKey(passphrase: string): Promise<CryptoKey> {
    // Use PBKDF2 with 100k iterations
    const encoder = new TextEncoder();
    const keyMaterial = await crypto.subtle.importKey(
      'raw',
      encoder.encode(passphrase),
      'PBKDF2',
      false,
      ['deriveBits', 'deriveKey']
    );
    
    return crypto.subtle.deriveKey(
      {
        name: 'PBKDF2',
        salt: encoder.encode(this.SALT),
        iterations: this.PBKDF2_ITERATIONS,
        hash: 'SHA-256'
      },
      keyMaterial,
      { name: 'AES-GCM', length: 256 },
      false,
      ['encrypt', 'decrypt']
    );
  }
  
  async storeTokens(tokens: AuthTokens): Promise<void> {
    // Validate tokens before storage
    if (tokens.expiresAt < Date.now()) {
      throw new Error('Cannot store expired tokens');
    }
    
    // Generate unique IV for this encryption
    const iv = crypto.getRandomValues(new Uint8Array(12));
    
    // Encrypt and store
    const encrypted = await this.encrypt(JSON.stringify(tokens), iv);
    localStorage.setItem('auth_tokens', encrypted);
    localStorage.setItem('auth_iv', this.arrayBufferToBase64(iv));
  }
}
```

**Testing Strategy**:
- Unit tests for encryption/decryption round-trip
- Tests for invalid data handling
- Tests for expired token rejection
- Tests for localStorage unavailability
- Tests for concurrent operations
- Tests for unique IV generation

### 2. AuthGuard Component

**Purpose**: Protect routes and manage automatic token refresh.

**Current Implementation Issues**:
- No test coverage (200 lines untested)
- No concurrent refresh protection (race condition risk)
- Timer cleanup missing (memory leak risk)
- Refresh scheduled incorrectly (not 5 minutes before expiry)

**Design Changes**:

```typescript
// Enhanced AuthGuard with concurrent refresh protection
export function AuthGuard({ children }: AuthGuardProps) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);
  const refreshPromiseRef = useRef<Promise<boolean> | null>(null);
  
  useEffect(() => {
    checkAuth();
    
    // Cleanup timer on unmount
    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
    };
  }, []);
  
  const checkAuth = async () => {
    const tokens = TokenStorage.getInstance().getTokens();
    
    if (!tokens) {
      setIsAuthenticated(false);
      return;
    }
    
    const timeUntilExpiry = tokens.expiresAt - Date.now();
    
    if (timeUntilExpiry <= 0) {
      // Token expired, try refresh before redirecting
      await handleTokenRefresh();
    } else if (timeUntilExpiry < REFRESH_THRESHOLD_MS) {
      // Close to expiry, refresh now
      await handleTokenRefresh();
    } else {
      // Schedule refresh 5 minutes before expiry
      scheduleRefresh(timeUntilExpiry - REFRESH_THRESHOLD_MS);
      setIsAuthenticated(true);
    }
  };
  
  const handleTokenRefresh = async (): Promise<boolean> => {
    // Return existing promise if refresh already in progress
    // This prevents race conditions better than useState
    if (refreshPromiseRef.current) {
      return refreshPromiseRef.current;
    }
    
    // Create new refresh promise
    refreshPromiseRef.current = (async () => {
      try {
        const authService = CognitoAuthService.getInstance();
        const newTokens = await authService.refreshTokens();
        
        TokenStorage.getInstance().storeTokens(newTokens);
        setIsAuthenticated(true);
        
        // Schedule next refresh
        const timeUntilExpiry = newTokens.expiresAt - Date.now();
        scheduleRefresh(timeUntilExpiry - REFRESH_THRESHOLD_MS);
        
        return true;
      } catch (error) {
        // Refresh failed, redirect to login
        TokenStorage.getInstance().clearTokens();
        setIsAuthenticated(false);
        return false;
      } finally {
        // Clear promise ref when done
        refreshPromiseRef.current = null;
      }
    })();
    
    return refreshPromiseRef.current;
  };
  
  const scheduleRefresh = (delayMs: number) => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
    }
    
    refreshTimerRef.current = setTimeout(() => {
      handleTokenRefresh();
    }, delayMs);
  };
  
  if (isAuthenticated === null) {
    return <LoadingSpinner />;
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  return <>{children}</>;
}
```

**Design Note on Concurrent Refresh**:

The `refreshPromiseRef` is component-level state, meaning each AuthGuard instance tracks its own refresh. This is appropriate for this application because:
- Only one AuthGuard instance exists (wraps entire app)
- If multiple instances existed, each would independently manage refresh
- The ref-based approach prevents timing issues better than useState

If global refresh protection across multiple AuthGuard instances is needed in the future, use a module-level variable:
```typescript
// Outside component (module level)
let globalRefreshPromise: Promise<boolean> | null = null;
```

**Testing Strategy**:
- Test unauthenticated user redirect
- Test authenticated user access
- Test token refresh on expiry
- Test concurrent refresh prevention (multiple rapid calls)
- Test timer cleanup on unmount
- Test refresh scheduling (5 min before expiry)
- Test loading state display


### 3. AuthError Class

**Purpose**: Provide consistent error handling with user-friendly messages.

**Current Implementation Issues**:
- No test coverage (200 lines untested)
- Error mapping may have gaps

**Design Changes**:

```typescript
// Enhanced AuthError with comprehensive error mapping
export class AuthError extends Error {
  public readonly code: string;
  public readonly userMessage: string;
  public readonly originalError?: Error;
  
  constructor(code: string, message: string, originalError?: Error) {
    super(message);
    this.name = 'AuthError';
    this.code = code;
    this.userMessage = this.getUserMessage(code);
    this.originalError = originalError;
  }
  
  static fromCognitoError(error: any): AuthError {
    const errorCode = error.code || error.name || 'UNKNOWN_ERROR';
    
    const errorMap: Record<string, string> = {
      'NotAuthorizedException': 'AUTH_INVALID_CREDENTIALS',
      'UserNotFoundException': 'AUTH_USER_NOT_FOUND',
      'UserNotConfirmedException': 'AUTH_USER_NOT_CONFIRMED',
      'PasswordResetRequiredException': 'AUTH_PASSWORD_RESET_REQUIRED',
      'TooManyRequestsException': 'AUTH_RATE_LIMIT',
      'NetworkError': 'AUTH_NETWORK_ERROR',
      // ... more mappings
    };
    
    const mappedCode = errorMap[errorCode] || 'AUTH_UNKNOWN_ERROR';
    return new AuthError(mappedCode, error.message, error);
  }
  
  private getUserMessage(code: string): string {
    const messages: Record<string, string> = {
      'AUTH_INVALID_CREDENTIALS': 'Invalid username or password',
      'AUTH_USER_NOT_FOUND': 'User not found',
      'AUTH_RATE_LIMIT': 'Too many attempts. Please try again later',
      'AUTH_NETWORK_ERROR': 'Network error. Please check your connection',
      // ... more messages
    };
    
    return messages[code] || 'An authentication error occurred';
  }
  
  toJSON() {
    return {
      name: this.name,
      code: this.code,
      message: this.message,
      userMessage: this.userMessage,
      stack: this.stack
    };
  }
}
```

**Testing Strategy**:
- Test error creation with all error codes
- Test Cognito error mapping
- Test user message generation
- Test JSON serialization
- Test error with/without original error

### 4. SessionCreationOrchestrator

**Purpose**: Orchestrate session creation with WebSocket connection and token management.

**Current Implementation Issues**:
- Token expiry calculation bug (recalculates from expiresIn)
- No WebSocket state validation before send
- Dynamic imports in critical path

**Design Changes**:

```typescript
// Fixed SessionCreationOrchestrator
export class SessionCreationOrchestrator {
  private wsClient: WebSocketClient;
  private authService: CognitoAuthService;
  
  async createSession(config: SessionConfig): Promise<SessionResult> {
    // Get tokens and validate
    const tokens = TokenStorage.getInstance().getTokens();
    if (!tokens) {
      throw new AuthError('AUTH_NO_TOKENS', 'No authentication tokens found');
    }
    
    // FIX: Use stored expiresAt directly, don't recalculate
    const timeUntilExpiry = tokens.expiresAt - Date.now();
    
    if (timeUntilExpiry <= 0) {
      // Token expired, refresh first
      const newTokens = await this.authService.refreshTokens();
      TokenStorage.getInstance().storeTokens(newTokens);
    }
    
    // Connect WebSocket with token
    await this.wsClient.connect(tokens.idToken);
    
    // FIX: Validate connection state before sending
    if (!this.wsClient.isConnected()) {
      throw new Error('WebSocket not connected');
    }
    
    // Send session creation request
    return this.sendCreationRequest(config);
  }
  
  private async sendCreationRequest(config: SessionConfig): Promise<SessionResult> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Session creation timeout'));
      }, SESSION_CREATION_TIMEOUT_MS);
      
      this.wsClient.once('sessionCreated', (data) => {
        clearTimeout(timeout);
        resolve(data);
      });
      
      this.wsClient.once('error', (error) => {
        clearTimeout(timeout);
        reject(error);
      });
      
      try {
        // Validate connection state before sending
        if (!this.wsClient.isConnected()) {
          throw new Error('WebSocket not connected');
        }
        
        this.wsClient.send({
          action: 'createSession',
          sourceLanguage: config.sourceLanguage,
          qualityTier: config.qualityTier,
        });
      } catch (error) {
        clearTimeout(timeout);
        reject(error);
      }
    });
  }
}
```

**Testing Strategy**:
- Test session creation with valid tokens
- Test session creation with expired tokens (triggers refresh)
- Test WebSocket connection validation
- Test timeout handling
- Test error handling


### 5. Lambda Authorizer

**Purpose**: Validate JWT tokens for WebSocket connections.

**Current Implementation Issues**:
- Error logging lacks context
- No structured logging for CloudWatch Insights

**Design Changes**:

```python
# Enhanced Lambda Authorizer with structured logging
import logging
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda authorizer for WebSocket API Gateway.
    Validates JWT tokens and returns IAM policy.
    """
    try:
        # Extract token from query string
        token = extract_token(event)
        
        if not token:
            logger.warning(
                'Authorization failed: No token provided',
                extra={
                    'error_type': 'MissingToken',
                    'method_arn': event.get('methodArn'),
                    'has_token': False,
                    'request_id': context.request_id if context else None,
                }
            )
            raise Exception('Unauthorized')
        
        # Validate token
        claims = validate_jwt(token)
        
        # Generate IAM policy
        policy = generate_policy(claims['sub'], 'Allow', event['methodArn'])
        
        logger.info(
            'Authorization successful',
            extra={
                'user_id': claims['sub'],
                'method_arn': event.get('methodArn'),
                'request_id': context.request_id if context else None,
            }
        )
        
        return policy
        
    except TokenExpiredError as e:
        logger.error(
            f'Authorization failed: Token expired',
            extra={
                'error_type': 'TokenExpired',
                'method_arn': event.get('methodArn'),
                'has_token': bool(token),
                'request_id': context.request_id if context else None,
            }
        )
        raise Exception('Unauthorized')
        
    except InvalidTokenError as e:
        logger.error(
            f'Authorization failed: Invalid token signature',
            extra={
                'error_type': 'InvalidSignature',
                'method_arn': event.get('methodArn'),
                'has_token': bool(token),
                'request_id': context.request_id if context else None,
            }
        )
        raise Exception('Unauthorized')
        
    except Exception as e:
        logger.error(
            f'Authorization failed: {str(e)}',
            extra={
                'error_type': type(e).__name__,
                'method_arn': event.get('methodArn'),
                'has_token': bool(token),
                'request_id': context.request_id if context else None,
            }
        )
        raise Exception('Unauthorized')
```

**Testing Strategy**:
- Existing tests already comprehensive
- Add tests for new logging structure
- Verify CloudWatch Insights compatibility

### 6. Constants Configuration

**Purpose**: Centralize magic numbers and configuration values.

**Design**:

```typescript
// frontend-client-apps/shared/config/constants.ts

// Token Management
export const TOKEN_REFRESH_THRESHOLD_MS = 5 * 60 * 1000; // 5 minutes
export const SESSION_CREATION_TIMEOUT_MS = 10 * 1000; // 10 seconds

// Encryption
export const PBKDF2_ITERATIONS = 100000;
export const ENCRYPTION_KEY_LENGTH = 32;
export const ENCRYPTION_IV_LENGTH = 12;
export const APPLICATION_SALT = 'low-latency-translate-v1';

// WebSocket
export enum WebSocketCloseCode {
  NORMAL_CLOSURE = 1000,
  ABNORMAL_CLOSURE = 1006,
  POLICY_VIOLATION = 1008,
  INTERNAL_ERROR = 1011,
}

// Environment Variables (for documentation)
export const REQUIRED_ENV_VARS = {
  BACKEND: ['USER_POOL_ID', 'CLIENT_ID', 'REGION'],
  FRONTEND: ['VITE_COGNITO_USER_POOL_ID', 'VITE_COGNITO_CLIENT_ID', 'VITE_AWS_REGION'],
};
```

## Data Models

### AuthTokens Interface

```typescript
interface AuthTokens {
  idToken: string;        // JWT for authentication
  accessToken: string;    // JWT for API access
  refreshToken: string;   // For token refresh
  expiresAt: number;      // Absolute timestamp (milliseconds since epoch)
}
```

**Key Change**: `expiresAt` is always an absolute timestamp, never a duration.

### WebSocket Connection State

```typescript
enum ConnectionState {
  DISCONNECTED = 'DISCONNECTED',
  CONNECTING = 'CONNECTING',
  CONNECTED = 'CONNECTED',
  RECONNECTING = 'RECONNECTING',
  FAILED = 'FAILED',
}

interface WebSocketClient {
  state: ConnectionState;
  isConnected(): boolean;
  connect(token: string): Promise<void>;
  send(message: any): void;
  disconnect(code?: WebSocketCloseCode): void;
}
```

## Error Handling

### Error Hierarchy

```
Error
└── AuthError
    ├── InvalidCredentialsError
    ├── TokenExpiredError
    ├── NetworkError
    ├── RateLimitError
    └── UnknownAuthError
```

### Error Response Format

```typescript
interface ErrorResponse {
  type: 'error';
  code: string;           // Machine-readable code
  message: string;        // Technical message
  userMessage: string;    // User-friendly message
  timestamp: number;      // Error timestamp
  requestId?: string;     // For correlation
}
```


## Testing Strategy

### Unit Testing Approach

**Framework**: Vitest (already in use)

**Coverage Target**: >90% for authentication components

**Mocking Strategy**:
- Mock Web Crypto API for encryption tests
- Mock localStorage for storage tests
- Mock CognitoAuthService for AuthGuard tests
- Mock WebSocketClient for orchestrator tests

### Test Organization

```
frontend-client-apps/shared/__tests__/
├── TokenStorage.test.ts          # NEW - 350 lines to test
├── AuthGuard.test.tsx            # NEW - 200 lines to test
├── AuthError.test.ts             # NEW - 200 lines to test
├── CognitoAuthService.test.ts    # EXISTS - keep as-is
└── SessionCreationOrchestrator.test.ts  # EXISTS - add bug fix tests
```

### Test Coverage by Component

| Component | Current Coverage | Target Coverage | New Tests Needed |
|-----------|-----------------|-----------------|------------------|
| TokenStorage.ts | 0% | 100% | ~15 tests |
| AuthGuard.tsx | 0% | 100% | ~12 tests |
| AuthError.ts | 0% | 80% | ~8 tests |
| SessionCreationOrchestrator.ts | 85% | 95% | ~3 tests |
| Lambda Authorizer | 95% | 95% | ~2 tests |

### Critical Test Scenarios

**TokenStorage**:
1. Encryption/decryption round-trip
2. PBKDF2 key derivation
3. Unique IV generation
4. Expired token rejection
5. localStorage unavailable handling
6. Concurrent operations
7. Invalid data handling

**AuthGuard**:
1. Unauthenticated redirect
2. Authenticated access
3. Token refresh on expiry
4. Concurrent refresh prevention
5. Timer cleanup on unmount
6. Refresh scheduling (5 min before)
7. Loading state display

**AuthError**:
1. Error creation with all codes
2. Cognito error mapping
3. User message generation
4. JSON serialization
5. Network error handling

## Performance Considerations

### Performance Benchmarks

**Expected Timings (p95)**:

**PBKDF2 Key Derivation**:
- Chrome: 50-70ms
- Firefox: 60-80ms
- Safari: 70-100ms
- Impact: One-time at app initialization

**Token Encryption**:
- AES-GCM encrypt: <5ms
- Total with PBKDF2: 50-100ms
- Frequency: Once per login/refresh

**Token Decryption**:
- AES-GCM decrypt: <5ms
- Total with PBKDF2: 50-100ms
- Frequency: Once at app startup

**Token Refresh**:
- Cognito API call: 200-400ms
- Token storage (encrypt): 5-10ms
- Total: 200-500ms (target: <500ms p95)

**WebSocket Connection**:
- Connection establishment: 100-300ms
- JWT validation (Lambda): 50-100ms
- Total: 200-500ms (target: <1s p95)

### Encryption Performance

**PBKDF2 with 100k iterations**:
- Expected time: 50-100ms on modern browsers
- Acceptable for login flow (not in hot path)
- Cached key after derivation

**Mitigation**: Derive key once at app startup, reuse for all operations.

### Token Refresh Timing

**Current Issue**: Refresh may happen too late or too early

**Solution**: Schedule refresh exactly 5 minutes before expiry
- Reduces unnecessary refreshes
- Prevents expired token usage
- Balances security and UX

### WebSocket Connection Validation

**Cost**: ~1ms to check connection state

**Benefit**: Prevents silent failures and improves error messages

## Security Considerations

### PBKDF2 Configuration

**Iterations**: 100,000
- OWASP recommendation for 2023+
- Balances security and performance
- Protects against brute force attacks

**Salt**: Fixed application salt
- Simpler than per-user salt
- Still secure with PBKDF2
- Consistent key derivation

### Concurrent Refresh Protection

**Risk**: Race condition if multiple components trigger refresh

**Mitigation**: Use `isRefreshing` flag
- Only one refresh at a time
- Other requests wait for completion
- Prevents token corruption

### Token Validation

**Before Storage**: Reject tokens with `expiresAt` in the past
- Prevents storing invalid tokens
- Catches clock skew issues
- Improves error messages

### Error Logging

**Never Log**:
- JWT tokens (full or partial)
- Refresh tokens
- User passwords
- Encryption keys

**Always Log**:
- Error types and codes
- Request IDs for correlation
- Method ARNs for debugging
- Whether token was present (boolean)

## Deployment Strategy

### Phase 1: Remove Orphaned Code (30 minutes)

1. Delete `AuthService.ts`
2. Verify no import errors
3. Run all tests
4. Commit and deploy

**Risk**: Low (file has zero references)

### Phase 2: Add Security Improvements (2-3 hours)

1. Implement PBKDF2 in TokenStorage
2. Add concurrent refresh protection to AuthGuard
3. Extract constants to config file
4. Run tests
5. Commit and deploy

**Risk**: Medium (changes security-critical code)
**Mitigation**: Comprehensive testing before deployment

### Phase 3: Add Test Coverage (8-10 hours)

1. Write TokenStorage tests (4-5 hours)
2. Write AuthGuard tests (3-4 hours)
3. Write AuthError tests (2-3 hours)
4. Achieve 90%+ coverage
5. Commit and deploy

**Risk**: Low (only adding tests, no code changes)

### Phase 4: Fix Bugs (1-2 hours)

1. Fix token expiry calculation
2. Add WebSocket state validation
3. Improve Lambda logging
4. Add close code enum
5. Run tests
6. Commit and deploy

**Risk**: Low (small, focused changes)

### Phase 5: Improve Observability (1-2 hours)

1. Add structured logging to Lambda
2. Add performance metrics
3. Update CloudWatch dashboards
4. Commit and deploy

**Risk**: Low (logging changes only)

### Rollback Plan

**If issues occur**:
1. Revert to previous deployment
2. Tokens remain valid (no breaking changes)
3. Users may need to re-login (worst case)

**Monitoring**:
- Watch authentication success rate
- Monitor token refresh failures
- Check error logs for new error types

## Migration Path

### No Breaking Changes

All changes are **backward compatible**:
- Existing tokens remain valid
- Token format unchanged
- API contracts unchanged
- WebSocket protocol unchanged

### Gradual Rollout

1. Deploy to dev environment
2. Test all authentication flows
3. Deploy to staging
4. Monitor for 24 hours
5. Deploy to production

### Validation Checklist

Before production deployment:
- [ ] All P0 requirements completed
- [ ] Test coverage >90%
- [ ] All tests passing
- [ ] Manual testing completed
- [ ] Performance benchmarks met
- [ ] Security review passed
- [ ] Rollback plan documented

## Monitoring and Observability

### CloudWatch Metrics

**New Metrics**:
- `AuthenticationDuration` (first-time login)
- `TokenRefreshDuration` (refresh operation)
- `WebSocketConnectionDuration` (connection time)
- `TokenStorageErrors` (encryption/decryption failures)
- `ConcurrentRefreshAttempts` (race condition detection)

### CloudWatch Logs

**Structured Logging Format**:
```json
{
  "timestamp": "2025-11-18T12:34:56.789Z",
  "level": "ERROR",
  "error_type": "TokenExpired",
  "method_arn": "arn:aws:execute-api:...",
  "has_token": true,
  "request_id": "abc-123-def"
}
```

**CloudWatch Insights Queries**:

```
# Find all authorization failures
fields @timestamp, error_type, method_arn
| filter level = "ERROR"
| stats count() by error_type

# Track authentication performance
fields @timestamp, operation, duration_ms
| filter operation in ["login", "refresh", "websocket_connect"]
| stats avg(duration_ms), p95(duration_ms), p99(duration_ms) by operation
```

### Alerts

**Critical Alerts** (page on-call):
- Authentication success rate <95%
- Token refresh failure rate >5%
- WebSocket connection failure rate >5%

**Warning Alerts** (email):
- Authentication duration p95 >2 seconds
- Token refresh duration p95 >500ms
- Concurrent refresh attempts detected

## Documentation Updates

### Files to Update

1. **README.md**: Remove OAuth2 references, document direct auth
2. **AUTHENTICATION_CLEANUP_GUIDE.md**: Mark as completed
3. **CLEANUP_ACTION_PLAN.md**: Mark tasks as done
4. **session-management/README.md**: Update Lambda authorizer logging
5. **frontend-client-apps/README.md**: Update auth flow documentation

### New Documentation

1. **SECURITY.md**: Document PBKDF2 configuration, token handling
2. **TESTING.md**: Document test coverage requirements
3. **TROUBLESHOOTING.md**: Common auth issues and solutions

## Success Criteria

### Functional Requirements

- [ ] All orphaned code removed
- [ ] Test coverage >90% for auth components
- [ ] All known bugs fixed
- [ ] Security best practices implemented

### Performance Requirements

- [ ] First-time authentication <2s (p95)
- [ ] Token refresh <500ms (p95)
- [ ] WebSocket connection <1s (p95)

### Quality Requirements

- [ ] Zero magic numbers in auth code
- [ ] All imports are static
- [ ] Consistent error messages
- [ ] Structured logging implemented

### Production Readiness

- [ ] All P0 requirements completed
- [ ] Zero auth-related bugs in staging
- [ ] End-to-end flow tested
- [ ] Rollback plan documented
- [ ] Monitoring configured

## Risks and Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| PBKDF2 too slow | Low | Medium | Benchmark early, adjust iterations if needed |
| Test coverage gaps | Medium | High | Code review + coverage reports |
| Breaking existing auth | Low | Critical | Comprehensive testing, gradual rollout |
| Token refresh race condition | Medium | Medium | Concurrent refresh protection |
| localStorage quota exceeded | Low | Low | Graceful error handling |

## Future Enhancements

**Not in scope for this cleanup, but consider for future**:

1. **Biometric Authentication**: Face ID, Touch ID support
2. **Multi-Factor Authentication**: SMS, TOTP codes
3. **Session Management**: View/revoke active sessions
4. **Token Rotation**: Automatic refresh token rotation
5. **Offline Support**: Cache tokens for offline use
6. **Security Headers**: CSP, HSTS for enhanced security
