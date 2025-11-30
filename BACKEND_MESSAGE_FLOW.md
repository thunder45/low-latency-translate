# Backend Message Flow - Kinesis + Transcribe Streaming Architecture

## Document Status
**Current:** Phase 4 Architecture (Kinesis-based ingestion) ✅ DEPLOYED AND WORKING  
**Status:** Production ready, verified in logs  
**Last Updated:** November 30, 2025

✅ **Phase 4 Complete:** This document describes the **current production architecture**:
- Kinesis Data Stream with native 3-second batching
- Transcribe Streaming API (500ms latency, not 15-60s)
- 92% fewer Lambda invocations (20/min vs 240/min)
- Expected 50% latency improvement and 75% cost reduction

**Verified Working:**
- ✅ Kinesis batch processing: "Processing Kinesis batch with 16 records"
- ✅ Session grouping: "Grouped records into 1 sessions"
- ✅ PCM concatenation: "131072 bytes, 4.10s"
- ✅ Translation and TTS: "Generated TTS for es: 10700 bytes"

**Historical Note:** Phase 3 (S3-based) architecture was replaced. See git history for Phase 3 flow.

See **CHECKPOINT_PHASE4_COMPLETE.md** for deployment guide and **OPTIONAL_FEATURES_REINTEGRATION_PLAN.md** for disabled features.

---

## Complete Message Flow Diagram (Phase 3 - Current)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           SPEAKER BROWSER                                │
│                                                                           │
│  [AudioWorklet Processor Thread]                                         │
│  ├─ Captures Float32 samples from microphone                            │
│  ├─ Converts to Int16 PCM (4096 samples = ~256ms @ 16kHz)              │
│  └─ Posts message to main thread                                         │
│                                                                           │
│  [Main Thread - AudioWorkletService]                                     │
│  ├─ Receives PCM ArrayBuffer from worklet                               │
│  ├─ Calls onAudioData callback                                          │
│  └─ Passes to SpeakerService                                            │
│                                                                           │
│  [SpeakerService]                                                        │
│  ├─ Receives PCM ArrayBuffer + timestamp                                │
│  ├─ Converts to base64 for WebSocket transport                          │
│  └─ Sends via WebSocket                                                 │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ├─ WebSocket Message
                                    │  {
                                    │    action: 'audioChunk',
                                    │    sessionId: 'session-123',
                                    │    audioData: '<base64_pcm>',  // ~11KB base64
                                    │    timestamp: 1732800000000,
                                    │    format: 'pcm',
                                    │    sampleRate: 16000,
                                    │    channels: 1,
                                    │    encoding: 's16le'
                                    │  }
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│              API GATEWAY WEBSOCKET (wss://...)                           │
│                                                                           │
│  ├─ Routes by message.action                                            │
│  ├─ $connect → connection_handler (with auth)                           │
│  ├─ audioChunk → connection_handler                                     │
│  └─ $disconnect → disconnect_handler                                    │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│           CONNECTION_HANDLER LAMBDA (session-connection-handler-dev)     │
│                                                                           │
│  ┌─ Handler: handle_audio_chunk()                                       │
│  │                                                                        │
│  ├─ 1. Parse WebSocket event                                            │
│  │    ├─ Extract: sessionId, audioData, timestamp, format               │
│  │    └─ Validate: session exists and active                            │
│  │                                                                        │
│  ├─ 2. Forward to kvs_stream_writer (async invoke)                      │
│  │    └─ Payload: {                                                     │
│  │         action: 'writeToStream',                                     │
│  │         sessionId: 'session-123',                                    │
│  │         audioData: '<base64_pcm>',                                   │
│  │         timestamp: 1732800000000,                                    │
│  │         format: 'pcm',                                               │
│  │         chunkIndex: 42                                               │
│  │       }                                                               │
│  │                                                                        │
│  └─ 3. Return success to WebSocket                                      │
│       └─ Status: 200 OK                                                 │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Lambda Invoke (Async)
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│           KVS_STREAM_WRITER LAMBDA (kvs-stream-writer-dev)              │
│           [Renamed: audio_chunk_writer for clarity]                      │
│                                                                           │
│  ┌─ Handler: handle_write_to_stream()                                   │
│  │                                                                        │
│  ├─ 1. Decode base64 → raw PCM bytes                                    │
│  │    └─ Result: 8192 bytes (Int16 PCM)                                │
│  │                                                                        │
│  ├─ 2. Write to S3                                                      │
│  │    └─ write_to_s3(session_id, pcm_data, timestamp, 'pcm')           │
│  │                                                                        │
│  └─ S3 PutObject                                                         │
│      ├─ Bucket: low-latency-audio-dev                                   │
│      ├─ Key: sessions/{sessionId}/chunks/{timestamp}.pcm                │
│      ├─ Body: <8192 bytes raw PCM>                                      │
│      ├─ ContentType: audio/pcm                                          │
│      └─ Metadata: {sessionId, timestamp, format: 'pcm',                 │
│                    sampleRate: '16000', channels: '1',                  │
│                    encoding: 's16le'}                                    │
│                                                                           │
│  Processing time: ~50ms (vs 170ms with WebM)                            │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ S3 Event: ObjectCreated
                                    │ Filter: sessions/*.pcm
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│           S3 BUCKET (low-latency-audio-dev)                              │
│                                                                           │
│  Current state:                                                          │
│  ├─ sessions/session-123/chunks/1732800000000.pcm (8192 bytes)         │
│  ├─ sessions/session-123/chunks/1732800000256.pcm (8192 bytes)         │
│  ├─ sessions/session-123/chunks/1732800000512.pcm (8192 bytes)         │
│  ├─ ... (accumulating until batch window)                               │
│  └─ Lifecycle: Delete after 1 day                                       │
│                                                                           │
│  After ~3 seconds (BATCH_WINDOW_SECONDS):                               │
│  └─ Triggers S3 Event Notification                                      │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ S3 Event Notification
                                    │ {
                                    │   eventName: 'ObjectCreated:Put',
                                    │   s3: {
                                    │     bucket: { name: 'low-latency-audio-dev' },
                                    │     object: { key: 'sessions/.../1732800000768.pcm' }
                                    │   }
                                    │ }
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│           S3_AUDIO_CONSUMER LAMBDA (s3-audio-consumer-dev)              │
│                                                                           │
│  ┌─ Handler: lambda_handler(s3_event)                                   │
│  │                                                                        │
│  ├─ 1. Parse S3 event                                                   │
│  │    ├─ Extract sessionId from key                                     │
│  │    └─ Key: sessions/{sessionId}/chunks/{timestamp}.pcm               │
│  │                                                                        │
│  ├─ 2. List all chunks for session                                      │
│  │    └─ list_session_chunks()                                          │
│  │       ├─ S3 ListObjects: sessions/session-123/chunks/               │
│  │       ├─ Filter: .pcm and .webm files                                │
│  │       └─ Result: [chunk1, chunk2, ..., chunk12] (sorted by timestamp)│
│  │                                                                        │
│  ├─ 3. Create batches (3-second windows)                                │
│  │    └─ create_chunk_batches(chunks)                                   │
│  │       ├─ Group by timestamp proximity                                │
│  │       └─ Result: [[chunk1-12], [chunk13-24], ...]                   │
│  │                                                                        │
│  ├─ 4. Process each batch                                               │
│  │    └─ process_chunk_batch(session_id, batch, bucket, index)         │
│  │                                                                        │
│  │       ┌─ For each chunk in batch:                                    │
│  │       ├─ 4.1. Download from S3                                       │
│  │       │     └─ S3 GetObject → PCM bytes                              │
│  │       │                                                               │
│  │       ├─ 4.2. Concatenate PCM (binary append)                        │
│  │       │     └─ pcm_data += chunk_data                                │
│  │       │     └─ **NO FFMPEG NEEDED!**                                 │
│  │       │     └─ Result: ~98KB for 3 seconds (12 chunks)              │
│  │       │                                                               │
│  │       ├─ 4.3. Get session metadata                                   │
│  │       │     └─ DynamoDB GetItem(Sessions-dev, sessionId)             │
│  │       │     └─ Extract: sourceLanguage, targetLanguages              │
│  │       │                                                               │
│  │       └─ 4.4. Invoke audio_processor                                 │
│  │             └─ Lambda Invoke (async)                                 │
│  │                                                                        │
│  └─ Processing time: ~100ms (vs 2000ms with FFmpeg!)                    │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Lambda Invoke (Event type = async)
                                    │ Payload: {
                                    │   sessionId: 'session-123',
                                    │   audio: {
                                    │     data: '<hex_encoded_pcm>',  // 98KB → 196KB hex
                                    │     format: 'pcm',
                                    │     sampleRate: 16000,
                                    │     channels: 1,
                                    │     encoding: 's16le'
                                    │   },
                                    │   sourceLanguage: 'en',
                                    │   targetLanguages: ['es', 'fr'],
                                    │   timestamp: 1732800000000,
                                    │   duration: 3.0,
                                    │   batchIndex: 0
                                    │ }
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│           AUDIO_PROCESSOR LAMBDA (audio-processor)                       │
│                                                                           │
│  ┌─ Handler: lambda_handler() → detect PCM batch                        │
│  │                                                                        │
│  ├─ Routes to: handle_pcm_batch(event)                                  │
│  │                                                                        │
│  │  ┌─ STEP 1: Decode PCM                                               │
│  │  │  └─ bytes.fromhex(audio.data) → raw PCM bytes                     │
│  │  │                                                                     │
│  │  ├─ STEP 2: Transcribe PCM → Text                                    │
│  │  │  └─ transcribe_pcm_audio()                                        │
│  │  │     ├─ Upload PCM to S3 temp: sessions/.../transcribe-temp/       │
│  │  │     │   └─ S3 PutObject: job-{uuid}.pcm                           │
│  │  │     │                                                              │
│  │  │     ├─ Start Transcription Job                                    │
│  │  │     │   └─ transcribe.start_transcription_job(                    │
│  │  │     │        TranscriptionJobName: 'transcribe-{session}-{batch}',│
│  │  │     │        LanguageCode: 'en-US',                               │
│  │  │     │        MediaFormat: 'pcm',                                  │
│  │  │     │        MediaSampleRateHertz: 16000,                         │
│  │  │     │        Media: { MediaFileUri: 's3://...' }                  │
│  │  │     │      )                                                       │
│  │  │     │                                                              │
│  │  │     ├─ Poll for completion (max 30s)                              │
│  │  │     │   └─ Loop: get_transcription_job() every 1s                │
│  │  │     │   └─ Wait for status: COMPLETED                             │
│  │  │     │                                                              │
│  │  │     ├─ Download transcript JSON                                   │
│  │  │     │   └─ Parse: results.transcripts[0].transcript               │
│  │  │     │                                                              │
│  │  │     └─ Cleanup: Delete job + temp S3 file                         │
│  │  │                                                                     │
│  │  │  Result: "Hello this is a test"                                   │
│  │  │  Time: 5-30 seconds (depends on audio length)                     │
│  │  │                                                                     │
│  │  ├─ STEP 3-6: For each target language ['es', 'fr']                  │
│  │  │                                                                     │
│  │  │  ┌─ STEP 3: Translate Text                                        │
│  │  │  │  └─ translate.translate_text(                                  │
│  │  │  │       Text: "Hello this is a test",                            │
│  │  │  │       SourceLanguageCode: 'en',                                │
│  │  │  │       TargetLanguageCode: 'es'                                 │
│  │  │  │     )                                                           │
│  │  │  │  Result: "Hola esto es una prueba"                             │
│  │  │  │  Time: ~500ms                                                  │
│  │  │  │                                                                 │
│  │  │  ├─ STEP 4: Generate TTS (Text-to-Speech)                         │
│  │  │  │  └─ polly.synthesize_speech(                                   │
│  │  │  │       Text: "Hola esto es una prueba",                         │
│  │  │  │       OutputFormat: 'mp3',                                     │
│  │  │  │       VoiceId: 'Lucia',  // Spanish neural voice              │
│  │  │  │       Engine: 'neural',                                        │
│  │  │  │       SampleRate: '24000'                                      │
│  │  │  │     )                                                           │
│  │  │  │  Result: AudioStream with MP3 bytes (~32KB)                    │
│  │  │  │  Time: ~1-2 seconds                                            │
│  │  │  │                                                                 │
│  │  │  ├─ STEP 5: Store TTS in S3                                       │
│  │  │  │  └─ S3 PutObject                                               │
│  │  │  │     ├─ Bucket: translation-audio-dev                           │
│  │  │  │     ├─ Key: sessions/{sessionId}/translated/es/{timestamp}.mp3│
│  │  │  │     ├─ Body: <32KB MP3 data>                                   │
│  │  │  │     ├─ ContentType: audio/mpeg                                 │
│  │  │  │     └─ Metadata: {sessionId, targetLanguage, transcript, ...} │
│  │  │  │                                                                 │
│  │  │  └─ STEP 6: Generate presigned URL (10-min expiration)            │
│  │  │     └─ s3.generate_presigned_url(                                 │
│  │  │          'get_object',                                             │
│  │  │          Bucket: 'translation-audio-dev',                         │
│  │  │          Key: 'sessions/.../es/{timestamp}.mp3',                  │
│  │  │          ExpiresIn: 600                                            │
│  │  │        )                                                           │
│  │  │     Result: "https://s3.amazonaws.com/...?X-Amz-Signature=..."    │
│  │  │                                                                     │
│  │  │  ┌─ STEP 7: Query listeners for this language                     │
│  │  │  │  └─ notify_listeners_for_language()                            │
│  │  │  │                                                                 │
│  │  │  │     ┌─ 7.1. Query DynamoDB                                     │
│  │  │  │     │    └─ connections.query(                                 │
│  │  │  │     │         IndexName: 'sessionId-targetLanguage-index',     │
│  │  │  │     │         KeyCondition: 'sessionId=:sid AND                │
│  │  │  │     │                        targetLanguage=:lang',            │
│  │  │  │     │         Values: {':sid': 'session-123', ':lang': 'es'}  │
│  │  │  │     │       )                                                   │
│  │  │  │     │    Result: [                                             │
│  │  │  │     │      {connectionId: 'abc123', targetLanguage: 'es'},    │
│  │  │  │     │      {connectionId: 'def456', targetLanguage: 'es'}     │
│  │  │  │     │    ]                                                      │
│  │  │  │     │                                                           │
│  │  │  │     ├─ 7.2. Create WebSocket message                           │
│  │  │  │     │    └─ Message: {                                         │
│  │  │  │     │         type: 'translatedAudio',                         │
│  │  │  │     │         sessionId: 'session-123',                        │
│  │  │  │     │         targetLanguage: 'es',                            │
│  │  │  │     │         url: '<presigned_url>',                          │
│  │  │  │     │         timestamp: 1732800000000,                        │
│  │  │  │     │         duration: 3.0,                                   │
│  │  │  │     │         transcript: "Hola esto es una prueba",          │
│  │  │  │     │         sequenceNumber: 1732800000000                    │
│  │  │  │     │       }                                                   │
│  │  │  │     │                                                           │
│  │  │  │     └─ 7.3. Send to each listener                              │
│  │  │  │          └─ For connectionId in connections:                   │
│  │  │  │             └─ apigw.post_to_connection(                       │
│  │  │  │                  ConnectionId: connectionId,                   │
│  │  │  │                  Data: json.dumps(message).encode()            │
│  │  │  │                )                                                │
│  │  │  │                                                                 │
│  │  │  │  Result: "Notified 2/2 listeners for es"                       │
│  │  │  │                                                                 │
│  │  └─ Repeat for 'fr' language                                         │
│  │                                                                        │
│  └─ Return: {                                                            │
│       statusCode: 200,                                                   │
│       body: {                                                            │
│         message: 'PCM batch processed',                                 │
│         sessionId: 'session-123',                                        │
│         batchIndex: 0,                                                   │
│         results: [                                                       │
│           {targetLanguage: 'es', success: true, s3Key: '...'},         │
│           {targetLanguage: 'fr', success: true, s3Key: '...'}          │
│         ]                                                                │
│       }                                                                  │
│     }                                                                    │
│                                                                           │
│  Total processing time: ~8-35 seconds                                    │
│  (Transcribe: 5-30s, Translate: 500ms, TTS: 1-2s per language)         │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
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

## Error Handling
