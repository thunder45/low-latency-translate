# Design Document

## Overview

This design addresses the session creation flow issue in the speaker application by restructuring the WebSocket initialization sequence. The current implementation attempts to send messages through a non-existent WebSocket client. The solution establishes the WebSocket connection first, then sends the session creation request through the connected client.

## Architecture

### Current Flow (Broken)

```
User clicks "Create Session"
  ↓
SessionCreator.handleCreateSession()
  ↓
onSendMessage(message) → wsClient?.send(msg)
  ↓
wsClient is null → Nothing happens ❌
```

### New Flow (Fixed)

```
User clicks "Create Session"
  ↓
SpeakerApp.handleCreateSession()
  ↓
1. Create WebSocket client
  ↓
2. Connect WebSocket
  ↓
3. Send session creation message
  ↓
4. Wait for sessionCreated response
  ↓
5. Initialize SpeakerService
  ↓
6. Start broadcasting
```

## Components and Interfaces

### Modified Components

#### 1. SessionCreator Component

**Changes:**
- Remove `onSendMessage` prop (no longer needed)
- Add `onCreateSession` callback that receives configuration
- Simplify to just collect user input and trigger creation

**New Interface:**
```typescript
interface SessionCreatorProps {
  onCreateSession: (config: SessionConfig) => Promise<void>;
  isCreating: boolean;
  error: string | null;
}

interface SessionConfig {
  sourceLanguage: string;
  qualityTier: 'standard' | 'premium';
}
```

#### 2. SpeakerApp Component

**Changes:**
- Add `handleCreateSession` method that orchestrates the full flow
- Create WebSocket client before sending messages
- Add state for creation progress and errors
- Handle WebSocket events during creation

**New State:**
```typescript
interface SpeakerAppState {
  isCreatingSession: boolean;
  creationError: string | null;
  creationStep: 'idle' | 'connecting' | 'creating' | 'initializing' | 'complete';
}
```

#### 3. SpeakerService

**Changes:**
- Modify `initialize()` to accept an already-connected WebSocket client
- Remove WebSocket creation from constructor
- Accept WebSocket client as a parameter

**New Constructor:**
```typescript
constructor(
  config: SpeakerServiceConfig,
  wsClient: WebSocketClient
)
```

### New Utility: SessionCreationOrchestrator

**Purpose:** Encapsulate the session creation flow logic

**Responsibilities:**
- Create and connect WebSocket client
- Send session creation request
- Wait for response with timeout
- Handle errors and retries
- Clean up on failure

**Interface:**
```typescript
class SessionCreationOrchestrator {
  async createSession(config: SessionCreationConfig): Promise<SessionCreationResult>
  
  private async connectWebSocket(): Promise<WebSocketClient>
  private async sendCreationRequest(): Promise<string>
  private async waitForResponse(timeout: number): Promise<SessionCreatedMessage>
  private cleanup(): void
}

interface SessionCreationConfig {
  wsUrl: string;
  jwtToken: string;
  sourceLanguage: string;
  qualityTier: 'standard' | 'premium';
  timeout?: number;
  retryAttempts?: number;
}

interface SessionCreationResult {
  success: boolean;
  sessionId?: string;
  wsClient?: WebSocketClient;
  error?: string;
}
```

## Data Models

### Session Creation State Machine

```
States:
- IDLE: Initial state, waiting for user action
- CONNECTING: Establishing WebSocket connection
- CREATING: Sending session creation request
- WAITING: Waiting for sessionCreated response
- INITIALIZING: Setting up SpeakerService
- COMPLETE: Session ready, broadcasting started
- ERROR: Creation failed, showing error message

Transitions:
IDLE → CONNECTING (user clicks "Create Session")
CONNECTING → CREATING (WebSocket connected)
CONNECTING → ERROR (connection failed after retries)
CREATING → WAITING (request sent)
CREATING → ERROR (send failed)
WAITING → INITIALIZING (sessionCreated received)
WAITING → ERROR (timeout or error response)
INITIALIZING → COMPLETE (SpeakerService started)
INITIALIZING → ERROR (initialization failed)
ERROR → IDLE (user clicks retry)
```

### WebSocket Message Flow

```typescript
// Client → Server
{
  action: 'createSession',
  sourceLanguage: 'en',
  qualityTier: 'standard'
}

// Server → Client (Success)
{
  type: 'sessionCreated',
  sessionId: 'golden-eagle-427',
  sourceLanguage: 'en',
  qualityTier: 'standard',
  timestamp: 1699500000000
}

// Server → Client (Error)
{
  type: 'error',
  code: 'SESSION_CREATION_FAILED',
  message: 'Failed to create session',
  details: { ... }
}
```

## Error Handling

### Error Categories

1. **Connection Errors**
   - WebSocket connection timeout
   - Network unavailable
   - Invalid WebSocket URL
   - **Handling:** Retry with exponential backoff (3 attempts)

2. **Creation Errors**
   - Session creation request failed
   - Invalid parameters
   - Server error
   - **Handling:** Display error, allow retry

3. **Timeout Errors**
   - No response within 5 seconds
   - **Handling:** Retry request, then fail with timeout message

4. **Initialization Errors**
   - SpeakerService initialization failed
   - Audio capture failed
   - **Handling:** Clean up WebSocket, display error

### Error Messages

```typescript
const ERROR_MESSAGES = {
  CONNECTION_FAILED: 'Unable to connect to server. Please check your internet connection and try again.',
  CONNECTION_TIMEOUT: 'Connection timed out. Please try again.',
  CREATION_FAILED: 'Failed to create session. Please try again.',
  CREATION_TIMEOUT: 'Session creation timed out. Please try again.',
  INITIALIZATION_FAILED: 'Failed to initialize broadcast. Please check your microphone permissions.',
  UNKNOWN_ERROR: 'An unexpected error occurred. Please try again.',
};
```

### Retry Strategy

```typescript
interface RetryConfig {
  maxAttempts: 3;
  initialDelay: 1000; // 1 second
  maxDelay: 4000; // 4 seconds
  backoffMultiplier: 2;
}

// Retry delays: 1s, 2s, 4s
```

## Testing Strategy

### Unit Tests

1. **SessionCreator Component**
   - Renders form correctly
   - Calls onCreateSession with correct config
   - Disables button when isCreating is true
   - Displays error when error prop is set

2. **SessionCreationOrchestrator**
   - Creates WebSocket client with correct config
   - Sends session creation request after connection
   - Waits for sessionCreated response
   - Retries on connection failure
   - Times out after 5 seconds
   - Cleans up on failure

3. **SpeakerApp Component**
   - Handles session creation flow
   - Updates state correctly during creation
   - Displays errors to user
   - Initializes SpeakerService after creation
   - Cleans up on unmount

### Integration Tests

1. **Successful Session Creation**
   - User clicks "Create Session"
   - WebSocket connects
   - Session is created
   - Broadcast starts
   - UI shows session display

2. **Connection Failure with Retry**
   - User clicks "Create Session"
   - First connection attempt fails
   - Automatic retry succeeds
   - Session is created

3. **Creation Timeout**
   - User clicks "Create Session"
   - WebSocket connects
   - No response received
   - Timeout error displayed
   - User can retry

4. **Multiple Rapid Clicks**
   - User clicks "Create Session" multiple times
   - Only one creation attempt is made
   - Subsequent clicks are ignored

### Manual Testing Checklist

- [ ] Click "Create Session" with valid config
- [ ] Session is created and broadcast starts
- [ ] Click "Create Session" with network disconnected
- [ ] Error message is displayed
- [ ] Reconnect network and retry
- [ ] Session is created successfully
- [ ] Click "Create Session" multiple times rapidly
- [ ] Only one session is created
- [ ] Navigate away during creation
- [ ] Resources are cleaned up

## Performance Considerations

### Latency Targets

- WebSocket connection: < 1 second
- Session creation request: < 500ms
- Total session creation: < 2 seconds (p95)

### Resource Management

- Clean up WebSocket on failure
- Cancel pending operations on unmount
- Prevent memory leaks from event listeners

### User Experience

- Show loading state immediately (< 100ms)
- Update progress during creation
- Provide clear error messages
- Allow easy retry on failure

## Security Considerations

### JWT Token Handling

- Token is passed to WebSocket client
- Token is included in connection query parameters
- Token is validated by backend authorizer

### Input Validation

- Validate source language code (ISO 639-1)
- Validate quality tier (standard | premium)
- Sanitize all user inputs

### Error Information

- Don't expose internal error details to user
- Log detailed errors for debugging
- Show user-friendly error messages

## Deployment Strategy

### Rollout Plan

1. **Development Testing**
   - Test locally with dev environment
   - Verify all error scenarios
   - Check retry logic

2. **Staging Deployment**
   - Deploy to staging environment
   - Run integration tests
   - Manual testing with real WebSocket

3. **Production Deployment**
   - Deploy during low-traffic period
   - Monitor error rates
   - Be ready to rollback if issues

### Rollback Plan

If issues are detected:
1. Revert to previous version
2. Investigate root cause
3. Fix and redeploy

### Monitoring

- Track session creation success rate
- Monitor WebSocket connection failures
- Alert on high error rates (> 5%)
- Track session creation latency

## Future Enhancements

### v1.1 Improvements

- Add progress bar during creation
- Show connection quality indicator
- Implement connection pre-check
- Add "Test Connection" button

### v2.0 Features

- Remember last used configuration
- Quick create with defaults
- Session templates
- Batch session creation

## Open Questions

1. **Q:** Should we pre-connect the WebSocket on app load?
   **A:** No, wait for user action to avoid unnecessary connections

2. **Q:** What should happen if user closes browser during creation?
   **A:** Backend will clean up after connection timeout (10 minutes)

3. **Q:** Should we show detailed connection progress?
   **A:** Yes, show "Connecting...", "Creating session...", "Starting broadcast..."

4. **Q:** How long should we wait for sessionCreated response?
   **A:** 5 seconds, then timeout and allow retry
