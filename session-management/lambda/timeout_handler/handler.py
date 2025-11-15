"""
Timeout Handler for detecting and closing idle WebSocket connections.

This Lambda is triggered periodically by EventBridge (every 60 seconds) to:
1. Query all active connections
2. Check lastActivityTime for each connection
3. Close connections idle for more than CONNECTION_IDLE_TIMEOUT_SECONDS
4. Send connectionTimeout message before closing
5. Trigger disconnect handler for cleanup
"""
import json
import logging
import os
import time
import boto3
from botocore.exceptions import ClientError
from typing import List, Dict, Any

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.data_access.connections_repository import ConnectionsRepository
from shared.utils.structured_logger import get_structured_logger
from shared.utils.metrics import MetricsPublisher

# Initialize logger
base_logger = logging.getLogger()
base_logger.setLevel(logging.INFO)
logger = get_structured_logger('TimeoutHandler')

# Initialize resources outside handler for reuse
connections_table = os.environ.get('CONNECTIONS_TABLE', 'Connections')
connections_repo = ConnectionsRepository(connections_table)

# Configuration
CONNECTION_IDLE_TIMEOUT_SECONDS = int(os.environ.get('CONNECTION_IDLE_TIMEOUT_SECONDS', 120))
API_GATEWAY_ENDPOINT = os.environ.get('API_GATEWAY_ENDPOINT', '')

# Initialize metrics publisher
metrics_publisher = MetricsPublisher(namespace='WebSocketAudioIntegration')


def send_timeout_message(connection_id: str, endpoint_url: str) -> bool:
    """
    Send connectionTimeout message to WebSocket connection.
    
    Args:
        connection_id: WebSocket connection ID
        endpoint_url: API Gateway endpoint URL
        
    Returns:
        True if message sent successfully, False otherwise
    """
    try:
        client = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=endpoint_url
        )
        
        message = {
            'type': 'connectionTimeout',
            'message': 'Connection closed due to inactivity',
            'idleSeconds': CONNECTION_IDLE_TIMEOUT_SECONDS,
            'timestamp': int(time.time() * 1000)
        }
        
        message_json = json.dumps(message)
        
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=message_json.encode('utf-8')
        )
        
        logger.info(
            message=f"Sent connectionTimeout message to {connection_id}",
            connection_id=connection_id
        )
        return True
        
    except Exception as e:
        # Connection may already be gone
        if e.__class__.__name__ == 'GoneException':
            logger.info(
                message=f"Connection {connection_id} already gone",
                connection_id=connection_id
            )
        else:
            logger.warning(
                message=f"Failed to send timeout message to {connection_id}: {e}",
                connection_id=connection_id,
                error=str(e)
            )
        return False


def close_connection(connection_id: str, endpoint_url: str) -> bool:
    """
    Close WebSocket connection via API Gateway Management API.
    
    Args:
        connection_id: WebSocket connection ID
        endpoint_url: API Gateway endpoint URL
        
    Returns:
        True if connection closed successfully, False otherwise
    """
    try:
        client = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=endpoint_url
        )
        
        client.delete_connection(ConnectionId=connection_id)
        
        logger.info(
            message=f"Closed connection {connection_id}",
            connection_id=connection_id
        )
        return True
        
    except Exception as e:
        if e.__class__.__name__ == 'GoneException':
            logger.info(
                message=f"Connection {connection_id} already closed",
                connection_id=connection_id
            )
            return True  # Already closed, consider it success
        else:
            logger.error(
                message=f"Failed to close connection {connection_id}: {e}",
                connection_id=connection_id,
                error=str(e)
            )
            return False


def trigger_disconnect_handler(connection_id: str, session_id: str, role: str) -> None:
    """
    Trigger disconnect handler Lambda for cleanup.
    
    Args:
        connection_id: WebSocket connection ID
        session_id: Session ID
        role: Connection role (speaker or listener)
    """
    try:
        lambda_client = boto3.client('lambda')
        disconnect_function = os.environ.get('DISCONNECT_HANDLER_FUNCTION', 'DisconnectHandler')
        
        # Create event similar to API Gateway disconnect event
        event = {
            'requestContext': {
                'connectionId': connection_id,
                'eventType': 'DISCONNECT',
                'disconnectReason': 'IDLE_TIMEOUT'
            },
            'sessionId': session_id,
            'role': role
        }
        
        lambda_client.invoke(
            FunctionName=disconnect_function,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(event)
        )
        
        logger.info(
            message=f"Triggered disconnect handler for {connection_id}",
            connection_id=connection_id,
            session_id=session_id,
            role=role
        )
        
    except Exception as e:
        logger.error(
            message=f"Failed to trigger disconnect handler for {connection_id}: {e}",
            connection_id=connection_id,
            error=str(e)
        )


def check_and_close_idle_connections(endpoint_url: str) -> Dict[str, int]:
    """
    Check all connections and close idle ones.
    
    Args:
        endpoint_url: API Gateway endpoint URL
        
    Returns:
        Dictionary with counts of checked, idle, and closed connections
    """
    current_time = int(time.time() * 1000)  # milliseconds
    timeout_threshold = current_time - (CONNECTION_IDLE_TIMEOUT_SECONDS * 1000)
    
    stats = {
        'checked': 0,
        'idle': 0,
        'closed': 0,
        'speaker_timeouts': 0,
        'listener_timeouts': 0
    }
    
    try:
        # Get all active connections
        # Note: In production, this should use pagination for large numbers of connections
        connections = connections_repo.scan_all_connections()
        
        stats['checked'] = len(connections)
        
        logger.info(
            message=f"Checking {stats['checked']} connections for timeouts",
            timeout_threshold_ms=timeout_threshold,
            idle_timeout_seconds=CONNECTION_IDLE_TIMEOUT_SECONDS
        )
        
        for connection in connections:
            connection_id = connection.get('connectionId')
            last_activity = connection.get('lastActivityTime', connection.get('connectedAt', current_time))
            session_id = connection.get('sessionId', '')
            role = connection.get('role', 'unknown')
            
            # Check if connection is idle
            if last_activity < timeout_threshold:
                stats['idle'] += 1
                idle_duration_seconds = (current_time - last_activity) / 1000
                
                logger.info(
                    message=f"Connection {connection_id} is idle",
                    connection_id=connection_id,
                    session_id=session_id,
                    role=role,
                    idle_duration_seconds=idle_duration_seconds
                )
                
                # Send timeout message (best effort)
                send_timeout_message(connection_id, endpoint_url)
                
                # Close connection
                if close_connection(connection_id, endpoint_url):
                    stats['closed'] += 1
                    
                    # Track by role
                    if role == 'speaker':
                        stats['speaker_timeouts'] += 1
                    elif role == 'listener':
                        stats['listener_timeouts'] += 1
                    
                    # Trigger disconnect handler for cleanup
                    trigger_disconnect_handler(connection_id, session_id, role)
                    
                    # Emit CloudWatch metric
                    metrics_publisher.emit_metric(
                        metric_name='ConnectionTimeout',
                        value=1,
                        unit='Count',
                        dimensions={
                            'Role': role,
                            'Reason': 'IDLE_TIMEOUT'
                        }
                    )
        
        logger.info(
            message="Timeout check complete",
            **stats
        )
        
        return stats
        
    except Exception as e:
        logger.error(
            message=f"Error checking connections for timeouts: {e}",
            error=str(e)
        )
        raise


def lambda_handler(event, context):
    """
    Handle periodic timeout check triggered by EventBridge.
    
    Args:
        event: EventBridge scheduled event
        context: Lambda context
        
    Returns:
        Response with status code and statistics
    """
    try:
        logger.info(
            message="Starting connection timeout check",
            idle_timeout_seconds=CONNECTION_IDLE_TIMEOUT_SECONDS
        )
        
        # Get API Gateway endpoint from environment
        endpoint_url = API_GATEWAY_ENDPOINT
        
        if not endpoint_url:
            logger.error(message="API_GATEWAY_ENDPOINT not configured")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'API Gateway endpoint not configured'})
            }
        
        # Check and close idle connections
        stats = check_and_close_idle_connections(endpoint_url)
        
        # Emit summary metrics
        metrics_publisher.emit_metric(
            metric_name='ConnectionsChecked',
            value=stats['checked'],
            unit='Count'
        )
        
        metrics_publisher.emit_metric(
            metric_name='IdleConnectionsDetected',
            value=stats['idle'],
            unit='Count'
        )
        
        metrics_publisher.emit_metric(
            metric_name='ConnectionsClosed',
            value=stats['closed'],
            unit='Count'
        )
        
        logger.info(
            message="Timeout check completed successfully",
            **stats
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Timeout check completed',
                'statistics': stats
            })
        }
        
    except Exception as e:
        logger.error(
            message=f"Unexpected error in timeout handler: {e}",
            error=str(e)
        )
        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }
