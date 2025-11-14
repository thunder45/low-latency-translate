# Tasks 13-15: Application Integration and Connection Refresh

## Task Description

Implemented the core integration services that orchestrate WebSocket communication, audio processing, and connection management for both speaker and listener applications. These services tie together all previously implemented components into functional applications.

## Task Instructions

### Task 13: Speaker Application Integration
- Create SpeakerService to orchestrate WebSocket and audio capture
- Implement audio transmission flow with pause/mute handling
- Implement session status polling every 5 seconds
- Handle quality warnings from server
- Implement session end flow with retry logic

### Task 14: Listener Application Integration
- Create ListenerService to orchestrate WebSocket and audio playback
- Implement audio reception and playback flow
- Implement language switching with buffer clearing
- Handle speaker state messages (paused, muted, resumed, unmuted)
- Handle session ended message

### Task 15: Connection Refresh Mechanism
- Handle connectionRefreshRequired message in both apps
- Display warning at 100 minutes, initiate refresh at 115 minutes
- Implement refresh retry logic with exponential backoff
- Support up to 5 retry attempts

## Task Solution

### Files Created

1. **frontend-client-apps/speaker-app/src/services/SpeakerService.ts**
   - Orchestrates WebSocket client and AudioCapture
   - Manages session lifecycle (initialize, start broadcast, end session)
   - Handles audio transmission with pause/mute controls
   - Implements session status polling every 5 seconds
   - Processes quality warnings and updates store
   - Implements retry logic for session end with exponential backoff

2. **frontend-client-apps/listener-app/src/services/ListenerService.ts**
   - Orchestrates WebSocket client and AudioPlayback
   - Manages session joining and audio reception
   - Handles playback controls (pause, resume, mute, volume)
   - Implements language switching with buffer clearing
   - Processes speaker state changes (paused, muted, resumed, unmuted)
   - Handles session ended message

3. **frontend-client-apps/shared/hooks/useConnectionRefresh.ts**
   - React hook for managing connection refresh
   - Monitors session duration and triggers refresh at 115 minutes
   - Shows warning at 100 minutes (20 minutes before refresh)
   - Implements retry logic with exponential backoff (up to 5 attempts)
   - Handles both client-initiated and server-initiated refresh

### Key Implementation Details

#### SpeakerService Architecture
```typescript
class SpeakerService {
  - wsClient: WebSocketClient
  - audioCapture: AudioCapture
  - statusPollInterval: NodeJS.Timeout
  - retryHandler: RetryHandler
  
  Methods:
  - initialize(): Connect WebSocket and create session
  - startBroadcast(): Start audio capture and transmission
  - pause/resume(): Control broadcast state
  - mute/unmute(): Control audio capture
  - endSession(): End session with retry logic
  - getInputLevel(): Get current audio level
}
```

#### ListenerService Architecture
```typescript
class ListenerService {
  - wsClient: WebSocketClient
  - audioPlayback: AudioPlayback
  
  Methods:
  - initialize(): Connect WebSocket and join session
  - pause/resume(): Control playback
  - mute/unmute(): Control audio output
  - setVolume(): Adjust playback volume
  - switchLanguage(): Change target language
  - leave(): Leave session and cleanup
}
```

#### Connection Refresh Hook
```typescript
useConnectionRefresh(wsClient, sessionStartTime, config) {
  - Monitors elapsed time since session start
  - Shows warning at 100 minutes
  - Initiates refresh at 115 minutes
  - Retries up to 5 times with exponential backoff
  - Handles server-initiated refresh requests
}
```

### Integration Points

1. **WebSocket Message Handlers**
   - sessionCreated → Update speaker store with session details
   - sessionJoined → Update listener store with session details
   - audio → Queue audio for playback in listener
   - audio_quality_warning → Add warning to speaker store
   - sessionStatus → Update listener stats in speaker store
   - speakerPaused/Resumed/Muted/Unmuted → Update listener store
   - sessionEnded → Stop playback and show message
   - connectionRefreshRequired → Trigger refresh warning

2. **Audio Processing Flow**
   - Speaker: AudioCapture → onChunk callback → WebSocket send
   - Listener: WebSocket receive → AudioPlayback.queueAudio → Playback

3. **State Management**
   - Both services update Zustand stores for UI reactivity
   - Store updates trigger component re-renders
   - Connection state, audio state, and session state synchronized

### Error Handling

1. **WebSocket Errors**
   - Handled by ErrorHandler with user-friendly messages
   - Automatic reconnection with exponential backoff
   - Maximum 5 reconnection attempts

2. **Audio Errors**
   - Microphone permission denial → User-friendly error message
   - Audio processing errors → Graceful degradation
   - Buffer overflow → Warning displayed to user

3. **Session End Errors**
   - Retry with exponential backoff (1s, 2s, 4s)
   - Up to 3 attempts before giving up
   - Cleanup performed regardless of success

### Requirements Addressed

**Task 13 Requirements:**
- Requirement 2.1, 2.3, 3.1: Session creation and WebSocket connection
- Requirement 3.2, 3.3: Audio capture and transmission
- Requirement 6.1, 6.2, 6.4: Pause/mute controls
- Requirement 5.1, 5.4, 5.5: Session status polling
- Requirement 4.1-4.5: Quality warning handling
- Requirement 7.1-7.5: Session end flow

**Task 14 Requirements:**
- Requirement 8.1, 8.2, 8.3: Session joining
- Requirement 9.1-9.5: Audio reception and playback
- Requirement 10.1, 10.4: Playback controls
- Requirement 11.1-11.5: Language switching
- Requirement 12.1-12.5: Speaker state handling
- Requirement 15.5: Session ended handling

**Task 15 Requirements:**
- Requirement 14.1-14.4: Connection refresh mechanism
- Requirement 14.5: Refresh retry logic

## Testing Notes

These services integrate multiple components and should be tested with:

1. **Unit Tests** (to be implemented in Task 23):
   - Mock WebSocketClient and AudioCapture/AudioPlayback
   - Test message handling logic
   - Test state updates
   - Test error handling

2. **Integration Tests** (to be implemented in Task 24):
   - Test complete speaker flow (login → create → broadcast → end)
   - Test complete listener flow (join → listen → controls → leave)
   - Test connection refresh flow
   - Test error recovery scenarios

3. **Manual Testing**:
   - Test with real WebSocket server
   - Test audio capture and playback
   - Test connection refresh at 115 minutes
   - Test quality warnings display
   - Test session end and cleanup

## Next Steps

1. Implement keyboard shortcuts (Task 16)
2. Implement accessibility features (Task 17)
3. Implement preference persistence (Task 18)
4. Create main application components that use these services
5. Write comprehensive tests (Tasks 23-24)

## Notes

- Services are designed to be instantiated once per session
- Cleanup methods should be called when unmounting components
- Connection refresh hook should be used in main app components
- Error handling relies on ErrorHandler utility for consistency
- All WebSocket messages follow the defined message types
- Audio processing uses Web Audio API for browser compatibility
