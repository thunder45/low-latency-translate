"""
Connection Refresh Handler Lambda.

Handles seamless connection refresh for sessions longer than 2 hours.
Supports both speaker and listener connection refresh with identity validation.
"""

import json
import logging
import os
import time
from typing import Dict, Any

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
sessions_table = dynamodb.Table(os.environ['SESSIONS_TABLE_NAME'])
connections_table = dynamodb.Table(os.environ['CONNECTIONS_TABLE_NAME'])

# Get API Gateway endpoint for sending messages
api_gateway_endpoint = os.environ['API_GATEWAY_ENDPOINT']
api_gateway = boto3.client(
    'apigatewaymanagementapi',
    endpoint_url=api_gateway_endpoint
)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle connection refresh for long-running sessions.
    
    Args:
        event: Lambda event with requestContext and queryStringParameters
        context: Lambda context
        
    Returns:
        Response dict with statusCode
    """
    connection_id = event['requestContext']['connectionId']
    query_params = event.get('queryStringParameters', {})
    
    try:
        session_id = query_params.get('sessionId')
        role = query_params.get('role')
        
        if not session_id:
            return error_response(400, 'MISSING_PARAMETER', 'sessionId is required')
        
        if not role or role not in ['speaker', 'listener']:
            return error_response(400, 'INVALID_PARAMETER', 'role must be speaker or listener')
        
        # Validate session exists and is active
        session = get_session(session_id)
        if not session or not session.get('isActive'):
            return error_response(404, 'SESSION_NOT_FOUND', 'Session not found or inactive')
        
        if role == 'speaker':
            return handle_speaker_refresh(event, connection_id, session_id, session)
        else:  # listener
            return handle_listener_refresh(event, connection_id, session_id, session, query_params)
    
    except Exception as e:
        logger.error(
            f"Connection refresh error: {str(e)}",
            extra={
                'connection_id': connection_id,
                'session_id': query_params.get('sessionId'),
                'role': query_params.get('role')
            },
            exc_info=True
        )
        return error_response(500, 'INTERNAL_ERROR', 'Connection refresh failed')


def handle_speaker_refresh(
    event: Dict[str, Any],
    connection_id: str,
    session_id: str,
    session: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Handle speaker connection refresh with identity validation.
    
    Args:
        event: Lambda event
        connection_id: New connection ID
        session_id: Session ID
        session: Session record
        
    Returns:
        Response dict
    """
    # Validate speaker identity matches
    authorizer_context = event['requestContext'].get('authorizer', {})
    user_id = authorizer_context.get('userId')
    
    if not user_id:
        return error_response(401, 'UNAUTHORIZED', 'Speaker authentication required')
    
    if user_id != session.get('speakerUserId'):
        logger.warning(
            f"Speaker identity mismatch for session {session_id}",
            extra={
                'expected_user_id': session.get('speakerUserId'),
                'provided_user_id': user_id,
                'session_id': session_id
            }
        )
        return error_response(403, 'FORBIDDEN', 'Speaker identity mismatch')
    
    # Get old connection ID for logging
    old_connection_id = session.get('speakerConnectionId')
    
    # Atomically update speaker connection ID
    try:
        sessions_table.update_item(
            Key={'sessionId': session_id},
            UpdateExpression='SET speakerConnectionId = :new_conn',
            ConditionExpression='attribute_exists(sessionId) AND isActive = :true',
            ExpressionAttributeValues={
                ':new_conn': connection_id,
                ':true': True
            }
        )
        
        logger.info(
            f"Speaker connection refreshed for session {session_id}",
            extra={
                'session_id': session_id,
                'old_connection_id': old_connection_id,
                'new_connection_id': connection_id,
                'user_id': user_id
            }
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return error_response(404, 'SESSION_NOT_FOUND', 'Session no longer active')
        raise
    
    # Send completion message to new connection
    send_message(connection_id, {
        'type': 'connectionRefreshComplete',
        'sessionId': session_id,
        'role': 'speaker',
        'timestamp': int(time.time() * 1000)
    })
    
    return {'statusCode': 200}


def handle_listener_refresh(
    event: Dict[str, Any],
    connection_id: str,
    session_id: str,
    session: Dict[str, Any],
    query_params: Dict[str, str]
) -> Dict[str, Any]:
    """
    Handle listener connection refresh with count management.
    
    Args:
        event: Lambda event
        connection_id: New connection ID
        session_id: Session ID
        session: Session record
        query_params: Query string parameters
        
    Returns:
        Response dict
    """
    target_language = query_params.get('targetLanguage')
    
    if not target_language:
        return error_response(400, 'MISSING_PARAMETER', 'targetLanguage is required for listener')
    
    # Get IP address for connection record
    source_ip = event['requestContext'].get('identity', {}).get('sourceIp', 'unknown')
    
    # Create new connection record
    connection_record = {
        'connectionId': connection_id,
        'sessionId': session_id,
        'targetLanguage': target_language,
        'role': 'listener',
        'connectedAt': int(time.time() * 1000),
        'ttl': int(time.time()) + int(os.environ.get('SESSION_MAX_DURATION_HOURS', '2')) * 3600 + 3600,
        'ipAddress': source_ip
    }
    
    try:
        # Create connection record
        connections_table.put_item(Item=connection_record)
        
        # Atomically increment listener count
        sessions_table.update_item(
            Key={'sessionId': session_id},
            UpdateExpression='ADD listenerCount :inc',
            ConditionExpression='attribute_exists(sessionId) AND isActive = :true',
            ExpressionAttributeValues={
                ':inc': 1,
                ':true': True
            }
        )
        
        logger.info(
            f"Listener connection refreshed for session {session_id}",
            extra={
                'session_id': session_id,
                'new_connection_id': connection_id,
                'target_language': target_language
            }
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return error_response(404, 'SESSION_NOT_FOUND', 'Session no longer active')
        raise
    
    # Send completion message
    send_message(connection_id, {
        'type': 'connectionRefreshComplete',
        'sessionId': session_id,
        'targetLanguage': target_language,
        'role': 'listener',
        'sourceLanguage': session.get('sourceLanguage'),
        'timestamp': int(time.time() * 1000)
    })
    
    return {'statusCode': 200}


def get_session(session_id: str) -> Dict[str, Any]:
    """
    Get session record from DynamoDB.
    
    Args:
        session_id: Session ID
        
    Returns:
        Session record or None if not found
    """
    try:
        response = sessions_table.get_item(Key={'sessionId': session_id})
        return response.get('Item')
    except ClientError as e:
        logger.error(f"Error getting session {session_id}: {e}")
        return None


def send_message(connection_id: str, message: Dict[str, Any]) -> None:
    """
    Send message to WebSocket connection.
    
    Args:
        connection_id: Connection ID
        message: Message dict to send
    """
    try:
        api_gateway.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message)
        )
    except api_gateway.exceptions.GoneException:
        logger.warning(f"Connection {connection_id} gone during message send")
    except Exception as e:
        logger.error(f"Error sending message to {connection_id}: {e}")


def error_response(status_code: int, error_code: str, message: str) -> Dict[str, Any]:
    """
    Create error response.
    
    Args:
        status_code: HTTP status code
        error_code: Error code
        message: Error message
        
    Returns:
        Response dict
    """
    return {
        'statusCode': status_code,
        'body': json.dumps({
            'type': 'error',
            'code': error_code,
            'message': message,
            'timestamp': int(time.time() * 1000)
        })
    }
