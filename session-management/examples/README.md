# Client Implementation Examples

This directory contains reference implementations for WebSocket clients that connect to the Session Management infrastructure.

## Overview

The examples demonstrate:
- **Speaker clients**: Authenticated users who create sessions and broadcast audio
- **Listener clients**: Anonymous users who join sessions and receive translated audio
- **Connection refresh**: Seamless reconnection for unlimited session duration
- **Error handling**: Robust error handling and automatic reconnection
- **Audio buffer management**: Zero-loss audio during connection transitions

## Directory Structure

```
examples/
├── javascript-client/
│   ├── speaker-client.js      # JavaScript/TypeScript speaker implementation
│   └── listener-client.js     # JavaScript/TypeScript listener implementation
├── python-client/
│   ├── speaker_client.py      # Python speaker implementation
│   └── listener_client.py     # Python listener implementation
└── README.md                  # This file
```

## Quick Start

### JavaScript/TypeScript Client

**Speaker:**
```javascript
const SpeakerClient = require('./javascript-client/speaker-client');

const client = new SpeakerClient({
  apiEndpoint: 'wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod',
  cognitoUserPoolId: 'us-east-1_ABC123XYZ',
  cognitoClientId: '1a2b3c4d5e6f7g8h9i0j',
  sourceLanguage: 'en',
  qualityTier: 'standard'
});

await client.authenticate('username', 'password');
await client.connect();
// Session ID will be available in client.sessionId
```

**Listener:**
```javascript
const ListenerClient = require('./javascript-client/listener-client');

const client = new ListenerClient({
  apiEndpoint: 'wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod',
  sessionId: 'golden-eagle-427',
  targetLanguage: 'es'
});

await client.connect();
// Audio will be played automatically
```

### Python Client

**Speaker:**
```python
from speaker_client import SpeakerClient

client = SpeakerClient({
    'api_endpoint': 'wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod',
    'cognito_user_pool_id': 'us-east-1_ABC123XYZ',
    'cognito_client_id': '1a2b3c4d5e6f7g8h9i0j',
    'source_language': 'en',
    'quality_tier': 'standard'
})

await client.authenticate('username', 'password')
await client.connect()
# Session ID will be available in client.session_id
```

**Listener:**
```python
from listener_client import ListenerClient

client = ListenerClient({
    'api_endpoint': 'wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod',
    'session_id': 'golden-eagle-427',
    'target_language': 'es'
})

await client.connect()
# Audio will be received via audioReceived event
```

## Connection Refresh Pattern

Both speaker and listener clients implement seamless connection refresh to support unlimited session duration (beyond the 2-hour API Gateway WebSocket limit).

### How It Works

1. **Server triggers refresh** at 100 minutes (20 minutes before 2-hour limit)
2. **Client establishes new connection** while keeping old one active
3. **Zero audio loss** during transition via buffering
4. **Old connection closes** gracefully after switch
5. **Process repeats** every 100 minutes for unlimited duration

### Implementation Pattern

```javascript
async handleConnectionRefresh(message) {
  // 1. Establish new connection
  const newWs = new WebSocket(refreshUrl);
  
  // 2. Wait for confirmation
  newWs.onmessage = (event) => {
    if (event.data.type === 'connectionRefreshComplete') {
      // 3. Switch audio streaming/playback
      this.switchToNewConnection(newWs);
      
      // 4. Close old connection
      this.ws.close(1000, 'Connection refresh');
      
      // 5. Update reference
      this.ws = newWs;
    }
  };
}
```

## Error Handling Patterns

### 1. Connection Errors

**Pattern**: Exponential backoff with maximum retry limit

```javascript
async attemptReconnect(retryCount = 0, maxRetries = 5) {
  if (retryCount >= maxRetries) {
    this.emit('reconnectFailed');
    return;
  }

  const backoffDelay = Math.min(30000 * Math.pow(2, retryCount), 300000);
  
  setTimeout(async () => {
    try {
      await this.connect();
      this.emit('reconnected');
    } catch (error) {
      this.attemptReconnect(retryCount + 1, maxRetries);
    }
  }, backoffDelay);
}
```

**Backoff Schedule**:
- Attempt 1: 30 seconds
- Attempt 2: 60 seconds
- Attempt 3: 120 seconds
- Attempt 4: 240 seconds
- Attempt 5: 300 seconds (max)

### 2. Authentication Errors

**Pattern**: Fail fast with clear error message

```javascript
async authenticate(username, password) {
  try {
    const response = await cognito.initiateAuth({...});
    this.jwtToken = response.IdToken;
  } catch (error) {
    if (error.code === 'NotAuthorizedException') {
      throw new Error('Invalid username or password');
    } else if (error.code === 'UserNotFoundException') {
      throw new Error('User not found');
    } else {
      throw new Error(`Authentication failed: ${error.message}`);
    }
  }
}
```

### 3. Message Parsing Errors

**Pattern**: Log and continue (don't crash on malformed messages)

```javascript
handleMessage(event) {
  try {
    const message = JSON.parse(event.data);
    // Process message
  } catch (error) {
    console.error('Error parsing message:', error);
    // Continue listening for next message
  }
}
```

### 4. Audio Streaming Errors

**Pattern**: Queue audio when connection not ready

```javascript
sendAudio(audioData) {
  if (this.ws && this.ws.readyState === WebSocket.OPEN) {
    this.ws.send(audioData);
  } else {
    console.warn('WebSocket not ready, queueing audio');
    this.audioQueue.push(audioData);
  }
}
```

### 5. Refresh Errors

**Pattern**: Retry with exponential backoff, keep old connection alive

```javascript
async handleConnectionRefresh(message) {
  try {
    const newWs = await this.establishNewConnection();
    await this.switchToNewConnection(newWs);
  } catch (error) {
    console.error('Refresh failed, retrying in 30s:', error);
    setTimeout(() => {
      this.handleConnectionRefresh(message);
    }, 30000);
    // Old connection remains active until refresh succeeds
  }
}
```

## Audio Buffer Management

### Speaker: Zero-Loss Audio Transmission

**Challenge**: Ensure no audio is lost during connection refresh

**Solution**: Queue audio during transition

```javascript
class AudioConnectionManager {
  constructor() {
    this.audioQueue = [];
    this.isTransitioning = false;
  }
  
  switchConnection(newConnection) {
    this.isTransitioning = true;
    
    // Queue audio from old connection during transition
    this.oldConnection.onAudioCapture = (audio) => {
      this.audioQueue.push(audio);
    };
    
    // Send queued audio through new connection
    newConnection.onReady = () => {
      while (this.audioQueue.length > 0) {
        const audio = this.audioQueue.shift();
        newConnection.send(audio);
      }
      this.isTransitioning = false;
    };
  }
}
```

### Listener: Seamless Audio Playback

**Challenge**: Maintain continuous audio playback during connection refresh

**Solution**: Buffer audio from old connection, flush through new connection

```javascript
class AudioPlaybackManager {
  constructor() {
    this.audioBuffer = [];
    this.isTransitioning = false;
  }
  
  switchConnection(newConnection) {
    this.isTransitioning = true;
    
    // Buffer audio from old connection
    this.oldConnection.onmessage = (event) => {
      if (event.data.type === 'audioData') {
        this.audioBuffer.push(event.data.audioData);
      }
    };
    
    // Flush buffered audio through new connection
    newConnection.onmessage = (event) => {
      if (this.isTransitioning) {
        // Play buffered audio first
        while (this.audioBuffer.length > 0) {
          this.playAudio(this.audioBuffer.shift());
        }
        this.isTransitioning = false;
      }
      
      // Then play new audio
      if (event.data.type === 'audioData') {
        this.playAudio(event.data.audioData);
      }
    };
  }
  
  playAudio(audioData) {
    // Decode and play audio using Web Audio API
    const audioBuffer = this.decodeAudio(audioData);
    const source = this.audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.audioContext.destination);
    source.start(0);
  }
}
```

### Buffer Size Recommendations

**Speaker**:
- Queue size: 30 seconds of audio (safety buffer)
- Chunk size: 100ms (balance latency and overhead)
- Flush strategy: FIFO (first in, first out)

**Listener**:
- Buffer size: 5 seconds of audio (smooth playback)
- Chunk size: 100ms (matches speaker chunks)
- Flush strategy: FIFO with jitter buffer

## Event Handling

### Speaker Events

```javascript
client.on('sessionCreated', (data) => {
  // Session created successfully
  // data.sessionId - Share with listeners
});

client.on('connectionWarning', (data) => {
  // Connection approaching 2-hour limit
  // data.remainingMinutes - Time until expiration
});

client.on('connectionRefreshed', (data) => {
  // Connection refresh completed
  // Continue streaming normally
});

client.on('error', (error) => {
  // Handle errors
  // error.message - Error description
  // error.code - Error code
});

client.on('disconnected', () => {
  // Connection closed
  // Clean up resources
});
```

### Listener Events

```javascript
client.on('sessionJoined', (data) => {
  // Successfully joined session
  // data.sessionId - Confirmed session ID
  // data.targetLanguage - Confirmed language
});

client.on('audioReceived', (data) => {
  // Received audio chunk
  // data.audioData - Base64 encoded audio
});

client.on('sessionEnded', () => {
  // Speaker ended session
  // Disconnect and clean up
});

client.on('sessionPaused', () => {
  // Speaker paused streaming
  // Stop audio playback
});

client.on('sessionResumed', () => {
  // Speaker resumed streaming
  // Resume audio playback
});

client.on('connectionRefreshed', () => {
  // Connection refresh completed
  // Continue listening normally
});

client.on('reconnected', () => {
  // Reconnected after unexpected disconnect
  // Resume normal operation
});
```

## Testing

### Unit Testing

Test individual components:

```javascript
// Test connection establishment
test('connects to WebSocket successfully', async () => {
  const client = new SpeakerClient(config);
  await client.authenticate('user', 'pass');
  await client.connect();
  expect(client.ws.readyState).toBe(WebSocket.OPEN);
});

// Test connection refresh
test('handles connection refresh', async () => {
  const client = new SpeakerClient(config);
  await client.connect();
  
  const refreshPromise = new Promise((resolve) => {
    client.on('connectionRefreshed', resolve);
  });
  
  // Simulate refresh message
  client.handleConnectionRefresh({
    type: 'connectionRefreshRequired',
    sessionId: 'test-session-123'
  });
  
  await refreshPromise;
  expect(client.ws.readyState).toBe(WebSocket.OPEN);
});
```

### Integration Testing

Test with actual WebSocket server:

```javascript
// Test end-to-end flow
test('speaker creates session and listener joins', async () => {
  const speaker = new SpeakerClient(config);
  await speaker.authenticate('speaker', 'pass');
  await speaker.connect();
  
  const sessionId = speaker.sessionId;
  
  const listener = new ListenerClient({
    ...config,
    sessionId: sessionId,
    targetLanguage: 'es'
  });
  
  await listener.connect();
  
  expect(listener.ws.readyState).toBe(WebSocket.OPEN);
});
```

### Load Testing

Test with multiple concurrent connections:

```javascript
// Test 100 concurrent listeners
test('handles 100 concurrent listeners', async () => {
  const speaker = new SpeakerClient(config);
  await speaker.connect();
  
  const listeners = [];
  for (let i = 0; i < 100; i++) {
    const listener = new ListenerClient({
      ...config,
      sessionId: speaker.sessionId,
      targetLanguage: 'es'
    });
    listeners.push(listener.connect());
  }
  
  await Promise.all(listeners);
  expect(listeners.length).toBe(100);
});
```

## Dependencies

### JavaScript/TypeScript

```json
{
  "dependencies": {
    "@aws-sdk/client-cognito-identity-provider": "^3.0.0",
    "websocket": "^1.0.34"
  },
  "devDependencies": {
    "@types/websocket": "^1.0.5",
    "typescript": "^5.0.0"
  }
}
```

### Python

```txt
boto3>=1.28.0
websockets>=11.0.0
```

## Best Practices

### 1. Always Handle Connection Refresh

Connection refresh is **required** for sessions longer than 2 hours. Implement the refresh handler even if you don't expect long sessions.

### 2. Implement Exponential Backoff

Use exponential backoff for reconnection attempts to avoid overwhelming the server during outages.

### 3. Buffer Audio During Transitions

Always buffer audio during connection refresh to ensure zero-loss transmission/playback.

### 4. Validate Messages

Always validate incoming messages before processing to prevent crashes from malformed data.

### 5. Clean Up Resources

Always clean up WebSocket connections, audio contexts, and event listeners when disconnecting.

### 6. Log Important Events

Log connection state changes, errors, and refresh events for debugging.

### 7. Handle Edge Cases

- Connection drops during refresh
- Multiple refresh messages
- Audio queue overflow
- Network timeouts

## Troubleshooting

### Connection Fails Immediately

**Cause**: Invalid WebSocket URL or network issue

**Solution**: Verify API endpoint URL and network connectivity

```javascript
// Check URL format
const url = 'wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod';
console.log('Connecting to:', url);
```

### Authentication Fails

**Cause**: Invalid credentials or Cognito configuration

**Solution**: Verify username, password, and Cognito settings

```javascript
// Test authentication separately
try {
  await client.authenticate('username', 'password');
  console.log('Authentication successful');
} catch (error) {
  console.error('Authentication failed:', error.message);
}
```

### No Audio Received

**Cause**: Speaker not streaming or language mismatch

**Solution**: Verify speaker is connected and streaming, check language codes

```javascript
// Log audio events
client.on('audioReceived', (data) => {
  console.log('Audio received:', data.audioData.length, 'bytes');
});
```

### Connection Refresh Fails

**Cause**: Network issue or server error

**Solution**: Implement retry logic with exponential backoff

```javascript
// Add retry logic
async handleConnectionRefresh(message, retryCount = 0) {
  try {
    await this.performRefresh(message);
  } catch (error) {
    if (retryCount < 5) {
      const delay = 30000 * Math.pow(2, retryCount);
      setTimeout(() => {
        this.handleConnectionRefresh(message, retryCount + 1);
      }, delay);
    }
  }
}
```

## Additional Resources

- [WebSocket API Documentation](../docs/API.md)
- [Deployment Guide](../DEPLOYMENT.md)
- [Design Document](../.kiro/specs/session-management-websocket/design.md)
- [Requirements Document](../.kiro/specs/session-management-websocket/requirements.md)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the design document for architecture details
3. Check CloudWatch Logs for server-side errors
4. Contact the development team
