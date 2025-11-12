# WebSocket Authorization Architecture

## AWS API Gateway WebSocket Limitation

**AWS API Gateway WebSocket APIs only support custom authorizers on the `$connect` route.**

Custom routes (like `refreshConnection`, `heartbeat`, etc.) **cannot** use API Gateway-level authorization. This is a platform limitation documented by AWS.

### Error Message
```
Currently, authorization is restricted to the $connect route only
(Service: AmazonApiGatewayV2; Status Code: 400; Error Code: BadRequestException)
```

## Our Authorization Strategy

### 1. `$connect` Route (API Gateway Authorizer)
- ✅ Uses Lambda Authorizer at API Gateway level
- ✅ Validates JWT token before connection is established
- ✅ Passes user context to Lambda functions via `event['requestContext']['authorizer']`
- ✅ Applies to: Speaker session creation, listener joining

### 2. Custom Routes (Application-Level Authorization)
- ⚠️ Cannot use API Gateway authorizers
- ✅ Implement JWT validation in Lambda function code
- ✅ Token passed via query string parameter: `?token=<JWT>`
- ✅ Applies to: `refreshConnection` route for speakers

## Implementation Details

### Routes with API Gateway Authorization
```python
# $connect route - AUTHORIZED
connect_route = apigwv2.CfnRoute(
    api_id=api.ref,
    route_key="$connect",
    authorization_type="CUSTOM",
    authorizer_id=authorizer.ref,  # ✅ Authorizer applied
)
```

### Routes with Application-Level Authorization
```python
# refreshConnection route - NO API GATEWAY AUTHORIZER
refresh_route = apigwv2.CfnRoute(
    api_id=api.ref,
    route_key="refreshConnection",
    # No authorization_type or authorizer_id
)
```

**Lambda function validates token:**
```python
# In refresh_handler/handler.py
from auth_validator import validate_speaker_token

def handle_speaker_refresh(event, connection_id, session_id, session):
    # Get token from query string
    token = event.get('queryStringParameters', {}).get('token')
    
    # Validate JWT token
    claims = validate_speaker_token(token)
    if not claims:
        return error_response(401, 'UNAUTHORIZED', 'Invalid token')
    
    # Validate user identity matches session
    user_id = claims.get('sub')
    if user_id != session.get('speakerUserId'):
        return error_response(403, 'FORBIDDEN', 'Identity mismatch')
```

## Security Considerations

### Why This Is Secure

1. **Initial Connection Authorized**: All connections go through `$connect` with API Gateway authorizer
2. **Token Validation**: Application-level validation uses same JWT validation logic as authorizer
3. **Identity Verification**: Speaker identity is verified against session owner
4. **Token Expiration**: JWT expiration is checked on every request
5. **Cognito Public Keys**: Keys are fetched and cached from Cognito JWKS endpoint

### Attack Scenarios & Mitigations

| Attack | Mitigation |
|--------|-----------|
| **Forged token** | JWT signature validation (requires valid Cognito signature) |
| **Expired token** | Expiration timestamp checked on every request |
| **Wrong user** | User ID from token must match session owner |
| **Replay attack** | Token expiration limits replay window to token lifetime |
| **Token theft** | HTTPS/WSS encryption protects token in transit |

### Limitations

1. **No rate limiting at API Gateway level** for custom routes
   - Mitigation: Implement rate limiting in Lambda function
   
2. **Token in query string** (visible in logs)
   - Mitigation: Use short-lived tokens (1 hour), sanitize logs
   
3. **Slightly higher latency** (Lambda validation vs API Gateway)
   - Impact: ~10-20ms additional latency (acceptable for refresh operation)

## Routes Authorization Summary

| Route | Authorization Method | Token Location | Validates |
|-------|---------------------|----------------|-----------|
| `$connect` | API Gateway Authorizer | Query string `?token=` | JWT signature, claims, expiration |
| `$disconnect` | None (automatic cleanup) | N/A | N/A |
| `heartbeat` | None (listeners only) | N/A | N/A |
| `refreshConnection` | Application-level | Query string `?token=` | JWT signature, claims, identity match |

## Client Implementation

### Speaker Connection Refresh
```javascript
// Client must include token in query string
const token = await getValidCognitoToken();
const message = {
  action: 'refreshConnection',
  sessionId: 'golden-eagle-427',
  role: 'speaker'
};

// Token passed in query string (not in message body)
websocket.send(JSON.stringify(message));
// Note: Token should be in connection URL: wss://api.example.com/prod?token=<JWT>
```

### Listener Connection Refresh
```javascript
// Listeners don't need authentication for refresh
const message = {
  action: 'refreshConnection',
  sessionId: 'golden-eagle-427',
  role: 'listener',
  targetLanguage: 'es'
};
websocket.send(JSON.stringify(message));
```

## Testing

### Test Invalid Token
```bash
# Should return 401 Unauthorized
wscat -c "wss://api.example.com/prod?token=invalid"
{"action": "refreshConnection", "sessionId": "test-123", "role": "speaker"}
```

### Test Expired Token
```bash
# Should return 401 Unauthorized
wscat -c "wss://api.example.com/prod?token=<EXPIRED_JWT>"
{"action": "refreshConnection", "sessionId": "test-123", "role": "speaker"}
```

### Test Wrong User
```bash
# Should return 403 Forbidden
wscat -c "wss://api.example.com/prod?token=<VALID_JWT_DIFFERENT_USER>"
{"action": "refreshConnection", "sessionId": "test-123", "role": "speaker"}
```

### Test Valid Token
```bash
# Should return connectionRefreshComplete
wscat -c "wss://api.example.com/prod?token=<VALID_JWT>"
{"action": "refreshConnection", "sessionId": "test-123", "role": "speaker"}
```

## References

- [AWS API Gateway WebSocket Authorization](https://docs.aws.amazon.com/apigateway/latest/developerguide/websocket-api-lambda-auth.html)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)
- [Cognito JWT Validation](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-tokens-verifying-a-jwt.html)
