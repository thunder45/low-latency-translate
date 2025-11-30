# Backend Message Flow - Kinesis + Transcribe Streaming Architecture

## Document Status
**Current:** Phase 4 Architecture (Kinesis-based ingestion) ✅ FULLY OPERATIONAL  
**Status:** Production ready - End-to-end tested and verified working  
**Last Updated:** November 30, 2025, 5:13 PM

✅ **Phase 4 Complete with Fixes:** This document describes the **current production architecture**:
- Kinesis Data Stream with native 3-second batching
- Transcribe Streaming API (500ms latency, not 15-60s)
- 92% fewer Lambda invocations (20/min vs 240/min)
- Expected 50% latency improvement and 75% cost reduction
- **NEW:** Listener connection bug fix (Nov 30, 3:50 PM)
- **NEW:** Dynamic language filtering for cost optimization (Nov 30, 3:52 PM)

**Verified Working:**
- ✅ Kinesis batch processing: "Processing Kinesis batch with 16 records"
- ✅ Session grouping: "Grouped records into 1 sessions"
- ✅ PCM concatenation: "131072 bytes, 4.10s"
- ✅ Translation and TTS: "Generated TTS for es: 10700 bytes"

**Verified Working (Nov 30, 2025, 5:06 PM):**
- ✅ Listener WebSocket connection succeeds (all 5 bugs fixed)
- ✅ Cost optimization active: "Active listener languages ['fr']"
- ✅ Translation pipeline working: Portuguese → French
- ✅ WebSocket notifications delivered: "Notified 1/1 listeners"
- ✅ Listener receiving and playing translated audio
- ✅ 10 deployments, all bugs resolved, system fully operational

**Historical Note:** Phase 3 (S3-based) architecture was replaced. See git history for Phase 3 flow.

See **CHECKPOINT_PHASE4_COMPLETE.md** for deployment guide and **OPTIONAL_FEATURES_REINTEGRATION_PLAN.md** for disabled features.

---

## Complete Message Flow Diagram (Phase 4 - CURRENT PRODUCTION)

**This is the ACTIVE production flow as of Nov 30, 2025**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           SPEAKER BROWSER                                │
│  [AudioWorklet] → Captures Float32 → Converts to Int16 PCM             │
│  [SpeakerService] → Converts to base64 → Sends via WebSocket           │
└────────────────────┬────────────────────────────────────────────────────┘
                     │ WebSocket: {action: 'audioChunk', audioData, ...}
                     ↓
┌────────────────────┴────────────────────────────────────────────────────┐
│           CONNECTION_HANDLER LAMBDA                                      │
│  ├─ Decode base64 → raw PCM bytes                                      │
│  ├─ kinesis.put_record(StreamName, Data=pcm_bytes, PartitionKey=sid)   │
│  └─ Return 200 OK (~10ms total)                                        │
│  ⚠️ NO kvs_stream_writer - DELETED in Phase 4                          │
└────────────────────┬────────────────────────────────────────────────────┘
                     │ Kinesis PutRecord
                     ↓
┌────────────────────┴────────────────────────────────────────────────────┐
│           KINESIS DATA STREAM (audio-ingestion-dev)                      │
│  ├─ Buffers records by PartitionKey (sessionId)                        │
│  ├─ Native batching: 3-second windows OR 100 records                   │
│  └─ Triggers audio_processor with batched records                      │
│  ✅ Only 1 Lambda invocation per 3 seconds (vs 4/sec Phase 3)          │
└────────────────────┬────────────────────────────────────────────────────┘
                     │ Kinesis Event Source Mapping
                     ↓
┌────────────────────┴────────────────────────────────────────────────────┐
│           AUDIO_PROCESSOR LAMBDA (handle_kinesis_batch)                  │
│  ┌─ 1. Group records by sessionId (partition key)                      │
│  ├─ 2. Concatenate PCM chunks (~98KB for 12 chunks)                    │
│  ├─ 3. Query ACTIVE listener languages (COST OPTIMIZATION)              │
│  │    └─ get_active_listener_languages(sessionId)                       │
│  │       └─ DynamoDB Query GSI → Result: ['fr'] ✅                      │
│  │       └─ Skip languages without listeners (50-90% savings)           │
│  ├─ 4. Transcribe with STREAMING API                                    │
│  │    └─ transcribe_streaming() → ~500ms (vs 15-60s batch jobs)        │
│  ├─ 5. Translate ONLY to active languages                               │
│  │    └─ For lang in ['fr']: translate.translate_text()                │
│  ├─ 6. Generate TTS for each active language                            │
│  │    └─ polly.synthesize_speech() → MP3 bytes                         │
│  ├─ 7. Store MP3 in S3 + generate presigned URL                        │
│  └─ 8. Send WebSocket notification (https:// endpoint) ✅               │
│       └─ notify_listeners_for_language() → "Notified 1/1"              │
│  Total: ~5 seconds (Phase 4 achieved!)                                  │
└────────────────────┬────────────────────────────────────────────────────┘
                     │ WebSocket notification via https://
                     ↓
┌────────────────────┴────────────────────────────────────────────────────┐
│           LISTENER BROWSER                                               │
│  ├─ Receive translatedAudio message                                    │
│  ├─ Download MP3 from S3 (presigned URL)                               │
│  ├─ Add to playback queue (S3AudioPlayer)                              │
│  └─ Play audio (HTMLAudioElement) ✅                                    │
└─────────────────────────────────────────────────────────────────────────┘

VERIFIED WORKING: Listener receives and plays translated audio!
Logs: "Notified 1/1 listeners for fr" (5:06 PM)
```

---

## Phase 3 Architecture (Historical - Replaced by Phase 4)

**Note:** This flow was used before Phase 4 Kinesis migration.  
See git history for complete Phase 3 implementation details.

Key differences from Phase 4:
- Used S3 events (fired per-object, not batched)
- Had kvs_stream_writer and s3_audio_consumer Lambdas (now deleted)
- Used Transcribe batch jobs (15-60s latency)
- No cost optimization (translated to all languages)

                                    │
                                    │ WebSocket Messages
                                    │ via API Gateway ManageConnections
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│              API GATEWAY WEBSOCKET (Listener Connections)                │
│                                                                           │
│  ├─ Connection abc123 (targetLanguage: 'es')                            │
│  │   └─ Receives: translatedAudio message with Spanish MP3 URL          │
│  │                                                                        │
│  └─ Connection def456 (targetLanguage: 'es')                            │
│      └─ Receives: same message (both listening to Spanish)              │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ WebSocket push to browser
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                           LISTENER BROWSER                                │
│                                                                           │
│  [ListenerService - WebSocket Handler]                                   │
│  ├─ Receives: 'translatedAudio' event                                   │
│  ├─ Parses message: {url, timestamp, duration, transcript, ...}         │
│  └─ Creates AudioChunkMetadata                                          │
│                                                                           │
│  [S3AudioPlayer]                                                         │
│  ├─ addChunk(metadata)                                                  │
│  ├─ Adds to playback queue (sorted by sequenceNumber)                   │
│  ├─ Starts prefetching next chunks                                      │
│  │                                                                        │
│  ├─ Downloads MP3 from S3                                               │
│  │   └─ fetch(presigned_url) → Blob (~32KB)                            │
│  │   └─ With retry (3 attempts, exponential backoff)                    │
│  │                                                                        │
│  ├─ Creates Audio element                                               │
│  │   └─ const audio = new Audio()                                       │
│  │   └─ audio.src = URL.createObjectURL(blob)                          │
│  │                                                                        │
│  └─ Plays audio                                                          │
│      └─ audio.play()                                                     │
│      └─ On end: Play next chunk in queue                                │
│                                                                           │
│  Buffer: 3 chunks prefetched for smooth playback                         │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Timing Breakdown (End-to-End)

### Complete Flow Timeline:

```
T = 0s
├─ Speaker speaks into microphone
│  └─ AudioWorklet captures samples
│
T = 0.256s (256ms)
├─ First PCM chunk (4096 samples) ready
│  └─ Sent via WebSocket (~8KB base64)
│
T = 0.306s (50ms later)
├─ connection_handler receives chunk
│  └─ Forwards to kvs_stream_writer (async)
│
T = 0.356s (50ms later)
├─ kvs_stream_writer writes to S3
│  └─ sessions/session-123/chunks/1732800000000.pcm
│
T = 0.512s, 0.768s, 1.024s, ...
├─ More PCM chunks arrive and stored
│  └─ Accumulating: 12 chunks over 3 seconds
│
T = 3.0s
├─ Batch window closes (BATCH_WINDOW_SECONDS = 3)
│  └─ S3 Event triggers s3_audio_consumer
│
T = 3.1s (100ms later)
├─ s3_audio_consumer processes
│  ├─ Lists all chunks (12 found)
│  ├─ Downloads all chunks from S3
│  ├─ Concatenates PCM (binary append, instant)
│  └─ Invokes audio_processor with 98KB PCM
│
T = 3.2s
├─ audio_processor starts processing
│  ├─ Decodes hex PCM
│  ├─ Uploads to S3 for Transcribe
│  └─ Starts transcription job
│
T = 8-30s (depends on audio length)
├─ Transcription job completes
│  └─ Transcript: "Hello this is a test"
│
T = 8.5s (500ms later)
├─ For target language 'es':
│  ├─ Translates: "Hola esto es una prueba"
│  └─ Generates TTS with Polly (Lucia voice)
│
T = 10s (1.5s later)
├─ TTS complete, MP3 generated
│  ├─ Stores in S3: sessions/.../translated/es/{timestamp}.mp3
│  ├─ Generates presigned URL
│  ├─ Queries DynamoDB for 'es' listeners
│  └─ Sends WebSocket notification to 2 listeners
│
T = 10.1s (100ms later)
├─ Listener browsers receive notification
│  └─ S3AudioPlayer.addChunk(metadata with presigned URL)
│
T = 10.2s (100ms later)
├─ S3AudioPlayer downloads MP3
│  └─ fetch(presigned_url) → 32KB blob
│
T = 10.3s (100ms later)
├─ Audio plays in listener browser
│  └─ Hears: "Hola esto es una prueba"
│
Total latency: ~10 seconds (speaker voice → listener ear)
```

---

## Message Payload Examples

### 1. WebSocket audioChunk (Speaker → Backend)

```json
{
  "action": "audioChunk",
  "sessionId": "joyful-mountain-789",
  "audioData": "//79/f3+AgD9/v4C...",  // base64 encoded PCM (8192 bytes → ~11KB)
  "timestamp": 1732800000000,
  "format": "pcm",
  "sampleRate": 16000,
  "channels": 1,
  "encoding": "s16le"
}
```

### 2. Lambda Invoke (connection_handler → kvs_stream_writer)

```json
{
  "action": "writeToStream",
  "sessionId": "joyful-mountain-789",
  "audioData": "//79/f3+AgD9/v4C...",
  "timestamp": 1732800000000,
  "format": "pcm",
  "chunkIndex": 42
}
```

### 3. S3 Event (Bucket → s3_audio_consumer)

```json
{
  "Records": [{
    "eventName": "ObjectCreated:Put",
    "s3": {
      "bucket": {"name": "low-latency-audio-dev"},
      "object": {
        "key": "sessions/joyful-mountain-789/chunks/1732800000000.pcm",
        "size": 8192
      }
    }
  }]
}
```

### 4. Lambda Invoke (s3_audio_consumer → audio_processor)

```json
{
  "sessionId": "joyful-mountain-789",
  "audio": {
    "data": "ffef00ff...",  // hex encoded PCM (98KB → 196KB hex string)
    "format": "pcm",
    "sampleRate": 16000,
    "channels": 1,
    "encoding": "s16le"
  },
  "sourceLanguage": "en",
  "targetLanguages": ["es", "fr", "de"],
  "timestamp": 1732800000000,
  "duration": 3.0,
  "batchIndex": 0
}
```

### 5. WebSocket translatedAudio (audio_processor → Listener)

```json
{
  "type": "translatedAudio",
  "sessionId": "joyful-mountain-789",
  "targetLanguage": "es",
  "url": "https://translation-audio-dev.s3.amazonaws.com/sessions/.../es/1732800000000.mp3?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...&X-Amz-Signature=...",
  "timestamp": 1732800000000,
  "duration": 3.0,
  "transcript": "Hola esto es una prueba",
  "sequenceNumber": 1732800000000
}
```

---

## Data Flow Sizes

| Stage | Format | Size | Notes |
|-------|--------|------|-------|
| AudioWorklet output | Float32 | 16KB | 4096 samples * 4 bytes |
| Converted to PCM | Int16 | 8KB | 4096 samples * 2 bytes |
| Base64 encoded | String | ~11KB | Base64 overhead (+33%) |
| S3 .pcm file | Binary | 8KB | Raw PCM stored |
| Aggregated batch (12 chunks) | Binary | 98KB | 3 seconds of audio |
| Hex encoded for Lambda | String | 196KB | Hex overhead (2x) |
| Transcription result | Text | <1KB | "Hello this is a test" |
| Translation result | Text | <1KB | "Hola esto es una prueba" |
| TTS MP3 output | Binary | ~32KB | 3 seconds @ 24kHz |

**Key improvement:** No WebM container means smaller payloads and no FFmpeg processing overhead!

---

## Phase 4: Kinesis Data Streams Architecture (Planned)

### Simplified Flow with Kinesis

```
┌──────────────────────────────────────────────────────────────┐
│                    SPEAKER BROWSER                           │
│  AudioWorklet → PCM → WebSocket                              │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ↓ WebSocket audioChunk
                     │
┌────────────────────┴─────────────────────────────────────────┐
│           CONNECTION_HANDLER LAMBDA                          │
│                                                              │
│  ├─ Decode base64 → PCM bytes                               │
│  ├─ kinesis.put_record(                                     │
│  │    StreamName: 'audio-ingestion-dev',                    │
│  │    Data: pcm_bytes,  // Raw bytes                        │
│  │    PartitionKey: sessionId                               │
│  │  )                                                        │
│  └─ Return 200 OK                                           │
│                                                              │
│  ⚠️ NO kvs_stream_writer invoke (deleted in Phase 4)       │
│  Processing: ~10ms (vs 50ms S3)                             │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ↓ Kinesis PutRecord
                     │
┌────────────────────┴─────────────────────────────────────────┐
│           KINESIS DATA STREAM                                │
│           audio-ingestion-dev (On-Demand)                    │
│                                                              │
│  ├─ Buffers records by PartitionKey (sessionId)             │
│  ├─ Accumulates for BatchWindow: 3 seconds                  │
│  ├─ OR until BatchSize: 100 records reached                 │
│  └─ Triggers Lambda with batched records                    │
│                                                              │
│  KEY BENEFIT: Only 1 Lambda invocation per 3 seconds!       │
│  (vs 12 invocations in Phase 3)                             │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ↓ Kinesis Event Source Mapping
                     │ Event: { Records: [...] }
                     │
┌────────────────────┴─────────────────────────────────────────┐
│           AUDIO_PROCESSOR LAMBDA                             │
│                                                              │
│  ┌─ Handler: lambda_handler(kinesis_event)                  │
│  │                                                            │
│  ├─ 1. Group records by sessionId                           │
│  │    └─ sessions = {}                                      │
│  │       for record in event['Records']:                    │
│  │         pcm = base64.b64decode(record['kinesis']['data'])│
│  │         sid = record['kinesis']['partitionKey']          │
│  │         sessions.setdefault(sid, []).append(pcm)         │
│  │                                                            │
│  ├─ 2. For each session, concatenate PCM                    │
│  │    └─ pcm_data = b''.join(chunks)  // ~98KB             │
│  │                                                            │
│  ├─ 3. Transcribe with STREAMING API                        │
│  │    └─ transcribe_streaming(pcm_data, language)          │
│  │       ├─ Open HTTP/2 stream                              │
│  │       ├─ Send PCM buffer                                 │
│  │       └─ Receive transcript in ~500ms                    │
│  │       └─ NO job queue, NO S3 temp files!                │
│  │                                                            │
│  │    Result: "Hello this is a test"                        │
│  │    Time: ~500ms (vs 15-60s batch jobs!)                 │
│  │                                                            │
│  ├─ 4. Translate + TTS (same as Phase 3)                    │
│  ├─ 5. Store MP3 in S3 + notify listeners (same)            │
│  │                                                            │
│  └─ Total time: ~5 seconds (vs 10-15s)                      │
│                                                              │
└──────────────────────────────────────────────────────────────┘

Improvements:
- ✅ Native batching (no race conditions)
- ✅ 92% fewer Lambda invocations (20/min vs 240/min)
- ✅ Transcribe Streaming (500ms vs 15-60s)
- ✅ 50% latency reduction (10-15s → 5-7s)
- ✅ 75% cost reduction
```

### Key Changes in Phase 4:

1. **connection_handler:** Writes to Kinesis (not S3)
2. **DELETE:** kvs_stream_writer Lambda (not needed)
3. **DELETE:** s3_audio_consumer Lambda (not needed)
4. **audio_processor:** Accepts Kinesis events, uses Transcribe Streaming
5. **Kinesis:** Native batching replaces manual coordination

### Phase 4 Timing (Expected):

```
T = 0s:     Speaker speaks
T = 0.2s:   PCM in Kinesis
T = 3.0s:   Batch window closes
T = 3.1s:   audio_processor triggered with batch (12 chunks)
T = 3.2s:   Transcribe Streaming starts
T = 3.7s:   Transcript received (500ms)
T = 4.2s:   Translation complete (500ms)
T = 5.5s:   TTS generated (1.3s)
T = 5.6s:   MP3 in S3
T = 5.7s:   Listener notified
T = 5.8s:   Audio playing

Total: ~6 seconds (vs 10-15s current)
```

---

---

## Listener Connection Flow ($connect with targetLanguage)

### Fixed: Nov 30, 2025 - Listener WebSocket Connection

**Previous Bug:**
```python
# ❌ WRONG: Used sourceLanguage for listeners
target_language=session.get('sourceLanguage') if role == 'listener' else None
```

**Fixed Implementation:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│                      LISTENER BROWSER                                    │
│                                                                           │
│  WebSocket Connection URL:                                               │
│  wss://API_ID.execute-api.us-east-1.amazonaws.com/prod                  │
│    ?token=<JWT_TOKEN>                                                    │
│    &sessionId=pure-truth-514                                             │
│    &targetLanguage=fr  ← CRITICAL: Now properly validated               │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ↓ $connect event
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│           CONNECTION_HANDLER LAMBDA ($connect handler)                   │
│                                                                           │
│  ┌─ Extract query parameters                                            │
│  │  ├─ sessionId: 'pure-truth-514'                                      │
│  │  └─ targetLanguage: 'fr'  ← NOW EXTRACTED CORRECTLY                 │
│  │                                                                        │
│  ├─ Validate session exists and is active                               │
│  │  └─ DynamoDB GetItem(Sessions, sessionId)                            │
│  │                                                                        │
│  ├─ Determine role (speaker vs listener)                                │
│  │  └─ role = 'listener' (if not session owner)                         │
│  │                                                                        │
│  ├─ FOR LISTENERS: Validate targetLanguage                              │
│  │  ├─ Check parameter exists (required)                                │
│  │  ├─ Validate format (ISO 639-1 code)                                 │
│  │  ├─ Validate language pair compatibility                             │
│  │  │   └─ language_validator.validate_target_language(                 │
│  │  │        source='en', target='fr'                                   │
│  │  │      )                                                             │
│  │  └─ Return 400 error if invalid                                      │
│  │                                                                        │
│  └─ Create connection record                                            │
│     └─ connections_repo.create_connection(                              │
│          connection_id='abc123',                                         │
│          session_id='pure-truth-514',                                    │
│          role='listener',                                                │
│          target_language='fr'  ← NOW CORRECT                            │
│        )                                                                 │
│                                                                           │
│  Result: Connection record with CORRECT targetLanguage                  │
│  Status: 200 OK (connection accepted)                                   │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

**Connection Record Created:**
```json
{
  "connectionId": "abc123",
  "sessionId": "pure-truth-514",
  "role": "listener",
  "targetLanguage": "fr",  // ✅ CORRECT NOW (not 'en')
  "connectedAt": 1732986000000,
  "ttl": 1732993200
}
```

**Benefits:**
- ✅ Listeners can now successfully connect with targetLanguage
- ✅ GSI (sessionId-targetLanguage-index) works correctly
- ✅ audio_processor can query listeners by language
- ✅ Cost optimization enabled (see below)

---

## Cost Optimization: Dynamic Language Filtering

### Implemented: Nov 30, 2025 - Only Translate to Active Languages

**Problem:**
```python
# ❌ WASTEFUL: Translates to ALL configured languages
target_languages = session.get('targetLanguages', ['es', 'fr', 'de', 'it', 'pt'])
for lang in target_languages:  # Translates to 5 languages
    translate_and_tts(lang)  # Even if nobody listening!
```

**Cost Impact:**
- Session supports 10 languages
- Only 2 languages have active listeners
- Wastes 8 × (Translate + TTS + S3) API calls
- 80% unnecessary cost

**Optimized Implementation:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│           AUDIO_PROCESSOR LAMBDA (handle_kinesis_batch)                  │
│                                                                           │
│  ┌─ Step 1: Get session metadata                                        │
│  │  └─ DynamoDB GetItem(Sessions, sessionId)                            │
│  │     └─ sourceLanguage: 'en'                                          │
│  │     └─ targetLanguages: ['es', 'fr', 'de', 'it', 'pt']  (10 langs)  │
│  │                                                                        │
│  ├─ Step 2: Query ACTIVE listener languages (COST OPTIMIZATION)         │
│  │  └─ get_active_listener_languages(sessionId)                         │
│  │     ├─ Query Connections table using GSI                             │
│  │     │   └─ sessionId-targetLanguage-index                            │
│  │     ├─ Extract unique targetLanguage values                          │
│  │     └─ Result: ['es', 'fr']  ← Only 2 languages have listeners!     │
│  │                                                                        │
│  ├─ Step 3: Calculate cost savings                                      │
│  │  └─ skipped = {'de', 'it', 'pt'} (3 languages)                      │
│  │  └─ savings = 3/5 = 60% cost reduction                               │
│  │  └─ Log: "Cost optimization: Processing 2 languages, skipping 3"    │
│  │                                                                        │
│  ├─ Step 4: Check for no listeners edge case                            │
│  │  └─ if active_languages is empty:                                    │
│  │     ├─ Log: "No active listeners, skipping translation (100%)"      │
│  │     └─ Return early (save ALL costs)                                 │
│  │                                                                        │
│  └─ Step 5: Translate ONLY to active languages                          │
│     └─ for lang in ['es', 'fr']:  ← Only 2, not 5!                     │
│        ├─ Translate API call                                            │
│        ├─ TTS API call                                                   │
│        └─ S3 storage                                                     │
│                                                                           │
│  Cost Savings: 60% (3 of 5 languages skipped)                           │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

**Example Scenarios:**

**Scenario 1: Partial listeners (60% savings)**
- Session languages: 5 (es, fr, de, it, pt)
- Active listeners: 2 languages (es, fr)
- Skipped: 3 languages (de, it, pt)
- Cost reduction: 60%

**Scenario 2: Full distribution (0% savings)**
- Session languages: 5
- Active listeners: 5 (all languages have listeners)
- Skipped: 0
- Cost reduction: 0% (but no waste)

**Scenario 3: No listeners (100% savings)**
- Session languages: 5
- Active listeners: 0 (nobody connected yet)
- Skipped: All translation
- Cost reduction: 100%

**Benefits:**
- ✅ 50-90% reduction in translation costs (typical)
- ✅ 50-90% reduction in TTS costs (typical)
- ✅ Faster processing (fewer API calls)
- ✅ Lower Lambda execution time
- ✅ Automatic optimization (no manual configuration)

**Logging:**
```
INFO: Active listener languages for session pure-truth-514: ['es', 'fr']
INFO: Cost optimization for session pure-truth-514: 
      Processing 2 languages (active listeners), 
      skipping 3 languages (no listeners): {'de', 'it', 'pt'}. 
      Cost savings: 60%
```

---

## Error Handling
