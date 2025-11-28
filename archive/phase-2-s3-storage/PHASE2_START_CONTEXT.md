# Phase 2 Start Context - Backend KVS Writer

## Current Status

**Phase 1**: COMPLETE ✅ (Verified working Nov 27, 10:02 AM)
- MediaRecorder audio capture working
- WebSocket authentication resolved (4 bugs fixed)
- Audio chunks flowing: 90+ chunks over 30 seconds
- All code committed and pushed

**Phase 2**: READY TO START
- Goal: Create kvs_stream_writer Lambda to process audio chunks
- Reference: PHASE2_BACKEND_KVS_WRITER_GUIDE.md (600+ lines, copy-paste ready)

---

## What's Working Now (Phase 1)

### Frontend
- **AudioStreamService.ts** (302 lines) - MediaRecorder wrapper
  - Captures 16kHz mono audio
  - 250ms chunks in WebM/Opus format
  - Base64 encoding for WebSocket
  - ~4-5 KB per chunk

### Backend
- **Connection established** - JWT validation working
- **Audio routing** - connection_handler receives audioChunk messages
- **Async invocation** - Forwards to kvs_stream_writer (doesn't exist yet)

### Current Flow
```
Speaker Browser (MediaRecorder)
  ↓ WebSocket audioChunk messages
connection_handler Lambda ✅
  ↓ Async invoke (fails silently)
kvs_stream_writer Lambda ❌ MISSING - Phase 2 goal
```

---

## Phase 2 Goal

Create `kvs_stream_writer` Lambda to:
1. Receive base64 WebM chunks from connection_handler
2. Convert WebM → PCM using ffmpeg
3. Write PCM to Kinesis Video Stream using PutMedia API
4. Manage KVS stream lifecycle (create on-demand, 1hr retention)
5. Handle errors and retries

---

## Key Implementation Details

### Input Format (from Phase 1)
```json
{
  "action": "writeToStream",
  "sessionId": "sacred-apostle-367",
  "audioData": "GkXfo59ChoEBQveBAULygQRC84EIQoKE...",
  "timestamp": 1732622783456,
  "format": "webm-opus",
  "chunkIndex": 42
}
```

### Output Requirements
- PCM audio: 16kHz, mono, 16-bit
- KVS Stream name: `session-{sessionId}`
- Retention: 1 hour
- Fragment duration: ~2 seconds

### Technical Requirements

**Lambda Configuration:**
- Runtime: Python 3.11
- Memory: 1024 MB (for ffmpeg)
- Timeout: 60 seconds
- Layers: ffmpeg layer (for WebM → PCM)

**Permissions Needed:**
- kinesisvideo:CreateStream
- kinesisvideo:DescribeStream
- kinesisvideo:PutMedia
- kinesisvideo:GetDataEndpoint
- dynamodb:GetItem (Sessions table - for validation)

**Environment Variables:**
- SESSIONS_TABLE: Sessions-dev
- AWS_REGION: us-east-1
- KVS_RETENTION_HOURS: 1

---

## Dependencies from Phase 1

### What Phase 2 Receives
✅ Base64 WebM chunks every 250ms
✅ SessionId in each chunk
✅ Async Lambda invocation configured
✅ Connection validated (speaker role)

### What Phase 2 Needs to Provide
- ❌ ffmpeg conversion (WebM → PCM)
- ❌ KVS stream creation/management
- ❌ PutMedia API client
- ❌ Fragment assembly
- ❌ Error handling

---

## Architecture After Phase 2

```
Speaker Browser (MediaRecorder)
  ↓ WebSocket (250ms WebM chunks)
connection_handler Lambda
  ↓ Async invoke
kvs_stream_writer Lambda (NEW)
  ↓ ffmpeg: WebM → PCM
  ↓ Buffer: ~2 seconds
  ↓ PutMedia API
KVS Stream
  ↓ EventBridge (on new fragments)
kvs_stream_consumer Lambda (Phase 3)
  ↓ GetMedia API
  ↓ Audio processor
Translation pipeline...
```

---

## Files to Create (Phase 2)

### Lambda Function
`session-management/lambda/kvs_stream_writer/handler.py` (~400 lines)

### Lambda Layer
`session-management/lambda_layers/ffmpeg/` - Pre-compiled ffmpeg binary

### Infrastructure
Update `session-management/infrastructure/stacks/session_management_stack.py`:
- Add kvs_stream_writer Lambda
- Add ffmpeg layer
- Grant KVS permissions
- Wire environment variables

### Tests
`session-management/tests/test_kvs_stream_writer.py` - Unit tests

---

## Current Deployment

### API Gateway WebSocket
- Endpoint: `wss://2y19uvhyq5.execute-api.us-east-1.amazonaws.com/prod`
- Deployment: `eyvcga` (active)
- Authorizer: Working
- Connection records: Created during $connect

### Lambda Functions
- session-authorizer-dev: Validates JWT ✅
- session-connection-handler-dev: Routes audioChunk ✅
- kvs-stream-writer-dev: **DOES NOT EXIST** - Phase 2 goal

### DynamoDB Tables
- Sessions-dev: Stores session metadata
- Connections-dev: Stores active connections

---

## Testing Strategy (Phase 2)

### Unit Tests
- Test WebM → PCM conversion
- Test KVS stream creation
- Test PutMedia API calls
- Test error handling

### Integration Tests
1. Deploy kvs_stream_writer Lambda
2. Run Phase 1 speaker app
3. Verify audio chunks processed
4. Check KVS stream contains fragments
5. Verify CloudWatch logs show success

### Verification Commands
```bash
# Check Lambda logs
./scripts/tail-lambda-logs.sh kvs-stream-writer-dev

# List KVS streams
aws kinesisvideo list-streams

# Describe specific stream
aws kinesisvideo describe-stream --stream-name session-{sessionId}
```

---

## Known Challenges (Phase 2)

### 1. ffmpeg in Lambda
- Need pre-compiled binary
- Lambda Layer size limits (250 MB unzipped)
- Solution: Use minimal ffmpeg build with only opus codec

### 2. PutMedia API
- Requires chunked transfer encoding
- Fragment headers must be correct
- Need to handle connection drops

### 3. Buffer Management
- Must accumulate ~2 seconds before writing fragment
- Handle first fragment (smaller)
- Handle final fragment (flush remaining)

### 4. Error Recovery
- Retry transient KVS errors
- Log permanently failed chunks
- Don't block subsequent chunks

---

## Success Criteria (Phase 2)

Phase 2 is complete when:
- [x] kvs_stream_writer Lambda deployed
- [x] Receives audioChunk events from connection_handler
- [x] Converts WebM → PCM successfully
- [x] Creates KVS streams on-demand
- [x] Writes fragments to KVS
- [x] CloudWatch shows successful processing
- [x] KVS stream viewable in AWS Console
- [x] No errors in Lambda execution
- [x] Audio quality maintained

---

## Time Estimate

**Estimated Duration**: 6-8 hours
- Lambda implementation: 3-4 hours
- ffmpeg layer setup: 1-2 hours  
- Testing & debugging: 2-3 hours

**Based on Phase 1 Experience**:
- Code implementation: Usually fast with guide
- Debugging: Can take longer if issues arise
- Infrastructure: CDK deployment usually smooth

---

## Quick Start (Phase 2)

1. **Read the guide**: PHASE2_BACKEND_KVS_WRITER_GUIDE.md
2. **Copy Lambda code**: handler.py is ready in guide
3. **Setup ffmpeg layer**: Download pre-built or compile
4. **Update CDK**: Add Lambda definition to stack
5. **Deploy**: `cd session-management && make deploy-websocket-dev`
6. **Test**: Run Phase 1 speaker app, check logs

---

## Reference Documents

### Phase 2 Implementation
- `PHASE2_BACKEND_KVS_WRITER_GUIDE.md` - Complete implementation guide

### Phase 1 Status
- `CHECKPOINT_PHASE1_COMPLETE.md` - What's working
- `WEBSOCKET_DEBUGGING_COMPLETE.md` - How we fixed WebSocket issues

### Architecture
- `ARCHITECTURE_DECISIONS.md` - Why Traditional KVS architecture

---

## Environment

### AWS Account
- Region: us-east-1
- Account: 193020606184

### Endpoints (Current)
- WebSocket API: wss://2y19uvhyq5.execute-api.us-east-1.amazonaws.com/prod
- HTTP API: https://gcneupzdtf.execute-api.us-east-1.amazonaws.com

### Cognito (For Testing)
- User Pool: us-east-1_WoaXmyQLQ
- Client ID: 38t8057tbi0o6873qt441kuo3n

---

## Next Steps

1. Start new task for Phase 2
2. Follow PHASE2_BACKEND_KVS_WRITER_GUIDE.md
3. Test with Phase 1 speaker app
4. Verify KVS streams created
5. Proceed to Phase 3 (listener S3 playback)

**All Phase 1 work committed and pushed to main branch!**
