# Phase 3 Testing & Verification Guide

## Overview
This guide provides step-by-step instructions to test the complete Phase 3 implementation: S3 audio consumer, AWS API integrations (Transcribe/Translate/TTS), and listener playback.

**Last Updated:** November 27, 2025, 7:28 PM  
**Status:** Ready for testing

---

## Prerequisites

### Required:
- ✅ Phase 2 complete (WebM chunks flowing to S3)
- ✅ Phase 3 infrastructure deployed
- ✅ Frontend listener app builds successfully
- ✅ AWS CLI configured with credentials
- ✅ Access to AWS Console (for monitoring)

### Deployed Resources to Verify:
```bash
# Lambda functions
aws lambda list-functions --query 'Functions[?contains(FunctionName, `audio-consumer`) || contains(FunctionName, `audio-processor`)].FunctionName'

# Expected output:
# - s3-audio-consumer-dev
# - audio-processor

# S3 buckets
aws s3 ls | grep -E 'low-latency-audio|translation-audio'

# Expected output:
# - low-latency-audio-dev
# - translation-audio-dev
```

---

## Test 1: Verify S3 Audio Consumer Trigger

### Goal
Confirm S3 events trigger the audio consumer when chunks are uploaded.

### Steps

1. **Check existing chunks from Phase 2:**
```bash
aws s3 ls s3://low-latency-audio-dev/sessions/ --recursive

# Should show chunks from previous testing:
# sessions/{SESSION_ID}/chunks/{TIMESTAMP}.webm
```

2. **Upload a test chunk manually:**
```bash
# Create a small test file
echo "test audio data" > /tmp/test.webm

# Upload to S3
aws s3 cp /tmp/test.webm s3://low-latency-audio-dev/sessions/test-session-123/chunks/$(date +%s)000.webm
```

3. **Check s3_audio_consumer logs:**
```bash
./scripts/tail-lambda-logs.sh s3-audio-consumer-dev

# Expected logs:
# "Received S3 event"
# "Processing new chunk: s3://low-latency-audio-dev/sessions/test-session-123/chunks/..."
# "Found X chunks for session test-session-123"
```

### Success Criteria
- ✅ S3 event triggers Lambda within 1-2 seconds
- ✅ Lambda processes chunks without errors
- ✅ Logs show "Found X chunks for session"

### Troubleshooting
- **No trigger:** Check S3 event notification configuration
- **Permission errors:** Verify Lambda has S3 read permissions
- **FFmpeg errors:** Check ffmpeg binary exists in layer

---

## Test 2: Verify Chunk Aggregation and FFmpeg Conversion

### Goal
Confirm the consumer aggregates chunks and converts WebM → PCM.

### Steps

1. **Trigger speaker app to create chunks:**
   - Open speaker app: `http://localhost:5173` (or deployed URL)
   - Create session and start broadcasting
   - Speak for 5-10 seconds
   - Stop broadcasting

2. **Monitor consumer processing:**
```bash
# Tail logs in real-time
./scripts/tail-lambda-logs.sh s3-audio-consumer-dev

# Look for:
# "Found X chunks for session {SESSION_ID}"
# "Processing batch 1/Y with Z chunks"
# "Downloaded chunk 1/Z"
# "Concatenated Z chunks"
# "Converted to PCM: {size} bytes"
# "Invoking audio_processor"
```

3. **Verify no errors:**
```bash
# Check for errors in last 10 minutes
aws logs filter-log-events \
  --log-group-name /aws/lambda/s3-audio-consumer-dev \
  --filter-pattern "ERROR" \
  --start-time $(date -u -v-10M +%s)000

# Should return no ERROR lines
```

### Success Criteria
- ✅ Chunks aggregated into 3-second batches
- ✅ FFmpeg conversion completes successfully
- ✅ PCM data generated (check byte size in logs)
- ✅ audio_processor invoked

### Troubleshooting
- **FFmpeg not found:** Verify layer attached to Lambda
- **Conversion failed:** Check ffmpeg command in logs
- **Memory errors:** Increase Lambda memory (currently 1024MB)

---

## Test 3: Verify Transcribe Integration

### Goal
Confirm PCM audio is transcribed to text.

### Steps

1. **Check audio_processor logs for transcription:**
```bash
./scripts/tail-lambda-logs.sh audio-processor-dev

# Look for:
# "Processing PCM batch from s3_audio_consumer"
# "Decoded PCM audio: X bytes, 16000Hz"
# "Generated unique job name: transcribe-{SESSION_ID}-..."
# "Uploaded PCM to S3: sessions/{SESSION_ID}/transcribe-temp/..."
# "Started transcription job"
# "Transcription complete: '{TEXT}...'"
```

2. **Verify transcription job:**
```bash
# List recent transcription jobs
aws transcribe list-transcription-jobs --max-results 5

# Check specific job status
aws transcribe get-transcription-job \
  --transcription-job-name transcribe-{SESSION_ID}-{BATCH}-{UUID}
```

3. **Check for transcription in S3:**
```bash
# Transcribe stores results temporarily
aws s3 ls s3://low-latency-audio-dev/sessions/ --recursive | grep transcribe-temp

# Should show: sessions/{SESSION_ID}/transcribe-temp/{JOB_NAME}.pcm
```

### Success Criteria
- ✅ Transcription job created
- ✅ Job completes within 30 seconds
- ✅ Transcript text logged
- ✅ Temp files cleaned up

### Troubleshooting
- **Job fails:** Check audio format (must be PCM, 16kHz, mono)
- **Timeout:** Audio may be too long (>5 seconds)
- **Permission denied:** Verify Transcribe IAM permissions

---

## Test 4: Verify Translation Integration

### Goal
Confirm transcribed text is translated to target languages.

### Steps

1. **Create session with multiple target languages:**
```bash
# Via HTTP API
curl -X POST https://gcneupzdtf.execute-api.us-east-1.amazonaws.com/sessions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "sourceLanguage": "en",
    "targetLanguages": ["es", "fr", "de"]
  }'
```

2. **Speak in English, check logs for translations:**
```bash
./scripts/tail-lambda-logs.sh audio-processor-dev

# Look for:
# "Translated to es: '{SPANISH_TEXT}...'"
# "Translated to fr: '{FRENCH_TEXT}...'"
# "Translated to de: '{GERMAN_TEXT}...'"
```

3. **Verify translation API calls:**
```bash
# Check CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Translate \
  --metric-name CharacterCount \
  --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

### Success Criteria
- ✅ Text translated for each target language
- ✅ Translated text different from original
- ✅ No "Translation failed" errors in logs

### Troubleshooting
- **Translation fails:** Check source/target language codes match AWS Translate supported languages
- **Permission denied:** Verify translate:TranslateText IAM permission
- **Empty translation:** Check transcript is not empty

---

## Test 5: Verify TTS (Polly) Integration

### Goal
Confirm translated text is converted to speech MP3.

### Steps

1. **Check logs for TTS generation:**
```bash
./scripts/tail-lambda-logs.sh audio-processor-dev

# Look for:
# "Generated TTS for es: X bytes"
# "Generated TTS for fr: Y bytes"
# "Stored TTS audio in S3: sessions/{SESSION_ID}/translated/es/{TIMESTAMP}.mp3"
```

2. **List generated MP3 files:**
```bash
# Check translation-audio bucket
aws s3 ls s3://translation-audio-dev/sessions/ --recursive

# Should show:
# sessions/{SESSION_ID}/translated/es/{TIMESTAMP}.mp3
# sessions/{SESSION_ID}/translated/fr/{TIMESTAMP}.mp3
```

3. **Download and verify MP3:**
```bash
# Download one file
aws s3 cp s3://translation-audio-dev/sessions/{SESSION_ID}/translated/es/{TIMESTAMP}.mp3 /tmp/test.mp3

# Check file size (should be >1KB for real audio)
ls -lh /tmp/test.mp3

# Play it (macOS)
afplay /tmp/test.mp3
```

### Success Criteria
- ✅ MP3 files created in S3
- ✅ File size indicates real audio (not fallback)
- ✅ Audio is playable
- ✅ Voice matches target language

### Troubleshooting
- **TTS fails:** Check Polly voice ID is valid for language
- **Silent MP3:** Fallback triggered, check logs for "TTS failed"
- **Permission denied:** Verify polly:SynthesizeSpeech IAM permission

---

## Test 6: Verify WebSocket Notifications

### Goal
Confirm listeners receive `translatedAudio` notifications.

### Steps

1. **Check logs for notification attempts:**
```bash
./scripts/tail-lambda-logs.sh audio-processor-dev

# Look for:
# "Generated presigned URL for s3://translation-audio-dev/..."
# "Notified X/Y listeners for es"
```

2. **If API_GATEWAY_ENDPOINT not set:**
```bash
# Check environment variable
aws lambda get-function-configuration \
  --function-name audio-processor \
  --query 'Environment.Variables.API_GATEWAY_ENDPOINT'

# Should return: "wss://2y19uvhyq5.execute-api.us-east-1.amazonaws.com/prod"
```

3. **Query connections for test session:**
```bash
# Check DynamoDB for active listeners
aws dynamodb query \
  --table-name Connections-dev \
  --index-name sessionId-targetLanguage-index \
  --key-condition-expression "sessionId = :sid AND targetLanguage = :lang" \
  --expression-attribute-values '{
    ":sid": {"S": "YOUR_SESSION_ID"},
    ":lang": {"S": "es"}
  }'
```

### Success Criteria
- ✅ Presigned URLs generated (logged)
- ✅ Listeners queried successfully
- ✅ WebSocket messages sent (success count > 0)
- ✅ No "Connection gone" errors

### Troubleshooting
- **No listeners found:** Check DynamoDB GSI exists and has data
- **Post failed:** Verify API_GATEWAY_ENDPOINT is correct
- **Permission denied:** Check execute-api:ManageConnections IAM permission

---

## Test 7: End-to-End Translation Flow

### Goal
Complete flow from speaker audio to listener playback.

### Prerequisites
- Speaker app running locally or deployed
- Listener app running locally or deployed
- Valid session created

### Steps

1. **Start speaker app:**
```bash
cd frontend-client-apps/speaker-app
npm run dev
# Open http://localhost:5173
```

2. **Create session and start broadcasting:**
   - Log in with test account
   - Create new session
   - Select source language: English
   - Click "Start Broadcasting"
   - **Speak clearly:** "Hello, this is a test of the translation system"

3. **Monitor backend processing:**
```bash
# Terminal 1: Watch chunks
watch -n 1 'aws s3 ls s3://low-latency-audio-dev/sessions/ --recursive | tail -10'

# Terminal 2: Watch consumer
./scripts/tail-lambda-logs.sh s3-audio-consumer-dev

# Terminal 3: Watch processor
./scripts/tail-lambda-logs.sh audio-processor-dev

# Terminal 4: Watch translated audio
watch -n 2 'aws s3 ls s3://translation-audio-dev/sessions/ --recursive'
```

4. **Open listener app:**
```bash
cd frontend-client-apps/listener-app
npm run dev
# Open http://localhost:5174
```

5. **Join session as listener:**
   - Enter session ID from speaker
   - Select target language: Spanish
   - Click "Join Session"
   - **Wait 5-10 seconds** for first audio

6. **Verify playback:**
   - Check browser console for S3AudioPlayer logs
   - Listen for translated audio
   - Verify audio quality

### Expected Timeline
```
T+0s:   Speaker starts talking
T+3s:   First 3-second batch aggregated
T+5s:   Transcription complete
T+6s:   Translation complete  
T+7s:   TTS generated
T+8s:   MP3 in S3
T+9s:   Listener receives notification
T+10s:  Listener plays first audio chunk
```

### Success Criteria
- ✅ Audio flows through all stages
- ✅ Transcription accurate
- ✅ Translation correct for target language
- ✅ TTS audio clear and understandable
- ✅ Listener receives and plays audio
- ✅ Total latency <15 seconds

### Troubleshooting

**No audio at listener:**
1. Check WebSocket connection: Browser console → Network tab
2. Check S3 files exist: `aws s3 ls s3://translation-audio-dev/sessions/{SESSION_ID}/`
3. Check for API_GATEWAY_ENDPOINT: Lambda logs should show notifications sent
4. Check browser console for S3AudioPlayer errors

**Poor audio quality:**
1. Check original chunks: Download and play WebM files
2. Check MP3 size: Should be >10KB for 2-3 seconds
3. Try different Polly voice or Engine (standard vs neural)

**High latency (>20s):**
1. Check Transcribe job duration in logs
2. Consider using Transcribe Streaming API instead of Jobs
3. Optimize batch window size (currently 3 seconds)

---

## Test 8: Multi-Language Testing

### Goal
Verify multiple listeners with different languages work simultaneously.

### Steps

1. **Start speaker (English):**
   - Create session with target languages: `["es", "fr", "de"]`
   - Start broadcasting

2. **Open 3 listener windows:**
   - Window 1: Spanish (es)
   - Window 2: French (fr)
   - Window 3: German (de)

3. **Verify each receives correct translation:**
   - Check browser consoles for `translatedAudio` messages
   - Verify `targetLanguage` matches selected language
   - Play audio and confirm language is correct

### Success Criteria
- ✅ All 3 listeners receive audio
- ✅ Each receives their selected language
- ✅ Audio plays without conflicts
- ✅ Latency similar across languages

---

## Monitoring Commands

### Real-Time Monitoring

**1. Watch CloudWatch Logs (all functions):**
```bash
# In separate terminals
./scripts/tail-lambda-logs.sh kvs-stream-writer-dev
./scripts/tail-lambda-logs.sh s3-audio-consumer-dev  
./scripts/tail-lambda-logs.sh audio-processor-dev
```

**2. Monitor S3 buckets:**
```bash
# Watch chunks being created
watch -n 1 'aws s3 ls s3://low-latency-audio-dev/sessions/ --recursive | wc -l'

# Watch translated audio
watch -n 2 'aws s3 ls s3://translation-audio-dev/sessions/ --recursive | tail -20'
```

**3. Monitor Lambda invocations:**
```bash
# Consumer invocations (last 5 minutes)
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=s3-audio-consumer-dev \
  --start-time $(date -u -v-5M +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum

# Processor invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=audio-processor \
  --start-time $(date -u -v-5M +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum
```

### Performance Metrics

**Check latency at each stage:**
```bash
# 1. Chunk upload (Phase 2)
aws logs filter-log-events \
  --log-group-name /aws/lambda/kvs-stream-writer-dev \
  --filter-pattern "Processing latency" \
  --start-time $(date -u -v-10M +%s)000 \
  | jq -r '.events[].message'

# 2. Consumer processing
aws logs filter-log-events \
  --log-group-name /aws/lambda/s3-audio-consumer-dev \
  --filter-pattern "batch" \
  --start-time $(date -u -v-10M +%s)000 \
  | jq -r '.events[].message'

# 3. Transcription time
aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor \
  --filter-pattern "Transcription complete" \
  --start-time $(date -u -v-10M +%s)000 \
  | jq -r '.events[].message'
```

---

## Verification Checklist

### Infrastructure ✅
- [x] s3-audio-consumer-dev Lambda deployed
- [x] ffmpeg-layer-dev attached
- [x] translation-audio-dev bucket created
- [x] S3 event notification configured
- [x] DynamoDB GSI: sessionId-targetLanguage-index exists

### Permissions ✅
- [x] Transcribe: StartTranscriptionJob, GetTranscriptionJob, DeleteTranscriptionJob
- [x] Translate: TranslateText
- [x] Polly: SynthesizeSpeech
- [x] S3: PutObject/GetObject on both buckets
- [x] API Gateway: ManageConnections
- [x] DynamoDB: Query on Connections table with GSI

### Environment Variables ✅
- [x] S3_BUCKET_NAME: translation-audio-dev
- [x] AUDIO_BUCKET_NAME: low-latency-audio-dev
- [x] CONNECTIONS_TABLE: Connections-dev
- [x] API_GATEWAY_ENDPOINT: wss://2y19uvhyq5.execute-api.us-east-1.amazonaws.com/prod
- [x] PRESIGNED_URL_EXPIRATION: 600

### Frontend ✅
- [x] S3AudioPlayer.ts created
- [x] ListenerService.ts updated (WebRTC removed)
- [x] translatedAudio WebSocket handler added
- [x] Listener app builds without errors

### AWS APIs ✅
- [x] Transcribe integration implemented
- [x] Translate integration implemented
- [x] Polly TTS integration implemented
- [x] WebSocket notification implemented

---

## Expected Log Flow

### Successful Processing Sequence:

```
[kvs-stream-writer]
→ "Received audio chunk for session {SESSION_ID}"
→ "Wrote 550 bytes to S3: sessions/{SESSION_ID}/chunks/{TS}.webm"

[s3-audio-consumer]  
→ "Processing new chunk: s3://low-latency-audio-dev/sessions/{SESSION_ID}/chunks/{TS}.webm"
→ "Found 12 chunks for session {SESSION_ID}"
→ "Processing batch 1/1 with 12 chunks"
→ "Downloaded chunk 1/12"
→ "Concatenated 12 chunks to /tmp/{UUID}/concatenated.webm"
→ "Converted to PCM: /tmp/{UUID}/audio.pcm"
→ "Converted batch to PCM: 96000 bytes"
→ "Invoking audio_processor for session {SESSION_ID}, batch 0, duration 3.00s"

[audio-processor]
→ "Processing PCM batch from s3_audio_consumer"
→ "Decoded PCM audio: 96000 bytes, 16000Hz"
→ "Started transcription job: transcribe-{SESSION_ID}-0-{UUID}"
→ "Transcription complete: 'Hello this is a test...'"
→ "Translated to es: 'Hola esto es una prueba...'"
→ "Generated TTS for es: 32456 bytes"
→ "Stored TTS audio in S3: sessions/{SESSION_ID}/translated/es/{TS}.mp3"
→ "Notified 1/1 listeners for es"
```

---

## Performance Benchmarks

### Target Latencies:
| Stage | Target | Measured |
|-------|--------|----------|
| Chunk upload | 200ms | Test to measure |
| S3 event trigger | <1s | Test to measure |
| Batch aggregation | 100ms | Test to measure |
| FFmpeg conversion | 2s | Test to measure |
| Transcription | 5-30s | Depends on audio length |
| Translation | 500ms | Per language |
| TTS generation | 1-2s | Per language |
| S3 upload | 100ms | Test to measure |
| WebSocket notify | 50ms | Test to measure |
| **Total End-to-End** | **<15s** | **Measure in test** |

### How to Measure:
```bash
# Extract timestamps from logs
START_TIME=$(aws logs filter-log-events \
  --log-group-name /aws/lambda/kvs-stream-writer-dev \
  --filter-pattern "Wrote" \
  --start-time $(date -u -v-5M +%s)000 \
  --max-items 1 \
  | jq -r '.events[0].timestamp')

END_TIME=$(aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor \
  --filter-pattern "Notified.*listeners" \
  --start-time $START_TIME \
  --max-items 1 \
  | jq -r '.events[0].timestamp')

# Calculate latency in seconds
echo "scale=2; ($END_TIME - $START_TIME) / 1000" | bc
```

---

## Common Issues & Solutions

### Issue 1: "No listeners found for {language}"

**Cause:** No active WebSocket connections for that language  
**Solution:**
1. Verify listener joined with correct language
2. Check Connections table:
   ```bash
   aws dynamodb scan --table-name Connections-dev \
     --filter-expression "sessionId = :sid" \
     --expression-attribute-values '{":sid":{"S":"YOUR_SESSION_ID"}}'
   ```
3. Ensure `targetLanguage` field is set in connection record

### Issue 2: "API_GATEWAY_ENDPOINT not set"

**Cause:** Environment variable missing  
**Solution:**
1. Already configured in deployment
2. Verify: `aws lambda get-function-configuration --function-name audio-processor`
3. Should show: `wss://2y19uvhyq5.execute-api.us-east-1.amazonaws.com/prod`

### Issue 3: Transcription job times out

**Cause:** Audio too long or Transcribe slow  
**Solution:**
1. Reduce batch window: `BATCH_WINDOW_SECONDS=2` in s3_audio_consumer
2. Consider Transcribe Streaming API instead of Jobs
3. Check audio format is correct (PCM, 16kHz, mono)

### Issue 4: TTS generates silent audio

**Cause:** create_silent_mp3() fallback triggered  
**Solution:**
1. Check logs for "TTS failed"
2. Verify Polly voice exists for language
3. Check text is not empty
4. Try standard engine instead of neural

---

## Quick Smoke Test

**5-Minute verification:**

```bash
# 1. Upload test chunk
echo "test" > /tmp/test.webm
aws s3 cp /tmp/test.webm s3://low-latency-audio-dev/sessions/smoke-test/chunks/$(date +%s)000.webm

# 2. Wait 3 seconds, check consumer triggered
sleep 3
aws logs tail /aws/lambda/s3-audio-consumer-dev --since 1m

# 3. Check if processor was invoked
aws logs tail /aws/lambda/audio-processor --since 1m | grep "Processing PCM batch"

# 4. Check S3 for results
aws s3 ls s3://translation-audio-dev/sessions/smoke-test/ --recursive

# Success if:
# - Consumer shows "Found X chunks"
# - Processor shows "Processing PCM batch"
# - Translation bucket has MP3 files
```

---

## Next Steps After Testing

### If All Tests Pass:
1. Document measured latencies
2. Update IMPLEMENTATION_STATUS.md with "Phase 3 COMPLETE"
3. Create Phase 4 plan (optimization, monitoring, UI improvements)
4. Consider production deployment

### If Tests Fail:
1. Check specific test section above for troubleshooting
2. Review CloudWatch logs for errors
3. Verify all permissions are correctly set
4. Test components in isolation before end-to-end

### Performance Optimization:
1. **If latency >15s:**
   - Switch to Transcribe Streaming API
   - Reduce batch window to 2 seconds
   - Parallelize Translate calls

2. **If errors occur:**
   - Add retry logic with exponential backoff
   - Implement circuit breaker pattern
   - Add dead letter queues

3. **If cost too high:**
   - Use standard Polly engine
   - Cache translations for common phrases
   - Implement request deduplication

---

## Production Readiness Checklist

Before deploying to production:

### Security:
- [ ] Restrict S3 CORS to specific domains
- [ ] Enable CloudTrail logging
- [ ] Add WAF rules for API Gateway
- [ ] Implement rate limiting per user
- [ ] Add encryption at rest for all data

### Reliability:
- [ ] Add error retry logic (currently partial)
- [ ] Implement circuit breakers
- [ ] Add dead letter queues for failed messages
- [ ] Set up CloudWatch alarms for all metrics
- [ ] Create runbook for incident response

### Performance:
- [ ] Load test with 10+ concurrent sessions
- [ ] Measure latency under load
- [ ] Optimize batch sizes based on measurements
- [ ] Consider Transcribe Streaming for lower latency
- [ ] Add caching for common translations

### Monitoring:
- [ ] CloudWatch dashboard for all metrics
- [ ] X-Ray tracing for request flows
- [ ] Custom metrics for business KPIs
- [ ] Alerts to on-call team
- [ ] Log aggregation and search

### Cost Optimization:
- [ ] Set up cost alerts
- [ ] Review Transcribe/Translate/Polly usage
- [ ] Implement caching strategies
- [ ] Consider reserved capacity for predictable load
- [ ] Auto-cleanup of old S3 objects

---

## Support & Debugging

### Get Help:
1. Check `CHECKPOINT_PHASE3_COMPLETE.md` for known issues
2. Review AWS service limits and quotas
3. Check AWS service health dashboard
4. Review CloudWatch Logs Insights queries

### Useful CloudWatch Insights Queries:

**Find errors:**
```
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 20
```

**Track latency:**
```
fields @timestamp, @message
| filter @message like /latency|duration/
| parse @message /latency:? *(?<latency>\d+)/
| stats avg(latency), max(latency), min(latency)
```

**Count successful translations:**
```
fields @timestamp, @message
| filter @message like /Translated to/
| stats count() by targetLanguage
```

---

## Summary

Phase 3 is now **fully implemented and deployed**:
- ✅ S3 audio consumer aggregates and converts chunks
- ✅ AWS Transcribe transcribes audio to text
- ✅ AWS Translate translates to target languages  
- ✅ AWS Polly generates speech from translations
- ✅ Listeners receive audio via S3 presigned URLs
- ✅ Frontend builds and ready for testing

**Start with Test 1 and work through systematically.**

Good luck with testing! 🚀
