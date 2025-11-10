"""
Unit tests for Disconnect Handler Lambda.

Tests speaker disconnect handling with session termination and listener notification.

Requirements: 4, 5, 16
"""
import json
import time
import sys
import os
from unittest.mock import Mock, MagicMock, patch
import pytest
import boto3
from moto import mock_dynamodb
import importlib.util

# Set environment variables for testing
os.environ['CONNECTIONS_TABLE'] = 'Connections-test'
os.environ['SESSIONS_TABLE'] = 'Sessions-test'

# Import handler using importlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
handler_path = os.path.join(os.path.dirname(__file__), '..', 'lambda', 'disconnect_handler', 'handler.py')
spec = importlib.util.spec_from_file_location('disconnect_handler', handler_path)
disconnect_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(disconnect_handler)

lambda_handler = disconnect_handler.lambda_handler


@pytest.fixture(scope='function')
def aws_credentials():
    """Mock AWS credentials."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'


@pytest.fixture(scope='function')
def dynamodb_tables(aws_credentials):
    """Create mock DynamoDB tables."""
    with mock_dynamodb():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        # Create Sessions table
        sessions_table = dynamodb.create_table(
            TableName='Sessions-test',
            KeySchema=[
                {'AttributeName': 'sessionId', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'sessionId', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Create Connections table with GSI
        connections_table = dynamodb.create_table(
            TableName='Connections-test',
            KeySchema=[
                {'AttributeName': 'connectionId', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'connectionId', 'AttributeType': 'S'},
                {'AttributeName': 'sessionId', 'AttributeType': 'S'},
                {'AttributeName': 'targetLanguage', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'sessionId-targetLanguage-index',
                    'KeySchema': [
                        {'AttributeName': 'sessionId', 'KeyType': 'HASH'},
                        {'AttributeName': 'targetLanguage', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        yield {
            'sessions': sessions_table,
            'connections': connections_table
        }


@pytest.fixture
def mock_api_gateway():
    """Mock API Gateway Management API client."""
    mock_client = MagicMock()
    mock_client.post_to_connection = MagicMock()
    
    # Patch boto3.client to return our mock
    original_client = disconnect_handler.boto3.client
    
    def mock_boto_client(service_name, **kwargs):
        if service_name == 'apigatewaymanagementapi':
            return mock_client
        return original_client(service_name, **kwargs)
    
    disconnect_handler.boto3.client = mock_boto_client
    
    yield mock_client
    
    # Restore original
    disconnect_handler.boto3.client = original_client


@pytest.fixture
def disconnect_event():
    """Create a sample disconnect event."""
    return {
        'requestContext': {
            'connectionId': 'speaker-conn-123',
            'domainName': 'test.execute-api.us-east-1.amazonaws.com',
            'stage': 'test',
            'eventType': 'DISCONNECT',
            'routeKey': '$disconnect'
        }
    }


class TestSpeakerDisconnect:
    """Test speaker disconnect handling."""
    
    def test_speaker_disconnect_marks_session_inactive(self, dynamodb_tables, mock_api_gateway, disconnect_event):
        """Test that speaker disconnect marks session as inactive."""
        # Arrange
        session_id = 'test-session-123'
        speaker_conn_id = 'speaker-conn-123'
        current_time = int(time.time() * 1000)
        
        # Create session
        dynamodb_tables['sessions'].put_item(Item={
            'sessionId': session_id,
            'speakerConnectionId': speaker_conn_id,
            'speakerUserId': 'user-123',
            'sourceLanguage': 'en',
            'qualityTier': 'standard',
            'createdAt': current_time - 60000,  # 1 minute ago
            'isActive': True,
            'listenerCount': 0,
            'expiresAt': int(time.time()) + 7200
        })
        
        # Create speaker connection
        dynamodb_tables['connections'].put_item(Item={
            'connectionId': speaker_conn_id,
            'sessionId': session_id,
            'role': 'speaker',
            'connectedAt': current_time - 60000,
            'ttl': int(time.time()) + 7200
        })
        
        # Act
        response = lambda_handler(disconnect_event, None)
        
        # Assert
        assert response['statusCode'] == 200
        
        # Verify session is marked inactive
        session = dynamodb_tables['sessions'].get_item(Key={'sessionId': session_id})['Item']
        assert session['isActive'] is False
    
    def test_speaker_disconnect_notifies_all_listeners(self, dynamodb_tables, mock_api_gateway, disconnect_event):
        """Test that speaker disconnect sends sessionEnded to all listeners."""
        # Arrange
        session_id = 'test-session-123'
        speaker_conn_id = 'speaker-conn-123'
        current_time = int(time.time() * 1000)
        
        # Create session
        dynamodb_tables['sessions'].put_item(Item={
            'sessionId': session_id,
            'speakerConnectionId': speaker_conn_id,
            'speakerUserId': 'user-123',
            'sourceLanguage': 'en',
            'qualityTier': 'standard',
            'createdAt': current_time - 60000,
            'isActive': True,
            'listenerCount': 3,
            'expiresAt': int(time.time()) + 7200
        })
        
        # Create speaker connection
        dynamodb_tables['connections'].put_item(Item={
            'connectionId': speaker_conn_id,
            'sessionId': session_id,
            'role': 'speaker',
            'connectedAt': current_time - 60000,
            'ttl': int(time.time()) + 7200
        })
        
        # Create listener connections
        listener_ids = ['listener-1', 'listener-2', 'listener-3']
        for listener_id in listener_ids:
            dynamodb_tables['connections'].put_item(Item={
                'connectionId': listener_id,
                'sessionId': session_id,
                'role': 'listener',
                'targetLanguage': 'es',
                'connectedAt': current_time - 30000,
                'ttl': int(time.time()) + 7200
            })
        
        # Act
        response = lambda_handler(disconnect_event, None)
        
        # Assert
        assert response['statusCode'] == 200
        
        # Verify sessionEnded message sent to all listeners
        assert mock_api_gateway.post_to_connection.call_count == 3
        
        # Check message content
        for call in mock_api_gateway.post_to_connection.call_args_list:
            kwargs = call[1]
            assert kwargs['ConnectionId'] in listener_ids
            
            message = json.loads(kwargs['Data'].decode('utf-8'))
            assert message['type'] == 'sessionEnded'
            assert message['sessionId'] == session_id
            assert 'timestamp' in message
    
    def test_speaker_disconnect_deletes_all_connections(self, dynamodb_tables, mock_api_gateway, disconnect_event):
        """Test that speaker disconnect deletes all connection records."""
        # Arrange
        session_id = 'test-session-123'
        speaker_conn_id = 'speaker-conn-123'
        current_time = int(time.time() * 1000)
        
        # Create session
        dynamodb_tables['sessions'].put_item(Item={
            'sessionId': session_id,
            'speakerConnectionId': speaker_conn_id,
            'speakerUserId': 'user-123',
            'sourceLanguage': 'en',
            'qualityTier': 'standard',
            'createdAt': current_time - 60000,
            'isActive': True,
            'listenerCount': 2,
            'expiresAt': int(time.time()) + 7200
        })
        
        # Create speaker connection
        dynamodb_tables['connections'].put_item(Item={
            'connectionId': speaker_conn_id,
            'sessionId': session_id,
            'role': 'speaker',
            'connectedAt': current_time - 60000,
            'ttl': int(time.time()) + 7200
        })
        
        # Create listener connections
        dynamodb_tables['connections'].put_item(Item={
            'connectionId': 'listener-1',
            'sessionId': session_id,
            'role': 'listener',
            'targetLanguage': 'es',
            'connectedAt': current_time - 30000,
            'ttl': int(time.time()) + 7200
        })
        dynamodb_tables['connections'].put_item(Item={
            'connectionId': 'listener-2',
            'sessionId': session_id,
            'role': 'listener',
            'targetLanguage': 'fr',
            'connectedAt': current_time - 30000,
            'ttl': int(time.time()) + 7200
        })
        
        # Act
        response = lambda_handler(disconnect_event, None)
        
        # Assert
        assert response['statusCode'] == 200
        
        # Verify all connections deleted
        # Speaker connection should be deleted
        speaker_conn = dynamodb_tables['connections'].get_item(
            Key={'connectionId': speaker_conn_id}
        ).get('Item')
        assert speaker_conn is None
        
        # Listener connections should be deleted
        listener1 = dynamodb_tables['connections'].get_item(
            Key={'connectionId': 'listener-1'}
        ).get('Item')
        assert listener1 is None
        
        listener2 = dynamodb_tables['connections'].get_item(
            Key={'connectionId': 'listener-2'}
        ).get('Item')
        assert listener2 is None
    
    def test_speaker_disconnect_with_no_listeners(self, dynamodb_tables, mock_api_gateway, disconnect_event):
        """Test speaker disconnect when no listeners are connected."""
        # Arrange
        session_id = 'test-session-123'
        speaker_conn_id = 'speaker-conn-123'
        current_time = int(time.time() * 1000)
        
        # Create session with no listeners
        dynamodb_tables['sessions'].put_item(Item={
            'sessionId': session_id,
            'speakerConnectionId': speaker_conn_id,
            'speakerUserId': 'user-123',
            'sourceLanguage': 'en',
            'qualityTier': 'standard',
            'createdAt': current_time - 60000,
            'isActive': True,
            'listenerCount': 0,
            'expiresAt': int(time.time()) + 7200
        })
        
        # Create speaker connection
        dynamodb_tables['connections'].put_item(Item={
            'connectionId': speaker_conn_id,
            'sessionId': session_id,
            'role': 'speaker',
            'connectedAt': current_time - 60000,
            'ttl': int(time.time()) + 7200
        })
        
        # Act
        response = lambda_handler(disconnect_event, None)
        
        # Assert
        assert response['statusCode'] == 200
        
        # Verify session is marked inactive
        session = dynamodb_tables['sessions'].get_item(Key={'sessionId': session_id})['Item']
        assert session['isActive'] is False
        
        # Verify no messages sent (no listeners)
        assert mock_api_gateway.post_to_connection.call_count == 0
    
    def test_disconnect_idempotent_when_connection_not_found(self, dynamodb_tables, mock_api_gateway, disconnect_event):
        """Test that disconnect is idempotent when connection doesn't exist."""
        # Act - disconnect event for non-existent connection
        response = lambda_handler(disconnect_event, None)
        
        # Assert - should return success (idempotent)
        assert response['statusCode'] == 200
    
    def test_disconnect_handles_api_gateway_gone_exception(self, dynamodb_tables, mock_api_gateway, disconnect_event):
        """Test that disconnect handles GoneException gracefully."""
        # Arrange
        session_id = 'test-session-123'
        speaker_conn_id = 'speaker-conn-123'
        current_time = int(time.time() * 1000)
        
        # Create session
        dynamodb_tables['sessions'].put_item(Item={
            'sessionId': session_id,
            'speakerConnectionId': speaker_conn_id,
            'speakerUserId': 'user-123',
            'sourceLanguage': 'en',
            'qualityTier': 'standard',
            'createdAt': current_time - 60000,
            'isActive': True,
            'listenerCount': 1,
            'expiresAt': int(time.time()) + 7200
        })
        
        # Create speaker connection
        dynamodb_tables['connections'].put_item(Item={
            'connectionId': speaker_conn_id,
            'sessionId': session_id,
            'role': 'speaker',
            'connectedAt': current_time - 60000,
            'ttl': int(time.time()) + 7200
        })
        
        # Create listener connection
        dynamodb_tables['connections'].put_item(Item={
            'connectionId': 'listener-1',
            'sessionId': session_id,
            'role': 'listener',
            'targetLanguage': 'es',
            'connectedAt': current_time - 30000,
            'ttl': int(time.time()) + 7200
        })
        
        # Mock GoneException
        class GoneException(Exception):
            pass
        
        mock_api_gateway.post_to_connection.side_effect = GoneException("Connection gone")
        
        # Act
        response = lambda_handler(disconnect_event, None)
        
        # Assert - should still succeed (listener already disconnected)
        assert response['statusCode'] == 200
        
        # Verify session still marked inactive
        session = dynamodb_tables['sessions'].get_item(Key={'sessionId': session_id})['Item']
        assert session['isActive'] is False


class TestListenerDisconnect:
    """Test listener disconnect handling."""
    
    def test_listener_disconnect_decrements_count(self, dynamodb_tables, mock_api_gateway):
        """Test that listener disconnect decrements listener count."""
        # Arrange
        session_id = 'test-session-123'
        listener_conn_id = 'listener-conn-123'
        current_time = int(time.time() * 1000)
        
        # Create session with 1 listener
        dynamodb_tables['sessions'].put_item(Item={
            'sessionId': session_id,
            'speakerConnectionId': 'speaker-123',
            'speakerUserId': 'user-123',
            'sourceLanguage': 'en',
            'qualityTier': 'standard',
            'createdAt': current_time - 60000,
            'isActive': True,
            'listenerCount': 1,
            'expiresAt': int(time.time()) + 7200
        })
        
        # Create listener connection
        dynamodb_tables['connections'].put_item(Item={
            'connectionId': listener_conn_id,
            'sessionId': session_id,
            'role': 'listener',
            'targetLanguage': 'es',
            'connectedAt': current_time - 30000,
            'ttl': int(time.time()) + 7200
        })
        
        # Create disconnect event for listener
        disconnect_event = {
            'requestContext': {
                'connectionId': listener_conn_id,
                'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                'stage': 'test',
                'eventType': 'DISCONNECT',
                'routeKey': '$disconnect'
            }
        }
        
        # Act
        response = lambda_handler(disconnect_event, None)
        
        # Assert
        assert response['statusCode'] == 200
        
        # Verify listener count decremented
        session = dynamodb_tables['sessions'].get_item(Key={'sessionId': session_id})['Item']
        assert session['listenerCount'] == 0
        
        # Verify connection deleted
        connection = dynamodb_tables['connections'].get_item(
            Key={'connectionId': listener_conn_id}
        ).get('Item')
        assert connection is None
    
    def test_listener_disconnect_prevents_negative_count(self, dynamodb_tables, mock_api_gateway):
        """Test that listener count doesn't go negative."""
        # Arrange
        session_id = 'test-session-123'
        listener_conn_id = 'listener-conn-123'
        current_time = int(time.time() * 1000)
        
        # Create session with 0 listeners (edge case - count already at 0)
        dynamodb_tables['sessions'].put_item(Item={
            'sessionId': session_id,
            'speakerConnectionId': 'speaker-123',
            'speakerUserId': 'user-123',
            'sourceLanguage': 'en',
            'qualityTier': 'standard',
            'createdAt': current_time - 60000,
            'isActive': True,
            'listenerCount': 0,
            'expiresAt': int(time.time()) + 7200
        })
        
        # Create listener connection (orphaned connection)
        dynamodb_tables['connections'].put_item(Item={
            'connectionId': listener_conn_id,
            'sessionId': session_id,
            'role': 'listener',
            'targetLanguage': 'es',
            'connectedAt': current_time - 30000,
            'ttl': int(time.time()) + 7200
        })
        
        # Create disconnect event for listener
        disconnect_event = {
            'requestContext': {
                'connectionId': listener_conn_id,
                'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                'stage': 'test',
                'eventType': 'DISCONNECT',
                'routeKey': '$disconnect'
            }
        }
        
        # Act
        response = lambda_handler(disconnect_event, None)
        
        # Assert
        assert response['statusCode'] == 200
        
        # Verify listener count stays at 0 (doesn't go negative)
        session = dynamodb_tables['sessions'].get_item(Key={'sessionId': session_id})['Item']
        assert session['listenerCount'] == 0
    
    def test_listener_disconnect_with_multiple_listeners(self, dynamodb_tables, mock_api_gateway):
        """Test listener disconnect when multiple listeners are connected."""
        # Arrange
        session_id = 'test-session-123'
        listener_conn_id = 'listener-conn-1'  # Use existing connection ID
        current_time = int(time.time() * 1000)
        
        # Create session with 3 listeners
        dynamodb_tables['sessions'].put_item(Item={
            'sessionId': session_id,
            'speakerConnectionId': 'speaker-123',
            'speakerUserId': 'user-123',
            'sourceLanguage': 'en',
            'qualityTier': 'standard',
            'createdAt': current_time - 60000,
            'isActive': True,
            'listenerCount': 3,
            'expiresAt': int(time.time()) + 7200
        })
        
        # Create listener connections
        for i in range(1, 4):
            dynamodb_tables['connections'].put_item(Item={
                'connectionId': f'listener-conn-{i}',
                'sessionId': session_id,
                'role': 'listener',
                'targetLanguage': 'es',
                'connectedAt': current_time - 30000,
                'ttl': int(time.time()) + 7200
            })
        
        # Create disconnect event for one listener
        disconnect_event = {
            'requestContext': {
                'connectionId': listener_conn_id,
                'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                'stage': 'test',
                'eventType': 'DISCONNECT',
                'routeKey': '$disconnect'
            }
        }
        
        # Act
        response = lambda_handler(disconnect_event, None)
        
        # Assert
        assert response['statusCode'] == 200
        
        # Verify listener count decremented by 1
        session = dynamodb_tables['sessions'].get_item(Key={'sessionId': session_id})['Item']
        assert session['listenerCount'] == 2
        
        # Verify only the disconnected listener's connection is deleted
        connection = dynamodb_tables['connections'].get_item(
            Key={'connectionId': listener_conn_id}
        ).get('Item')
        assert connection is None
        
        # Verify other listeners still connected
        for i in range(2, 4):
            conn = dynamodb_tables['connections'].get_item(
                Key={'connectionId': f'listener-conn-{i}'}
            ).get('Item')
            assert conn is not None


class TestIdempotentOperations:
    """Test idempotent disconnect operations."""
    
    def test_disconnect_is_idempotent_for_speaker(self, dynamodb_tables, mock_api_gateway):
        """Test that speaker disconnect can be called multiple times safely."""
        # Arrange
        session_id = 'test-session-123'
        speaker_conn_id = 'speaker-conn-123'
        current_time = int(time.time() * 1000)
        
        # Create session
        dynamodb_tables['sessions'].put_item(Item={
            'sessionId': session_id,
            'speakerConnectionId': speaker_conn_id,
            'speakerUserId': 'user-123',
            'sourceLanguage': 'en',
            'qualityTier': 'standard',
            'createdAt': current_time - 60000,
            'isActive': True,
            'listenerCount': 0,
            'expiresAt': int(time.time()) + 7200
        })
        
        # Create speaker connection
        dynamodb_tables['connections'].put_item(Item={
            'connectionId': speaker_conn_id,
            'sessionId': session_id,
            'role': 'speaker',
            'connectedAt': current_time - 60000,
            'ttl': int(time.time()) + 7200
        })
        
        disconnect_event = {
            'requestContext': {
                'connectionId': speaker_conn_id,
                'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                'stage': 'test',
                'eventType': 'DISCONNECT',
                'routeKey': '$disconnect'
            }
        }
        
        # Act - call disconnect twice
        response1 = lambda_handler(disconnect_event, None)
        response2 = lambda_handler(disconnect_event, None)
        
        # Assert - both should succeed
        assert response1['statusCode'] == 200
        assert response2['statusCode'] == 200
        
        # Verify session is inactive
        session = dynamodb_tables['sessions'].get_item(Key={'sessionId': session_id})['Item']
        assert session['isActive'] is False
    
    def test_disconnect_is_idempotent_for_listener(self, dynamodb_tables, mock_api_gateway):
        """Test that listener disconnect can be called multiple times safely."""
        # Arrange
        session_id = 'test-session-123'
        listener_conn_id = 'listener-conn-123'
        current_time = int(time.time() * 1000)
        
        # Create session with 1 listener
        dynamodb_tables['sessions'].put_item(Item={
            'sessionId': session_id,
            'speakerConnectionId': 'speaker-123',
            'speakerUserId': 'user-123',
            'sourceLanguage': 'en',
            'qualityTier': 'standard',
            'createdAt': current_time - 60000,
            'isActive': True,
            'listenerCount': 1,
            'expiresAt': int(time.time()) + 7200
        })
        
        # Create listener connection
        dynamodb_tables['connections'].put_item(Item={
            'connectionId': listener_conn_id,
            'sessionId': session_id,
            'role': 'listener',
            'targetLanguage': 'es',
            'connectedAt': current_time - 30000,
            'ttl': int(time.time()) + 7200
        })
        
        disconnect_event = {
            'requestContext': {
                'connectionId': listener_conn_id,
                'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                'stage': 'test',
                'eventType': 'DISCONNECT',
                'routeKey': '$disconnect'
            }
        }
        
        # Act - call disconnect twice
        response1 = lambda_handler(disconnect_event, None)
        response2 = lambda_handler(disconnect_event, None)
        
        # Assert - both should succeed (idempotent)
        assert response1['statusCode'] == 200
        assert response2['statusCode'] == 200
        
        # Verify listener count is 0 (not negative)
        session = dynamodb_tables['sessions'].get_item(Key={'sessionId': session_id})['Item']
        assert session['listenerCount'] == 0
