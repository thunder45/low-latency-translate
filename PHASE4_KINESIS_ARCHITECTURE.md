# Phase 4: Kinesis Data Streams for True Low Latency

## Critical Issues with Current S3 Architecture

### ❌ Flaw 1: S3 Event Batching Doesn't Work
**My assumption:** S3 accumulates chunks, then triggers after 3 seconds  
**Reality:** S3 fires event **immediately** for each .pcm file

**Impact:**
- 4 Lambda invocations per second (250ms chunks)
- Thousands of concurrent s3_audio_consumer instances
- Each one doing S3 ListObjects (race conditions)
- High S3 API costs
- Batch window logic doesn't help - trigger is per-object

### ❌ Flaw 2: Transcribe Batch Jobs Are Too Slow  
**My assumption:** StartTranscriptionJob takes 5-30s  
**Reality:** Queue time + boot time + processing = 15-60s

**Impact:**
- Job enters queue (unpredictable delay)
- Engine spins up (overhead)
- Downloads from S3 (more latency)
- For 3-second audio, overhead > audio duration
- Total latency: 15-60s (unacceptable)

### ❌ Flaw 3: S3 PUT Costs
**Cost calculation:**
- 4 writes/second/user
- 240 writes/minute/user
- 1000 users = 240,000 writes/minute
- S3 pricing: $0.005 per 1000 PUT requests
- Cost: $1.20/minute = $72/hour for 1000 users

**Plus:** S3 ListObjects costs from consumer

---

## Solution: Kinesis Data Streams

### New Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      SPEAKER BROWSER                          │
│                                                                │
│  AudioWorklet → PCM → WebSocket                               │
│                                                                │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ↓
┌──────────────────────────────────────────────────────────────┐
│              API GATEWAY WEBSOCKET                            │
│                                                                │
│  Routes audioChunk → connection_handler                       │
│                                                                │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ↓
┌──────────────────────────────────────────────────────────────┐
│           CONNECTION_HANDLER LAMBDA                           │
│                                                                │
│  ├─ Receives PCM chunk (base64)                              │
│  ├─ Decodes to bytes                                          │
│  └─ Writes to Kinesis Data Stream                            │
│      └─ kinesis.put_record(                                   │
│           StreamName: 'audio-ingestion-{stage}',              │
│           Data: pcm_bytes,                                    │
│           PartitionKey: sessionId                             │
│         )                                                      │
│                                                                │
│  Processing time: ~10ms (vs 50ms S3 PutObject)               │
│                                                                │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ↓
┌──────────────────────────────────────────────────────────────┐
│           KINESIS DATA STREAM                                 │
│           (audio-ingestion-dev)                               │
│                                                                │
│  Configuration:                                               │
│  ├─ Mode: On-Demand (auto-scales)                            │
│  ├─ Retention: 24 hours                                       │
│  ├─ Encryption: AWS managed                                   │
│  └─ Shard count: Auto (scales with load)                     │
│                                                                │
│  Behavior:                                                    │
│  ├─ Buffers records by PartitionKey (sessionId)              │
│  ├─ Accumulates for BatchWindow: 3 seconds                   │
│  ├─ OR until MaximumBatchingWindowInSeconds reached          │
│  └─ Triggers Lambda with batch of records                    │
│                                                                │
│  **KEY BENEFIT:** Only 1 Lambda invocation per 3 seconds!    │
│                                                                │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         │ Lambda Event Source Mapping
                         │ BatchSize: 100
                         │ BatchWindow: 3 seconds
                         │
                         ↓
┌──────────────────────────────────────────────────────────────┐
│           AUDIO_PROCESSOR LAMBDA                              │
│                                                                │
│  ┌─ Triggered by Kinesis with batched records                │
│  │                                                             │
│  ├─ Event structure:                                          │
│  │   {                                                         │
│  │     Records: [                                             │
│  │       {                                                     │
│  │         kinesis: {                                         │
│  │           data: '<base64_pcm>',  // 8KB                   │
│  │           partitionKey: 'session-123',                    │
│  │           sequenceNumber: '...'                           │
│  │         }                                                  │
│  │       },                                                   │
│  │       ... (up to 100 records or 3s worth)                │
│  │     ]                                                      │
│  │   }                                                        │
│  │                                                             │
│  ├─ 1. Group records by sessionId                            │
│  │    └─ {                                                    │
│  │         'session-123': [record1, record2, ...],           │
│  │         'session-456': [record3, record4, ...]            │
│  │       }                                                    │
│  │                                                             │
│  ├─ 2. For each session:                                     │
│  │    ├─ Decode all PCM chunks                               │
│  │    ├─ Concatenate (binary append)                         │
│  │    └─ Result: 98KB PCM for 3 seconds                     │
│  │                                                             │
│  ├─ 3. Transcribe with STREAMING API                         │
│  │    └─ Use amazon-transcribe-streaming-sdk                 │
│  │       └─ Opens HTTP/2 stream                               │
│  │       └─ Sends PCM buffer                                  │
│  │       └─ Receives transcript in ~500ms                     │
│  │       └─ NO job queue, NO S3 temp files!                  │
│  │                                                             │
│  ├─ 4. Translate + TTS (same as before)                      │
│  │    └─ translate.translate_text()                          │
│  │    └─ polly.synthesize_speech()                           │
│  │                                                             │
│  ├─ 5. Store MP3 in S3 + notify listeners                    │
│  │    └─ (same as current implementation)                    │
│  │                                                             │
│  └─ Total time: ~5 seconds (vs 10-15s)                       │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

---

## Implementation Changes Required

### 1. Create Kinesis Data Stream (CDK)

**File:** `session-management/infrastructure/stacks/session_management_stack.py`

```python
from aws_cdk import aws_kinesis as kinesis

# Replace audio_chunks_bucket with Kinesis stream
self.audio_stream = kinesis.Stream(
    self,
    "AudioIngestionStream",
    stream_name=f"audio-ingestion-{self.env_name}",
    stream_mode=kinesis.StreamMode.ON_DEMAND,  # Auto-scales
    retention_period=Duration.hours(24),
    encryption=kinesis.StreamEncryption.MANAGED,
)
```

### 2. Update connection_handler

**File:** `session-management/lambda/connection_handler/handler.py`

```python
# Replace kvs_stream_writer invoke with Kinesis put_record

kinesis_client = boto3.client('kinesis')

def handle_audio_chunk(event):
    # ... parse event ...
    
    # Decode PCM
    pcm_bytes = base64.b64decode(audio_data_base64)
    
    # Write to Kinesis
    kinesis_client.put_record(
        StreamName=f'audio-ingestion-{STAGE}',
        Data=pcm_bytes,  # Raw bytes (not base64)
        PartitionKey=session_id  # Groups by session
    )
    
    return {'statusCode': 200}
```

### 3. Configure Lambda Event Source Mapping

**File:** `session-management/infrastructure/stacks/session_management_stack.py`

```python
from aws_cdk import aws_lambda_event_sources as event_sources

# Connect audio_processor to Kinesis
self.audio_processor_function.add_event_source(
    event_sources.KinesisEventSource(
        stream=self.audio_stream,
        starting_position=lambda_.StartingPosition.LATEST,
        batch_size=100,  # Max records per invocation
        max_batching_window=Duration.seconds(3),  # Wait 3s for batching
        parallelization_factor=10,  # Process 10 shards in parallel
    )
)
```

### 4. Update audio_processor Handler

**File:** `audio-transcription/lambda/audio_processor/handler.py`

```python
def lambda_handler(event, context):
    """Handle Kinesis batch event."""
    
    # Group records by session
    sessions = {}
    for record in event['Records']:
        kinesis_data = record['kinesis']
        pcm_bytes = base64.b64decode(kinesis_data['data'])
        partition_key = kinesis_data['partitionKey']  # sessionId
        
        if partition_key not in sessions:
            sessions[partition_key] = []
        sessions[partition_key].append(pcm_bytes)
    
    # Process each session
    for session_id, chunks in sessions.items():
        # Concatenate PCM
        pcm_data = b''.join(chunks)
        
        # Get session metadata from DynamoDB
        session = get_session(session_id)
        
        # Transcribe with STREAMING API
        transcript = await transcribe_streaming(
            pcm_data, 
            session['sourceLanguage']
        )
        
        # Translate + TTS + notify (same as before)
        # ...
```

### 5. Implement Transcribe Streaming

**File:** `audio-transcription/lambda/audio_processor/handler.py`

```python
async def transcribe_streaming(
    pcm_bytes: bytes,
    language_code: str
) -> str:
    """
    Use Transcribe Streaming API (HTTP/2).
    Much faster than batch jobs - no queue time.
    """
    from amazon_transcribe.client import TranscribeStreamingClient
    from amazon_transcribe.handlers import TranscriptResultStreamHandler
    from amazon_transcribe.model import TranscriptEvent
    
    client = TranscribeStreamingClient(region='us-east-1')
    
    stream = await client.start_stream_transcription(
        language_code=language_code,
        media_sample_rate_hz=16000,
        media_encoding='pcm'
    )
    
    # Send PCM data
    await stream.input_stream.send_audio_event(audio_chunk=pcm_bytes)
    await stream.input_stream.end_stream()
    
    # Collect transcript
    transcript_text = ""
    async for event in stream.output_stream:
        if isinstance(event, TranscriptEvent):
            for result in event.transcript.results:
                if not result.is_partial:
                    for alt in result.alternatives:
                        transcript_text = alt.transcript
    
    return transcript_text
```

---

## Benefits of Kinesis Architecture

### 1. Correct Batching
- **S3 approach:** 4 Lambda invocations/second (chaos)
- **Kinesis approach:** 1 Lambda invocation/3 seconds (controlled)
- **Benefit:** 12x reduction in Lambda cold starts

### 2. Lower Latency
- **S3 approach:** 10-15 seconds
- **Kinesis approach:** 5-7 seconds  
- **Improvement:** 40-50% faster

### 3. Lower Cost
| Component | S3 Approach | Kinesis Approach | Savings |
|-----------|-------------|------------------|---------|
| Ingestion | 240 PUTs/min | 240 PutRecords/min | Similar |
| Lambdas | 240 invocations/min | 20 invocations/min | **92%** |
| S3 ListObjects | 240/min | 0 | **100%** |
| Transcribe | Batch jobs (slow) | Streaming (fast) | 50% time |

### 4. Simpler Code
- **Delete:** kvs_stream_writer Lambda
- **Delete:** s3_audio_consumer Lambda
- **Delete:** S3 event notification logic
- **Add:** 20 lines for Kinesis integration

---

## Comparison: S3 vs Kinesis

| Aspect | S3 Events (Current) | Kinesis Data Streams |
|--------|---------------------|----------------------|
| **Event firing** | Per object (immediate) | Batched (configurable) |
| **Batching** | Manual (complex) | Native (BatchWindow) |
| **Lambda invocations** | 4/sec = 240/min | 1/3sec = 20/min |
| **Race conditions** | Yes (ListObjects) | No (sequential) |
| **Cost** | High (PUTs + Lists) | Medium (PutRecord) |
| **Latency** | 10-15s | 5-7s |
| **Code complexity** | High | Low |
| **Transcribe** | Batch jobs (slow) | Streaming (fast) |

---

## Implementation Plan

### Step 1: Create Kinesis Stream (30 min)
- Add to session_management_stack.py
- Configure On-Demand mode
- Set retention to 24 hours

### Step 2: Update connection_handler (15 min)
- Replace Lambda invoke with kinesis.put_record
- Send raw PCM bytes (not base64)
- Use sessionId as partition key

### Step 3: Connect audio_processor to Kinesis (20 min)
- Add Kinesis event source mapping
- Configure BatchWindow: 3 seconds
- Update handler to process Kinesis records

### Step 4: Implement Transcribe Streaming (1 hour)
- Add amazon-transcribe-streaming-sdk
- Replace batch job with streaming API
- Handle HTTP/2 connection

### Step 5: Remove Old Components (15 min)
- Delete kvs_stream_writer Lambda
- Delete s3_audio_consumer Lambda
- Remove S3 event notifications
- Update IAM permissions

### Step 6: Deploy and Test (30 min)
- Deploy session-management stack
- Deploy audio-transcription stack
- Test end-to-end
- Measure improved latency

**Total estimate: 3-4 hours**

---

## Expected Performance

### With Kinesis + Transcribe Streaming:

```
T+0.0s:  Speaker speaks
T+0.2s:  PCM in Kinesis
T+3.0s:  Batch window closes
T+3.1s:  audio_processor triggered with batch
T+3.2s:  Transcribe Streaming starts
T+3.7s:  Transcript received (500ms)
T+4.2s:  Translation complete (500ms)
T+5.5s:  TTS generated (1.3s)
T+5.6s:  MP3 in S3
T+5.7s:  Listener notified
T+5.8s:  Audio playing

Total: ~6 seconds (vs 10-15s current)
```

### Latency breakdown:
- Browser → Kinesis: 0.2s
- Kinesis buffering: 3s (configurable)
- Lambda processing: 0.1s
- Transcribe Streaming: 0.5s
- Translate: 0.5s
- TTS: 1.3s
- S3 + notification: 0.2s
- **Total: 5.8 seconds**

---

## Cost Comparison (1000 users, 1 hour)

### Current S3 Architecture:
- Lambda invocations: 240/min * 60 * 1000 = 14.4M invocations
- S3 PUTs: 14.4M writes @ $0.005/1K = $72
- S3 ListObjects: 14.4M calls @ $0.0004/1K = $5.76
- Lambda compute: 14.4M * 256MB * 0.1s = high
- **Total: ~$100/hour**

### Kinesis Architecture:
- Lambda invocations: 20/min * 60 * 1000 = 1.2M invocations
- Kinesis PutRecords: 14.4M records @ $0.014/1M = $0.20
- Kinesis shard hours: On-Demand auto-scales, ~$15/hour
- Lambda compute: 1.2M * 512MB * 1s = moderate
- **Total: ~$25/hour (75% savings)**

---

## Migration Path

### Option A: Full Kinesis Migration (Recommended)
**Time:** 3-4 hours  
**Benefit:** Correct architecture, 50% latency reduction, 75% cost savings

1. Implement Kinesis Data Stream
2. Update connection_handler
3. Add event source mapping
4. Implement Transcribe Streaming
5. Delete kvs_stream_writer and s3_audio_consumer
6. Deploy and test

### Option B: Hybrid (Quick Fix)
**Time:** 1-2 hours  
**Benefit:** Fixes batching issue, keeps current code

1. Keep S3 for storage
2. Add Kinesis for event batching
3. connection_handler writes to both S3 and Kinesis
4. S3 for audit trail, Kinesis for processing
5. Simpler but not optimal

### Option C: Stay with S3 (Not Recommended)
**Time:** 1 hour  
**Fix:** Add DynamoDB-based batching coordination

- Use DynamoDB to track chunks
- Only trigger processing when batch complete
- Complex, prone to edge cases
- Still has Transcribe batch job latency

---

## Recommended Next Steps

**I recommend Option A: Full Kinesis Migration**

1. **Create Kinesis stream** in CDK
2. **Update connection_handler** to use PutRecord
3. **Add event source mapping** to audio_processor
4. **Implement Transcribe Streaming** API
5. **Remove** kvs_stream_writer and s3_audio_consumer
6. **Test** end-to-end with 5-7s latency

This will give you:
- ✅ True low latency (5-7s vs 10-15s)
- ✅ Correct batching (no race conditions)
- ✅ 75% cost reduction
- ✅ Simpler architecture (2 fewer Lambdas)
- ✅ Industry-standard approach

**Shall I proceed with implementing the Kinesis architecture?**
