"""
Integration tests for Connection Handler Lambda.
"""
import json
import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from moto import mock_dynamodb

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'connection_handler'))

import handler as connection_handler
from shared.data_access import SessionsRepository, ConnectionsRepository
from shared.data_access.dynamodb_client import DynamoDBClient


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables for tests."""
    monkeypatch.setenv('SESSIONS_TABLE', 'Sessions')
    monkeypatch.setenv('CONNECTIONS_TABLE', 'Connections')
    monkeypatch.setenv('RATE_LIMITS_TABLE', 'RateLimits')
    monkeypatch.setenv('AWS_REGION', 'us-east-1')
    monkeypatch.setenv('MAX_LISTENERS_PER_SESSION', '500')
    monkeypatch.setenv('SESSION_MAX_DURATION_HOURS', '2')


@pytest.fixture
def dynamodb_tables():
    """Create DynamoDB tables for testing."""
    with mock_dynamodb():
        client = DynamoDBClient()
        
        # Create Sessions table
        client.dynamodb.create_table(
            TableName='Sessions',
            KeySchema=[{'AttributeName': 'sessionId', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'sessionId', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Create Connections table with GSI
        client.dynamodb.create_table(
            TableName='Connections',
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
        
        # Create RateLimits table
        client.dynamodb.create_table(
            TableName='RateLimits',
            KeySchema=[{'AttributeName': 'identifier', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'identifier', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        
        yield client


def create_connect_event(action, query_params, authorizer_context=None):
    """Helper to create $connect event."""
    event = {
        'requestContext': {
            'connectionId': 'test-connection-123',
            'eventType': 'CONNECT',
            'identity': {
                'sourceIp': '192.168.1.1'
            }
        },
        'queryStringParameters': {
            'action': action,
            **query_params
        }
    }
    
    if authorizer_context:
        event['requestContext']['authorizer'] = authorizer_context
    
    return event


@patch('handler.language_validator')
@patch('handler.session_id_service')
def test_create_session_success(
    mock_session_id_service,
    mock_language_validator,
    dynamodb_tables,
    mock_env
):
    """Test successful speaker session creation."""
    # Mock session ID generation
    mock_session_id_service.generate_unique_session_id.return_value = 'golden-eagle-427'
    
    # Create event
    event = create_connect_event(
        action='createSession',
        query_params={
            'sourceLanguage': 'en',
            'qualityTier': 'standard'
        },
        authorizer_context={'userId': 'user-123'}
    )
    
    # Execute handler
    response = connection_handler.lambda_handler(event, None)
    
    # Verify response
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == 'sessionCreated'
    assert body['sessionId'] == 'golden-eagle-427'
    assert body['sourceLanguage'] == 'en'
    assert body['qualityTier'] == 'standard'
    
    # Verify session was created in DynamoDB
    sessions_repo = SessionsRepository('Sessions')
    session = sessions_repo.get_session('golden-eagle-427')
    assert session is not None
    assert session['speakerUserId'] == 'user-123'
    assert session['isActive'] is True
    assert session['listenerCount'] == 0


@patch('handler.language_validator')
def test_join_session_success(
    mock_language_validator,
    dynamodb_tables,
    mock_env
):
    """Test successful listener joining session."""
    # Create a session first
    sessions_repo = SessionsRepository('Sessions')
    sessions_repo.create_session(
        session_id='golden-eagle-427',
        speaker_connection_id='speaker-conn-123',
        speaker_user_id='user-123',
        source_language='en',
        quality_tier='standard'
    )
    
    # Mock language validation
    mock_language_validator.validate_target_language.return_value = None
    
    # Create event
    event = create_connect_event(
        action='joinSession',
        query_params={
            'sessionId': 'golden-eagle-427',
            'targetLanguage': 'es'
        }
    )
    
    # Execute handler
    response = connection_handler.lambda_handler(event, None)
    
    # Verify response
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == 'sessionJoined'
    assert body['sessionId'] == 'golden-eagle-427'
    assert body['targetLanguage'] == 'es'
    assert body['sourceLanguage'] == 'en'
    
    # Verify connection was created
    connections_repo = ConnectionsRepository('Connections')
    connection = connections_repo.get_connection('test-connection-123')
    assert connection is not None
    assert connection['role'] == 'listener'
    assert connection['targetLanguage'] == 'es'
    
    # Verify listener count was incremented
    session = sessions_repo.get_session('golden-eagle-427')
    assert session['listenerCount'] == 1


def test_join_session_not_found(dynamodb_tables, mock_env):
    """Test listener joining non-existent session."""
    event = create_connect_event(
        action='joinSession',
        query_params={
            'sessionId': 'nonexistent-session-999',
            'targetLanguage': 'es'
        }
    )
    
    response = connection_handler.lambda_handler(event, None)
    
    assert response['statusCode'] == 404
    body = json.loads(response['body'])
    assert body['code'] == 'SESSION_NOT_FOUND'


def test_join_inactive_session(dynamodb_tables, mock_env):
    """Test listener joining inactive session."""
    # Create inactive session
    sessions_repo = SessionsRepository('Sessions')
    sessions_repo.create_session(
        session_id='golden-eagle-427',
        speaker_connection_id='speaker-conn-123',
        speaker_user_id='user-123',
        source_language='en',
        quality_tier='standard'
    )
    sessions_repo.mark_session_inactive('golden-eagle-427')
    
    event = create_connect_event(
        action='joinSession',
        query_params={
            'sessionId': 'golden-eagle-427',
            'targetLanguage': 'es'
        }
    )
    
    response = connection_handler.lambda_handler(event, None)
    
    assert response['statusCode'] == 404
    body = json.loads(response['body'])
    assert body['code'] == 'SESSION_NOT_FOUND'


def test_join_session_at_capacity(
    dynamodb_tables,
    mock_env,
    monkeypatch
):
    """Test listener joining session at capacity."""
    # Create session with 2 listeners (at capacity)
    sessions_repo = SessionsRepository('Sessions')
    sessions_repo.create_session(
        session_id='golden-eagle-427',
        speaker_connection_id='speaker-conn-123',
        speaker_user_id='user-123',
        source_language='en',
        quality_tier='standard'
    )
    
    # Manually set listener count to capacity (2)
    sessions_repo.client.update_item(
        table_name='Sessions',
        key={'sessionId': 'golden-eagle-427'},
        update_expression='SET listenerCount = :count',
        expression_attribute_values={':count': 2}
    )
    
    # Patch MAX_LISTENERS_PER_SESSION in the handler module
    with patch.object(connection_handler, 'MAX_LISTENERS_PER_SESSION', 2):
        # Mock boto3 clients for language validation
        with patch('boto3.client') as mock_boto_client:
            # Mock Translate client
            mock_translate = MagicMock()
            mock_translate.list_languages.return_value = {
                'Languages': [
                    {'LanguageCode': 'en'},
                    {'LanguageCode': 'es'}
                ]
            }
            
            # Mock Polly client
            mock_polly = MagicMock()
            mock_polly.describe_voices.return_value = {
                'Voices': [
                    {'LanguageCode': 'en-US'},
                    {'LanguageCode': 'es-ES'}
                ]
            }
            
            def client_factory(service_name, **kwargs):
                if service_name == 'translate':
                    return mock_translate
                elif service_name == 'polly':
                    return mock_polly
                else:
                    return MagicMock()
            
            mock_boto_client.side_effect = client_factory
            
            event = create_connect_event(
                action='joinSession',
                query_params={
                    'sessionId': 'golden-eagle-427',
                    'targetLanguage': 'es'
                }
            )
            
            response = connection_handler.lambda_handler(event, None)
            
            assert response['statusCode'] == 503
            body = json.loads(response['body'])
            assert body['code'] == 'SESSION_FULL'


@patch('handler.language_validator')
def test_unsupported_language(
    mock_language_validator,
    dynamodb_tables,
    mock_env
):
    """Test listener joining with unsupported language."""
    from shared.services.language_validator import UnsupportedLanguageError
    
    # Create session
    sessions_repo = SessionsRepository('Sessions')
    sessions_repo.create_session(
        session_id='golden-eagle-427',
        speaker_connection_id='speaker-conn-123',
        speaker_user_id='user-123',
        source_language='en',
        quality_tier='standard'
    )
    
    # Mock language validation to raise error
    mock_language_validator.validate_target_language.side_effect = UnsupportedLanguageError(
        "Target language 'xx' is not supported",
        'xx'
    )
    
    event = create_connect_event(
        action='joinSession',
        query_params={
            'sessionId': 'golden-eagle-427',
            'targetLanguage': 'xx'
        }
    )
    
    response = connection_handler.lambda_handler(event, None)
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['code'] == 'UNSUPPORTED_LANGUAGE'


def test_invalid_session_id_format(dynamodb_tables, mock_env):
    """Test validation of session ID format."""
    event = create_connect_event(
        action='joinSession',
        query_params={
            'sessionId': 'invalid-format',
            'targetLanguage': 'es'
        }
    )
    
    response = connection_handler.lambda_handler(event, None)
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['code'] == 'INVALID_PARAMETERS'


def test_invalid_language_code(dynamodb_tables, mock_env):
    """Test validation of language code format."""
    event = create_connect_event(
        action='createSession',
        query_params={
            'sourceLanguage': 'english',  # Should be 2-letter code
            'qualityTier': 'standard'
        },
        authorizer_context={'userId': 'user-123'}
    )
    
    response = connection_handler.lambda_handler(event, None)
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['code'] == 'INVALID_PARAMETERS'


def test_invalid_quality_tier(dynamodb_tables, mock_env):
    """Test validation of quality tier."""
    event = create_connect_event(
        action='createSession',
        query_params={
            'sourceLanguage': 'en',
            'qualityTier': 'ultra'  # Invalid tier
        },
        authorizer_context={'userId': 'user-123'}
    )
    
    response = connection_handler.lambda_handler(event, None)
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['code'] == 'INVALID_PARAMETERS'


def test_missing_authorizer_context(dynamodb_tables, mock_env):
    """Test speaker session creation without authentication."""
    event = create_connect_event(
        action='createSession',
        query_params={
            'sourceLanguage': 'en',
            'qualityTier': 'standard'
        }
        # No authorizer context
    )
    
    response = connection_handler.lambda_handler(event, None)
    
    assert response['statusCode'] == 401
    body = json.loads(response['body'])
    assert body['code'] == 'UNAUTHORIZED'


@patch('handler.rate_limit_service')
def test_rate_limit_exceeded(
    mock_rate_limit_service,
    dynamodb_tables,
    mock_env
):
    """Test rate limit enforcement."""
    from shared.data_access.exceptions import RateLimitExceededError
    
    # Mock rate limit check to raise error
    mock_rate_limit_service.check_connection_attempt_limit.side_effect = RateLimitExceededError(
        "Rate limit exceeded",
        retry_after=60
    )
    
    event = create_connect_event(
        action='joinSession',
        query_params={
            'sessionId': 'golden-eagle-427',
            'targetLanguage': 'es'
        }
    )
    
    response = connection_handler.lambda_handler(event, None)
    
    assert response['statusCode'] == 429
    body = json.loads(response['body'])
    assert body['code'] == 'RATE_LIMIT_EXCEEDED'
    assert body['details']['retryAfter'] == 60
