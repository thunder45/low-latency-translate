# Design Document

## Overview

Fix the WebSocket connection failure by implementing proper JWT token validation in the Lambda authorizer. The root cause is that the authorizer is not correctly validating the Cognito ID tokens, causing all connection attempts to be rejected even when the user has successfully authenticated.

## Architecture

### Current Flow (Broken)

```
┌─────────────┐
│ Speaker App │
│ Logs In     │
└──────┬──────┘
       │
       │ Cognito USER_PASSWORD_AUTH
       ▼
┌──────────────────┐
│ AWS Cognito      │
│ Returns Tokens   │
└────────┬─────────┘
         │
         │ ID Token
         ▼
┌──────────────────────────────┐
│ WebSocket Connection Attempt │
│ wss://...?token=<ID_TOKEN>   │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────┐
│ API Gateway          │
│ Invokes Authorizer   │
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ Lambda Authorizer    │
│ ❌ REJECTS TOKEN     │  ← PROBLEM HERE
│ (Invalid validation) │
└──────────────────────┘
```

### Fixed Flow

```
┌─────────────┐
│ Speaker App │
│ Logs In     │
└──────┬──────┘
       │
       │ Cognito USER_PASSWORD_AUTH
       ▼
┌──────────────────┐
│ AWS Cognito      │
│ Returns Tokens   │
└────────┬─────────┘
         │
         │ ID Token
         ▼
┌──────────────────────────────┐
│ WebSocket Connection Attempt │
│ wss://...?token=<ID_TOKEN>   │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────┐
│ API Gateway          │
│ Invokes Authorizer   │
└────────┬─────────────┘
         │
         ▼
┌──────────────────────────────┐
│ Lambda Authorizer            │
│ 1. Extract token from query  │
│ 2. Fetch Cognito JWKS        │
│ 3. Verify JWT signature      │
│ 4. Validate issuer/aud/exp   │
│ 5. Extract user ID (sub)     │
│ ✅ ALLOW CONNECTION          │
└────────┬─────────────────────┘
         │
         │ principalId = user_id
         ▼
┌──────────────────────┐
│ Connection Handler   │
│ Creates session      │
└──────────────────────┘
```

## Components and Interfaces

### 1. Lambda Authorizer (Fix)

**Location**: `session-management/lambda/authorizer/handler.py`

**Current Issues**:
- Not properly validating JWT signature
- Not fetching Cognito public keys (JWKS)
- Not validating token claims (iss, aud, exp)
- Poor error logging

**Required Changes**:

```python
import json
import os
import time
from typing import Dict, Any, Optional
import jwt
from jwt import PyJWKClient
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
COGNITO_USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID')
COGNITO_CLIENT_ID = os.environ.get('COGNITO_CLIENT_ID')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Cognito JWKS URL
JWKS_URL = f'https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json'

# Cache JWKS client (reused across invocations)
jwks_client = None

def get_jwks_client():
    """Get or create JWKS client for token validation"""
    global jwks_client
    if jwks_client is None:
        jwks_client = PyJWKClient(JWKS_URL)
    return jwks_client

def extract_token(event: Dict[str, Any]) -> Optional[str]:
    """
    Extract JWT token from query string or Authorization header
    
    Priority:
    1. Query string parameter 'token'
    2. Authorization header (Bearer format)
    """
    # Try query string first
    query_params = event.get('queryStringParameters') or {}
    token = query_params.get('token')
    
    if token:
        logger.info('Token found in query string')
        return token
    
    # Try Authorization header
    headers = event.get('headers') or {}
    auth_header = headers.get('Authorization') or headers.get('authorization')
    
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        logger.info('Token found in Authorization header')
        return token
    
    logger.warning('No token found in query string or Authorization header')
    return None

def validate_token(token: str) -> Dict[str, Any]:
    """
    Validate JWT token from Cognito
    
    Validates:
    - Signature using Cognito public keys
    - Issuer (iss claim)
    - Audience (aud claim)
    - Expiration (exp claim)
    - Token use (token_use claim should be 'id')
    
    Returns decoded token claims if valid
    Raises jwt.PyJWTError if invalid
    """
    try:
        # Get signing key from JWKS
        client = get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        
        # Expected issuer
        expected_issuer = f'https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}'
        
        # Decode and validate token
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=['RS256'],
            audience=COGNITO_CLIENT_ID,
            issuer=expected_issuer,
            options={
                'verify_signature': True,
                'verify_exp': True,
                'verify_aud': True,
                'verify_iss': True,
            }
        )
        
        # Verify token_use is 'id' (not access token)
        token_use = decoded.get('token_use')
        if token_use != 'id':
            raise jwt.InvalidTokenError(f'Invalid token_use: {token_use}, expected "id"')
        
        logger.info(f'Token validated successfully for user: {decoded.get("sub")}')
        return decoded
        
    except jwt.ExpiredSignatureError:
        logger.error('Token validation failed: Token expired')
        raise
    except jwt.InvalidAudienceError:
        logger.error(f'Token validation failed: Invalid audience. Expected: {COGNITO_CLIENT_ID}')
        raise
    except jwt.InvalidIssuerError:
        logger.error(f'Token validation failed: Invalid issuer. Expected: {expected_issuer}')
        raise
    except jwt.InvalidSignatureError:
        logger.error('Token validation failed: Invalid signature')
        raise
    except jwt.InvalidTokenError as e:
        logger.error(f'Token validation failed: {str(e)}')
        raise
    except Exception as e:
        logger.error(f'Unexpected error during token validation: {str(e)}')
        raise

def generate_policy(principal_id: str, effect: str, resource: str, context: Optional[Dict] = None) -> Dict:
    """Generate IAM policy for API Gateway"""
    policy = {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': effect,
                    'Resource': resource
                }
            ]
        }
    }
    
    if context:
        policy['context'] = context
    
    return policy

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict:
    """
    Lambda authorizer for WebSocket API Gateway
    
    Validates JWT token from Cognito and returns IAM policy
    """
    try:
        # Validate configuration
        if not COGNITO_USER_POOL_ID or not COGNITO_CLIENT_ID:
            logger.error('Missing Cognito configuration')
            raise Exception('Unauthorized')
        
        # Extract token
        token = extract_token(event)
        if not token:
            logger.error('No token provided')
            raise Exception('Unauthorized')
        
        # Validate token
        decoded = validate_token(token)
        
        # Extract user information
        user_id = decoded.get('sub')
        email = decoded.get('email')
        
        if not user_id:
            logger.error('Token missing sub claim')
            raise Exception('Unauthorized')
        
        # Generate allow policy
        method_arn = event['methodArn']
        policy = generate_policy(
            principal_id=user_id,
            effect='Allow',
            resource=method_arn,
            context={
                'userId': user_id,
                'email': email or '',
            }
        )
        
        logger.info(f'Authorization successful for user: {user_id}')
        return policy
        
    except jwt.ExpiredSignatureError:
        logger.error('Authorization failed: Token expired')
        raise Exception('Unauthorized')
    except jwt.PyJWTError as e:
        logger.error(f'Authorization failed: JWT validation error: {str(e)}')
        raise Exception('Unauthorized')
    except Exception as e:
        logger.error(f'Authorization failed: {str(e)}')
        raise Exception('Unauthorized')
```

**Dependencies**:
```
PyJWT[crypto]==2.8.0
cryptography==41.0.0
```

### 2. WebSocket Client (Frontend Enhancement)

**Location**: `frontend-client-apps/shared/websocket/WebSocketClient.ts`

**Current Issues**:
- Generic error handling
- No token refresh on auth failure
- Poor error messages

**Required Changes**:

```typescript
export class WebSocketClient {
  // ... existing code ...

  async connect(token: string): Promise<void> {
    try {
      const url = `${this.wsUrl}?token=${encodeURIComponent(token)}`;
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.emit('connected');
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.handleConnectionError(error);
      };

      this.ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        this.isConnected = false;
        this.handleConnectionClose(event);
      };

      // ... rest of handlers ...
    } catch (error) {
      console.error('WebSocket connection failed:', error);
      throw error;
    }
  }

  private handleConnectionError(error: Event): void {
    // Check if this is an authentication error
    // WebSocket errors don't provide detailed info, but we can infer from close code
    this.emit('error', {
      type: 'connection_error',
      message: 'Failed to connect to server',
      error,
    });
  }

  private handleConnectionClose(event: CloseEvent): void {
    // WebSocket close codes:
    // 1000 = Normal closure
    // 1006 = Abnormal closure (no close frame)
    // 1008 = Policy violation (auth failure)
    // 1011 = Server error
    
    if (event.code === 1008) {
      // Authentication failure
      this.emit('auth_error', {
        type: 'authentication_failed',
        message: 'Authentication failed. Please log in again.',
        code: event.code,
        reason: event.reason,
      });
    } else if (event.code === 1006) {
      // Connection failed (could be network or auth)
      this.emit('connection_failed', {
        type: 'connection_failed',
        message: 'Connection failed. Please check your network.',
        code: event.code,
      });
    } else {
      // Other errors
      this.emit('disconnected', {
        code: event.code,
        reason: event.reason,
      });
    }

    // Attempt reconnection if not a normal closure
    if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
      this.scheduleReconnect();
    }
  }
}
```

### 3. Session Creation Orchestrator (Frontend Enhancement)

**Location**: `frontend-client-apps/shared/services/SessionCreationOrchestrator.ts`

**Required Changes**:

```typescript
export class SessionCreationOrchestrator {
  // ... existing code ...

  async createSession(sourceLanguage: string): Promise<Session> {
    try {
      // Get current token
      const tokens = await this.tokenStorage.getTokens();
      if (!tokens) {
        throw new Error('Not authenticated');
      }

      // Check if token is expired or close to expiry
      const now = Date.now();
      const expiresAt = new Date(tokens.expiresAt).getTime();
      const timeUntilExpiry = expiresAt - now;

      // If token expires in less than 5 minutes, refresh it
      if (timeUntilExpiry < 5 * 60 * 1000) {
        console.log('Token close to expiry, refreshing...');
        try {
          const newTokens = await this.authService.refreshTokens(tokens.refreshToken);
          await this.tokenStorage.storeTokens(newTokens);
          tokens.idToken = newTokens.idToken;
        } catch (error) {
          console.error('Token refresh failed:', error);
          throw new Error('Session expired. Please log in again.');
        }
      }

      // Connect to WebSocket with ID token
      await this.wsClient.connect(tokens.idToken);

      // Wait for connection
      await this.waitForConnection();

      // Send createSession message
      const sessionId = await this.sendCreateSessionMessage(sourceLanguage);

      return {
        sessionId,
        sourceLanguage,
        status: 'active',
      };
    } catch (error) {
      console.error('Session creation failed:', error);
      
      // Check if this is an auth error
      if (error.message?.includes('Authentication') || error.message?.includes('Unauthorized')) {
        // Try to refresh token and retry once
        try {
          const tokens = await this.tokenStorage.getTokens();
          if (tokens) {
            const newTokens = await this.authService.refreshTokens(tokens.refreshToken);
            await this.tokenStorage.storeTokens(newTokens);
            
            // Retry connection with new token
            await this.wsClient.connect(newTokens.idToken);
            await this.waitForConnection();
            const sessionId = await this.sendCreateSessionMessage(sourceLanguage);
            
            return {
              sessionId,
              sourceLanguage,
              status: 'active',
            };
          }
        } catch (retryError) {
          console.error('Retry after token refresh failed:', retryError);
          throw new Error('Authentication failed. Please log in again.');
        }
      }
      
      throw error;
    }
  }

  private waitForConnection(): Promise<void> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Connection timeout'));
      }, 10000); // 10 second timeout

      const onConnected = () => {
        clearTimeout(timeout);
        this.wsClient.off('connected', onConnected);
        this.wsClient.off('auth_error', onAuthError);
        this.wsClient.off('connection_failed', onConnectionFailed);
        resolve();
      };

      const onAuthError = (error: any) => {
        clearTimeout(timeout);
        this.wsClient.off('connected', onConnected);
        this.wsClient.off('auth_error', onAuthError);
        this.wsClient.off('connection_failed', onConnectionFailed);
        reject(new Error('Authentication failed'));
      };

      const onConnectionFailed = (error: any) => {
        clearTimeout(timeout);
        this.wsClient.off('connected', onConnected);
        this.wsClient.off('auth_error', onAuthError);
        this.wsClient.off('connection_failed', onConnectionFailed);
        reject(new Error('Connection failed'));
      };

      this.wsClient.on('connected', onConnected);
      this.wsClient.on('auth_error', onAuthError);
      this.wsClient.on('connection_failed', onConnectionFailed);
    });
  }
}
```

## Data Models

### JWT Token Claims (from Cognito)

```typescript
interface CognitoIdToken {
  sub: string;              // User ID (UUID)
  email: string;            // User email
  email_verified: boolean;  // Email verification status
  iss: string;              // Issuer (Cognito User Pool URL)
  aud: string;              // Audience (Client ID)
  token_use: 'id';          // Token type
  auth_time: number;        // Authentication timestamp
  exp: number;              // Expiration timestamp
  iat: number;              // Issued at timestamp
  jti: string;              // JWT ID
  'cognito:username': string; // Cognito username
}
```

### Authorizer Context

```python
{
    'userId': str,      # User ID from sub claim
    'email': str,       # User email
}
```

## Error Handling

### Lambda Authorizer Errors

| Error | Cause | Response | Log Message |
|-------|-------|----------|-------------|
| Missing token | No token in query/header | Unauthorized | "No token provided" |
| Invalid signature | JWT signature verification failed | Unauthorized | "Invalid signature" |
| Expired token | Token exp claim < current time | Unauthorized | "Token expired" |
| Invalid issuer | iss claim doesn't match User Pool | Unauthorized | "Invalid issuer" |
| Invalid audience | aud claim doesn't match Client ID | Unauthorized | "Invalid audience" |
| Wrong token type | token_use != 'id' | Unauthorized | "Invalid token_use" |
| Missing config | COGNITO_USER_POOL_ID not set | Unauthorized | "Missing Cognito configuration" |

### Frontend Error Handling

```typescript
// WebSocket connection error
wsClient.on('auth_error', async (error) => {
  console.error('Authentication error:', error);
  
  // Try to refresh token
  try {
    const tokens = await tokenStorage.getTokens();
    if (tokens) {
      const newTokens = await authService.refreshTokens(tokens.refreshToken);
      await tokenStorage.storeTokens(newTokens);
      
      // Retry connection
      await wsClient.connect(newTokens.idToken);
      return;
    }
  } catch (refreshError) {
    console.error('Token refresh failed:', refreshError);
  }
  
  // Redirect to login
  window.location.href = '/login';
});

wsClient.on('connection_failed', (error) => {
  console.error('Connection failed:', error);
  
  // Show user-friendly error
  showError('Connection failed. Please check your network and try again.');
});
```

## Testing Strategy

### Unit Tests

1. **Lambda Authorizer**
   - Test token extraction from query string
   - Test token extraction from Authorization header
   - Test JWT signature validation
   - Test issuer validation
   - Test audience validation
   - Test expiration validation
   - Test token_use validation
   - Test missing configuration handling
   - Test policy generation

2. **WebSocket Client**
   - Test connection with valid token
   - Test connection error handling
   - Test auth error detection
   - Test reconnection logic

3. **Session Creation Orchestrator**
   - Test token refresh before connection
   - Test retry on auth failure
   - Test error propagation

### Integration Tests

1. **End-to-End Auth Flow**
   - Login → Get tokens
   - Connect WebSocket with ID token
   - Verify connection success
   - Create session
   - Verify session created

2. **Token Expiry Handling**
   - Login with short-lived token
   - Wait for near-expiry
   - Attempt connection
   - Verify auto-refresh
   - Verify connection success

3. **Error Scenarios**
   - Connect with expired token → Refresh → Retry
   - Connect with invalid token → Show error
   - Connect with no token → Redirect to login

## Configuration

### Lambda Authorizer Environment Variables

```yaml
COGNITO_USER_POOL_ID: us-east-1_WoaXmyQLQ
COGNITO_CLIENT_ID: 38t8057tbi0o6873qt441kuo3n
AWS_REGION: us-east-1
```

### Lambda Layer Dependencies

Add to `session-management/lambda/authorizer/requirements.txt`:
```
PyJWT[crypto]==2.8.0
cryptography==41.0.0
```

## Deployment Considerations

### Lambda Authorizer Updates

1. Update `requirements.txt` with PyJWT
2. Deploy Lambda layer with new dependencies
3. Update Lambda function code
4. Verify environment variables are set
5. Test with sample token

### Frontend Updates

1. Update WebSocketClient error handling
2. Update SessionCreationOrchestrator retry logic
3. Test with dev environment
4. Deploy to staging
5. Verify end-to-end flow

### Rollback Plan

If issues arise:
1. Revert Lambda authorizer code
2. Keep frontend changes (they're backward compatible)
3. Investigate logs
4. Fix and redeploy

## Security Considerations

### Token Validation

- Always verify JWT signature using Cognito public keys
- Always verify issuer, audience, and expiration
- Never trust client-provided claims without validation
- Cache JWKS for performance but refresh periodically

### Logging

- Log validation failures for debugging
- Never log full tokens in production
- Log user IDs for audit trail
- Use structured logging for CloudWatch Insights

### Error Messages

- Don't leak sensitive information in error messages
- Use generic "Unauthorized" for all auth failures
- Provide detailed logs for debugging (server-side only)

## Performance Considerations

### JWKS Caching

- Cache PyJWKClient instance across Lambda invocations
- Reduces latency from ~200ms to ~50ms
- JWKS keys are rotated infrequently (days/weeks)

### Token Validation

- JWT validation is CPU-intensive (~10-20ms)
- Acceptable for connection establishment
- Not a bottleneck for WebSocket messages

## Success Criteria

1. ✅ WebSocket connections succeed with valid Cognito ID tokens
2. ✅ Invalid tokens are rejected with clear error messages
3. ✅ Expired tokens trigger automatic refresh and retry
4. ✅ Detailed error logs for debugging
5. ✅ No security vulnerabilities in token validation
6. ✅ Performance impact < 50ms for connection establishment
7. ✅ All tests passing

