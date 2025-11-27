# Phase 3 Start Context - Consumer & Audio Processing

## Current Status

**Phase 2**: COMPLETE ✅ (Verified working Nov 27, 4:17 PM)
- Audio chunks flowing to S3: 56 chunks over 15 seconds
- kvs_stream_writer Lambda deployed and tested
- S3 bucket created with lifecycle rules
- All code committed and pushed (commit: af44acc)

**Phase 3**: READY TO START
- Goal: Read S3 chunks, process audio, enable listener playback
- Reference: PHASE3_LISTENER_S3_PLAYBACK_GUIDE.md

---

## What's Working Now (Phase 2)

### Frontend
- **AudioStreamService.ts** - MediaRecorder wrapper working
  - Captures 16kHz mono audio
  - 250ms chunks in WebM/Opus format
  - Base64 encoding for WebSocket
  - ~4-5 KB per chunk

### Backend Audio Flow
```
Speaker Browser (MediaRecorder)
  ↓ WebSocket audioChunk messages
connection_handler Lambda ✅
  ↓ Async invoke
kvs_stream_writer Lambda ✅
  ↓ Decode base64
  ↓ Write to S3
S3 Bucket ✅
  ↓ sessions/{sessionId}/chunks/{timestamp}.webm
  ↓ 56 chunks = ~15 seconds of audio
```

### S3 Storage
- **Bucket:** low-latency-audio-dev
- **Path pattern:** sessions/{sessionId}/chunks/{timestamp}.webm
- **Chunk size:** ~550 bytes each
- **Lifecycle:** Auto-delete after 1 day
- **Verified:** 56 chunks successfully stored

---

## Phase 3 Goal

Implement audio consumption and playback for listeners:

1. **Read S3 chunks** - Aggregate chunks for a session
2. **Reassemble audio** - Concatenate WebM chunks into complete stream
3. **Convert to PCM** - Use ffmpeg on complete stream
4. **Process audio** - Forward to audio_processor for transcription
5. **Enable playback** - Send processed audio to listeners

---

## Key Technical Decisions from Phase 2

### Decision: S3 Instead of KVS Streams

**Why Changed:**
- MediaRecorder chunks lack complete WebM headers
- Individual chunks cannot be processed by ffmpeg
- KVS PutMedia API requires streaming connection (complex)
- S3 provides simpler chunk storage

**Impact on Phase 3:**
- Consumer must read from S3 (not KVS GetMedia)
- Concatenate chunks before conversion
- ffmpeg processes complete stream (not individual chunks)

### Decision: No Real-Time Conversion

**Why:**
- Individual chunks are streaming fragments
- Conversion requires complete audio stream
- Batching chunks adds slight latency but ensures quality

**Phase 3 Approach:**
- Aggregate chunks every 2-5 seconds
- Convert batches to PCM
- Forward to transcription pipeline

---

## Critical Issue to Address in Phase 3

### FFmpeg Binary in Git (76 MB)

**Problem:**
```
remote: warning: File session-management/lambda_layers/ffmpeg/bin/ffmpeg is 76.23 MB
remote: warning: GH001: Large files detected.
```

**Solutions for Phase 3:**

**Option 1: Add to .gitignore** (RECOMMENDED)
```bash
echo "session-management/lambda_layers/ffmpeg/bin/ffmpeg" >> .gitignore
git rm --cached session-management/lambda_layers/ffmpeg/bin/ffmpeg
```

**Option 2: Download during deployment**
- Add script to download ffmpeg before CDK deploy
- Document in deployment steps

**Option 3: Use public Lambda layer**
- Revert to external ffmpeg layer
- Document ARN in infrastructure

**Recommended:** Option 1 + deployment script

---

## Phase 3 Architecture

```
S3 Bucket (low-latency-audio-dev)
  ↓ S3 event notification (new object)
  ↓
S3 Event Consumer Lambda (NEW - Phase 3)
  ↓ List all chunks for session
  ↓ Aggregate chunks (2-5 second batches)
  ↓ Concatenate WebM fragments
  ↓ ffmpeg: Complete WebM → PCM
  ↓ Invoke audio_processor
  ↓
audio_processor Lambda (existing)
  ↓ Transcribe (AWS Transcribe Streaming)
  ↓ Translate (AWS Translate)
  ↓ Text-to-Speech (AWS Polly)
  ↓ Upload translated audio to S3
  ↓
Listener Playback
  ↓ Fetch audio from S3
  ↓ Play via HTML5 Audio
```

---

## Files to Create (Phase 3)

### 1. S3 Event Consumer Lambda
`session-management/lambda/s3_audio_consumer/handler.py`
- Triggered by S3 events (new chunk uploaded)
- Aggregates chunks for session
- Concatenates WebM fragments
- Converts to PCM using ffmpeg
- Forwards to audio_processor

### 2. Update CDK Stack
`session-management/infrastructure/stacks/session_management_stack.py`
- Add S3 event notification
- Create s3_audio_consumer Lambda
- Grant S3 read permissions
- Add ffmpeg layer to consumer
- Wire to audio_processor

### 3. FFmpeg Handling
- Add .gitignore entry
- Create deployment script to download ffmpeg
- Document setup in Phase 3

### 4. Tests
`session-management/tests/test_s3_audio_consumer.py`

---

## Current Deployment State

### Lambda Functions
- session-authorizer-dev ✅
- session-connection-handler-dev ✅
- kvs-stream-writer-dev ✅ (writes to S3)
- kvs-stream-consumer-dev ⚠️ (exists but not wired for S3)

### S3 Bucket
- low-latency-audio-dev ✅
- Lifecycle: 1 day
- Public access: blocked
- Encryption: S3-managed

### DynamoDB Tables
- Sessions-dev ✅
- Connections-dev ✅
- RateLimits-dev ✅

### WebSocket API
- Endpoint: wss://2y19uvhyq5.execute-api.us-east-1.amazonaws.com/prod
- Deployment: qfqdg7 (active)
- Routes: audioChunk ✅, createSession, joinSession, etc.

---

## Phase 3 Implementation Steps

### Step 1: Fix FFmpeg in Git
1. Add ffmpeg to .gitignore
2. Remove from git cache
3. Create download script
4. Update deployment docs

### Step 2: Implement S3 Consumer
1. Read PHASE3_LISTENER_S3_PLAYBACK_GUIDE.md
2. Create s3_audio_consumer Lambda
3. Implement chunk aggregation logic
4. Add WebM concatenation
5. Convert complete stream to PCM
6. Forward to audio_processor

### Step 3: Configure S3 Events
1. Add S3 event notification to CDK
2. Trigger on new .webm objects
3. Filter by sessions/ prefix
4. Invoke s3_audio_consumer

### Step 4: Wire to Audio Pipeline
1. Ensure audio_processor accepts PCM input
2. Configure transcription settings
3. Test translation flow
4. Verify TTS output

### Step 5: Listener Playback
1. Implement S3 presigned URLs
2. Add playback endpoint for listeners
3. Test audio delivery
4. Verify end-to-end flow

---

## Testing Strategy (Phase 3)

### Unit Tests
- Test chunk aggregation logic
- Test WebM concatenation
- Test ffmpeg conversion on complete stream
- Mock S3 events

### Integration Tests
1. Run speaker app (15 seconds)
2. Verify S3 consumer triggered
3. Check audio_processor invoked
4. Verify transcription created
5. Check translation generated
6. Verify TTS audio in S3
7. Test listener playback

### Verification Commands
```bash
# Check S3 consumer logs
./scripts/tail-lambda-logs.sh s3-audio-consumer-dev

# List processed audio
aws s3 ls s3://low-latency-audio-dev/processed/${SESSION_ID}/

# Test listener playback
curl https://{listener-endpoint}/audio/${SESSION_ID}/en
```

---

## Known Challenges (Phase 3)

### 1. WebM Chunk Concatenation
- Chunks are fragments without headers
- Need to reconstruct valid WebM container
- May need mkvmerge or custom logic

### 2. Timing and Latency
- Batch size affects latency
- Too small: frequent invocations, incomplete audio
- Too large: higher latency
- Target: 2-3 second batches

### 3. FFmpeg Binary Management
- 76 MB binary too large for git
- Need deployment-time download
- Consider Lambda layer vs in-function

### 4. Audio Quality
- Ensure no audio degradation
- Maintain 16kHz mono quality
- Test with various languages

---

## Performance Targets (Phase 3)

- **Chunk aggregation:** < 100ms
- **WebM concatenation:** < 500ms
- **PCM conversion:** < 2 seconds per batch
- **Total latency:** 3-5 seconds (speaker → listener)
- **Throughput:** 100 concurrent sessions

---

## Success Criteria (Phase 3)

Phase 3 is complete when:
- [x] S3 event triggers consumer Lambda
- [x] Chunks aggregated correctly
- [x] Complete WebM stream created
- [x] PCM conversion successful
- [x] audio_processor receives PCM
- [x] Transcription works
- [x] Translation works
- [x] TTS audio generated
- [x] Listeners can play audio
- [x] End-to-end flow verified
- [x] FFmpeg not in git repository

---

## Environment Details

### AWS Account
- Region: us-east-1
- Account: 193020606184

### Endpoints (Current)
- WebSocket: wss://2y19uvhyq5.execute-api.us-east-1.amazonaws.com/prod
- HTTP API: https://gcneupzdtf.execute-api.us-east-1.amazonaws.com

### S3 Buckets
- low-latency-audio-dev (chunks)
- [Need to create: processed audio bucket]

### Cognito
- User Pool: us-east-1_WoaXmyQLQ
- Client ID: 38t8057tbi0o6873qt441kuo3n

---

## Quick Reference: Phase 2 Lessons

### What Worked Well
✅ S3 for chunk storage (simple, reliable)
✅ Async Lambda invocation (no WebSocket blocking)
✅ Base64 encoding for WebSocket transport
✅ Timestamp-based chunk naming

### What Didn't Work
❌ Individual chunk ffmpeg conversion (incomplete headers)
❌ KVS PutMedia with fragments (too complex)
❌ FFmpeg binary in git (76 MB, too large)

### Carry Forward to Phase 3
- Keep S3-based storage
- Process complete streams (not fragments)
- Download ffmpeg during deployment
- Batch processing for efficiency

---

## Next Steps

1. Create new task for Phase 3
2. Address ffmpeg binary in git
3. Follow PHASE3_LISTENER_S3_PLAYBACK_GUIDE.md
4. Implement S3 consumer with aggregation
5. Wire to audio_processor
6. Test with speaker + listener apps
7. Verify full translation pipeline

**All Phase 2 work committed and pushed!** (Note: ffmpeg binary should be removed from git in Phase 3)

---

## Related Documents

- `PHASE2_START_CONTEXT.md` - What led to Phase 2
- `PHASE2_BACKEND_KVS_WRITER_GUIDE.md` - Original implementation guide
- `CHECKPOINT_PHASE2_COMPLETE.md` - What Phase 2 delivered
- `PHASE3_LISTENER_S3_PLAYBACK_GUIDE.md` - Next implementation guide
- `CHECKPOINT_PHASE1_COMPLETE.md` - MediaRecorder implementation
- `ARCHITECTURE_DECISIONS.md` - Why we chose this approach
