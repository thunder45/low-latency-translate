# Architecture Decisions - Traditional KVS Stream Implementation

## Document Purpose
This is the **SINGLE SOURCE OF TRUTH** for the Low-Latency Translation project architecture. If context is lost or confusion arises, refer to this document first.

## Last Updated
**Date:** November 26, 2025  
**Status:** ✅ APPROVED - Ready for implementation  
**Progress:** Phase 0 (Cleanup & Planning)

---

## Critical Decision: Traditional KVS Stream Architecture

### Decision Date: November 26, 2025

### Problem Identified
Previous WebRTC implementation had audio flowing peer-to-peer between browsers, completely bypassing the backend translation pipeline. No translation was actually happening.

### Solution Chosen: Traditional KVS Stream (Option 3)

**Rationale:**
- ✅ **Simplicity**: Standard browser APIs, no complex media servers
- ✅ **Cost-effective**: ~$0.01 per stream-hour (pay-per-use)
- ✅ **Low maintenance**: AWS-managed, no servers to maintain
- ✅ **Existing code**: kvs_stream_consumer already designed for this
- ✅ **Acceptable latency**: 3-4s total (translation use case)
- ✅ **No original audio needed**: Listeners only need translated audio

**Rejected Alternatives:**
- ❌ Dual-Path (WebRTC + Backend): Unnecessary complexity, original audio not needed
- ❌ Janus Media Server: Expensive, complex, high maintenance burden

---

## Complete Architecture Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    SPEAKER BROWSER                          │
│                                                             │
│  1. getUserMedia() → Microphone access                     │
│  2. MediaRecorder → Capture audio                          │
│     - Format: WebM (Opus codec)                            │
│     - Chunk size: 250ms                                    │
│     - Sample rate: 16kHz mono                              │
│     - Bitrate: 16kbps (low for streaming)                  │
│  3. Convert to base64                                      │
│  4. Send via WebSocket                                     │
│                                                             │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓ WebSocket (wss://)
                   │ Action: 'audioChunk'
                   │ Payload: { sessionId, audioData, timestamp }
                   │
┌──────────────────┴──────────────────────────────────────────┐
│              BACKEND: kvs_stream_writer Lambda              │
│                                                             │
│  1. Receive WebM chunk (base64)                            │
│  2. Decode base64 → binary WebM                            │
│  3. Convert WebM → PCM using ffmpeg                        │
│     - Format: PCM 16-bit signed little-endian              │
│     - Sample rate: 16kHz                                   │
│     - Channels: 1 (mono)                                   │
│  4. Write to KVS Stream via PutMedia API                   │
│     - Stream name: session-{sessionId}                     │
│     - Continuous streaming                                 │
│                                                             │
│  Latency: ~250ms (decode + convert + upload)               │
│                                                             │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓ KVS PutMedia
                   │
┌──────────────────┴──────────────────────────────────────────┐
│                  KVS STREAM (AWS Service)                   │
│                                                             │
│  - Stream name: session-{sessionId}                        │
│  - Stores audio fragments                                  │
│  - Retention: 1 hour (no long-term recording)              │
│  - Can query fragments: aws kinesisvideo list-fragments    │
│                                                             │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓ EventBridge Event
                   │ Event: "KVS Fragment Ready"
                   │
┌──────────────────┴──────────────────────────────────────────┐
│           BACKEND: kvs_stream_consumer Lambda               │
│                                                             │
│  1. Triggered by EventBridge when fragments ready          │
│  2. GetMedia from KVS Stream                               │
│  3. Extract PCM audio chunks                               │
│  4. Invoke audio_processor Lambda (async)                  │
│     - Pass PCM data                                        │
│     - Session metadata                                     │
│                                                             │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓ Lambda Invocation (async)
                   │
┌──────────────────┴──────────────────────────────────────────┐
│            BACKEND: audio_processor Lambda                  │
│                                                             │
│  1. Receive PCM audio chunk                                │
│  2. Transcribe Streaming API                               │
│     - Real-time speech-to-text                             │
│     - Language: Source language from session               │
│     - Latency: 1-2 seconds                                 │
│  3. AWS Translate API (per target language)                │
│     - Translate transcribed text                           │
│     - Multiple target languages in parallel                │
│     - Latency: ~500ms per language                         │
│  4. Amazon Polly TTS                                       │
│     - Generate speech from translated text                 │
│     - 2-second audio chunks (MP3)                          │
│     - Latency: ~1 second                                   │
│  5. Store in S3                                            │
│     - Bucket: translation-audio-{stage}                    │
│     - Key: sessions/{sessionId}/translated/{lang}/{ts}.mp3 │
│     - Lifecycle: Delete after 24 hours                     │
│  6. Generate presigned URL (10-minute expiration)          │
│  7. Send URL to listeners via WebSocket                    │
│                                                             │
│  Total processing latency: 2-3 seconds                     │
│                                                             │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓ WebSocket notification
                   │ Message: { type: 'translatedAudio', url, duration }
                   │
┌──────────────────┴──────────────────────────────────────────┐
│                  LISTENER BROWSER (per language)            │
│                                                             │
│  1. Receive WebSocket notification                         │
│  2. Parse S3 presigned URL                                 │
│  3. Download MP3 chunk from S3                             │
│     - Latency: ~100ms                                      │
│  4. Add to playback queue                                  │
│  5. Play audio (HTMLAudioElement)                          │
│  6. Prefetch next chunk while playing                      │
│                                                             │
│  Buffering: 2-3 chunks ahead for smooth playback           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Technical Specifications

### Audio Formats at Each Stage

| Stage | Format | Sample Rate | Channels | Bitrate | Encoding |
|-------|--------|-------------|----------|---------|----------|
| Browser Capture | WebM (Opus) | 16kHz | Mono | 16kbps | Opus |
| KVS Stream | PCM | 16kHz | Mono | 256kbps | s16le |
| Transcribe Input | PCM | 16kHz | Mono | 256kbps | s16le |
| TTS Output | MP3 | 24kHz | Mono | 64kbps | MP3 |
| Listener Playback | MP3 | 24kHz | Mono | 64kbps | MP3 |

### Chunk Sizes

| Component | Chunk Duration | Typical Size | Rationale |
|-----------|---------------|--------------|-----------|
| MediaRecorder | 250ms | ~4-5 KB | Fast capture, low latency |
| KVS Stream | 250ms | ~8 KB PCM | Matches input chunks |
| TTS Output | 2 seconds | ~32 KB | Balance download time vs smoothness |
| Listener Buffer | 3 chunks | ~96 KB | Smooth playback with prefetch |

### Latency Budget

| Stage | Target Latency | Notes |
|-------|----------------|-------|
| Browser Capture | 100ms | MediaRecorder internal buffering |
| Upload to Backend | 200ms | WebSocket + network |
| Format Conversion | 50ms | ffmpeg WebM → PCM |
| KVS Ingestion | 200ms | PutMedia API |
| Transcribe | 1-2s | Streaming with partial results |
| Translate | 500ms | Per language, parallelized |
| TTS | 1s | Polly synthesis |
| S3 Upload | 100ms | Store MP3 chunk |
| Download to Listener | 100ms | Presigned URL fetch |
| **Total End-to-End** | **3-4s** | ✅ Acceptable |

---

## Key Requirements (User Confirmed)

### Speaker App:
- ✅ **Lightweight browser**: MediaRecorder only, no format conversion
- ✅ **WebM upload**: Let backend handle conversion
- ✅ **250ms chunks**: Small for low latency
- ✅ **No peer-to-peer**: Backend processing only

### Listener App:
- ✅ **S3-only delivery**: No WebSocket audio streaming
- ✅ **Small S3 chunks**: 2-second segments for low download latency
- ✅ **Presigned URLs**: 10-minute expiration
- ✅ **Auto-cleanup**: No long-term storage

### Backend:
- ✅ **Format conversion**: WebM → PCM in Lambda
- ✅ **Traditional KVS Stream**: Not WebRTC Signaling Channel
- ✅ **Process and discard**: No session recording
- ✅ **Multi-language support**: Parallel translation

---

## Components to REMOVE

### From Speaker App:
- ❌ `KVSWebRTCService` - WebRTC peer connection logic
- ❌ `getKVSCredentialsProvider` usage for WebRTC
- ❌ ICE candidate handling
- ❌ Peer connection management
- ❌ Master role logic

### From Listener App:
- ❌ `KVSWebRTCService` - WebRTC viewer logic
- ❌ `getKVSCredentialsProvider` usage for WebRTC
- ❌ Remote track handling
- ❌ Viewer role logic
- ❌ `waitForSpeakerReady()` - Not needed with traditional KVS

### From Backend:
- ❌ WebRTC-specific EventBridge rules (keep KVS Stream rules)
- ⚠️ `kvs_stream_consumer` - Keep but refactor (remove WebRTC assumptions)

### Documentation:
- ✅ Already archived in `archive/webrtc-architecture/`

---

## Components to ADD

### Frontend (Speaker):
1. **AudioStreamService.ts** (NEW)
   - MediaRecorder implementation
   - 250ms chunking
   - WebM/Opus capture
   - WebSocket streaming

### Backend:
2. **kvs_stream_writer Lambda** (NEW)
   - Receives WebM chunks via WebSocket
   - Converts WebM → PCM (ffmpeg)
   - Writes to KVS Stream (PutMedia)
   - Creates streams on-demand

3. **EventBridge Rule** (NEW)
   - Trigger: KVS Stream fragment ready
   - Target: kvs_stream_consumer Lambda
   - Pattern: Traditional stream events (not WebRTC)

4. **S3 Bucket** (NEW or reuse existing)
   - Stores TTS chunks
   - Lifecycle: Delete after 24 hours
   - CORS: Allow listener origin

### Frontend (Listener):
5. **S3AudioPlayer.ts** (NEW)
   - Downloads MP3 chunks from S3
   - Buffers 2-3 chunks ahead
   - Handles language-specific streams
   - Auto-cleanup

---

## Implementation Phases

### Phase 0: Cleanup & Blueprints ⏳ (Current)
- Archive obsolete WebRTC docs
- Create implementation guides
- Update verification scripts

### Phase 1: Speaker MediaRecorder (Day 1)
- Replace WebRTC with MediaRecorder
- Implement audio streaming via WebSocket
- Test chunks reach backend

### Phase 2: Backend KVS Writer (Day 2)
- Create kvs_stream_writer Lambda
- Implement format conversion
- Write to KVS Stream
- Verify fragments exist

### Phase 3: Translation Pipeline (Day 3)
- Connect kvs_stream_consumer → audio_processor
- Implement S3 chunk storage
- Add listener S3 player
- Test end-to-end translation

### Phase 4: Testing & Polish (Day 4)
- Measure latency
- Test multi-listener
- Add error handling
- Verify quality

### Phase 5: UI & Monitoring (Week 2-3)
- Session ID display
- Status indicators
- Error notifications
- CloudWatch metrics

---

## AWS Resources Required

### Already Exist:
- ✅ DynamoDB: Sessions table, Connections table
- ✅ Lambda: connection_handler, disconnect_handler, audio_processor
- ✅ API Gateway: WebSocket API, HTTP API
- ✅ Cognito: User Pool, Identity Pool
- ✅ IAM: Various roles

### Need to Create:
- 🆕 Lambda: kvs_stream_writer
- 🆕 Lambda Layer: ffmpeg (for audio conversion)
- 🆕 S3 Bucket: translation-audio-{stage}
- 🆕 EventBridge Rule: KVS Stream → kvs_stream_consumer
- 🆕 WebSocket Route: audioChunk action

### Need to Modify:
- 🔧 kvs_stream_consumer: Remove WebRTC assumptions, fix numpy
- 🔧 audio_processor: Add S3 storage for TTS chunks
- 🔧 WebSocket API: Add audioChunk route

---

## Data Flow Details

### 1. Speaker → Backend (Audio Upload)

**WebSocket Message Format:**
```json
{
  "action": "audioChunk",
  "sessionId": "joyful-hope-911",
  "audioData": "base64_encoded_webm_data...",
  "timestamp": 1732614567890,
  "format": "webm-opus",
  "chunkIndex": 42
}
```

**Size:** ~4-5 KB per 250ms chunk = ~16-20 KB/second

### 2. Backend → KVS Stream (PutMedia)

**PCM Format:**
- Encoding: PCM signed 16-bit little-endian
- Sample rate: 16000 Hz
- Channels: 1 (mono)
- Bitrate: 256 kbps
- Size: ~8 KB per 250ms chunk

### 3. Backend → Listener (Translated Audio)

**WebSocket Message Format:**
```json
{
  "type": "translatedAudio",
  "sessionId": "joyful-hope-911",
  "targetLanguage": "es",
  "url": "https://s3.../sessions/joyful-hope-911/translated/es/1732614570.mp3?X-Amz-...",
  "timestamp": 1732614570000,
  "duration": 2.0,
  "sequenceNumber": 15
}
```

**S3 Object:**
- Format: MP3
- Duration: 2 seconds
- Size: ~32 KB
- Expiration: 10 minutes (presigned URL)
- Lifecycle: Delete after 24 hours

---

## Error Handling Strategy

### Speaker App:
- WebSocket disconnect → Retry 3 times with backoff
- MediaRecorder failure → Display error, retry microphone access
- Chunk send failure → Buffer locally, retry on reconnect

### Backend:
- WebM conversion failure → Log error, skip chunk, continue
- KVS PutMedia failure → Retry 3 times, then alert
- Transcribe failure → Log error, notify speaker
- S3 upload failure → Retry 3 times, then skip chunk

### Listener App:
- S3 download failure → Retry 3 times, display buffering indicator
- Playback failure → Skip chunk, continue with next
- WebSocket disconnect → Show disconnected status, attempt reconnect

---

## Monitoring & Metrics

### CloudWatch Metrics:
- `AudioChunksReceived` (kvs_stream_writer)
- `KVSStreamFragments` (KVS Stream)
- `AudioChunksProcessed` (kvs_stream_consumer)
- `TranscriptionLatency` (audio_processor)
- `TranslationLatency` (audio_processor)
- `TTSLatency` (audio_processor)
- `S3DownloadLatency` (listener client-side)
- `EndToEndLatency` (full pipeline)

### CloudWatch Alarms:
- End-to-end latency > 5 seconds
- kvs_stream_writer errors > 5%
- audio_processor errors > 5%
- S3 download failures > 10%

---

## Security Considerations

### Speaker Authentication:
- Cognito User Pool (authenticated users only)
- JWT token for WebSocket connection
- IAM role: Can write to KVS Streams

### Listener Authentication:
- Cognito Identity Pool (guest/unauthenticated)
- Anonymous access to WebSocket
- IAM role: Can read from S3 (presigned URLs only)

### Data Protection:
- WebSocket: TLS (wss://)
- S3: Presigned URLs with 10-minute expiration
- KVS Stream: Encrypted at rest
- No long-term storage: Auto-delete after 24 hours

---

## Scalability Targets

### Current Phase (MVP):
- Sessions: 10 concurrent
- Listeners: 50 per session
- Languages: 10 supported
- Latency: 3-4 seconds

### Future Scale:
- Sessions: 100 concurrent
- Listeners: 500 per session
- Languages: 20 supported
- Latency: < 3 seconds

---

## Testing Strategy

### Unit Tests:
- AudioStreamService (MediaRecorder)
- kvs_stream_writer (format conversion)
- S3AudioPlayer (download queue)

### Integration Tests:
- Speaker → kvs_stream_writer → KVS Stream
- KVS Stream → kvs_stream_consumer → audio_processor
- audio_processor → S3 → Listener

### E2E Tests:
- Single listener scenario
- Multiple listeners (same language)
- Multiple listeners (different languages)
- Error scenarios (network loss, service failures)

### Load Tests:
- 10 concurrent sessions
- 50 listeners per session
- Measure latency at scale

---

## Rollback Plan

If implementation fails:
1. Keep current WebSocket + HTTP API (working)
2. Disable new Lambda functions
3. Restore WebRTC code from git history if needed
4. No data loss (no permanent storage)

---

## Success Criteria

### Phase 1 Success:
- ✅ MediaRecorder captures audio
- ✅ Chunks sent via WebSocket
- ✅ kvs_stream_writer receives chunks

### Phase 2 Success:
- ✅ KVS Stream has fragments (verifiable via AWS CLI)
- ✅ kvs_stream_consumer triggered by EventBridge
- ✅ PCM audio extracted correctly

### Phase 3 Success:
- ✅ Listener receives translated audio within 4 seconds
- ✅ Audio quality is good
- ✅ Multiple languages work simultaneously

### Phase 4 Success:
- ✅ End-to-end latency measured
- ✅ System handles 10+ listeners
- ✅ Error recovery works

---

## Configuration Changes

### Environment Variables:

**kvs_stream_writer Lambda:**
```bash
STAGE=dev
SESSIONS_TABLE_NAME=low-latency-sessions-dev
KVS_STREAM_RETENTION_HOURS=1
```

**audio_processor Lambda:**
```bash
STAGE=dev
S3_BUCKET_NAME=translation-audio-dev
PRESIGNED_URL_EXPIRATION=600  # 10 minutes
TTS_CHUNK_DURATION=2  # seconds
```

**Frontend Apps:**
```javascript
VITE_WS_URL=wss://...
VITE_HTTP_API_URL=https://...
VITE_COGNITO_USER_POOL_ID=...
VITE_COGNITO_IDENTITY_POOL_ID=...
VITE_AWS_REGION=us-east-1
```

---

## Critical Files Reference

### Frontend (Speaker):
- `frontend-client-apps/speaker-app/src/services/AudioStreamService.ts` (NEW)
- `frontend-client-apps/speaker-app/src/services/SpeakerService.ts` (MODIFY)

### Frontend (Listener):
- `frontend-client-apps/listener-app/src/services/S3AudioPlayer.ts` (NEW)
- `frontend-client-apps/listener-app/src/services/ListenerService.ts` (MODIFY)

### Backend:
- `session-management/lambda/kvs_stream_writer/handler.py` (NEW)
- `session-management/lambda/kvs_stream_consumer/handler.py` (MODIFY)
- `audio-transcription/lambda/audio_processor/handler.py` (MODIFY)

### Infrastructure:
- `session-management/infrastructure/stacks/session_management_stack.py` (MODIFY)
- `audio-transcription/infrastructure/stacks/audio_stack.py` (MODIFY)

### Documentation (Master):
- `ARCHITECTURE_DECISIONS.md` (THIS FILE)
- `PHASE1_SPEAKER_MEDIARECORDER_GUIDE.md`
- `PHASE2_BACKEND_KVS_WRITER_GUIDE.md`
- `PHASE3_LISTENER_S3_PLAYBACK_GUIDE.md`

---

## Quick Reference Commands

```bash
# Verify KVS Stream exists and has fragments
aws kinesisvideo describe-stream \
  --stream-name session-{sessionId} \
  --region us-east-1

aws kinesisvideo list-fragments \
  --stream-name session-{sessionId} \
  --region us-east-1 \
  --max-results 10

# Tail Lambda logs
./scripts/tail-lambda-logs.sh kvs-stream-writer-dev
./scripts/tail-lambda-logs.sh kvs-stream-consumer-dev
./scripts/tail-lambda-logs.sh audio-processor-dev

# Check S3 for translated audio
aws s3 ls s3://translation-audio-dev/sessions/{sessionId}/translated/

# Test Lambda functions
aws lambda invoke \
  --function-name kvs-stream-writer-dev \
  --payload '{"action":"health_check"}' \
  response.json

# Deploy infrastructure
cd session-management && make deploy
cd audio-transcription && make deploy
```

---

## Decision Log

### Nov 26, 2025 - Initial Architecture Decision
- **Decision:** Traditional KVS Stream
- **Alternatives Considered:** WebRTC dual-path, Janus media server
- **Reason:** Simplest, lowest cost, no original audio needed
- **Approved By:** User confirmed

### Nov 26, 2025 - Listener Delivery Method
- **Decision:** S3-only with presigned URLs
- **Alternatives Considered:** WebSocket streaming, hybrid
- **Reason:** Simple, scalable, small chunks
- **Chunk Size:** 2 seconds (balance latency vs download time)

### Nov 26, 2025 - Browser Format
- **Decision:** Upload WebM, convert in backend
- **Alternatives Considered:** Convert to PCM in browser
- **Reason:** Keep browser lightweight
- **Trade-off:** More backend processing, but negligible with Lambda

### Nov 26, 2025 - Session Recording
- **Decision:** No recording, process and discard
- **Alternatives Considered:** Store in S3 for playback
- **Reason:** Not required, saves storage costs
- **Retention:** 1 hour in KVS Stream, 24 hours in S3 (for active sessions)

---

## Next Steps

1. ✅ Complete Phase 0 cleanup and blueprints
2. Toggle to Act Mode
3. Implement Phase 1 (Speaker MediaRecorder)
4. Create checkpoint after each phase
5. Use new_task if hitting token limits

---

## Contact & Context

If resuming after interruption:
1. **Read this file first** - ARCHITECTURE_DECISIONS.md
2. **Check task_progress** - See what's completed
3. **Read latest CHECKPOINT file** - Get phase status
4. **Continue from next unchecked task**

**Current Phase:** Phase 0 (Cleanup & Blueprints)
**Next Phase:** Phase 1 (Speaker MediaRecorder)
**Timeline:** 3-4 days to working translation
