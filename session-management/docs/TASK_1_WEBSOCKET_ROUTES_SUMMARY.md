# Task 1: Configure WebSocket API Routes and Integrate with Handlers

## Task Description

Configure 10 new custom WebSocket routes in API Gateway and integrate them with existing and new Lambda handlers to support audio streaming, speaker controls, session status queries, and listener controls.

## Task Instructions

### Requirements Addressed

- **Requirement 19**: WebSocket Route Configuration - Configure 10 custom routes in API Gateway
- **Requirement 20**: Lambda Handler Implementation - Implement handlers for all routes with appropriate timeouts and memory

### Subtasks Completed

#### 1.1 Add sendAudio Route Configuration ✅ (Placeholder)
- **Status**: Placeholder added - Full implementation in Task 2
- **Note**: The sendAudio route will be configured when the audio_processor Lambda from the audio-transcription component is integrated
- **Configuration**:
  - Route: `sendAudio`
  - Handler: audio_processor Lambda (from audio-transcription component)
  - Timeout: 60 seconds
  - Binary WebSocket frame support required
  - Content handling: CONVERT_TO_BINARY for audio chunks

#### 1.2 Add Speaker Control Routes ✅
- **Status**: Complete
- **Routes Configured**:
  1. `pauseBroadcast` - Pause audio broadcasting
  2. `resumeBroadcast` - Resume audio broadcasting
  3. `muteBroadcast` - Mute microphone
  4. `unmuteBroadcast` - Unmute microphone
  5. `setVolume` - Set broadcast volume (0.0-1.0)
  6. `speakerStateChange` - Update multiple state fields
- **Handler**: connection_handler Lambda (extended)
- **Integration Timeout**: 10 seconds
- **IAM Permissions Added**:
  - `execute-api:ManageConnections` - Send messages to WebSocket connections
  - `execute-api:Invoke` - Invoke API Gateway Management API

#### 1.3 Add Session Status Route ✅
- **Status**: Complete
- **Route**: `getSessionStatus`
- **Handler**: session_status_handler Lambda (new)
- **Integration Timeout**: 5 seconds
- **Lambda Configuration**:
  - Memory: 256 MB (default)
  - Timeout: 5 seconds
  - Environment Variables:
    - `SESSIONS_TABLE`: Sessions DynamoDB table name
    - `CONNECTIONS_TABLE`: Connections DynamoDB table name
    - `STATUS_QUERY_TIMEOUT_MS`: 500ms
    - `PERIODIC_UPDATE_INTERVAL_SECONDS`: 30s
    - `LISTENER_COUNT_CHANGE_THRESHOLD_PERCENT`: 10%
- **IAM Permissions**:
  - DynamoDB read access to Sessions and Connections tables

#### 1.4 Add Listener Control Routes ✅
- **Status**: Complete
- **Routes Configured**:
  1. `pausePlayback` - Pause audio playback (client-side)
  2. `changeLanguage` - Switch target language
- **Handler**: connection_handler Lambda (extended)
- **Integration Timeout**: 5 seconds

## Task Solution

### Files Created

1. **session-management/lambda/session_status_handler/__init__.py**
   - Package initialization for session status handler

2. **session-management/lambda/session_status_handler/handler.py**
   - Placeholder Lambda handler for session status queries
   - Returns mock session status response
   - Full implementation will be done in Task 4

3. **session-management/lambda/session_status_handler/requirements.txt**
   - No additional dependencies (uses Python standard library)

### Files Modified

1. **session-management/infrastructure/stacks/session_management_stack.py**
   - Added `_create_session_status_handler()` method
   - Updated `_create_lambda_integration()` to support custom timeouts
   - Added 9 new WebSocket routes (8 implemented + 1 placeholder):
     - Speaker control routes (6): pauseBroadcast, resumeBroadcast, muteBroadcast, unmuteBroadcast, setVolume, speakerStateChange
     - Session status route (1): getSessionStatus
     - Listener control routes (2): pausePlayback, changeLanguage
   - Added API Gateway Management API permissions to connection_handler
   - Updated deployment dependencies to include all new routes

### Route Configuration Summary

| Route | Handler | Timeout | Status | Requirements |
|-------|---------|---------|--------|--------------|
| sendAudio | audio_processor | 60s | Placeholder | 1, 19 |
| pauseBroadcast | connection_handler | 10s | ✅ Complete | 6, 19 |
| resumeBroadcast | connection_handler | 10s | ✅ Complete | 7, 19 |
| muteBroadcast | connection_handler | 10s | ✅ Complete | 8, 19 |
| unmuteBroadcast | connection_handler | 10s | ✅ Complete | 8, 19 |
| setVolume | connection_handler | 10s | ✅ Complete | 9, 19 |
| speakerStateChange | connection_handler | 10s | ✅ Complete | 10, 19 |
| getSessionStatus | session_status_handler | 5s | ✅ Complete | 11, 19 |
| pausePlayback | connection_handler | 5s | ✅ Complete | 18, 19 |
| changeLanguage | connection_handler | 5s | ✅ Complete | 18, 19 |

### IAM Permissions Added

**connection_handler Lambda**:
- `execute-api:ManageConnections` - Required to send messages to WebSocket connections (for listener notifications)
- `execute-api:Invoke` - Required to invoke API Gateway Management API

**session_status_handler Lambda**:
- `dynamodb:GetItem` - Read session records
- `dynamodb:Query` - Query connections by sessionId using GSI

### Integration Details

#### Speaker Control Integration
- **Integration ID**: SpeakerControlIntegration
- **Timeout**: 10,000ms (10 seconds)
- **Routes**: pauseBroadcast, resumeBroadcast, muteBroadcast, unmuteBroadcast, setVolume, speakerStateChange
- **Handler**: connection_handler Lambda
- **Purpose**: Handle speaker broadcast control messages and notify listeners

#### Session Status Integration
- **Integration ID**: SessionStatusIntegration
- **Timeout**: 5,000ms (5 seconds)
- **Route**: getSessionStatus
- **Handler**: session_status_handler Lambda
- **Purpose**: Query and return real-time session statistics

#### Listener Control Integration
- **Integration ID**: ListenerControlIntegration
- **Timeout**: 5,000ms (5 seconds)
- **Routes**: pausePlayback, changeLanguage
- **Handler**: connection_handler Lambda
- **Purpose**: Handle listener-specific control messages

### Deployment Dependencies

All new routes are added as dependencies to the WebSocket API deployment to ensure proper ordering:
- pause_broadcast_route
- resume_broadcast_route
- mute_broadcast_route
- unmute_broadcast_route
- set_volume_route
- speaker_state_change_route
- get_session_status_route
- pause_playback_route
- change_language_route

### Next Steps

1. **Task 1.1 (sendAudio route)**: Will be completed when audio_processor Lambda is integrated in Task 2
2. **Task 2**: Extend audio_processor Lambda to handle WebSocket audio messages
3. **Task 3**: Extend connection_handler Lambda for speaker controls
4. **Task 4**: Implement session_status_handler Lambda for status queries

### Testing Notes

- CDK stack can be synthesized to verify infrastructure configuration
- Routes will be functional after deployment
- Handler implementations (Tasks 2-4) are required for full functionality
- Integration tests should verify route routing and timeout configurations

### Architecture Notes

**Route Selection Expression**: `$request.body.action`
- All custom routes use the `action` field in the message body for routing
- Example: `{"action": "pauseBroadcast"}` routes to pauseBroadcast route

**Binary WebSocket Support**:
- sendAudio route will require binary frame support (not JSON)
- API Gateway supports binary frames up to 128 KB
- Content handling will be set to CONVERT_TO_BINARY for audio chunks

**Timeout Strategy**:
- Audio processing: 60s (allows for Transcribe stream initialization)
- Speaker controls: 10s (includes DynamoDB updates + listener notifications)
- Session status: 5s (read-only queries)
- Listener controls: 5s (simple updates)

## Verification

### CDK Synthesis
```bash
cd session-management/infrastructure
cdk synth
```

Expected output should include:
- 9 new CfnRoute resources
- 3 new CfnIntegration resources
- 1 new Lambda function (session_status_handler)
- Updated IAM policies for connection_handler

### Route Verification
After deployment, verify routes exist:
```bash
aws apigatewayv2 get-routes --api-id <api-id>
```

Expected routes:
- $connect
- $disconnect
- heartbeat
- refreshConnection
- pauseBroadcast
- resumeBroadcast
- muteBroadcast
- unmuteBroadcast
- setVolume
- speakerStateChange
- getSessionStatus
- pausePlayback
- changeLanguage

## Summary

Task 1 successfully configured 9 out of 10 WebSocket routes with appropriate Lambda integrations and IAM permissions. The sendAudio route is documented as a placeholder and will be implemented when the audio_processor Lambda is integrated in Task 2. All speaker control routes, session status route, and listener control routes are fully configured and ready for handler implementation in subsequent tasks.
