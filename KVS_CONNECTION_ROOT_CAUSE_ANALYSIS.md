# KVS WebSocket Connection - Root Cause Analysis & Fix

## Problem Statement

**Error:** `SESSION_NOT_FOUND: Session does not exist or is inactive`
**Location:** KVS WebSocket signaling connection (listener connecting as viewer)

## Root Cause Identified ✅

The issue is a **timing/coordination problem** between Speaker (Master) and Listener (Viewer) connections.

### How KVS WebRTC Works

```
┌─────────────────────────────────────────────────────────────┐
│                   KVS WebRTC Flow                             │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. MASTER (Speaker) connects first                          │
│     • Opens KVS signaling channel                            │
│     • Establishes presence on channel                        │
│     • Waits for viewers                                      │
│                                                               │
│  2. VIEWER (Listener) connects second                        │
│     • Opens signaling channel to same channel ARN            │
│     • Creates SDP offer                                      │
│     • Sends offer to Master via KVS signaling               │
│                                                               │
│  3. MASTER receives offer                                    │
│     • Creates SDP answer                                     │
│     • Sends answer back to viewer                            │
│                                                               │
│  4. ICE candidates exchanged                                 │
│     • Both peers exchange network information                │
│     • WebRTC P2P connection established                      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### The Problem

**Current Code Flow:**

1. **Listener joins session** via HTTP API
2. **Listener immediately tries to connect to KVS** as viewer
3. **Speaker might not be connected yet** as master
4. **KVS signaling rejects viewer** → `SESSION_NOT_FOUND`

**Why This Fails:**

In `frontend-client-apps/shared/services/KVSWebRTCService.ts` (lines 139-152):

```typescript
// Viewer creates offer when channel opens
this.signalingClient.on('open', async () => {
  console.log('[KVS] Signaling channel opened as Viewer, creating offer...');
  
  try {
    const offer = await this.peerConnection!.createOffer({
      offerToReceiveAudio: true,
      offerToReceiveVideo: false,
    });
    
    await this.peerConnection!.setLocalDescription(offer);
    this.signalingClient!.sendSdpOffer(this.peerConnection!.localDescription!);
  }
});
```

**The viewer immediately sends an SDP offer when the channel opens, but if no master is present, KVS has no one to deliver the offer to!**

## Evidence From Logs

✅ **Authentication working:**
```
✅ [KVS Credentials] Using cached credentials
✅ [KVS] ICE servers obtained: 2
```

❌ **Connection timing issue:**
```
❌ WebSocket connection to 'wss://m-2a06b28b.kinesisvideo.us-east-1.amazonaws.com/...' failed
❌ SESSION_NOT_FOUND: Session does not exist or is inactive
```

## The Fix: Speaker-Ready Coordination

We need to coordinate the connection timing between speaker and listener.

### Solution Architecture

```
┌──────────────┐                ┌──────────────┐
│   Speaker    │                │   Listener   │
│   (Master)   │                │   (Viewer)   │
└──────┬───────┘                └──────┬───────┘
       │                               │
       │ 1. Connect to KVS as Master   │
       ├──────────────────────────────►│
       │                               │
       │ 2. Notify "Master Ready"      │
       ├──────────────────────────────►│
       │    (via WebSocket/HTTP API)   │
       │                               │
       │                          3. Check if Master Ready
       │                               │
       │                          4. Connect to KVS as Viewer
       │◄──────────────────────────────┤
       │                               │
       │ 5. Exchange SDP & ICE         │
       │◄──────────────────────────────┤
       │                               │
       │ 6. WebRTC P2P Established     │
       │◄═════════════════════════════►│
       │                               │
```

### Implementation Options

#### Option 1: Session Metadata Flag (Recommended) ✅

**Backend Changes:**
- Add `speakerKvsConnected` boolean to session metadata
- Speaker updates this field when KVS master connection succeeds
- Listener checks this before attempting KVS connection

**Pros:**
- Clean separation of concerns
- Reliable state tracking
- Easy to implement

#### Option 2: WebSocket Ready Event

**Backend Changes:**
- Speaker emits "speakerKvsReady" WebSocket event
- Listeners subscribe and wait for event
- Retry with timeout if event not received

**Pros:**
- Real-time notification
- Lower latency

**Cons:**
- Requires WebSocket to be connected
- Event could be missed if listener connects late

#### Option 3: Polling with Exponential Backoff

**Frontend Only:**
- Listener polls session status endpoint
- Checks for `speakerKvsConnected` flag
- Retries KVS connection with backoff

**Pros:**
- No backend event system needed
- Self-healing

**Cons:**
- Higher latency
- More API calls

### Recommended Implementation: Hybrid Approach

**Combine Options 1 + 2 + 3:**

1. **Backend tracks speaker KVS state** (Option 1)
2. **WebSocket event for real-time notification** (Option 2)  
3. **Polling + retry as fallback** (Option 3)

## Implementation Plan

### Phase 1: Backend Session State Tracking

**File:** `session-management/lambda/http_session_handler/handler.py`

```python
# Add field to session metadata
session_data = {
    'sessionId': session_id,
    'kvsChannelArn': channel_arn,
    'kvsSignalingEndpoints': endpoints,
    'speakerKvsConnected': False,  # NEW FIELD
    'createdAt': timestamp,
    'status': 'active'
}
```

**New endpoint:** `PUT /sessions/{sessionId}/kvs-status`
- Called by speaker after successful KVS master connection
- Updates `speakerKvsConnected` to `True`
- Emits WebSocket event to all listeners

### Phase 2: Speaker Updates KVS Status

**File:** `frontend-client-apps/speaker-app/src/services/SpeakerService.ts`

```typescript
async startBroadcast(): Promise<void> {
  // ... existing code ...
  
  // Connect as Master
  await this.kvsService.connectAsMaster();
  
  // NEW: Notify backend that speaker is ready
  await this.notifySpeakerReady();
  
  console.log('[SpeakerService] WebRTC broadcast started');
}

private async notifySpeakerReady(): Promise<void> {
  try {
    const sessionId = useSpeakerStore.getState().sessionId;
    await fetch(`${this.config.httpApiUrl}/sessions/${sessionId}/kvs-status`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.config.jwtToken}`,
      },
      body: JSON.stringify({
        kvsConnected: true,
      }),
    });
    console.log('[SpeakerService] Notified backend: Speaker KVS ready');
  } catch (error) {
    console.warn('[SpeakerService] Failed to notify KVS status:', error);
    // Non-critical, listeners can still poll
  }
}
```

### Phase 3: Listener Waits for Speaker Ready

**File:** `frontend-client-apps/listener-app/src/services/ListenerService.ts`

```typescript
async startListening(): Promise<void> {
  try {
    console.log('[ListenerService] Checking if speaker is ready...');
    
    // Wait for speaker to be KVS-ready
    await this.waitForSpeakerReady();
    
    console.log('[ListenerService] Speaker is ready, starting WebRTC...');
    
    // ... rest of existing code ...
  }
}

private async waitForSpeakerReady(maxWaitMs: number = 30000): Promise<void> {
  const startTime = Date.now();
  const pollInterval = 1000; // Poll every 1 second
  
  while (Date.now() - startTime < maxWaitMs) {
    try {
      // Check session metadata
      const response = await fetch(
        `${this.config.httpApiUrl}/sessions/${this.config.sessionId}`
      );
      
      if (response.ok) {
        const session = await response.json();
        
        if (session.speakerKvsConnected === true) {
          console.log('[ListenerService] Speaker KVS connection confirmed');
          return;
        }
      }
      
      // Wait before next poll
      await new Promise(resolve => setTimeout(resolve, pollInterval));
      
    } catch (error) {
      console.warn('[ListenerService] Error polling speaker status:', error);
      await new Promise(resolve => setTimeout(resolve, pollInterval));
    }
  }
  
  // Timeout - try anyway (speaker might be ready but status update failed)
  console.warn('[ListenerService] Timeout waiting for speaker, attempting connection anyway');
}
```

### Phase 4: Add WebSocket Event (Optional)

**Backend emits event when speaker connects:**

```python
# In kvs-status update handler
await websocket_service.broadcast_to_session(
    session_id,
    {
        'type': 'speakerKvsReady',
        'timestamp': int(time.time() * 1000)
    }
)
```

**Frontend listens:**

```typescript
// In ListenerService.setupEventHandlers()
this.wsClient.on('speakerKvsReady', () => {
  console.log('[ListenerService] Received speaker ready event');
  // Trigger KVS connection if waiting
  if (this.pendingKvsConnection) {
    this.startKvsConnection();
  }
});
```

## Testing Plan

### Test Scenario 1: Normal Flow
1. Start speaker app
2. Speaker creates session
3. Speaker starts broadcast (KVS master connects)
4. Speaker updates backend status
5. Listener joins session
6. Listener waits for speaker ready (immediate success)
7. Listener connects to KVS as viewer
8. ✅ Connection succeeds

### Test Scenario 2: Listener Joins First
1. Create session via HTTP API (no speaker yet)
2. Listener tries to join
3. Listener polls for speaker ready
4. Speaker starts broadcast 5 seconds later
5. Listener detects speaker ready
6. Listener connects to KVS
7. ✅ Connection succeeds

### Test Scenario 3: Speaker Disconnects
1. Normal flow - both connected
2. Speaker loses connection
3. Backend marks `speakerKvsConnected = false`
4. Listener detects disconnection
5. Listener UI shows "Waiting for speaker..."
6. Speaker reconnects
7. ✅ Listener reconnects automatically

## Alternative Quick Fix: Add Retry Logic

If backend changes are complex, we can add retry logic to the listener as a temporary fix:

```typescript
async connectAsViewer(retries: number = 3, delayMs: number = 2000): Promise<void> {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      console.log(`[KVS] Connection attempt ${attempt}/${retries}`);
      
      await this.doConnectAsViewer(); // Original logic
      
      console.log('[KVS] Connection successful');
      return;
      
    } catch (error) {
      if (attempt === retries) {
        console.error('[KVS] All connection attempts failed');
        throw error;
      }
      
      console.warn(`[KVS] Attempt ${attempt} failed, retrying in ${delayMs}ms...`);
      await new Promise(resolve => setTimeout(resolve, delayMs));
      
      // Exponential backoff
      delayMs *= 1.5;
    }
  }
}
```

## Next Steps

1. ✅ **Identified root cause** - timing issue between master and viewer
2. ⏭️ **Implement backend session state tracking** - Add `speakerKvsConnected` field
3. ⏭️ **Update speaker to notify readiness** - Call HTTP API after KVS connection
4. ⏭️ **Update listener to wait for speaker** - Poll/wait before connecting
5. ⏭️ **Add retry logic as fallback** - Handle edge cases
6. ⏭️ **Test all scenarios** - Normal flow, listener-first, disconnections
7. ⏭️ **Add monitoring** - Track connection success rates

## Key Insight

> The authentication is working perfectly. The problem is that **KVS WebRTC requires the Master (speaker) to establish the signaling channel before Viewers (listeners) can connect**. The current implementation doesn't coordinate this timing, causing "SESSION_NOT_FOUND" errors when listeners connect before speakers.

## Related Files

- `frontend-client-apps/shared/services/KVSWebRTCService.ts` - WebRTC connection logic
- `frontend-client-apps/listener-app/src/services/ListenerService.ts` - Listener service
- `frontend-client-apps/speaker-app/src/services/SpeakerService.ts` - Speaker service
- `session-management/lambda/http_session_handler/handler.py` - Session management
