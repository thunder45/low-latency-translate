# WebSocket Authentication Fix - Summary

## Problem Identified

**Root Cause**: The JWT authorizer was NOT attached to the `$connect` route, causing all connections to be treated as anonymous listeners instead of authenticated speakers.

### Observable Symptoms
```
1. HTTP API creates session "glorious-prophet-375" ✅
2. WebSocket connects with readyState: 1 ✅
3. Lambda logs: "Listener connection accepted" ❌ WRONG ROLE
   - user_id: null ❌ 
   - role: "listener" ❌
4. Lambda returns 200 OK ✅
5. ~1 second later: WebSocket closes (code 1005) ❌
6. startBroadcast() fails: "WebSocket not connected" ❌
```

### Why It Happened
1. The `session_management_stack.py` had `authorization_type="NONE"` on the `$connect` route
2. Without the authorizer, the JWT token in the query parameter was never validated
3. The `connection_handler` Lambda received `user_id: null` in the authorizer context
4. Without a valid userId, the connection couldn't be matched to the session speaker
5. Connection was treated as a listener, which caused role mismatch
6. The connection closed because it wasn't properly associated with the session

## Solution Implemented

### 1. Updated Lambda Authorizer (`session-management/lambda/authorizer/handler.py`)

**Before**: Rejected all connections without tokens (blocking listeners)

**After**: Handles both authenticated and anonymous connections:
```python
# Case 1: No token provided - Allow as anonymous listener
if not token:
    logger.info('No token provided - authorizing as anonymous listener')
    policy = generate_policy(
        principal_id='anonymous',
        effect='Allow',
        resource=method_arn,
        context={
            'userId': '',  # Empty string for listeners
            'email': '',
        }
    )
    return policy

# Case 2: Token provided - Validate and authorize as speaker
decoded = validate_token(token)
user_id = decoded.get('sub')
policy = generate_policy(
    principal_id=user_id,
    effect='Allow',
    resource=method_arn,
    context={
        'userId': user_id,
        'email': email or '',
    }
)
```

### 2. Attached Authorizer to $connect Route (`session_management_stack.py`)

**Before**:
```python
connect_route = apigwv2.CfnRoute(
    self,
    "ConnectRoute",
    api_id=api.ref,
    route_key="$connect",
    authorization_type="NONE",  # ❌ No authorizer!
    target=f"integrations/{connect_integration.ref}",
)
```

**After**:
```python
connect_route = apigwv2.CfnRoute(
    self,
    "ConnectRoute",
    api_id=api.ref,
    route_key="$connect",
    authorization_type="CUSTOM",  # ✅ Custom authorizer
    authorizer_id=authorizer.ref,  # ✅ Attached!
    target=f"integrations/{connect_integration.ref}",
)
```

## What Changed in the Flow

### NEW Connection Flow (After Fix)

#### For Speakers (with JWT token):
```
1. Frontend: wss://api.com/prod?token=<JWT>&sessionId=<id>
2. API Gateway → JWT Authorizer Lambda
3. Authorizer: Validates JWT signature against Cognito
4. Authorizer: Extracts userId from JWT claims (sub)
5. Authorizer: Returns Allow policy with context: { userId: <cognito-sub> }
6. Connection Handler: Receives authorizer context with userId
7. Connection Handler: Matches userId to session.speakerId
8. Connection Handler: Assigns role="speaker" ✅
9. Connection Handler: Saves to DynamoDB with proper role
10. Connection stays open ✅
11. Audio streaming works ✅
```

#### For Listeners (without JWT token):
```
1. Frontend: wss://api.com/prod?sessionId=<id>
2. API Gateway → JWT Authorizer Lambda
3. Authorizer: No token provided
4. Authorizer: Returns Allow policy with context: { userId: '' }
5. Connection Handler: Receives authorizer context with empty userId
6. Connection Handler: Assigns role="listener" ✅
7. Connection Handler: Saves to DynamoDB with proper role
8. Connection stays open ✅
9. Translation streaming works ✅
```

## Deployment Status

**Deployed**: November 26, 2025 at 8:41 PM CET

**Stack**: `SessionManagement-dev`

**Changes**:
- ✅ Lambda Authorizer function updated
- ✅ ConnectRoute updated with authorizer attachment
- ✅ No other infrastructure changes required

**Endpoints** (unchanged):
- WebSocket: `wss://2y19uvhyq5.execute-api.us-east-1.amazonaws.com/prod`
- HTTP API: `https://gcneupzdtf.execute-api.us-east-1.amazonaws.com`

## Expected Behavior After Fix

### For Speaker Connections:
1. **Lambda logs will show**:
   ```
   Authorizer: "Token validated successfully for user: <cognito-sub>"
   Connection Handler: "Speaker connection accepted for session <id>"
   user_id: "<actual-cognito-sub>"  ✅
   role: "speaker"  ✅
   ```

2. **WebSocket stays open**: No premature disconnection
3. **Audio streaming works**: `startBroadcast()` succeeds
4. **Audio chunks flow**: MediaRecorder → WebSocket → Lambda

### For Listener Connections:
1. **Lambda logs will show**:
   ```
   Authorizer: "No token provided - authorizing as anonymous listener"
   Connection Handler: "Listener connection accepted for session <id>"
   user_id: null
   role: "listener"  ✅
   ```

2. **WebSocket stays open**: Connection maintained
3. **Translation streaming works**: S3 → Listener

## Testing Instructions

### Test 1: Verify Speaker Connection (CRITICAL)

1. **Start the speaker app**:
   ```bash
   cd frontend-client-apps/speaker-app
   npm run dev
   ```

2. **Open browser console** and watch for:
   ```
   ✅ "Session created: glorious-prophet-375"
   ✅ "WebSocket connected, readyState: 1"
   ✅ "Session state changed to: broadcasting"
   ✅ "Broadcasting audio..."
   ```

3. **Check Lambda logs**:
   ```bash
   cd /Volumes/workplace/low-latency-translate
   ./scripts/tail-lambda-logs.sh session-authorizer-dev
   ```
   
   **Look for**:
   ```
   ✅ "Token validated successfully for user: <uuid>"
   ✅ "Authorization successful for speaker: <uuid>"
   ```

4. **Check connection handler logs**:
   ```bash
   ./scripts/tail-lambda-logs.sh session-connection-handler-dev
   ```
   
   **Look for**:
   ```
   ✅ "Speaker connection accepted for session <id>"
   ✅ "user_id": "<actual-uuid>"  (NOT null)
   ✅ "role": "speaker"  (NOT "listener")
   ```

5. **Verify connection stays open**:
   - Wait 5 seconds
   - WebSocket should remain connected (readyState: 1)
   - No code 1005 disconnection
   - Audio chunks should start flowing

### Test 2: Verify Audio Streaming

1. **Click the microphone button**
2. **Speak into microphone**
3. **Check browser console**:
   ```
   ✅ "Audio chunk sent: 1234 bytes"
   ✅ "Audio chunk sent: 1567 bytes"
   ```
4. **Connection should stay open** for entire broadcast duration

### Test 3: Verify Listener Connection (Optional)

1. **Open listener app** with session URL
2. **Check connection**:
   - Should connect successfully as anonymous listener
   - No JWT token required
   - Connection stays open

## Success Criteria

The fix is successful when:
- [x] **Deployed successfully** ✅
- [ ] Lambda logs show: "Speaker connection accepted"
- [ ] `user_id` shows actual Cognito sub (not null)
- [ ] `role: "speaker"` (not "listener")
- [ ] WebSocket stays open for at least 1 minute
- [ ] `startBroadcast()` can access open WebSocket
- [ ] Audio chunks start flowing to backend

## Next Steps After Verification

Once the WebSocket connection stays open:

1. **Phase 1 is COMPLETE** ✅
   - MediaRecorder audio streaming fully working
   - WebSocket authentication fixed
   - Audio chunks flowing to backend

2. **Ready for Phase 2**: Backend KVS Writer
   - Reference: `PHASE2_BACKEND_KVS_WRITER_GUIDE.md`
   - Create `kvs_stream_writer` Lambda
   - Process audio chunks from WebSocket
   - Write to Kinesis Video Streams

## Rollback Instructions (If Needed)

If the fix causes issues:

```bash
# Revert the authorizer Lambda
cd session-management/lambda/authorizer
git checkout HEAD~1 handler.py

# Revert the infrastructure
cd ../infrastructure/stacks
git checkout HEAD~1 session_management_stack.py

# Redeploy
cd ..
make deploy-websocket-dev
```

## Files Modified

1. `session-management/lambda/authorizer/handler.py`
   - Updated to handle both speakers and listeners
   - Speakers: JWT validated, userId extracted
   - Listeners: No JWT required, empty userId

2. `session-management/infrastructure/stacks/session_management_stack.py`
   - Changed `authorization_type="NONE"` to `"CUSTOM"`
   - Added `authorizer_id=authorizer.ref` to $connect route
   - Updated comments to reflect new behavior

## Technical Details

### JWT Token Flow
1. Frontend obtains JWT from Cognito (already working)
2. Frontend adds token to WebSocket URL: `?token=<jwt>`
3. API Gateway extracts token from query parameter
4. Authorizer validates:
   - Signature (using Cognito public keys)
   - Issuer (Cognito User Pool)
   - Audience (Cognito Client ID)
   - Expiration (not expired)
   - Token use (must be 'id' token)
5. Authorizer extracts userId from 'sub' claim
6. Authorizer returns policy with userId in context
7. Connection handler receives userId from context

### Why Connection Was Closing

The 1005 close code indicated an internal error. The root cause:
1. Connection was authenticated as listener (wrong role)
2. Session expected a speaker connection
3. Role mismatch caused the connection to be invalid
4. WebSocket closed automatically due to this mismatch

## References

- WebSocket Disconnect Debug: `WEBSOCKET_DISCONNECT_DEBUG.md`
- Phase 1 Complete: `CHECKPOINT_PHASE1_COMPLETE.md`
- Phase 1 Guide: `PHASE1_SPEAKER_MEDIARECORDER_GUIDE.md`
- Architecture Decisions: `ARCHITECTURE_DECISIONS.md`
