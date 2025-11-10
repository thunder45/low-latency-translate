"""
Integration tests for Connection Refresh Handler.

Tests speaker and listener connection refresh with identity validation,
count management, and error scenarios.
"""
import json
import time
from unittest.mock import Mock, patch, MagicMock
import sys
import os

import pytest
from moto import mock_dynamodb

# Add handler to path but don't import yet
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../lambda/refresh_handler'))


@pytest.fixture
def lambda_handler(env_vars):
    """Import lambda_handler after environment is set up."""
    from handler import lambda_handler as handler
    return handler


@pytest.fixture
def dynamodb_tables(aws_credentials, env_vars):
    """Create mock DynamoDB tables."""
    with mock_dynamodb():
        import boto3
        
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
        
        # Create Connections table
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
def active_session(dynamodb_tables):
    """Create an active session."""
    session_id = 'test-session-123'
    speaker_user_id = 'user-123'
    
    dynamodb_tables['sessions'].put_item(
        Item={
            'sessionId': session_id,
            'speakerConnectionId': 'old-conn-123',
            'speakerUserId': speaker_user_id,
            'sourceLanguage': 'en',
            'isActive': True,
            'listenerCount': 5,
            'qualityTier': 'standard',
            'createdAt': int(time.time() * 1000),
            'expiresAt': int(time.time()) + 7200
        }
    )
    
    return {
        'sessionId': session_id,
        'speakerUserId': speaker_user_id
    }


class TestSpeakerConnectionRefresh:
    """Test speaker connection refresh with identity validation."""
    
    @patch('handler.api_gateway')
    def test_speaker_refresh_with_valid_identity_succeeds(
        self,
        mock_api_gateway,
        lambda_handler,
        dynamodb_tables,
        active_session
    ):
        """Test speaker connection refresh with matching identity."""
        # Arrange
        new_connection_id = 'new-conn-456'
        event = {
            'requestContext': {
                'connectionId': new_connection_id,
                'authorizer': {
                    'userId': active_session['speakerUserId']
                }
            },
            'queryStringParameters': {
                'sessionId': active_session['sessionId'],
                'role': 'speaker'
            }
        }
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 200
        
        # Verify session updated with new connection ID
        session = dynamodb_tables['sessions'].get_item(
            Key={'sessionId': active_session['sessionId']}
        )['Item']
        assert session['speakerConnectionId'] == new_connection_id
        
        # Verify message sent to new connection
        mock_api_gateway.post_to_connection.assert_called_once()
        call_args = mock_api_gateway.post_to_connection.call_args
        assert call_args[1]['ConnectionId'] == new_connection_id
        
        message = json.loads(call_args[1]['Data'])
        assert message['type'] == 'connectionRefreshComplete'
        assert message['sessionId'] == active_session['sessionId']
        assert message['role'] == 'speaker'
    
    @patch('handler.api_gateway')
    def test_speaker_refresh_with_mismatched_identity_fails(
        self,
        mock_api_gateway,
        lambda_handler,
        dynamodb_tables,
        active_session
    ):
        """Test speaker refresh fails with wrong user ID."""
        # Arrange
        event = {
            'requestContext': {
                'connectionId': 'new-conn-456',
                'authorizer': {
                    'userId': 'wrong-user-999'
                }
            },
            'queryStringParameters': {
                'sessionId': active_session['sessionId'],
                'role': 'speaker'
            }
        }
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 403
        body = json.loads(response['body'])
        assert body['code'] == 'FORBIDDEN'
        assert 'identity mismatch' in body['message'].lower()
        
        # Verify session NOT updated
        session = dynamodb_tables['sessions'].get_item(
            Key={'sessionId': active_session['sessionId']}
        )['Item']
        assert session['speakerConnectionId'] == 'old-conn-123'
    
    @patch('handler.api_gateway')
    def test_speaker_refresh_without_authentication_fails(
        self,
        mock_api_gateway,
        lambda_handler,
        dynamodb_tables,
        active_session
    ):
        """Test speaker refresh requires authentication."""
        # Arrange
        event = {
            'requestContext': {
                'connectionId': 'new-conn-456',
                'authorizer': {}  # No userId
            },
            'queryStringParameters': {
                'sessionId': active_session['sessionId'],
                'role': 'speaker'
            }
        }
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert body['code'] == 'UNAUTHORIZED'


class TestListenerConnectionRefresh:
    """Test listener connection refresh with count management."""
    
    @patch('handler.api_gateway')
    def test_listener_refresh_creates_new_connection_and_increments_count(
        self,
        mock_api_gateway,
        lambda_handler,
        dynamodb_tables,
        active_session
    ):
        """Test listener refresh creates connection and increments count."""
        # Arrange
        new_connection_id = 'listener-conn-789'
        target_language = 'es'
        
        event = {
            'requestContext': {
                'connectionId': new_connection_id,
                'identity': {
                    'sourceIp': '192.168.1.1'
                }
            },
            'queryStringParameters': {
                'sessionId': active_session['sessionId'],
                'role': 'listener',
                'targetLanguage': target_language
            }
        }
        
        initial_count = dynamodb_tables['sessions'].get_item(
            Key={'sessionId': active_session['sessionId']}
        )['Item']['listenerCount']
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 200
        
        # Verify new connection record created
        connection = dynamodb_tables['connections'].get_item(
            Key={'connectionId': new_connection_id}
        )['Item']
        assert connection['sessionId'] == active_session['sessionId']
        assert connection['targetLanguage'] == target_language
        assert connection['role'] == 'listener'
        
        # Verify listener count incremented
        session = dynamodb_tables['sessions'].get_item(
            Key={'sessionId': active_session['sessionId']}
        )['Item']
        assert session['listenerCount'] == initial_count + 1
        
        # Verify message sent
        mock_api_gateway.post_to_connection.assert_called_once()
        call_args = mock_api_gateway.post_to_connection.call_args
        message = json.loads(call_args[1]['Data'])
        assert message['type'] == 'connectionRefreshComplete'
        assert message['role'] == 'listener'
        assert message['targetLanguage'] == target_language
    
    @patch('handler.api_gateway')
    def test_listener_refresh_without_target_language_fails(
        self,
        mock_api_gateway,
        lambda_handler,
        dynamodb_tables,
        active_session
    ):
        """Test listener refresh requires targetLanguage parameter."""
        # Arrange
        event = {
            'requestContext': {
                'connectionId': 'listener-conn-789',
                'identity': {'sourceIp': '192.168.1.1'}
            },
            'queryStringParameters': {
                'sessionId': active_session['sessionId'],
                'role': 'listener'
                # Missing targetLanguage
            }
        }
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['code'] == 'MISSING_PARAMETER'
        assert 'targetLanguage' in body['message']


class TestConnectionRefreshErrorScenarios:
    """Test error scenarios for connection refresh."""
    
    @patch('handler.api_gateway')
    def test_refresh_with_invalid_session_id_fails(
        self,
        mock_api_gateway,
        lambda_handler,
        dynamodb_tables
    ):
        """Test refresh with non-existent session."""
        # Arrange
        event = {
            'requestContext': {
                'connectionId': 'new-conn-456',
                'authorizer': {'userId': 'user-123'}
            },
            'queryStringParameters': {
                'sessionId': 'nonexistent-session',
                'role': 'speaker'
            }
        }
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['code'] == 'SESSION_NOT_FOUND'
    
    @patch('handler.api_gateway')
    def test_refresh_with_inactive_session_fails(
        self,
        mock_api_gateway,
        lambda_handler,
        dynamodb_tables
    ):
        """Test refresh fails for inactive session."""
        # Arrange - create inactive session
        session_id = 'inactive-session-123'
        dynamodb_tables['sessions'].put_item(
            Item={
                'sessionId': session_id,
                'speakerConnectionId': 'old-conn-123',
                'speakerUserId': 'user-123',
                'sourceLanguage': 'en',
                'isActive': False,  # Inactive
                'listenerCount': 0,
                'createdAt': int(time.time() * 1000),
                'expiresAt': int(time.time()) + 7200
            }
        )
        
        event = {
            'requestContext': {
                'connectionId': 'new-conn-456',
                'authorizer': {'userId': 'user-123'}
            },
            'queryStringParameters': {
                'sessionId': session_id,
                'role': 'speaker'
            }
        }
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['code'] == 'SESSION_NOT_FOUND'
    
    @patch('handler.api_gateway')
    def test_refresh_without_session_id_fails(
        self,
        mock_api_gateway,
        lambda_handler,
        dynamodb_tables
    ):
        """Test refresh requires sessionId parameter."""
        # Arrange
        event = {
            'requestContext': {
                'connectionId': 'new-conn-456',
                'authorizer': {'userId': 'user-123'}
            },
            'queryStringParameters': {
                'role': 'speaker'
                # Missing sessionId
            }
        }
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['code'] == 'MISSING_PARAMETER'
        assert 'sessionId' in body['message']
    
    @patch('handler.api_gateway')
    def test_refresh_with_invalid_role_fails(
        self,
        mock_api_gateway,
        lambda_handler,
        dynamodb_tables,
        active_session
    ):
        """Test refresh requires valid role parameter."""
        # Arrange
        event = {
            'requestContext': {
                'connectionId': 'new-conn-456',
                'authorizer': {'userId': 'user-123'}
            },
            'queryStringParameters': {
                'sessionId': active_session['sessionId'],
                'role': 'invalid-role'
            }
        }
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['code'] == 'INVALID_PARAMETER'


class TestListenerCountTolerance:
    """Test temporary listenerCount spike tolerance during refresh."""
    
    @patch('handler.api_gateway')
    def test_listener_refresh_allows_temporary_count_spike(
        self,
        mock_api_gateway,
        lambda_handler,
        dynamodb_tables,
        active_session
    ):
        """
        Test that listener refresh increments count even if temporarily
        above MAX_LISTENERS_PER_SESSION during transition.
        
        This is expected behavior - old connection will decrement when it closes.
        """
        # Arrange - set listener count to max
        max_listeners = int(os.environ.get('MAX_LISTENERS_PER_SESSION', '500'))
        dynamodb_tables['sessions'].update_item(
            Key={'sessionId': active_session['sessionId']},
            UpdateExpression='SET listenerCount = :count',
            ExpressionAttributeValues={':count': max_listeners}
        )
        
        event = {
            'requestContext': {
                'connectionId': 'refresh-conn-999',
                'identity': {'sourceIp': '192.168.1.1'}
            },
            'queryStringParameters': {
                'sessionId': active_session['sessionId'],
                'role': 'listener',
                'targetLanguage': 'es'
            }
        }
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert - refresh succeeds even though count temporarily exceeds max
        assert response['statusCode'] == 200
        
        # Verify count incremented (temporarily above max)
        session = dynamodb_tables['sessions'].get_item(
            Key={'sessionId': active_session['sessionId']}
        )['Item']
        assert session['listenerCount'] == max_listeners + 1
        
        # Note: In real scenario, old connection's $disconnect will decrement
        # bringing count back to max_listeners
