# Task 3: Extend connection_handler Lambda for Speaker Controls

## Task Description

Extended the existing `connection_handler` Lambda to handle speaker broadcast control messages (pause, resume, mute, unmute, volume, state changes) and listener control messages (pause playback, change language). Implemented complete control message routing, state management, and listener notification logic.

## Task Instructions

### Requirements Addressed
- **Requirement 6**: Speaker Pause Control
- **Requirement 7**: Speaker Resume Control
- **Requirement 8**: Speaker Mute Control
- **Requirement 9**: Speaker Volume Control
- **Requirement 10**: Speaker State Change Notifications
- **Requirement 18**: Listener Control Message Routing

### Subtasks Completed
1. ✅ Add control message routing with role-based authorization
2. ✅ Implement pause/resume broadcast handlers
3. ✅ Implement mute/unmute broadcast handlers
4. ✅ Implement volume control handler with validation
5. ✅ Implement speaker state change handler
6. ✅ Implement listener notification logic using API Gateway Management API
7. ✅ Add listener control handlers (pausePlayback, changeLanguage)
8. ✅ Add comprehensive unit tests for all control handlers

## Task Tests

All tests passing:

```bash
python -m pytest tests/test_connection_handler.py -k "pause_broadcast or resume_broadcast or mute_broadcast or unmute_broadcast or set_volume or speaker_state_change or pause_playback or change_language or unauthorized or connection_not_found_for_control" -v
```

**Test Results**: 12 passed

### Test Coverage
- ✅ `test_pause_broadcast_success` - Pause broadcast with listener notification
- ✅ `test_resume_broadcast_success` - Resume broadcast with pause duration tracking
- ✅ `test_mute_broadcast_success` - Mute broadcast with listener notification
- ✅ `test_unmute_broadcast_success` - Unmute broadcast with listener notification
- ✅ `test_set_volume_success` - Set volume with validation and listener notification
- ✅ `test_set_volume_invalid_range` - Volume validation (0.0-1.0 range)
- ✅ `test_speaker_state_change_success` - Atomic state updates with multiple fields
- ✅ `test_pause_playback_listener_success` - Listener pause playback (client-side)
- ✅ `test_change_language_success` - Listener language change with validation
- ✅ `test_unauthorized_speaker_action_for_listener` - Authorization validation
- ✅ `test_unauthorized_listener_action_for_speaker` - Authorization validation
- ✅ `test_connection_not_found_for_control_message` - Error handling

## Task Solution

### Key Implementation Decisions

1. **Extended Existing Handler**: Modified `connection_handler` to handle both $connect events and MESSAGE events for control messages, avoiding the need for separate Lambda functions.

2. **Role-Based Authorization**: Implemented strict role validation ensuring speakers can only perform speaker actions and listeners can only perform listener actions.

3. **API Gateway Management API Integration**: Added boto3 client for `apigatewaymanagementapi` to send messages to WebSocket connections.

4. **Parallel Listener Notification**: Implemented `notify_listeners()` function that sends messages to all listeners in parallel, logging failures but continuing with other listeners.

5. **Decimal Handling**: Fixed BroadcastState model to properly serialize volume as Decimal for DynamoDB storage and convert back to float for JSON responses.

6. **Atomic State Updates**: Used existing repository methods for atomic broadcast state updates with proper error handling.

### Files Modified

#### Core Handler
- **`session-management/lambda/connection_handler/handler.py`**
  - Added imports for boto3, typing, and ItemNotFoundError
  - Initialized API Gateway Management API client
  - Updated `lambda_handler()` to route MESSAGE events to control handlers
  - Added `route_control_message()` for action routing with role validation
  - Added `broadcast_state_to_json()` helper for Decimal-to-float conversion
  - Added `send_to_connection()` for WebSocket message sending
  - Added `notify_listeners()` for parallel listener notification
  - Implemented 6 speaker control handlers:
    - `handle_pause_broadcast()`
    - `handle_resume_broadcast()` with pause duration tracking
    - `handle_mute_broadcast()`
    - `handle_unmute_broadcast()`
    - `handle_set_volume()` with validation
    - `handle_speaker_state_change()` with atomic updates
  - Implemented 2 listener control handlers:
    - `handle_pause_playback()` (acknowledgment only)
    - `handle_change_language()` with language validation

#### Models
- **`session-management/shared/models/broadcast_state.py`**
  - Updated `to_dict()` to convert volume to Decimal for DynamoDB compatibility

#### Metrics
- **`session-management/shared/utils/metrics.py`**
  - Added `emit_control_message_latency()`
  - Added `emit_listener_notification_latency()`
  - Added `emit_listener_notification_failures()`
  - Added `emit_pause_duration()`

#### Tests
- **`session-management/tests/test_connection_handler.py`**
  - Added `create_message_event()` helper for MESSAGE events
  - Added 12 comprehensive unit tests covering all control handlers
  - Tests validate state updates, listener notifications, authorization, and error handling

### Control Message Flow

1. **Speaker sends control message** → WebSocket MESSAGE event
2. **Lambda routes to `route_control_message()`** → Validates connection exists
3. **Role validation** → Ensures speaker/listener has permission for action
4. **Handler execution** → Updates broadcast state in DynamoDB
5. **Listener notification** → Sends message to all listeners via API Gateway Management API
6. **Acknowledgment** → Returns success response to sender

### Message Formats

**Speaker Control Messages**:
```json
{
  "action": "pauseBroadcast" | "resumeBroadcast" | "muteBroadcast" | "unmuteBroadcast",
  // No additional fields required
}

{
  "action": "setVolume",
  "volumeLevel": 0.75  // 0.0-1.0
}

{
  "action": "speakerStateChange",
  "state": {
    "isPaused": true,
    "isMuted": false,
    "volume": 0.8
  }
}
```

**Listener Control Messages**:
```json
{
  "action": "pausePlayback"
  // Client-side only, just acknowledgment
}

{
  "action": "changeLanguage",
  "targetLanguage": "fr"
}
```

**Listener Notification Messages**:
```json
{
  "type": "broadcastPaused" | "broadcastResumed" | "broadcastMuted" | "broadcastUnmuted",
  "sessionId": "golden-eagle-427",
  "timestamp": 1699500000000
}

{
  "type": "volumeChanged",
  "sessionId": "golden-eagle-427",
  "volumeLevel": 0.75,
  "timestamp": 1699500000000
}

{
  "type": "speakerStateChanged",
  "sessionId": "golden-eagle-427",
  "broadcastState": {
    "isActive": true,
    "isPaused": false,
    "isMuted": false,
    "volume": 1.0,
    "lastStateChange": 1699500000000
  },
  "timestamp": 1699500000000
}
```

### Error Handling

- **403 Forbidden**: Unauthorized action for role
- **404 Not Found**: Connection or session not found
- **400 Bad Request**: Invalid parameters (volume out of range, invalid language, etc.)
- **500 Internal Server Error**: Unexpected errors with detailed logging

### Metrics Emitted

- `ControlMessageLatency` - Processing time by action type
- `ListenerNotificationLatency` - Time to notify all listeners
- `ListenerNotificationFailures` - Count of failed notifications
- `BroadcastPauseDuration` - Duration of broadcast pauses

## Next Steps

Task 3 is complete. The connection_handler Lambda now fully supports:
- ✅ Speaker broadcast controls (pause, resume, mute, unmute, volume, state changes)
- ✅ Listener controls (pause playback, change language)
- ✅ Role-based authorization
- ✅ Parallel listener notification
- ✅ Comprehensive error handling and metrics

The next task (Task 4) will implement the session_status_handler Lambda for real-time session statistics.
