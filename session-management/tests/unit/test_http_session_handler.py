"""
Unit tests for HTTP Session Handler Lambda.

Tests all CRUD operations for session management via HTTP API:
- POST /sessions - Create session
- GET /sessions/{sessionId} - Get session
- PATCH /sessions/{sessionId} - Update session
- DELETE /sessions/{sessionId} - Delete session
- GET /health - Health check
"""
import json
import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

# Set environment variables before importing handler
os.environ['ENV'] = 'test'
os.environ['SESSIONS_TABLE'] = 'Sessions-test'
os.environ['CONNECTIONS_TABLE'] = 'Connections-test'
os.environ['USER_POOL_ID'] = 'us-east-1_test123'
os.environ['REGION'] = 'us-east-1'
os.environ['WEBSOCKET_API_ENDPOINT'] = 'https://test.execute-api.us-east-1.amazonaws.com/test'

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'http_session_handler'))

import handler


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables for tests."""
    monkeypatch.setenv('ENV', 'test')
    monkeypatch.setenv('SESSIONS_TABLE', 'Sessions-test')
    monkeypatch.setenv('CONNECTIONS_TABLE', 'Connections-test')
    monkeypatch.setenv('USER_POOL_ID', 'us-east-1_test123')
    monkeypatch.setenv('REGION', 'us-east-1')
    monkeypatch.setenv('WEBSOCKET_API_ENDPOINT', 'https://test.execute-api.us-east-1.amazonaws.com/test')


@pytest.fixture
def mock_dynamodb_tables():
    """Mock DynamoDB tables."""
    with patch.object(handler, 'sessions_table') as mock_sessions, \
         patch.object(handler, 'connections_table') as mock_connections:
        yield mock_sessions, mock_connections


@pytest.fixture
def mock_session_id():
    """Mock session ID generator."""
    with patch.object(handler, 'generate_session_id', return_value='blessed-shepherd-427'):
        yield


@pytest.fixture
def mock_cloudwatch():
    """Mock CloudWatch metrics."""
    with patch.object(handler, 'emit_metric'):
        yield


def create_http_event(method, path, body=None, user_id=None):
    """Helper to create HTTP API event."""
    event = {
        'requestContext': {
            'http': {
                'method': method,
                'path': path,
            },
            'requestId': 'test-request-123',
        },
        'body': json.dumps(body) if body else None,
    }
    
    if user_id:
        event['requestContext']['authorizer'] = {
            'jwt': {
                'claims': {
                    'sub': user_id
                }
            }
        }
    
    return event


class TestCreateSession:
    """Test suite for create_session endpoint."""
    
    def test_create_session_with_valid_input_succeeds(
        self,
        mock_env,
        mock_dynamodb_tables,
        mock_session_id,
        mock_cloudwatch
    ):
        """Test create_session with valid input."""
        # Arrange
        mock_sessions, _ = mock_dynamodb_tables
        mock_sessions.put_item = Mock()
        
        event = create_http_event(
            'POST',
            '/sessions',
            body={'sourceLanguage': 'en', 'qualityTier': 'standard'},
            user_id='user-123'
        )
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 201
        assert 'Content-Type' in response['headers']
        
        body = json.loads(response['body'])
        assert body['sessionId'] == 'blessed-shepherd-427'
        assert body['speakerId'] == 'user-123'
        assert body['sourceLanguage'] == 'en'
        assert body['qualityTier'] == 'standard'
        assert body['status'] == 'active'
        assert body['listenerCount'] == 0
        assert 'createdAt' in body
        assert 'updatedAt' in body
        assert 'expiresAt' in body
        
        # Verify DynamoDB put_item was called
        mock_sessions.put_item.assert_called_once()
        call_args = mock_sessions.put_item.call_args
        assert call_args[1]['Item']['sessionId'] == 'blessed-shepherd-427'
    
    def test_create_session_with_invalid_language_fails(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test create_session with invalid language code."""
        # Arrange
        event = create_http_event(
            'POST',
            '/sessions',
            body={'sourceLanguage': 'invalid', 'qualityTier': 'standard'},
            user_id='user-123'
        )
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Invalid sourceLanguage' in body['error']
    
    def test_create_session_with_missing_source_language_fails(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test create_session with missing sourceLanguage."""
        # Arrange
        event = create_http_event(
            'POST',
            '/sessions',
            body={'qualityTier': 'standard'},
            user_id='user-123'
        )
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'sourceLanguage is required' in body['error']
    
    def test_create_session_with_invalid_quality_tier_fails(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test create_session with invalid qualityTier."""
        # Arrange
        event = create_http_event(
            'POST',
            '/sessions',
            body={'sourceLanguage': 'en', 'qualityTier': 'invalid'},
            user_id='user-123'
        )
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Invalid qualityTier' in body['error']
    
    def test_create_session_without_authentication_fails(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test create_session without authentication."""
        # Arrange
        event = create_http_event(
            'POST',
            '/sessions',
            body={'sourceLanguage': 'en', 'qualityTier': 'standard'}
        )
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Authentication required' in body['error']
    
    def test_create_session_with_dynamodb_error_fails(
        self,
        mock_env,
        mock_dynamodb_tables,
        mock_session_id
    ):
        """Test create_session with DynamoDB error."""
        # Arrange
        mock_sessions, _ = mock_dynamodb_tables
        mock_sessions.put_item.side_effect = ClientError(
            {'Error': {'Code': 'InternalServerError', 'Message': 'Internal error'}},
            'PutItem'
        )
        
        event = create_http_event(
            'POST',
            '/sessions',
            body={'sourceLanguage': 'en', 'qualityTier': 'standard'},
            user_id='user-123'
        )
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Failed to create session' in body['error']


class TestGetSession:
    """Test suite for get_session endpoint."""
    
    def test_get_session_with_existing_session_succeeds(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test get_session with existing session."""
        # Arrange
        mock_sessions, _ = mock_dynamodb_tables
        mock_sessions.get_item.return_value = {
            'Item': {
                'sessionId': 'blessed-shepherd-427',
                'speakerId': 'user-123',
                'sourceLanguage': 'en',
                'qualityTier': 'standard',
                'status': 'active',
                'listenerCount': 5,
                'createdAt': 1699500000000,
                'updatedAt': 1699500000000,
            }
        }
        
        event = create_http_event('GET', '/sessions/blessed-shepherd-427')
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['sessionId'] == 'blessed-shepherd-427'
        assert body['speakerId'] == 'user-123'
        assert body['sourceLanguage'] == 'en'
        assert body['status'] == 'active'
        assert body['listenerCount'] == 5
        
        # Verify DynamoDB get_item was called
        mock_sessions.get_item.assert_called_once_with(
            Key={'sessionId': 'blessed-shepherd-427'}
        )
    
    def test_get_session_with_non_existent_session_fails(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test get_session with non-existent session."""
        # Arrange
        mock_sessions, _ = mock_dynamodb_tables
        mock_sessions.get_item.return_value = {}  # No Item in response
        
        event = create_http_event('GET', '/sessions/non-existent-session')
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Session not found' in body['error']
    
    def test_get_session_with_dynamodb_error_fails(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test get_session with DynamoDB error."""
        # Arrange
        mock_sessions, _ = mock_dynamodb_tables
        mock_sessions.get_item.side_effect = ClientError(
            {'Error': {'Code': 'InternalServerError', 'Message': 'Internal error'}},
            'GetItem'
        )
        
        event = create_http_event('GET', '/sessions/blessed-shepherd-427')
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Failed to retrieve session' in body['error']


class TestUpdateSession:
    """Test suite for update_session endpoint."""
    
    def test_update_session_with_ownership_succeeds(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test update_session with ownership."""
        # Arrange
        mock_sessions, _ = mock_dynamodb_tables
        
        # Mock get_item to return existing session
        mock_sessions.get_item.return_value = {
            'Item': {
                'sessionId': 'blessed-shepherd-427',
                'speakerId': 'user-123',
                'sourceLanguage': 'en',
                'qualityTier': 'standard',
                'status': 'active',
                'listenerCount': 5,
            }
        }
        
        # Mock update_item to return updated session
        mock_sessions.update_item.return_value = {
            'Attributes': {
                'sessionId': 'blessed-shepherd-427',
                'speakerId': 'user-123',
                'sourceLanguage': 'en',
                'qualityTier': 'standard',
                'status': 'paused',
                'listenerCount': 5,
                'updatedAt': 1699500100000,
            }
        }
        
        event = create_http_event(
            'PATCH',
            '/sessions/blessed-shepherd-427',
            body={'status': 'paused'},
            user_id='user-123'
        )
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['sessionId'] == 'blessed-shepherd-427'
        assert body['status'] == 'paused'
        
        # Verify DynamoDB operations
        mock_sessions.get_item.assert_called_once()
        mock_sessions.update_item.assert_called_once()
    
    def test_update_session_without_ownership_fails(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test update_session without ownership."""
        # Arrange
        mock_sessions, _ = mock_dynamodb_tables
        
        # Mock get_item to return session owned by different user
        mock_sessions.get_item.return_value = {
            'Item': {
                'sessionId': 'blessed-shepherd-427',
                'speakerId': 'other-user',
                'sourceLanguage': 'en',
                'status': 'active',
            }
        }
        
        event = create_http_event(
            'PATCH',
            '/sessions/blessed-shepherd-427',
            body={'status': 'paused'},
            user_id='user-123'
        )
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 403
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Not authorized' in body['error']
    
    def test_update_session_with_invalid_status_fails(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test update_session with invalid status."""
        # Arrange
        mock_sessions, _ = mock_dynamodb_tables
        
        mock_sessions.get_item.return_value = {
            'Item': {
                'sessionId': 'blessed-shepherd-427',
                'speakerId': 'user-123',
                'status': 'active',
            }
        }
        
        event = create_http_event(
            'PATCH',
            '/sessions/blessed-shepherd-427',
            body={'status': 'invalid'},
            user_id='user-123'
        )
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Invalid status' in body['error']
    
    def test_update_session_with_no_updates_fails(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test update_session with no valid updates."""
        # Arrange
        mock_sessions, _ = mock_dynamodb_tables
        
        mock_sessions.get_item.return_value = {
            'Item': {
                'sessionId': 'blessed-shepherd-427',
                'speakerId': 'user-123',
                'status': 'active',
            }
        }
        
        # Create event with empty body dict (will be serialized to '{}')
        event = {
            'requestContext': {
                'http': {
                    'method': 'PATCH',
                    'path': '/sessions/blessed-shepherd-427',
                },
                'requestId': 'test-request-123',
                'authorizer': {
                    'jwt': {
                        'claims': {
                            'sub': 'user-123'
                        }
                    }
                }
            },
            'body': '{}',  # Empty JSON object as string
        }
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'No valid updates' in body['error']
    
    def test_update_session_with_non_existent_session_fails(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test update_session with non-existent session."""
        # Arrange
        mock_sessions, _ = mock_dynamodb_tables
        mock_sessions.get_item.return_value = {}
        
        event = create_http_event(
            'PATCH',
            '/sessions/non-existent',
            body={'status': 'paused'},
            user_id='user-123'
        )
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Session not found' in body['error']


class TestDeleteSession:
    """Test suite for delete_session endpoint."""
    
    def test_delete_session_with_ownership_succeeds(
        self,
        mock_env,
        mock_dynamodb_tables,
        mock_cloudwatch
    ):
        """Test delete_session with ownership."""
        # Arrange
        mock_sessions, mock_connections = mock_dynamodb_tables
        
        # Mock get_item to return existing session
        mock_sessions.get_item.return_value = {
            'Item': {
                'sessionId': 'blessed-shepherd-427',
                'speakerId': 'user-123',
                'status': 'active',
            }
        }
        
        # Mock update_item for marking session as ended
        mock_sessions.update_item.return_value = {}
        
        # Mock connections query to return empty list
        mock_connections.query.return_value = {'Items': []}
        
        event = create_http_event(
            'DELETE',
            '/sessions/blessed-shepherd-427',
            user_id='user-123'
        )
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 204
        
        # Verify DynamoDB operations
        mock_sessions.get_item.assert_called_once()
        mock_sessions.update_item.assert_called_once()
        
        # Verify update_item was called with correct parameters
        update_call = mock_sessions.update_item.call_args
        assert update_call[1]['Key'] == {'sessionId': 'blessed-shepherd-427'}
        assert ':status' in update_call[1]['ExpressionAttributeValues']
        assert update_call[1]['ExpressionAttributeValues'][':status'] == 'ended'
    
    def test_delete_session_without_ownership_fails(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test delete_session without ownership."""
        # Arrange
        mock_sessions, _ = mock_dynamodb_tables
        
        # Mock get_item to return session owned by different user
        mock_sessions.get_item.return_value = {
            'Item': {
                'sessionId': 'blessed-shepherd-427',
                'speakerId': 'other-user',
                'status': 'active',
            }
        }
        
        event = create_http_event(
            'DELETE',
            '/sessions/blessed-shepherd-427',
            user_id='user-123'
        )
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 403
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Not authorized' in body['error']
    
    def test_delete_session_with_non_existent_session_fails(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test delete_session with non-existent session."""
        # Arrange
        mock_sessions, _ = mock_dynamodb_tables
        mock_sessions.get_item.return_value = {}
        
        event = create_http_event(
            'DELETE',
            '/sessions/non-existent',
            user_id='user-123'
        )
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Session not found' in body['error']
    
    def test_delete_session_with_dynamodb_error_fails(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test delete_session with DynamoDB error."""
        # Arrange
        mock_sessions, _ = mock_dynamodb_tables
        
        mock_sessions.get_item.return_value = {
            'Item': {
                'sessionId': 'blessed-shepherd-427',
                'speakerId': 'user-123',
                'status': 'active',
            }
        }
        
        mock_sessions.update_item.side_effect = ClientError(
            {'Error': {'Code': 'InternalServerError', 'Message': 'Internal error'}},
            'UpdateItem'
        )
        
        event = create_http_event(
            'DELETE',
            '/sessions/blessed-shepherd-427',
            user_id='user-123'
        )
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Failed to delete session' in body['error']


class TestHealthCheck:
    """Test suite for health check endpoint."""
    
    def test_health_check_succeeds(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test health check with healthy service."""
        # Arrange
        mock_sessions, _ = mock_dynamodb_tables
        mock_sessions.scan.return_value = {'Items': []}
        
        event = create_http_event('GET', '/health')
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'healthy'
        assert body['service'] == 'session-management-http-api'
        assert body['environment'] == 'test'
        assert 'timestamp' in body
        assert 'responseTimeMs' in body
        assert 'version' in body
    
    def test_health_check_with_dynamodb_error_fails(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test health check with DynamoDB error."""
        # Arrange
        mock_sessions, _ = mock_dynamodb_tables
        mock_sessions.scan.side_effect = ClientError(
            {'Error': {'Code': 'InternalServerError', 'Message': 'Internal error'}},
            'Scan'
        )
        
        event = create_http_event('GET', '/health')
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 503
        body = json.loads(response['body'])
        assert body['status'] == 'unhealthy'
        assert 'error' in body


class TestErrorHandling:
    """Test suite for error handling."""
    
    def test_invalid_route_returns_404(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test invalid route returns 404."""
        # Arrange
        event = create_http_event('GET', '/invalid-route')
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Not found' in body['error']
    
    def test_unhandled_exception_returns_500(
        self,
        mock_env,
        mock_dynamodb_tables
    ):
        """Test unhandled exception returns 500."""
        # Arrange
        event = {
            'requestContext': {}  # Missing required fields
        }
        
        # Act
        response = handler.lambda_handler(event, None)
        
        # Assert
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Internal server error' in body['error']
