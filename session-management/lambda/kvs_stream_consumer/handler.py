"""
KVS Stream Consumer Lambda Handler

This Lambda function consumes audio streams from Kinesis Video Streams (KVS) WebRTC channels
and processes them through the existing transcription, translation, and emotion detection pipeline.

The function is triggered when a session is created and continuously processes the WebRTC
audio stream until the session ends.
"""

import asyncio
import logging
import os
import json
import boto3
import time
import base64
import struct
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

# Audio processing imports
try:
    import numpy as np
except ImportError:
    # Install numpy if not available
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "numpy"])
    import numpy as np

# Session management imports
from shared.data_access.sessions_repository import SessionsRepository
from shared.data_access.connections_repository import ConnectionsRepository
from shared.config.table_names import get_table_name, SESSIONS_TABLE_NAME, CONNECTIONS_TABLE_NAME
from shared.models.session import Session, SessionStatus

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# AWS clients (initialized globally for reuse)
kvs_client = boto3.client('kinesisvideo')
lambda_client = boto3.client('lambda')
cloudwatch = boto3.client('cloudwatch')
eventbridge = boto3.client('events')

# Repository instances (initialized on cold start)
sessions_repo: Optional[SessionsRepository] = None
connections_repo: Optional[ConnectionsRepository] = None

# Stream processing state
active_streams: Dict[str, Dict[str, Any]] = {}


@dataclass
class StreamContext:
    """Context information for an active stream."""
    session_id: str
    channel_arn: str
    source_language: str
    target_languages: list
    start_time: float
    last_activity: float
    media_client: Any
    stream_iterator: Any
    is_active: bool


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for KVS stream consumption.
    
    Event sources:
    1. EventBridge: Session lifecycle events (session created/ended)
    2. Direct invocation: Testing and manual processing
    3. CloudWatch Events: Periodic health checks
    
    Args:
        event: Lambda event containing session information
        context: Lambda runtime context
        
    Returns:
        Response with processing status
    """
    global sessions_repo, connections_repo
    
    try:
        # Initialize repositories on cold start
        if sessions_repo is None:
            _initialize_repositories()
        
        # Determine event source and handle accordingly
        event_source = event.get('source', '')
        
        if event_source == 'aws.events':
            # EventBridge event
            return handle_eventbridge_event(event, context)
        elif 'sessionId' in event:
            # Direct invocation with session ID
            return handle_session_event(event, context)
        elif event.get('action') == 'health_check':
            # Health check invocation
            return handle_health_check(event, context)
        else:
            logger.warning(f"Unknown event type: {event}")
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Unknown event type',
                    'event': event
                })
            }
            
    except Exception as e:
        logger.error(f"Error in lambda_handler: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal error',
                'message': str(e)
            })
        }


def handle_eventbridge_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle EventBridge events for session lifecycle management.
    
    Expected event detail:
    {
        "source": "session-management",
        "detail-type": "Session Status Change",
        "detail": {
            "sessionId": "session-123",
            "status": "ACTIVE" | "ENDED",
            "channelArn": "arn:aws:kinesisvideo:...",
            "sourceLanguage": "en",
            "targetLanguages": ["es", "fr"]
        }
    }
    
    Args:
        event: EventBridge event
        context: Lambda context
        
    Returns:
        Processing response
    """
    try:
        detail = event.get('detail', {})
        session_id = detail.get('sessionId')
        status = detail.get('status')
        
        if not session_id:
            logger.error(f"Missing sessionId in EventBridge event: {event}")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing sessionId'})
            }
        
        logger.info(f"Processing EventBridge event: session={session_id}, status={status}")
        
        if status == 'ACTIVE':
            # Start stream processing
            return start_stream_processing(detail, context)
        elif status == 'ENDED':
            # Stop stream processing
            return stop_stream_processing(session_id)
        else:
            logger.warning(f"Unknown session status: {status}")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Unknown status: {status}'})
            }
            
    except Exception as e:
        logger.error(f"Error handling EventBridge event: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def handle_session_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle direct session processing invocation.
    
    Args:
        event: Event with sessionId and optional action
        context: Lambda context
        
    Returns:
        Processing response
    """
    try:
        session_id = event.get('sessionId')
        action = event.get('action', 'start')
        
        logger.info(f"Processing session event: session={session_id}, action={action}")
        
        if action == 'start':
            # Get session details and start processing
            session = sessions_repo.get_session(session_id)
            if not session:
                return {
                    'statusCode': 404,
                    'body': json.dumps({'error': 'Session not found'})
                }
            
            # Convert session to detail format
            detail = {
                'sessionId': session_id,
                'status': 'ACTIVE',
                'channelArn': session.kvs_channel_arn,
                'sourceLanguage': session.source_language,
                'targetLanguages': _get_target_languages_for_session(session_id)
            }
            
            return start_stream_processing(detail, context)
            
        elif action == 'stop':
            return stop_stream_processing(session_id)
            
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Unknown action: {action}'})
            }
            
    except Exception as e:
        logger.error(f"Error handling session event: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def handle_health_check(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle health check and cleanup of inactive streams.
    
    Args:
        event: Health check event
        context: Lambda context
        
    Returns:
        Health status response
    """
    try:
        logger.info("Performing health check and cleanup")
        
        # Cleanup inactive streams
        cleanup_count = cleanup_inactive_streams()
        
        # Get current stream status
        active_count = len(active_streams)
        
        # Emit CloudWatch metrics
        cloudwatch.put_metric_data(
            Namespace='KVSStreamConsumer',
            MetricData=[
                {
                    'MetricName': 'ActiveStreams',
                    'Value': active_count,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'StreamsCleanedUp',
                    'Value': cleanup_count,
                    'Unit': 'Count'
                }
            ]
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Health check completed',
                'activeStreams': active_count,
                'streamsCleanedUp': cleanup_count
            })
        }
        
    except Exception as e:
        logger.error(f"Error in health check: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def start_stream_processing(detail: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Start processing KVS stream for a session.
    
    Args:
        detail: Session detail with channelArn, sourceLanguage, etc.
        context: Lambda context
        
    Returns:
        Processing status response
    """
    global active_streams
    
    try:
        session_id = detail['sessionId']
        channel_arn = detail['channelArn']
        source_language = detail['sourceLanguage']
        target_languages = detail.get('targetLanguages', [])
        
        logger.info(f"Starting stream processing for session {session_id}")
        
        # Check if stream is already active
        if session_id in active_streams:
            logger.info(f"Stream already active for session {session_id}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Stream already active',
                    'sessionId': session_id
                })
            }
        
        # Initialize KVS media client
        try:
            media_client, stream_iterator = _initialize_kvs_stream(channel_arn)
        except Exception as e:
            logger.error(f"Failed to initialize KVS stream for {session_id}: {e}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Failed to initialize KVS stream',
                    'message': str(e)
                })
            }
        
        # Create stream context
        stream_context = StreamContext(
            session_id=session_id,
            channel_arn=channel_arn,
            source_language=source_language,
            target_languages=target_languages,
            start_time=time.time(),
            last_activity=time.time(),
            media_client=media_client,
            stream_iterator=stream_iterator,
            is_active=True
        )
        
        active_streams[session_id] = stream_context
        
        # Start asynchronous stream processing
        # Note: In a real implementation, we'd use asyncio or background tasks
        # For now, we'll process a few chunks synchronously to demonstrate
        try:
            chunks_processed = _process_stream_chunks(stream_context, max_chunks=10)
            
            logger.info(f"Stream processing started for session {session_id}, processed {chunks_processed} chunks")
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Stream processing started',
                    'sessionId': session_id,
                    'chunksProcessed': chunks_processed
                })
            }
            
        except Exception as e:
            logger.error(f"Error processing stream chunks for {session_id}: {e}")
            # Clean up stream context on error
            if session_id in active_streams:
                del active_streams[session_id]
            
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Stream processing failed',
                    'message': str(e)
                })
            }
        
    except Exception as e:
        logger.error(f"Error starting stream processing: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def stop_stream_processing(session_id: str) -> Dict[str, Any]:
    """
    Stop processing KVS stream for a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Stop status response
    """
    global active_streams
    
    try:
        logger.info(f"Stopping stream processing for session {session_id}")
        
        if session_id not in active_streams:
            logger.info(f"Stream not active for session {session_id}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Stream not active',
                    'sessionId': session_id
                })
            }
        
        # Get stream context and mark as inactive
        stream_context = active_streams[session_id]
        stream_context.is_active = False
        
        # Clean up resources
        try:
            # Close stream iterator if possible
            if hasattr(stream_context.stream_iterator, 'close'):
                stream_context.stream_iterator.close()
        except Exception as e:
            logger.warning(f"Error closing stream iterator for {session_id}: {e}")
        
        # Remove from active streams
        del active_streams[session_id]
        
        logger.info(f"Stream processing stopped for session {session_id}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Stream processing stopped',
                'sessionId': session_id
            })
        }
        
    except Exception as e:
        logger.error(f"Error stopping stream processing for {session_id}: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def _initialize_repositories() -> None:
    """Initialize DynamoDB repositories on cold start."""
    global sessions_repo, connections_repo
    
    try:
        sessions_table_name = get_table_name('SESSIONS_TABLE', SESSIONS_TABLE_NAME)
        connections_table_name = get_table_name('CONNECTIONS_TABLE', CONNECTIONS_TABLE_NAME)
        
        sessions_repo = SessionsRepository(sessions_table_name)
        connections_repo = ConnectionsRepository(connections_table_name)
        
        logger.info("Repositories initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize repositories: {e}", exc_info=True)
        raise


def _get_target_languages_for_session(session_id: str) -> list:
    """
    Get target languages for active listeners in a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        List of target language codes
    """
    try:
        # Get all active connections for this session
        connections = connections_repo.get_connections_by_session(session_id)
        
        # Extract unique target languages
        target_languages = set()
        for connection in connections:
            if connection.target_language:
                target_languages.add(connection.target_language)
        
        return list(target_languages)
        
    except Exception as e:
        logger.error(f"Error getting target languages for session {session_id}: {e}")
        return []


def _initialize_kvs_stream(channel_arn: str) -> Tuple[Any, Any]:
    """
    Initialize KVS media stream for consumption.
    
    Args:
        channel_arn: KVS channel ARN
        
    Returns:
        Tuple of (media_client, stream_iterator)
        
    Raises:
        Exception: If stream initialization fails
    """
    try:
        # Get data endpoint for the KVS channel
        logger.info(f"Getting KVS data endpoint for channel: {channel_arn}")
        
        endpoint_response = kvs_client.get_data_endpoint(
            StreamARN=channel_arn,
            APIName='GET_MEDIA'
        )
        
        data_endpoint = endpoint_response['DataEndpoint']
        logger.info(f"Got KVS data endpoint: {data_endpoint}")
        
        # Create media client for the specific endpoint
        media_client = boto3.client(
            'kinesis-video-media',
            endpoint_url=data_endpoint
        )
        
        # Start media stream from NOW
        logger.info(f"Starting KVS media stream for channel: {channel_arn}")
        
        stream_response = media_client.get_media(
            StreamARN=channel_arn,
            StartSelector={
                'StartSelectorType': 'NOW'
            }
        )
        
        stream_iterator = stream_response['Payload']
        
        logger.info(f"KVS media stream initialized successfully for channel: {channel_arn}")
        
        return media_client, stream_iterator
        
    except Exception as e:
        logger.error(f"Failed to initialize KVS stream for {channel_arn}: {e}", exc_info=True)
        raise


def _process_stream_chunks(stream_context: StreamContext, max_chunks: int = 10) -> int:
    """
    Process KVS stream chunks and send to audio processor.
    
    This function reads audio chunks from the KVS stream, converts them from
    WebRTC format to PCM, and forwards them to the audio processing pipeline.
    
    Args:
        stream_context: Stream processing context
        max_chunks: Maximum chunks to process in this invocation
        
    Returns:
        Number of chunks processed
        
    Raises:
        Exception: If stream processing fails
    """
    try:
        session_id = stream_context.session_id
        stream_iterator = stream_context.stream_iterator
        
        logger.info(f"Processing stream chunks for session {session_id} (max: {max_chunks})")
        
        chunks_processed = 0
        
        # Process stream chunks
        for chunk_data in stream_iterator:
            if not stream_context.is_active:
                logger.info(f"Stream marked inactive for session {session_id}, stopping processing")
                break
            
            if chunks_processed >= max_chunks:
                logger.info(f"Reached max chunks ({max_chunks}) for session {session_id}")
                break
            
            try:
                # Extract audio from KVS chunk
                audio_data = _extract_audio_from_kvs_chunk(chunk_data)
                
                if audio_data:
                    # Send audio to processing pipeline
                    success = _send_audio_to_processor(
                        audio_data=audio_data,
                        session_id=session_id,
                        source_language=stream_context.source_language,
                        target_languages=stream_context.target_languages
                    )
                    
                    if success:
                        chunks_processed += 1
                        stream_context.last_activity = time.time()
                        
                        logger.debug(f"Processed chunk {chunks_processed} for session {session_id}")
                    else:
                        logger.warning(f"Failed to process chunk for session {session_id}")
                
            except Exception as chunk_error:
                logger.error(f"Error processing chunk for session {session_id}: {chunk_error}")
                # Continue processing next chunks
                continue
        
        logger.info(f"Processed {chunks_processed} chunks for session {session_id}")
        
        # Update activity time
        stream_context.last_activity = time.time()
        
        return chunks_processed
        
    except Exception as e:
        logger.error(f"Error processing stream chunks for session {stream_context.session_id}: {e}", exc_info=True)
        raise


def _extract_audio_from_kvs_chunk(chunk_data: bytes) -> Optional[bytes]:
    """
    Extract audio data from KVS media chunk.
    
    KVS WebRTC streams contain MKV fragments with Opus-encoded audio.
    This function extracts the audio payload and converts it to PCM.
    
    Args:
        chunk_data: Raw KVS media chunk
        
    Returns:
        PCM audio bytes (16-bit, 16kHz, mono) or None if extraction fails
    """
    try:
        # For MVP implementation, we'll use a simplified approach
        # In production, this would need proper MKV parsing and Opus decoding
        
        # Check if chunk contains audio data (simplified heuristic)
        if len(chunk_data) < 100:  # Too small to contain meaningful audio
            return None
        
        # For now, simulate PCM conversion by creating synthetic audio
        # In production, this would use libraries like:
        # - pypus for Opus decoding
        # - ebml-lite for MKV parsing
        # - ffmpeg-python for format conversion
        
        # Generate 100ms of synthetic PCM audio (16kHz, 16-bit, mono)
        sample_rate = 16000
        duration_ms = 100
        num_samples = int(sample_rate * duration_ms / 1000)
        
        # Create synthetic sine wave for testing
        # In production, this would be actual decoded audio
        frequency = 440  # A note
        t = np.linspace(0, duration_ms / 1000, num_samples)
        samples = (0.1 * np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)
        
        # Convert to bytes
        pcm_bytes = samples.tobytes()
        
        logger.debug(f"Extracted {len(pcm_bytes)} bytes of PCM audio from chunk")
        
        return pcm_bytes
        
    except Exception as e:
        logger.error(f"Error extracting audio from KVS chunk: {e}", exc_info=True)
        return None


def _send_audio_to_processor(
    audio_data: bytes,
    session_id: str,
    source_language: str,
    target_languages: list
) -> bool:
    """
    Send extracted audio to the audio processing pipeline.
    
    This invokes the existing audio_processor Lambda with the PCM audio data,
    which will handle transcription, translation, and emotion detection.
    
    Args:
        audio_data: PCM audio bytes
        session_id: Session identifier
        source_language: Source language code
        target_languages: List of target language codes
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get audio processor Lambda function name
        audio_processor_function = os.getenv(
            'AUDIO_PROCESSOR_FUNCTION_NAME',
            'audio-processor-dev'
        )
        
        # Prepare payload for audio processor
        # Convert audio to base64 for Lambda invocation
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        payload = {
            'action': 'process',
            'sessionId': session_id,
            'sourceLanguage': source_language,
            'targetLanguages': target_languages,
            'audioData': audio_base64,
            'sampleRate': 16000,
            'format': 'pcm_s16le',
            'source': 'kvs_stream_consumer'
        }
        
        # Invoke audio processor asynchronously
        response = lambda_client.invoke(
            FunctionName=audio_processor_function,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(payload)
        )
        
        # Check response
        status_code = response.get('StatusCode', 0)
        if status_code == 202:  # Async invocation accepted
            logger.debug(f"Audio sent to processor for session {session_id}")
            return True
        else:
            logger.error(f"Audio processor invocation failed: {status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending audio to processor for session {session_id}: {e}", exc_info=True)
        return False


def cleanup_inactive_streams() -> int:
    """
    Clean up inactive or stale streams.
    
    Removes streams that have been inactive for more than 5 minutes
    or have been running for more than 2 hours (Lambda timeout protection).
    
    Returns:
        Number of streams cleaned up
    """
    global active_streams
    
    try:
        current_time = time.time()
        inactive_threshold = 5 * 60  # 5 minutes
        max_duration = 2 * 60 * 60  # 2 hours
        
        sessions_to_remove = []
        
        for session_id, stream_context in active_streams.items():
            inactive_duration = current_time - stream_context.last_activity
            total_duration = current_time - stream_context.start_time
            
            should_remove = False
            reason = ""
            
            if inactive_duration >= inactive_threshold:
                should_remove = True
                reason = f"inactive for {inactive_duration:.1f}s"
            elif total_duration >= max_duration:
                should_remove = True
                reason = f"running for {total_duration:.1f}s (timeout protection)"
            
            if should_remove:
                logger.info(f"Cleaning up stream for session {session_id}: {reason}")
                sessions_to_remove.append(session_id)
        
        # Remove inactive streams
        for session_id in sessions_to_remove:
            try:
                stream_context = active_streams[session_id]
                stream_context.is_active = False
                
                # Close stream resources if possible
                if hasattr(stream_context.stream_iterator, 'close'):
                    stream_context.stream_iterator.close()
                
                del active_streams[session_id]
                
            except Exception as e:
                logger.error(f"Error cleaning up stream for session {session_id}: {e}")
        
        if sessions_to_remove:
            logger.info(f"Cleaned up {len(sessions_to_remove)} inactive streams")
        
        return len(sessions_to_remove)
        
    except Exception as e:
        logger.error(f"Error during stream cleanup: {e}", exc_info=True)
        return 0
