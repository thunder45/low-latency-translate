# Phase 4 Start Context - Kinesis Data Streams Migration

## Current Status (Nov 28, 2025, 11:39 AM)

**Phase 3:** ✅ COMPLETE (AudioWorklet + PCM + AWS APIs)  
**Phase 4:** 📋 READY TO START (Kinesis Migration)

---

## What Works Now (Phase 3 Complete)

### Frontend ✅
- **AudioWorklet PCM capture** at 16kHz (audio-worklet-processor.js)
- **AudioWorkletService.ts** - Low-latency audio capture (~3ms)
- **SpeakerService.ts** - Sends PCM via WebSocket
- **S3AudioPlayer.ts** - Downloads and plays translated MP3
- **ListenerService.ts** - Handles WebSocket notifications
- **Both apps build successfully**

### Backend ✅
```
Current Flow:
AudioWorklet → PCM → WebSocket → connection_handler 
  → kvs_stream_writer → S3 (.pcm files)
  → S3 Event → s3_audio_consumer (per-object!)
  → audio_processor (Transcribe/Translate/TTS)
  → S3 (MP3) → WebSocket → Listener
```

**Deployed Lambdas:**
- ✅ session-connection-handler-dev
- ✅ kvs-stream-writer-dev (writes .pcm to S3)
- ✅ s3-audio-consumer-dev (aggregates and forwards)
- ✅ audio-processor (Transcribe/Translate/TTS)

**AWS APIs Integrated:**
- ✅ Transcribe: StartTranscriptionJob (but too slow)
- ✅ Translate: translate_text()
- ✅ Polly: synthesize_speech()
- ✅ S3: presigned URLs
- ✅ WebSocket: post_to_connection()

---

## Critical Problems Identified

### 🔴 Problem 1: S3 Event Batching Doesn't Work

**My Assumption (WRONG):**
- S3 accumulates chunks
- After 3 seconds, fires one event
- s3_audio_consumer processes batch

**Reality:**
- S3 fires event **immediately** for each .pcm file
- 250ms chunks = 4 events/second
- s3_audio_consumer triggered 4 times/second
- Each invocation does S3 ListObjects (race conditions)
- Batch window logic doesn't help - trigger is per-object

**Evidence:**
- S3 event notification configured for .pcm suffix
- No way to configure "wait for N objects"
- S3 is object storage, not event buffer

**Impact:**
- 240 Lambda invocations/minute/user
- High S3 API costs (PUTs + Lists)
- Race conditions between concurrent invocations
- Unpredictable batch formation

### 🔴 Problem 2: Transcribe Batch Jobs Too Slow

**Current Implementation:**
```python
# audio_processor/handler.py line ~300
async def transcribe_pcm_audio():
    # Upload PCM to S3
    # Start transcription JOB
    # Poll for completion (30s timeout)
```

**Issue:**
- StartTranscriptionJob is async batch process
- Job enters queue (unpredictable delay)
- Engine spins up (overhead)
- Downloads from S3 (more latency)
- Typical: 15-60 seconds for 3-second audio

**Measurement Needed:**
- Test with actual audio
- Likely to see 20-40s latencies
- Unacceptable for "low-latency-translate"

### 🔴 Problem 3: High S3 Costs at Scale

**Current:**
- 4 PUTs/second/user = 240/minute
- 240 ListObjects/minute (s3_audio_consumer)
- 1000 users = 240,000 PUTs + 240,000 Lists per minute
- Cost: ~$100/hour

**Kinesis would be:**
- 240 PutRecords/minute
- 20 Lambda invocations/minute
- Cost: ~$25/hour (75% savings)

---

## Phase 4: Kinesis Solution

### Target Architecture

```
AudioWorklet → PCM → WebSocket → connection_handler
  → Kinesis PutRecord
  → Kinesis Data Stream (batches for 3s)
  → audio_processor (triggered once per 3s)
  → Transcribe Streaming API (500ms)
  → Translate + TTS
  → S3 (MP3) → WebSocket → Listener
  
Total latency: 5-7 seconds (vs 10-15s current)
```

### Changes Required

**1. Create Kinesis Data Stream (CDK)**
```python
# session_management_stack.py
self.audio_stream = kinesis.Stream(
    stream_name=f"audio-ingestion-{env_name}",
    stream_mode=kinesis.StreamMode.ON_DEMAND,
    retention_period=Duration.hours(24)
)
```

**2. Update connection_handler**
```python
# Replace kvs_stream_writer invoke with:
kinesis_client.put_record(
    StreamName=f'audio-ingestion-{STAGE}',
    Data=pcm_bytes,  # Raw bytes
    PartitionKey=session_id
)
```

**3. Add Kinesis Event Source**
```python
# session_management_stack.py or audio_transcription_stack.py
audio_processor.add_event_source(
    KinesisEventSource(
        stream=audio_stream,
        starting_position=StartingPosition.LATEST,
        batch_size=100,
        max_batching_window=Duration.seconds(3)
    )
)
```

**4. Update audio_processor Handler**
```python
def lambda_handler(event, context):
    # Handle Kinesis batch event
    sessions = {}
    for record in event['Records']:
        pcm_bytes = base64.b64decode(record['kinesis']['data'])
        session_id = record['kinesis']['partitionKey']
        sessions.setdefault(session_id, []).append(pcm_bytes)
    
    for session_id, chunks in sessions.items():
        pcm_data = b''.join(chunks)
        # Process with Transcribe Streaming...
```

**5. Implement Transcribe Streaming**
```python
async def transcribe_streaming(pcm_bytes, language_code):
    # Use amazon-transcribe-streaming-sdk
    # HTTP/2 stream, no S3 temp files
    # ~500ms latency
```

**6. Delete Old Components**
- Remove kvs_stream_writer Lambda
- Remove s3_audio_consumer Lambda
- Remove S3 event notifications
- Keep S3 bucket for translated audio output

---

## Files to Modify (Phase 4)

### Infrastructure:
1. **session-management/infrastructure/stacks/session_management_stack.py**
   - Add Kinesis Data Stream
   - Remove kvs_stream_writer Lambda creation
   - Remove s3_audio_consumer Lambda creation
   - Remove S3 event notifications
   - Grant connection_handler Kinesis PutRecord permission

2. **audio-transcription/infrastructure/stacks/audio_transcription_stack.py**
   - Add Kinesis event source mapping to audio_processor
   - Add amazon-transcribe-streaming SDK to requirements
   - Increase timeout to 120s (for streaming)

### Backend Code:
3. **session-management/lambda/connection_handler/handler.py**
   - Replace kvs_stream_writer invoke with kinesis.put_record
   - Add Kinesis client initialization
   - Update audioChunk handler

4. **audio-transcription/lambda/audio_processor/handler.py**
   - Add Kinesis event handler (new code path)
   - Replace transcribe_pcm_audio() with transcribe_streaming()
   - Remove S3 temp file logic
   - Keep Translate + TTS + WebSocket notification

5. **audio-transcription/lambda/audio_processor/requirements.txt**
   - Add: amazon-transcribe-streaming-sdk

### Files to Delete:
6. **session-management/lambda/kvs_stream_writer/** (entire directory)
7. **session-management/lambda/s3_audio_consumer/** (entire directory)

---

## Implementation Checklist

### Step 1: Infrastructure (CDK)
- [ ] Add Kinesis Data Stream to session_management_stack
- [ ] Add event source mapping to audio_processor
- [ ] Remove kvs_stream_writer Lambda
- [ ] Remove s3_audio_consumer Lambda
- [ ] Remove S3 event notifications
- [ ] Grant connection_handler Kinesis:PutRecord permission
- [ ] Grant audio_processor Kinesis:GetRecords permission

### Step 2: connection_handler Updates
- [ ] Add Kinesis client initialization
- [ ] Update handle_audio_chunk() to use put_record
- [ ] Remove kvs_stream_writer invocation
- [ ] Test: Verify records in Kinesis stream

### Step 3: audio_processor Updates
- [ ] Add Kinesis event handler
- [ ] Implement transcribe_streaming() function
- [ ] Replace transcribe_pcm_audio() calls
- [ ] Add amazon-transcribe-streaming-sdk
- [ ] Remove S3 temp file logic
- [ ] Test: Verify batch processing from Kinesis

### Step 4: Deploy
- [ ] Deploy session-management stack
- [ ] Deploy audio-transcription stack
- [ ] Verify Kinesis stream created
- [ ] Verify event source mapping active

### Step 5: Testing
- [ ] Test speaker sends to Kinesis
- [ ] Test Kinesis triggers audio_processor after 3s
- [ ] Test Transcribe Streaming works
- [ ] Measure end-to-end latency
- [ ] Verify cost reduction

---

## Expected Outcomes

### Latency Improvement:
| Stage | Current (S3) | Target (Kinesis) | Improvement |
|-------|-------------|------------------|-------------|
| Ingestion | 50ms | 10ms | 5x faster |
| Batching | Immediate (chaos) | 3s (controlled) | Predictable |
| Transcribe | 15-60s | 500ms | 30-120x faster |
| **Total** | **10-15s** | **5-7s** | **40-60% faster** |

### Cost Improvement:
- Lambda invocations: 240/min → 20/min (92% reduction)
- S3 API calls: 480/min → 0 (100% reduction)
- Total cost: ~$100/hr → ~$25/hr (75% savings)

### Code Simplification:
- Delete 2 Lambda functions
- Remove 400+ lines of batching logic
- Add ~100 lines for Kinesis integration
- Net: Simpler, more maintainable

---

## Testing After Phase 4

### Verify Kinesis Flow:
```bash
# 1. Check Kinesis stream exists
aws kinesis describe-stream --stream-name audio-ingestion-dev

# 2. Monitor shard metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Kinesis \
  --metric-name IncomingRecords \
  --dimensions Name=StreamName,Value=audio-ingestion-dev \
  --start-time $(date -u -v-5M +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum

# 3. Test speaker app
cd frontend-client-apps/speaker-app && npm run dev
# Speak for 5 seconds, check:
# - Browser: AudioWorklet logs
# - Backend: connection_handler logs show Kinesis PutRecord
# - Backend: audio_processor triggered after 3s (not continuously)

# 4. Monitor audio_processor
./scripts/tail-lambda-logs.sh audio-processor

# Expected logs:
# "Processing Kinesis batch with X records"
# "Transcription complete in 500ms"  (not 15-60s)
```

---

## Reference Documents

### For Phase 4 Implementation:
1. **PHASE4_KINESIS_ARCHITECTURE.md** - Complete architecture plan
2. **BACKEND_MESSAGE_FLOW.md** - Current message flow (will change)
3. **ARCHITECTURE_DECISIONS.md** - Updated with Phase 4 decision

### For Understanding Current State:
1. **AUDIOWORKLET_IMPLEMENTATION_COMPLETE.md** - What Phase 3 delivered
2. **IMPLEMENTATION_STATUS.md** - This file (overall progress)
3. **CHECKPOINT_PHASE3_COMPLETE.md** - Phase 3 checkpoint

### For Context:
1. **PHASE3_AUDIOWORKLET_PIVOT.md** - Why AudioWorklet
2. **PHASE3_START_CONTEXT.md** - What led to Phase 3

---

## Key Takeaways for Phase 4

### What to Keep from Phase 3:
- ✅ AudioWorklet (perfect for low-latency)
- ✅ Raw PCM format (no conversion overhead)
- ✅ S3AudioPlayer (listener playback)
- ✅ Translate + TTS pipeline
- ✅ WebSocket notifications
- ✅ S3 storage for translated audio

### What to Replace:
- ❌ S3-based PCM ingestion → **Kinesis Data Stream**
- ❌ S3 event notifications → **Kinesis event source mapping**
- ❌ kvs_stream_writer Lambda → **Direct Kinesis PutRecord**
- ❌ s3_audio_consumer Lambda → **Delete (not needed)**
- ❌ Transcribe Batch Jobs → **Transcribe Streaming API**

### Architecture Evolution:
```
Phase 1: MediaRecorder → WebM → WebSocket → S3
Phase 2: (Same but confirmed working)
Phase 3: AudioWorklet → PCM → WebSocket → S3 (no FFmpeg)
Phase 4: AudioWorklet → PCM → WebSocket → Kinesis → Streaming APIs
```

---

## Critical Success Factors for Phase 4

1. **Native Batching:** Kinesis BatchWindow must be 3 seconds
2. **Streaming Transcribe:** Use HTTP/2 Streaming API, not batch jobs
3. **Cost Validation:** Measure actual costs, verify 75% reduction
4. **Latency Measurement:** Achieve <7 seconds end-to-end
5. **Lambda Reduction:** Verify only 1 invocation per 3 seconds

---

## Estimated Timeline

### Phase 4 Implementation (3-4 hours):
- Hour 1: CDK changes (Kinesis stream, event source mapping)
- Hour 2: connection_handler + audio_processor updates
- Hour 3: Transcribe Streaming API implementation
- Hour 4: Testing, deployment, validation

### Expected Completion:
- **Start:** When you're ready
- **Complete:** Same day (3-4 hours)
- **Benefit:** Production-ready architecture

---

## Quick Start Commands for Phase 4

### 1. Start with CDK:
```bash
cd session-management/infrastructure/stacks
# Add Kinesis stream to session_management_stack.py
# Remove kvs_stream_writer and s3_audio_consumer
```

### 2. Update connection_handler:
```bash
cd session-management/lambda/connection_handler
# Modify handler.py to use Kinesis
```

### 3. Update audio_processor:
```bash
cd audio-transcription/lambda/audio_processor
# Add Kinesis event handler
# Implement Transcribe Streaming
```

### 4. Deploy and test:
```bash
cd session-management && make deploy-websocket-dev
cd audio-transcription && make deploy-dev
# Test end-to-end
```

---

## Success Criteria for Phase 4

### Must Achieve:
- [ ] Kinesis stream created and healthy
- [ ] connection_handler writes to Kinesis successfully
- [ ] audio_processor triggered by Kinesis (not S3)
- [ ] Only 1 Lambda invocation per 3 seconds
- [ ] Transcribe Streaming works (<1s latency)
- [ ] End-to-end latency <7 seconds
- [ ] Cost per user <$0.03/hour

### Can Verify:
```bash
# Lambda invocations should drop dramatically
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=audio-processor \
  --start-time $(date -u -v-5M +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum

# Should see: ~20 invocations/minute (not 240)
```

---

## Rollback Plan

If Phase 4 fails:
1. **Revert CDK changes:** `git revert HEAD~1`
2. **Redeploy:** Current S3-based architecture
3. **No data loss:** Kinesis is additive
4. **Fallback:** Phase 3 works (just slower and more expensive)

**Git tag before starting:** Consider tagging current commit as `phase3-stable`

---

## All Context Documents

### Phase 4 Planning:
- **PHASE4_KINESIS_ARCHITECTURE.md** - Detailed architecture
- **PHASE4_START_CONTEXT.md** - This file

### Phase 3 Reference:
- **AUDIOWORKLET_IMPLEMENTATION_COMPLETE.md** - What was built
- **BACKEND_MESSAGE_FLOW.md** - Current flow
- **CHECKPOINT_PHASE3_COMPLETE.md** - Checkpoint

### Overall:
- **ARCHITECTURE_DECISIONS.md** - All decisions
- **IMPLEMENTATION_STATUS.md** - Progress tracking

---

## Ready to Start!

Phase 4 is fully planned and documented. When you're ready:

1. Read **PHASE4_KINESIS_ARCHITECTURE.md** for complete details
2. Follow implementation steps in order
3. Test thoroughly after each step
4. Measure latency and cost improvements

**Goal:** Production-ready, truly low-latency translation system with 5-7 second end-to-end latency and 75% cost savings!
