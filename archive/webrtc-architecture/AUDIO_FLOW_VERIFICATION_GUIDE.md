# Audio Flow Verification Guide

## Purpose
This guide provides step-by-step instructions for verifying that audio flows correctly through the entire Low-Latency Translation pipeline: Speaker → KVS → EventBridge → kvs_stream_consumer → audio_processor → Transcribe → Translate → TTS → Listeners.

## Current Status: ~30% Complete
- ✅ WebRTC connections working (Speaker as Master, Listeners as Viewers)
- ✅ Infrastructure deployed (KVS streams, Lambda functions, EventBridge)
- ❌ **Audio flow NOT YET VERIFIED** - This is what we're testing

## Prerequisites

### Required Tools
```bash
# AWS CLI v2
aws --version

# jq for JSON processing
jq --version

# Verify AWS credentials
aws sts get-caller-identity
```

### Required Environment Variables
```bash
export AWS_REGION=us-east-1
export STAGE=dev
```

## Verification Steps

### Step 1: Run Automated Verification Script

The fastest way to check all components:

```bash
# Without a session (checks infrastructure only)
./scripts/verify-audio-pipeline.sh

# With an active session (full verification)
export SESSION_ID=abc123-def456-ghi789
./scripts/verify-audio-pipeline.sh
```

**What This Checks:**
1. ✓ KVS stream exists for session
2. ✓ Audio fragments present in KVS stream
3. ✓ EventBridge rule configured correctly
4. ✓ kvs_stream_consumer Lambda exists and has logs
5. ✓ SQS queue receiving messages (if applicable)
6. ✓ audio_processor Lambda processing audio
7. ✓ Transcribe integration working

### Step 2: Manual Step-by-Step Verification

If automated script fails or you need detailed diagnostics:

#### 2.1 Create a Test Session

1. Open speaker app: `http://localhost:3000` (or your deployed URL)
2. Login with Cognito credentials
3. Click "Create Session"
4. **Copy the Session ID** shown in browser console
5. Keep the session open and browser tab active

```bash
# Export session ID for testing
export SESSION_ID=<your-session-id>
```

#### 2.2 Verify KVS Stream Exists

```bash
STREAM_NAME="session-${SESSION_ID}"

# Check stream exists
aws kinesisvideo describe-stream \
  --stream-name "$STREAM_NAME" \
  --region us-east-1 \
  --output json

# Expected: StreamInfo with Status: ACTIVE
```

#### 2.3 Check for Audio Fragments

**This is the CRITICAL test** - if no fragments, audio isn't reaching KVS:

```bash
# List recent fragments (last 10)
aws kinesisvideo list-fragments \
  --stream-name "session-${SESSION_ID}" \
  --region us-east-1 \
  --max-results 10 \
  --output json

# Expected: Array of Fragments with ProducerTimestamp
# If empty: Audio is NOT reaching KVS - WebRTC issue
```

**Expected Output (SUCCESS):**
```json
{
  "Fragments": [
    {
      "FragmentNumber": "91343852333181432392682062722375517702289339392",
      "FragmentSizeInBytes": 12345,
      "ProducerTimestamp": 1732610745123,
      "ServerTimestamp": 1732610745456,
      "FragmentLengthInMilliseconds": 2000
    }
  ]
}
```

**If No Fragments:**
- Audio is NOT reaching KVS
- Check browser console for WebRTC errors
- Verify microphone permissions granted
- Check KVSWebRTCService logs in browser

#### 2.4 Verify EventBridge Rule Triggers

```bash
# Check EventBridge rule
aws events describe-rule \
  --name "session-kvs-consumer-trigger-dev" \
  --region us-east-1

# List rule targets
aws events list-targets-by-rule \
  --rule "session-kvs-consumer-trigger-dev" \
  --region us-east-1

# Expected: Target pointing to kvs-stream-consumer Lambda
```

#### 2.5 Check kvs_stream_consumer Invocations

```bash
# Tail logs in real-time
./scripts/tail-lambda-logs.sh kvs-stream-consumer-dev

# OR check recent logs
aws logs tail /aws/lambda/kvs-stream-consumer-dev \
  --since 1h \
  --format short
```

**Look For:**
- "Processing EventBridge event"
- "Starting stream processing for session"
- "Processed X chunks for session"
- **RED FLAG:** "Failed to initialize KVS stream"
- **RED FLAG:** "Error processing stream chunks"

#### 2.6 Verify SQS Queue (if used)

```bash
# Get queue URL
QUEUE_URL=$(aws sqs get-queue-url \
  --queue-name audio-processing-queue-dev \
  --region us-east-1 \
  --output text 2>/dev/null)

# Check message count
aws sqs get-queue-attributes \
  --queue-url "$QUEUE_URL" \
  --attribute-names ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible \
  --region us-east-1

# Peek at message (doesn't delete)
aws sqs receive-message \
  --queue-url "$QUEUE_URL" \
  --max-number-of-messages 1 \
  --visibility-timeout 5 \
  --region us-east-1
```

#### 2.7 Check audio_processor Processing

```bash
# Tail audio processor logs
./scripts/tail-lambda-logs.sh audio-processor-dev

# Look for:
# - "Processing audio chunk"
# - "Transcribe stream started"
# - "Received transcription result"
# - "Translation complete"
```

#### 2.8 Verify Transcribe Integration

```bash
# Check for Transcribe streaming sessions (requires Transcribe API access)
# Note: This is harder to verify directly
# Best verified through audio_processor logs

# Search for Transcribe logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor-dev \
  --filter-pattern "Transcribe" \
  --start-time $(($(date +%s) * 1000 - 3600000)) \
  --region us-east-1
```

### Step 3: End-to-End Test with Listener

1. **Keep speaker session active**
2. **Open listener app** in new browser/incognito
3. **Join the session** (paste session ID)
4. **Speak into microphone** on speaker side
5. **Listen for translated audio** on listener side

**What to Check:**
- Listener connects successfully (check browser console)
- Audio visualizer shows activity (if implemented)
- Translated audio plays within 3-5 seconds
- Audio quality is acceptable

### Step 4: Measure Latency

Track timestamps through the pipeline:

```bash
# Enable detailed timestamp logging first (see section below)

# Then search logs for latency markers
aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor-dev \
  --filter-pattern "latency" \
  --start-time $(($(date +%s) * 1000 - 600000)) \
  --region us-east-1 | \
  jq '.events[] | .message' | \
  grep -E "(received|transcribed|translated|synthesized)"
```

**Target Latencies:**
- KVS Ingestion: < 500ms
- Transcribe Streaming: 1-2 seconds
- Translation: < 500ms
- TTS: < 1 second
- **Total End-to-End: 3-5 seconds**

## Common Issues and Fixes

### Issue 1: No Fragments in KVS Stream

**Symptom:** `list-fragments` returns empty array

**Diagnosis:**
1. Check browser console for WebRTC errors
2. Verify microphone permissions granted
3. Check KVSWebRTCService connection status

**Possible Causes:**
- WebRTC connection not sending media
- ICE negotiation failed
- Microphone not captured
- KVS credentials invalid

**Fix:**
```javascript
// In browser console, check:
window.kvsWebRTC?.peerConnection?.getStats()
  .then(stats => {
    stats.forEach(stat => {
      if (stat.type === 'outbound-rtp' && stat.mediaType === 'audio') {
        console.log('Audio packets sent:', stat.packetsSent);
        console.log('Bytes sent:', stat.bytesSent);
      }
    });
  });
```

If `packetsSent` is 0, WebRTC isn't sending audio.

### Issue 2: kvs_stream_consumer Not Invoked

**Symptom:** No logs in `/aws/lambda/kvs-stream-consumer-dev`

**Diagnosis:**
```bash
# Check EventBridge rule state
aws events describe-rule \
  --name session-kvs-consumer-trigger-dev \
  --region us-east-1

# Check if events are being published
aws events list-rule-names-by-target \
  --target-arn $(aws lambda get-function --function-name kvs-stream-consumer-dev --query 'Configuration.FunctionArn' --output text) \
  --region us-east-1
```

**Possible Causes:**
- EventBridge rule disabled
- Rule target not configured
- Session creation not publishing events
- IAM permissions missing

**Fix:**
```bash
# Re-deploy session-management stack
cd session-management
make deploy
```

### Issue 3: Audio Format Mismatch

**Symptom:** audio_processor logs show format errors

**Diagnosis:**
```bash
# Check logs for format errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor-dev \
  --filter-pattern "format" \
  --region us-east-1
```

**Possible Causes:**
- KVS audio is Opus, audio_processor expects PCM
- Sample rate mismatch (KVS: 48kHz, Transcribe: 16kHz)
- Channel mismatch (stereo vs mono)

**Fix:** Implement proper audio transcoding in kvs_stream_consumer

### Issue 4: Transcribe Not Receiving Audio

**Symptom:** No transcription results in audio_processor logs

**Diagnosis:**
```bash
# Check for Transcribe errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor-dev \
  --filter-pattern "Transcribe" \
  --region us-east-1 | \
  jq '.events[] | .message' | \
  grep -i error
```

**Possible Causes:**
- Audio format not compatible
- Language code invalid
- Transcribe streaming connection failed
- IAM permissions missing

**Fix:** Verify audio format matches Transcribe requirements:
- Format: PCM 16-bit signed little-endian
- Sample rate: 8000 or 16000 Hz
- Channels: 1 (mono)

## Enhanced Logging

To enable comprehensive logging for better debugging:

### kvs_stream_consumer Logging

Add to `session-management/lambda/kvs_stream_consumer/handler.py`:

```python
# At the start of _process_stream_chunks:
logger.info(
    f"[AUDIO_FLOW] Starting chunk processing",
    extra={
        "session_id": session_id,
        "timestamp_ms": int(time.time() * 1000)
    }
)

# After extracting audio:
logger.info(
    f"[AUDIO_FLOW] Extracted audio chunk",
    extra={
        "session_id": session_id,
        "chunk_size_bytes": len(audio_data),
        "timestamp_ms": int(time.time() * 1000)
    }
)

# After sending to processor:
logger.info(
    f"[AUDIO_FLOW] Sent to audio_processor",
    extra={
        "session_id": session_id,
        "success": success,
        "timestamp_ms": int(time.time() * 1000)
    }
)
```

### audio_processor Logging

Add to `audio-transcription/lambda/audio_processor/handler.py`:

```python
# When receiving audio:
logger.info(
    f"[AUDIO_FLOW] Received audio chunk",
    extra={
        "session_id": session_id,
        "chunk_size_bytes": len(audio_data),
        "source": "kvs_stream_consumer",
        "timestamp_ms": int(time.time() * 1000)
    }
)

# When sending to Transcribe:
logger.info(
    f"[AUDIO_FLOW] Sending to Transcribe",
    extra={
        "session_id": session_id,
        "timestamp_ms": int(time.time() * 1000)
    }
)

# When receiving transcription:
logger.info(
    f"[AUDIO_FLOW] Received transcription",
    extra={
        "session_id": session_id,
        "transcript": partial_transcript,
        "timestamp_ms": int(time.time() * 1000),
        "latency_ms": latency
    }
)
```

Then search logs:
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/kvs-stream-consumer-dev \
  --filter-pattern "[AUDIO_FLOW]" \
  --region us-east-1
```

## Quick Reference Commands

```bash
# Complete verification
SESSION_ID=<session-id> ./scripts/verify-audio-pipeline.sh

# Check specific session
aws kinesisvideo list-fragments \
  --stream-name session-<session-id> \
  --region us-east-1

# Tail Lambda logs
./scripts/tail-lambda-logs.sh kvs-stream-consumer-dev
./scripts/tail-lambda-logs.sh audio-processor-dev

# Check SQS messages
aws sqs receive-message \
  --queue-url $(aws sqs get-queue-url --queue-name audio-processing-queue-dev --output text) \
  --max-number-of-messages 1

# Search for audio flow logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor-dev \
  --filter-pattern "[AUDIO_FLOW]" \
  --since 10m
```

## Success Criteria

✅ **Audio Flow Verified When:**
1. KVS stream has fragments (audio reaching KVS)
2. kvs_stream_consumer shows "Processed X chunks"
3. audio_processor receives audio chunks
4. Transcribe returns transcription results
5. Translation completes successfully
6. TTS generates audio
7. Listener receives and plays translated audio
8. End-to-end latency < 5 seconds

## Next Steps After Verification

Once audio flow is verified:
1. Implement UI feedback (session ID display, status indicators)
2. Fix AudioVisualizer component
3. Add error handling and recovery
4. Optimize latency (buffer sizes, batch processing)
5. Add comprehensive monitoring
6. Load testing with multiple listeners

## Support

For issues:
1. Check CloudWatch Logs for all Lambda functions
2. Review EventBridge event history
3. Verify IAM permissions
4. Check KVS stream status
5. Review WebRTC connection in browser console

**Documentation:**
- [KVS Testing Guide](./KVS_TESTING_GUIDE.md)
- [WebRTC Implementation Guide](./WEBRTC_KVS_COMPLETE_IMPLEMENTATION_GUIDE.md)
- [Lambda Functions Overview](./LAMBDA_FUNCTIONS_OVERVIEW.md)
