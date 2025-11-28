"""
WebSocket Connection Handler for $connect events and control messages.
Handles speaker session creation, listener joining, and broadcast control messages.
"""
import json
import logging
import os
import time
import boto3
from decimal import Decimal
from typing import Dict, Any, List


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

from shared.data_access import (
    SessionsRepository,
    ConnectionsRepository,
    RateLimitExceededError,
    ConditionalCheckFailedError,
    ItemNotFoundError,
)
from shared.services.rate_limit_service import RateLimitService
from shared.services.language_validator import LanguageValidator, UnsupportedLanguageError
from shared.utils.session_id_service import SessionIDService
from shared.utils.validators import (
    ValidationError,
    validate_language_code,
    validate_session_id_format,
    validate_quality_tier,
    validate_action,
)
from shared.utils.response_builder import (
    success_response,
    error_response,
    rate_limit_error_response,
)
from shared.utils.structured_logger import get_structured_logger
from shared.utils.metrics import get_metrics_publisher
from shared.config.table_names import get_table_name, SESSIONS_TABLE_NAME, CONNECTIONS_TABLE_NAME

# Initialize structured logger
base_logger = logging.getLogger()
base_logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))
logger = get_structured_logger('ConnectionHandler')

# Initialize repositories and services (reused across Lambda invocations)
sessions_repo = SessionsRepository(get_table_name('SESSIONS_TABLE_NAME', SESSIONS_TABLE_NAME))
connections_repo = ConnectionsRepository(get_table_name('CONNECTIONS_TABLE_NAME', CONNECTIONS_TABLE_NAME))
rate_limit_service = RateLimitService()
language_validator = LanguageValidator(region=os.environ.get('AWS_REGION', 'us-east-1'))
session_id_service = SessionIDService(sessions_repo)
metrics_publisher = get_metrics_publisher()

# Initialize API Gateway Management API client
api_gateway_endpoint = os.environ.get('API_GATEWAY_ENDPOINT', '')
if api_gateway_endpoint:
    apigw_management_client = boto3.client(
        'apigatewaymanagementapi',
        endpoint_url=api_gateway_endpoint
    )
else:
    apigw_management_client = None

# Configuration
MAX_LISTENERS_PER_SESSION = int(os.environ.get('MAX_LISTENERS_PER_SESSION', '500'))
SESSION_MAX_DURATION_HOURS = int(os.environ.get('SESSION_MAX_DURATION_HOURS', '2'))
SUPPORTED_LANGUAGES = os.environ.get('SUPPORTED_LANGUAGES', 'en,es,fr,de,pt,it,ja,ko,zh').split(',')


def lambda_handler(event, context):
    """
    Handle WebSocket events: $connect and MESSAGE events.
    
    Args:
        event: API Gateway WebSocket event
        context: Lambda context
        
    Returns:
        Response with status code and body
    """
    connection_id = event['requestContext']['connectionId']
    event_type = event['requestContext'].get('eventType', 'MESSAGE')
    route_key = event['requestContext'].get('routeKey', '$default')
    
    # Extract IP address for rate limiting
    ip_address = event['requestContext'].get('identity', {}).get('sourceIp', 'unknown')
    
    logger.info(
        message="Connection handler invoked",
        correlation_id=connection_id,
        operation='lambda_handler',
        ip_address=ip_address,
        event_type=event_type,
        route_key=route_key
    )
    
    try:
        # Handle $connect events - validate sessionId and session status
        if event_type == 'CONNECT':
            # Check connection attempt rate limit
            rate_limit_service.check_connection_attempt_limit(ip_address)
            
            # Extract sessionId from query parameters (REQUIRED for hybrid architecture)
            query_params = event.get('queryStringParameters') or {}
            session_id = query_params.get('sessionId', '').strip()
            
            # SessionId is now REQUIRED for all connections
            if not session_id:
                logger.warning(
                    message="Connection rejected: missing sessionId parameter",
                    correlation_id=connection_id,
                    operation='lambda_handler',
                    error_code='MISSING_SESSION_ID',
                    ip_address=ip_address
                )
                metrics_publisher.emit_connection_error('MISSING_SESSION_ID')
                return error_response(
                    status_code=400,
                    error_code='MISSING_SESSION_ID',
                    message='sessionId query parameter is required'
                )
            
            # Validate sessionId format
            try:
                validate_session_id_format(session_id)
            except ValidationError as e:
                logger.warning(
                    message=f"Connection rejected: invalid sessionId format: {session_id}",
                    correlation_id=connection_id,
                    operation='lambda_handler',
                    error_code='INVALID_SESSION_ID',
                    ip_address=ip_address,
                    sessionId=session_id
                )
                metrics_publisher.emit_connection_error('INVALID_SESSION_ID')
                return error_response(
                    status_code=400,
                    error_code='INVALID_SESSION_ID',
                    message='Invalid sessionId format'
                )
            
            # Validate session exists and is active
            session = sessions_repo.get_session(session_id)
            
            if not session:
                logger.warning(
                    message=f"Connection rejected: session not found: {session_id}",
                    correlation_id=f"{session_id}-{connection_id}",
                    operation='lambda_handler',
                    error_code='SESSION_NOT_FOUND',
                    ip_address=ip_address,
                    sessionId=session_id
                )
                metrics_publisher.emit_connection_error('SESSION_NOT_FOUND')
                return error_response(
                    status_code=404,
                    error_code='SESSION_NOT_FOUND',
                    message='Session does not exist'
                )
            
            if session.get('status') != 'active':
                logger.warning(
                    message=f"Connection rejected: session is not active: {session_id}, status: {session.get('status')}",
                    correlation_id=f"{session_id}-{connection_id}",
                    operation='lambda_handler',
                    error_code='SESSION_INACTIVE',
                    ip_address=ip_address,
                    sessionId=session_id
                )
                metrics_publisher.emit_connection_error('SESSION_INACTIVE')
                return error_response(
                    status_code=403,
                    error_code='SESSION_INACTIVE',
                    message='Session is not active'
                )
            
            # Extract user context from authorizer (speaker only)
            authorizer_context = event['requestContext'].get('authorizer', {})
            user_id = authorizer_context.get('userId')
            
            # Determine role based on authentication
            # Speaker: authenticated user who owns the session
            # Listener: anonymous or authenticated user who doesn't own the session
            speaker_user_id = session.get('speakerId', '')
            is_speaker = user_id and user_id == speaker_user_id
            role = 'speaker' if is_speaker else 'listener'
            
            # Create connection record in DynamoDB
            # CRITICAL: Must create this during $connect so disconnect handler can find it
            try:
                connections_repo.create_connection(
                    connection_id=connection_id,
                    session_id=session_id,
                    role=role,
                    target_language=session.get('sourceLanguage') if role == 'listener' else None,
                    ip_address=ip_address,
                    session_max_duration_hours=SESSION_MAX_DURATION_HOURS
                )
                logger.info(
                    message=f"Connection record created successfully in DynamoDB",
                    correlation_id=f"{session_id}-{connection_id}",
                    operation='lambda_handler',
                    sessionId=session_id,
                    role=role
                )
            except Exception as e:
                logger.error(
                    message=f"CRITICAL: Failed to create connection record: {str(e)}",
                    correlation_id=f"{session_id}-{connection_id}",
                    operation='lambda_handler',
                    error_code='DB_WRITE_FAILED',
                    sessionId=session_id,
                    role=role,
                    exc_info=True
                )
                # Return error to prevent connection
                return error_response(
                    status_code=500,
                    error_code='DB_WRITE_FAILED',
                    message='Failed to initialize connection'
                )
            
            logger.info(
                message=f"{role.capitalize()} connection accepted for session {session_id}",
                correlation_id=f"{session_id}-{connection_id}",
                operation='lambda_handler',
                user_id=user_id,
                ip_address=ip_address,
                sessionId=session_id,
                role=role
            )
            
            # Accept connection - return ONLY statusCode for $connect (no body per AWS docs)
            return {'statusCode': 200}
        
        # Handle MESSAGE events
        elif event_type == 'MESSAGE':
            # Parse message body
            try:
                body = json.loads(event.get('body', '{}'))
                action = body.get('action', '')
            except json.JSONDecodeError:
                return error_response(
                    status_code=400,
                    error_code='INVALID_MESSAGE',
                    message='Invalid JSON in message body'
                )
            
            # Route to appropriate handler
            if action == 'createSession':
                return handle_create_session_message(event, connection_id, body, ip_address)
            elif action == 'joinSession':
                return handle_join_session_message(event, connection_id, body, ip_address)
            elif action == 'audioChunk':
                return handle_audio_chunk(event, connection_id, body, ip_address)
            elif action:
                # Route other control messages (pauseBroadcast, muteBroadcast, etc.)
                return route_control_message(connection_id, action, body)
            else:
                # Handle missing or empty action - $default route
                logger.warning(
                    message="Message received with no action specified",
                    correlation_id=connection_id,
                    operation='lambda_handler',
                    event_type=event_type
                )
                return success_response(status_code=200, body={
                    'type': 'error',
                    'code': 'MISSING_ACTION',
                    'message': 'Message must include an action parameter',
                    'timestamp': int(time.time() * 1000)
                })
        
        else:
            return error_response(
                status_code=400,
                error_code='INVALID_EVENT_TYPE',
                message=f'Unsupported event type: {event_type}'
            )
    
    except ValidationError as e:
        logger.warning(
            message=f"Validation error: {e.message}",
            correlation_id=connection_id,
            operation='lambda_handler',
            error_code='INVALID_PARAMETERS',
            ip_address=ip_address,
            field=e.field
        )
        metrics_publisher.emit_connection_error('INVALID_PARAMETERS')
        return error_response(
            status_code=400,
            error_code='INVALID_PARAMETERS',
            message=e.message,
            details={'field': e.field}
        )
    
    except RateLimitExceededError as e:
        logger.warning(
            message=f"Rate limit exceeded: {str(e)}",
            correlation_id=connection_id,
            operation='lambda_handler',
            error_code='RATE_LIMIT_EXCEEDED',
            ip_address=ip_address
        )
        # Emit rate limit metric (action may not be defined for CONNECT events)
        action_name = locals().get('action', 'connect')
        metrics_publisher.emit_rate_limit_exceeded(action_name)
        return rate_limit_error_response(e.retry_after)
    
    except UnsupportedLanguageError as e:
        logger.warning(
            message=f"Unsupported language: {e.message}",
            correlation_id=connection_id,
            operation='lambda_handler',
            error_code='UNSUPPORTED_LANGUAGE',
            ip_address=ip_address,
            languageCode=e.language_code
        )
        metrics_publisher.emit_connection_error('UNSUPPORTED_LANGUAGE')
        return error_response(
            status_code=400,
            error_code='UNSUPPORTED_LANGUAGE',
            message=e.message,
            details={'languageCode': e.language_code}
        )
    
    except Exception as e:
        logger.error(
            message=f"Unexpected error in connection handler: {str(e)}",
            correlation_id=connection_id,
            operation='lambda_handler',
            error_code='INTERNAL_ERROR',
            ip_address=ip_address,
            exc_info=True
        )
        metrics_publisher.emit_connection_error('INTERNAL_ERROR')
        return error_response(
            status_code=500,
            error_code='INTERNAL_ERROR',
            message='An unexpected error occurred'
        )


def handle_create_session_message(event, connection_id, body, ip_address):
    """
    Handle speaker session creation via MESSAGE event.
    
    Args:
        event: Lambda event
        connection_id: WebSocket connection ID
        body: Message body dict
        ip_address: Client IP address
    
    Returns:
        API Gateway response
    """
    start_time = time.time()
    
    # Extract and validate parameters from message body
    source_language = body.get('sourceLanguage', '')
    quality_tier = body.get('qualityTier', 'standard')
    
    validate_language_code(source_language, 'sourceLanguage')
    validate_quality_tier(quality_tier)
    
    # Extract and validate partial results configuration
    partial_results_enabled = body.get('partialResults', True)
    if isinstance(partial_results_enabled, str):
        partial_results_enabled = partial_results_enabled.lower() == 'true'
    
    min_stability = body.get('minStability', 0.85)
    max_buffer_timeout = body.get('maxBufferTimeout', 5.0)
    
    # Validate configuration parameters
    try:
        min_stability_threshold = float(min_stability) if not isinstance(min_stability, float) else min_stability
        max_buffer_timeout_seconds = float(max_buffer_timeout) if not isinstance(max_buffer_timeout, float) else max_buffer_timeout
        
        # Validate ranges
        if not 0.70 <= min_stability_threshold <= 0.95:
            raise ValueError(
                f"minStability must be between 0.70 and 0.95, got {min_stability_threshold}"
            )
        
        if not 2.0 <= max_buffer_timeout_seconds <= 10.0:
            raise ValueError(
                f"maxBufferTimeout must be between 2.0 and 10.0, got {max_buffer_timeout_seconds}"
            )
    except (ValueError, TypeError) as e:
        logger.warning(
            message=f"Invalid partial results configuration: {str(e)}",
            correlation_id=connection_id,
            operation='handle_create_session_message',
            error_code='INVALID_CONFIGURATION'
        )
        metrics_publisher.emit_connection_error('INVALID_CONFIGURATION')
        
        # Send error message to client
        error_msg = {
            'type': 'error',
            'code': 'INVALID_CONFIGURATION',
            'message': str(e),
            'timestamp': int(time.time() * 1000)
        }
        send_to_connection(connection_id, error_msg)
        
        return success_response(status_code=200, body={})
    
    # Extract user context from authorizer
    authorizer_context = event['requestContext'].get('authorizer', {})
    user_id = authorizer_context.get('userId')
    
    if not user_id:
        logger.error(
            message="Missing userId in authorizer context",
            correlation_id=connection_id,
            operation='handle_create_session_message',
            error_code='UNAUTHORIZED'
        )
        metrics_publisher.emit_connection_error('UNAUTHORIZED')
        
        # Send error message to client
        error_msg = {
            'type': 'error',
            'code': 'UNAUTHORIZED',
            'message': 'Authentication required',
            'timestamp': int(time.time() * 1000)
        }
        send_to_connection(connection_id, error_msg)
        
        return success_response(status_code=200, body={})
    
    logger.info(
        message=f"Creating session for user {user_id}",
        correlation_id=connection_id,
        operation='handle_create_session_message',
        user_id=user_id,
        sourceLanguage=source_language,
        qualityTier=quality_tier
    )
    
    # Check rate limit for session creation
    rate_limit_service.check_session_creation_limit(user_id)
    
    # Generate unique session ID
    session_id = session_id_service.generate_unique_session_id()
    
    # Create session record
    session = sessions_repo.create_session(
        session_id=session_id,
        speaker_connection_id=connection_id,
        speaker_user_id=user_id,
        source_language=source_language,
        quality_tier=quality_tier,
        session_max_duration_hours=SESSION_MAX_DURATION_HOURS,
        partial_results_enabled=partial_results_enabled,
        min_stability_threshold=min_stability_threshold,
        max_buffer_timeout=max_buffer_timeout_seconds
    )
    
    # Create connection record for speaker
    connections_repo.create_connection(
        connection_id=connection_id,
        session_id=session_id,
        role='speaker',
        ip_address=ip_address,
        session_max_duration_hours=SESSION_MAX_DURATION_HOURS
    )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        message="Session created successfully",
        correlation_id=session_id,
        operation='handle_create_session_message',
        duration_ms=duration_ms,
        user_id=user_id
    )
    
    # Emit metrics
    metrics_publisher.emit_session_creation_latency(duration_ms, user_id)
    
    # Send message via post_to_connection (asynchronously)
    success_msg = {
        'type': 'sessionCreated',
        'sessionId': session_id,
        'sourceLanguage': source_language,
        'qualityTier': quality_tier,
        'partialResultsEnabled': partial_results_enabled,
        'minStabilityThreshold': min_stability_threshold,
        'maxBufferTimeout': max_buffer_timeout_seconds,
        'connectionId': connection_id,
        'timestamp': int(time.time() * 1000)
    }
    
    # Send message to client
    send_result = send_to_connection(connection_id, success_msg)
    
    if not send_result:
        logger.error(
            message="CRITICAL: Failed to send sessionCreated message",
            correlation_id=session_id,
            connection_id=connection_id,
            operation='handle_create_session_message'
        )
        # Connection is likely already gone, but still mark success
        # since session was created successfully
    else:
        logger.info(
            message="SUCCESS: sessionCreated message sent to connection",
            correlation_id=session_id,
            connection_id=connection_id,
            operation='handle_create_session_message',
            timestamp_ms=int(time.time() * 1000)
        )
    
    logger.info(
        message="Lambda completing immediately after message send",
        correlation_id=session_id,
        operation='handle_create_session_message'
    )
    
    # Return success response to keep connection open
    return success_response(status_code=200, body={})


def handle_join_session_message(event, connection_id, body, ip_address):
    """
    Handle listener joining session via MESSAGE event.
    
    Args:
        event: Lambda event
        connection_id: WebSocket connection ID
        body: Message body dict
        ip_address: Client IP address
    
    Returns:
        API Gateway response
    """
    start_time = time.time()
    
    # Extract and validate parameters from message body
    session_id = body.get('sessionId', '')
    target_language = body.get('targetLanguage', '')
    
    validate_session_id_format(session_id)
    validate_language_code(target_language, 'targetLanguage')
    
    logger.info(
        message="Listener joining session",
        correlation_id=f"{session_id}-{connection_id}",
        operation='handle_join_session_message',
        sessionId=session_id,
        targetLanguage=target_language
    )
    
    # Check rate limit for listener joins
    rate_limit_service.check_listener_join_limit(ip_address)
    
    # Validate session exists and is active
    session = sessions_repo.get_session(session_id)
    
    if not session:
        logger.warning(
            message=f"Session not found: {session_id}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_join_session_message',
            error_code='SESSION_NOT_FOUND',
            sessionId=session_id
        )
        metrics_publisher.emit_connection_error('SESSION_NOT_FOUND')
        
        # Send error message to client
        error_msg = {
            'type': 'error',
            'code': 'SESSION_NOT_FOUND',
            'message': 'Session does not exist or is inactive',
            'details': {'sessionId': session_id},
            'timestamp': int(time.time() * 1000)
        }
        send_to_connection(connection_id, error_msg)
        
        return success_response(status_code=200, body={})
    
    # Check session status (HTTP API uses 'status' field, not 'isActive')
    session_status = session.get('status', '')
    if session_status != 'active':
        logger.warning(
            message=f"Session is not active: {session_id}, status: {session_status}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_join_session_message',
            error_code='SESSION_NOT_FOUND',
            sessionId=session_id,
            sessionStatus=session_status
        )
        metrics_publisher.emit_connection_error('SESSION_NOT_FOUND')
        
        # Send error message to client
        error_msg = {
            'type': 'error',
            'code': 'SESSION_NOT_FOUND',
            'message': 'Session does not exist or is inactive',
            'details': {'sessionId': session_id},
            'timestamp': int(time.time() * 1000)
        }
        send_to_connection(connection_id, error_msg)
        
        return success_response(status_code=200, body={})
    
    # Validate language support
    source_language = session['sourceLanguage']
    try:
        language_validator.validate_target_language(source_language, target_language)
    except UnsupportedLanguageError as e:
        logger.warning(
            message=f"Unsupported language: {e.message}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_join_session_message',
            error_code='UNSUPPORTED_LANGUAGE',
            languageCode=e.language_code
        )
        metrics_publisher.emit_connection_error('UNSUPPORTED_LANGUAGE')
        
        # Send error message to client
        error_msg = {
            'type': 'error',
            'code': 'UNSUPPORTED_LANGUAGE',
            'message': e.message,
            'details': {'languageCode': e.language_code},
            'timestamp': int(time.time() * 1000)
        }
        send_to_connection(connection_id, error_msg)
        
        return success_response(status_code=200, body={})
    
    # Check session capacity
    current_listener_count = session.get('listenerCount', 0)
    if current_listener_count >= MAX_LISTENERS_PER_SESSION:
        logger.warning(
            message=f"Session at capacity: {session_id} ({current_listener_count} listeners)",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_join_session_message',
            error_code='SESSION_FULL',
            sessionId=session_id,
            listenerCount=current_listener_count
        )
        metrics_publisher.emit_connection_error('SESSION_FULL')
        
        # Send error message to client
        error_msg = {
            'type': 'error',
            'code': 'SESSION_FULL',
            'message': f'Session has reached maximum capacity of {MAX_LISTENERS_PER_SESSION} listeners',
            'details': {
                'sessionId': session_id,
                'maxListeners': MAX_LISTENERS_PER_SESSION
            },
            'timestamp': int(time.time() * 1000)
        }
        send_to_connection(connection_id, error_msg)
        
        return success_response(status_code=200, body={})
    
    # Create connection record
    connections_repo.create_connection(
        connection_id=connection_id,
        session_id=session_id,
        role='listener',
        target_language=target_language,
        ip_address=ip_address,
        session_max_duration_hours=SESSION_MAX_DURATION_HOURS
    )
    
    # Atomically increment listener count
    try:
        new_listener_count = sessions_repo.increment_listener_count(session_id)
    except ConditionalCheckFailedError:
        # Session became inactive or was deleted
        logger.warning(
            message=f"Session became inactive during join: {session_id}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_join_session_message',
            error_code='SESSION_NOT_FOUND',
            sessionId=session_id
        )
        # Clean up connection record
        connections_repo.delete_connection(connection_id)
        metrics_publisher.emit_connection_error('SESSION_NOT_FOUND')
        
        # Send error message to client
        error_msg = {
            'type': 'error',
            'code': 'SESSION_NOT_FOUND',
            'message': 'Session is no longer active',
            'details': {'sessionId': session_id},
            'timestamp': int(time.time() * 1000)
        }
        send_to_connection(connection_id, error_msg)
        
        return success_response(status_code=200, body={})
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        message="Listener joined successfully",
        correlation_id=f"{session_id}-{connection_id}",
        operation='handle_join_session_message',
        duration_ms=duration_ms,
        sessionId=session_id,
        targetLanguage=target_language,
        listenerCount=new_listener_count
    )
    
    # Emit metrics
    metrics_publisher.emit_listener_join_latency(duration_ms, session_id)
    
    # Send message via post_to_connection (asynchronously)
    success_msg = {
        'type': 'sessionJoined',
        'sessionId': session_id,
        'targetLanguage': target_language,
        'sourceLanguage': source_language,
        'connectionId': connection_id,
        'timestamp': int(time.time() * 1000)
    }
    
    # Send message to client
    send_result = send_to_connection(connection_id, success_msg)
    
    logger.info(
        message=f"Session joined, message sent: {send_result}",
        correlation_id=f"{session_id}-{connection_id}",
        operation='handle_join_session_message'
    )
    
    # Return success response to keep connection open
    return success_response(status_code=200, body={})


def handle_audio_chunk(event, connection_id, body, ip_address):
    """
    Handle audio chunk from speaker - write directly to Kinesis Data Stream (Phase 4).
    
    This replaces the previous approach of invoking kvs_stream_writer Lambda.
    Benefits:
    - Lower latency (~10ms vs ~50ms)
    - No intermediate Lambda invocation
    - Native Kinesis batching (3-second window)
    
    Args:
        event: Lambda event
        connection_id: WebSocket connection ID
        body: Message body with audio data
        ip_address: Client IP
        
    Returns:
        Success response
    """
    try:
        session_id = body.get('sessionId', '')
        audio_data_base64 = body.get('audioData', '')
        chunk_index = body.get('chunkIndex', 0)
        
        if not session_id or not audio_data_base64:
            logger.warning(
                message="Invalid audio chunk: missing sessionId or audioData",
                correlation_id=connection_id,
                operation='handle_audio_chunk'
            )
            return success_response(status_code=200, body={})
        
        # Verify connection is speaker role
        connection = connections_repo.get_connection(connection_id)
        if not connection or connection.get('role') != 'speaker':
            logger.warning(
                message="Audio chunk from non-speaker connection",
                correlation_id=connection_id,
                operation='handle_audio_chunk',
                role=connection.get('role') if connection else 'unknown'
            )
            return success_response(status_code=200, body={})
        
        # Decode base64 to get raw PCM bytes
        import base64
        pcm_bytes = base64.b64decode(audio_data_base64)
        
        # Write directly to Kinesis Data Stream
        stream_name = os.environ.get('AUDIO_STREAM_NAME', f'audio-ingestion-{os.environ.get("ENV", "dev")}')
        
        kinesis_client = boto3.client('kinesis')
        kinesis_client.put_record(
            StreamName=stream_name,
            Data=pcm_bytes,  # Raw bytes (not base64)
            PartitionKey=session_id  # Groups records by session
        )
        
        # Log every 40th chunk to avoid log spam
        if chunk_index % 40 == 0:
            logger.info(
                message=f"Wrote audio chunk {chunk_index} to Kinesis stream",
                correlation_id=f"{session_id}-{connection_id}",
                operation='handle_audio_chunk',
                sessionId=session_id,
                chunkIndex=chunk_index,
                streamName=stream_name
            )
        
        return success_response(status_code=200, body={})
        
    except Exception as e:
        logger.error(
            message=f"Error handling audio chunk: {str(e)}",
            correlation_id=connection_id,
            operation='handle_audio_chunk',
            exc_info=True
        )
        # Return success to avoid WebSocket disconnect
        return success_response(status_code=200, body={})


# Keep old function for backwards compatibility (not used anymore)
def handle_join_session(event, connection_id, query_params, ip_address):
    """
    Handle listener joining session.
    
    Args:
        event: Lambda event
        connection_id: WebSocket connection ID
        query_params: Query string parameters
        ip_address: Client IP address
    
    Returns:
        API Gateway response
    """
    start_time = time.time()
    
    # Extract and validate parameters
    session_id = query_params.get('sessionId', '')
    target_language = query_params.get('targetLanguage', '')
    
    validate_session_id_format(session_id)
    validate_language_code(target_language, 'targetLanguage')
    
    logger.info(
        message="Listener joining session",
        correlation_id=f"{session_id}-{connection_id}",
        operation='handle_join_session',
        sessionId=session_id,
        targetLanguage=target_language
    )
    
    # Check rate limit for listener joins
    rate_limit_service.check_listener_join_limit(ip_address)
    
    # Validate session exists and is active
    session = sessions_repo.get_session(session_id)
    
    if not session:
        logger.warning(
            message=f"Session not found: {session_id}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_join_session',
            error_code='SESSION_NOT_FOUND',
            sessionId=session_id
        )
        metrics_publisher.emit_connection_error('SESSION_NOT_FOUND')
        return error_response(
            status_code=404,
            error_code='SESSION_NOT_FOUND',
            message='Session does not exist or is inactive',
            details={'sessionId': session_id}
        )
    
    if not session.get('isActive', False):
        logger.warning(
            message=f"Session is inactive: {session_id}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_join_session',
            error_code='SESSION_NOT_FOUND',
            sessionId=session_id
        )
        metrics_publisher.emit_connection_error('SESSION_NOT_FOUND')
        return error_response(
            status_code=404,
            error_code='SESSION_NOT_FOUND',
            message='Session does not exist or is inactive',
            details={'sessionId': session_id}
        )
    
    # Validate language support
    source_language = session['sourceLanguage']
    language_validator.validate_target_language(source_language, target_language)
    
    # Check session capacity
    current_listener_count = session.get('listenerCount', 0)
    if current_listener_count >= MAX_LISTENERS_PER_SESSION:
        logger.warning(
            message=f"Session at capacity: {session_id} ({current_listener_count} listeners)",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_join_session',
            error_code='SESSION_FULL',
            sessionId=session_id,
            listenerCount=current_listener_count
        )
        metrics_publisher.emit_connection_error('SESSION_FULL')
        return error_response(
            status_code=503,
            error_code='SESSION_FULL',
            message=f'Session has reached maximum capacity of {MAX_LISTENERS_PER_SESSION} listeners',
            details={
                'sessionId': session_id,
                'maxListeners': MAX_LISTENERS_PER_SESSION
            }
        )
    
    # Create connection record
    connections_repo.create_connection(
        connection_id=connection_id,
        session_id=session_id,
        role='listener',
        target_language=target_language,
        ip_address=ip_address,
        session_max_duration_hours=SESSION_MAX_DURATION_HOURS
    )
    
    # Atomically increment listener count
    try:
        new_listener_count = sessions_repo.increment_listener_count(session_id)
    except ConditionalCheckFailedError:
        # Session became inactive or was deleted
        logger.warning(
            message=f"Session became inactive during join: {session_id}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_join_session',
            error_code='SESSION_NOT_FOUND',
            sessionId=session_id
        )
        # Clean up connection record
        connections_repo.delete_connection(connection_id)
        metrics_publisher.emit_connection_error('SESSION_NOT_FOUND')
        return error_response(
            status_code=404,
            error_code='SESSION_NOT_FOUND',
            message='Session is no longer active',
            details={'sessionId': session_id}
        )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        message="Listener joined successfully",
        correlation_id=f"{session_id}-{connection_id}",
        operation='handle_join_session',
        duration_ms=duration_ms,
        sessionId=session_id,
        targetLanguage=target_language,
        listenerCount=new_listener_count
    )
    
    # Emit metrics
    metrics_publisher.emit_listener_join_latency(duration_ms, session_id)
    
    # Return success response
    return success_response(
        status_code=200,
        body={
            'type': 'sessionJoined',
            'sessionId': session_id,
            'targetLanguage': target_language,
            'sourceLanguage': source_language,
            'connectionId': connection_id,
            'timestamp': int(time.time() * 1000)
        }
    )



def route_control_message(connection_id: str, action: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Route control messages to appropriate handlers.
    
    Args:
        connection_id: WebSocket connection ID
        action: Control action to perform
        body: Message body
        
    Returns:
        API Gateway response
    """
    start_time = time.time()
    
    logger.info(
        message=f"Routing control message: {action}",
        correlation_id=connection_id,
        operation='route_control_message',
        action=action
    )
    
    try:
        # Get connection to validate role
        connection = connections_repo.get_connection(connection_id)
        
        if not connection:
            logger.warning(
                message="Connection not found",
                correlation_id=connection_id,
                operation='route_control_message',
                error_code='CONNECTION_NOT_FOUND'
            )
            metrics_publisher.emit_connection_error('CONNECTION_NOT_FOUND')
            return error_response(
                status_code=404,
                error_code='CONNECTION_NOT_FOUND',
                message='Connection not found'
            )
        
        role = connection.get('role', '')
        session_id = connection.get('sessionId', '')
        
        # Speaker control actions
        speaker_actions = [
            'pauseBroadcast',
            'resumeBroadcast',
            'muteBroadcast',
            'unmuteBroadcast',
            'setVolume',
            'speakerStateChange'
        ]
        
        # Listener control actions
        listener_actions = [
            'pausePlayback',
            'changeLanguage'
        ]
        
        # Validate role for action
        if action in speaker_actions and role != 'speaker':
            logger.warning(
                message=f"Unauthorized action {action} for role {role}",
                correlation_id=f"{session_id}-{connection_id}",
                operation='route_control_message',
                error_code='UNAUTHORIZED_ACTION',
                action=action,
                role=role
            )
            metrics_publisher.emit_connection_error('UNAUTHORIZED_ACTION')
            return error_response(
                status_code=403,
                error_code='UNAUTHORIZED_ACTION',
                message=f'Action {action} requires speaker role'
            )
        
        if action in listener_actions and role != 'listener':
            logger.warning(
                message=f"Unauthorized action {action} for role {role}",
                correlation_id=f"{session_id}-{connection_id}",
                operation='route_control_message',
                error_code='UNAUTHORIZED_ACTION',
                action=action,
                role=role
            )
            metrics_publisher.emit_connection_error('UNAUTHORIZED_ACTION')
            return error_response(
                status_code=403,
                error_code='UNAUTHORIZED_ACTION',
                message=f'Action {action} requires listener role'
            )
        
        # Log control action
        logger.info(
            message=f"Processing control action: {action}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='route_control_message',
            action=action,
            role=role,
            sessionId=session_id
        )
        
        # Route to handler
        if action == 'heartbeat':
            return handle_heartbeat(connection_id, session_id)
        elif action == 'pauseBroadcast':
            return handle_pause_broadcast(connection_id, session_id)
        elif action == 'resumeBroadcast':
            return handle_resume_broadcast(connection_id, session_id)
        elif action == 'muteBroadcast':
            return handle_mute_broadcast(connection_id, session_id)
        elif action == 'unmuteBroadcast':
            return handle_unmute_broadcast(connection_id, session_id)
        elif action == 'setVolume':
            return handle_set_volume(connection_id, session_id, body)
        elif action == 'speakerStateChange':
            return handle_speaker_state_change(connection_id, session_id, body)
        elif action == 'pausePlayback':
            return handle_pause_playback(connection_id, session_id)
        elif action == 'changeLanguage':
            return handle_change_language(connection_id, session_id, body)
        else:
            return error_response(
                status_code=400,
                error_code='INVALID_ACTION',
                message=f'Unsupported control action: {action}'
            )
    
    except Exception as e:
        logger.error(
            message=f"Error routing control message: {str(e)}",
            correlation_id=connection_id,
            operation='route_control_message',
            error_code='INTERNAL_ERROR',
            exc_info=True
        )
        metrics_publisher.emit_connection_error('INTERNAL_ERROR')
        return error_response(
            status_code=500,
            error_code='INTERNAL_ERROR',
            message='An unexpected error occurred'
        )
    finally:
        duration_ms = int((time.time() - start_time) * 1000)
        metrics_publisher.emit_control_message_latency(duration_ms, action)


def broadcast_state_to_json(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert broadcast state dictionary to JSON-serializable format.
    
    Args:
        state_dict: Broadcast state dictionary
        
    Returns:
        JSON-serializable dictionary
    """
    from decimal import Decimal
    
    result = state_dict.copy()
    # Convert Decimal to float for JSON serialization
    if 'volume' in result and isinstance(result['volume'], Decimal):
        result['volume'] = float(result['volume'])
    return result


def send_to_connection(connection_id: str, message: Dict[str, Any]) -> bool:
    """
    Send message to WebSocket connection.
    
    Args:
        connection_id: WebSocket connection ID
        message: Message to send
        
    Returns:
        True if successful, False otherwise
    """
    if not apigw_management_client:
        logger.error(
            message="API Gateway Management client not initialized",
            correlation_id=connection_id,
            operation='send_to_connection'
        )
        return False
    
    try:
        data = json.dumps(message, cls=DecimalEncoder).encode('utf-8')
        logger.info(
            message=f"Sending message to connection {connection_id}: {message.get('type', 'unknown')}",
            correlation_id=connection_id,
            operation='send_to_connection',
            message_type=message.get('type')
        )
        apigw_management_client.post_to_connection(
            ConnectionId=connection_id,
            Data=data
        )
        logger.info(
            message=f"Successfully sent message to connection {connection_id}",
            correlation_id=connection_id,
            operation='send_to_connection'
        )
        return True
    except apigw_management_client.exceptions.GoneException:
        logger.warning(
            message=f"Connection {connection_id} is gone",
            correlation_id=connection_id,
            operation='send_to_connection'
        )
        # Clean up stale connection
        try:
            connections_repo.delete_connection(connection_id)
        except Exception as e:
            logger.error(
                message=f"Error deleting stale connection: {str(e)}",
                correlation_id=connection_id,
                operation='send_to_connection'
            )
        return False
    except Exception as e:
        logger.error(
            message=f"Error sending message to connection: {str(e)}",
            correlation_id=connection_id,
            operation='send_to_connection',
            exc_info=True
        )
        return False


def notify_listeners(session_id: str, message: Dict[str, Any]) -> Dict[str, int]:
    """
    Send message to all listeners in a session.
    
    Args:
        session_id: Session identifier
        message: Message to send
        
    Returns:
        Dictionary with success and failure counts
    """
    start_time = time.time()
    
    # Get all listener connections
    listeners = connections_repo.get_listener_connections(session_id)
    
    success_count = 0
    failure_count = 0
    
    for listener in listeners:
        listener_conn_id = listener.get('connectionId')
        if send_to_connection(listener_conn_id, message):
            success_count += 1
        else:
            failure_count += 1
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        message=f"Notified {success_count} listeners, {failure_count} failures",
        correlation_id=session_id,
        operation='notify_listeners',
        duration_ms=duration_ms,
        success_count=success_count,
        failure_count=failure_count
    )
    
    # Emit metrics
    metrics_publisher.emit_listener_notification_latency(duration_ms, session_id)
    if failure_count > 0:
        metrics_publisher.emit_listener_notification_failures(failure_count, session_id)
    
    return {
        'success': success_count,
        'failure': failure_count
    }



def handle_pause_broadcast(connection_id: str, session_id: str) -> Dict[str, Any]:
    """
    Handle pause broadcast request from speaker.
    
    Args:
        connection_id: WebSocket connection ID
        session_id: Session identifier
        
    Returns:
        API Gateway response
    """
    start_time = time.time()
    
    logger.info(
        message="Pausing broadcast",
        correlation_id=f"{session_id}-{connection_id}",
        operation='handle_pause_broadcast',
        sessionId=session_id
    )
    
    try:
        # Update broadcast state in DynamoDB
        new_state = sessions_repo.pause_broadcast(session_id)
        
        # Notify all listeners
        listener_message = {
            'type': 'broadcastPaused',
            'sessionId': session_id,
            'timestamp': int(time.time() * 1000)
        }
        
        notification_result = notify_listeners(session_id, listener_message)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            message="Broadcast paused successfully",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_pause_broadcast',
            duration_ms=duration_ms,
            sessionId=session_id,
            listeners_notified=notification_result['success']
        )
        
        # Return acknowledgment to speaker
        return success_response(
            status_code=200,
            body={
                'type': 'broadcastPaused',
                'sessionId': session_id,
                'broadcastState': broadcast_state_to_json(new_state.to_dict()),
                'listenersNotified': notification_result['success'],
                'timestamp': int(time.time() * 1000)
            }
        )
    
    except ItemNotFoundError:
        logger.warning(
            message=f"Session not found: {session_id}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_pause_broadcast',
            error_code='SESSION_NOT_FOUND',
            sessionId=session_id
        )
        return error_response(
            status_code=404,
            error_code='SESSION_NOT_FOUND',
            message='Session not found'
        )
    
    except Exception as e:
        logger.error(
            message=f"Error pausing broadcast: {str(e)}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_pause_broadcast',
            error_code='INTERNAL_ERROR',
            sessionId=session_id,
            exc_info=True
        )
        return error_response(
            status_code=500,
            error_code='INTERNAL_ERROR',
            message='Failed to pause broadcast'
        )


def handle_resume_broadcast(connection_id: str, session_id: str) -> Dict[str, Any]:
    """
    Handle resume broadcast request from speaker.
    
    Args:
        connection_id: WebSocket connection ID
        session_id: Session identifier
        
    Returns:
        API Gateway response
    """
    start_time = time.time()
    pause_start_time = None
    
    logger.info(
        message="Resuming broadcast",
        correlation_id=f"{session_id}-{connection_id}",
        operation='handle_resume_broadcast',
        sessionId=session_id
    )
    
    try:
        # Get current state to calculate pause duration
        current_state = sessions_repo.get_broadcast_state(session_id)
        if current_state and current_state.isPaused:
            pause_start_time = current_state.lastStateChange
        
        # Update broadcast state in DynamoDB
        new_state = sessions_repo.resume_broadcast(session_id)
        
        # Calculate pause duration if available
        pause_duration_ms = None
        if pause_start_time:
            pause_duration_ms = int(time.time() * 1000) - pause_start_time
            # Emit metric for pause duration
            metrics_publisher.emit_pause_duration(pause_duration_ms, session_id)
        
        # Notify all listeners
        listener_message = {
            'type': 'broadcastResumed',
            'sessionId': session_id,
            'timestamp': int(time.time() * 1000)
        }
        
        notification_result = notify_listeners(session_id, listener_message)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            message="Broadcast resumed successfully",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_resume_broadcast',
            duration_ms=duration_ms,
            sessionId=session_id,
            pause_duration_ms=pause_duration_ms,
            listeners_notified=notification_result['success']
        )
        
        # Return acknowledgment to speaker
        return success_response(
            status_code=200,
            body={
                'type': 'broadcastResumed',
                'sessionId': session_id,
                'broadcastState': broadcast_state_to_json(new_state.to_dict()),
                'pauseDuration': pause_duration_ms,
                'listenersNotified': notification_result['success'],
                'timestamp': int(time.time() * 1000)
            }
        )
    
    except ItemNotFoundError:
        logger.warning(
            message=f"Session not found: {session_id}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_resume_broadcast',
            error_code='SESSION_NOT_FOUND',
            sessionId=session_id
        )
        return error_response(
            status_code=404,
            error_code='SESSION_NOT_FOUND',
            message='Session not found'
        )
    
    except Exception as e:
        logger.error(
            message=f"Error resuming broadcast: {str(e)}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_resume_broadcast',
            error_code='INTERNAL_ERROR',
            sessionId=session_id,
            exc_info=True
        )
        return error_response(
            status_code=500,
            error_code='INTERNAL_ERROR',
            message='Failed to resume broadcast'
        )



def handle_mute_broadcast(connection_id: str, session_id: str) -> Dict[str, Any]:
    """
    Handle mute broadcast request from speaker.
    
    Args:
        connection_id: WebSocket connection ID
        session_id: Session identifier
        
    Returns:
        API Gateway response
    """
    start_time = time.time()
    
    logger.info(
        message="Muting broadcast",
        correlation_id=f"{session_id}-{connection_id}",
        operation='handle_mute_broadcast',
        sessionId=session_id
    )
    
    try:
        # Update broadcast state in DynamoDB
        new_state = sessions_repo.mute_broadcast(session_id)
        
        # Notify all listeners
        listener_message = {
            'type': 'broadcastMuted',
            'sessionId': session_id,
            'timestamp': int(time.time() * 1000)
        }
        
        notification_result = notify_listeners(session_id, listener_message)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            message="Broadcast muted successfully",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_mute_broadcast',
            duration_ms=duration_ms,
            sessionId=session_id,
            listeners_notified=notification_result['success']
        )
        
        # Return acknowledgment to speaker
        return success_response(
            status_code=200,
            body={
                'type': 'broadcastMuted',
                'sessionId': session_id,
                'broadcastState': broadcast_state_to_json(new_state.to_dict()),
                'listenersNotified': notification_result['success'],
                'timestamp': int(time.time() * 1000)
            }
        )
    
    except ItemNotFoundError:
        logger.warning(
            message=f"Session not found: {session_id}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_mute_broadcast',
            error_code='SESSION_NOT_FOUND',
            sessionId=session_id
        )
        return error_response(
            status_code=404,
            error_code='SESSION_NOT_FOUND',
            message='Session not found'
        )
    
    except Exception as e:
        logger.error(
            message=f"Error muting broadcast: {str(e)}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_mute_broadcast',
            error_code='INTERNAL_ERROR',
            sessionId=session_id,
            exc_info=True
        )
        return error_response(
            status_code=500,
            error_code='INTERNAL_ERROR',
            message='Failed to mute broadcast'
        )


def handle_unmute_broadcast(connection_id: str, session_id: str) -> Dict[str, Any]:
    """
    Handle unmute broadcast request from speaker.
    
    Args:
        connection_id: WebSocket connection ID
        session_id: Session identifier
        
    Returns:
        API Gateway response
    """
    start_time = time.time()
    
    logger.info(
        message="Unmuting broadcast",
        correlation_id=f"{session_id}-{connection_id}",
        operation='handle_unmute_broadcast',
        sessionId=session_id
    )
    
    try:
        # Update broadcast state in DynamoDB
        new_state = sessions_repo.unmute_broadcast(session_id)
        
        # Notify all listeners
        listener_message = {
            'type': 'broadcastUnmuted',
            'sessionId': session_id,
            'timestamp': int(time.time() * 1000)
        }
        
        notification_result = notify_listeners(session_id, listener_message)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            message="Broadcast unmuted successfully",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_unmute_broadcast',
            duration_ms=duration_ms,
            sessionId=session_id,
            listeners_notified=notification_result['success']
        )
        
        # Return acknowledgment to speaker
        return success_response(
            status_code=200,
            body={
                'type': 'broadcastUnmuted',
                'sessionId': session_id,
                'broadcastState': broadcast_state_to_json(new_state.to_dict()),
                'listenersNotified': notification_result['success'],
                'timestamp': int(time.time() * 1000)
            }
        )
    
    except ItemNotFoundError:
        logger.warning(
            message=f"Session not found: {session_id}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_unmute_broadcast',
            error_code='SESSION_NOT_FOUND',
            sessionId=session_id
        )
        return error_response(
            status_code=404,
            error_code='SESSION_NOT_FOUND',
            message='Session not found'
        )
    
    except Exception as e:
        logger.error(
            message=f"Error unmuting broadcast: {str(e)}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_unmute_broadcast',
            error_code='INTERNAL_ERROR',
            sessionId=session_id,
            exc_info=True
        )
        return error_response(
            status_code=500,
            error_code='INTERNAL_ERROR',
            message='Failed to unmute broadcast'
        )



def handle_set_volume(connection_id: str, session_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle set volume request from speaker.
    
    Args:
        connection_id: WebSocket connection ID
        session_id: Session identifier
        body: Message body containing volumeLevel
        
    Returns:
        API Gateway response
    """
    start_time = time.time()
    
    # Extract and validate volume level
    volume_level = body.get('volumeLevel')
    
    if volume_level is None:
        return error_response(
            status_code=400,
            error_code='MISSING_PARAMETER',
            message='volumeLevel parameter is required'
        )
    
    try:
        volume_level = float(volume_level)
    except (ValueError, TypeError):
        return error_response(
            status_code=400,
            error_code='INVALID_PARAMETER',
            message='volumeLevel must be a number'
        )
    
    # Validate range
    if not 0.0 <= volume_level <= 1.0:
        return error_response(
            status_code=400,
            error_code='INVALID_PARAMETER',
            message='volumeLevel must be between 0.0 and 1.0',
            details={'volumeLevel': volume_level}
        )
    
    logger.info(
        message=f"Setting broadcast volume to {volume_level}",
        correlation_id=f"{session_id}-{connection_id}",
        operation='handle_set_volume',
        sessionId=session_id,
        volumeLevel=volume_level
    )
    
    try:
        # Update broadcast state in DynamoDB
        new_state = sessions_repo.set_broadcast_volume(session_id, volume_level)
        
        # Notify all listeners
        listener_message = {
            'type': 'volumeChanged',
            'sessionId': session_id,
            'volumeLevel': volume_level,
            'timestamp': int(time.time() * 1000)
        }
        
        notification_result = notify_listeners(session_id, listener_message)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Check if volume is 0.0 (treated as mute)
        is_muted = volume_level == 0.0
        
        logger.info(
            message=f"Broadcast volume set successfully to {volume_level}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_set_volume',
            duration_ms=duration_ms,
            sessionId=session_id,
            volumeLevel=volume_level,
            is_muted=is_muted,
            listeners_notified=notification_result['success']
        )
        
        # Return acknowledgment to speaker
        return success_response(
            status_code=200,
            body={
                'type': 'volumeChanged',
                'sessionId': session_id,
                'volumeLevel': volume_level,
                'broadcastState': broadcast_state_to_json(new_state.to_dict()),
                'listenersNotified': notification_result['success'],
                'timestamp': int(time.time() * 1000)
            }
        )
    
    except ItemNotFoundError:
        logger.warning(
            message=f"Session not found: {session_id}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_set_volume',
            error_code='SESSION_NOT_FOUND',
            sessionId=session_id
        )
        return error_response(
            status_code=404,
            error_code='SESSION_NOT_FOUND',
            message='Session not found'
        )
    
    except Exception as e:
        logger.error(
            message=f"Error setting volume: {str(e)}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_set_volume',
            error_code='INTERNAL_ERROR',
            sessionId=session_id,
            exc_info=True
        )
        return error_response(
            status_code=500,
            error_code='INTERNAL_ERROR',
            message='Failed to set volume'
        )



def handle_speaker_state_change(connection_id: str, session_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle speaker state change request.
    
    Args:
        connection_id: WebSocket connection ID
        session_id: Session identifier
        body: Message body containing state object
        
    Returns:
        API Gateway response
    """
    start_time = time.time()
    
    # Extract state object
    state = body.get('state')
    
    if not state or not isinstance(state, dict):
        return error_response(
            status_code=400,
            error_code='MISSING_PARAMETER',
            message='state parameter is required and must be an object'
        )
    
    # Validate state fields
    valid_fields = {'isPaused', 'isMuted', 'volume'}
    provided_fields = set(state.keys())
    invalid_fields = provided_fields - valid_fields
    
    if invalid_fields:
        return error_response(
            status_code=400,
            error_code='INVALID_PARAMETER',
            message=f'Invalid state fields: {", ".join(invalid_fields)}',
            details={'invalidFields': list(invalid_fields)}
        )
    
    if not provided_fields:
        return error_response(
            status_code=400,
            error_code='INVALID_PARAMETER',
            message='state object must contain at least one field (isPaused, isMuted, volume)'
        )
    
    # Validate volume if provided
    if 'volume' in state:
        try:
            volume = float(state['volume'])
            if not 0.0 <= volume <= 1.0:
                return error_response(
                    status_code=400,
                    error_code='INVALID_PARAMETER',
                    message='volume must be between 0.0 and 1.0',
                    details={'volume': volume}
                )
            state['volume'] = volume
        except (ValueError, TypeError):
            return error_response(
                status_code=400,
                error_code='INVALID_PARAMETER',
                message='volume must be a number'
            )
    
    # Validate boolean fields
    for field in ['isPaused', 'isMuted']:
        if field in state and not isinstance(state[field], bool):
            return error_response(
                status_code=400,
                error_code='INVALID_PARAMETER',
                message=f'{field} must be a boolean'
            )
    
    logger.info(
        message=f"Updating speaker state: {state}",
        correlation_id=f"{session_id}-{connection_id}",
        operation='handle_speaker_state_change',
        sessionId=session_id,
        state=state
    )
    
    try:
        # Get current broadcast state
        current_state = sessions_repo.get_broadcast_state(session_id)
        
        if not current_state:
            return error_response(
                status_code=404,
                error_code='SESSION_NOT_FOUND',
                message='Session not found'
            )
        
        # Update fields that were provided
        if 'isPaused' in state:
            current_state = current_state.pause() if state['isPaused'] else current_state.resume()
        if 'isMuted' in state:
            current_state = current_state.mute() if state['isMuted'] else current_state.unmute()
        if 'volume' in state:
            current_state = current_state.set_volume(state['volume'])
        
        # Update broadcast state atomically in DynamoDB
        sessions_repo.update_broadcast_state(
            session_id=session_id,
            broadcast_state=current_state
        )
        
        new_state = current_state
        
        # Notify all listeners
        listener_message = {
            'type': 'speakerStateChanged',
            'sessionId': session_id,
            'broadcastState': new_state.to_dict(),
            'timestamp': int(time.time() * 1000)
        }
        
        notification_result = notify_listeners(session_id, listener_message)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            message="Speaker state updated successfully",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_speaker_state_change',
            duration_ms=duration_ms,
            sessionId=session_id,
            new_state=new_state.to_dict(),
            listeners_notified=notification_result['success']
        )
        
        # Return acknowledgment to speaker
        return success_response(
            status_code=200,
            body={
                'type': 'speakerStateChanged',
                'sessionId': session_id,
                'broadcastState': broadcast_state_to_json(new_state.to_dict()),
                'listenersNotified': notification_result['success'],
                'timestamp': int(time.time() * 1000)
            }
        )
    
    except ItemNotFoundError:
        logger.warning(
            message=f"Session not found: {session_id}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_speaker_state_change',
            error_code='SESSION_NOT_FOUND',
            sessionId=session_id
        )
        return error_response(
            status_code=404,
            error_code='SESSION_NOT_FOUND',
            message='Session not found'
        )
    
    except Exception as e:
        logger.error(
            message=f"Error updating speaker state: {str(e)}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_speaker_state_change',
            error_code='INTERNAL_ERROR',
            sessionId=session_id,
            exc_info=True
        )
        return error_response(
            status_code=500,
            error_code='INTERNAL_ERROR',
            message='Failed to update speaker state'
        )



def handle_heartbeat(connection_id: str, session_id: str) -> Dict[str, Any]:
    """
    Handle heartbeat message from client.
    
    Args:
        connection_id: WebSocket connection ID
        session_id: Session identifier
        
    Returns:
        API Gateway response
    """
    logger.debug(
        message="Heartbeat received",
        correlation_id=f"{session_id}-{connection_id}",
        operation='handle_heartbeat',
        sessionId=session_id
    )
    
    # Send heartbeat acknowledgment
    ack_msg = {
        'type': 'heartbeatAck',
        'timestamp': int(time.time() * 1000)
    }
    
    send_to_connection(connection_id, ack_msg)
    
    # Return success to keep connection open
    return success_response(status_code=200, body={})


def handle_pause_playback(connection_id: str, session_id: str) -> Dict[str, Any]:
    """
    Handle pause playback request from listener (client-side only).
    
    Args:
        connection_id: WebSocket connection ID
        session_id: Session identifier
        
    Returns:
        API Gateway response
    """
    logger.info(
        message="Listener pausing playback (client-side)",
        correlation_id=f"{session_id}-{connection_id}",
        operation='handle_pause_playback',
        sessionId=session_id
    )
    
    # This is a client-side operation, just acknowledge
    return success_response(
        status_code=200,
        body={
            'type': 'playbackPaused',
            'sessionId': session_id,
            'timestamp': int(time.time() * 1000)
        }
    )


def handle_change_language(connection_id: str, session_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle change language request from listener.
    
    Args:
        connection_id: WebSocket connection ID
        session_id: Session identifier
        body: Message body containing targetLanguage
        
    Returns:
        API Gateway response
    """
    start_time = time.time()
    
    # Extract and validate target language
    target_language = body.get('targetLanguage', '').strip()
    
    if not target_language:
        return error_response(
            status_code=400,
            error_code='MISSING_PARAMETER',
            message='targetLanguage parameter is required'
        )
    
    # Validate language code format
    try:
        validate_language_code(target_language, 'targetLanguage')
    except ValidationError as e:
        return error_response(
            status_code=400,
            error_code='INVALID_PARAMETER',
            message=e.message,
            details={'field': e.field}
        )
    
    # Validate language is supported
    if target_language not in SUPPORTED_LANGUAGES:
        return error_response(
            status_code=400,
            error_code='UNSUPPORTED_LANGUAGE',
            message=f'Language {target_language} is not supported',
            details={
                'targetLanguage': target_language,
                'supportedLanguages': SUPPORTED_LANGUAGES
            }
        )
    
    logger.info(
        message=f"Changing listener language to {target_language}",
        correlation_id=f"{session_id}-{connection_id}",
        operation='handle_change_language',
        sessionId=session_id,
        targetLanguage=target_language
    )
    
    try:
        # Get session to validate source language compatibility
        session = sessions_repo.get_session(session_id)
        
        if not session:
            return error_response(
                status_code=404,
                error_code='SESSION_NOT_FOUND',
                message='Session not found'
            )
        
        source_language = session.get('sourceLanguage', '')
        
        # Validate language pair
        try:
            language_validator.validate_target_language(source_language, target_language)
        except UnsupportedLanguageError as e:
            return error_response(
                status_code=400,
                error_code='UNSUPPORTED_LANGUAGE',
                message=e.message,
                details={'languageCode': e.language_code}
            )
        
        # Update connection record with new target language
        connection = connections_repo.get_connection(connection_id)
        
        if not connection:
            return error_response(
                status_code=404,
                error_code='CONNECTION_NOT_FOUND',
                message='Connection not found'
            )
        
        # Update the connection with new target language
        old_language = connection.get('targetLanguage', '')
        
        # Delete old connection and create new one with updated language
        # (DynamoDB doesn't support updating GSI sort keys, so we recreate)
        connections_repo.delete_connection(connection_id)
        connections_repo.create_connection(
            connection_id=connection_id,
            session_id=session_id,
            role='listener',
            target_language=target_language,
            ip_address=connection.get('ipAddress'),
            session_max_duration_hours=SESSION_MAX_DURATION_HOURS
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            message=f"Listener language changed from {old_language} to {target_language}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_change_language',
            duration_ms=duration_ms,
            sessionId=session_id,
            oldLanguage=old_language,
            newLanguage=target_language
        )
        
        # Return acknowledgment to listener
        return success_response(
            status_code=200,
            body={
                'type': 'languageChanged',
                'sessionId': session_id,
                'targetLanguage': target_language,
                'sourceLanguage': source_language,
                'timestamp': int(time.time() * 1000)
            }
        )
    
    except Exception as e:
        logger.error(
            message=f"Error changing language: {str(e)}",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_change_language',
            error_code='INTERNAL_ERROR',
            sessionId=session_id,
            exc_info=True
        )
        return error_response(
            status_code=500,
            error_code='INTERNAL_ERROR',
            message='Failed to change language'
        )
