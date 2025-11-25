# KVS WebRTC Connection Testing Guide

## Critical: Correct Testing Sequence ⚠️

The error you're seeing (`SESSION_NOT_FOUND`) indicates the **speaker hasn't started broadcasting yet** when the listener tries to connect.

### Why This Happens

```
Current Flow (WRONG):
1. Speaker creates session ✅
2. Listener joins session ❌ (speaker not broadcasting)
3. Listener tries KVS connection ❌
4. Error: SESSION_NOT_FOUND (no master on KVS channel)

Correct Flow:
1. Speaker creates session ✅
2. Speaker starts broadcasting ✅ (KVS master connection)
3. Wait for "Connected as Master" log ✅
4. Listener joins session ✅
5. Listener waits 3 seconds ✅
6. Listener connects as viewer ✅
7. Audio streaming works! ✅
```

### The Problem

Looking at your logs:
```
[ListenerService] Session verified after 143ms ✅
[ListenerService] Waiting 3 seconds for speaker KVS master connection... ✅
[ListenerService] Ready to connect to KVS as viewer ✅
[KVS] Viewer connection attempt 1/3... ✅
[KVS] Connecting as Viewer (Listener)... ✅
[KVS] ICE servers obtained: 2 ✅
[KVS] Opening signaling channel... ✅
[KVS] Connected as Viewer, waiting for media from Master ✅
WebSocket connection to 'wss://m-787070a8.kinesisvideo...' failed ❌
```

The session exists, the 3-second delay passed, but **the speaker still hasn't connected as master**!

## Solution: Test in Correct Order

### Step-by-Step Testing

**Terminal 1 - Speaker App:**
```bash
cd frontend-client-apps/speaker-app
npm run dev
```

**Actions in Speaker App:**
1. ✅ Login with credentials
2. ✅ Click "New Session"
3. ✅ Allow microphone access when prompted
4. ✅ **WAIT for this log:** `[KVS] Connected as Master, ready for viewers`
5. ✅ **Note the session ID** (e.g., "serene-truth-682")
6. ✅ Verify you see: `[SpeakerService] WebRTC broadcast started`

**Terminal 2 - Listener App (ONLY AFTER STEP 6 ABOVE):**
```bash
cd frontend-client-apps/listener-app
npm run dev
```

**Actions in Listener App:**
1. ✅ Login with credentials
2. ✅ Enter the session ID from speaker
3. ✅ Select target language
4. ✅ Click "Join Session"
5. ✅ Wait for connection (~5 seconds total)
6. ✅ Verify audio playback starts

### Expected Logs - Speaker

```
[SpeakerService] Starting WebRTC broadcast...
[KVS] Connecting as Master (Speaker)...
[KVS] ICE servers obtained: 2
[KVS] Requesting microphone access...
[KVS] Microphone access granted
[KVS] Added audio track to peer connection
[KVS] Opening signaling channel...
[KVS] Signaling channel opened as Master  👈 SPEAKER IS READY!
[KVS] Connected as Master, ready for viewers  👈 NOW LISTENER CAN JOIN!
[SpeakerService] WebRTC broadcast started
```

### Expected Logs - Listener

```
[ListenerService] Starting WebRTC audio reception...
[ListenerService] Waiting for speaker to establish KVS connection...
[ListenerService] Session verified after Xms
[ListenerService] Waiting 3 seconds for speaker KVS master connection...
[ListenerService] Ready to connect to KVS as viewer
[KVS] Viewer connection attempt 1/3...
[KVS] ICE servers obtained: 2
[KVS] Opening signaling channel...
[KVS] Signaling channel opened as Viewer, creating offer...
[KVS] Created and set local SDP offer
[KVS] Sent SDP offer to Master
[KVS] Received SDP answer from: (master-id)  👈 SPEAKER RESPONDED!
[KVS] Set remote description (answer)
[KVS] ICE connection state: checking
[KVS] ICE connection state: connected  👈 SUCCESS!
[ListenerService] Received remote audio track
[ListenerService] Audio track connected to player
```

## Common Mistakes

### ❌ Mistake 1: Listener Joins Before Speaker Broadcasts

**Symptom:**
```
WebSocket connection to 'wss://m-xxx.kinesisvideo...' failed
SESSION_NOT_FOUND
```

**Fix:** Make sure speaker has started broadcasting first! Look for "Connected as Master" log.

### ❌ Mistake 2: Speaker Creates Session But Doesn't Broadcast

**Symptom:**
- Session ID is valid
- No KVS connection errors in speaker
- Listener gets SESSION_NOT_FOUND

**Fix:** Speaker must click the microphone button to start broadcasting, not just create the session.

### ❌ Mistake 3: Not Waiting Long Enough

**Symptom:**
- Session verified quickly (<500ms)
- Still get SESSION_NOT_FOUND after 3s delay

**Fix:** Speaker took >3 seconds to establish KVS connection. Increase delay or ensure speaker connects faster.

## Debugging Steps

### 1. Verify Speaker is Broadcasting

**In Speaker App Console:**
```javascript
// Should see these logs:
✅ [KVS] Connected as Master, ready for viewers
✅ [KVS] Signaling channel opened as Master
✅ [SpeakerService] WebRTC broadcast started
```

**If NOT seen:**
- Speaker didn't click broadcast button
- Microphone permission denied
- KVS connection failed (check speaker credentials)

### 2. Check Session Exists

```bash
# Check session in DynamoDB
curl https://sj1yqxts79.execute-api.us-east-1.amazonaws.com/sessions/SESSION-ID

# Should return session with kvsChannelArn and kvsSignalingEndpoints
```

### 3. Check KVS Channel Status

```bash
# Verify channel exists and is ACTIVE
aws kinesisvideo describe-signaling-channel \
  --channel-name session-SESSION-ID \
  --region us-east-1 \
  --query 'ChannelInfo.ChannelStatus'
  
# Should return: "ACTIVE"
```

### 4. Manual Connection Test

If automated testing fails, try manual sequence:

```
1. Speaker: Start app, login, create session
2. Speaker: Click microphone button
3. Speaker: Wait 5 seconds (ensure KVS connection stable)
4. Speaker: Share session ID
5. Listener: Start app, login
6. Listener: Enter session ID  
7. Listener: Click join
8. Listener: Should connect successfully
```

## Tuning the Delays

Current timing:
- Session verification polling: Every 1s, up to 15s
- Stability delay: 3 seconds
- KVS retry: 3 attempts with 2s, 3s, 4.5s delays

### If Still Getting Errors

**Increase stability delay to 5 seconds:**

Edit `frontend-client-apps/listener-app/src/services/ListenerService.ts`:

```typescript
// Line ~203
console.log('[ListenerService] Waiting 5 seconds for speaker KVS master connection...');
await new Promise(resolve => setTimeout(resolve, 5000)); // Changed from 3000
```

**Or increase retry attempts:**

When calling `connectAsViewer()` in `startListening()`:

```typescript
// Line ~162
await this.kvsService.connectAsViewer(5, 3000); // 5 retries, 3s initial delay
```

## Production Solution

For production, implement backend status tracking:

**Backend Changes:**
1. Add `speakerKvsConnected: boolean` to session metadata
2. Speaker calls `PUT /sessions/{id}/kvs-status` after KVS connection
3. Listener checks this field instead of guessing with delays

**Benefits:**
- No arbitrary delays needed
- Instant feedback when speaker ready
- More reliable connection timing

See `KVS_CONNECTION_ROOT_CAUSE_ANALYSIS.md` for full implementation details.

## Quick Test Commands

### Test 1: Speaker First (Should Work)

```bash
# Terminal 1
cd frontend-client-apps/speaker-app && npm run dev
# Login → New Session → Start Broadcasting → Wait 5s

# Terminal 2  
cd frontend-client-apps/listener-app && npm run dev
# Login → Enter Session ID → Join
```

### Test 2: Current Code (3s delay)

Your logs show the listener connected successfully but then got SESSION_NOT_FOUND. This means:
- The 3 second delay wasn't enough
- Speaker took >3 seconds to establish KVS master connection
- Need to either: increase delay OR test with speaker fully ready first

## Recommendations

**For immediate testing:**
1. Always ensure speaker shows "Connected as Master" before listener joins
2. Wait 5 seconds after speaker starts broadcasting
3. Then join with listener

**For production:**
1. Implement backend `speakerKvsConnected` tracking
2. Remove arbitrary delays
3. Use real-time status checks

**Current workaround:**
- Increased stability delay to 3 seconds
- Retry logic provides fallback
- Works if speaker connects within ~8 seconds of session creation
