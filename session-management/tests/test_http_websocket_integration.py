"""
Integration tests for HTTP + WebSocket hybrid architecture.

Simplified tests focusing on HTTP API integration with DynamoDB.
WebSocket connection testing is covered by existing test_e2e_integration.py
"""
import json
from unittest.mock import patch
import pytest
from moto import mock_dynamodb
import boto3


@pytest.fixture
def dynamodb_tables(aws_credentials, env_vars):
    """Create DynamoDB tables for testing."""
    with mock_dynamodb():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        sessions_table = dynamodb.create_table(
            TableName='Sessions-test',
            KeySchema=[{'AttributeName': 'sessionId', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'sessionId', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        
        connections_table = dynamodb.create_table(
            TableName='Connections-test',
            KeySchema=[{'AttributeName': 'connectionId', 'KeyType': 'HASH'}],
            AttributeDefinitions=[
                {'AttributeName': 'connectionId', 'AttributeType': 'S'},
                {'AttributeName': 'sessionId', 'AttributeType': 'S'},
                {'AttributeName': 'targetLanguage', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[{
                'IndexName': 'sessionId-targetLanguage-index',
                'KeySchema': [
                    {'AttributeName': 'sessionId', 'KeyType': 'HASH'},
                    {'AttributeName': 'targetLanguage', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'}
            }],
            BillingMode='PAY_PER_REQUEST'
        )
        
        yield sessions_table, connections_table


@pytest.fixture
def setup_http_handler(env_vars, aws_credentials):
    """Set up HTTP session handler."""
    import sys
    import os
    import importlib.util
    
    modules_to_remove = [k for k in sys.modules.keys() if 'http_session_handler' in k]
    for mod in modules_to_remove:
        del sys.modules[mod]
    
    handler_path = os.path.join(
        os.path.dirname(__file__), '..', 'lambda', 
        'http_session_handler', 'handler.py'
    )
    
    spec = importlib.util.spec_from_file_location('http_session_handler_module', handler_path)
    handler_module = importlib.util.module_from_spec(spec)
    
    handler_parent_dir = os.path.dirname(handler_path)
    sys.path.insert(0, handler_parent_dir)
    
    try:
        spec.loader.exec_module(handler_module)
    finally:
        if handler_parent_dir in sys.path:
            sys.path.remove(handler_parent_dir)
    
    return handler_module


class TestHTTPSessionLifecycle:
    """Test 16.1-16.4: HTTP session lifecycle operations."""
    
    def test_create_and_retrieve_session(self, dynamodb_tables, setup_http_handler):
        """Test session creation and retrieval via HTTP."""
        sessions_table, connections_table = dynamodb_tables
        http_handler = setup_http_handler
        user_id = 'test-user-123'
        
        create_event = {
            'requestContext': {
                'http': {'method': 'POST', 'path': '/sessions'},
                'requestId': 'req-1',
                'authorizer': {'jwt': {'claims': {'sub': user_id, 'email': 'test@example.com'}}}
            },
            'body': json.dumps({'sourceLanguage': 'en', 'qualityTier': 'standard'})
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            response = http_handler.lambda_handler(create_event, {})
        
        assert response['statusCode'] == 201
        body = json.loads(response['body'])
        session_id = body['sessionId']
        assert body['speakerId'] == user_id
        
        session = sessions_table.get_item(Key={'sessionId': session_id})['Item']
        assert session['speakerId'] == user_id
        assert session['status'] == 'active'
    
    def test_get_nonexistent_session_returns_404(self, dynamodb_tables, setup_http_handler):
        """Test GET for non-existent session returns 404."""
        sessions_table, connections_table = dynamodb_tables
        http_handler = setup_http_handler
        
        get_event = {
            'requestContext': {
                'http': {'method': 'GET', 'path': '/sessions/invalid-id'},
                'requestId': 'req-2'
            }
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            response = http_handler.lambda_handler(get_event, {})
        
        assert response['statusCode'] == 404
    
    def test_delete_session_marks_as_ended(self, dynamodb_tables, setup_http_handler):
        """Test session deletion marks it as ended."""
        sessions_table, connections_table = dynamodb_tables
        http_handler = setup_http_handler
        user_id = 'test-user-456'
        
        create_event = {
            'requestContext': {
                'http': {'method': 'POST', 'path': '/sessions'},
                'requestId': 'req-3',
                'authorizer': {'jwt': {'claims': {'sub': user_id, 'email': 'test@example.com'}}}
            },
            'body': json.dumps({'sourceLanguage': 'en', 'qualityTier': 'standard'})
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            create_response = http_handler.lambda_handler(create_event, {})
        
        session_id = json.loads(create_response['body'])['sessionId']
        
        delete_event = {
            'requestContext': {
                'http': {'method': 'DELETE', 'path': f'/sessions/{session_id}'},
                'requestId': 'req-4',
                'authorizer': {'jwt': {'claims': {'sub': user_id, 'email': 'test@example.com'}}}
            }
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            delete_response = http_handler.lambda_handler(delete_event, {})
        
        assert delete_response['statusCode'] == 204
        session = sessions_table.get_item(Key={'sessionId': session_id})['Item']
        assert session['status'] == 'ended'
    
    def test_update_session_status(self, dynamodb_tables, setup_http_handler):
        """Test session status update via PATCH."""
        sessions_table, connections_table = dynamodb_tables
        http_handler = setup_http_handler
        user_id = 'test-user-789'
        
        create_event = {
            'requestContext': {
                'http': {'method': 'POST', 'path': '/sessions'},
                'requestId': 'req-5',
                'authorizer': {'jwt': {'claims': {'sub': user_id, 'email': 'test@example.com'}}}
            },
            'body': json.dumps({'sourceLanguage': 'en', 'qualityTier': 'standard'})
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            create_response = http_handler.lambda_handler(create_event, {})
        
        session_id = json.loads(create_response['body'])['sessionId']
        
        update_event = {
            'requestContext': {
                'http': {'method': 'PATCH', 'path': f'/sessions/{session_id}'},
                'requestId': 'req-6',
                'authorizer': {'jwt': {'claims': {'sub': user_id, 'email': 'test@example.com'}}}
            },
            'body': json.dumps({'status': 'paused'})
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            update_response = http_handler.lambda_handler(update_event, {})
        
        assert update_response['statusCode'] == 200
        body = json.loads(update_response['body'])
        assert body['status'] == 'paused'


class TestJWTAuthentication:
    """Test 16.5: JWT authentication and authorization."""
    
    def test_request_without_token_fails(self, dynamodb_tables, setup_http_handler):
        """Test HTTP requests without token fail."""
        sessions_table, connections_table = dynamodb_tables
        http_handler = setup_http_handler
        
        create_event = {
            'requestContext': {
                'http': {'method': 'POST', 'path': '/sessions'},
                'requestId': 'req-7'
            },
            'body': json.dumps({'sourceLanguage': 'en', 'qualityTier': 'standard'})
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            response = http_handler.lambda_handler(create_event, {})
        
        assert response['statusCode'] in [400, 401]
    
    def test_request_with_valid_token_succeeds(self, dynamodb_tables, setup_http_handler):
        """Test HTTP requests with valid token succeed."""
        sessions_table, connections_table = dynamodb_tables
        http_handler = setup_http_handler
        
        create_event = {
            'requestContext': {
                'http': {'method': 'POST', 'path': '/sessions'},
                'requestId': 'req-8',
                'authorizer': {'jwt': {'claims': {'sub': 'user-123', 'email': 'test@example.com'}}}
            },
            'body': json.dumps({'sourceLanguage': 'en', 'qualityTier': 'standard'})
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            response = http_handler.lambda_handler(create_event, {})
        
        assert response['statusCode'] == 201
    
    def test_update_with_wrong_user_returns_403(self, dynamodb_tables, setup_http_handler):
        """Test update with wrong user returns 403."""
        sessions_table, connections_table = dynamodb_tables
        http_handler = setup_http_handler
        
        create_event = {
            'requestContext': {
                'http': {'method': 'POST', 'path': '/sessions'},
                'requestId': 'req-9',
                'authorizer': {'jwt': {'claims': {'sub': 'owner-123', 'email': 'owner@example.com'}}}
            },
            'body': json.dumps({'sourceLanguage': 'en', 'qualityTier': 'standard'})
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            create_response = http_handler.lambda_handler(create_event, {})
        
        session_id = json.loads(create_response['body'])['sessionId']
        
        update_event = {
            'requestContext': {
                'http': {'method': 'PATCH', 'path': f'/sessions/{session_id}'},
                'requestId': 'req-10',
                'authorizer': {'jwt': {'claims': {'sub': 'other-456', 'email': 'other@example.com'}}}
            },
            'body': json.dumps({'status': 'paused'})
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            response = http_handler.lambda_handler(update_event, {})
        
        assert response['statusCode'] == 403
    
    def test_delete_with_wrong_user_returns_403(self, dynamodb_tables, setup_http_handler):
        """Test delete with wrong user returns 403."""
        sessions_table, connections_table = dynamodb_tables
        http_handler = setup_http_handler
        
        create_event = {
            'requestContext': {
                'http': {'method': 'POST', 'path': '/sessions'},
                'requestId': 'req-11',
                'authorizer': {'jwt': {'claims': {'sub': 'owner-789', 'email': 'owner@example.com'}}}
            },
            'body': json.dumps({'sourceLanguage': 'en', 'qualityTier': 'standard'})
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            create_response = http_handler.lambda_handler(create_event, {})
        
        session_id = json.loads(create_response['body'])['sessionId']
        
        delete_event = {
            'requestContext': {
                'http': {'method': 'DELETE', 'path': f'/sessions/{session_id}'},
                'requestId': 'req-12',
                'authorizer': {'jwt': {'claims': {'sub': 'other-012', 'email': 'other@example.com'}}}
            }
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            response = http_handler.lambda_handler(delete_event, {})
        
        assert response['statusCode'] == 403
    
    def test_delete_session_marks_as_ended(self, dynamodb_tables, setup_http_handler):
        """Test session deletion marks it as ended."""
        sessions_table, connections_table = dynamodb_tables
        http_handler = setup_http_handler
        user_id = 'test-user-456'
        
        create_event = {
            'requestContext': {
                'http': {'method': 'POST', 'path': '/sessions'},
                'requestId': 'req-3',
                'authorizer': {'jwt': {'claims': {'sub': user_id, 'email': 'test@example.com'}}}
            },
            'body': json.dumps({'sourceLanguage': 'en', 'qualityTier': 'standard'})
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            create_response = http_handler.lambda_handler(create_event, {})
        
        session_id = json.loads(create_response['body'])['sessionId']
        
        delete_event = {
            'requestContext': {
                'http': {'method': 'DELETE', 'path': f'/sessions/{session_id}'},
                'requestId': 'req-4',
                'authorizer': {'jwt': {'claims': {'sub': user_id, 'email': 'test@example.com'}}}
            }
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            delete_response = http_handler.lambda_handler(delete_event, {})
        
        assert delete_response['statusCode'] == 204
        session = sessions_table.get_item(Key={'sessionId': session_id})['Item']
        assert session['status'] == 'ended'
    
    def test_update_session_status(self, dynamodb_tables, setup_http_handler):
        """Test session status update via PATCH."""
        sessions_table, connections_table = dynamodb_tables
        http_handler = setup_http_handler
        user_id = 'test-user-789'
        
        create_event = {
            'requestContext': {
                'http': {'method': 'POST', 'path': '/sessions'},
                'requestId': 'req-5',
                'authorizer': {'jwt': {'claims': {'sub': user_id, 'email': 'test@example.com'}}}
            },
            'body': json.dumps({'sourceLanguage': 'en', 'qualityTier': 'standard'})
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            create_response = http_handler.lambda_handler(create_event, {})
        
        session_id = json.loads(create_response['body'])['sessionId']
        
        update_event = {
            'requestContext': {
                'http': {'method': 'PATCH', 'path': f'/sessions/{session_id}'},
                'requestId': 'req-6',
                'authorizer': {'jwt': {'claims': {'sub': user_id, 'email': 'test@example.com'}}}
            },
            'body': json.dumps({'status': 'paused'})
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            update_response = http_handler.lambda_handler(update_event, {})
        
        assert update_response['statusCode'] == 200
        body = json.loads(update_response['body'])
        assert body['status'] == 'paused'


class TestJWTAuthentication:
    """Test 16.5: JWT authentication and authorization."""
    
    def test_request_without_token_fails(self, dynamodb_tables, setup_http_handler):
        """Test HTTP requests without token fail."""
        sessions_table, connections_table = dynamodb_tables
        http_handler = setup_http_handler
        
        create_event = {
            'requestContext': {
                'http': {'method': 'POST', 'path': '/sessions'},
                'requestId': 'req-7'
            },
            'body': json.dumps({'sourceLanguage': 'en', 'qualityTier': 'standard'})
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            response = http_handler.lambda_handler(create_event, {})
        
        assert response['statusCode'] in [400, 401]
    
    def test_request_with_valid_token_succeeds(self, dynamodb_tables, setup_http_handler):
        """Test HTTP requests with valid token succeed."""
        sessions_table, connections_table = dynamodb_tables
        http_handler = setup_http_handler
        
        create_event = {
            'requestContext': {
                'http': {'method': 'POST', 'path': '/sessions'},
                'requestId': 'req-8',
                'authorizer': {'jwt': {'claims': {'sub': 'user-123', 'email': 'test@example.com'}}}
            },
            'body': json.dumps({'sourceLanguage': 'en', 'qualityTier': 'standard'})
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            response = http_handler.lambda_handler(create_event, {})
        
        assert response['statusCode'] == 201
    
    def test_update_with_wrong_user_returns_403(self, dynamodb_tables, setup_http_handler):
        """Test update with wrong user returns 403."""
        sessions_table, connections_table = dynamodb_tables
        http_handler = setup_http_handler
        
        create_event = {
            'requestContext': {
                'http': {'method': 'POST', 'path': '/sessions'},
                'requestId': 'req-9',
                'authorizer': {'jwt': {'claims': {'sub': 'owner-123', 'email': 'owner@example.com'}}}
            },
            'body': json.dumps({'sourceLanguage': 'en', 'qualityTier': 'standard'})
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            create_response = http_handler.lambda_handler(create_event, {})
        
        session_id = json.loads(create_response['body'])['sessionId']
        
        update_event = {
            'requestContext': {
                'http': {'method': 'PATCH', 'path': f'/sessions/{session_id}'},
                'requestId': 'req-10',
                'authorizer': {'jwt': {'claims': {'sub': 'other-456', 'email': 'other@example.com'}}}
            },
            'body': json.dumps({'status': 'paused'})
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            response = http_handler.lambda_handler(update_event, {})
        
        assert response['statusCode'] == 403
    
    def test_delete_with_wrong_user_returns_403(self, dynamodb_tables, setup_http_handler):
        """Test delete with wrong user returns 403."""
        sessions_table, connections_table = dynamodb_tables
        http_handler = setup_http_handler
        
        create_event = {
            'requestContext': {
                'http': {'method': 'POST', 'path': '/sessions'},
                'requestId': 'req-11',
                'authorizer': {'jwt': {'claims': {'sub': 'owner-789', 'email': 'owner@example.com'}}}
            },
            'body': json.dumps({'sourceLanguage': 'en', 'qualityTier': 'standard'})
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            create_response = http_handler.lambda_handler(create_event, {})
        
        session_id = json.loads(create_response['body'])['sessionId']
        
        delete_event = {
            'requestContext': {
                'http': {'method': 'DELETE', 'path': f'/sessions/{session_id}'},
                'requestId': 'req-12',
                'authorizer': {'jwt': {'claims': {'sub': 'other-012', 'email': 'other@example.com'}}}
            }
        }
        
        with patch.object(http_handler, 'sessions_table', sessions_table), \
             patch.object(http_handler, 'connections_table', connections_table):
            response = http_handler.lambda_handler(delete_event, {})
        
        assert response['statusCode'] == 403
