"""
Heartbeat Handler for maintaining WebSocket connections.
"""
import json
import logging
import os
import time
import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.data_access.connections_repository import ConnectionsRepository
from shared.config.constants import (
    CONNECTION_REFRESH_MINUTES,
    CONNECTION_WARNING_MINUTES
)
from shared.config.table_names import get_table_name, CONNECTIONS_TABLE_NAME

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize resources outside handler for reuse
connections_repo = ConnectionsRepository(get_table_name('CONNECTIONS_TABLE_NAME', CONNECTIONS_TABLE_NAME))

# API Gateway Management API client (initialized per request with endpoint)
api_gateway_endpoint = os.environ.get('API_GATEWAY_ENDPOINT', '')


def send_message(connection_id: str, message: dict, endpoint_url: str) -> bool:
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
        # Check if it's a GoneException
        if e.__class__.__name__ == 'GoneException':
            logger.warning(f"Connection {connection_id} is gone (disconnected)")
            return False
        
        logger.error(f"Failed to send message to {connection_id}: {e}")
        return False


def lambda_handler(event, context):
    """
    Handle heartbeat messages with connection duration monitoring.
    
    Sends:
    - heartbeatAck: Always sent to acknowledge heartbeat
    - connectionRefreshRequired: At CONNECTION_REFRESH_MINUTES (100 min)
    - connectionWarning: At CONNECTION_WARNING_MINUTES (105 min)
    
    Args:
        event: API Gateway WebSocket heartbeat event
        context: Lambda context
        
    Returns:
        Response with status code
    """
    try:
        # Extract connection ID from request context
        connection_id = event['requestContext']['connectionId']
        
        # Get API Gateway endpoint from request context
        domain_name = event['requestContext']['domainName']
        stage = event['requestContext']['stage']
        endpoint_url = f"https://{domain_name}/{stage}"
        
        logger.info(f"Heartbeat received from connection {connection_id}")
        
        # Get connection details to check duration
        connection = connections_repo.get_connection(connection_id)
        
        current_time = int(time.time() * 1000)  # milliseconds
        
        if connection:
            connected_at = connection.get('connectedAt', current_time)
            duration_minutes = (current_time - connected_at) / (1000 * 60)
            
            # Get thresholds from environment or use defaults
            refresh_threshold = int(os.environ.get(
                'CONNECTION_REFRESH_MINUTES',
                CONNECTION_REFRESH_MINUTES
            ))
            warning_threshold = int(os.environ.get(
                'CONNECTION_WARNING_MINUTES',
                CONNECTION_WARNING_MINUTES
            ))
            
            logger.info(
                f"Connection {connection_id} duration: {duration_minutes:.1f} minutes "
                f"(refresh at {refresh_threshold}, warning at {warning_threshold})"
            )
            
            # Check if connection refresh is needed (for long sessions)
            # Send refresh message only once when threshold is crossed
            if refresh_threshold <= duration_minutes < refresh_threshold + 1:
                session_id = connection.get('sessionId')
                role = connection.get('role')
                target_language = connection.get('targetLanguage')
                
                refresh_message = {
                    'type': 'connectionRefreshRequired',
                    'sessionId': session_id,
                    'role': role,
                    'message': 'Please establish new connection to continue session',
                    'timestamp': current_time
                }
                
                if target_language:
                    refresh_message['targetLanguage'] = target_language
                
                send_message(connection_id, refresh_message, endpoint_url)
                logger.info(
                    f"Sent connectionRefreshRequired to {connection_id} "
                    f"(duration: {duration_minutes:.1f} min)"
                )
            
            # Check if connection is approaching timeout
            elif duration_minutes >= warning_threshold:
                max_duration = int(os.environ.get('CONNECTION_MAX_DURATION_HOURS', 2)) * 60
                remaining_minutes = max_duration - duration_minutes
                
                warning_message = {
                    'type': 'connectionWarning',
                    'message': f'Connection will expire in {remaining_minutes:.0f} minutes',
                    'remainingMinutes': remaining_minutes,
                    'timestamp': current_time
                }
                
                send_message(connection_id, warning_message, endpoint_url)
                logger.info(
                    f"Sent connectionWarning to {connection_id} "
                    f"(remaining: {remaining_minutes:.0f} min)"
                )
        
        # Always send heartbeat acknowledgment
        ack_message = {
            'type': 'heartbeatAck',
            'timestamp': current_time
        }
        
        success = send_message(connection_id, ack_message, endpoint_url)
        
        if success:
            return {'statusCode': 200}
        else:
            # Connection is gone, return 410
            return {'statusCode': 410}
    
    except KeyError as e:
        logger.error(f"Missing required field in event: {e}")
        return {'statusCode': 400, 'body': json.dumps({'error': 'Invalid event structure'})}
    
    except Exception as e:
        logger.error(f"Unexpected error in heartbeat handler: {e}", exc_info=True)
        return {'statusCode': 500, 'body': json.dumps({'error': 'Internal server error'})}
