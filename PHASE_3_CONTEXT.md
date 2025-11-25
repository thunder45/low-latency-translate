# Phase 3 Context: Backend KVS Stream Processing

**Created**: November 25, 2025  
**Purpose**: Context for Phase 3 backend implementation task

---

## Phase 2 Completion Status

### ✅ What's Working

**Speaker App (Fully Functional)**:
- EventEmitter browser compatibility fixed
- WebRTC UDP audio streaming to KVS channel
- Session creation via HTTP API
- WebSocket control messages
- Microphone capture and streaming
- Master role connection to KVS

**Infrastructure Created**:
- New Identity Pool: `us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4`
- Authenticated Role: `KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN`
- Guest Role: `KVSWebRTC-dev-GuestRole` (viewer-only permissions)
- KVSWebRTC-dev CDK stack deployed
- WebSocket $connect route: Authorization set to NONE

**What Works End-to-End**:
- Speaker logs in → creates session → streams audio via WebRTC UDP
- Listener fetches session metadata → connects WebSocket → joins session
- Session management and control messages functional

### ⚠️ What's Not Working

**Listener WebRTC** (Blocked by permissions):
- Guest role has correct KVS permissions
- Identity Pool configured for guest access
- Still getting 403 on `GetSignalingChannelEndpoint`
- May require CDK-managed role instead of manually created role
- **OR** this is expected - Phase 3 backend should handle viewer connections

**Also**: Backend doesn't consume KVS streams yet (Phase 3 work)

---

## Current Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SPEAKER APP (WORKING)                    │
├─────────────────────────────────────────────────────────────┤
│ • User authenticates (Cognito User Pool + JWT)             │
│ • HTTP API: Create session → Get KVS channel info          │
│ • WebRTC: Connect as MASTER → Stream microphone audio      │
│ • WebSocket: Control messages, session status              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  AWS INFRASTRUCTURE                         │
├─────────────────────────────────────────────────────────────┤
│ • HTTP API (Lambda): Session management, KVS channel CRUD  │
│ • WebSocket API: Control plane, coordination               │
│ • KVS Signaling Channel: WebRTC signaling per session      │
│ • DynamoDB: Sessions, connections, rate limits             │
│ • Identity Pool: AWS credentials for KVS access            │
│                                                             │
│ ⚠️  MISSING (Phase 3):                                      │
│ • Lambda to consume KVS streams                            │
│ • Audio extraction from WebRTC                             │
│ • Transcription service integration                        │
│ • Translation service integration                          │
│ • Emotion detection integration                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  LISTENER APP (PARTIAL)                     │
├─────────────────────────────────────────────────────────────┤
│ • HTTP API: Get session metadata ✅                         │
│ • WebSocket: Connect, join session, control messages ✅    │
│ • WebRTC: Connect as VIEWER → Get audio ❌ (403)           │
│                                                             │
│ CURRENT EXPECTED FLOW (not working):                       │
│ • Get guest credentials from Identity Pool                 │
│ • Connect to KVS channel as VIEWER                         │
│ • Receive audio directly from speaker                      │
│                                                             │
│ PHASE 3 TARGET FLOW:                                        │
│ • WebSocket receives transcription/translation             │
│ • WebSocket receives emotion data                          │
│ • Display text + play processed audio                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Files Modified in Phase 2 (Not Yet Committed)

### Frontend

1. **`frontend-client-apps/speaker-app/vite.config.ts`**
   - Fixed events polyfill path for EventEmitter

2. **`frontend-client-apps/listener-app/vite.config.ts`**
   - Fixed events polyfill path for EventEmitter

3. **`frontend-client-apps/shared/services/KVSWebRTCService.ts`** (NEW - 508 lines)
   - Master/Viewer WebRTC connections
   - KVS SignalingClient integration
   - ICE server (STUN/TURN) management
   - Audio track management

4. **`frontend-client-apps/shared/services/KVSCredentialsProvider.ts`** (NEW - 151 lines, modified)
   - JWT → AWS credentials exchange
   - Supports authenticated and unauthenticated flows
   - Credential caching (50-min TTL)

5. **`frontend-client-apps/speaker-app/src/services/SpeakerService.ts`** (REWRITTEN)
   - Removed AudioCapture (WebSocket audio)
   - Added KVS WebRTC for audio streaming
   - WebSocket for control messages only

6. **`frontend-client-apps/listener-app/src/services/ListenerService.ts`** (REWRITTEN, modified)
   - Removed AudioPlayback (WebSocket audio)
   - Added KVS WebRTC for audio reception
   - Fixed to not pass empty JWT token to WebSocket
   - WebSocket for control messages only

7. **`frontend-client-apps/speaker-app/src/components/SpeakerApp.tsx`**
   - Extract KVS config from HTTP session response
   - Pass to SpeakerService

8. **`frontend-client-apps/listener-app/src/components/ListenerApp.tsx`**
   - Fetch session metadata for KVS config
   - Pass to ListenerService

9. **`frontend-client-apps/shared/utils/SessionCreationOrchestrator.ts`**
   - Return full SessionMetadata with KVS fields

10. **`frontend-client-apps/shared/utils/config.ts`**
    - Added identityPoolId to config interface

### Backend

1. **`session-management/infrastructure/stacks/kvs_webrtc_stack.py`** (ALREADY EXISTS)
   - Creates KVSManagementRole for Lambda
   - Creates KVSClientRole for authenticated users
   - Only creates client role if cognito_identity_pool_id provided

2. **`session-management/infrastructure/stacks/session_management_stack.py`** (MODIFIED)
   - Changed $connect route: CUSTOM authorization → NONE
   - Allows both speakers (with JWT) and listeners (without JWT)

3. **`session-management/infrastructure/config/dev.json`** (LOCAL ONLY - gitignored)
   - Added: `"cognito_identity_pool_id": "us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4"`

4. **`session-management/infrastructure/app.py`**
   - Passes cognito_identity_pool_id to KVSWebRTC stack

### IAM Roles Created Manually

1. **KVSWebRTC-dev-GuestRole** (CLI created)
   - Trust policy: unauthenticated identities
   - Permissions: Viewer-only KVS access
   - ARN: `arn:aws:iam::193020606184:role/KVSWebRTC-dev-GuestRole`

---

## Configuration State

### Identity Pool
- **ID**: `us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4`
- **Name**: `IdentityPool_LowLatencyTranslate`
- **Authenticated Access**: ✅ Enabled
- **Unauthenticated (Guest) Access**: ✅ Enabled
- **Authenticated Role**: `KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN`
- **Guest Role**: `KVSWebRTC-dev-GuestRole`

### Frontend .env Files
Both speaker and listener have:
```bash
VITE_COGNITO_IDENTITY_POOL_ID=us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4
VITE_COGNITO_USER_POOL_ID=us-east-1_WoaXmyQLQ
VITE_COGNITO_CLIENT_ID=38t8057tbi0o6873qt441kuo3n
VITE_AWS_REGION=us-east-1
```

### Backend Config
`session-management/infrastructure/config/dev.json`:
```json
{
  "cognito_identity_pool_id": "us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4"
}
```

### CDK Stacks Deployed
- ✅ `KVSWebRTC-dev`: IAM roles for KVS access
- ✅ `SessionManagement-dev`: WebSocket API, Lambda functions

---

## Phase 2 Commits

**Commit 1**: `bf53c67` - EventEmitter browser compatibility fix  
**Commit 2**: `f590674` - Phase 3 IAM permissions documentation  
**Commit 3**: `ace4061` - Identity Pool ID clarification

---

## Phase 3 Objective

**Goal**: Backend consumes KVS streams, processes audio, sends results to listeners

### Architecture Target

```
Speaker → WebRTC UDP → KVS Channel
                           ↓
                    Backend Lambda (NEW)
                           ↓
                  ┌────────┴────────┐
                  ↓                 ↓
            Transcription      Translation
                  ↓                 ↓
              WebSocket ←── Emotion Detection
                  ↓
            Listener App
```

### What Needs to Be Built

1. **KVS Stream Consumer Lambda**
   - Subscribe to KVS signaling channel events
   - Extract audio from WebRTC stream
   - Convert to format for transcription
   - Send to transcription service

2. **Audio Processing Pipeline Integration**
   - Feed audio to existing AWS Transcribe
   - Get transcription results
   - Send to translation service
   - Get emotion detection from audio features

3. **WebSocket Distribution**
   - Send transcriptions to listeners (target language)
   - Send translations in real-time
   - Send emotion data
   - Handle multiple listeners per session

4. **Connection Management**
   - Map KVS channel → Session ID
   - Track which listeners need which languages
   - Handle KVS stream lifecycle

---

## Key Technical Details for Phase 3

### KVS Stream Consumption

**AWS Service**: Kinesis Video Streams GetMedia API
**Lambda Trigger**: Need to poll or use EventBridge
**Audio Format**: WebRTC uses Opus codec, need to convert

```python
import boto3

kvs_client = boto3.client('kinesisvideo')
kvs_video_client = boto3.client('kinesis-video-media')

# Get media endpoint
endpoint_response = kvs_client.get_data_endpoint(
    StreamARN=channel_arn,
    APIName='GET_MEDIA'
)

# Get media stream
stream = kvs_video_client.get_media(
    StreamARN=channel_arn,
    StartSelector={'StartSelectorType': 'NOW'}
)

# Process fragments
for chunk in stream['Payload']:
    # Extract audio
    # Send to transcription
```

### Transcription Service Integration

**Already Exists**: `audio-transcription/lambda/audio_processor/`

**Current Input**: Base64 encoded PCM audio (WebSocket)  
**Phase 3 Input**: Binary audio from KVS stream

**Need to adapt**:
- Audio format conversion
- Streaming transcription setup
- Real-time result delivery

### WebSocket Message Format

Listeners expect:
```json
{
  "type": "transcription",
  "sessionId": "...",
  "text": "...",
  "isFinal": true/false,
  "language": "de",
  "timestamp": 1234567890
}
```

### Session Lifecycle

**Current**: 
- Speaker creates → KVS channel created
- Listener joins → tries to connect to KVS directly ❌

**Phase 3**:
- Speaker creates → KVS channel created → Backend starts consuming
- Listener joins → WebSocket only → receives processed data
- Backend reads KVS → processes → pushes via WebSocket

---

## Outstanding Issues from Phase 2

### 1. Listener Direct KVS Access (403)

**Issue**: Guest role has permissions but still denied  
**Possible Causes**:
- IAM propagation delay (unlikely after 10+ min)
- Resource-based policy on KVS channel
- Trust policy not fully propagated
- Guest role needs additional setup

**Decision**: May not need direct listener access if Phase 3 backend handles it

### 2. Session Not Found Error

Backend logs show: `SESSION_NOT_FOUND` for listener join  
**Cause**: Sessions expire or aren't found  
**Need to verify**: Session still active when listener joins

---

## Phase 3 Implementation Plan

### Step 1: KVS Stream Consumer Lambda

Create Lambda that:
- Triggered by KVS channel activity (EventBridge or polling)
- Consumes WebRTC audio stream
- Extracts PCM audio
- Feeds to transcription service

**Files to Create**:
- `session-management/lambda/kvs_stream_consumer/handler.py`
- Update CDK stack to deploy Lambda
- Grant Lambda permissions to read KVS streams

### Step 2: Transcription Integration

Connect KVS consumer to existing transcription:
- Reuse `audio-transcription/lambda/audio_processor/`
- Adapt input format (binary vs Base64)
- Stream results to WebSocket instead of returning

**Files to Modify**:
- Audio processor to accept KVS audio format
- WebSocket sender for transcription results

### Step 3: Real-Time Distribution

Send processed results to listeners:
- Query DynamoDB for session's listeners
- Filter by target language
- Send transcription + translation + emotion
- Handle connection failures gracefully

**Files to Modify**:
- Connection handler: distribute to listeners
- Listener WebSocket handlers: receive processed data

### Step 4: Testing

- Speaker streams audio → backend processes → listener receives text
- Verify latency (<2s end-to-end)
- Test multiple listeners with different languages
- Verify emotion detection works

---

## Documentation Created in Phase 2

1. `EVENTEMITTER_FIX_SOLUTION.md` - EventEmitter technical fix
2. `PHASE_2_COMPLETE.md` - Phase 2 implementation summary
3. `PHASE_2_CODE_REVIEW.md` - Code verification
4. `PHASE_2_TESTING_GUIDE.md` - Testing procedures
5. `COGNITO_POOLS_EXPLAINED.md` - User Pool vs Identity Pool
6. `CREATE_NEW_IDENTITY_POOL_GUIDE.md` - Identity Pool creation
7. `CONFIGURE_IDENTITY_POOL_ROLE.md` - Role assignment guide
8. `LISTENER_WEBSOCKET_FIX.md` - WebSocket auth fix
9. `LISTENER_TOKEN_FIX.md` - Empty token fix
10. `MANUAL_ROUTE_FIX_GUIDE.md` - API Gateway route fix
11. `GUEST_ROLE_SETUP.md` - Guest role creation

---

## Key Code References

### WebRTC Services

**KVSWebRTCService** (`frontend-client-apps/shared/services/KVSWebRTCService.ts`):
- Line 74-128: `connectAsMaster()` - Speaker connection
- Line 141-187: `connectAsViewer()` - Listener connection
- Line 194-255: `getICEServers()` - STUN/TURN configuration
- Line 256-373: `setupSignalingHandlers()` - WebRTC signaling

**KVSCredentialsProvider** (`frontend-client-apps/shared/services/KVSCredentialsProvider.ts`):
- Line 37-121: `getCredentials()` - Supports authenticated + unauthenticated
- Uses Cognito Identity Pool to exchange JWT for AWS creds

### Session Management

**HTTP Session Handler** (`session-management/lambda/http_session_handler/handler.py`):
- Creates KVS signaling channels dynamically
- Returns channel ARN and endpoints to speaker
- Session metadata includes KVS configuration

**WebSocket Connection Handler** (`session-management/lambda/connection_handler/handler.py`):
- $connect: Validates sessionId, determines role (speaker/listener)
- joinSession: Listener joins, increments count
- Control messages: pause, mute, volume, language change

---

## Phase 3 Success Criteria

### Must Have:
1. ✅ Backend consumes KVS audio streams
2. ✅ Audio transcribed in real-time
3. ✅ Transcriptions translated to target languages
4. ✅ Emotion detection from audio features
5. ✅ Results pushed to listeners via WebSocket
6. ✅ Multiple listeners with different languages supported

### Nice to Have:
- Buffering and latency optimization
- Retry and error handling
- Metrics and monitoring
- Cost optimization

---

## Expected Latency

- **Current** (Phase 2): Speaker → KVS → Listener (direct, <500ms if working)
- **Phase 3 Target**: Speaker → KVS → Backend → Process → WebSocket → Listener (~1-2s)

---

## Technical Constraints

### KVS Limitations
- WebRTC streams are ephemeral (not stored)
- Need real-time processing
- Can't replay or seek
- Opus codec standard for WebRTC audio

### Lambda Limitations
- 15-minute max execution
- May need long-running consumer
- Consider Fargate for sustained processing

### WebSocket Limitations
- 2-hour max connection duration
- Must handle reconnections
- Message size limits

---

## Recommended Phase 3 Approach

### Option A: Lambda with GetMedia (Simplest)
- Lambda polls KVS GetMedia API
- Processes audio chunks
- Sends to transcription
- Distributes results via WebSocket

### Option B: Fargate Long-Running (Production)
- ECS Fargate container consumes stream
- More stable for continuous processing
- Better for high-volume sessions

### Option C: EventBridge + Step Functions (Complex)
- Event-driven architecture
- Step Functions coordinate processing
- More AWS services involved

**Recommendation for Phase 3**: Start with Option A (Lambda), can migrate to Fargate later.

---

## Next Steps for Phase 3

1. **Design KVS consumer Lambda**
   - How to trigger (EventBridge? Polling?)
   - Audio format conversion
   - Integration with transcription service

2. **Update transcription service**
   - Accept binary audio from KVS
   - Stream results instead of batch
   - WebSocket integration

3. **Test end-to-end**
   - Speaker audio → backend processing → listener text
   - Verify all features work
   - Measure latency

---

## Questions for Phase 3

1. **KVS Consumer Architecture**: Lambda polling or Fargate long-running?
2. **Audio Format**: Keep Opus or convert to PCM for transcription?
3. **Transcription Streaming**: Real-time partial results or wait for finals?
4. **Error Handling**: What if transcription fails? Retry? Skip?
5. **Multiple Listeners**: Transcribe once, translate per language?

---

## Summary

**Phase 2 Status**: 
- ✅ Frontend WebRTC code complete
- ✅ Speaker fully working
- ✅ WebSocket working
- ⚠️ Listener KVS direct access blocked (may not be needed for Phase 3)

**Phase 3 Objective**:
Backend KVS stream consumption and audio processing pipeline

**Ready to Start**: All frontend infrastructure in place, need backend processing
