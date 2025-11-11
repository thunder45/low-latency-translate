"""
Audio Processor Lambda handler with partial results support.

This module provides the Lambda handler for processing audio transcription
with partial results. It bridges the synchronous Lambda handler interface
with the asynchronous AWS Transcribe Streaming API.
"""

import asyncio
import logging
import os
import json
import boto3
from typing import Dict, Any, Optional
from shared.models.configuration import PartialResultConfig
from shared.services.partial_result_processor import PartialResultProcessor

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Global processor instance (singleton per Lambda container)
# Initialized on cold start and reused across invocations
partial_processor: Optional[PartialResultProcessor] = None

# CloudWatch client for metrics
cloudwatch = boto3.client('cloudwatch')

# Fallback state tracking
fallback_mode_enabled = False
fallback_reason = None

# Health monitoring state
last_result_time = None
audio_session_active = False


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Synchronous Lambda handler that bridges to async Transcribe processing.
    
    This handler is invoked by AWS Lambda for each audio processing request.
    It initializes the PartialResultProcessor on cold start (singleton pattern)
    and bridges the synchronous Lambda interface with the asynchronous
    Transcribe processing.
    
    Args:
        event: Lambda event object containing:
            - sessionId: Session identifier
            - sourceLanguage: Source language code (ISO 639-1)
            - audioData: Base64-encoded audio data (optional)
            - action: Action to perform (e.g., 'initialize', 'process')
        context: Lambda context object
    
    Returns:
        Response dict with statusCode and body
    
    Examples:
        >>> # Initialize session
        >>> event = {
        ...     'action': 'initialize',
        ...     'sessionId': 'golden-eagle-427',
        ...     'sourceLanguage': 'en'
        ... }
        >>> response = lambda_handler(event, context)
        >>> assert response['statusCode'] == 200
        
        >>> # Process audio
        >>> event = {
        ...     'action': 'process',
        ...     'sessionId': 'golden-eagle-427',
        ...     'audioData': 'base64_encoded_audio...'
        ... }
        >>> response = lambda_handler(event, context)
    """
    global partial_processor
    
    try:
        # Extract session information
        session_id = event.get('sessionId', '')
        source_language = event.get('sourceLanguage', 'en')
        action = event.get('action', 'process')
        
        logger.info(
            f"Lambda handler invoked: action={action}, "
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
                
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Audio processed',
                        'sessionId': session_id,
                        'fallbackMode': fallback_mode_enabled
                    })
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
