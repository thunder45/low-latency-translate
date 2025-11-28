"""
S3 Audio Consumer Lambda Handler

Triggered by S3 events when PCM chunks are uploaded.
Aggregates chunks and forwards to audio_processor.
No conversion needed - PCM is ready to use.
"""

import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import unquote_plus

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')
dynamodb = boto3.resource('dynamodb')

# Environment variables
STAGE = os.environ.get('STAGE', 'dev')
AUDIO_BUCKET_NAME = os.environ.get('AUDIO_BUCKET_NAME', f'low-latency-audio-{STAGE}')
AUDIO_PROCESSOR_FUNCTION = os.environ.get('AUDIO_PROCESSOR_FUNCTION', f'audio-processor-{STAGE}')
SESSIONS_TABLE_NAME = os.environ.get('SESSIONS_TABLE_NAME', f'Sessions-{STAGE}')

# Processing configuration
BATCH_WINDOW_SECONDS = int(os.environ.get('BATCH_WINDOW_SECONDS', '3'))  # Aggregate 3 seconds of chunks
MIN_CHUNKS_FOR_PROCESSING = int(os.environ.get('MIN_CHUNKS_FOR_PROCESSING', '8'))  # Minimum 2 seconds (8 * 250ms)
CHUNK_DURATION_MS = 250  # Each chunk is 250ms

# Note: FFmpeg no longer needed for PCM chunks


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler triggered by S3 events.
    
    Args:
        event: S3 event notification
        context: Lambda context
        
    Returns:
        Status response
    """
    try:
        logger.info(f"Received S3 event: {json.dumps(event)}")
        
        # Parse S3 event
        for record in event.get('Records', []):
            if record.get('eventName', '').startswith('ObjectCreated'):
                bucket = record['s3']['bucket']['name']
                key = unquote_plus(record['s3']['object']['key'])
                
                logger.info(f"Processing new chunk: s3://{bucket}/{key}")
                
                # Extract session ID from key: sessions/{sessionId}/chunks/{timestamp}.webm
                parts = key.split('/')
                if len(parts) >= 4 and parts[0] == 'sessions' and parts[2] == 'chunks':
                    session_id = parts[1]
                    
                    # Process chunks for this session
                    process_session_chunks(session_id, bucket)
                else:
                    logger.warning(f"Unexpected key format: {key}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Processing complete'})
        }
        
    except Exception as e:
        logger.error(f"Error processing S3 event: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def process_session_chunks(session_id: str, bucket: str) -> None:
    """
    Process accumulated chunks for a session.
    
    Args:
        session_id: Session identifier
        bucket: S3 bucket name
    """
    try:
        # List all chunks for this session
        prefix = f"sessions/{session_id}/chunks/"
        chunks = list_session_chunks(bucket, prefix)
        
        if not chunks:
            logger.info(f"No chunks found for session {session_id}")
            return
        
        logger.info(f"Found {len(chunks)} chunks for session {session_id}")
        
        # Group chunks into batches for processing
        batches = create_chunk_batches(chunks)
        
        for batch_index, batch in enumerate(batches):
            if len(batch) >= MIN_CHUNKS_FOR_PROCESSING:
                logger.info(
                    f"Processing batch {batch_index + 1}/{len(batches)} "
                    f"with {len(batch)} chunks for session {session_id}"
                )
                
                # Process this batch
                process_chunk_batch(session_id, batch, bucket, batch_index)
            else:
                logger.info(
                    f"Batch {batch_index + 1} has only {len(batch)} chunks, "
                    f"waiting for more (minimum {MIN_CHUNKS_FOR_PROCESSING})"
                )
        
    except Exception as e:
        logger.error(
            f"Error processing chunks for session {session_id}: {str(e)}",
            exc_info=True
        )


def list_session_chunks(bucket: str, prefix: str) -> List[Dict[str, Any]]:
    """
    List all chunks for a session from S3.
    
    Args:
        bucket: S3 bucket name
        prefix: S3 key prefix
        
    Returns:
        List of chunk metadata (sorted by timestamp)
    """
    chunks = []
    
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
        
        for page in pages:
            for obj in page.get('Contents', []):
                key = obj['Key']
                
                # Extract timestamp from filename: {timestamp}.pcm or {timestamp}.webm
                filename = key.split('/')[-1]
                if filename.endswith('.pcm'):
                    timestamp_str = filename[:-4]  # Remove .pcm
                elif filename.endswith('.webm'):
                    timestamp_str = filename[:-5]  # Remove .webm (legacy)
                    try:
                        timestamp = int(timestamp_str)
                        chunks.append({
                            'key': key,
                            'timestamp': timestamp,
                            'size': obj['Size'],
                            'last_modified': obj['LastModified']
                        })
                    except ValueError:
                        logger.warning(f"Invalid timestamp in filename: {filename}")
        
        # Sort by timestamp
        chunks.sort(key=lambda x: x['timestamp'])
        
        return chunks
        
    except ClientError as e:
        logger.error(f"Error listing chunks: {str(e)}")
        return []


def create_chunk_batches(chunks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """
    Group chunks into batches for processing.
    
    Batches are created based on timestamp gaps and batch window size.
    
    Args:
        chunks: List of chunk metadata
        
    Returns:
        List of chunk batches
    """
    if not chunks:
        return []
    
    batches = []
    current_batch = []
    batch_window_ms = BATCH_WINDOW_SECONDS * 1000
    
    for chunk in chunks:
        if not current_batch:
            # Start new batch
            current_batch = [chunk]
        else:
            # Check if chunk fits in current batch window
            batch_start_ts = current_batch[0]['timestamp']
            chunk_ts = chunk['timestamp']
            
            if chunk_ts - batch_start_ts <= batch_window_ms:
                # Add to current batch
                current_batch.append(chunk)
            else:
                # Start new batch
                batches.append(current_batch)
                current_batch = [chunk]
    
    # Add last batch
    if current_batch:
        batches.append(current_batch)
    
    return batches


def process_chunk_batch(
    session_id: str,
    batch: List[Dict[str, Any]],
    bucket: str,
    batch_index: int
) -> None:
    """
    Process a batch of PCM chunks: concatenate and forward.
    
    For PCM: Simple binary concatenation (no conversion needed)
    For WebM: Would need FFmpeg (but deprecated with AudioWorklet)
    
    Args:
        session_id: Session identifier
        batch: List of chunk metadata
        bucket: S3 bucket name
        batch_index: Index of this batch
    """
    try:
        logger.info(f"Processing batch {batch_index} with {len(batch)} chunks")
        
        # Download and concatenate PCM chunks directly
        pcm_data = b''
        
        for i, chunk in enumerate(batch):
            # Download chunk from S3
            response = s3_client.get_object(Bucket=bucket, Key=chunk['key'])
            chunk_data = response['Body'].read()
            
            # Concatenate (PCM is just raw samples, simple binary append)
            pcm_data += chunk_data
            
            logger.debug(f"Downloaded chunk {i + 1}/{len(batch)}: {chunk['key']}, size: {len(chunk_data)}")
        
        logger.info(f"Concatenated PCM batch: {len(pcm_data)} bytes")
        
        # Calculate batch metadata
        batch_start_ts = batch[0]['timestamp']
        batch_end_ts = batch[-1]['timestamp']
        duration_seconds = (batch_end_ts - batch_start_ts + CHUNK_DURATION_MS) / 1000.0
        
        # Invoke audio processor
        invoke_audio_processor(
            session_id=session_id,
            pcm_data=pcm_data,
            sample_rate=16000,
            timestamp=batch_start_ts,
            duration=duration_seconds,
            batch_index=batch_index
        )
        
    except Exception as e:
        logger.error(
            f"Error processing batch {batch_index} for session {session_id}: {str(e)}",
            exc_info=True
        )


def invoke_audio_processor(
    session_id: str,
    pcm_data: bytes,
    sample_rate: int,
    timestamp: int,
    duration: float,
    batch_index: int
) -> None:
    """
    Invoke audio_processor Lambda with PCM audio data.
    
    Args:
        session_id: Session identifier
        pcm_data: PCM audio bytes
        sample_rate: Audio sample rate
        timestamp: Batch start timestamp
        duration: Audio duration in seconds
        batch_index: Index of this batch
    """
    try:
        # Get session details from DynamoDB
        sessions_table = dynamodb.Table(SESSIONS_TABLE_NAME)
        response = sessions_table.get_item(Key={'sessionId': session_id})
        
        if 'Item' not in response:
            logger.warning(f"Session {session_id} not found in DynamoDB")
            return
        
        session = response['Item']
        
        # Prepare payload for audio_processor
        payload = {
            'sessionId': session_id,
            'audio': {
                'data': pcm_data.hex(),  # Convert bytes to hex string for JSON
                'format': 'pcm',
                'sampleRate': sample_rate,
                'channels': 1,
                'encoding': 's16le'
            },
            'sourceLanguage': session.get('sourceLanguage', 'en'),
            'targetLanguages': session.get('targetLanguages', []),
            'timestamp': timestamp,
            'duration': duration,
            'batchIndex': batch_index
        }
        
        logger.info(
            f"Invoking audio_processor for session {session_id}, "
            f"batch {batch_index}, duration {duration:.2f}s, "
            f"PCM size: {len(pcm_data)} bytes"
        )
        
        # Invoke async
        lambda_client.invoke(
            FunctionName=AUDIO_PROCESSOR_FUNCTION,
            InvocationType='Event',  # Async
            Payload=json.dumps(payload)
        )
        
        logger.info(f"Successfully invoked audio_processor for batch {batch_index}")
        
    except ClientError as e:
        logger.error(f"Error invoking audio_processor: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error preparing audio_processor invocation: {str(e)}")
        raise


def health_check() -> Dict[str, Any]:
    """Health check for the Lambda function."""
    return {
        'statusCode': 200,
        'body': json.dumps({
            'status': 'healthy',
            'function': 's3_audio_consumer',
            'stage': STAGE,
            'mode': 'pcm-direct',
            'ffmpeg_needed': False
        })
    }
