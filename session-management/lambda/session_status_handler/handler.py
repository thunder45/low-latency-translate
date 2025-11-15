"""
WebSocket Session Status Handler for getSessionStatus route.
Handles session status queries and periodic status updates.
"""
import json
import logging
import os
import time
from typing import Dict, Any, List, Optional
from collections import defaultdict

from shared.data_access import (
    SessionsRepository,
    ConnectionsRepository,
    ItemNotFoundError,
)
from shared.utils.response_builder import (
    success_response,
    error_response,
)
from shared.utils.structured_logger import get_structured_logger
from shared.utils.metrics import get_metrics_publisher

# Initialize structured logger
base_logger = logging.getLogger()
base_logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))
logger = get_structured_logger('SessionStatusHandler')

# Initialize repositories (reused across Lambda invocations)
sessions_repo = SessionsRepository(os.environ.get('SESSIONS_TABLE', 'Sessions'))
connections_repo = ConnectionsRepository(os.environ.get('CONNECTIONS_TABLE', 'Connections'))
metrics_publisher = get_metrics_publisher()

# Configuration
STATUS_QUERY_TIMEOUT_MS = int(os.environ.get('STATUS_QUERY_TIMEOUT_MS', '500'))


def lambda_handler(event, context):
    """
    Handle WebSocket session status events.
    
    Supports two invocation modes:
    1. WebSocket MESSAGE event (getSessionStatus action)
    2. EventBridge scheduled event (periodic updates)
    
    Args:
        event: API Gateway WebSocket event or EventBridge event
        context: Lambda context
        
    Returns:
        Response with status code and body
    """
    # Check if this is an EventBridge scheduled event
    if event.get('source') == 'aws.events':
        return handle_periodic_updates(event, context)
    
    # Otherwise, handle as WebSocket MESSAGE event
    connection_id = event['requestContext']['connectionId']
    event_type = event['requestContext'].get('eventType', 'MESSAGE')
    
    logger.info(
        message="Session status handler invoked",
        correlation_id=connection_id,
        operation='lambda_handler',
        event_type=event_type
    )
    
    try:
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
        
        # Validate action
        if action != 'getSessionStatus':
            return error_response(
                status_code=400,
                error_code='INVALID_ACTION',
                message=f'Unsupported action: {action}'
            )
        
        # Handle status query
        return handle_get_session_status(connection_id)
    
    except Exception as e:
        logger.error(
            message=f"Unexpected error in session status handler: {str(e)}",
            correlation_id=connection_id,
            operation='lambda_handler',
            error_code='INTERNAL_ERROR',
            exc_info=True
        )
        metrics_publisher.emit_connection_error('INTERNAL_ERROR')
        return error_response(
            status_code=500,
            error_code='INTERNAL_ERROR',
            message='An unexpected error occurred'
        )


def handle_get_session_status(connection_id: str) -> Dict[str, Any]:
    """
    Handle getSessionStatus request from speaker.
    
    Args:
        connection_id: WebSocket connection ID
        
    Returns:
        API Gateway response with session status
    """
    start_time = time.time()
    
    logger.info(
        message="Getting session status",
        correlation_id=connection_id,
        operation='handle_get_session_status'
    )
    
    try:
        # Get connection to extract sessionId
        connection = connections_repo.get_connection(connection_id)
        
        if not connection:
            logger.warning(
                message="Connection not found",
                correlation_id=connection_id,
                operation='handle_get_session_status',
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
        
        # Validate role is speaker
        if role != 'speaker':
            logger.warning(
                message=f"Unauthorized action getSessionStatus for role {role}",
                correlation_id=f"{session_id}-{connection_id}",
                operation='handle_get_session_status',
                error_code='UNAUTHORIZED_ACTION',
                role=role
            )
            metrics_publisher.emit_connection_error('UNAUTHORIZED_ACTION')
            return error_response(
                status_code=403,
                error_code='UNAUTHORIZED_ACTION',
                message='Action getSessionStatus requires speaker role'
            )
        
        # Get session status
        status = get_session_status(session_id)
        
        if not status:
            logger.warning(
                message=f"Session not found: {session_id}",
                correlation_id=f"{session_id}-{connection_id}",
                operation='handle_get_session_status',
                error_code='SESSION_NOT_FOUND',
                sessionId=session_id
            )
            metrics_publisher.emit_connection_error('SESSION_NOT_FOUND')
            return error_response(
                status_code=404,
                error_code='SESSION_NOT_FOUND',
                message='Session not found'
            )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Check if query exceeded timeout
        if duration_ms > STATUS_QUERY_TIMEOUT_MS:
            logger.warning(
                message=f"Status query exceeded timeout: {duration_ms}ms > {STATUS_QUERY_TIMEOUT_MS}ms",
                correlation_id=f"{session_id}-{connection_id}",
                operation='handle_get_session_status',
                duration_ms=duration_ms,
                timeout_ms=STATUS_QUERY_TIMEOUT_MS
            )
        
        logger.info(
            message="Session status retrieved successfully",
            correlation_id=f"{session_id}-{connection_id}",
            operation='handle_get_session_status',
            duration_ms=duration_ms,
            sessionId=session_id,
            listenerCount=status['listenerCount']
        )
        
        # Emit metrics
        metrics_publisher.emit_status_query_latency(duration_ms, session_id)
        
        # Add updateReason for explicit query
        status['updateReason'] = 'requested'
        
        # Return status response
        return success_response(
            status_code=200,
            body=status
        )
    
    except Exception as e:
        logger.error(
            message=f"Error getting session status: {str(e)}",
            correlation_id=connection_id,
            operation='handle_get_session_status',
            error_code='INTERNAL_ERROR',
            exc_info=True
        )
        metrics_publisher.emit_connection_error('INTERNAL_ERROR')
        return error_response(
            status_code=500,
            error_code='INTERNAL_ERROR',
            message='Failed to get session status'
        )


def get_session_status(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Get comprehensive session status.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Session status dictionary or None if session not found
    """
    # Get session record
    session = sessions_repo.get_session(session_id)
    
    if not session or not session.get('isActive', False):
        return None
    
    # Get all listener connections for session
    listener_connections = connections_repo.get_listener_connections(session_id)
    
    # Aggregate language distribution
    language_distribution = aggregate_language_distribution(listener_connections)
    
    # Calculate session duration
    created_at = session.get('createdAt', 0)
    current_time = int(time.time() * 1000)
    session_duration = int((current_time - created_at) / 1000)  # Convert to seconds
    
    # Get broadcast state
    broadcast_state_data = session.get('broadcastState', {})
    
    # Convert Decimal to float for JSON serialization
    from decimal import Decimal
    broadcast_state = {}
    for key, value in broadcast_state_data.items():
        if isinstance(value, Decimal):
            broadcast_state[key] = float(value)
        else:
            broadcast_state[key] = value
    
    # Build status response
    status = {
        'type': 'sessionStatus',
        'sessionId': session_id,
        'listenerCount': len(listener_connections),
        'languageDistribution': language_distribution,
        'sessionDuration': session_duration,
        'broadcastState': broadcast_state,
        'timestamp': current_time
    }
    
    return status


def aggregate_language_distribution(connections: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Aggregate listener count by target language.
    
    Args:
        connections: List of listener connection records
        
    Returns:
        Dictionary mapping language code to listener count
    """
    distribution = defaultdict(int)
    
    for connection in connections:
        target_language = connection.get('targetLanguage', '')
        if target_language:
            distribution[target_language] += 1
        else:
            # Handle empty language gracefully
            distribution['unknown'] += 1
    
    return dict(distribution)


def handle_periodic_updates(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle periodic status updates triggered by EventBridge.
    
    Queries all active sessions and sends status updates to each speaker.
    
    Args:
        event: EventBridge scheduled event
        context: Lambda context
        
    Returns:
        Response with summary of updates sent
    """
    start_time = time.time()
    
    logger.info(
        message="Processing periodic status updates",
        operation='handle_periodic_updates'
    )
    
    try:
        # Query all active sessions
        # Note: In production, this should use pagination for large numbers of sessions
        active_sessions = get_all_active_sessions()
        
        logger.info(
            message=f"Found {len(active_sessions)} active sessions",
            operation='handle_periodic_updates',
            session_count=len(active_sessions)
        )
        
        updates_sent = 0
        updates_failed = 0
        
        # Send status update to each speaker
        for session in active_sessions:
            session_id = session.get('sessionId', '')
            speaker_connection_id = session.get('speakerConnectionId', '')
            
            if not speaker_connection_id:
                logger.warning(
                    message=f"No speaker connection for session {session_id}",
                    operation='handle_periodic_updates',
                    sessionId=session_id
                )
                continue
            
            # Get session status
            status = get_session_status(session_id)
            
            if not status:
                logger.warning(
                    message=f"Could not get status for session {session_id}",
                    operation='handle_periodic_updates',
                    sessionId=session_id
                )
                updates_failed += 1
                continue
            
            # Add updateReason for periodic update
            status['updateReason'] = 'periodic'
            
            # Send status to speaker
            if send_status_to_speaker(speaker_connection_id, status):
                updates_sent += 1
            else:
                updates_failed += 1
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            message=f"Periodic status updates completed: {updates_sent} sent, {updates_failed} failed",
            operation='handle_periodic_updates',
            duration_ms=duration_ms,
            updates_sent=updates_sent,
            updates_failed=updates_failed
        )
        
        # Emit metric
        metrics_publisher.emit_periodic_status_updates_sent(updates_sent)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'updatesSent': updates_sent,
                'updatesFailed': updates_failed,
                'duration_ms': duration_ms
            })
        }
    
    except Exception as e:
        logger.error(
            message=f"Error processing periodic updates: {str(e)}",
            operation='handle_periodic_updates',
            error_code='INTERNAL_ERROR',
            exc_info=True
        )
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Failed to process periodic updates'
            })
        }


def get_all_active_sessions() -> List[Dict[str, Any]]:
    """
    Get all active sessions.
    
    Note: This uses a scan operation which is not efficient for large numbers of sessions.
    In production, consider using a GSI on isActive or maintaining a separate active sessions index.
    
    Returns:
        List of active session records
    """
    # Use DynamoDB scan to get all sessions
    # Filter for isActive=true
    from shared.data_access.dynamodb_client import DynamoDBClient
    
    client = DynamoDBClient()
    table_name = os.environ.get('SESSIONS_TABLE', 'Sessions')
    
    sessions = client.scan(
        table_name=table_name,
        filter_expression='isActive = :true',
        expression_attribute_values={':true': True}
    )
    
    return sessions


def send_status_to_speaker(connection_id: str, status: Dict[str, Any]) -> bool:
    """
    Send status message to speaker connection.
    
    Args:
        connection_id: Speaker WebSocket connection ID
        status: Status message to send
        
    Returns:
        True if successful, False otherwise
    """
    import boto3
    
    # Get API Gateway endpoint from environment
    api_gateway_endpoint = os.environ.get('API_GATEWAY_ENDPOINT', '')
    
    if not api_gateway_endpoint:
        logger.error(
            message="API_GATEWAY_ENDPOINT not configured",
            correlation_id=connection_id,
            operation='send_status_to_speaker'
        )
        return False
    
    try:
        client = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=api_gateway_endpoint
        )
        
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(status).encode('utf-8')
        )
        
        logger.debug(
            message=f"Sent status update to speaker {connection_id}",
            correlation_id=connection_id,
            operation='send_status_to_speaker'
        )
        
        return True
    
    except client.exceptions.GoneException:
        logger.warning(
            message=f"Speaker connection {connection_id} is gone",
            correlation_id=connection_id,
            operation='send_status_to_speaker'
        )
        # Clean up stale connection
        try:
            connections_repo.delete_connection(connection_id)
        except Exception as e:
            logger.error(
                message=f"Error deleting stale connection: {str(e)}",
                correlation_id=connection_id,
                operation='send_status_to_speaker'
            )
        return False
    
    except Exception as e:
        logger.error(
            message=f"Error sending status to speaker: {str(e)}",
            correlation_id=connection_id,
            operation='send_status_to_speaker',
            exc_info=True
        )
        return False
