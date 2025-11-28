"""
Audio Chunk Writer Lambda
Receives PCM audio chunks and writes to S3 for processing.

Architecture:
- Triggered by connection_handler Lambda (async invocation)  
- Receives base64-encoded PCM chunks from AudioWorklet
- Writes directly to S3 (no conversion needed)
- S3 events trigger s3_audio_consumer for aggregation
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
        audio_format = event.get('format', 'pcm')  # Now defaults to PCM
        timestamp = event.get('timestamp', int(time.time() * 1000))
        
        if not session_id or not audio_data_base64:
            logger.error("Missing required parameters: sessionId or audioData")
            return {'statusCode': 400, 'body': json.dumps({'error': 'Missing parameters'})}
        
        # Log every 40th chunk to avoid spam
        if chunk_index % 40 == 0:
            logger.info(
                f"[AUDIO_WRITER] Processing chunk {chunk_index} for session {session_id}",
                extra={
                    'session_id': session_id,
                    'chunk_index': chunk_index,
                    'format': audio_format
                }
            )
        
        # Decode base64 audio
        audio_data = base64.b64decode(audio_data_base64)
        
        if len(audio_data) == 0:
            logger.warning(f"Empty audio data for chunk {chunk_index}")
            return {'statusCode': 200, 'body': json.dumps({'message': 'Empty chunk skipped'})}
        
        # Write to S3 (PCM ready for direct use, no conversion needed)
        success = write_to_s3(session_id, audio_data, timestamp, audio_format)
        
        if not success:
            logger.error(f"Failed to write chunk {chunk_index} to S3")
            return {'statusCode': 500, 'body': json.dumps({'error': 'S3 write failed'})}
        
        # Log timing for monitoring
        duration_ms = int((time.time() - start_time) * 1000)
        
        if chunk_index % 40 == 0:
            logger.info(
                f"[AUDIO_WRITER] Chunk {chunk_index} processed successfully",
                extra={
                    'session_id': session_id,
                    'chunk_index': chunk_index,
                    'duration_ms': duration_ms,
                    'audio_size': len(audio_data),
                    'format': audio_format
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


def write_to_s3(session_id: str, audio_data: bytes, timestamp: int, audio_format: str = 'pcm') -> bool:
    """
    Write audio chunk to S3.
    
    For PCM: No conversion needed, write directly
    For WebM: Keep for backward compatibility (though deprecated)
    
    Args:
        session_id: Session identifier
        audio_data: Raw audio bytes (PCM or WebM)
        timestamp: Timestamp in milliseconds
        audio_format: Format identifier ('pcm' or 'webm')
        
    Returns:
        True if successful, False otherwise
    """
    try:
        s3_client = boto3.client('s3')
        bucket = f'low-latency-audio-{STAGE}'
        
        # Determine file extension and content type
        if audio_format == 'pcm':
            extension = 'pcm'
            content_type = 'audio/pcm'
        else:
            extension = 'webm'
            content_type = 'audio/webm'
        
        # Create S3 key
        key = f'sessions/{session_id}/chunks/{timestamp}.{extension}'
        
        # Write to S3
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=audio_data,
            ContentType=content_type,
            Metadata={
                'sessionId': session_id,
                'timestamp': str(timestamp),
                'format': audio_format,
                'sampleRate': '16000',
                'channels': '1',
                'encoding': 's16le'
            }
        )
        
        logger.debug(f"Wrote {len(audio_data)} bytes to S3: {key}")
        return True
        
    except Exception as e:
        logger.error(f"Error writing to S3: {str(e)}", exc_info=True)
        return False


def handle_health_check(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle health check requests."""
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'audio_chunk_writer healthy',
            'stage': STAGE,
            'supports': ['pcm', 'webm'],
            'timestamp': int(time.time() * 1000)
        })
    }


def handle_create_stream(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle explicit stream creation request (legacy, not needed for PCM)."""
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Stream creation not needed for PCM flow',
            'info': 'PCM chunks written directly to S3'
        })
    }
