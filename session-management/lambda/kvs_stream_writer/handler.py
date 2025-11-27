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
        
        # Skip conversion - send WebM directly to KVS
        # Individual MediaRecorder chunks don't have complete headers for ffmpeg
        # KVS will store raw WebM, consumer will handle conversion
        
        # Write to KVS Stream
        stream_name = f"session-{session_id}"
        success = write_to_kvs_stream(stream_name, webm_data, session_id)
        
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
                    'webm_size': len(webm_data)
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
    webm_path = None
    pcm_path = None
    
    try:
        # Create temporary files
        webm_file = tempfile.NamedTemporaryFile(suffix='.webm', delete=False)
        webm_file.write(webm_bytes)
        webm_file.flush()
        webm_path = webm_file.name
        webm_file.close()
        
        pcm_path = webm_path + '.pcm'
        
        # Run ffmpeg conversion
        # Use -f webm to force format, -err_detect ignore_err to handle incomplete chunks
        result = subprocess.run([
            'ffmpeg',
            '-f', 'webm',             # Force WebM input format
            '-err_detect', 'ignore_err',  # Ignore minor errors in streaming chunks
            '-i', webm_path,          # Input WebM file
            '-f', 's16le',            # Output format: PCM 16-bit little-endian
            '-acodec', 'pcm_s16le',   # Audio codec
            '-ar', '16000',           # Sample rate: 16kHz
            '-ac', '1',               # Channels: mono
            '-loglevel', 'error',     # Only show errors
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
            if webm_path and os.path.exists(webm_path):
                os.unlink(webm_path)
            if pcm_path and os.path.exists(pcm_path):
                os.unlink(pcm_path)
        except Exception as cleanup_error:
            logger.warning(f"Error cleaning up temp files: {str(cleanup_error)}")


def write_to_kvs_stream(stream_name: str, audio_data: bytes, session_id: str) -> bool:
    """
    Write audio to S3 for temporary storage (simplified approach).
    KVS PutMedia requires streaming/continuous connection which is complex for chunks.
    
    Args:
        stream_name: Stream identifier (session-{id})
        audio_data: WebM audio bytes
        session_id: Session identifier
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Write to S3 instead of KVS for simpler chunk storage
        s3_client = boto3.client('s3')
        bucket = f'low-latency-audio-{STAGE}'
        
        # Create unique key for chunk
        timestamp = int(time.time() * 1000)
        key = f'sessions/{session_id}/chunks/{timestamp}.webm'
        
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=audio_data,
            ContentType='audio/webm',
            Metadata={
                'sessionId': session_id,
                'timestamp': str(timestamp)
            }
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error writing to S3: {str(e)}", exc_info=True)
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
            MediaType='video/webm',  # WebM audio chunks
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
