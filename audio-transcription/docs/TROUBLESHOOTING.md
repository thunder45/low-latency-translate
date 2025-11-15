# WebSocket Audio Integration Troubleshooting Guide

## Overview

This guide provides solutions to common issues in the WebSocket Audio Integration system, including debugging steps, CloudWatch Logs Insights queries, and resolution procedures.

## Table of Contents

1. [Transcribe Stream Failures](#transcribe-stream-failures)
2. [Translation Pipeline Invocation Failures](#translation-pipeline-invocation-failures)
3. [Emotion Detection Issues](#emotion-detection-issues)
4. [Audio Quality Problems](#audio-quality-problems)
5. [Performance Issues](#performance-issues)
6. [CloudWatch Logs Insights Queries](#cloudwatch-logs-insights-queries)

## Transcribe Stream Failures

### Issue: Stream Initialization Fails

**Symptoms**:
- Audio chunks not being transcribed
- Error logs: "Failed to initialize Transcribe stream"
- No transcript events received

**Common Causes**:
1. Invalid source language code
2. IAM permissions missing
3. Transcribe service unavailable
4. Network connectivity issues

**Debugging Steps**:

1. **Check CloudWatch Logs**:
```
fields @timestamp, @message, level, session_id, error
| filter level = "ERROR" and @message like /Transcribe stream/
| sort @timestamp desc
| limit 50
```

2. **Verify IAM Permissions**:
```bash
# Check Lambda execution role
aws iam get-role-policy \
  --role-name AudioProcessorLambdaRole \
  --policy-name TranscribePolicy
```

Expected permissions:
```json
{
  "Effect": "Allow",
  "Action": ["transcribe:StartStreamTranscription"],
  "Resource": "*"
}
```

3. **Test Transcribe Service**:
```bash
# Test if Transcribe is available in region
aws transcribe list-transcription-jobs --region us-east-1
```

4. **Verify Language Code**:
```python
# Valid language codes
SUPPORTED_LANGUAGES = [
    'en-US', 'es-ES', 'fr-FR', 'de-DE', 'it-IT',
    'pt-BR', 'ja-JP', 'ko-KR', 'zh-CN', 'ar-SA'
]
```

**Resolution**:

1. **Fix IAM Permissions**:
```python
# Update CDK stack
audio_processor_function.add_to_role_policy(
    iam.PolicyStatement(
        actions=['transcribe:StartStreamTranscription'],
        resources=['*']
    )
)
```

2. **Validate Language Code**:
```python
def validate_language_code(language: str) -> bool:
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {language}")
    return True
```

3. **Add Retry Logic**:
```python
async def initialize_stream_with_retry(self, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await self.initialize_stream()
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise
```

### Issue: Stream Disconnects Unexpectedly

**Symptoms**:
- Transcription stops mid-session
- Error logs: "Error in Transcribe event loop"
- Partial transcripts not received

**Common Causes**:
1. Network timeout
2. Transcribe service limits exceeded
3. Audio stream interrupted
4. Lambda timeout

**Debugging Steps**:

1. **Check Stream Duration**:
```
fields @timestamp, session_id, operation, duration_ms
| filter operation = "transcribe_stream_active"
| stats max(duration_ms) as max_duration by session_id
```

2. **Check for Timeouts**:
```
fields @timestamp, @message, session_id
| filter @message like /timeout/ or @message like /disconnect/
| sort @timestamp desc
```

3. **Monitor Lambda Duration**:
```
fields @timestamp, @duration, session_id
| filter @duration > 50000  # More than 50 seconds
| sort @timestamp desc
```

**Resolution**:

1. **Implement Reconnection Logic**:
```python
async def _reconnect(self):
    logger.warning(f"Reconnecting Transcribe stream for session {self.session_id}")
    
    # Close existing stream
    await self.close_stream()
    
    # Wait before reconnecting
    await asyncio.sleep(1)
    
    # Reinitialize
    success = await self.initialize_stream()
    
    if success:
        logger.info(f"Transcribe stream reconnected for session {self.session_id}")
    else:
        logger.error(f"Failed to reconnect Transcribe stream for session {self.session_id}")
```

2. **Add Heartbeat Mechanism**:
```python
async def _send_heartbeat(self):
    while self.is_active:
        await asyncio.sleep(30)
        # Send empty audio frame to keep stream alive
        await self.stream.input_stream.send_audio_event(
            audio_chunk=b'\x00' * 3200
        )
```

3. **Increase Lambda Timeout**:
```python
# In CDK stack
audio_processor_function = lambda_.Function(
    self, 'AudioProcessor',
    timeout=Duration.seconds(60),  # Increase from 30s
    memory_size=1024
)
```

### Issue: Partial Results Not Received

**Symptoms**:
- Only final transcripts received
- High latency (>5 seconds)
- Missing stability scores

**Common Causes**:
1. Partial results not enabled
2. Stability threshold too high
3. Audio quality too low

**Debugging Steps**:

1. **Check Stream Configuration**:
```python
# Verify partial results enabled
logger.debug(f"Stream config: {self.stream.config}")
```

2. **Monitor Stability Scores**:
```
fields @timestamp, session_id, stability_score, is_partial
| filter is_partial = true
| stats avg(stability_score) as avg_stability by session_id
```

**Resolution**:

1. **Enable Partial Results**:
```python
self.stream = await TranscribeStreamingClient(
    region=os.environ.get('AWS_REGION', 'us-east-1')
).start_stream_transcription(
    language_code=self.source_language,
    media_sample_rate_hz=16000,
    media_encoding='pcm',
    enable_partial_results_stabilization=True,  # Enable
    partial_results_stability='high'  # Set stability level
)
```

2. **Adjust Stability Threshold**:
```python
# Lower threshold for faster results
STABILITY_THRESHOLD = 0.75  # Down from 0.85
```

## Translation Pipeline Invocation Failures

### Issue: Lambda Invocation Fails

**Symptoms**:
- Transcripts not reaching Translation Pipeline
- Error logs: "Failed to invoke Translation Pipeline"
- No translated audio for listeners

**Common Causes**:
1. Lambda function not found
2. IAM permissions missing
3. Payload too large
4. Lambda throttling

**Debugging Steps**:

1. **Check Invocation Errors**:
```
fields @timestamp, @message, session_id, error_code
| filter @message like /Translation Pipeline/ and level = "ERROR"
| sort @timestamp desc
| limit 50
```

2. **Verify Lambda Exists**:
```bash
aws lambda get-function \
  --function-name TranslationProcessor \
  --region us-east-1
```

3. **Check IAM Permissions**:
```bash
aws iam get-role-policy \
  --role-name AudioProcessorLambdaRole \
  --policy-name LambdaInvokePolicy
```

4. **Monitor Throttling**:
```
fields @timestamp, session_id, attempts
| filter @message like /retry/
| stats count() as retry_count by session_id
```

**Resolution**:

1. **Fix IAM Permissions**:
```python
# Grant invoke permission
translation_pipeline_function.grant_invoke(audio_processor_function)
```

2. **Reduce Payload Size**:
```python
def process(self, text, session_id, ...):
    # Truncate long transcripts
    if len(text) > 5000:
        text = text[:5000]
        logger.warning(f"Truncated transcript for session {session_id}")
    
    payload = {
        'sessionId': session_id,
        'transcriptText': text,
        # ... other fields
    }
```

3. **Implement Circuit Breaker**:
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
            raise
```

### Issue: Retry Logic Not Working

**Symptoms**:
- Single failure causes permanent loss
- No retry attempts logged
- Immediate failure on transient errors

**Debugging Steps**:

1. **Check Retry Attempts**:
```
fields @timestamp, session_id, attempts, error
| filter @message like /retry/
| sort @timestamp desc
```

2. **Verify Error Types**:
```
fields @timestamp, error_code, error_message
| filter level = "ERROR"
| stats count() by error_code
```

**Resolution**:

1. **Implement Exponential Backoff**:
```python
def process_with_backoff(self, text, session_id, ...):
    for attempt in range(self.max_retries + 1):
        try:
            response = self.lambda_client.invoke(...)
            return True
        except ClientError as e:
            if attempt < self.max_retries:
                # Exponential backoff: 100ms, 200ms, 400ms
                delay = self.retry_delay_ms * (2 ** attempt) / 1000
                time.sleep(delay)
                continue
            else:
                logger.error(f"Failed after {attempt + 1} attempts")
                return False
```

2. **Add Retry Metrics**:
```python
metrics_emitter.emit_metric(
    'TranslationPipelineRetries',
    attempt,
    'Count',
    dimensions={'SessionId': session_id}
)
```

## Emotion Detection Issues

### Issue: Emotion Extraction Fails

**Symptoms**:
- Default neutral emotion values used
- Error logs: "Error extracting emotion dynamics"
- Flat, monotone synthesized speech

**Common Causes**:
1. Invalid audio format
2. librosa import error
3. Insufficient memory
4. Audio too short

**Debugging Steps**:

1. **Check Emotion Extraction Errors**:
```
fields @timestamp, session_id, error
| filter @message like /emotion/ and level = "ERROR"
| sort @timestamp desc
```

2. **Monitor Memory Usage**:
```
fields @timestamp, @maxMemoryUsed, session_id
| filter @maxMemoryUsed > 900000000  # >900MB
| sort @timestamp desc
```

3. **Verify Audio Format**:
```python
# Check audio properties
audio_array = np.frombuffer(audio_data, dtype=np.int16)
logger.debug(f"Audio shape: {audio_array.shape}, dtype: {audio_array.dtype}")
```

**Resolution**:

1. **Increase Lambda Memory**:
```python
# In CDK stack
audio_processor_function = lambda_.Function(
    self, 'AudioProcessor',
    memory_size=1536,  # Increase from 1024MB
    timeout=Duration.seconds(60)
)
```

2. **Add Input Validation**:
```python
def process_audio_chunk_with_emotion(session_id, audio_data):
    # Validate audio length
    if len(audio_data) < 3200:  # Less than 100ms
        logger.warning(f"Audio chunk too short: {len(audio_data)} bytes")
        return default_emotion()
    
    # Validate audio format
    try:
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
    except ValueError as e:
        logger.error(f"Invalid audio format: {e}")
        return default_emotion()
    
    # Extract emotion
    try:
        return emotion_orchestrator.process_audio_chunk(audio_array, 16000)
    except Exception as e:
        logger.error(f"Emotion extraction failed: {e}")
        return default_emotion()
```

3. **Optimize librosa Usage**:
```python
# Use lightweight features only
def extract_emotion_lightweight(audio_array, sample_rate):
    # Volume (RMS energy) - fast
    volume = np.sqrt(np.mean(audio_array ** 2))
    
    # Speaking rate (zero crossing rate) - fast
    zcr = np.mean(librosa.feature.zero_crossing_rate(audio_array))
    
    # Energy (spectral centroid) - moderate
    spectral_centroid = np.mean(librosa.feature.spectral_centroid(
        y=audio_array,
        sr=sample_rate
    ))
    
    return {
        'volume': normalize_volume(volume),
        'rate': normalize_rate(zcr),
        'energy': normalize_energy(spectral_centroid)
    }
```

### Issue: Emotion Cache Not Working

**Symptoms**:
- Emotion data not included in payloads
- Cache misses logged
- Inconsistent emotion across transcripts

**Debugging Steps**:

1. **Check Cache Size**:
```
fields @timestamp, cache_size
| filter @message like /emotion cache/
| sort @timestamp desc
```

2. **Monitor Cache Hits/Misses**:
```
fields @timestamp, session_id, cache_hit
| filter @message like /emotion/
| stats count() by cache_hit
```

**Resolution**:

1. **Implement TTL for Cache**:
```python
emotion_cache = {}
cache_timestamps = {}

def cache_emotion(session_id, emotion_data):
    emotion_cache[session_id] = emotion_data
    cache_timestamps[session_id] = time.time()

def get_cached_emotion(session_id):
    # Check if cached and not expired
    if session_id in emotion_cache:
        age = time.time() - cache_timestamps[session_id]
        if age < 60:  # 60 second TTL
            return emotion_cache[session_id]
        else:
            # Expired, remove from cache
            del emotion_cache[session_id]
            del cache_timestamps[session_id]
    
    return default_emotion()
```

2. **Add Cache Metrics**:
```python
metrics_emitter.emit_metric(
    'EmotionCacheSize',
    len(emotion_cache),
    'Count'
)

metrics_emitter.emit_metric(
    'EmotionCacheHitRate',
    cache_hits / (cache_hits + cache_misses),
    'Percent'
)
```

## Audio Quality Problems

### Issue: Audio Distortion

**Symptoms**:
- Clipping detected
- Poor transcription accuracy
- Listener complaints about audio quality

**Debugging Steps**:

1. **Check Audio Quality Metrics**:
```
fields @timestamp, session_id, snr, clipping_detected
| filter clipping_detected = true
| sort @timestamp desc
```

2. **Monitor SNR Values**:
```
fields @timestamp, session_id, snr
| stats avg(snr) as avg_snr, min(snr) as min_snr by session_id
```

**Resolution**:

1. **Warn Speaker**:
```python
if audio_quality.clipping_detected:
    send_warning_to_speaker(
        session_id,
        'AUDIO_CLIPPING',
        'Audio distortion detected. Please reduce microphone volume.'
    )
```

2. **Implement Auto-Gain Control**:
```python
def apply_auto_gain(audio_data):
    audio_array = np.frombuffer(audio_data, dtype=np.int16)
    
    # Calculate current RMS
    rms = np.sqrt(np.mean(audio_array ** 2))
    
    # Target RMS (50% of max)
    target_rms = 16384  # 50% of 32768
    
    # Calculate gain
    if rms > 0:
        gain = target_rms / rms
        # Limit gain to prevent over-amplification
        gain = min(gain, 2.0)
        
        # Apply gain
        audio_array = (audio_array * gain).astype(np.int16)
    
    return audio_array.tobytes()
```

## Performance Issues

### Issue: High Latency

**Symptoms**:
- End-to-end latency >5 seconds
- Listener complaints about delay
- Transcription lag

**Debugging Steps**:

1. **Measure Each Stage**:
```
fields @timestamp, operation, duration_ms
| filter operation in ["audio_processing", "transcribe_forward", "translation_invoke"]
| stats avg(duration_ms) as avg_latency by operation
```

2. **Identify Bottlenecks**:
```
fields @timestamp, operation, duration_ms
| filter duration_ms > 1000  # >1 second
| sort duration_ms desc
| limit 20
```

**Resolution**:

1. **Optimize Audio Processing**:
```python
# Use faster audio validation
def validate_audio_fast(audio_data):
    # Quick length check
    if len(audio_data) != 3200:
        return False
    
    # Skip detailed validation for performance
    return True
```

2. **Reduce Emotion Extraction Overhead**:
```python
# Make emotion detection optional
if os.getenv('ENABLE_EMOTION_DETECTION', 'false') == 'true':
    emotion_data = extract_emotion(audio_data)
else:
    emotion_data = default_emotion()
```

3. **Use Provisioned Concurrency**:
```python
# In CDK stack
audio_processor_function.add_alias(
    'live',
    provisioned_concurrent_executions=10  # Eliminate cold starts
)
```

## CloudWatch Logs Insights Queries

### Find All Errors in Last Hour

```
fields @timestamp, @message, level, session_id, error_code
| filter level = "ERROR"
| filter @timestamp > ago(1h)
| sort @timestamp desc
| limit 100
```

### Track Session Lifecycle

```
fields @timestamp, operation, session_id, message
| filter session_id = "golden-eagle-427"
| sort @timestamp asc
```

### Measure Latency by Operation

```
fields @timestamp, operation, duration_ms
| filter operation in ["audio_processing", "transcribe_forward", "translation_invoke"]
| stats avg(duration_ms) as avg_latency, p95(duration_ms) as p95_latency by operation
```

### Find Slow Requests

```
fields @timestamp, session_id, operation, duration_ms
| filter duration_ms > 1000
| sort duration_ms desc
| limit 50
```

### Monitor Retry Attempts

```
fields @timestamp, session_id, operation, attempts
| filter attempts > 1
| stats count() as retry_count, avg(attempts) as avg_attempts by operation
```

### Track Emotion Extraction Performance

```
fields @timestamp, session_id, emotion_extraction_ms
| filter emotion_extraction_ms > 0
| stats avg(emotion_extraction_ms) as avg_time, max(emotion_extraction_ms) as max_time
```

### Find Translation Pipeline Failures

```
fields @timestamp, session_id, error_code, error_message
| filter @message like /Translation Pipeline/ and level = "ERROR"
| stats count() by error_code
```

### Monitor Buffer Overflow

```
fields @timestamp, session_id, buffer_size, buffer_overflow
| filter buffer_overflow = true
| sort @timestamp desc
```

### Track Transcribe Stream Reconnections

```
fields @timestamp, session_id, operation
| filter operation = "transcribe_reconnect"
| stats count() as reconnect_count by session_id
```

### Analyze Audio Quality Issues

```
fields @timestamp, session_id, snr, clipping_detected, echo_detected
| filter clipping_detected = true or echo_detected = true or snr < 10
| sort @timestamp desc
```

## Escalation Procedures

### When to Escalate

**Immediate Escalation** (page on-call):
- System-wide outage (>50% of sessions failing)
- Data loss detected
- Security incident
- AWS service outage affecting multiple regions

**Escalate Within 1 Hour**:
- Single region degradation
- Elevated error rate (>5%)
- Performance degradation (latency >2x normal)
- Multiple customer complaints

**Escalate Within 4 Hours**:
- Isolated session failures
- Non-critical feature degradation
- Monitoring alert threshold breached

### Escalation Contacts

1. **On-Call Engineer**: Check PagerDuty rotation
2. **Team Lead**: [Contact info]
3. **AWS Support**: Premium support case
4. **Security Team**: For security incidents

## Additional Resources

- [Integration Points Documentation](./INTEGRATION_POINTS.md)
- [AWS Transcribe Troubleshooting](https://docs.aws.amazon.com/transcribe/latest/dg/troubleshooting.html)
- [AWS Lambda Troubleshooting](https://docs.aws.amazon.com/lambda/latest/dg/lambda-troubleshooting.html)
- [CloudWatch Logs Insights Query Syntax](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html)
