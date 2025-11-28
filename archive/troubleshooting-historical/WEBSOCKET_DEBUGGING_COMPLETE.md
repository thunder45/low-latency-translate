# WebSocket Connection Debugging - Complete Resolution

## Executive Summary

Phase 1 Traditional KVS Stream architecture was blocked by WebSocket connection issues. After extensive debugging, we identified and fixed **FOUR separate bugs**:

### Backend Issues (3):
1. Authorizer not attached to $connect route
2. Identity source preventing authorizer invocation
3. Connection record not created in DynamoDB

### Frontend Issue (1):
4. React useEffect cleanup disconnecting WebSocket prematurely

**Status**: All issues resolved. WebSocket connections now stable, audio streaming working, Phase 1 complete.

## Complete Timeline & Root Cause Analysis

### Issue 1: Authorizer Not Attached (Discovered 8:38 PM, Nov 26)

**Symptom**: JWT authorizer never invoked, all connections treated as listeners
**Evidence**:
- Lambda logs: `user_id: null`, `role: "listener"` (should be "speaker")
- Connection closed with code 1005 within 1 second

**Root Cause**:
```python
# session_management_stack.py line 427
connect_route = apigwv2.CfnRoute(
    authorization_type="NONE",  # ❌ No authorizer!
)
```

**Fix**:
```python
connect_route = apigwv2.CfnRoute(
    authorization_type="CUSTOM",
    authorizer_id=authorizer.ref,  # ✅ Attached!
)
```

### Issue 2: Identity Source Blocking Invocation (Discovered 8:52 PM, Nov 26)

**Symptom**: Even with authorizer attached, it wasn't being invoked
**Evidence**:
- No authorizer logs in CloudWatch
- wscat tests showed no invocation
- AWS Console showed authorizer configured but not active

**Root Cause**:
```python
# session_management_stack.py line 276
authorizer = apigwv2.CfnAuthorizer(
    identity_source=["route.request.querystring.token"],  # ❌ Only invokes when token present!
)
```

From AWS Documentation:
> For REQUEST authorizers on WebSocket APIs, identity_source determines when the authorizer is invoked. If specified, the authorizer is ONLY invoked when that parameter is present.

**Fix**:
```python
authorizer = apigwv2.CfnAuthorizer(
    # identity_source removed - authorizer ALWAYS invoked ✅
)
```

### Issue 3: CDK Not Creating API Gateway Deployments (Discovered 9:03 PM, Nov 26)

**Symptom**: Fixes deployed but authorizer still not working
**Evidence**:
- CDK showed "no changes"
- Stage using deployment from 11:15 AM (old config)
- No new deployments created after 7 PM

**Root Cause**: CDK doesn't trigger new API Gateway deployments when only Lambda code or authorizer configuration changes (infrastructure change detection limitation)

**Solution**:
1. Manual deployment creation: `aws apigatewayv2 create-deployment`
2. Manual stage update: `aws apigatewayv2 update-stage`
3. **Automated in Makefile** (added to `deploy-websocket-dev`)

**Deployments Created**:
- `voq9om` (20:03:42) - Authorizer config fix
- `4s7n0v` (20:21:01) - Response format fix
- `4sz151` (20:28:46) - Connection record creation
- `eyvcga` (21:44:46) - Error logging added

### Issue 4: Connection Record Not Created (Discovered 9:24 PM, Nov 26)

**Symptom**: Connection authenticated correctly but closed after 1 second
**Evidence**:
- Authorizer logs: "Token validated", "Authorization successful"
- Connection handler: "Speaker connection accepted", `user_id: "44688478-b021-706b-8c3d-02481ffc9d2b"`, `role: "speaker"`
- **Disconnect handler**: "Connection not found in database (already cleaned up)"

**Root Cause**:
```python
# connection_handler.py lines 188-192 (original)
# Note: We don't create the full connection record here yet
# That happens in joinSession MESSAGE event for listeners
# For speakers, the connection was already created during HTTP session creation
return {'statusCode': 200}
```

This comment was **WRONG**! The HTTP API creates the SESSION, not the speaker's CONNECTION record. Without a connection record, the disconnect handler couldn't find it, causing premature disconnection.

**Fix**:
```python
# connection_handler.py lines 179-207 (fixed)
# Create connection record in DynamoDB
# CRITICAL: Must create this during $connect so disconnect handler can find it
try:
    connections_repo.create_connection(
        connection_id=connection_id,
        session_id=session_id,
        role=role,
        target_language=session.get('sourceLanguage') if role == 'listener' else None,
        ip_address=ip_address,
        session_max_duration_hours=SESSION_MAX_DURATION_HOURS
    )
    logger.info("Connection record created successfully in DynamoDB")
except Exception as e:
    logger.error(f"CRITICAL: Failed to create connection record: {str(e)}")
    return error_response(status_code=500, error_code='DB_WRITE_FAILED')
```

### Issue 5: Frontend useEffect Cleanup (Discovered 10:00 AM, Nov 27)

**Symptom**: WebSocket opened successfully but closed before startBroadcast could use it
**Evidence** from console logs:
```
08:54:36.328 - WebSocket OPENED
08:54:36.328 - SpeakerService init complete
08:54:36.328 - [SessionOrchestrator] Cleaning up resources... ← PREMATURE!
08:54:36.328 - [SessionOrchestrator] Disconnecting WebSocket...
08:54:36.439 - WebSocket CLOSED
08:54:36.440 - startBroadcast() fails
```

**Root Cause**:
```typescript
// SpeakerApp.tsx lines 206-220 (original)
useEffect(() => {
  return () => {
    if (orchestrator) orchestrator.abort();
    if (speakerService) speakerService.cleanup();
  };
}, [speakerService, orchestrator]);  // ❌ Cleanup runs when dependencies change!
```

When `setSpeakerService(service)` was called, it changed the dependency, triggering the cleanup function which called `orchestrator.abort()` which disconnected the WebSocket!

**Fix**:
```typescript
useEffect(() => {
  return () => {
    if (orchestrator) orchestrator.abort();
    if (speakerService) speakerService.cleanup();
  };
}, []);  // ✅ Empty deps - only runs on mount/unmount!
```

## Files Modified

### Backend:
1. `session-management/lambda/authorizer/handler.py`
   - Handles both authenticated speakers (with JWT) and anonymous listeners (without JWT)
   
2. `session-management/infrastructure/stacks/session_management_stack.py`
   - Removed `identity_source` from authorizer (line 267-276)
   - Attached authorizer to $connect route (line 433-434)
   
3. `session-management/lambda/connection_handler/handler.py`
   - Creates connection record during $connect (lines 179-207)
   - Returns `{'statusCode': 200}` for $connect (no body field)
   - Added error logging for connection record creation

4. `session-management/Makefile`
   - Added auto-deployment to `deploy-websocket-dev` target
   - Creates API Gateway deployment automatically
   - Updates stage automatically

### Frontend:
5. `frontend-client-apps/speaker-app/src/components/SpeakerApp.tsx`
   - Fixed useEffect dependencies to empty array (line 217)
   - Removed premature orchestrator cleanup

6. `frontend-client-apps/shared/websocket/WebSocketClient.ts`
   - Added comprehensive logging (can be removed in production)
   - Logs connection, messages, errors, close events with timestamps

## Verification - Working System

**Test Results** (Nov 27, 10:02 AM):
```
✅ Session created: gracious-faith-726
✅ WebSocket connected (readyState: 1)
✅ Authorizer validated JWT
✅ Connection record created
✅ Audio streaming started
✅ 90+ chunks sent over 30 seconds
✅ Status polling working (every 5 seconds)
✅ Clean session end
✅ WebSocket stayed open entire duration
```

## Key Learnings

### 1. WebSocket REQUEST Authorizer Behavior
- **With identity_source**: Only invoked when specified parameter present
- **Without identity_source**: Always invoked for every connection
- For dual authentication (speakers + listeners), must NOT specify identity_source

### 2. API Gateway Deployment Detection
- CDK doesn't create new deployments for Lambda-only changes
- Must manually create deployment after infrastructure changes
- Automated in Makefile for future deployments

### 3. $connect Response Format
Per AWS documentation:
```python
# Correct
return {"statusCode": 200}

# Incorrect (was causing issues)
return {"statusCode": 200, "body": "{}"}
```

### 4. Connection Record Lifecycle
- Must create during $connect (not MESSAGE event)
- Disconnect handler needs it to clean up properly
- Without it, connections close immediately

### 5. React useEffect Dependencies
- Include state in dependencies → cleanup runs on state changes
- Empty dependencies → cleanup only on unmount
- Be careful with cleanup functions that disconnect resources

## Testing Tools

### wscat Test Script
`scripts/test-websocket-auth.sh` - Tests WebSocket connection without browser

### Log Monitoring
```bash
# Authorizer
./scripts/tail-lambda-logs.sh session-authorizer-dev

# Connection Handler  
./scripts/tail-lambda-logs.sh session-connection-handler-dev

# Disconnect Handler
aws logs tail /aws/lambda/session-disconnect-handler-dev --since 5m --follow
```

## Current Deployment

**API Gateway**: 
- API ID: `2y19uvhyq5`
- Deployment: `eyvcga`
- Stage: `prod`
- Last Updated: Nov 26, 21:44:46

**Configuration**:
- Authorizer: Attached to $connect, no identity_source
- Connection Handler: Creates connection records
- Frontend: useEffect fixed, logging enhanced

## Phase 1 Status

**COMPLETE** ✅

All blocking issues resolved:
- MediaRecorder audio streaming working
- WebSocket authentication working
- Connection stability achieved
- Audio chunks flowing to backend
- Clean session lifecycle

Ready for Phase 2: Backend KVS Writer Lambda
