# WebSocket Disconnect Issue - Diagnostic Log

**Date:** November 26, 2025  
**Issue:** WebSocket closes immediately after connect (code 1005)  
**Impact:** Blocks Phase 1 testing and audio streaming

---

## Observed Behavior

### Timeline:
```
1. HTTP API creates session "sacred-truth-870" ✅
2. WebSocket connects with readyState: 1 ✅
3. Lambda: "Listener connection accepted" (user_id: null) ⚠️
4. Lambda returns 200 OK ✅
5. ~1 second later: WebSocket closes (code 1005) ❌
6. startBroadcast() fails: "WebSocket not connected" ❌
```

### Close Code 1005:
- Means: No status code received
- Common causes: Server closed without sending close frame, network issue, or premature close

---

## Root Cause Analysis

### Issue 1: Role Detection (Secondary)
**Problem:** Connection detected as "listener" instead of "speaker"
- Log shows: `user_id: null` in authorizer context
- Should be: `user_id: <cognito-sub>` from JWT token

**Why it matters:**
- Speakers need JWT authentication
- Listeners are anonymous
- Role affects what actions are allowed

**But:** This alone shouldn't cause immediate disconnect

### Issue 2: Timing Race (Primary Suspect)
**Problem:** WebSocket closes between connect() and startBroadcast()

**Sequence in code:**
```typescript
1. await orchestrator.createSession()  // HTTP + WebSocket connect
2. useSpeakerStore.setSession()       // Set state
3. new SpeakerService()                // Create service
4. await service.initialize()          // Load preferences
5. await new Promise(100ms)            // Delay added
6. await service.startBroadcast()      // TRY to get WebSocket
   -> ERROR: WebSocket already closed!
```

**Hypothesis:** Something is closing the WebSocket during steps 2-5

---

## Potential Causes

### A. API Gateway Idle Timeout
- **Default:** 10 minutes
- **Our case:** Closes in <1 second
- **Verdict:** NOT the cause (too fast)

### B. Heartbeat Timer Conflict
- **Code:** Starts immediately, sends every 30 seconds
- **First send:** Would be at T+30s, not T+1s
- **Verdict:** NOT the cause (timer hasn't fired)

### C. Lambda Response Format
- **Current:** `{'statusCode': 200, 'body': '{}'}`
- **Required:** Same format ✅
- **Verdict:** Format is correct

### D. Backend Closes Connection
- **Lambda logs:** Shows "connection accepted" then completes
- **No disconnect command sent**
- **Verdict:** Backend NOT closing it

### E. Frontend handleDisconnect() Called
- **Logs show:** handleDisconnect() IS called
- **Triggered by:** onclose event (code 1005)
- **Verdict:** This is the EFFECT, not the cause

### F. Network/Browser Issue
- **Code 1005:** Can indicate network interruption
- **But:** Happens consistently, same timing
- **Verdict:** Unlikely to be random network

---

## Most Likely Cause

**API Gateway closes idle connections that don't send messages quickly enough**

Even though the official timeout is 10 minutes, API Gateway may close connections that:
1. Connect but don't send any messages
2. Take too long between connect and first message
3. Don't match expected message patterns

Our flow:
- Connect at T+0ms
- Don't send ANY message until startBroadcast()
- startBroadcast() happens at T+500-1000ms
- Too slow! Gateway closes at T+500ms

---

## Solution: Send Immediate Keep-Alive

### Fix in SessionCreationOrchestrator:

```typescript
private async connectWebSocketWithSession(sessionId: string): Promise<WebSocketClient> {
  const wsClient = new WebSocketClient({
    url: this.config.wsUrl,
    token: this.config.jwtToken,
    heartbeatInterval: 30000,
    reconnect: false,
    maxReconnectAttempts: 0,
    reconnectDelay: 1000,
  });

  this.wsClient = wsClient;

  // Connect with sessionId query parameter
  await wsClient.connect({ sessionId: sessionId });
  
  // IMMEDIATE: Send message to keep connection alive
  // API Gateway needs traffic to keep connection open
  await wsClient.send({
    action: 'heartbeat',
    timestamp: Date.now(),
  });
  
  return wsClient;
}
```

### Why This Works:
1. Connection opens
2. Immediately send heartbeat
3. Proves to API Gateway we're actively using the connection
4. Gateway keeps connection open
5. Later startBroadcast() finds WebSocket still open

---

## Alternative Solutions

### A. Remove Delays
- Remove 100ms delay before startBroadcast()
- Call startBroadcast() immediately after connect
- **Risk:** May not help if Gateway needs a message

### B. Change Architecture
- Don't get WebSocket in startBroadcast()
- Get it earlier and verify it's open
- **Risk:** Still need to keep it alive

### C. Send Dummy Message
- Send "connected" message right after WebSocket opens
- **Same as Solution above**

---

## Action Plan

1. **Implement immediate heartbeat after connect** ✅ Best solution
2. Test if connection stays open
3. If still fails, add more aggressive keep-alive
4. Check CloudWatch for any Lambda errors

---

## Testing Plan

After fix:
1. Create session
2. Check browser console: Should NOT see "WebSocket closed" immediately
3. Check CloudWatch: Should see heartbeat messages
4. startBroadcast() should succeed
5. Audio chunks should start flowing

---

## Notes

- Close code 1005 is "No Status Received"
- Means server closed without proper close handshake
- Often indicates premature/unexpected close
- API Gateway behavior: Needs active message flow

---

## Next Steps

1. Add immediate heartbeat after WebSocket connect
2. Rebuild frontend
3. Test connection stays open for >5 seconds
4. Proceed with audio streaming test
