"""
HTTP API Lambda handler for session CRUD operations.

This handler implements REST API endpoints for session management:
- POST /sessions - Create new session
- GET /sessions/{sessionId} - Retrieve session details
- PATCH /sessions/{sessionId} - Update session
- DELETE /sessions/{sessionId} - Delete session
- GET /health - Health check
"""
import json
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
apigateway_management = boto3.client('apigatewaymanagementapi')
kvs_client = boto3.client('kinesisvideo')
eventbridge = boto3.client('events')

# Environment variables
ENV = os.environ.get('ENV', 'dev')
SESSIONS_TABLE_NAME = os.environ['SESSIONS_TABLE']
CONNECTIONS_TABLE_NAME = os.environ['CONNECTIONS_TABLE']
USER_POOL_ID = os.environ.get('USER_POOL_ID', '')
REGION = os.environ.get('REGION', 'us-east-1')

# DynamoDB tables
sessions_table = dynamodb.Table(SESSIONS_TABLE_NAME)
connections_table = dynamodb.Table(CONNECTIONS_TABLE_NAME)

# Supported languages (AWS Translate + Polly intersection)
SUPPORTED_LANGUAGES = [
    'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh',
    'ar', 'hi', 'nl', 'pl', 'tr', 'sv', 'da', 'no', 'fi'
]

# Quality tiers
QUALITY_TIERS = ['standard', 'premium']


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    HTTP API Lambda handler for session CRUD operations.
    
    Routes:
    - POST /sessions -> create_session
    - GET /sessions/{sessionId} -> get_session
    - PATCH /sessions/{sessionId} -> update_session
    - DELETE /sessions/{sessionId} -> delete_session
    - GET /health -> health_check
    """
    try:
        # Extract request details
        http_method = event['requestContext']['http']['method']
        path = event['requestContext']['http']['path']
        
        logger.info(
            f'HTTP request received',
            extra={
                'method': http_method,
                'path': path,
                'request_id': event['requestContext']['requestId'],
            }
        )
        
        # Extract user ID from JWT claims (if authenticated)
        user_id = None
        if 'authorizer' in event['requestContext'] and 'jwt' in event['requestContext']['authorizer']:
            user_id = event['requestContext']['authorizer']['jwt']['claims'].get('sub')
        
        # Route to appropriate handler
        if http_method == 'POST' and path == '/sessions':
            return create_session(event, user_id)
        elif http_method == 'GET' and '/sessions/' in path:
            session_id = path.split('/')[-1]
            return get_session(session_id)
        elif http_method == 'PATCH' and '/sessions/' in path:
            session_id = path.split('/')[-1]
            return update_session(event, session_id, user_id)
        elif http_method == 'DELETE' and '/sessions/' in path:
            session_id = path.split('/')[-1]
            return delete_session(session_id, user_id)
        elif http_method == 'GET' and path == '/health':
            return health_check()
        else:
            return error_response(404, 'Not found')
            
    except Exception as e:
        logger.error(f'Unhandled error: {str(e)}', exc_info=True)
        return error_response(500, 'Internal server error')


def create_session(event: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    """Create a new session."""
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        source_language = body.get('sourceLanguage')
        quality_tier = body.get('qualityTier', 'standard')
        
        # Validate inputs
        if not source_language:
            return error_response(400, 'sourceLanguage is required')
        
        if source_language not in SUPPORTED_LANGUAGES:
            return error_response(
                400,
                f'Invalid sourceLanguage. Supported: {", ".join(SUPPORTED_LANGUAGES)}'
            )
        
        if quality_tier not in QUALITY_TIERS:
            return error_response(
                400,
                f'Invalid qualityTier. Supported: {", ".join(QUALITY_TIERS)}'
            )
        
        if not user_id:
            return error_response(401, 'Authentication required')
        
        # Generate unique session ID
        session_id = generate_session_id()
        
        # Create KVS Signaling Channel for WebRTC
        channel_name = f'session-{session_id}'
        
        try:
            kvs_response = kvs_client.create_signaling_channel(
                ChannelName=channel_name,
                ChannelType='SINGLE_MASTER',  # 1 speaker (master), many listeners (viewers)
                SingleMasterConfiguration={
                    'MessageTtlSeconds': 60  # TTL for signaling messages
                },
                Tags=[
                    {'Key': 'SessionId', 'Value': session_id},
                    {'Key': 'CreatedBy', 'Value': user_id},
                    {'Key': 'SourceLanguage', 'Value': source_language},
                ]
            )
            
            channel_arn = kvs_response['ChannelARN']
            
            logger.info(
                f'KVS signaling channel created',
                extra={
                    'session_id': session_id,
                    'channel_name': channel_name,
                    'channel_arn': channel_arn
                }
            )
            
            # Get signaling channel endpoints
            endpoints_response = kvs_client.get_signaling_channel_endpoint(
                ChannelARN=channel_arn,
                SingleMasterChannelEndpointConfiguration={
                    'Protocols': ['WSS', 'HTTPS'],
                    'Role': 'MASTER'
                }
            )
            
            signaling_endpoints = {
                endpoint['Protocol']: endpoint['ResourceEndpoint']
                for endpoint in endpoints_response['ResourceEndpointList']
            }
            
        except ClientError as e:
            logger.error(f'Failed to create KVS channel: {str(e)}')
            return error_response(500, 'Failed to create streaming channel')
        
        # Create session record with KVS channel info
        now = int(datetime.utcnow().timestamp() * 1000)
        ttl = int((datetime.utcnow() + timedelta(hours=24)).timestamp())
        
        session_data = {
            'sessionId': session_id,
            'speakerId': user_id,
            'sourceLanguage': source_language,
            'qualityTier': quality_tier,
            'status': 'active',
            'listenerCount': 0,
            'createdAt': now,
            'updatedAt': now,
            'expiresAt': ttl,
            # KVS WebRTC fields
            'kvsChannelArn': channel_arn,
            'kvsChannelName': channel_name,
            'kvsSignalingEndpoints': signaling_endpoints,
        }
        
        sessions_table.put_item(Item=session_data)
        
        logger.info(
            f'Session created successfully',
            extra={
                'session_id': session_id,
                'speaker_id': user_id,
                'source_language': source_language,
            }
        )
        
        # Emit CloudWatch metric
        emit_metric('SessionCreationCount', 1, {'SourceLanguage': source_language})
        
        # Emit EventBridge event to trigger KVS stream consumer
        try:
            event_detail = {
                'sessionId': session_id,
                'status': 'ACTIVE',
                'channelArn': channel_arn,
                'sourceLanguage': source_language,
                'targetLanguages': [],  # Will be populated as listeners join
                'qualityTier': quality_tier,
                'speakerId': user_id,
                'timestamp': now,
            }
            
            eventbridge.put_events(
                Entries=[{
                    'Source': 'session-management',
                    'DetailType': 'Session Status Change',
                    'Detail': json.dumps(event_detail),
                    'EventBusName': 'default',
                }]
            )
            
            logger.info(
                f'EventBridge event emitted for session creation',
                extra={
                    'session_id': session_id,
                    'event_detail': event_detail,
                }
            )
        except Exception as e:
            logger.error(
                f'Failed to emit EventBridge event: {str(e)}',
                extra={'session_id': session_id}
            )
            # Don't fail the request if EventBridge emission fails
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps(session_data),
        }
        
    except ValueError as e:
        return error_response(400, str(e))
    except ClientError as e:
        logger.error(f'DynamoDB error: {str(e)}')
        return error_response(500, 'Failed to create session')


def get_session(session_id: str) -> Dict[str, Any]:
    """Retrieve session details."""
    try:
        response = sessions_table.get_item(Key={'sessionId': session_id})
        
        if 'Item' not in response:
            return error_response(404, 'Session not found')
        
        session = response['Item']
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps(session, default=str),
        }
        
    except ClientError as e:
        logger.error(f'DynamoDB error: {str(e)}')
        return error_response(500, 'Failed to retrieve session')


def update_session(
    event: Dict[str, Any],
    session_id: str,
    user_id: Optional[str]
) -> Dict[str, Any]:
    """Update session details."""
    try:
        if not user_id:
            return error_response(401, 'Authentication required')
        
        # Get existing session
        response = sessions_table.get_item(Key={'sessionId': session_id})
        
        if 'Item' not in response:
            return error_response(404, 'Session not found')
        
        session = response['Item']
        
        # Verify ownership
        if session['speakerId'] != user_id:
            return error_response(403, 'Not authorized to update this session')
        
        # Parse updates
        body = json.loads(event.get('body', '{}'))
        update_expression_parts = []
        expression_attribute_values = {}
        expression_attribute_names = {}
        
        if 'status' in body:
            if body['status'] not in ['active', 'paused', 'ended']:
                return error_response(400, 'Invalid status value')
            update_expression_parts.append('#status = :status')
            expression_attribute_names['#status'] = 'status'
            expression_attribute_values[':status'] = body['status']
        
        if 'sourceLanguage' in body:
            if body['sourceLanguage'] not in SUPPORTED_LANGUAGES:
                return error_response(400, 'Invalid sourceLanguage')
            update_expression_parts.append('sourceLanguage = :sourceLanguage')
            expression_attribute_values[':sourceLanguage'] = body['sourceLanguage']
        
        if 'qualityTier' in body:
            if body['qualityTier'] not in QUALITY_TIERS:
                return error_response(400, 'Invalid qualityTier')
            update_expression_parts.append('qualityTier = :qualityTier')
            expression_attribute_values[':qualityTier'] = body['qualityTier']
        
        if not update_expression_parts:
            return error_response(400, 'No valid updates provided')
        
        # Add updatedAt timestamp
        update_expression_parts.append('updatedAt = :updatedAt')
        expression_attribute_values[':updatedAt'] = int(datetime.utcnow().timestamp() * 1000)
        
        # Update session
        update_expression = 'SET ' + ', '.join(update_expression_parts)
        
        update_params = {
            'Key': {'sessionId': session_id},
            'UpdateExpression': update_expression,
            'ExpressionAttributeValues': expression_attribute_values,
            'ReturnValues': 'ALL_NEW',
        }
        
        if expression_attribute_names:
            update_params['ExpressionAttributeNames'] = expression_attribute_names
        
        response = sessions_table.update_item(**update_params)
        updated_session = response['Attributes']
        
        logger.info(
            f'Session updated successfully',
            extra={
                'session_id': session_id,
                'updates': list(body.keys()),
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps(updated_session, default=str),
        }
        
    except ValueError as e:
        return error_response(400, str(e))
    except ClientError as e:
        logger.error(f'DynamoDB error: {str(e)}')
        return error_response(500, 'Failed to update session')


def delete_session(session_id: str, user_id: Optional[str]) -> Dict[str, Any]:
    """Delete (end) a session."""
    try:
        if not user_id:
            return error_response(401, 'Authentication required')
        
        # Get existing session
        response = sessions_table.get_item(Key={'sessionId': session_id})
        
        if 'Item' not in response:
            return error_response(404, 'Session not found')
        
        session = response['Item']
        
        # Verify ownership
        if session['speakerId'] != user_id:
            return error_response(403, 'Not authorized to delete this session')
        
        # Delete KVS signaling channel
        channel_arn = session.get('kvsChannelArn')
        if channel_arn:
            try:
                kvs_client.delete_signaling_channel(ChannelARN=channel_arn)
                logger.info(
                    f'KVS signaling channel deleted',
                    extra={
                        'session_id': session_id,
                        'channel_arn': channel_arn
                    }
                )
            except ClientError as e:
                logger.warning(
                    f'Failed to delete KVS channel: {str(e)}',
                    extra={'session_id': session_id}
                )
                # Continue with session deletion even if KVS deletion fails
        
        # Mark session as ended (soft delete)
        sessions_table.update_item(
            Key={'sessionId': session_id},
            UpdateExpression='SET #status = :status, updatedAt = :updatedAt',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'ended',
                ':updatedAt': int(datetime.utcnow().timestamp() * 1000),
            },
        )
        
        # Disconnect all WebSocket connections for this session
        disconnect_session_connections(session_id)
        
        logger.info(
            f'Session deleted successfully',
            extra={'session_id': session_id}
        )
        
        # Emit CloudWatch metric
        emit_metric('SessionDeletionCount', 1)
        
        # Emit EventBridge event to signal session end
        try:
            event_detail = {
                'sessionId': session_id,
                'status': 'ENDED',
                'channelArn': channel_arn,
                'sourceLanguage': session.get('sourceLanguage', ''),
                'timestamp': int(datetime.utcnow().timestamp() * 1000),
            }
            
            eventbridge.put_events(
                Entries=[{
                    'Source': 'session-management',
                    'DetailType': 'Session Status Change',
                    'Detail': json.dumps(event_detail),
                    'EventBusName': 'default',
                }]
            )
            
            logger.info(
                f'EventBridge event emitted for session deletion',
                extra={
                    'session_id': session_id,
                    'event_detail': event_detail,
                }
            )
        except Exception as e:
            logger.error(
                f'Failed to emit EventBridge event: {str(e)}',
                extra={'session_id': session_id}
            )
            # Don't fail the request if EventBridge emission fails
        
        return {
            'statusCode': 204,
            'headers': {
                'Access-Control-Allow-Origin': '*',
            },
        }
        
    except ClientError as e:
        logger.error(f'DynamoDB error: {str(e)}')
        return error_response(500, 'Failed to delete session')


def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    try:
        # Test DynamoDB connectivity
        start_time = datetime.utcnow()
        sessions_table.scan(Limit=1)
        response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        health_data = {
            'status': 'healthy',
            'service': 'session-management-http-api',
            'environment': ENV,
            'timestamp': int(datetime.utcnow().timestamp() * 1000),
            'responseTimeMs': response_time_ms,
            'version': '1.0.0',
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps(health_data),
        }
        
    except Exception as e:
        logger.error(f'Health check failed: {str(e)}')
        return {
            'statusCode': 503,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'status': 'unhealthy',
                'error': 'Service unavailable',
                'timestamp': int(datetime.utcnow().timestamp() * 1000),
            }),
        }


def disconnect_session_connections(session_id: str):
    """
    Disconnect all WebSocket connections for a session.
    
    This function:
    1. Queries all connections for the session using GSI
    2. Sends disconnect message to each connection
    3. Closes WebSocket connections gracefully
    4. Deletes connection records from DynamoDB
    
    Args:
        session_id: Session identifier
    """
    try:
        # Query connections by sessionId using GSI
        response = connections_table.query(
            IndexName='sessionId-targetLanguage-index',
            KeyConditionExpression='sessionId = :sid',
            ExpressionAttributeValues={':sid': session_id},
        )
        
        connections = response.get('Items', [])
        
        logger.info(
            f'Disconnecting {len(connections)} connections for session',
            extra={'session_id': session_id, 'connection_count': len(connections)}
        )
        
        # Get API Gateway endpoint from environment
        api_gateway_endpoint = os.environ.get('WEBSOCKET_API_ENDPOINT', '')
        
        if not api_gateway_endpoint:
            logger.warning(
                'WEBSOCKET_API_ENDPOINT not configured, skipping WebSocket disconnection',
                extra={'session_id': session_id}
            )
            # Still delete connection records
            for connection in connections:
                connections_table.delete_item(
                    Key={'connectionId': connection['connectionId']}
                )
            return
        
        # Initialize API Gateway Management API client
        apigw_management = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=api_gateway_endpoint
        )
        
        success_count = 0
        failure_count = 0
        
        # Send disconnect message and close each connection
        for connection in connections:
            connection_id = connection['connectionId']
            
            try:
                # Send disconnect message to client
                disconnect_message = {
                    'type': 'sessionEnded',
                    'sessionId': session_id,
                    'reason': 'Session was deleted by speaker',
                    'timestamp': int(datetime.utcnow().timestamp() * 1000)
                }
                
                apigw_management.post_to_connection(
                    ConnectionId=connection_id,
                    Data=json.dumps(disconnect_message).encode('utf-8')
                )
                
                logger.info(
                    f'Sent disconnect message to connection',
                    extra={
                        'session_id': session_id,
                        'connection_id': connection_id
                    }
                )
                
                # Note: We don't explicitly close the connection here
                # The client will close it upon receiving the sessionEnded message
                # API Gateway will clean up stale connections automatically
                
                success_count += 1
                
            except apigw_management.exceptions.GoneException:
                # Connection already closed
                logger.info(
                    f'Connection already closed',
                    extra={
                        'session_id': session_id,
                        'connection_id': connection_id
                    }
                )
                success_count += 1
                
            except Exception as e:
                logger.error(
                    f'Failed to disconnect connection: {str(e)}',
                    extra={
                        'session_id': session_id,
                        'connection_id': connection_id
                    }
                )
                failure_count += 1
            
            finally:
                # Always delete connection record from DynamoDB
                try:
                    connections_table.delete_item(
                        Key={'connectionId': connection_id}
                    )
                except Exception as e:
                    logger.error(
                        f'Failed to delete connection record: {str(e)}',
                        extra={
                            'session_id': session_id,
                            'connection_id': connection_id
                        }
                    )
        
        logger.info(
            f'Disconnection complete: {success_count} succeeded, {failure_count} failed',
            extra={
                'session_id': session_id,
                'success_count': success_count,
                'failure_count': failure_count
            }
        )
        
        # Emit metrics
        emit_metric('SessionConnectionsDisconnected', success_count)
        if failure_count > 0:
            emit_metric('SessionConnectionsDisconnectFailed', failure_count)
        
    except Exception as e:
        logger.error(
            f'Failed to disconnect session connections: {str(e)}',
            extra={'session_id': session_id}
        )


def generate_session_id() -> str:
    """Generate human-readable session ID."""
    import random
    
    # Christian/Bible-themed adjectives
    adjectives = [
        'blessed', 'faithful', 'gracious', 'holy', 'joyful',
        'peaceful', 'righteous', 'sacred', 'divine', 'eternal',
        'glorious', 'merciful', 'pure', 'radiant', 'serene',
    ]
    
    # Christian/Bible-themed nouns
    nouns = [
        'shepherd', 'covenant', 'temple', 'prophet', 'angel',
        'disciple', 'apostle', 'psalm', 'gospel', 'grace',
        'faith', 'hope', 'light', 'truth', 'wisdom',
    ]
    
    adjective = random.choice(adjectives)
    noun = random.choice(nouns)
    number = random.randint(100, 999)
    
    return f'{adjective}-{noun}-{number}'


def emit_metric(metric_name: str, value: float, dimensions: Optional[Dict[str, str]] = None):
    """Emit CloudWatch metric."""
    try:
        cloudwatch = boto3.client('cloudwatch')
        
        metric_data = {
            'MetricName': metric_name,
            'Value': value,
            'Unit': 'Count',
            'Timestamp': datetime.utcnow(),
        }
        
        if dimensions:
            metric_data['Dimensions'] = [
                {'Name': k, 'Value': v} for k, v in dimensions.items()
            ]
        
        cloudwatch.put_metric_data(
            Namespace='SessionManagement',
            MetricData=[metric_data]
        )
    except Exception as e:
        logger.warning(f'Failed to emit metric: {str(e)}')


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Generate error response."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'error': message,
            'timestamp': int(datetime.utcnow().timestamp() * 1000),
        }),
    }
