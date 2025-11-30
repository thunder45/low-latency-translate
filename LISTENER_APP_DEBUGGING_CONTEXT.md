# Listener App Debugging Context

## Task Overview
**Created:** November 30, 2025, 2:55 PM  
**Status:** Ready for new task  
**Goal:** Fix WebSocket connection failures in listener app

---

## Current System State

### ✅ Phase 4 Complete - Backend Working
- Kinesis Data Stream: ACTIVE and processing audio
- audio_processor: Successfully processing batches, generating translations
- Translation pipeline: Transcribe → Translate → TTS → S3 working
- S3 storage: MP3 files being created successfully

### ❌ Listener App: WebSocket Connection Failing
- Error code: 1006 (abnormal closure)
- Connection attempt made but immediately fails
- No error message from backend (empty close reason)
- Reconnect logic triggers but fails repeatedly

---

## Error Details

### Primary Error: WebSocket Connection Failure (Code 1006)

**Error Sequence:**
1. ListenerService initializes
2. WebSocket connect attempt
3. Immediate failure with code 1006
4. No close reason provided
5. Reconnect attempts (all fail)

**Console Logs:**
```
✅ [ListenerService] Initializing WebRTC+WebSocket hybrid service...
✅ [WebSocketClient] Connecting to WebSocket server: wss://2y19uvhyq5.execute-api.us-east-1.amazonaws.com/prod?token=...&sessionId=pure-truth-514&targetLanguage=fr
❌ WebSocket connection to 'wss://...' failed
❌ [WebSocketClient] WebSocket ERROR EVENT
❌ [WebSocketClient] ReadyState: 3 (CLOSED)
❌ [WebSocketClient] WebSocket CLOSED
❌ Close code: 1006 (abnormal closure)
❌ Close reason: (empty)
❌ Was clean: false
❌ ListenerService initialization failed: Error: WebSocket connection error
```

### Secondary Error: Browser Extension Noise
```
content_script.js:1 Uncaught TypeError: Cannot read properties of undefined (reading 'control')
```
**Note:** This is unrelated browser extension noise, can be ignored.

---

## Connection Attempt Details

### WebSocket URL:
```
wss://2y19uvhyq5.execute-api.us-east-1.amazonaws.com/prod
```

### Query Parameters:
- `token`: Valid JWT from Cognito (decoded successfully)
- `sessionId`: pure-truth-514 (speaker session)
- `targetLanguage`: fr (French)

### Token Payload (Decoded):
```json
{
  "sub": "f4b8a408-40f1-70fa-5e6d-3cb74f02c4c4",
  "email_verified": true,
  "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_Tn5BZTL7h",
  "cognito:username": "f4b8a408-40f1-70fa-5e6d-3cb74f02c4c4",
  "aud": "584d2mf9c495vpd68r0efdv2i",
  "event_id": "932bf7c7-67a7-47a9-90d0-fbeab8f9ddcb",
  "token_use": "id",
  "auth_time": 1764092927,
  "exp": 1764513471,  // Valid until Dec 30, 2025
  "iat": 1764509871,
  "jti": "0a1124f9-0940-4d72-9add-aa2ed6e03c2b",
  "email": "advm@advm.lu"
}
```

**Token Status:** ✅ Valid, not expired

---

## Potential Causes

### 1. Backend Connection Handler Issues
**Likelihood:** HIGH

**Possible problems:**
- connection_handler not handling listener connections properly
- Missing or incorrect authentication for listeners
- Lambda error during $connect (check CloudWatch logs)
- DynamoDB query failing when validating session

**Investigation needed:**
- Check connection_handler logs for $connect events
- Verify IAM permissions for Cognito Identity Pool
- Check if Sessions-dev table has session "pure-truth-514"
- Verify Connections-dev table structure

### 2. Query Parameter Parsing
**Likelihood:** MEDIUM

**Possible problems:**
- Backend expects parameters in different format
- sessionId or targetLanguage not being extracted correctly
- Token validation failing silently

**Investigation needed:**
- Review connection_handler.py $connect route
- Check how query parameters are parsed
- Verify token validation logic

### 3. CORS or API Gateway Configuration
**Likelihood:** MEDIUM

**Possible problems:**
- API Gateway not allowing WebSocket upgrade
- CORS headers missing or incorrect
- Route not configured for listener connections

**Investigation needed:**
- Check API Gateway configuration
- Verify $connect route exists and is configured
- Check IAM authorizer (if used)

### 4. DynamoDB Connection Record Creation
**Likelihood:** LOW

**Possible problems:**
- connection_handler fails to create connection record
- GSI (sessionId-targetLanguage-index) missing or misconfigured
- Permission error writing to Connections table

**Investigation needed:**
- Check DynamoDB table schema
- Verify GSI exists
- Check IAM permissions

---

## Files to Investigate

### Frontend (Listener App):
1. `frontend-client-apps/listener-app/src/services/ListenerService.ts`
   - Line 57: Initialization point
   - WebSocket connection setup

2. `frontend-client-apps/shared/src/utils/WebSocketClient.ts`
   - Lines 45-106: Connection and error handling
   - Query parameter construction

3. `frontend-client-apps/listener-app/src/components/ListenerApp.tsx`
   - Line 146: handleSessionJoined() calls initialize()
   - Error handling

### Backend:
4. `session-management/lambda/connection_handler/handler.py`
   - $connect route handler
   - Token validation
   - DynamoDB connection record creation
   - Query parameter parsing

5. `session-management/infrastructure/stacks/session_management_stack.py`
   - WebSocket API configuration
   - Routes and integrations
   - IAM permissions

---

## What's Known to Work

### Speaker App:
- ✅ AudioWorklet capturing audio
- ✅ WebSocket connection successful
- ✅ Audio chunks sent to backend
- ✅ Kinesis receives and batches records
- ✅ Session "pure-truth-514" created in DynamoDB

### Backend Processing:
- ✅ connection_handler receives and processes speaker audio
- ✅ Kinesis batching working (3-second windows)
- ✅ audio_processor transcribes and translates successfully
- ✅ TTS MP3 files generated and stored in S3

### What's Broken:
- ❌ Listener WebSocket $connect fails immediately
- ❌ No connection record created in Connections table
- ❌ Listener cannot receive translatedAudio notifications

---

## Debugging Steps

### Step 1: Check Backend Logs
```bash
# Monitor connection attempts
./scripts/tail-lambda-logs.sh connection-handler

# Look for:
# - $connect events from listener
# - Any errors or exceptions
# - Token validation failures
# - DynamoDB errors
```

### Step 2: Verify Session Exists
```bash
# Check if session exists in DynamoDB
aws dynamodb get-item \
  --table-name Sessions-dev \
  --key '{"sessionId": {"S": "pure-truth-514"}}' \
  --query 'Item'
```

### Step 3: Test WebSocket Manually
```bash
# Use wscat to test connection
npm install -g wscat

wscat -c "wss://2y19uvhyq5.execute-api.us-east-1.amazonaws.com/prod?token=YOUR_TOKEN&sessionId=pure-truth-514&targetLanguage=fr"
```

### Step 4: Check API Gateway Logs
```bash
# Enable CloudWatch logs for API Gateway WebSocket if not already
aws apigatewayv2 get-stage \
  --api-id 2y19uvhyq5 \
  --stage-name prod

# Check logs
aws logs tail /aws/apigateway/2y19uvhyq5/prod
```

### Step 5: Verify IAM Permissions
```bash
# Check Cognito Identity Pool permissions
# Listener should have permissions to connect to WebSocket
```

---

## Connection Handler Code Review Points

### Check in connection_handler.py:

1. **$connect Route:**
   - Does it handle both speaker and listener connections?
   - How does it differentiate between them?
   - Is targetLanguage parameter being read?

2. **Token Validation:**
   - Is token being extracted from query parameters?
   - Is validation working for both Cognito User Pool (speaker) and Identity Pool (listener)?
   - Any errors being swallowed?

3. **Session Validation:**
   - Is sessionId being extracted correctly?
   - Is session being looked up in DynamoDB?
   - What happens if session doesn't exist?

4. **Connection Record Creation:**
   - Is connection record being created with targetLanguage?
   - Is connectionType set correctly (speaker vs listener)?
   - Any DynamoDB write errors?

5. **Error Responses:**
   - Are errors being logged before returning?
   - Is statusCode being set correctly (403, 404, 500)?
   - Is connection being closed properly on error?

---

## Expected Behavior

### Successful Listener Connection:

**Step 1:** Browser sends WebSocket $connect
- URL: wss://.../prod
- Query params: token, sessionId, targetLanguage

**Step 2:** connection_handler $connect route
- Validates token (Cognito)
- Validates session exists (DynamoDB Sessions)
- Creates connection record (DynamoDB Connections)
  - connectionId
  - sessionId
  - targetLanguage
  - connectionType: 'listener'
  - timestamp

**Step 3:** Return 200 OK
- WebSocket connection established
- ReadyState: 1 (OPEN)

**Step 4:** Listener waits for translatedAudio messages
- No immediate messages expected
- Waits for audio_processor to send notifications

---

## Success Criteria for Fix

### After fix is applied:
- [ ] Listener WebSocket connects successfully (ReadyState: 1)
- [ ] No 1006 error code
- [ ] connection_handler logs show successful $connect from listener
- [ ] DynamoDB Connections table has listener connection record
- [ ] Listener receives translatedAudio WebSocket messages
- [ ] S3AudioPlayer downloads and plays MP3 files

---

## Test Session Details

**Session ID:** pure-truth-514  
**Speaker:** Authenticated user (advm@advm.lu)  
**Target Language:** fr (French)  
**Expected:** Listener should connect and receive French translations

---

## Related Issues

### Known from Earlier Work:
- ✅ Speaker WebSocket connection works fine
- ✅ $connect for speaker creates connection record
- ✅ Audio chunking and processing working
- ❓ Listener-specific connection logic may be missing or broken

### Hypothesis:
The connection_handler may only be configured for **speaker** connections. Listener connections might need:
- Different authentication flow (Identity Pool vs User Pool)
- Additional query parameter handling (targetLanguage)
- Different connection record schema
- Separate $connect logic path

---

## Quick Reference

### Backend Lambda:
- **Function:** session-connection-handler-dev
- **File:** session-management/lambda/connection_handler/handler.py
- **Logs:** `./scripts/tail-lambda-logs.sh connection-handler`

### Frontend Files:
- **ListenerService:** frontend-client-apps/listener-app/src/services/ListenerService.ts
- **WebSocketClient:** frontend-client-apps/shared/src/utils/WebSocketClient.ts

### DynamoDB Tables:
- **Sessions:** Sessions-dev
- **Connections:** Connections-dev
- **GSI:** sessionId-targetLanguage-index

### API Gateway:
- **ID:** 2y19uvhyq5
- **Stage:** prod
- **Endpoint:** wss://2y19uvhyq5.execute-api.us-east-1.amazonaws.com/prod

---

## Recommended Investigation Order

1. **Check connection_handler logs** during listener connection attempt
2. **Verify session exists** in Sessions-dev table
3. **Review $connect handler** in connection_handler.py
4. **Check IAM permissions** for Cognito Identity Pool
5. **Test WebSocket manually** with wscat
6. **Fix identified issue**
7. **Test end-to-end** with speaker + listener

---

## Context for AI/Human Developer

**Starting Point:** Phase 4 complete, backend working, listener connection broken

**Problem:** Listener WebSocket connection fails immediately with 1006 error

**Known Good:** Speaker WebSocket works, backend processes audio successfully

**Investigation Focus:** connection_handler $connect logic, especially listener-specific code

**Success:** Listener connects, receives translatedAudio messages, plays audio

---

## Files Changed in This Session (Phase 4)

**Backend:**
- session-management/lambda/connection_handler/handler.py (Kinesis integration)
- session-management/infrastructure/stacks/session_management_stack.py (Kinesis stream)
- audio-transcription/lambda/audio_processor/handler.py (Kinesis batch handler)
- audio-transcription/infrastructure/stacks/audio_transcription_stack.py (Event source)

**Note:** connection_handler was modified for Kinesis, but $connect logic may not have been touched. The listener connection issue might be pre-existing or introduced during Phase 4 changes.

---

## Next Task: Debug and Fix Listener WebSocket Connection

**Priority:** HIGH (blocks end-to-end testing)  
**Estimated Time:** 1-2 hours  
**Dependencies:** None (backend is working)

Start by checking connection_handler logs and reviewing $connect handler logic!
