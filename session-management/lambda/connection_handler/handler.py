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

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize repositories and services (reused across Lambda invocations)
sessions_repo = SessionsRepository(os.environ.get('SESSIONS_TABLE', 'Sessions'))
connections_repo = ConnectionsRepository(os.environ.get('CONNECTIONS_TABLE', 'Connections'))
rate_limit_service = RateLimitService()
language_validator = LanguageValidator(region=os.environ.get('AWS_REGION', 'us-east-1'))
session_id_service = SessionIDService(sessions_repo)

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
        f"Connection handler invoked",
        extra={
            'connectionId': connection_id,
            'action': action,
            'ipAddress': ip_address
        }
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
        logger.warning(f"Validation error: {e.message}", extra={'field': e.field})
        return error_response(
            status_code=400,
            error_code='INVALID_PARAMETERS',
            message=e.message,
            details={'field': e.field}
        )
    
    except RateLimitExceededError as e:
        logger.warning(f"Rate limit exceeded: {str(e)}")
        return rate_limit_error_response(e.retry_after)
    
    except UnsupportedLanguageError as e:
        logger.warning(f"Unsupported language: {e.message}")
        return error_response(
            status_code=400,
            error_code='UNSUPPORTED_LANGUAGE',
            message=e.message,
            details={'languageCode': e.language_code}
        )
    
    except Exception as e:
        logger.error(
            f"Unexpected error in connection handler: {str(e)}",
            exc_info=True,
            extra={'connectionId': connection_id}
        )
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
    
    # Extract user context from authorizer
    authorizer_context = event['requestContext'].get('authorizer', {})
    user_id = authorizer_context.get('userId')
    
    if not user_id:
        logger.error("Missing userId in authorizer context")
        return error_response(
            status_code=401,
            error_code='UNAUTHORIZED',
            message='Authentication required'
        )
    
    logger.info(
        f"Creating session for user {user_id}",
        extra={
            'userId': user_id,
            'sourceLanguage': source_language,
            'qualityTier': quality_tier
        }
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
        session_max_duration_hours=SESSION_MAX_DURATION_HOURS
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
        f"Session created successfully",
        extra={
            'sessionId': session_id,
            'userId': user_id,
            'durationMs': duration_ms
        }
    )
    
    # Return success response
    return success_response(
        status_code=200,
        body={
            'type': 'sessionCreated',
            'sessionId': session_id,
            'sourceLanguage': source_language,
            'qualityTier': quality_tier,
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
        f"Listener joining session",
        extra={
            'sessionId': session_id,
            'targetLanguage': target_language
        }
    )
    
    # Check rate limit for listener joins
    rate_limit_service.check_listener_join_limit(ip_address)
    
    # Validate session exists and is active
    session = sessions_repo.get_session(session_id)
    
    if not session:
        logger.warning(f"Session not found: {session_id}")
        return error_response(
            status_code=404,
            error_code='SESSION_NOT_FOUND',
            message='Session does not exist or is inactive',
            details={'sessionId': session_id}
        )
    
    if not session.get('isActive', False):
        logger.warning(f"Session is inactive: {session_id}")
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
            f"Session at capacity: {session_id} ({current_listener_count} listeners)"
        )
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
        logger.warning(f"Session became inactive during join: {session_id}")
        # Clean up connection record
        connections_repo.delete_connection(connection_id)
        return error_response(
            status_code=404,
            error_code='SESSION_NOT_FOUND',
            message='Session is no longer active',
            details={'sessionId': session_id}
        )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        f"Listener joined successfully",
        extra={
            'sessionId': session_id,
            'targetLanguage': target_language,
            'listenerCount': new_listener_count,
            'durationMs': duration_ms
        }
    )
    
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
