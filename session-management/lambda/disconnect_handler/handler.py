"""
WebSocket Disconnect Handler for $disconnect events.
Handles cleanup when connections close.
"""
import json
import logging
import os
import time
import boto3

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.data_access.connections_repository import ConnectionsRepository
from shared.data_access.sessions_repository import SessionsRepository
from shared.config.table_names import get_table_name, SESSIONS_TABLE_NAME, CONNECTIONS_TABLE_NAME

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize resources outside handler for reuse
connections_repo = ConnectionsRepository(get_table_name('CONNECTIONS_TABLE_NAME', CONNECTIONS_TABLE_NAME))
sessions_repo = SessionsRepository(get_table_name('SESSIONS_TABLE_NAME', SESSIONS_TABLE_NAME))


def send_message_to_connection(connection_id: str, message: dict, endpoint_url: str) -> bool:
    """
    Send message to WebSocket connection via API Gateway Management API.
    
    Args:
        connection_id: WebSocket connection ID
        message: Message dictionary to send
        endpoint_url: API Gateway endpoint URL
        
    Returns:
        True if message sent successfully, False otherwise
    """
    try:
        client = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=endpoint_url
        )
        
        # Convert message to JSON, handling Decimal types from DynamoDB
        message_json = json.dumps(message, default=str)
        
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=message_json.encode('utf-8')
        )
        
        logger.info(f"Sent message type '{message.get('type')}' to connection {connection_id}")
        return True
        
    except Exception as e:
        # Check if it's a GoneException (connection already closed)
        if e.__class__.__name__ == 'GoneException':
            logger.warning(f"Connection {connection_id} is gone (already disconnected)")
            return False
        
        logger.error(f"Failed to send message to {connection_id}: {e}")
        return False


def handle_listener_disconnect(session_id: str, connection_id: str) -> None:
    """
    Handle listener disconnection - decrement listener count.
    
    Args:
        session_id: Session identifier
        connection_id: Listener connection ID
    """
    try:
        # Atomically decrement listener count with floor of 0
        new_count = sessions_repo.decrement_listener_count(session_id)
        
        logger.info(
            f"Listener {connection_id} disconnected from session {session_id} - "
            f"New listener count: {new_count}"
        )
        
    except Exception as e:
        logger.error(f"Error handling listener disconnect for session {session_id}: {e}", exc_info=True)
        # Don't raise - we want disconnect to succeed even if count update fails


def handle_speaker_disconnect(session_id: str, connection_id: str, endpoint_url: str) -> None:
    """
    Handle speaker disconnection - end session and notify all listeners.
    
    Args:
        session_id: Session identifier
        connection_id: Speaker connection ID
        endpoint_url: API Gateway endpoint URL
    """
    try:
        # Get session details for logging duration
        session = sessions_repo.get_session(session_id)
        
        # Mark session as inactive
        sessions_repo.mark_session_inactive(session_id)
        logger.info(f"Marked session {session_id} as inactive")
        
        # Query all listener connections for the session using GSI
        listener_connections = connections_repo.get_listener_connections(session_id)
        logger.info(f"Found {len(listener_connections)} listeners for session {session_id}")
        
        # Send sessionEnded message to all listeners
        current_time = int(time.time() * 1000)
        session_ended_message = {
            'type': 'sessionEnded',
            'sessionId': session_id,
            'message': 'Speaker has ended the session',
            'timestamp': current_time
        }
        
        for listener in listener_connections:
            listener_conn_id = listener['connectionId']
            send_message_to_connection(listener_conn_id, session_ended_message, endpoint_url)
        
        # Delete all connection records for the session
        deleted_count = connections_repo.delete_all_session_connections(session_id)
        logger.info(f"Deleted {deleted_count} connection records for session {session_id}")
        
        # Log session termination with duration
        if session:
            created_at = session.get('createdAt', 0)
            duration_ms = current_time - created_at
            duration_minutes = duration_ms / (1000 * 60)
            
            logger.info(
                f"Session {session_id} terminated - "
                f"Duration: {duration_minutes:.1f} minutes, "
                f"Listeners notified: {len(listener_connections)}"
            )
        else:
            logger.info(f"Session {session_id} terminated")
            
    except Exception as e:
        logger.error(f"Error handling speaker disconnect for session {session_id}: {e}", exc_info=True)
        raise


def lambda_handler(event, context):
    """
    Handle WebSocket $disconnect event.
    
    Determines role (speaker or listener) and performs appropriate cleanup:
    - Speaker: Mark session inactive, notify all listeners, delete all connections
    - Listener: Delete connection record, decrement listener count
    
    Args:
        event: API Gateway WebSocket $disconnect event
        context: Lambda context
        
    Returns:
        Response with status code (always 200 for idempotent operations)
    """
    try:
        # Extract connection ID from request context
        connection_id = event['requestContext']['connectionId']
        
        # Get API Gateway endpoint from request context
        domain_name = event['requestContext']['domainName']
        stage = event['requestContext']['stage']
        endpoint_url = f"https://{domain_name}/{stage}"
        
        logger.info(f"Disconnect event for connection {connection_id}")
        
        # Get connection details to determine role
        connection = connections_repo.get_connection(connection_id)
        
        if not connection:
            logger.warning(f"Connection {connection_id} not found in database (already cleaned up)")
            return {'statusCode': 200}  # Idempotent - safe to retry
        
        session_id = connection['sessionId']
        role = connection['role']
        
        logger.info(f"Processing disconnect for {role} in session {session_id}")
        
        # Delete connection record first (idempotent)
        connections_repo.delete_connection(connection_id)
        
        if role == 'speaker':
            # Speaker disconnected - end session and notify listeners
            handle_speaker_disconnect(session_id, connection_id, endpoint_url)
        else:
            # Listener disconnected - decrement count
            handle_listener_disconnect(session_id, connection_id)
        
        return {'statusCode': 200}
        
    except KeyError as e:
        logger.error(f"Missing required field in event: {e}")
        return {'statusCode': 200}  # Return success to avoid retries
        
    except Exception as e:
        logger.error(f"Unexpected error in disconnect handler: {e}", exc_info=True)
        return {'statusCode': 200}  # Return success to avoid retries
