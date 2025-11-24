# Phase 2 Testing Guide

**Date:** November 24, 2025  
**Scope:** Testing WebRTC + KVS integration (Frontend only)  
**Prerequisites:** Phase 1 backend deployed, Phase 2 frontend committed  

---

## Overview

This guide walks through testing the Phase 2 WebRTC integration. Since the backend KVS consumer (Phase 3-4) isn't implemented yet, we'll focus on verifying:

1. ✅ Frontend WebRTC connections work
2. ✅ KVS signaling channels function
3. ✅ Microphone capture works
4. ✅ Audio transmits to KVS
5. ⚠️ Audio playback (limited until Phase 3-4)

---

## Prerequisites

### 1. Backend Deployment Status

Check if backend is deployed:
```bash
# Check if CDK stacks are deployed
cd session-management/infrastructure
cdk list

# Expected output should include:
# - SessionManagementStack
# - KVSWebRTCStack (Phase 1)
```

If not deployed:
```bash
cd session-management/infrastructure
cdk deploy --all
```

### 2. Get Cognito Identity Pool ID

**Option A: From AWS Console**
1. Go to AWS Console → Cognito → Identity Pools
2. Find your identity pool (or create one if missing)
3. Copy the Identity Pool ID (format: `us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

**Option B: From CDK Output**
```bash
cd session-management/infrastructure
cdk outputs KVSWebRTCStack
# Look for CognitoIdentityPoolId
```

### 3. Configure Environment Variables

**Speaker App:**
```bash
# Edit frontend-client-apps/speaker-app/.env
cd frontend-client-apps/speaker-app

# Add this line (replace with your actual ID):
echo "VITE_COGNITO_IDENTITY_POOL_ID=us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" >> .env
```

**Listener App:**
```bash
# Edit frontend-client-apps/listener-app/.env
cd frontend-client-apps/listener-app

# Add this line (same ID as speaker):
echo "VITE_COGNITO_IDENTITY_POOL_ID=us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" >> .env
```

### 4. Verify Identity Pool IAM Role

**Check the authenticated role has KVS permissions:**
```bash
# Get the role name from CDK output
cd session-management/infrastructure
cdk outputs KVSWebRTCStack | grep AuthenticatedRoleName
```

**The role should have permissions for:**
- `kinesisvideo:DescribeSignalingChannel`
- `kinesisvideo:GetSignalingChannelEndpoint`
- `kinesisvideo:GetIceServerConfig`
- `kinesisvideo:SendAlexaOfferToMaster`
- `kinesisvideo:ConnectAsMaster`
- `kinesisvideo:ConnectAsViewer`

---

## Testing Procedure

### Test 1: Build Verification ✅

**Purpose:** Ensure code compiles without errors

```bash
cd frontend-client-apps

# Build all apps
npm run build:all
```

**Expected Output:**
```
✓ Shared library: tsc completed successfully
✓ Speaker app: built in ~3s
✓ Listener app: built in ~2s
```

**Success Criteria:**
- No TypeScript errors
- Dist folders created for both apps
- Warnings about dynamic imports are OK (not errors)

---

### Test 2: Speaker App - Session Creation

**Purpose:** Verify speaker can create session and get KVS config

```bash
cd frontend-client-apps/speaker-app

# Start dev server
npm run dev
```

**Steps:**
1. Open browser to http://localhost:5173
2. Log in with Cognito credentials
3. Create a session (select language: English, quality: standard)
4. Open browser console (F12)

**Expected Console Logs:**
```
[SessionOrchestrator] Creating session via HTTP API...
[SessionOrchestrator] Session created: <session-id>
[SpeakerService] Initializing WebRTC+WebSocket hybrid service...
[SpeakerService] Starting WebRTC broadcast...
[KVS] Connecting as Master (Speaker)...
[KVS] ICE servers obtained: X servers
[KVS] Requesting microphone access...
[KVS] Microphone access granted
[KVS] Added audio track to peer connection
[KVS] Opening signaling channel...
[KVS] Signaling channel opened as Master
[KVS] Connected as Master, ready for viewers
[SpeakerService] WebRTC broadcast started - audio streaming via UDP
```

**Success Criteria:**
- ✅ Session ID displayed in UI
- ✅ Microphone permission granted
- ✅ "[KVS] Connected as Master" appears
- ✅ No errors in console
- ✅ Connection state reaches "connected"
- ✅ ICE connection state reaches "connected" or "completed"

**Common Issues:**

**Issue 1: "Missing Cognito Identity Pool ID"**
```
Solution: Set VITE_COGNITO_IDENTITY_POOL_ID in .env file
```

**Issue 2: "Failed to obtain AWS credentials"**
```
Solution: Verify Identity Pool exists and IAM role has permissions
Check: AWS Console → Cognito → Identity Pools
```

**Issue 3: "Microphone permission denied"**
```
Solution: Allow microphone access when browser prompts
Chrome: Click lock icon in address bar → Site settings → Microphone
```

**Issue 4: "[KVS] ICE connection failed"**
```
Possible causes:
- Network firewall blocking UDP
- TURN servers not configured (check ICE servers count > 1)
- NAT type too restrictive

Check: Console should show "[KVS] ICE servers obtained: X servers"
If X = 1, only STUN is available (TURN may be needed)
```

---

### Test 3: Listener App - Join Session

**Purpose:** Verify listener can join session and receive WebRTC audio

```bash
cd frontend-client-apps/listener-app

# Start dev server (different port than speaker)
npm run dev
```

**Steps:**
1. Open browser to http://localhost:5174 (different port)
2. Enter the session ID from speaker app
3. Select target language (e.g., Spanish)
4. Click "Join Session"
5. Open browser console (F12)

**Expected Console Logs:**
```
[ListenerApp] Fetching session metadata...
[ListenerApp] Session metadata retrieved: <session-id>
[ListenerService] Initializing WebRTC+WebSocket hybrid service...
[ListenerService] Starting WebRTC audio reception...
[KVS] Connecting as Viewer (Listener)...
[KVS] ICE servers obtained: X servers
[KVS] Opening signaling channel...
[KVS] Signaling channel opened as Viewer, creating offer...
[KVS] Created and set local SDP offer
[KVS] Sent SDP offer to Master
[KVS] Received SDP answer from: <master-client-id>
[KVS] Set remote description (answer)
[KVS] ICE connection state: connected
[ListenerService] Received remote audio track
[ListenerService] Audio track connected to player
[ListenerService] WebRTC audio reception started
```

**Success Criteria:**
- ✅ Session metadata fetched successfully
- ✅ "[KVS] Connected as Viewer" appears
- ✅ "[ListenerService] Received remote audio track" appears
- ✅ No errors in console
- ✅ ICE connection state reaches "connected"

**What Won't Work Yet (Expected):**
- ❌ You won't hear translated audio (backend not processing yet)
- ❌ Original audio from speaker won't play (direct peer-to-peer not implemented)
- ⚠️ This is EXPECTED - Phase 3-4 will add backend processing

**Common Issues:**

**Issue 1: "Session metadata missing KVS configuration"**
```
Solution: Verify backend Phase 1 is deployed
Check: HTTP handler returns kvsChannelArn and kvsSignalingEndpoints
```

**Issue 2: "Failed to obtain AWS credentials"**
```
Solution: Same as speaker app - verify Identity Pool and IAM role
```

**Issue 3: ICE connection stuck at "checking"**
```
Possible causes:
- Speaker not connected yet (connect speaker first)
- Network issues (firewall blocking UDP)
- NAT traversal issues

Solution: Ensure speaker is already broadcasting before listener joins
```

---

### Test 4: WebRTC Connection States

**Purpose:** Monitor WebRTC connection health

**In Browser Console (Both Apps):**

**Check Connection States:**
```javascript
// These logs should appear automatically
[KVS] Connection state: connecting → connected
[KVS] ICE connection state: checking → connected (or completed)
[KVS] ICE gathering state: gathering → complete
[KVS] Signaling state: stable
```

**Success Criteria:**
- Connection state: "connected"
- ICE connection state: "connected" or "completed"
- No "failed" or "disconnected" states

**State Meanings:**
- `new` → Initial state
- `connecting` → Attempting connection
- `connected` → Connection established ✅
- `disconnected` → Temporary disconnect
- `failed` → Connection failed ❌
- `closed` → Connection closed

---

### Test 5: Control Functions

**Purpose:** Verify WebSocket control messages work

**Speaker Controls:**
1. Click "Pause" button
   - Expected: "[SpeakerService] WebRTC connection state: connected" (muted)
   - Audio track disabled but WebRTC connection maintained
   
2. Click "Resume" button
   - Expected: Audio track re-enabled
   
3. Click "Mute" button
   - Expected: "[KVS] Audio muted"
   
4. Check listener app
   - Expected: "Speaker Paused" indicator shows/hides

**Listener Controls:**
1. Adjust volume slider
   - Expected: Console log, store updated
   
2. Switch language
   - Expected: WebSocket message sent (no audio change yet until Phase 3-4)

**Success Criteria:**
- ✅ UI buttons respond
- ✅ Console logs appear
- ✅ WebSocket messages sent
- ✅ State updates reflected

---

### Test 6: Resource Cleanup

**Purpose:** Verify proper cleanup on session end

**Steps:**
1. With speaker broadcasting and listener listening
2. Speaker: Click "End Session"
3. Check both consoles

**Expected Logs (Speaker):**
```
[KVS] Cleaning up WebRTC resources...
[KVS] Stopped media track
[KVS] Closed peer connection
[KVS] Closed signaling client
```

**Expected Logs (Listener):**
```
[ListenerService] Received remote audio track (stream ended)
[KVS] Connection state: closed
```

**Success Criteria:**
- ✅ No errors during cleanup
- ✅ Resources properly disposed
- ✅ No memory leaks (check browser task manager)

---

## Monitoring & Debugging

### Browser Developer Tools

**Console Logs to Monitor:**
```
[KVS] - All KVS WebRTC operations
[SpeakerService] - Speaker-side operations
[ListenerService] - Listener-side operations
[SessionOrchestrator] - Session creation
```

**Chrome WebRTC Internals:**
```
URL: chrome://webrtc-internals
```
- View detailed WebRTC stats
- Check ICE candidate pairs
- Monitor audio track stats
- View bitrate graphs

**Firefox WebRTC Stats:**
```
URL: about:webrtc
```

### AWS Console Checks

**CloudWatch Logs:**
```
Log Groups:
- /aws/lambda/http-session-handler
- /aws/lambda/websocket-handler

Look for:
- Session creation events
- KVS channel creation
- Any backend errors
```

**KVS Console:**
```
AWS Console → Kinesis Video Streams → Signaling Channels

Verify:
- Channel created with session ID as name
- Channel status: ACTIVE
- Endpoints listed (WSS, HTTPS)
```

**Cognito Console:**
```
AWS Console → Cognito → Identity Pools

Verify:
- Identity pool exists
- Authenticated role has proper permissions
- Trust relationship allows Cognito authentication
```

---

## Expected Behavior Summary

### ✅ What SHOULD Work (Phase 2)

| Component | Expected Behavior |
|-----------|-------------------|
| Session Creation | HTTP API returns KVS config |
| KVS Channel | Created dynamically per session |
| Speaker WebRTC | Connects as Master, microphone access |
| Listener WebRTC | Connects as Viewer to same channel |
| Signaling | SDP/ICE exchange via KVS |
| Audio Capture | Microphone input captured by speaker |
| Audio Transmission | Speaker streams to KVS via UDP |
| Control Messages | Pause, mute, language switch via WebSocket |
| Cleanup | Resources properly disposed |

### ⚠️ What PARTIALLY Works (Backend Gap)

| Component | Current Behavior | After Phase 3-4 |
|-----------|------------------|-----------------|
| Audio Playback | No audio at listener | Translated audio plays |
| Transcription | None | Real-time transcription |
| Translation | None | Multi-language translation |
| Audio Quality | Not verified | Quality monitoring |

### ❌ What DOESN'T Work Yet (Expected)

- Listener won't hear audio (backend not consuming KVS)
- No transcription (Transcribe not connected)
- No translation (Translate not connected)
- No processed audio delivery

**This is EXPECTED** - Phase 3-4 will implement backend processing.

---

## Testing Checklist

### Pre-Testing Configuration
- [ ] Backend Phase 1 deployed (CDK stacks)
- [ ] Cognito Identity Pool ID obtained
- [ ] VITE_COGNITO_IDENTITY_POOL_ID set in speaker-app/.env
- [ ] VITE_COGNITO_IDENTITY_POOL_ID set in listener-app/.env
- [ ] Frontend builds successfully (npm run build:all)

### Speaker App Tests
- [ ] App loads without errors
- [ ] Login works with Cognito
- [ ] Session creation succeeds
- [ ] Microphone permission requested and granted
- [ ] Console shows "[KVS] Connected as Master"
- [ ] Console shows "audio streaming via UDP"
- [ ] No WebRTC errors
- [ ] ICE connection reaches "connected"
- [ ] Pause button works (track disabled)
- [ ] Mute button works (track muted)
- [ ] End session cleans up properly

### Listener App Tests
- [ ] App loads without errors
- [ ] Session ID input works
- [ ] Session metadata fetched successfully
- [ ] Console shows "[KVS] Connected as Viewer"
- [ ] Console shows "Received remote audio track"
- [ ] No WebRTC errors
- [ ] ICE connection reaches "connected"
- [ ] Volume controls update (audio element volume)
- [ ] Language selector sends WebSocket message
- [ ] Leave session cleans up properly

### WebRTC Connection Tests
- [ ] Speaker: Check chrome://webrtc-internals shows active connection
- [ ] Listener: Check chrome://webrtc-internals shows active connection
- [ ] ICE candidate pairs show "succeeded" state
- [ ] Audio track shows in WebRTC internals
- [ ] Bitrate > 0 (indicates data flowing)

### AWS Infrastructure Tests
- [ ] CloudWatch: HTTP handler creates KVS channel
- [ ] KVS Console: Channel appears with session ID
- [ ] KVS Console: Channel status = ACTIVE
- [ ] CloudWatch: No errors in Lambda logs
- [ ] Cognito: GetId API calls appear (Identity Pool usage)

---

## Troubleshooting Guide

### Problem: Identity Pool ID Not Found

**Symptoms:**
```
Error: Missing Cognito Identity Pool ID in configuration
```

**Solution:**
1. Check if Identity Pool was created in Phase 1:
   ```bash
   aws cognito-identity list-identity-pools --max-results 10 --region us-east-1
   ```
2. If missing, create one:
   ```bash
   cd session-management/infrastructure
   cdk deploy KVSWebRTCStack
   ```
3. Get the ID and add to .env files

---

### Problem: WebRTC Connection Fails

**Symptoms:**
```
[KVS] ICE connection state: failed
Error: Failed to connect as Master/Viewer
```

**Diagnosis:**
1. Check ICE servers:
   ```
   Look for: [KVS] ICE servers obtained: X servers
   If X = 0: KVS API call failed (check credentials)
   If X = 1: Only STUN available (may need TURN)
   If X > 1: STUN + TURN available ✅
   ```

2. Check credentials:
   ```
   Look for: [SpeakerService] Failed to get AWS credentials
   If present: Identity Pool role permissions issue
   ```

3. Check network:
   ```
   - Firewall blocking UDP ports 10000-20000?
   - Corporate proxy interfering?
   - Try different network (mobile hotspot)
   ```

**Solutions:**
- **Credentials:** Verify IAM role attached to Identity Pool
- **Network:** Check firewall settings, try TURN-only mode
- **Browser:** Try different browser (Chrome recommended)

---

### Problem: Microphone Access Denied

**Symptoms:**
```
Error: Failed to initialize broadcast
NotAllowedError: Permission denied
```

**Solutions:**
1. **Chrome:** Settings → Privacy → Site Settings → Microphone → Allow
2. **Firefox:** Click lock icon → Permissions → Microphone → Allow
3. **Safari:** Preferences → Websites → Microphone → Allow
4. Try opening in new incognito window (fresh permissions)

---

### Problem: No Audio at Listener

**Symptoms:**
- Listener connects successfully
- Console shows "[ListenerService] Received remote audio track"
- But no audio plays

**Expected Behavior:**
⚠️ **THIS IS NORMAL IN PHASE 2**

Until Phase 3-4 backend is implemented:
- Audio DOES reach KVS from speaker ✅
- Listener DOES connect to KVS ✅
- But backend doesn't process/translate/forward yet ❌

**Verification:**
1. Check speaker console: "[KVS] Connected as Master" ✅
2. Check listener console: "[ListenerService] Received remote audio track" ✅
3. Check WebRTC internals: Audio track present ✅
4. Expected: No processed audio yet (Phase 3-4)

**To Verify Raw Audio Reaches Listener:**
Open chrome://webrtc-internals and check:
- Track: kind="audio", readyState="live"
- Packets received > 0
- Bytes received > 0

If these values increase, audio IS being received (just not processed).

---

## Performance Testing

### Latency Measurement (Phase 2 Baseline)

**Current Limitations:**
- Can't measure end-to-end latency yet (no backend processing)
- Can measure WebRTC connection establishment time

**Measure WebRTC Connection Time:**
```javascript
// In browser console after starting broadcast:
// Look for time between these logs:
[KVS] Connecting as Master (Speaker)...  // Start
[KVS] Connected as Master, ready for viewers  // End

// Typical times:
// - STUN only: 1-3 seconds
// - STUN + TURN: 3-5 seconds
```

**Expected Results (Phase 2):**
- Session creation: <2s
- WebRTC connection: 1-5s (depends on network)
- Control operations: <100ms
- Credential fetch: <500ms (cached after first call)

---

## Success Criteria

### Phase 2 Complete Success ✅

**All of these must be true:**

**Speaker Side:**
- [x] Session created with KVS config
- [x] WebRTC connects as Master
- [x] Microphone captured
- [x] "[KVS] Connected as Master" in console
- [x] No errors in console
- [x] ICE connection state = "connected" or "completed"

**Listener Side:**
- [x] Session fetched with KVS config
- [x] WebRTC connects as Viewer
- [x] "[ListenerService] Received remote audio track" in console
- [x] No errors in console
- [x] ICE connection state = "connected" or "completed"

**Infrastructure:**
- [x] KVS channel created
- [x] KVS channel status = ACTIVE
- [x] Cognito Identity Pool working
- [x] IAM roles allow KVS operations

**Code Quality:**
- [x] TypeScript compiles
- [x] Production builds successful
- [x] No runtime errors

### Phase 2 Partial Success ⚠️

**If any WebRTC connection issues:**
- Debug with chrome://webrtc-internals
- Check IAM permissions
- Verify network allows UDP
- Test with different network/browser

---

## Next Steps After Testing

### If All Tests Pass ✅

**Phase 2 is COMPLETE** - Proceed to Phase 3:

1. **Phase 3: KVS Stream Ingestion**
   - Create KVS Consumer Lambda
   - Subscribe to KVS data stream
   - Extract audio chunks from WebRTC
   - Forward to Transcribe Streaming API

2. **Phase 4: Translation Pipeline**
   - Receive transcriptions
   - Translate via Amazon Translate
   - Forward to listeners

### If Tests Fail ❌

**Debug Order:**
1. Fix configuration (Identity Pool ID)
2. Fix IAM permissions
3. Fix network issues
4. Fix browser compatibility
5. Re-test

---

## Quick Test Script

**Run this to verify basics:**

```bash
#!/bin/bash

echo "Phase 2 Testing Quick Check"
echo "============================"
echo ""

# 1. Check builds
echo "1. Checking TypeScript builds..."
cd frontend-client-apps
npm run build:all
if [ $? -eq 0 ]; then
  echo "✅ Builds successful"
else
  echo "❌ Build failed"
  exit 1
fi

echo ""

# 2. Check Identity Pool ID configured
echo "2. Checking Identity Pool ID..."
if grep -q "VITE_COGNITO_IDENTITY_POOL_ID" speaker-app/.env; then
  echo "✅ Speaker .env configured"
else
  echo "❌ Speaker .env missing VITE_COGNITO_IDENTITY_POOL_ID"
fi

if grep -q "VITE_COGNITO_IDENTITY_POOL_ID" listener-app/.env; then
  echo "✅ Listener .env configured"
else
  echo "❌ Listener .env missing VITE_COGNITO_IDENTITY_POOL_ID"
fi

echo ""
echo "3. Manual tests required:"
echo "   - Start speaker app: cd speaker-app && npm run dev"
echo "   - Start listener app: cd listener-app && npm run dev"
echo "   - Check browser console for [KVS] logs"
echo ""
echo "See PHASE_2_TESTING_GUIDE.md for full testing procedure"
```

Save as `frontend-client-apps/test-phase2.sh` and run:
```bash
chmod +x frontend-client-apps/test-phase2.sh
./frontend-client-apps/test-phase2.sh
```

---

## Summary

**Phase 2 Testing Focus:**
- ✅ WebRTC connections establish
- ✅ Credentials obtained correctly
- ✅ Audio captured and streamed to KVS
- ✅ Control messages work
- ⚠️ Audio processing happens in Phase 3-4

**Testing Time Estimate:**
- Configuration: 10 minutes
- Basic tests: 15 minutes
- Debug (if needed): 30-60 minutes
- Total: 30-90 minutes

**Expected Outcome:**
- Speaker broadcasts to KVS successfully
- Listener connects to KVS successfully
- No audio playback yet (expected)
- Ready for Phase 3-4 backend implementation
