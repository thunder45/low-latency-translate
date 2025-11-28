# Phase 2: Backend KVS Stream Writer Implementation Guide

## Overview
Create backend Lambda to receive WebM chunks, convert to PCM, and write to KVS Stream.

**Duration:** 6-8 hours  
**Prerequisites:** Phase 1 complete (MediaRecorder working)  
**Goal:** Audio chunks written to KVS Stream, verifiable via AWS CLI

---

## Architecture Flow

```
connection_handler Lambda
    ↓ Receives audioChunk via WebSocket
    ↓ Invokes async
kvs_stream_writer Lambda
    ↓ Decode base64 → WebM binary
    ↓ Convert WebM → PCM (ffmpeg)
    ↓ PutMedia → KVS Stream
KVS Stream (session-{id})
    ↓ Stores fragments
    ↓ EventBridge event fired
kvs_stream_consumer Lambda
    ↓ Triggered by EventBridge
    ↓ GetMedia from stream
    ↓ Extract audio chunks
    ↓ Forward to audio_processor
```

---

## Step 1: Create kvs_stream_writer Lambda

**Directory:** `session-management/lambda/kvs_stream_writer/`

### File 1: handler.py

```python
"""
KVS Stream Writer Lambda
Receives WebM audio chunks, converts to PCM, and writes to KVS Stream.

Architecture:
- Triggered by connection_handler Lambda (async invocation)
- Receives base64-encoded WebM chunks
- Converts to PCM using ffmpeg
- Writes to KVS Stream via PutMedia API
- Creates streams on-demand
"""
import json
import logging
import os
import time
import base64
import boto3
import subprocess
import tempfile
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
kvs_client = boto3.client('kinesisvideo')
dynamodb = boto3.resource('dynamodb')

# Configuration
STAGE = os.environ.get('STAGE', 'dev')
SESSIONS_TABLE_NAME = os.environ.get('SESSIONS_TABLE_NAME', f'low-latency-sessions-{STAGE}')
KVS_STREAM_RETENTION_HOURS = int(os.environ.get('KVS_STREAM_RETENTION_HOURS', '1'))

# Cache for stream endpoints (reuse across invocations)
stream_endpoints_cache: Dict[str, str] = {}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for KVS stream writing.
    
    Event format:
    {
        "action": "writeToStream",
        "sessionId": "session-id",
        "audioData": "base64_webm_data...",
        "timestamp": 1732614567890,
        "format": "webm-opus",
        "chunkIndex": 42
    }
    """
    try:
        action = event.get('action', '')
        
        if action == 'writeToStream':
            return handle_write_to_stream(event, context)
        elif action == 'health_check':
            return handle_health_check(event, context)
        elif action == 'createStream':
            return handle_create_stream(event, context)
        else:
            logger.warning(f"Unknown action: {action}")
            return {'statusCode': 400, 'body': json.dumps({'error': 'Unknown action'})}
            
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}", exc_info=True)
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}


def handle_write_to_stream(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle writing audio chunk to KVS Stream.
    """
    start_time = time.time()
    
    try:
        session_id = event.get('sessionId', '')
        audio_data_base64 = event.get('audioData', '')
        chunk_index = event.get('chunkIndex', 0)
        audio_format = event.get('format', 'webm-opus')
        
        if not session_id or not audio_data_base64:
            logger.error("Missing required parameters: sessionId or audioData")
            return {'statusCode': 400, 'body': json.dumps({'error': 'Missing parameters'})}
        
        # Log every 40th chunk to avoid spam
        if chunk_index % 40 == 0:
            logger.info(
                f"[KVS_WRITER] Processing chunk {chunk_index} for session {session_id}",
                extra={
                    'session_id': session_id,
                    'chunk_index': chunk_index,
                    'format': audio_format
                }
            )
        
        # Decode base64 audio
        webm_data = base64.b64decode(audio_data_base64)
        
        if len(webm_data) == 0:
            logger.warning(f"Empty audio data for chunk {chunk_index}")
            return {'statusCode': 200, 'body': json.dumps({'message': 'Empty chunk skipped'})}
        
        # Convert WebM to PCM
        pcm_data = convert_webm_to_pcm(webm_data)
        
        if not pcm_data:
            logger.error(f"Failed to convert audio chunk {chunk_index}")
            return {'statusCode': 500, 'body': json.dumps({'error': 'Conversion failed'})}
        
        # Write to KVS Stream
        stream_name = f"session-{session_id}"
        success = write_to_kvs_stream(stream_name, pcm_data, session_id)
        
        if not success:
            logger.error(f"Failed to write chunk {chunk_index} to KVS Stream")
            return {'statusCode': 500, 'body': json.dumps({'error': 'KVS write failed'})}
        
        # Log timing for monitoring
        duration_ms = int((time.time() - start_time) * 1000)
        
        if chunk_index % 40 == 0:
            logger.info(
                f"[KVS_WRITER] Chunk {chunk_index} processed successfully",
                extra={
                    'session_id': session_id,
                    'chunk_index': chunk_index,
                    'duration_ms': duration_ms,
                    'webm_size': len(webm_data),
                    'pcm_size': len(pcm_data)
                }
            )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Chunk written successfully',
                'chunkIndex': chunk_index,
                'durationMs': duration_ms
            })
        }
        
    except Exception as e:
        logger.error(f"Error writing to stream: {str(e)}", exc_info=True)
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}


def convert_webm_to_pcm(webm_bytes: bytes) -> Optional[bytes]:
    """
    Convert WebM (Opus codec) to PCM using ffmpeg.
    
    Target format:
    - PCM 16-bit signed little-endian
    - 16kHz sample rate
    - Mono (1 channel)
    
    Args:
        webm_bytes: Input WebM audio data
        
    Returns:
        PCM audio bytes or None if conversion fails
    """
    webm_file = None
    pcm_file = None
    
    try:
        # Create temporary files
        webm_file = tempfile.NamedTemporaryFile(suffix='.webm', delete=False)
        webm_file.write(webm_bytes)
        webm_file.flush()
        webm_path = webm_file.name
        webm_file.close()
        
        pcm_path = webm_path + '.pcm'
        
        # Run ffmpeg conversion
        result = subprocess.run([
            'ffmpeg',
            '-i', webm_path,          # Input WebM file
            '-f', 's16le',            # Output format: PCM 16-bit little-endian
            '-acodec', 'pcm_s16le',   # Audio codec
            '-ar', '16000',           # Sample rate: 16kHz
            '-ac', '1',               # Channels: mono
            '-y',                     # Overwrite output
            pcm_path                  # Output file
        ], capture_output=True, timeout=5)
        
        if result.returncode != 0:
            logger.error(
                f"ffmpeg conversion failed: {result.stderr.decode('utf-8')}",
                extra={'returncode': result.returncode}
            )
            return None
        
        # Read PCM data
        with open(pcm_path, 'rb') as f:
            pcm_data = f.read()
        
        return pcm_data
        
    except subprocess.TimeoutExpired:
        logger.error("ffmpeg conversion timed out after 5 seconds")
        return None
    except Exception as e:
        logger.error(f"Error converting WebM to PCM: {str(e)}", exc_info=True)
        return None
    finally:
        # Clean up temporary files
        try:
            if webm_file and os.path.exists(webm_path):
                os.unlink(webm_path)
            if pcm_file and os.path.exists(pcm_path):
                os.unlink(pcm_path)
        except Exception as cleanup_error:
            logger.warning(f"Error cleaning up temp files: {str(cleanup_error)}")


def write_to_kvs_stream(stream_name: str, pcm_data: bytes, session_id: str) -> bool:
    """
    Write PCM audio to KVS Stream using PutMedia API.
    
    Args:
        stream_name: KVS stream name (session-{id})
        pcm_data: PCM audio bytes
        session_id: Session identifier
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure stream exists (create if needed)
        ensure_stream_exists(stream_name, session_id)
        
        # Get or cache data endpoint
        endpoint = stream_endpoints_cache.get(stream_name)
        
        if not endpoint:
            response = kvs_client.get_data_endpoint(
                StreamName=stream_name,
                APIName='PUT_MEDIA'
            )
            endpoint = response['DataEndpoint']
            stream_endpoints_cache[stream_name] = endpoint
            logger.info(f"Cached endpoint for stream {stream_name}: {endpoint}")
        
        # Create media client for the endpoint
        kvs_media_client = boto3.client('kinesis-video-media', endpoint_url=endpoint)
        
        # Put media to stream
        # Note: This is simplified - production should handle MKV container properly
        kvs_media_client.put_media(
            StreamName=stream_name,
            FragmentTimecodeType='ABSOLUTE',
            ProducerStartTimestamp=time.time(),
            Payload=pcm_data
        )
        
        return True
        
    except kvs_client.exceptions.ResourceNotFoundException:
        logger.error(f"KVS Stream not found: {stream_name}")
        # Try to create stream
        try:
            ensure_stream_exists(stream_name, session_id, force_create=True)
            # Retry write after creation
            return write_to_kvs_stream(stream_name, pcm_data, session_id)
        except Exception as create_error:
            logger.error(f"Failed to create stream: {str(create_error)}")
            return False
            
    except Exception as e:
        logger.error(f"Error writing to KVS Stream: {str(e)}", exc_info=True)
        return False


def ensure_stream_exists(stream_name: str, session_id: str, force_create: bool = False) -> bool:
    """
    Ensure KVS Stream exists, create if needed.
    
    Args:
        stream_name: Stream name
        session_id: Session identifier
        force_create: Force creation even if exists
        
    Returns:
        True if stream exists/created, False otherwise
    """
    try:
        if not force_create:
            # Check if stream exists
            try:
                kvs_client.describe_stream(StreamName=stream_name)
                return True  # Stream exists
            except kvs_client.exceptions.ResourceNotFoundException:
                pass  # Stream doesn't exist, create it
        
        # Create stream
        logger.info(f"Creating KVS Stream: {stream_name}")
        
        kvs_client.create_stream(
            DeviceName=stream_name,
            StreamName=stream_name,
            MediaType='audio/x-raw',  # PCM audio
            DataRetentionInHours=KVS_STREAM_RETENTION_HOURS,
            Tags={
                'Application': 'LowLatencyTranslation',
                'SessionId': session_id,
                'Stage': STAGE,
                'CreatedBy': 'kvs-stream-writer',
            }
        )
        
        logger.info(f"KVS Stream created successfully: {stream_name}")
        
        # Wait for stream to become active (max 10 seconds)
        for i in range(10):
            try:
                response = kvs_client.describe_stream(StreamName=stream_name)
                status = response['StreamInfo']['Status']
                
                if status == 'ACTIVE':
                    logger.info(f"Stream {stream_name} is ACTIVE")
                    return True
                    
                logger.info(f"Stream {stream_name} status: {status}, waiting...")
                time.sleep(1)
                
            except Exception as check_error:
                logger.warning(f"Error checking stream status: {str(check_error)}")
                time.sleep(1)
        
        logger.warning(f"Stream {stream_name} not ACTIVE after 10 seconds")
        return False
        
    except kvs_client.exceptions.ResourceInUseException:
        # Stream already exists
        logger.info(f"Stream {stream_name} already exists")
        return True
        
    except Exception as e:
        logger.error(f"Error ensuring stream exists: {str(e)}", exc_info=True)
        return False


def handle_health_check(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle health check requests."""
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'kvs_stream_writer healthy',
            'stage': STAGE,
            'timestamp': int(time.time() * 1000)
        })
    }


def handle_create_stream(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle explicit stream creation request."""
    try:
        session_id = event.get('sessionId', '')
        stream_name = f"session-{session_id}"
        
        success = ensure_stream_exists(stream_name, session_id, force_create=True)
        
        if success:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Stream created',
                    'streamName': stream_name
                })
            }
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to create stream'})
            }
            
    except Exception as e:
        logger.error(f"Error creating stream: {str(e)}", exc_info=True)
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
```

### File 2: requirements.txt

```txt
boto3>=1.28.0
```

**Note:** ffmpeg will be provided via Lambda Layer (see infrastructure section)

---

## Step 2: Create FFmpeg Lambda Layer

FFmpeg is needed for WebM → PCM conversion. We'll use a pre-built layer.

### Option A: Use Existing FFmpeg Layer (RECOMMENDED)

```bash
# Use ARN from Serverless FFmpeg project
# us-east-1: arn:aws:lambda:us-east-1:145266761615:layer:ffmpeg:4
```

### Option B: Build Custom FFmpeg Layer

```bash
# Create layer directory
mkdir -p lambda_layers/ffmpeg/bin

# Download static ffmpeg binary
cd lambda_layers/ffmpeg/bin
wget https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz
tar xf ffmpeg-git-amd64-static.tar.xz
mv ffmpeg-git-*-amd64-static/ffmpeg .
mv ffmpeg-git-*-amd64-static/ffprobe .
chmod +x ffmpeg ffprobe
rm -rf ffmpeg-git-*

# Create layer
cd lambda_layers/ffmpeg
zip -r ../ffmpeg-layer.zip .

# Upload to AWS
aws lambda publish-layer-version \
  --layer-name ffmpeg-layer-dev \
  --zip-file fileb://../ffmpeg-layer.zip \
  --compatible-runtimes python3.11 \
  --region us-east-1
```

---

## Step 3: Update CDK Stack

**File:** `session-management/infrastructure/stacks/session_management_stack.py`

Add kvs_stream_writer Lambda:

```python
# After connection_handler Lambda definition

# ========================================
# KVS Stream Writer Lambda
# ========================================

# FFmpeg Layer (use existing public layer or create custom)
ffmpeg_layer_arn = f"arn:aws:lambda:{self.region}:145266761615:layer:ffmpeg:4"
ffmpeg_layer = _lambda.LayerVersion.from_layer_version_arn(
    self, 'FFmpegLayer', ffmpeg_layer_arn
)

kvs_stream_writer = _lambda.Function(
    self,
    'KVSStreamWriter',
    runtime=_lambda.Runtime.PYTHON_3_11,
    handler='handler.lambda_handler',
    code=_lambda.Code.from_asset(
        '../lambda/kvs_stream_writer',
        exclude=['__pycache__', '*.pyc', '.pytest_cache', 'tests']
    ),
    layers=[shared_layer, ffmpeg_layer],  # Add ffmpeg layer
    timeout=Duration.seconds(60),
    memory_size=1024,  # 1GB for ffmpeg conversion
    environment={
        'STAGE': config['stage'],
        'SESSIONS_TABLE_NAME': sessions_table.table_name,
        'KVS_STREAM_RETENTION_HOURS': '1',
        'LOG_LEVEL': 'INFO',
    },
    log_retention=logs.RetentionDays.ONE_WEEK,
    description='Receives WebM chunks and writes to KVS Stream',
)

# Grant KVS permissions
kvs_stream_writer.add_to_role_policy(
    iam.PolicyStatement(
        sid='KVSStreamManagement',
        actions=[
            'kinesisvideo:CreateStream',
            'kinesisvideo:DescribeStream',
            'kinesisvideo:GetDataEndpoint',
            'kinesisvideo:TagStream',
        ],
        resources=[
            f'arn:aws:kinesisvideo:{self.region}:{self.account}:stream/session-*/*'
        ],
    )
)

kvs_stream_writer.add_to_role_policy(
    iam.PolicyStatement(
        sid='KVSPutMedia',
        actions=[
            'kinesisvideo:PutMedia',
        ],
        resources=[
            f'arn:aws:kinesisvideo:{self.region}:{self.account}:stream/session-*/*'
        ],
    )
)

# Grant DynamoDB read access (for session metadata)
sessions_table.grant_read_data(kvs_stream_writer)

# Grant connection_handler permission to invoke kvs_stream_writer
kvs_stream_writer.grant_invoke(connection_handler)

# Add environment variable to connection_handler
connection_handler.add_environment(
    'KVS_STREAM_WRITER_FUNCTION',
    kvs_stream_writer.function_name
)
```

---

## Step 4: Fix kvs_stream_consumer Numpy Dependency

**File:** `session-management/lambda/kvs_stream_consumer/handler.py`

### Problem:
```python
try:
    import numpy as np
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "numpy"])
    import numpy as np
```
This fails in Lambda runtime (read-only filesystem).

### Solution 1: Remove NumPy (RECOMMENDED)

Replace the synthetic audio generation with simple approach:

```python
def _extract_audio_from_kvs_chunk(chunk_data: bytes) -> Optional[bytes]:
    """
    Extract audio data from KVS media chunk.
    
    For traditional KVS Stream, chunks are already in PCM format.
    No conversion needed - just return the data.
    
    Args:
        chunk_data: Raw KVS media chunk (PCM)
        
    Returns:
        PCM audio bytes or None if extraction fails
    """
    try:
        # With traditional KVS Stream (not WebRTC), data is PCM
        # Just validate and return
        if len(chunk_data) < 100:  # Too small
            return None
        
        logger.debug(f"Extracted {len(chunk_data)} bytes of PCM audio from chunk")
        
        return chunk_data
        
    except Exception as e:
        logger.error(f"Error extracting audio from KVS chunk: {e}", exc_info=True)
        return None
```

### Solution 2: Use Pre-built NumPy Layer (If needed)

```python
# In CDK stack, add NumPy layer
numpy_layer = _lambda.LayerVersion.from_layer_version_arn(
    self,
    'NumpyLayer',
    'arn:aws:lambda:us-east-1:770693421928:layer:Klayers-p311-numpy:5'
)

# Add to kvs_stream_consumer
kvs_stream_consumer = _lambda.Function(
    ...,
    layers=[shared_layer, numpy_layer],
    ...
)
```

But for traditional KVS Stream, NumPy is not needed at all.

---

## Step 5: Deploy EventBridge Rule

**File:** `session-management/infrastructure/stacks/session_management_stack.py`

Add EventBridge rule to trigger kvs_stream_consumer:

```python
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets

# After kvs_stream_consumer definition

# ========================================
# EventBridge Rule for KVS Stream Events
# ========================================

# Rule to trigger kvs_stream_consumer when KVS Stream receives data
kvs_stream_rule = events.Rule(
    self,
    'KVSStreamConsumerTrigger',
    rule_name=f'kvs-stream-consumer-trigger-{config["stage"]}',
    description='Trigger kvs_stream_consumer when KVS Stream has new fragments',
    event_pattern=events.EventPattern(
        source=['aws.kinesisvideo'],
        detail_type=['KVS Stream State Change'],
        detail={
            'StreamName': [{'prefix': 'session-'}],
            'EventType': ['FragmentComplete', 'FragmentStarted']
        }
    ),
    enabled=True,
)

# Add kvs_stream_consumer as target
kvs_stream_rule.add_target(
    targets.LambdaFunction(
        kvs_stream_consumer,
        retry_attempts=2,
    )
)

logger.info(f"EventBridge rule created: {kvs_stream_rule.rule_name}")
```

**Note:** KVS Stream events require explicit opt-in. Add to stream creation:

```python
# In kvs_stream_writer handler.py, when creating stream:
kvs_client.create_stream(
    ...,
    # Enable EventBridge events
    Tags={
        ...
        'EnableEventBridge': 'true',
    }
)
```

---

## Step 6: Testing Phase 2

### Test 1: Verify Stream Creation

```bash
# After speaker starts streaming, check if stream exists
export SESSION_ID=your-session-id

aws kinesisvideo describe-stream \
  --stream-name session-${SESSION_ID} \
  --region us-east-1

# Expected: StreamInfo with Status: ACTIVE
```

### Test 2: Check for Fragments

```bash
# This is the CRITICAL test
aws kinesisvideo list-fragments \
  --stream-name session-${SESSION_ID} \
  --region us-east-1 \
  --max-results 10

# Expected: Array of fragments with timestamps
# Each fragment = 250ms of audio
```

**If fragments exist:** ✅ Audio IS reaching KVS Stream!

### Test 3: Monitor kvs_stream_writer Logs

```bash
./scripts/tail-lambda-logs.sh kvs-stream-writer-dev

# Look for:
# "[KVS_WRITER] Processing chunk 0 for session..."
# "[KVS_WRITER] Chunk 40 processed successfully"
# "Creating KVS Stream: session-..."
# "Stream session-... is ACTIVE"
```

### Test 4: Check kvs_stream_consumer Triggered

```bash
./scripts/tail-lambda-logs.sh kvs-stream-consumer-dev

# Look for:
# "Processing EventBridge event"
# "Starting stream processing for session..."
# "Processed X chunks for session..."
```

### Test 5: Verify EventBridge Rule

```bash
aws events describe-rule \
  --name kvs-stream-consumer-trigger-dev \
  --region us-east-1

# Should show: State: ENABLED

aws events list-targets-by-rule \
  --rule kvs-stream-consumer-trigger-dev \
  --region us-east-1

# Should show kvs-stream-consumer Lambda as target
```

---

## Step 7: Update Verification Script

**File:** `scripts/verify-audio-pipeline.sh`

The script should now correctly check for traditional KVS Streams (not Signaling Channels).

Verify it works:

```bash
SESSION_ID=your-session-id ./scripts/verify-audio-pipeline.sh

# Should show:
# ✓ PASS: KVS Stream exists
# ✓ PASS: Found X fragments
# ✓ PASS: EventBridge rule exists
# ✓ PASS: kvs_stream_consumer has recent logs
```

---

## Deployment Steps

### 1. Deploy Backend Infrastructure

```bash
cd session-management

# Deploy CDK stack with new Lambda
make deploy

# Verify deployment
aws lambda list-functions \
  --query 'Functions[?contains(FunctionName, `kvs-stream-writer`)].FunctionName' \
  --output table
```

### 2. Test Lambda Directly

```bash
# Test health check
aws lambda invoke \
  --function-name kvs-stream-writer-dev \
  --payload '{"action":"health_check"}' \
  --region us-east-1 \
  response.json

cat response.json
# Should show: {"message": "kvs_stream_writer healthy", ...}
```

### 3. Test Stream Creation

```bash
# Test creating a stream
aws lambda invoke \
  --function-name kvs-stream-writer-dev \
  --payload '{
    "action": "createStream",
    "sessionId": "test-session-123"
  }' \
  --region us-east-1 \
  response.json

cat response.json

# Verify stream exists
aws kinesisvideo describe-stream \
  --stream-name session-test-session-123 \
  --region us-east-1
```

---

## Common Issues & Solutions

### Issue 1: ffmpeg Not Found

**Error:** "ffmpeg: command not found"

**Solution:**
- Verify FFmpeg layer attached to Lambda
- Check layer ARN is correct for your region
- Verify PATH includes /opt/bin (layer location)

**Debug:**
```python
# Add to handler.py for debugging
import subprocess
result = subprocess.run(['which', 'ffmpeg'], capture_output=True)
logger.info(f"ffmpeg location: {result.stdout.decode()}")
```

### Issue 2: PutMedia Permission Denied

**Error:** "User is not authorized to perform: kinesisvideo:PutMedia"

**Solution:**
- Check Lambda IAM role has PutMedia permission
- Verify resource ARN pattern matches: `stream/session-*/*`
- Check stream name format: `session-{sessionId}`

### Issue 3: Stream Creation Fails

**Error:** "ResourceInUseException" or "LimitExceededException"

**Solution:**
- Check if stream already exists (describe-stream)
- Verify account KVS Stream limit (default: 100)
- Delete old test streams if needed

### Issue 4: Conversion Takes Too Long

**Error:** Lambda timeout or ffmpeg timeout

**Solution:**
- Increase Lambda timeout: 30s → 60s
- Increase memory: 512MB → 1024MB (faster CPU)
- Check chunk size isn't too large

### Issue 5: EventBridge Not Triggering

**Error:** kvs_stream_consumer never invoked

**Solution:**
```bash
# Check if EventBridge events are enabled for KVS
# Add to stream tags: EnableEventBridge=true

# Check rule exists and is enabled
aws events describe-rule --name kvs-stream-consumer-trigger-dev

# Check rule targets
aws events list-targets-by-rule --rule kvs-stream-consumer-trigger-dev

# Test rule manually
aws events put-events --entries '[{
  "Source": "aws.kinesisvideo",
  "DetailType": "KVS Stream State Change",
  "Detail": "{\"StreamName\":\"session-test\",\"EventType\":\"FragmentComplete\"}"
}]'
```

---

## Performance Optimization

### Conversion Speed:
- **Current:** WebM → PCM in ~50ms per 250ms chunk
- **Memory:** 1024MB Lambda (faster CPU)
- **Timeout:** 60 seconds (plenty for 250ms chunks)

### Caching:
- Stream endpoints cached (avoid repeated GetDataEndpoint calls)
- Reduces latency by ~100ms per chunk

### Batching (Future):
- Could batch multiple 250ms chunks into single PutMedia call
- Reduces API calls, slightly higher latency
- Trade-off: Simplicity vs performance

---

## Success Criteria

✅ **Phase 2 Complete When:**
1. kvs_stream_writer Lambda deployed and healthy
2. FFmpeg conversion working (WebM → PCM)
3. KVS Stream created on first audio chunk
4. Fragments visible in KVS Stream (via list-fragments)
5. EventBridge rule triggers kvs_stream_consumer
6. kvs_stream_consumer processes audio correctly
7. No errors in any Lambda logs

---

## Checkpoint: What to Verify

Before moving to Phase 3, confirm:
- [ ] kvs_stream_writer Lambda exists and is invocable
- [ ] FFmpeg layer attached and working
- [ ] KVS Stream has fragments (`list-fragments` returns data)
- [ ] EventBridge rule exists and is enabled
- [ ] kvs_stream_consumer logs show "Processed X chunks"
- [ ] No conversion errors in logs
- [ ] No permission errors

**Create:** `CHECKPOINT_PHASE2_COMPLETE.md` with test results

---

## Estimated Timeline

- **kvs_stream_writer creation**: 2 hours
- **FFmpeg layer setup**: 1 hour
- **CDK stack updates**: 1 hour
- **kvs
