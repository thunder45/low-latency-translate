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

@pytest.fixture
def mock_api_gateway():
    """Mock API Gateway Management API client."""
    with patch('boto3.client') as mock_client:
        mock_api_gw = Mock()
        mock_client.return_value = mock_api_gw
        yield mock_api_gw


@pytest.fixture
def lambda_handler(env_vars, mock_api_gateway):
    """Import lambda_handler after environment is set up using importlib to avoid path pollution."""
    import importlib.util
    
    # Import handler using importlib to avoid adding Lambda dir to sys.path
    # This prevents importing Linux cryptography binaries that don't work on macOS
    handler_path = os.path.join(os.path.dirname(__file__), '../lambda/refresh_handler/handler.py')
    spec = importlib.util.spec_from_file_location('refresh_handler', handler_path)
    handler_module = importlib.util.module_from_spec(spec)
    
    # Temporarily add only the handler's parent dir to sys.path for relative imports
    refresh_handler_dir = os.path.dirname(handler_path)
    sys.path.insert(0, refresh_handler_dir)
    try:
        spec.loader.exec_module(handler_module)
    finally:
        # Remove from sys.path to avoid polluting other tests
        if refresh_handler_dir in sys.path:
            sys.path.remove(refresh_handler_dir)
    
    return handler_module.lambda_handler


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
        
        # Import auth_validator to patch it
        import importlib.util
        auth_validator_path = os.path.join(os.path.dirname(__file__), '../lambda/refresh_handler/auth_validator.py')
        spec = importlib.util.spec_from_file_location('auth_validator', auth_validator_path)
        auth_validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(auth_validator)
        
        # Mock the token validation to return valid claims
        with patch.object(auth_validator, 'validate_speaker_token') as mock_validate:
            mock_validate.return_value = {
                'sub': active_session['speakerUserId'],
                'email': 'speaker@example.com'
            }
            
            event = {
                'requestContext': {
                    'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                    'stage': 'test',
                    'connectionId': new_connection_id
                },
                'queryStringParameters': {
                    'sessionId': active_session['sessionId'],
                    'role': 'speaker',
                    'token': 'valid-jwt-token'  # Token is required for speaker refresh
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
    
    def test_speaker_refresh_with_mismatched_identity_fails(
        self,
        mock_api_gateway,
        lambda_handler,
        dynamodb_tables,
        active_session
    ):
        """Test speaker refresh fails with wrong user ID."""
        # Arrange
        # Mock the token validation to return claims with wrong user ID
        # Patch in the refresh_handler module where it's imported
        with patch('refresh_handler.validate_speaker_token') as mock_validate:
            mock_validate.return_value = {
                'sub': 'wrong-user-999',  # Different from session owner
                'email': 'wrong@example.com'
            }
            
            event = {
                'requestContext': {
                    'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                    'stage': 'test',
                    'connectionId': 'new-conn-456'
                },
                'queryStringParameters': {
                    'sessionId': active_session['sessionId'],
                    'role': 'speaker',
                    'token': 'valid-jwt-token-wrong-user'  # Token with wrong user
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
                'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                'stage': 'test',
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
                'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                'stage': 'test',
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
                'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                'stage': 'test',
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
                'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                'stage': 'test',
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
                'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                'stage': 'test',
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
                'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                'stage': 'test',
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
                'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                'stage': 'test',
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
                'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                'stage': 'test',
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
