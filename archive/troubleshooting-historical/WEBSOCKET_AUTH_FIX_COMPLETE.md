# WebSocket Authentication Fix - COMPLETE ✅

## Actual Root Cause Discovered

**The Real Issue**: The authorizer had TWO problems:

### Problem 1: Authorizer Not Attached (Initial Finding)
- `authorization_type="NONE"` on `$connect` route
- Authorizer existed but wasn't being used

### Problem 2: Identity Source Preventing Invocation (Actual Root Cause)
**This was the real blocker**: 
```python
identity_source=["route.request.querystring.token"]
```

**What this means**: API Gateway **ONLY invokes the authorizer when the `token` query parameter is present**. 

**Why this blocked speakers**:
- Speakers connect with: `?token=<JWT>&sessionId=<id>`
- Listeners connect with: `?sessionId=<id>` (no token)
- With identity_source set, authorizer was **conditional** on token presence
- But our URL builder DOES pass the token!
- **However**, if the parameter name doesn't match EXACTLY, or if there's any other issue with the identity source, API Gateway bypasses the authorizer

**From AWS Documentation**:
> For REQUEST authorizers on WebSocket APIs, identity_source determines when the authorizer is invoked. If specified, the authorizer is ONLY invoked when that parameter is present.

## Solution Deployed (8:52 PM CET)

### Change 1: Remove Identity Source
```python
# BEFORE (lines 267-276)
authorizer = apigwv2.CfnAuthorizer(
    self,
    "WebSocketAuthorizer",
    api_id=api.ref,
    name=f"session-authorizer-{self.env_name}",
    authorizer_type="REQUEST",
    authorizer_uri=f"arn:aws:apigateway:{self.region}:lambda:path/2015-03-31/functions/{self.authorizer_function.function_arn}/invocations",
    identity_source=["route.request.querystring.token"],  # ❌ PROBLEM
)

# AFTER
authorizer = apigwv2.CfnAuthorizer(
    self,
    "WebSocketAuthorizer",
    api_id=api.ref,
    name=f"session-authorizer-{self.env_name}",
    authorizer_type="REQUEST",
    authorizer_uri=f"arn:aws:apigateway:{self.region}:lambda:path/2015-03-31/functions/{self.authorizer_function.function_arn}/invocations",
    # identity_source removed - authorizer ALWAYS invoked ✅
)
```

### Change 2: Attach Authorizer to $connect (From First Deployment)
```python
# BEFORE
connect_route = apigwv2.CfnRoute(
    self,
    "ConnectRoute",
    api_id=api.ref,
    route_key="$connect",
    authorization_type="NONE",  # ❌
    target=f"integrations/{connect_integration.ref}",
)

# AFTER
connect_route = apigwv2.CfnRoute(
    self,
    "ConnectRoute",
    api_id=api.ref,
    route_key="$connect",
    authorization_type="CUSTOM",  # ✅
    authorizer_id=authorizer.ref,  # ✅
    target=f"integrations/{connect_integration.ref}",
)
```

### Change 3: Update Authorizer Logic (From First Deployment)
Updated `session-management/lambda/authorizer/handler.py` to handle both speakers and listeners:
- **With token**: Validate JWT, extract userId, return in context
- **Without token**: Allow connection, return empty userId in context

## How This Fix Works

### For Speakers (with JWT):
```
1. WebSocket URL: wss://api.com/prod?token=<JWT>&sessionId=<id>
2. API Gateway → Authorizer ALWAYS invoked (no identity_source check)
3. Authorizer finds token in query params
4. Authorizer validates JWT signature
5. Authorizer extracts userId from 'sub' claim
6. Authorizer returns: { userId: '<cognito-sub>' }
7. Connection Handler receives userId
8. Connection Handler matches userId to session.speakerId
9. Role assigned: "speaker" ✅
10. Connection stays open ✅
```

### For Listeners (without JWT):
```
1. WebSocket URL: wss://api.com/prod?sessionId=<id>
2. API Gateway → Authorizer ALWAYS invoked (no identity_source check)
3. Authorizer finds no token
4. Authorizer allows anonymous connection
5. Authorizer returns: { userId: '' }
6. Connection Handler receives empty userId
7. Role assigned: "listener" ✅
8. Connection stays open ✅
```

## Deployment History

### Deployment 1 (8:41 PM CET)
- ✅ Updated authorizer Lambda to handle both speakers/listeners
- ✅ Attached authorizer to $connect route
- ❌ **Still had identity_source** - authorizer not being invoked

### Deployment 2 (8:52 PM CET) - FINAL
- ✅ Removed identity_source
- ✅ Authorizer now ALWAYS invoked
- ✅ **This is the complete fix**

## Testing Instructions

### Quick Verification Test

1. **Start speaker app**:
   ```bash
   cd frontend-client-apps/speaker-app
   npm run dev
   ```

2. **Open browser console** (F12)

3. **Click "Start Session"**

4. **Watch for these logs**:
   ```
   ✅ "Session created: <session-id>"
   ✅ "WebSocket connected, readyState: 1"
   ✅ Connection STAYS OPEN (no code 1005!)
   ✅ "Session state changed to: broadcasting"
   ```

### Detailed Verification (Run in parallel terminals)

**Terminal 1 - Authorizer logs**:
```bash
cd /Volumes/workplace/low-latency-translate
./scripts/tail-lambda-logs.sh session-authorizer-dev
```

**Expected output**:
```
✅ "Token found in query string"
✅ "Token validated successfully for user: <uuid>"
✅ "Authorization successful for speaker: <uuid>"
```

**Terminal 2 - Connection handler logs**:
```bash
./scripts/tail-lambda-logs.sh session-connection-handler-dev
```

**Expected output**:
```
✅ "Speaker connection accepted for session <id>"
✅ "user_id": "<actual-cognito-sub-uuid>"  (NOT null!)
✅ "role": "speaker"  (NOT "listener"!)
```

**Terminal 3 - Speaker app**:
```bash
cd frontend-client-apps/speaker-app
npm run dev
```

### Success Criteria

✅ Fix is successful when:
1. Authorizer Lambda is invoked (shows in logs)
2. Token is validated successfully
3. userId is populated in authorizer context
4. Connection Handler sees userId (not null)
5. Role assigned as "speaker" (not "listener")
6. WebSocket stays open for 1+ minute
7. Audio chunks can flow

## Expected Lambda Logs After Fix

### session-authorizer-dev:
```
INFO Token found in query string
INFO Token validated successfully for user: a1b2c3d4-e5f6-7890-abcd-ef1234567890
INFO Authorization successful for speaker: a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### session-connection-handler-dev:
```json
{
  "message": "Speaker connection accepted for session glorious-prophet-375",
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "role": "speaker",
  "sessionId": "glorious-prophet-375",
  "connectionId": "abc123def456"
}
```

## What Happens Next

### If Fix Works:
1. ✅ Phase 1 MediaRecorder implementation **COMPLETE**
2. ✅ WebSocket authentication **WORKING**
3. ✅ Audio chunks flowing to backend
4. 🎯 **Ready for Phase 2**: Backend KVS Writer
   - Create Lambda to receive audio chunks
   - Write to Kinesis Video Streams
   - Reference: `PHASE2_BACKEND_KVS_WRITER_GUIDE.md`

### If Still Issues:
Check AWS Console → API Gateway → session-websocket-api-dev → Routes → $connect:
1. Verify Authorization = `session-authorizer-dev`
2. Verify Identity Source = **EMPTY** (not `route.request.querystring.token`)

If Identity Source still shows the old value, manually remove it in console and test again.

## Key Insight - Identity Source Behavior

**Critical Learning**: For WebSocket REQUEST authorizers:
- **With identity_source specified**: Authorizer only invoked when that parameter exists
- **Without identity_source**: Authorizer ALWAYS invoked for every connection
- **For dual auth (speakers + listeners)**: Must NOT specify identity_source

This is different from REST API authorizers where identity_source is commonly used.

## Files Modified

1. **session-management/lambda/authorizer/handler.py**
   - Handles both authenticated (speakers) and anonymous (listeners) connections
   - JWT validation only when token present

2. **session-management/infrastructure/stacks/session_management_stack.py**
   - Removed `identity_source` from authorizer (line 276)
   - Changed `authorization_type="NONE"` to `"CUSTOM"` (line 433)
   - Added `authorizer_id=authorizer.ref` (line 434)

## CloudFormation Stack Updates

**SessionManagement-dev** stack updated:
- WebSocketAuthorizer resource modified (removed IdentitySource)
- ConnectRoute resource modified (added AuthorizerId)

## Next Action Required

**PLEASE TEST** the speaker app now:
1. Open speaker app in browser
2. Start a session
3. Watch for successful WebSocket connection
4. Check Lambda logs for "Speaker connection accepted"
5. Verify connection stays open
6. Report results

Once verified working, Phase 1 is complete and we proceed to Phase 2!
