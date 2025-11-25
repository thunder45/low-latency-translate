# Listener WebSocket Token Fix

**Date**: November 25, 2025  
**Status**: ✅ **FIXED - Ready for Testing**

## Problem

Listener app WebSocket connection failed with code 1006:
```
WebSocket connection to 'wss://...?sessionId=pure-psalm-481&targetLanguage=de&token=' failed
```

## Root Cause

**Empty token parameter in URL**:
- ListenerApp passes `jwtToken: ''` (empty string)
- ListenerService constructor passed it to WebSocketClient
- WebSocketClient added it to URL: `?token=`
- Backend may have rejected connection due to empty token parameter

## Solution

Updated ListenerService to **only add token if non-empty**:

```typescript
// Before (BROKEN)
this.wsClient = new WebSocketClient({
  url: config.wsUrl,
  token: config.jwtToken,  // Empty string '' still added to URL
  ...
});

// After (FIXED)
const wsConfig: any = {
  url: config.wsUrl,
  heartbeatInterval: 30000,
  reconnect: true,
  reconnectDelay: 1000,
  maxReconnectAttempts: 5,
};

// Only add token if it's a non-empty string
if (config.jwtToken && config.jwtToken.trim()) {
  wsConfig.token = config.jwtToken;
}

this.wsClient = new WebSocketClient(wsConfig);
```

## What This Fixes

**Old URL** (with empty token):
```
wss://mji0q10vm1.execute-api.us-east-1.amazonaws.com/prod?sessionId=pure-psalm-481&targetLanguage=de&token=
```

**New URL** (no token param):
```
wss://mji0q10vm1.execute-api.us-east-1.amazonaws.com/prod?sessionId=pure-psalm-481&targetLanguage=de
```

## Files Modified

- `frontend-client-apps/listener-app/src/services/ListenerService.ts`

## Testing

### Restart Listener App

The listener app dev server needs to reload with the new code:

```bash
# Stop the current dev server (Ctrl+C)
# Then restart:
cd frontend-client-apps/listener-app
npm run dev
```

### Test Connection

1. Enter session code (e.g., `pure-psalm-481`)
2. Select language (e.g., `de`)
3. Click "Join Session"

### Expected Success

```
[ListenerApp] Fetching session metadata...
[ListenerApp] Session metadata retrieved: pure-psalm-481
[ListenerService] Initializing WebRTC+WebSocket hybrid service...
[WebSocketClient] WebSocket connection opened, readyState: 1  ✅
[WebSocketClient] onopen handlers completed
[ListenerService] Initialization complete, ready to receive audio
[ListenerService] Starting WebRTC audio reception...
[KVS Credentials] Fetching new credentials...
[KVS] Connecting as Viewer (Listener)...
[KVS] ICE servers obtained: 2
[KVS] Connected as Viewer, waiting for media from Master
[KVS] Received media track from Master  ✅
[ListenerService] Audio track connected to player  ✅
```

## Summary

**Problem**: Empty JWT token string added to WebSocket URL  
**Solution**: Only add token parameter if non-empty  
**Result**: Listener can connect without JWT token

**Next**: Restart listener app and test connection
