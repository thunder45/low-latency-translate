"""
WebSocket Connection Handler for $connect events.
Handles both speaker session creation and listener joining.
"""
import json
import logging
import os
import time

from shared.data_access import (
    SessionsRepository,
    ConnectionsRepository,
    RateLimitExceededError,
    ConditionalCheckFailedError,
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

# Initialize structured logger
base_logger = logging.getLogger()
base_logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))
logger = get_structured_logger('ConnectionHandler')

# Initialize repositories and services (reused across Lambda invocations)
sessions_repo = SessionsRepository(os.environ.get('SESSIONS_TABLE', 'Sessions'))
connections_repo = ConnectionsRepository(os.environ.get('CONNECTIONS_TABLE', 'Connections'))
rate_limit_service = RateLimitService()
language_validator = LanguageValidator(region=os.environ.get('AWS_REGION', 'us-east-1'))
session_id_service = SessionIDService(sessions_repo)
metrics_publisher = get_metrics_publisher()

# Configuration
MAX_LISTENERS_PER_SESSION = int(os.environ.get('MAX_LISTENERS_PER_SESSION', '500'))
SESSION_MAX_DURATION_HOURS = int(os.environ.get('SESSION_MAX_DURATION_HOURS', '2'))


def lambda_handler(event, context):
    """
    Handle WebSocket $connect event.
    
    Args:
        event: API Gateway WebSocket $connect event
        context: Lambda context
        
    Returns:
        Response with status code and body
    """
    connection_id = event['requestContext']['connectionId']
    query_params = event.get('queryStringParameters') or {}
    action = query_params.get('action', '')
    
    # Extract IP address for rate limiting
    ip_address = event['requestContext'].get('identity', {}).get('sourceIp', 'unknown')
    
    logger.info(
        message="Connection handler invoked",
        correlation_id=connection_id,
        operation='lambda_handler',
        ip_address=ip_address,
        action=action
    )
    
    try:
        # Validate action parameter
        validate_action(action)
        
        # Check connection attempt rate limit
        rate_limit_service.check_connection_attempt_limit(ip_address)
        
        # Route to appropriate handler
        if action == 'createSession':
            return handle_create_session(event, connection_id, query_params, ip_address)
        elif action == 'joinSession':
            return handle_join_session(event, connection_id, query_params, ip_address)
        else:
            return error_response(
                status_code=400,
                error_code='INVALID_ACTION',
                message=f'Unsupported action: {action}'
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
        metrics_publisher.emit_rate_limit_exceeded(action)
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


def handle_create_session(event, connection_id, query_params, ip_address):
    """
    Handle speaker session creation.
    
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
    source_language = query_params.get('sourceLanguage', '')
    quality_tier = query_params.get('qualityTier', 'standard')
    
    validate_language_code(source_language, 'sourceLanguage')
    validate_quality_tier(quality_tier)
    
    # Extract and validate partial results configuration
    partial_results_enabled = query_params.get('partialResults', 'true').lower() == 'true'
    min_stability = query_params.get('minStability', '0.85')
    max_buffer_timeout = query_params.get('maxBufferTimeout', '5.0')
    
    # Validate configuration parameters
    try:
        min_stability_threshold = float(min_stability)
        max_buffer_timeout_seconds = float(max_buffer_timeout)
        
        # Validate ranges
        if not 0.70 <= min_stability_threshold <= 0.95:
            raise ValueError(
                f"minStability must be between 0.70 and 0.95, got {min_stability_threshold}"
            )
        
        if not 2.0 <= max_buffer_timeout_seconds <= 10.0:
            raise ValueError(
                f"maxBufferTimeout must be between 2.0 and 10.0, got {max_buffer_timeout_seconds}"
            )
    except ValueError as e:
        logger.warning(
            message=f"Invalid partial results configuration: {str(e)}",
            correlation_id=connection_id,
            operation='handle_create_session',
            error_code='INVALID_CONFIGURATION'
        )
        metrics_publisher.emit_connection_error('INVALID_CONFIGURATION')
        return error_response(
            status_code=400,
            error_code='INVALID_CONFIGURATION',
            message=str(e)
        )
    
    # Extract user context from authorizer
    authorizer_context = event['requestContext'].get('authorizer', {})
    user_id = authorizer_context.get('userId')
    
    if not user_id:
        logger.error(
            message="Missing userId in authorizer context",
            correlation_id=connection_id,
            operation='handle_create_session',
            error_code='UNAUTHORIZED'
        )
        metrics_publisher.emit_connection_error('UNAUTHORIZED')
        return error_response(
            status_code=401,
            error_code='UNAUTHORIZED',
            message='Authentication required'
        )
    
    logger.info(
        message=f"Creating session for user {user_id}",
        correlation_id=connection_id,
        operation='handle_create_session',
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
        operation='handle_create_session',
        duration_ms=duration_ms,
        user_id=user_id
    )
    
    # Emit metrics
    metrics_publisher.emit_session_creation_latency(duration_ms, user_id)
    
    # Return success response
    return success_response(
        status_code=200,
        body={
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
    )


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
