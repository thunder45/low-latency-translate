"""
Audio Processor Lambda handler with WebSocket audio integration.

This module provides the Lambda handler for processing audio transcription
from WebSocket connections. It handles audio chunk reception, validation,
rate limiting, and streaming to AWS Transcribe with partial results support.
"""

import asyncio
import logging
import os
import json
import boto3
import numpy as np
import base64
import time
from typing import Dict, Any, Optional
from shared.models.configuration import PartialResultConfig
from shared.services.partial_result_processor import PartialResultProcessor

# WebSocket audio processing imports
from shared.utils.websocket_parser import (
    WebSocketMessageParser,
    WebSocketParseError
)
from shared.services.connection_validator import (
    ConnectionValidator,
    ValidationError,
    UnauthorizedError,
    SessionNotFoundError,
    SessionInactiveError
)
from shared.services.audio_rate_limiter import AudioRateLimiter
from shared.services.audio_format_validator import (
    AudioFormatValidator,
    AudioFormatError as FormatValidationError
)
from shared.services.audio_buffer import AudioBuffer

# Transcribe streaming imports
from shared.services.transcribe_stream_handler import TranscribeStreamHandler
from shared.services.transcribe_client import (
    TranscribeClientConfig,
    TranscribeClientManager,
    create_transcribe_client_for_session
)

# Translation Pipeline imports
from shared.services.lambda_translation_pipeline import LambdaTranslationPipeline

# Emotion dynamics imports - TEMPORARILY DISABLED FOR PHASE 4
# Large dependencies (scipy, librosa) exceed Lambda 250MB limit
# See OPTIONAL_FEATURES_REINTEGRATION_PLAN.md for adding back
# from emotion_dynamics.orchestrator import AudioDynamicsOrchestrator

# Audio quality imports - TEMPORARILY DISABLED FOR PHASE 4
# from audio_quality.analyzers.quality_analyzer import AudioQualityAnalyzer
# from audio_quality.models.quality_config import QualityConfig
# from audio_quality.notifiers.metrics_emitter import QualityMetricsEmitter
# from audio_quality.notifiers.speaker_notifier import SpeakerNotifier
# from audio_quality.utils.graceful_degradation import analyze_with_fallback
# from audio_quality.exceptions import (
#     AudioQualityError,
#     AudioFormatError,
#     QualityAnalysisError,
#     ConfigurationError
# )

# Placeholder classes for disabled features
class AudioQualityError(Exception): pass
class AudioFormatError(Exception): pass
class QualityAnalysisError(Exception): pass
class ConfigurationError(Exception): pass
class AudioQualityAnalyzer: pass
class QualityMetricsEmitter: pass
class SpeakerNotifier: pass
class AudioDynamicsOrchestrator: pass
class QualityConfig: pass

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Global processor instance (singleton per Lambda container)
# Initialized on cold start and reused across invocations
partial_processor: Optional[PartialResultProcessor] = None

# Audio quality components (singleton per Lambda container) - DISABLED
quality_analyzer = None
metrics_emitter = None
speaker_notifier = None

# WebSocket audio processing components (singleton per Lambda container)
websocket_parser: Optional[WebSocketMessageParser] = None
connection_validator: Optional[ConnectionValidator] = None
rate_limiter: Optional[AudioRateLimiter] = None
format_validator: Optional[AudioFormatValidator] = None

# Transcribe stream management (per session)
# session_id -> (client, manager, handler, buffer, last_activity_time)
active_streams: Dict[str, tuple] = {}

# Translation Pipeline client (singleton per Lambda container)
translation_pipeline: Optional[LambdaTranslationPipeline] = None

# Emotion detection orchestrator (singleton per Lambda container) - DISABLED
emotion_orchestrator = None

# Emotion cache for correlating with transcripts
# session_id -> {'volume': float, 'rate': float, 'energy': float, 'timestamp': int}
emotion_cache: Dict[str, Dict[str, Any]] = {}

# CloudWatch and EventBridge clients
cloudwatch = boto3.client('cloudwatch')
eventbridge = boto3.client('events')

# Fallback state tracking
fallback_mode_enabled = False
fallback_reason = None

# Health monitoring state
last_result_time = None
audio_session_active = False

# Stream lifecycle constants
STREAM_IDLE_TIMEOUT_SECONDS = 60  # Close stream after 60 seconds of inactivity
STREAM_CLEANUP_INTERVAL_SECONDS = 300  # Check for idle streams every 5 minutes


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Synchronous Lambda handler for audio processing.
    
    This handler processes audio from multiple sources:
    - Kinesis Data Stream (Phase 4 - primary path)
    - WebSocket API Gateway (legacy)
    - Direct invocation from s3_audio_consumer (Phase 3 - deprecated)
    
    Args:
        event: Lambda event object containing either:
            Kinesis batch event (Phase 4):
            - Records: List of Kinesis records with PCM audio
            
            WebSocket event from API Gateway:
            - requestContext: {connectionId, routeKey, ...}
            - body: Audio data (base64 or binary)
            - isBase64Encoded: Boolean
            
            Or direct invocation (from s3_audio_consumer - Phase 3 - deprecated):
            - sessionId: Session identifier
            - audio: {data: hex, format: 'pcm', sampleRate, channels, encoding}
            - sourceLanguage: Source language code
            - targetLanguages: List of target language codes
            - timestamp: Batch start timestamp
            - duration: Batch duration in seconds
            - batchIndex: Index of this batch
            
            Or legacy direct invocation:
            - action: 'initialize' or 'process'
            - sessionId: Session identifier
            - sourceLanguage: Source language code
            - audioData: Base64-encoded audio (optional)
            - connectionId: WebSocket connection ID (optional)
        
        context: Lambda context object
    
    Returns:
        Response dict with statusCode and body
    """
    global partial_processor, quality_analyzer, metrics_emitter, speaker_notifier
    global websocket_parser, connection_validator, rate_limiter, format_validator
    
    try:
        # Determine event type
        is_kinesis_event = 'Records' in event and len(event.get('Records', [])) > 0 and 'kinesis' in event['Records'][0]
        is_websocket_event = 'requestContext' in event and 'connectionId' in event.get('requestContext', {})
        is_pcm_batch = 'audio' in event and isinstance(event.get('audio'), dict)
        
        if is_kinesis_event:
            # Handle Kinesis batch event (Phase 4 - primary path)
            logger.info("Processing Kinesis batch event")
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(handle_kinesis_batch(event, context))
        elif is_websocket_event:
            # Handle WebSocket audio event
            logger.info("Processing WebSocket audio event")
            return handle_websocket_audio_event(event, context)
        elif is_pcm_batch:
            # Handle PCM batch from s3_audio_consumer (Phase 3 - deprecated)
            logger.info("Processing PCM batch from s3_audio_consumer")
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(handle_pcm_batch(event, context))
        else:
            # Handle direct invocation (legacy/testing)
            logger.info("Processing direct invocation event")
            return handle_direct_invocation(event, context)
            
    except Exception as e:
        logger.error(f"Error in lambda_handler: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }


def get_active_listener_languages(session_id: str) -> list:
    """
    Get active target languages from connected listeners (cost optimization).
    
    This queries the Connections table to find which languages actually have
    active listeners, so we only translate to languages that are being used.
    
    Benefits:
    - 50-90% reduction in translation costs
    - 50-90% reduction in TTS costs
    - Faster processing (fewer API calls)
    
    Args:
        session_id: Session identifier
    
    Returns:
        List of target language codes with active listeners
    """
    try:
        # Query DynamoDB directly (no shared layer dependency)
        dynamodb_client = boto3.resource('dynamodb')
        connections_table_name = os.environ.get('CONNECTIONS_TABLE', 'Connections-dev')
        connections_table = dynamodb_client.Table(connections_table_name)
        
        # Query GSI for all connections in this session
        response = connections_table.query(
            IndexName='sessionId-targetLanguage-index',
            KeyConditionExpression='sessionId = :sid',
            FilterExpression='#role = :role',
            ExpressionAttributeNames={'#role': 'role'},
            ExpressionAttributeValues={
                ':sid': session_id,
                ':role': 'listener'
            }
        )
        
        connections = response.get('Items', [])
        
        # Extract unique target languages
        unique_languages = set(
            conn.get('targetLanguage')
            for conn in connections
            if conn.get('targetLanguage')
        )
        
        active_languages = list(unique_languages)
        
        logger.info(
            f"Active listener languages for session {session_id}: {active_languages}"
        )
        
        return active_languages
        
    except Exception as e:
        logger.error(
            f"Error querying active listener languages for session {session_id}: {str(e)}",
            exc_info=True
        )
        # On error, return empty list (no translation)
        return []


def handle_direct_invocation(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle direct invocation (non-WebSocket) for testing and legacy support.
    
    Args:
        event: Lambda event with action, sessionId, etc.
        context: Lambda context
    
    Returns:
        Response dict
    """
    global partial_processor, quality_analyzer, metrics_emitter, speaker_notifier
    
    try:
        # Extract session information
        session_id = event.get('sessionId', '')
        source_language = event.get('sourceLanguage', 'en')
        action = event.get('action', 'process')
        
        logger.info(
            f"Direct invocation: action={action}, "
            f"session={session_id}, language={source_language}"
        )
        
        # Initialize processor on cold start
        if partial_processor is None:
            logger.info("Cold start: Initializing PartialResultProcessor")
            config = _load_config_from_environment()
            partial_processor = PartialResultProcessor(
                config=config,
                session_id=session_id,
                source_language=source_language
            )
            logger.info("PartialResultProcessor initialized successfully")
        
        # Initialize audio quality components on cold start
        if quality_analyzer is None:
            logger.info("Cold start: Initializing audio quality components")
            try:
                quality_config = _load_quality_config_from_environment()
                quality_analyzer = AudioQualityAnalyzer(quality_config)
                metrics_emitter = QualityMetricsEmitter(cloudwatch, eventbridge)
                speaker_notifier = SpeakerNotifier(websocket_manager=None)  # WebSocket manager to be injected
                logger.info("Audio quality components initialized successfully")
            except ConfigurationError as e:
                logger.error(
                    f"Invalid audio quality configuration: {e}. "
                    f"Audio quality validation will be disabled.",
                    exc_info=True
                )
                # Continue without quality validation if configuration is invalid
                quality_analyzer = None
                metrics_emitter = None
                speaker_notifier = None
            except Exception as e:
                logger.error(
                    f"Failed to initialize audio quality components: {e}. "
                    f"Audio quality validation will be disabled.",
                    exc_info=True
                )
                # Continue without quality validation if initialization fails
                quality_analyzer = None
                metrics_emitter = None
                speaker_notifier = None
        
        # Bridge async/sync: Run async processing in event loop
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            process_audio_async(event, context, partial_processor)
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }


def handle_websocket_audio_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle WebSocket audio event from API Gateway.
    
    This function processes audio chunks from WebSocket connections:
    1. Parse WebSocket message and extract audio data
    2. Validate connection and session
    3. Check rate limits
    4. Validate audio format
    5. Stream to Transcribe (initialize stream if needed)
    6. Handle backpressure with buffer
    
    Args:
        event: WebSocket event from API Gateway
        context: Lambda context
    
    Returns:
        Response dict with statusCode
    """
    global websocket_parser, connection_validator, rate_limiter, format_validator
    global partial_processor, active_streams
    
    try:
        # Initialize components on cold start
        _initialize_websocket_components()
        
        # Step 1: Parse WebSocket message
        try:
            connection_id, audio_bytes = websocket_parser.parse_audio_message(event)
            logger.info(
                f"Parsed WebSocket message: connection={connection_id}, "
                f"audio_size={len(audio_bytes)} bytes"
            )
        except WebSocketParseError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Invalid message format',
                    'message': str(e)
                })
            }
        
        # Step 2: Validate connection and session
        try:
            validation_result = connection_validator.validate_connection_and_session(
                connection_id
            )
            session_id = validation_result.session_id
            source_language = validation_result.source_language
            
            logger.info(
                f"Validation successful: session={session_id}, "
                f"language={source_language}"
            )
        except UnauthorizedError as e:
            logger.warning(f"Unauthorized connection: {e}")
            return {
                'statusCode': 403,
                'body': json.dumps({
                    'error': 'Unauthorized',
                    'message': str(e)
                })
            }
        except SessionNotFoundError as e:
            logger.warning(f"Session not found: {e}")
            return {
                'statusCode': 404,
                'body': json.dumps({
                    'error': 'Session not found',
                    'message': str(e)
                })
            }
        except SessionInactiveError as e:
            logger.warning(f"Session inactive: {e}")
            return {
                'statusCode': 410,
                'body': json.dumps({
                    'error': 'Session inactive',
                    'message': str(e)
                })
            }
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Validation failed',
                    'message': str(e)
                })
            }
        
        # Step 3: Check rate limits
        if not rate_limiter.check_rate_limit(connection_id):
            logger.warning(f"Rate limit exceeded for connection {connection_id}")
            
            # Check if warning should be sent
            if rate_limiter.should_send_warning(connection_id):
                # TODO: Send warning message to speaker via WebSocket
                logger.warning(f"Sending rate limit warning to {connection_id}")
            
            # Check if connection should be closed
            if rate_limiter.should_close_connection(connection_id):
                logger.error(f"Closing connection {connection_id} due to rate limit violations")
                # TODO: Close WebSocket connection
                return {
                    'statusCode': 429,
                    'body': json.dumps({
                        'error': 'Rate limit exceeded',
                        'message': 'Connection closed due to excessive rate limit violations'
                    })
                }
            
            # Drop this chunk
            return {
                'statusCode': 429,
                'body': json.dumps({
                    'error': 'Rate limit exceeded',
                    'message': 'Audio chunk dropped'
                })
            }
        
        # Step 4: Validate audio format (first chunk only, then cached)
        try:
            format_validator.validate_audio_chunk(connection_id, audio_bytes)
        except FormatValidationError as e:
            logger.error(f"Invalid audio format: {e}")
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Invalid audio format',
                    'message': str(e)
                })
            }
        
        # Step 5: Initialize or get Transcribe stream
        try:
            stream_info = _get_or_create_stream(session_id, source_language)
            client, manager, handler, buffer, _ = stream_info
            
            # Update last activity time
            active_streams[session_id] = (
                client, manager, handler, buffer, time.time()
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize Transcribe stream: {e}", exc_info=True)
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Stream initialization failed',
                    'message': str(e)
                })
            }
        
        # Step 6: Extract emotion dynamics from audio (if enabled)
        try:
            loop = asyncio.get_event_loop()
            emotion_data = loop.run_until_complete(
                process_audio_chunk_with_emotion(session_id, audio_bytes)
            )
            
            if emotion_data:
                logger.debug(
                    f"Emotion data extracted for session {session_id}: "
                    f"volume={emotion_data.get('volume')}, "
                    f"rate={emotion_data.get('rate')}"
                )
        except Exception as e:
            logger.warning(f"Failed to extract emotion data: {e}")
            # Continue processing even if emotion extraction fails
        
        # Step 7: Add audio to buffer and send to Transcribe
        try:
            # Add to buffer (handles backpressure)
            buffer.add_chunk(audio_bytes, session_id)
            
            # Send audio to Transcribe stream asynchronously
            # Run in event loop
            loop = asyncio.get_event_loop()
            success = loop.run_until_complete(
                _send_audio_to_stream(session_id, audio_bytes)
            )
            
            if not success:
                logger.error(f"Failed to send audio to Transcribe for session {session_id}")
                # Continue processing - buffer will hold the audio
            
            logger.debug(
                f"Audio chunk processed for session {session_id}: "
                f"buffer_size={buffer.size()}/{buffer.capacity_chunks}, "
                f"sent_to_transcribe={success}"
            )
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Audio chunk processed',
                    'sessionId': session_id,
                    'bufferSize': buffer.size(),
                    'sentToTranscribe': success
                })
            }
            
        except Exception as e:
            logger.error(f"Failed to process audio chunk: {e}", exc_info=True)
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Audio processing failed',
                    'message': str(e)
                })
            }
        
    except Exception as e:
        logger.error(f"Unexpected error in handle_websocket_audio_event: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }


async def handle_kinesis_batch(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle Kinesis batch event (Phase 4 - primary path).
    
    This processes batched audio records from Kinesis Data Stream:
    1. Group records by sessionId (partition key)
    2. Concatenate PCM chunks per session
    3. Transcribe using Transcribe Streaming API (NOT batch jobs)
    4. Translate to target languages
    5. Generate TTS for each language
    6. Store TTS audio in S3
    7. Send WebSocket notifications to listeners
    
    Benefits vs Phase 3:
    - Native Kinesis batching (3-second windows)
    - Transcribe Streaming API (500ms vs 15-60s)
    - 92% fewer Lambda invocations
    - No S3 ListObjects race conditions
    
    Args:
        event: Kinesis batch event containing:
            - Records: List of Kinesis records
              - kinesis.data: base64-encoded PCM bytes
              - kinesis.partitionKey: sessionId
              - kinesis.sequenceNumber: Sequence number
        context: Lambda context
    
    Returns:
        Response dict with statusCode and results
    """
    try:
        records = event.get('Records', [])
        
        if not records:
            logger.warning("Received empty Kinesis batch")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Empty batch, no processing'})
            }
        
        logger.info(f"Processing Kinesis batch with {len(records)} records")
        
        # Step 1: Group records by sessionId (partition key)
        sessions = {}
        for record in records:
            kinesis_data = record.get('kinesis', {})
            pcm_bytes = base64.b64decode(kinesis_data.get('data', ''))
            partition_key = kinesis_data.get('partitionKey', '')  # sessionId
            
            if not partition_key:
                logger.warning("Record missing partition key, skipping")
                continue
            
            if partition_key not in sessions:
                sessions[partition_key] = []
            sessions[partition_key].append(pcm_bytes)
        
        logger.info(f"Grouped records into {len(sessions)} sessions")
        
        # Step 2-7: Process each session
        all_results = []
        
        for session_id, pcm_chunks in sessions.items():
            try:
                # Concatenate PCM chunks
                pcm_data = b''.join(pcm_chunks)
                duration = len(pcm_data) / (16000 * 2)  # 16kHz, 16-bit (2 bytes per sample)
                
                logger.info(
                    f"Session {session_id}: {len(pcm_chunks)} chunks, "
                    f"{len(pcm_data)} bytes, {duration:.2f}s"
                )
                
                # Get session metadata from DynamoDB
                dynamodb_client = boto3.resource('dynamodb')
                sessions_table_name = os.environ.get('SESSIONS_TABLE_NAME', 'Sessions-dev')
                sessions_table = dynamodb_client.Table(sessions_table_name)
                
                session_response = sessions_table.get_item(Key={'sessionId': session_id})
                session = session_response.get('Item')
                
                if not session:
                    logger.error(f"Session not found in DynamoDB: {session_id}")
                    continue
                
                source_language = session.get('sourceLanguage', 'en')
                
                # COST OPTIMIZATION: Only translate to languages with active listeners
                active_languages = get_active_listener_languages(session_id)
                
                if not active_languages:
                    logger.info(
                        f"No active listeners for session {session_id}, skipping translation "
                        f"(cost savings: 100%)"
                    )
                    all_results.append({
                        'sessionId': session_id,
                        'skipped': True,
                        'reason': 'No active listeners',
                        'costSavings': '100%'
                    })
                    continue
                
                # Log cost savings if some languages are skipped
                session_target_languages = session.get('targetLanguages', [])
                skipped_languages = set(session_target_languages) - set(active_languages)
                
                if skipped_languages:
                    savings_pct = int(len(skipped_languages) / len(session_target_languages) * 100)
                    logger.info(
                        f"Cost optimization for session {session_id}: "
                        f"Processing {len(active_languages)} languages (active listeners), "
                        f"skipping {len(skipped_languages)} languages (no listeners): {skipped_languages}. "
                        f"Cost savings: {savings_pct}%"
                    )
                
                # Convert to AWS language code
                aws_language = _convert_to_aws_language_code(source_language)
                
                # Step 3: Transcribe using Transcribe Streaming API
                try:
                    transcript = await transcribe_streaming(
                        pcm_data,
                        aws_language,
                        16000
                    )
                    logger.info(f"Transcription complete for {session_id}: '{transcript[:100]}...'")
                except Exception as transcribe_error:
                    logger.error(f"Transcription failed for {session_id}: {str(transcribe_error)}")
                    transcript = "[Transcription unavailable]"
                
                # Step 4-7: Translate and deliver ONLY to active listener languages
                session_results = await process_translation_and_delivery(
                    session_id,
                    transcript,
                    source_language,
                    active_languages,  # Use active languages, not all target languages
                    int(time.time() * 1000),
                    duration
                )
                
                all_results.append({
                    'sessionId': session_id,
                    'results': session_results
                })
                
            except Exception as session_error:
                logger.error(
                    f"Error processing session {session_id}: {str(session_error)}",
                    exc_info=True
                )
                all_results.append({
                    'sessionId': session_id,
                    'error': str(session_error)
                })
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Kinesis batch processed',
                'recordCount': len(records),
                'sessionCount': len(sessions),
                'results': all_results
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing Kinesis batch: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Kinesis batch processing failed',
                'message': str(e)
            })
        }


async def transcribe_streaming(
    pcm_bytes: bytes,
    language_code: str,
    sample_rate: int
) -> str:
    """
    Transcribe PCM audio using AWS Transcribe Streaming API (Phase 4).
    
    This uses HTTP/2 streaming (not batch jobs) for low latency:
    - No queue time
    - No engine boot overhead
    - ~500ms latency for 3-second audio
    
    Args:
        pcm_bytes: PCM audio data
        language_code: AWS language code (e.g., 'en-US')
        sample_rate: Audio sample rate
    
    Returns:
        Transcribed text
    """
    try:
        from amazon_transcribe.client import TranscribeStreamingClient
        from amazon_transcribe.handlers import TranscriptResultStreamHandler
        from amazon_transcribe.model import TranscriptEvent
        
        # Create streaming client
        client = TranscribeStreamingClient(region=os.environ.get('AWS_REGION', 'us-east-1'))
        
        # Start stream
        stream = await client.start_stream_transcription(
            language_code=language_code,
            media_sample_rate_hz=sample_rate,
            media_encoding='pcm'
        )
        
        # Send PCM data in chunks (Transcribe has frame size limit)
        # Max frame size is ~32KB, send in 16KB chunks to be safe
        chunk_size = 16384  # 16KB per chunk
        for i in range(0, len(pcm_bytes), chunk_size):
            chunk = pcm_bytes[i:i + chunk_size]
            await stream.input_stream.send_audio_event(audio_chunk=chunk)
        
        await stream.input_stream.end_stream()
        
        # Collect transcript
        transcript_text = ""
        async for event in stream.output_stream:
            if isinstance(event, TranscriptEvent):
                for result in event.transcript.results:
                    if not result.is_partial:
                        for alt in result.alternatives:
                            transcript_text = alt.transcript
        
        return transcript_text if transcript_text else "[No transcription]"
        
    except Exception as e:
        logger.error(f"Transcribe Streaming error: {str(e)}", exc_info=True)
        raise


async def process_translation_and_delivery(
    session_id: str,
    transcript: str,
    source_language: str,
    target_languages: list,
    timestamp: int,
    duration: float
) -> list:
    """
    Translate transcript and deliver to listeners.
    
    This is extracted from handle_pcm_batch for reuse in handle_kinesis_batch.
    
    Args:
        session_id: Session identifier
        transcript: Transcribed text
        source_language: Source language code
        target_languages: List of target language codes
        timestamp: Audio timestamp
        duration: Audio duration in seconds
    
    Returns:
        List of results per target language
    """
    # Initialize clients
    s3_client = boto3.client('s3')
    translate_client = boto3.client('translate')
    polly_client = boto3.client('polly')
    
    s3_bucket = os.environ.get('S3_BUCKET_NAME', f'translation-audio-{os.environ.get("STAGE", "dev")}')
    
    # API Gateway client for WebSocket
    api_endpoint = os.environ.get('API_GATEWAY_ENDPOINT', '')
    if api_endpoint:
        apigw_client = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=api_endpoint
        )
    else:
        logger.warning("API_GATEWAY_ENDPOINT not set, cannot send WebSocket notifications")
        apigw_client = None
    
    results = []
    for target_lang in target_languages:
        try:
            # Translate
            try:
                translation_response = translate_client.translate_text(
                    Text=transcript,
                    SourceLanguageCode=source_language,
                    TargetLanguageCode=target_lang
                )
                translated_text = translation_response['TranslatedText']
                logger.info(f"Translated to {target_lang}: '{translated_text[:50]}...'")
            except Exception as translate_error:
                logger.error(f"Translation failed for {target_lang}: {str(translate_error)}")
                translated_text = transcript
            
            # Generate TTS
            try:
                voice_id = get_polly_voice_for_language(target_lang)
                tts_response = polly_client.synthesize_speech(
                    Text=translated_text,
                    OutputFormat='mp3',
                    VoiceId=voice_id,
                    Engine='neural',
                    SampleRate='24000'
                )
                tts_audio_bytes = tts_response['AudioStream'].read()
                logger.info(f"Generated TTS for {target_lang}: {len(tts_audio_bytes)} bytes")
            except Exception as tts_error:
                logger.error(f"TTS failed for {target_lang}: {str(tts_error)}")
                tts_audio_bytes = create_silent_mp3(duration)
            
            # Store in S3
            s3_key = f"sessions/{session_id}/translated/{target_lang}/{timestamp}.mp3"
            
            # Encode transcript to ASCII for S3 metadata (only ASCII allowed)
            try:
                transcript_ascii = translated_text[:1000].encode('ascii', errors='ignore').decode('ascii')
            except:
                transcript_ascii = "[Transcript contains non-ASCII characters]"
            
            s3_client.put_object(
                Bucket=s3_bucket,
                Key=s3_key,
                Body=tts_audio_bytes,
                ContentType='audio/mpeg',
                Metadata={
                    'sessionId': session_id,
                    'targetLanguage': target_lang,
                    'transcript': transcript_ascii,  # ASCII-only
                    'timestamp': str(timestamp),
                    'duration': str(duration),
                }
            )
            
            # Generate presigned URL
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': s3_bucket, 'Key': s3_key},
                ExpiresIn=600
            )
            
            # Notify listeners
            if apigw_client:
                success = await notify_listeners_for_language(
                    apigw_client,
                    session_id,
                    target_lang,
                    presigned_url,
                    timestamp,
                    duration,
                    translated_text
                )
                
                if success:
                    logger.info(f"Notified listeners for language {target_lang}")
            
            results.append({
                'targetLanguage': target_lang,
                'success': True,
                's3Key': s3_key
            })
            
        except Exception as lang_error:
            logger.error(
                f"Error processing language {target_lang}: {str(lang_error)}",
                exc_info=True
            )
            results.append({
                'targetLanguage': target_lang,
                'success': False,
                'error': str(lang_error)
            })
    
    return results


async def process_audio_chunk_with_emotion(
    session_id: str,
    audio_bytes: bytes,
    sample_rate: int = 16000
) -> Optional[Dict[str, Any]]:
    """
    Process audio chunk with emotion detection.
    
    This function extracts emotion dynamics from audio chunks and caches
    them for correlation with transcripts. It handles errors gracefully
    and continues processing even if emotion extraction fails.
    
    Args:
        session_id: Session identifier
        audio_bytes: PCM audio data (16-bit, mono)
        sample_rate: Audio sample rate in Hz (default: 16000)
    
    Returns:
        Dictionary with emotion data (volume, rate, energy, timestamp)
        or None if emotion detection is disabled or fails
    """
    global emotion_orchestrator, emotion_cache
    
    # Skip if emotion detection is disabled
    if emotion_orchestrator is None:
        return None
    
    try:
        # Convert bytes to numpy array
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
        
        # Extract emotion dynamics using orchestrator
        # This runs volume and rate detection in parallel
        dynamics, volume_ms, rate_ms, combined_ms = emotion_orchestrator.detect_audio_dynamics(
            audio_data=audio_array,
            sample_rate=sample_rate,
            correlation_id=session_id
        )
        
        # Extract emotion data from dynamics
        # Map volume level to 0.0-1.0 scale
        volume_mapping = {
            'whisper': 0.2,
            'soft': 0.4,
            'medium': 0.6,
            'loud': 1.0
        }
        volume = volume_mapping.get(dynamics.volume.level, 0.6)
        
        # Map rate classification to speaking rate multiplier
        rate_mapping = {
            'very_slow': 0.7,
            'slow': 0.85,
            'medium': 1.0,
            'fast': 1.15,
            'very_fast': 1.3
        }
        rate = rate_mapping.get(dynamics.rate.classification, 1.0)
        
        # Calculate energy from volume (normalized 0.0-1.0)
        # Energy is derived from volume level
        energy = volume
        
        # Cache emotion data with session_id and timestamp
        emotion_data = {
            'volume': volume,
            'rate': rate,
            'energy': energy,
            'timestamp': int(time.time() * 1000),
            'volume_level': dynamics.volume.level,
            'rate_classification': dynamics.rate.classification,
            'volume_db': dynamics.volume.db_value,
            'rate_wpm': dynamics.rate.wpm
        }
        
        emotion_cache[session_id] = emotion_data
        
        # Emit CloudWatch metrics for successful emotion extraction
        try:
            cloudwatch.put_metric_data(
                Namespace='AudioTranscription/EmotionDetection',
                MetricData=[
                    {
                        'MetricName': 'EmotionExtractionLatency',
                        'Value': combined_ms,
                        'Unit': 'Milliseconds',
                        'Dimensions': [
                            {'Name': 'SessionId', 'Value': session_id}
                        ]
                    },
                    {
                        'MetricName': 'EmotionCacheSize',
                        'Value': len(emotion_cache),
                        'Unit': 'Count'
                    }
                ]
            )
        except Exception as metric_error:
            logger.warning(f"Failed to emit emotion extraction metrics: {metric_error}")
        
        logger.debug(
            f"Emotion data extracted for session {session_id}: "
            f"volume={dynamics.volume.level} ({volume:.2f}), "
            f"rate={dynamics.rate.classification} ({rate:.2f}), "
            f"energy={energy:.2f}, "
            f"latency={combined_ms}ms"
        )
        
        return emotion_data
        
    except Exception as e:
        logger.error(
            f"Error extracting emotion data for session {session_id}: {e}",
            exc_info=True
        )
        
        # Emit CloudWatch metric for emotion extraction failure
        try:
            cloudwatch.put_metric_data(
                Namespace='AudioTranscription/EmotionDetection',
                MetricData=[
                    {
                        'MetricName': 'EmotionExtractionErrors',
                        'Value': 1,
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'SessionId', 'Value': session_id}
                        ]
                    }
                ]
            )
        except Exception as metric_error:
            logger.warning(f"Failed to emit emotion extraction error metric: {metric_error}")
        
        # Return default neutral emotion values on failure
        default_emotion = {
            'volume': 0.5,
            'rate': 1.0,
            'energy': 0.5,
            'timestamp': int(time.time() * 1000),
            'volume_level': 'medium',
            'rate_classification': 'medium',
            'volume_db': -15.0,
            'rate_wpm': 145.0
        }
        
        # Cache default values
        emotion_cache[session_id] = default_emotion
        
        logger.info(
            f"Using default neutral emotion values for session {session_id} "
            f"after extraction failure"
        )
        
        return default_emotion


async def handle_pcm_batch(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle PCM batch from s3_audio_consumer (Phase 3).
    
    This processes aggregated audio batches:
    1. Decode PCM audio data
    2. Transcribe using AWS Transcribe
    3. Translate to target languages
    4. Generate TTS for each language
    5. Store TTS audio in S3
    6. Send WebSocket notifications to listeners
    
    Args:
        event: Event from s3_audio_consumer containing:
            - sessionId: Session identifier
            - audio: {data: hex, format, sampleRate, channels, encoding}
            - sourceLanguage: Source language code
            - targetLanguages: List of target language codes
            - timestamp: Batch start timestamp
            - duration: Batch duration in seconds
            - batchIndex: Index of this batch
        context: Lambda context
    
    Returns:
        Response dict with statusCode and results
    """
    try:
        # Extract event data
        session_id = event['sessionId']
        audio_info = event['audio']
        source_language = event['sourceLanguage']
        target_languages = event['targetLanguages']
        timestamp = event['timestamp']
        duration = event['duration']
        batch_index = event['batchIndex']
        
        logger.info(
            f"Processing PCM batch for session {session_id}: "
            f"batch={batch_index}, duration={duration:.2f}s, "
            f"languages={target_languages}"
        )
        
        # Decode PCM audio from hex string
        pcm_bytes = bytes.fromhex(audio_info['data'])
        sample_rate = audio_info['sampleRate']
        
        logger.info(f"Decoded PCM audio: {len(pcm_bytes)} bytes, {sample_rate}Hz")
        
        # Step 2: Transcribe audio using AWS Transcribe
        # For Phase 3, using simplified approach with StartTranscriptionJob
        aws_language = _convert_to_aws_language_code(source_language)
        
        try:
            transcript = await transcribe_pcm_audio(
                pcm_bytes, 
                aws_language, 
                sample_rate,
                session_id,
                batch_index
            )
            logger.info(f"Transcription complete: '{transcript[:100]}...'")
        except Exception as transcribe_error:
            logger.error(f"Transcription failed: {str(transcribe_error)}")
            # Use fallback
            transcript = "[Transcription unavailable]"
        
        # Step 3-6: Translate and deliver for each target language
        # TODO: This should use the actual translation pipeline
        # For now, creating placeholder implementation
        
        # Initialize S3 client for TTS storage
        s3_client = boto3.client('s3')
        s3_bucket = os.environ.get('S3_BUCKET_NAME', f'translation-audio-{os.environ.get("STAGE", "dev")}')
        
        # Initialize API Gateway Management client for WebSocket
        api_endpoint = os.environ.get('API_GATEWAY_ENDPOINT', '')
        if api_endpoint:
            apigw_client = boto3.client(
                'apigatewaymanagementapi',
                endpoint_url=api_endpoint
            )
        else:
            logger.warning("API_GATEWAY_ENDPOINT not set, cannot send WebSocket notifications")
            apigw_client = None
        
        # Initialize Translate and Polly clients
        translate_client = boto3.client('translate')
        polly_client = boto3.client('polly')
        
        # Process each target language
        results = []
        for target_lang in target_languages:
            try:
                # Step 3: Translate transcript
                try:
                    translation_response = translate_client.translate_text(
                        Text=transcript,
                        SourceLanguageCode=source_language,
                        TargetLanguageCode=target_lang
                    )
                    translated_text = translation_response['TranslatedText']
                    logger.info(f"Translated to {target_lang}: '{translated_text[:50]}...'")
                except Exception as translate_error:
                    logger.error(f"Translation failed for {target_lang}: {str(translate_error)}")
                    translated_text = transcript  # Use original if translation fails
                
                # Step 4: Generate TTS audio with Polly
                try:
                    voice_id = get_polly_voice_for_language(target_lang)
                    tts_response = polly_client.synthesize_speech(
                        Text=translated_text,
                        OutputFormat='mp3',
                        VoiceId=voice_id,
                        Engine='neural',
                        SampleRate='24000'
                    )
                    tts_audio_bytes = tts_response['AudioStream'].read()
                    logger.info(f"Generated TTS for {target_lang}: {len(tts_audio_bytes)} bytes")
                except Exception as tts_error:
                    logger.error(f"TTS failed for {target_lang}: {str(tts_error)}")
                    # Create silent MP3 as fallback
                    tts_audio_bytes = create_silent_mp3(duration)
                
                # Store in S3
                s3_key = f"sessions/{session_id}/translated/{target_lang}/{timestamp}.mp3"
                s3_client.put_object(
                    Bucket=s3_bucket,
                    Key=s3_key,
                    Body=tts_audio_bytes,
                    ContentType='audio/mpeg',
                    Metadata={
                        'sessionId': session_id,
                        'targetLanguage': target_lang,
                        'transcript': translated_text[:1000],
                        'timestamp': str(timestamp),
                        'duration': str(duration),
                    }
                )
                
                logger.info(f"Stored TTS audio in S3: {s3_key}")
                
                # Generate presigned URL
                presigned_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': s3_bucket, 'Key': s3_key},
                    ExpiresIn=600  # 10 minutes
                )
                
                # Send WebSocket notification to listeners
                if apigw_client:
                    success = await notify_listeners_for_language(
                        apigw_client,
                        session_id,
                        target_lang,
                        presigned_url,
                        timestamp,
                        duration,
                        translated_text
                    )
                    
                    if success:
                        logger.info(f"Notified listeners for language {target_lang}")
                
                results.append({
                    'targetLanguage': target_lang,
                    'success': True,
                    's3Key': s3_key
                })
                
            except Exception as lang_error:
                logger.error(
                    f"Error processing language {target_lang}: {str(lang_error)}",
                    exc_info=True
                )
                results.append({
                    'targetLanguage': target_lang,
                    'success': False,
                    'error': str(lang_error)
                })
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'PCM batch processed',
                'sessionId': session_id,
                'batchIndex': batch_index,
                'results': results
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing PCM batch: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'PCM batch processing failed',
                'message': str(e)
            })
        }


async def notify_listeners_for_language(
    apigw_client,
    session_id: str,
    target_language: str,
    presigned_url: str,
    timestamp: int,
    duration: float,
    transcript: str
) -> bool:
    """
    Send WebSocket notification to listeners for specific language.
    
    Args:
        apigw_client: API Gateway Management client
        session_id: Session identifier  
        target_language: Target language code
        presigned_url: S3 presigned URL for audio
        timestamp: Audio timestamp
        duration: Audio duration in seconds
        transcript: Translated transcript
    
    Returns:
        True if at least one listener notified successfully
    """
    try:
        # Get connections for this session and language from DynamoDB
        dynamodb_client = boto3.resource('dynamodb')
        connections_table_name = os.environ.get('CONNECTIONS_TABLE', 'Connections-dev')
        connections_table = dynamodb_client.Table(connections_table_name)
        
        # Query GSI: sessionId-targetLanguage-index
        response = connections_table.query(
            IndexName='sessionId-targetLanguage-index',
            KeyConditionExpression='sessionId = :sid AND targetLanguage = :lang',
            ExpressionAttributeValues={
                ':sid': session_id,
                ':lang': target_language
            }
        )
        
        connections = response.get('Items', [])
        
        if not connections:
            logger.warning(f"No listeners found for {target_language} in session {session_id}")
            return False
        
        # Create message
        message = {
            'type': 'translatedAudio',
            'sessionId': session_id,
            'targetLanguage': target_language,
            'url': presigned_url,
            'timestamp': timestamp,
            'duration': duration,
            'transcript': transcript,
            'sequenceNumber': timestamp  # Use timestamp as sequence
        }
        
        message_data = json.dumps(message).encode('utf-8')
        
        # Send to each connection
        success_count = 0
        for connection in connections:
            connection_id = connection.get('connectionId')
            
            try:
                apigw_client.post_to_connection(
                    ConnectionId=connection_id,
                    Data=message_data
                )
                success_count += 1
                
            except apigw_client.exceptions.GoneException:
                logger.info(f"Connection gone: {connection_id}")
            except Exception as send_error:
                logger.error(f"Error sending to connection {connection_id}: {str(send_error)}")
        
        logger.info(
            f"Notified {success_count}/{len(connections)} listeners for {target_language}"
        )
        
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Error notifying listeners: {str(e)}", exc_info=True)
        return False


def _initialize_websocket_components() -> None:
    """
    Initialize WebSocket processing components on cold start.
    
    Initializes:
    - WebSocket message parser
    - Connection validator
    - Rate limiter
    - Audio format validator
    - Translation Pipeline client
    - Emotion detection orchestrator
    """
    global websocket_parser, connection_validator, rate_limiter, format_validator
    global translation_pipeline, emotion_orchestrator
    
    if websocket_parser is None:
        logger.info("Cold start: Initializing WebSocket components")
        
        # Initialize parser
        websocket_parser = WebSocketMessageParser()
        
        # Initialize validator (requires table names from environment)
        try:
            import sys
            session_mgmt_path = os.path.join(
                os.path.dirname(__file__),
                '../../../session-management'
            )
            if os.path.exists(session_mgmt_path):
                sys.path.insert(0, session_mgmt_path)
            
            from shared.data_access.connections_repository import ConnectionsRepository
            from shared.data_access.sessions_repository import SessionsRepository
            from shared.config.table_names import get_table_name, SESSIONS_TABLE_NAME, CONNECTIONS_TABLE_NAME
            
            connections_repo = ConnectionsRepository(get_table_name('CONNECTIONS_TABLE_NAME', CONNECTIONS_TABLE_NAME))
            sessions_repo = SessionsRepository(get_table_name('SESSIONS_TABLE_NAME', SESSIONS_TABLE_NAME))
            
            connection_validator = ConnectionValidator(connections_repo, sessions_repo)
            
        except Exception as e:
            logger.error(f"Failed to initialize connection validator: {e}")
            # Continue without validator - will fail on first validation attempt
            connection_validator = None
        
        # Initialize rate limiter
        rate_limit = int(os.getenv('AUDIO_RATE_LIMIT', '50'))
        rate_limiter = AudioRateLimiter(
            limit=rate_limit,
            cloudwatch_client=cloudwatch
        )
        
        # Initialize format validator
        format_validator = AudioFormatValidator()
        
        # Initialize Translation Pipeline client
        translation_function_name = os.getenv(
            'TRANSLATION_PIPELINE_FUNCTION_NAME',
            'TranslationProcessor'
        )
        translation_pipeline = LambdaTranslationPipeline(
            function_name=translation_function_name
        )
        logger.info(
            f"Translation Pipeline client initialized: "
            f"function={translation_function_name}"
        )
        
        # Initialize Emotion Detection orchestrator if enabled
        enable_emotion_detection = os.getenv('ENABLE_EMOTION_DETECTION', 'true').lower() == 'true'
        if enable_emotion_detection:
            try:
                emotion_orchestrator = AudioDynamicsOrchestrator()
                logger.info("Emotion detection orchestrator initialized successfully")
            except Exception as e:
                logger.warning(
                    f"Failed to initialize emotion detection orchestrator: {e}. "
                    f"Emotion detection will be disabled.",
                    exc_info=True
                )
                emotion_orchestrator = None
        else:
            logger.info("Emotion detection disabled via ENABLE_EMOTION_DETECTION environment variable")
            emotion_orchestrator = None
        
        logger.info("WebSocket components initialized successfully")


def _get_or_create_stream(
    session_id: str,
    source_language: str
) -> tuple:
    """
    Get existing Transcribe stream or create new one.
    
    Args:
        session_id: Session identifier
        source_language: Source language code
    
    Returns:
        Tuple of (client, manager, handler, buffer, last_activity_time, is_active)
    """
    global active_streams, partial_processor, translation_pipeline
    
    # Check if stream already exists
    if session_id in active_streams:
        logger.debug(f"Using existing stream for session {session_id}")
        return active_streams[session_id]
    
    # Create new stream
    logger.info(f"Creating new Transcribe stream for session {session_id}")
    
    # Initialize partial processor if needed
    if partial_processor is None:
        config = _load_config_from_environment()
        partial_processor = PartialResultProcessor(
            config=config,
            session_id=session_id,
            source_language=source_language
        )
    
    # Create Transcribe client and manager
    # Convert ISO 639-1 to AWS language code (e.g., 'en' -> 'en-US')
    aws_language_code = _convert_to_aws_language_code(source_language)
    
    client, manager = create_transcribe_client_for_session(
        language_code=aws_language_code,
        sample_rate_hz=16000,
        encoding='pcm',
        region=os.getenv('AWS_REGION', 'us-east-1')
    )
    
    # Create stream handler with processor and translation pipeline
    # The handler will process transcription events and forward to translation
    handler = TranscribeStreamHandler(
        output_stream=None,  # Will be set when stream starts
        processor=partial_processor,
        session_id=session_id,
        source_language=source_language
    )
    
    # Inject translation pipeline into handler for forwarding
    handler.translation_pipeline = translation_pipeline
    
    # Inject emotion cache reference for accessing cached emotion data
    # The handler will use this to retrieve emotion data when forwarding to translation
    handler.emotion_cache = emotion_cache
    
    # Create audio buffer
    buffer = AudioBuffer(
        capacity_seconds=5.0,
        chunk_duration_ms=100,
        cloudwatch_client=cloudwatch
    )
    
    # Store stream info with is_active flag
    stream_info = (client, manager, handler, buffer, time.time(), False)
    active_streams[session_id] = stream_info
    
    logger.info(f"Created Transcribe stream for session {session_id}")
    
    return stream_info


def _convert_to_aws_language_code(iso_code: str) -> str:
    """
    Convert ISO 639-1 language code to AWS Transcribe language code.
    
    Args:
        iso_code: ISO 639-1 code (e.g., 'en', 'es')
    
    Returns:
        AWS language code (e.g., 'en-US', 'es-ES')
    """
    # Simple mapping for common languages
    # In production, this should be more comprehensive
    mapping = {
        'en': 'en-US',
        'es': 'es-ES',
        'fr': 'fr-FR',
        'de': 'de-DE',
        'it': 'it-IT',
        'pt': 'pt-BR',
        'ja': 'ja-JP',
        'ko': 'ko-KR',
        'zh': 'zh-CN',
        'ar': 'ar-SA',
        'hi': 'hi-IN',
        'ru': 'ru-RU'
    }
    
    return mapping.get(iso_code, f"{iso_code}-US")


async def _initialize_stream_async(session_id: str) -> bool:
    """
    Initialize Transcribe stream asynchronously.
    
    This function starts the Transcribe streaming connection and begins
    the event loop for processing transcription events.
    
    Args:
        session_id: Session identifier
    
    Returns:
        True if successful, False otherwise
    """
    global active_streams
    
    if session_id not in active_streams:
        logger.error(f"Cannot initialize stream: session {session_id} not found")
        return False
    
    try:
        client, manager, handler, buffer, last_activity, is_active = active_streams[session_id]
        
        # Skip if already active
        if is_active:
            logger.debug(f"Stream already active for session {session_id}")
            return True
        
        logger.info(f"Initializing Transcribe stream for session {session_id}")
        
        # Start the stream using the manager
        # This creates the output stream and starts the event loop
        output_stream = await manager.start_stream()
        
        # Set the output stream on the handler
        handler.output_stream = output_stream
        
        # Mark stream as active
        active_streams[session_id] = (
            client, manager, handler, buffer, time.time(), True
        )
        
        logger.info(f"Transcribe stream initialized for session {session_id}")
        return True
        
    except Exception as e:
        logger.error(
            f"Failed to initialize Transcribe stream for session {session_id}: {e}",
            exc_info=True
        )
        return False


async def _send_audio_to_stream(session_id: str, audio_bytes: bytes) -> bool:
    """
    Send audio chunk to Transcribe stream.
    
    This function sends audio data to the active Transcribe stream.
    If the stream is not initialized, it will attempt to initialize it first.
    
    Args:
        session_id: Session identifier
        audio_bytes: PCM audio data (16-bit, 16kHz, mono)
    
    Returns:
        True if successful, False otherwise
    """
    global active_streams
    
    if session_id not in active_streams:
        logger.error(f"Cannot send audio: session {session_id} not found")
        return False
    
    try:
        client, manager, handler, buffer, last_activity, is_active = active_streams[session_id]
        
        # Initialize stream if not active
        if not is_active:
            success = await _initialize_stream_async(session_id)
            if not success:
                logger.error(f"Failed to initialize stream for session {session_id}")
                return False
            
            # Reload stream info after initialization
            client, manager, handler, buffer, last_activity, is_active = active_streams[session_id]
        
        # Send audio to stream via manager
        await manager.send_audio(audio_bytes)
        
        # Update last activity time
        active_streams[session_id] = (
            client, manager, handler, buffer, time.time(), is_active
        )
        
        logger.debug(f"Sent {len(audio_bytes)} bytes to Transcribe stream for session {session_id}")
        return True
        
    except Exception as e:
        logger.error(
            f"Failed to send audio to stream for session {session_id}: {e}",
            exc_info=True
        )
        return False


def cleanup_idle_streams() -> None:
    """
    Clean up idle Transcribe streams.
    
    Closes streams that have been inactive for more than STREAM_IDLE_TIMEOUT_SECONDS.
    Should be called periodically.
    """
    global active_streams
    
    current_time = time.time()
    sessions_to_remove = []
    
    for session_id, stream_info in active_streams.items():
        *_, last_activity_time, is_active = stream_info
        idle_duration = current_time - last_activity_time
        
        if idle_duration >= STREAM_IDLE_TIMEOUT_SECONDS:
            logger.info(
                f"Closing idle stream for session {session_id} "
                f"(idle for {idle_duration:.1f} seconds)"
            )
            sessions_to_remove.append(session_id)
    
    # Remove idle streams
    for session_id in sessions_to_remove:
        asyncio.create_task(_close_stream_async(session_id))


async def _close_stream_async(session_id: str) -> None:
    """
    Close Transcribe stream for session asynchronously.
    
    This function gracefully closes the Transcribe stream, clears buffers,
    clears emotion cache, and removes the session from active streams.
    
    Args:
        session_id: Session identifier
    """
    global active_streams, emotion_cache
    
    if session_id not in active_streams:
        return
    
    try:
        client, manager, handler, buffer, last_activity, is_active = active_streams[session_id]
        
        logger.info(f"Closing Transcribe stream for session {session_id}")
        
        # Clear buffer
        buffer.clear()
        
        # Clear emotion cache for this session
        if session_id in emotion_cache:
            del emotion_cache[session_id]
            logger.debug(f"Cleared emotion cache for session {session_id}")
        
        # Close stream gracefully if active
        if is_active:
            try:
                await manager.end_stream()
                logger.debug(f"Ended Transcribe stream for session {session_id}")
            except Exception as e:
                logger.warning(f"Error ending stream for session {session_id}: {e}")
        
        # Remove from active streams
        del active_streams[session_id]
        
        logger.info(f"Closed stream for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error closing stream for session {session_id}: {e}", exc_info=True)


def _close_stream(session_id: str) -> None:
    """
    Close Transcribe stream for session (synchronous wrapper).
    
    This is a synchronous wrapper around _close_stream_async for
    compatibility with synchronous code paths.
    
    Args:
        session_id: Session identifier
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, create a task
            asyncio.create_task(_close_stream_async(session_id))
        else:
            # If loop is not running, run until complete
            loop.run_until_complete(_close_stream_async(session_id))
    except Exception as e:
        logger.error(f"Error in _close_stream wrapper: {e}", exc_info=True)


async def process_audio_async(
    event: Dict[str, Any],
    context: Any,
    processor: PartialResultProcessor
) -> Dict[str, Any]:
    """
    Async function that handles Transcribe streaming and event processing.
    
    This function is called by the synchronous lambda_handler and performs
    the actual asynchronous processing of audio and transcription events.
    It includes error handling and automatic fallback to final-only mode
    when Transcribe failures are detected.
    
    Args:
        event: Lambda event object
        context: Lambda context object
        processor: PartialResultProcessor instance
    
    Returns:
        Response dict with statusCode and body
    """
    global fallback_mode_enabled, fallback_reason
    
    try:
        action = event.get('action', 'process')
        session_id = event.get('sessionId', '')
        
        if action == 'initialize':
            # Initialize session (processor already created)
            logger.info(f"Session {session_id} initialized")
            
            # Mark audio session as active
            update_health_status(session_active=True, session_id=session_id)
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Session initialized',
                    'sessionId': session_id,
                    'partialResultsEnabled': processor.config.enabled and not fallback_mode_enabled,
                    'fallbackMode': fallback_mode_enabled,
                    'fallbackReason': fallback_reason
                })
            }
        
        elif action == 'process':
            # Process audio chunk
            # Note: Actual Transcribe streaming integration would go here
            # For now, this is a placeholder that demonstrates the structure
            
            logger.info(f"Processing audio for session {session_id}")
            
            try:
                # Check Transcribe service health before processing
                check_transcribe_health(session_id=session_id)
                
                # Extract audio data and parameters
                audio_data_b64 = event.get('audioData', '')
                sample_rate = event.get('sampleRate', 16000)
                connection_id = event.get('connectionId', '')
                
                # Analyze audio quality if components are initialized
                quality_metrics = None
                if quality_analyzer is not None and audio_data_b64:
                    try:
                        # Decode audio data
                        audio_bytes = base64.b64decode(audio_data_b64)
                        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
                        
                        # Analyze audio quality with graceful degradation
                        # This will return default metrics if analysis fails
                        logger.debug(f"Analyzing audio quality for session {session_id}")
                        quality_metrics = analyze_with_fallback(
                            analyzer=quality_analyzer,
                            audio_chunk=audio_array,
                            sample_rate=sample_rate,
                            stream_id=session_id
                        )
                        
                        # Emit metrics to CloudWatch
                        if metrics_emitter is not None:
                            try:
                                metrics_emitter.emit_metrics(session_id, quality_metrics)
                                logger.debug(f"Quality metrics emitted for session {session_id}")
                            except Exception as e:
                                logger.warning(f"Failed to emit quality metrics: {e}")
                        
                        # Send speaker notifications for threshold violations
                        # Only send notifications if we have real metrics (not fallback defaults)
                        if speaker_notifier is not None and connection_id and quality_metrics.snr_db > 0:
                            try:
                                quality_config = quality_analyzer.config
                                
                                # Check SNR threshold
                                if quality_metrics.snr_db < quality_config.snr_threshold_db:
                                    speaker_notifier.notify_speaker(
                                        connection_id,
                                        'snr_low',
                                        {
                                            'snr': quality_metrics.snr_db,
                                            'threshold': quality_config.snr_threshold_db
                                        }
                                    )
                                
                                # Check clipping threshold
                                if quality_metrics.is_clipping:
                                    speaker_notifier.notify_speaker(
                                        connection_id,
                                        'clipping',
                                        {
                                            'percentage': quality_metrics.clipping_percentage,
                                            'threshold': quality_config.clipping_threshold_percent
                                        }
                                    )
                                
                                # Check echo threshold
                                if quality_metrics.has_echo:
                                    speaker_notifier.notify_speaker(
                                        connection_id,
                                        'echo',
                                        {
                                            'echo_db': quality_metrics.echo_level_db,
                                            'delay_ms': quality_metrics.echo_delay_ms
                                        }
                                    )
                                
                                # Check silence threshold
                                if quality_metrics.is_silent:
                                    speaker_notifier.notify_speaker(
                                        connection_id,
                                        'silence',
                                        {
                                            'duration': quality_metrics.silence_duration_s
                                        }
                                    )
                                
                            except Exception as e:
                                logger.warning(f"Failed to send speaker notifications: {e}")
                        
                    except Exception as e:
                        # Catch any unexpected errors during audio decoding or processing
                        logger.error(
                            f"Failed to process audio quality for session {session_id}: {e}",
                            exc_info=True
                        )
                        # Continue processing even if quality analysis completely fails
                        quality_metrics = None
                
                # In a real implementation, this would:
                # 1. Get audio data from event
                # 2. Stream to AWS Transcribe
                # 3. Process transcription events via processor
                # 4. Update health status when results received
                # 5. Return success response
                
                # Check if fallback mode is enabled
                if fallback_mode_enabled:
                    logger.warning(
                        f"Fallback mode enabled: {fallback_reason}. "
                        f"Processing with final results only."
                    )
                    # Process with final results only
                    # (actual implementation would skip partial result processing)
                
                # Simulate receiving a result (in real implementation, this would
                # be called when actual Transcribe results are received)
                # update_health_status(received_result=True, session_id=session_id)
                
                response_body = {
                    'message': 'Audio processed',
                    'sessionId': session_id,
                    'fallbackMode': fallback_mode_enabled
                }
                
                # Include quality metrics in response if available
                if quality_metrics is not None:
                    response_body['qualityMetrics'] = {
                        'snr_db': quality_metrics.snr_db,
                        'clipping_percentage': quality_metrics.clipping_percentage,
                        'is_clipping': quality_metrics.is_clipping,
                        'echo_level_db': quality_metrics.echo_level_db,
                        'has_echo': quality_metrics.has_echo,
                        'is_silent': quality_metrics.is_silent
                    }
                
                return {
                    'statusCode': 200,
                    'body': json.dumps(response_body)
                }
                
            except Exception as transcribe_error:
                # Transcribe failure detected - enable fallback mode
                logger.error(
                    f"Transcribe error detected: {transcribe_error}. "
                    f"Enabling fallback to final-only mode.",
                    exc_info=True
                )
                
                # Enable fallback mode
                _enable_fallback_mode(
                    reason=f"Transcribe error: {str(transcribe_error)}",
                    session_id=session_id
                )
                
                # Disable partial processing in processor
                processor.config.enabled = False
                
                # Return error response
                return {
                    'statusCode': 500,
                    'body': json.dumps({
                        'error': 'Transcribe error',
                        'message': str(transcribe_error),
                        'fallbackMode': True,
                        'fallbackReason': fallback_reason
                    })
                }
        
        else:
            logger.warning(f"Unknown action: {action}")
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Invalid action',
                    'message': f'Unknown action: {action}'
                })
            }
    
    except Exception as e:
        logger.error(f"Error in process_audio_async: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Processing error',
                'message': str(e)
            })
        }


def _load_config_from_environment() -> PartialResultConfig:
    """
    Load configuration from Lambda environment variables.
    
    This function reads all configuration parameters from environment
    variables, providing sensible defaults for optional parameters.
    
    Environment variables:
    - PARTIAL_RESULTS_ENABLED: Enable/disable partial processing (default: true)
    - MIN_STABILITY_THRESHOLD: Minimum stability threshold (default: 0.85)
    - MAX_BUFFER_TIMEOUT: Maximum buffer timeout in seconds (default: 5.0)
    - PAUSE_THRESHOLD: Pause threshold in seconds (default: 2.0)
    - ORPHAN_TIMEOUT: Orphan timeout in seconds (default: 15.0)
    - MAX_RATE_PER_SECOND: Maximum rate per second (default: 5)
    - DEDUP_CACHE_TTL: Deduplication cache TTL in seconds (default: 10)
    
    Returns:
        PartialResultConfig with values from environment or defaults
    
    Raises:
        ValueError: If configuration validation fails
    """
    try:
        config = PartialResultConfig(
            enabled=os.getenv('PARTIAL_RESULTS_ENABLED', 'true').lower() == 'true',
            min_stability_threshold=float(os.getenv('MIN_STABILITY_THRESHOLD', '0.85')),
            max_buffer_timeout_seconds=float(os.getenv('MAX_BUFFER_TIMEOUT', '5.0')),
            pause_threshold_seconds=float(os.getenv('PAUSE_THRESHOLD', '2.0')),
            orphan_timeout_seconds=float(os.getenv('ORPHAN_TIMEOUT', '15.0')),
            max_rate_per_second=int(os.getenv('MAX_RATE_PER_SECOND', '5')),
            dedup_cache_ttl_seconds=int(os.getenv('DEDUP_CACHE_TTL', '10'))
        )
        
        # Validate configuration
        config.validate()
        
        logger.info(
            f"Configuration loaded: enabled={config.enabled}, "
            f"min_stability={config.min_stability_threshold}, "
            f"max_buffer_timeout={config.max_buffer_timeout_seconds}s"
        )
        
        return config
        
    except ValueError as e:
        logger.error(f"Invalid configuration: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading configuration: {e}", exc_info=True)
        raise ValueError(f"Failed to load configuration: {e}")


def _load_quality_config_from_environment() -> QualityConfig:
    """
    Load audio quality configuration from Lambda environment variables.
    
    This function reads audio quality configuration parameters from environment
    variables, providing sensible defaults for optional parameters.
    
    Environment variables:
    - SNR_THRESHOLD: Minimum acceptable SNR in dB (default: 20.0)
    - SNR_UPDATE_INTERVAL: SNR update interval in ms (default: 500)
    - SNR_WINDOW_SIZE: SNR rolling window size in seconds (default: 5.0)
    - CLIPPING_THRESHOLD: Maximum acceptable clipping percentage (default: 1.0)
    - CLIPPING_AMPLITUDE: Amplitude threshold percentage (default: 98.0)
    - CLIPPING_WINDOW: Clipping detection window in ms (default: 100)
    - ECHO_THRESHOLD: Echo level threshold in dB (default: -15.0)
    - ECHO_MIN_DELAY: Minimum echo delay in ms (default: 10)
    - ECHO_MAX_DELAY: Maximum echo delay in ms (default: 500)
    - ECHO_UPDATE_INTERVAL: Echo update interval in seconds (default: 1.0)
    - SILENCE_THRESHOLD: Silence threshold in dB (default: -50.0)
    - SILENCE_DURATION: Silence duration threshold in seconds (default: 5.0)
    - ENABLE_HIGH_PASS: Enable high-pass filter (default: false)
    - ENABLE_NOISE_GATE: Enable noise gate (default: false)
    
    Returns:
        QualityConfig with values from environment or defaults
    
    Raises:
        ConfigurationError: If configuration validation fails
    """
    try:
        config = QualityConfig(
            snr_threshold_db=float(os.getenv('SNR_THRESHOLD', '20.0')),
            snr_update_interval_ms=int(os.getenv('SNR_UPDATE_INTERVAL', '500')),
            snr_window_size_s=float(os.getenv('SNR_WINDOW_SIZE', '5.0')),
            clipping_threshold_percent=float(os.getenv('CLIPPING_THRESHOLD', '1.0')),
            clipping_amplitude_percent=float(os.getenv('CLIPPING_AMPLITUDE', '98.0')),
            clipping_window_ms=int(os.getenv('CLIPPING_WINDOW', '100')),
            echo_threshold_db=float(os.getenv('ECHO_THRESHOLD', '-15.0')),
            echo_min_delay_ms=int(os.getenv('ECHO_MIN_DELAY', '10')),
            echo_max_delay_ms=int(os.getenv('ECHO_MAX_DELAY', '500')),
            echo_update_interval_s=float(os.getenv('ECHO_UPDATE_INTERVAL', '1.0')),
            silence_threshold_db=float(os.getenv('SILENCE_THRESHOLD', '-50.0')),
            silence_duration_threshold_s=float(os.getenv('SILENCE_DURATION', '5.0')),
            enable_high_pass=os.getenv('ENABLE_HIGH_PASS', 'false').lower() == 'true',
            enable_noise_gate=os.getenv('ENABLE_NOISE_GATE', 'false').lower() == 'true'
        )
        
        # Validate configuration
        errors = config.validate()
        if errors:
            raise ConfigurationError(
                "Invalid quality configuration",
                validation_errors=errors
            )
        
        logger.info(
            f"Quality configuration loaded: snr_threshold={config.snr_threshold_db}dB, "
            f"clipping_threshold={config.clipping_threshold_percent}%, "
            f"echo_threshold={config.echo_threshold_db}dB"
        )
        
        return config
        
    except ConfigurationError:
        # Re-raise ConfigurationError as-is
        raise
    except ValueError as e:
        logger.error(f"Invalid quality configuration value: {e}")
        raise ConfigurationError(f"Invalid configuration value: {e}")
    except Exception as e:
        logger.error(f"Error loading quality configuration: {e}", exc_info=True)
        raise ConfigurationError(f"Failed to load quality configuration: {e}")


def _enable_fallback_mode(reason: str, session_id: str = "") -> None:
    """
    Enable fallback to final-only mode.
    
    This function is called when Transcribe failures are detected. It:
    1. Sets the global fallback_mode_enabled flag
    2. Logs the fallback trigger event
    3. Emits a CloudWatch metric for monitoring
    
    Args:
        reason: Reason for enabling fallback mode
        session_id: Session ID (optional, for logging)
    """
    global fallback_mode_enabled, fallback_reason
    
    fallback_mode_enabled = True
    fallback_reason = reason
    
    logger.error(
        f"Fallback mode enabled for session {session_id}: {reason}"
    )
    
    # Emit CloudWatch metric
    try:
        cloudwatch.put_metric_data(
            Namespace='AudioTranscription/PartialResults',
            MetricData=[
                {
                    'MetricName': 'TranscribeFallbackTriggered',
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'SessionId', 'Value': session_id or 'unknown'}
                    ]
                }
            ]
        )
    except Exception as e:
        logger.warning(f"Failed to emit fallback metric: {e}")


def _disable_fallback_mode(session_id: str = "") -> None:
    """
    Disable fallback mode and re-enable partial processing.
    
    This function is called when Transcribe service recovers and starts
    providing results again. It resets the fallback state.
    
    Args:
        session_id: Session ID (optional, for logging)
    """
    global fallback_mode_enabled, fallback_reason
    
    if fallback_mode_enabled:
        logger.info(
            f"Disabling fallback mode for session {session_id}. "
            f"Transcribe service recovered."
        )
        
        fallback_mode_enabled = False
        fallback_reason = None


def update_health_status(
    received_result: bool = False,
    session_active: bool = None,
    session_id: str = ""
) -> None:
    """
    Update Transcribe service health status.
    
    This function tracks the health of the Transcribe service by monitoring
    when results are received. If no results are received for 10+ seconds
    during an active audio session, it automatically enables fallback mode.
    
    When results resume, it automatically re-enables partial processing.
    
    Args:
        received_result: True if a result was just received
        session_active: True if audio session is active (optional)
        session_id: Session ID for logging
    """
    global last_result_time, audio_session_active, fallback_mode_enabled
    
    import time
    current_time = time.time()
    
    # Update session active status if provided
    if session_active is not None:
        audio_session_active = session_active
        logger.debug(f"Audio session active status: {audio_session_active}")
    
    # Update last result time if result received
    if received_result:
        last_result_time = current_time
        logger.debug(f"Result received at {current_time}")
        
        # If we were in fallback mode, check if we should re-enable
        if fallback_mode_enabled and fallback_reason and 'health' in fallback_reason.lower():
            logger.info(
                f"Transcribe service recovered (result received). "
                f"Re-enabling partial processing."
            )
            _disable_fallback_mode(session_id)
        
        return
    
    # Check health if session is active
    if audio_session_active and last_result_time is not None:
        time_since_last_result = current_time - last_result_time
        
        # If no results for 10+ seconds, enable fallback
        if time_since_last_result >= 10.0 and not fallback_mode_enabled:
            logger.error(
                f"Transcribe service appears unhealthy: no results for "
                f"{time_since_last_result:.1f} seconds. Enabling fallback mode."
            )
            
            _enable_fallback_mode(
                reason=f"Transcribe health check failed: no results for {time_since_last_result:.1f}s",
                session_id=session_id
            )


def check_transcribe_health(session_id: str = "") -> bool:
    """
    Check if Transcribe service is healthy.
    
    This function checks the current health status based on when the last
    result was received. It's called periodically during audio processing.
    
    Args:
        session_id: Session ID for logging
    
    Returns:
        True if service is healthy, False otherwise
    """
    global last_result_time, audio_session_active, fallback_mode_enabled
    
    # If not in active session, assume healthy
    if not audio_session_active:
        return True
    
    # If no results received yet, assume healthy (just started)
    if last_result_time is None:
        return True
    
    # Check time since last result
    import time
    current_time = time.time()
    time_since_last_result = current_time - last_result_time
    
    # Service is unhealthy if no results for 10+ seconds
    is_healthy = time_since_last_result < 10.0
    
    if not is_healthy and not fallback_mode_enabled:
        logger.warning(
            f"Transcribe health check: no results for "
            f"{time_since_last_result:.1f} seconds"
        )
        update_health_status(session_id=session_id)
    
    return is_healthy


# ============================================================================
# Phase 3: AWS API Integration Helper Functions
# ============================================================================

async def transcribe_pcm_audio(
    pcm_bytes: bytes,
    language_code: str,
    sample_rate: int,
    session_id: str,
    batch_index: int
) -> str:
    """
    Transcribe PCM audio using AWS Transcribe.
    
    For Phase 3, using StartTranscriptionJob approach.
    Uploads audio to S3, starts job, polls for completion.
    
    Args:
        pcm_bytes: PCM audio data
        language_code: AWS language code (e.g., 'en-US')
        sample_rate: Audio sample rate
        session_id: Session identifier
        batch_index: Batch index for naming
    
    Returns:
        Transcribed text
    """
    try:
        import uuid
        import tempfile
        
        transcribe_client = boto3.client('transcribe')
        s3_client = boto3.client('s3')
        
        # Generate unique job name
        job_name = f"transcribe-{session_id}-{batch_index}-{uuid.uuid4().hex[:8]}"
        
        # Get S3 bucket for temporary storage
        audio_bucket = os.environ.get('AUDIO_BUCKET_NAME', f'low-latency-audio-{os.environ.get("STAGE", "dev")}')
        
        # Upload PCM to S3 temporarily
        s3_key = f"sessions/{session_id}/transcribe-temp/{job_name}.pcm"
        s3_client.put_object(
            Bucket=audio_bucket,
            Key=s3_key,
            Body=pcm_bytes
        )
        
        # Start transcription job
        transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            LanguageCode=language_code,
            MediaFormat='pcm',
            MediaSampleRateHertz=sample_rate,
            Media={'MediaFileUri': f's3://{audio_bucket}/{s3_key}'}
        )
        
        # Poll for completion (with timeout)
        max_wait = 30  # 30 seconds max
        wait_interval = 1
        elapsed = 0
        
        while elapsed < max_wait:
            await asyncio.sleep(wait_interval)
            elapsed += wait_interval
            
            status_response = transcribe_client.get_transcription_job(
                TranscriptionJobName=job_name
            )
            
            status = status_response['TranscriptionJob']['TranscriptionJobStatus']
            
            if status == 'COMPLETED':
                transcript_uri = status_response['TranscriptionJob']['Transcript']['TranscriptFileUri']
                
                # Download and parse transcript
                import urllib.request
                with urllib.request.urlopen(transcript_uri) as response:
                    transcript_data = json.loads(response.read())
                
                transcript = transcript_data['results']['transcripts'][0]['transcript']
                
                # Cleanup
                try:
                    transcribe_client.delete_transcription_job(TranscriptionJobName=job_name)
                    s3_client.delete_object(Bucket=audio_bucket, Key=s3_key)
                except:
                    pass
                
                return transcript
            
            elif status == 'FAILED':
                raise Exception(f"Transcription job failed: {status_response.get('FailureReason', 'Unknown')}")
        
        # Timeout
        raise Exception(f"Transcription job timed out after {max_wait} seconds")
        
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        raise


def get_polly_voice_for_language(language_code: str) -> str:
    """
    Get appropriate Polly voice ID for language.
    
    Args:
        language_code: ISO 639-1 language code
    
    Returns:
        Polly voice ID
    """
    # Neural voices for better quality
    voice_mapping = {
        'en': 'Joanna',  # US English, Neural
        'es': 'Lucia',   # Spanish, Neural
        'fr': 'Lea',     # French, Neural
        'de': 'Vicki',   # German, Neural
        'it': 'Bianca',  # Italian, Neural
        'pt': 'Camila',  # Portuguese (BR), Neural
        'ja': 'Takumi',  # Japanese, Neural
        'ko': 'Seoyeon', # Korean, Neural
        'zh': 'Zhiyu',   # Chinese, Neural
        'ar': 'Zeina',   # Arabic
        'hi': 'Aditi',   # Hindi
        'ru': 'Tatyana'  # Russian
    }
    
    return voice_mapping.get(language_code, 'Joanna')


def create_silent_mp3(duration: float) -> bytes:
    """
    Create a silent MP3 file as fallback.
    
    Args:
        duration: Duration in seconds
    
    Returns:
        MP3 bytes (minimal silent audio)
    """
    # Minimal MP3 header for silent audio
    # This is a very basic implementation
    # In production, use ffmpeg or pydub for proper silent audio
    silent_mp3_header = b'\xff\xfb\x90\x00' * int(duration * 10)
    return silent_mp3_header
