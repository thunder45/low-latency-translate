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
        # Mock boto3 clients for language validation and metrics
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
            
            # Mock CloudWatch client for metrics
            mock_cloudwatch = MagicMock()
            
            def client_factory(service_name, **kwargs):
                if service_name == 'translate':
                    return mock_translate
                elif service_name == 'polly':
                    return mock_polly
                elif service_name == 'cloudwatch':
                    return mock_cloudwatch
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



def create_message_event(connection_id, action, body=None):
    """Helper to create MESSAGE event for control messages."""
    message_body = {'action': action}
    if body:
        message_body.update(body)
    
    return {
        'requestContext': {
            'connectionId': connection_id,
            'eventType': 'MESSAGE',
            'routeKey': '$default',
            'identity': {
                'sourceIp': '192.168.1.1'
            }
        },
        'body': json.dumps(message_body)
    }


@patch('handler.apigw_management_client')
@patch('handler.metrics_publisher')
def test_pause_broadcast_success(
    mock_metrics,
    mock_apigw,
    mock_env,
    dynamodb_tables
):
    """Test successful pause broadcast."""
    # Create session and speaker connection
    sessions_repo = SessionsRepository('Sessions')
    connections_repo = ConnectionsRepository('Connections')
    
    session_id = 'test-session-123'
    connection_id = 'speaker-conn-123'
    
    sessions_repo.create_session(
        session_id=session_id,
        speaker_connection_id=connection_id,
        speaker_user_id='user-123',
        source_language='en',
        quality_tier='standard'
    )
    
    connections_repo.create_connection(
        connection_id=connection_id,
        session_id=session_id,
        role='speaker'
    )
    
    # Create listener connections
    for i in range(3):
        connections_repo.create_connection(
            connection_id=f'listener-{i}',
            session_id=session_id,
            role='listener',
            target_language='es'
        )
    
    # Mock API Gateway client
    mock_apigw.post_to_connection = Mock()
    
    # Create pause broadcast event
    event = create_message_event(connection_id, 'pauseBroadcast')
    
    # Execute handler
    response = connection_handler.lambda_handler(event, {})
    
    # Verify response
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == 'broadcastPaused'
    assert body['sessionId'] == session_id
    assert body['broadcastState']['isPaused'] is True
    assert body['listenersNotified'] == 3
    
    # Verify broadcast state updated
    session = sessions_repo.get_session(session_id)
    assert session['broadcastState']['isPaused'] is True
    
    # Verify listeners notified
    assert mock_apigw.post_to_connection.call_count == 3


@patch('handler.apigw_management_client')
@patch('handler.metrics_publisher')
def test_resume_broadcast_success(
    mock_metrics,
    mock_apigw,
    mock_env,
    dynamodb_tables
):
    """Test successful resume broadcast."""
    # Create session and speaker connection
    sessions_repo = SessionsRepository('Sessions')
    connections_repo = ConnectionsRepository('Connections')
    
    session_id = 'test-session-123'
    connection_id = 'speaker-conn-123'
    
    sessions_repo.create_session(
        session_id=session_id,
        speaker_connection_id=connection_id,
        speaker_user_id='user-123',
        source_language='en',
        quality_tier='standard'
    )
    
    # Pause broadcast first
    sessions_repo.pause_broadcast(session_id)
    
    connections_repo.create_connection(
        connection_id=connection_id,
        session_id=session_id,
        role='speaker'
    )
    
    # Mock API Gateway client
    mock_apigw.post_to_connection = Mock()
    
    # Create resume broadcast event
    event = create_message_event(connection_id, 'resumeBroadcast')
    
    # Execute handler
    response = connection_handler.lambda_handler(event, {})
    
    # Verify response
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == 'broadcastResumed'
    assert body['sessionId'] == session_id
    assert body['broadcastState']['isPaused'] is False
    assert 'pauseDuration' in body
    
    # Verify broadcast state updated
    session = sessions_repo.get_session(session_id)
    assert session['broadcastState']['isPaused'] is False


@patch('handler.apigw_management_client')
@patch('handler.metrics_publisher')
def test_mute_broadcast_success(
    mock_metrics,
    mock_apigw,
    mock_env,
    dynamodb_tables
):
    """Test successful mute broadcast."""
    # Create session and speaker connection
    sessions_repo = SessionsRepository('Sessions')
    connections_repo = ConnectionsRepository('Connections')
    
    session_id = 'test-session-123'
    connection_id = 'speaker-conn-123'
    
    sessions_repo.create_session(
        session_id=session_id,
        speaker_connection_id=connection_id,
        speaker_user_id='user-123',
        source_language='en',
        quality_tier='standard'
    )
    
    connections_repo.create_connection(
        connection_id=connection_id,
        session_id=session_id,
        role='speaker'
    )
    
    # Mock API Gateway client
    mock_apigw.post_to_connection = Mock()
    
    # Create mute broadcast event
    event = create_message_event(connection_id, 'muteBroadcast')
    
    # Execute handler
    response = connection_handler.lambda_handler(event, {})
    
    # Verify response
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == 'broadcastMuted'
    assert body['sessionId'] == session_id
    assert body['broadcastState']['isMuted'] is True
    
    # Verify broadcast state updated
    session = sessions_repo.get_session(session_id)
    assert session['broadcastState']['isMuted'] is True


@patch('handler.apigw_management_client')
@patch('handler.metrics_publisher')
def test_unmute_broadcast_success(
    mock_metrics,
    mock_apigw,
    mock_env,
    dynamodb_tables
):
    """Test successful unmute broadcast."""
    # Create session and speaker connection
    sessions_repo = SessionsRepository('Sessions')
    connections_repo = ConnectionsRepository('Connections')
    
    session_id = 'test-session-123'
    connection_id = 'speaker-conn-123'
    
    sessions_repo.create_session(
        session_id=session_id,
        speaker_connection_id=connection_id,
        speaker_user_id='user-123',
        source_language='en',
        quality_tier='standard'
    )
    
    # Mute broadcast first
    sessions_repo.mute_broadcast(session_id)
    
    connections_repo.create_connection(
        connection_id=connection_id,
        session_id=session_id,
        role='speaker'
    )
    
    # Mock API Gateway client
    mock_apigw.post_to_connection = Mock()
    
    # Create unmute broadcast event
    event = create_message_event(connection_id, 'unmuteBroadcast')
    
    # Execute handler
    response = connection_handler.lambda_handler(event, {})
    
    # Verify response
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == 'broadcastUnmuted'
    assert body['sessionId'] == session_id
    assert body['broadcastState']['isMuted'] is False
    
    # Verify broadcast state updated
    session = sessions_repo.get_session(session_id)
    assert session['broadcastState']['isMuted'] is False


@patch('handler.apigw_management_client')
@patch('handler.metrics_publisher')
def test_set_volume_success(
    mock_metrics,
    mock_apigw,
    mock_env,
    dynamodb_tables
):
    """Test successful set volume."""
    # Create session and speaker connection
    sessions_repo = SessionsRepository('Sessions')
    connections_repo = ConnectionsRepository('Connections')
    
    session_id = 'test-session-123'
    connection_id = 'speaker-conn-123'
    
    sessions_repo.create_session(
        session_id=session_id,
        speaker_connection_id=connection_id,
        speaker_user_id='user-123',
        source_language='en',
        quality_tier='standard'
    )
    
    connections_repo.create_connection(
        connection_id=connection_id,
        session_id=session_id,
        role='speaker'
    )
    
    # Mock API Gateway client
    mock_apigw.post_to_connection = Mock()
    
    # Create set volume event
    event = create_message_event(
        connection_id,
        'setVolume',
        {'volumeLevel': 0.75}
    )
    
    # Execute handler
    response = connection_handler.lambda_handler(event, {})
    
    # Verify response
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == 'volumeChanged'
    assert body['sessionId'] == session_id
    assert body['volumeLevel'] == 0.75
    assert body['broadcastState']['volume'] == 0.75
    
    # Verify broadcast state updated
    session = sessions_repo.get_session(session_id)
    assert float(session['broadcastState']['volume']) == 0.75


@patch('handler.metrics_publisher')
def test_set_volume_invalid_range(
    mock_metrics,
    mock_env,
    dynamodb_tables
):
    """Test set volume with invalid range."""
    # Create session and speaker connection
    sessions_repo = SessionsRepository('Sessions')
    connections_repo = ConnectionsRepository('Connections')
    
    session_id = 'test-session-123'
    connection_id = 'speaker-conn-123'
    
    sessions_repo.create_session(
        session_id=session_id,
        speaker_connection_id=connection_id,
        speaker_user_id='user-123',
        source_language='en',
        quality_tier='standard'
    )
    
    connections_repo.create_connection(
        connection_id=connection_id,
        session_id=session_id,
        role='speaker'
    )
    
    # Create set volume event with invalid value
    event = create_message_event(
        connection_id,
        'setVolume',
        {'volumeLevel': 1.5}
    )
    
    # Execute handler
    response = connection_handler.lambda_handler(event, {})
    
    # Verify error response
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['code'] == 'INVALID_PARAMETER'
    assert 'between 0.0 and 1.0' in body['message']


@patch('handler.apigw_management_client')
@patch('handler.metrics_publisher')
def test_speaker_state_change_success(
    mock_metrics,
    mock_apigw,
    mock_env,
    dynamodb_tables
):
    """Test successful speaker state change."""
    # Create session and speaker connection
    sessions_repo = SessionsRepository('Sessions')
    connections_repo = ConnectionsRepository('Connections')
    
    session_id = 'test-session-123'
    connection_id = 'speaker-conn-123'
    
    sessions_repo.create_session(
        session_id=session_id,
        speaker_connection_id=connection_id,
        speaker_user_id='user-123',
        source_language='en',
        quality_tier='standard'
    )
    
    connections_repo.create_connection(
        connection_id=connection_id,
        session_id=session_id,
        role='speaker'
    )
    
    # Mock API Gateway client
    mock_apigw.post_to_connection = Mock()
    
    # Create speaker state change event
    event = create_message_event(
        connection_id,
        'speakerStateChange',
        {
            'state': {
                'isPaused': True,
                'isMuted': False,
                'volume': 0.8
            }
        }
    )
    
    # Execute handler
    response = connection_handler.lambda_handler(event, {})
    
    # Verify response
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == 'speakerStateChanged'
    assert body['sessionId'] == session_id
    assert body['broadcastState']['isPaused'] is True
    assert body['broadcastState']['isMuted'] is False
    assert body['broadcastState']['volume'] == 0.8
    
    # Verify broadcast state updated
    session = sessions_repo.get_session(session_id)
    assert session['broadcastState']['isPaused'] is True
    assert session['broadcastState']['isMuted'] is False
    assert float(session['broadcastState']['volume']) == 0.8


@patch('handler.metrics_publisher')
def test_pause_playback_listener_success(
    mock_metrics,
    mock_env,
    dynamodb_tables
):
    """Test successful pause playback for listener."""
    # Create session and listener connection
    sessions_repo = SessionsRepository('Sessions')
    connections_repo = ConnectionsRepository('Connections')
    
    session_id = 'test-session-123'
    connection_id = 'listener-conn-123'
    
    sessions_repo.create_session(
        session_id=session_id,
        speaker_connection_id='speaker-123',
        speaker_user_id='user-123',
        source_language='en',
        quality_tier='standard'
    )
    
    connections_repo.create_connection(
        connection_id=connection_id,
        session_id=session_id,
        role='listener',
        target_language='es'
    )
    
    # Create pause playback event
    event = create_message_event(connection_id, 'pausePlayback')
    
    # Execute handler
    response = connection_handler.lambda_handler(event, {})
    
    # Verify response
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == 'playbackPaused'
    assert body['sessionId'] == session_id


@patch('handler.language_validator')
@patch('handler.metrics_publisher')
def test_change_language_success(
    mock_metrics,
    mock_language_validator,
    mock_env,
    dynamodb_tables
):
    """Test successful change language for listener."""
    # Create session and listener connection
    sessions_repo = SessionsRepository('Sessions')
    connections_repo = ConnectionsRepository('Connections')
    
    session_id = 'test-session-123'
    connection_id = 'listener-conn-123'
    
    sessions_repo.create_session(
        session_id=session_id,
        speaker_connection_id='speaker-123',
        speaker_user_id='user-123',
        source_language='en',
        quality_tier='standard'
    )
    
    connections_repo.create_connection(
        connection_id=connection_id,
        session_id=session_id,
        role='listener',
        target_language='es',
        ip_address='192.168.1.1'
    )
    
    # Mock language validator
    mock_language_validator.validate_target_language = Mock()
    
    # Create change language event
    event = create_message_event(
        connection_id,
        'changeLanguage',
        {'targetLanguage': 'fr'}
    )
    
    # Execute handler
    response = connection_handler.lambda_handler(event, {})
    
    # Verify response
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['type'] == 'languageChanged'
    assert body['sessionId'] == session_id
    assert body['targetLanguage'] == 'fr'
    assert body['sourceLanguage'] == 'en'
    
    # Verify connection updated
    connection = connections_repo.get_connection(connection_id)
    assert connection['targetLanguage'] == 'fr'


@patch('handler.metrics_publisher')
def test_unauthorized_speaker_action_for_listener(
    mock_metrics,
    mock_env,
    dynamodb_tables
):
    """Test unauthorized speaker action from listener."""
    # Create session and listener connection
    sessions_repo = SessionsRepository('Sessions')
    connections_repo = ConnectionsRepository('Connections')
    
    session_id = 'test-session-123'
    connection_id = 'listener-conn-123'
    
    sessions_repo.create_session(
        session_id=session_id,
        speaker_connection_id='speaker-123',
        speaker_user_id='user-123',
        source_language='en',
        quality_tier='standard'
    )
    
    connections_repo.create_connection(
        connection_id=connection_id,
        session_id=session_id,
        role='listener',
        target_language='es'
    )
    
    # Create pause broadcast event (speaker action)
    event = create_message_event(connection_id, 'pauseBroadcast')
    
    # Execute handler
    response = connection_handler.lambda_handler(event, {})
    
    # Verify error response
    assert response['statusCode'] == 403
    body = json.loads(response['body'])
    assert body['code'] == 'UNAUTHORIZED_ACTION'
    assert 'speaker role' in body['message']


@patch('handler.metrics_publisher')
def test_unauthorized_listener_action_for_speaker(
    mock_metrics,
    mock_env,
    dynamodb_tables
):
    """Test unauthorized listener action from speaker."""
    # Create session and speaker connection
    sessions_repo = SessionsRepository('Sessions')
    connections_repo = ConnectionsRepository('Connections')
    
    session_id = 'test-session-123'
    connection_id = 'speaker-conn-123'
    
    sessions_repo.create_session(
        session_id=session_id,
        speaker_connection_id=connection_id,
        speaker_user_id='user-123',
        source_language='en',
        quality_tier='standard'
    )
    
    connections_repo.create_connection(
        connection_id=connection_id,
        session_id=session_id,
        role='speaker'
    )
    
    # Create change language event (listener action)
    event = create_message_event(
        connection_id,
        'changeLanguage',
        {'targetLanguage': 'fr'}
    )
    
    # Execute handler
    response = connection_handler.lambda_handler(event, {})
    
    # Verify error response
    assert response['statusCode'] == 403
    body = json.loads(response['body'])
    assert body['code'] == 'UNAUTHORIZED_ACTION'
    assert 'listener role' in body['message']


@patch('handler.metrics_publisher')
def test_connection_not_found_for_control_message(
    mock_metrics,
    mock_env,
    dynamodb_tables
):
    """Test control message with non-existent connection."""
    # Create pause broadcast event with non-existent connection
    event = create_message_event('non-existent-conn', 'pauseBroadcast')
    
    # Execute handler
    response = connection_handler.lambda_handler(event, {})
    
    # Verify error response
    assert response['statusCode'] == 404
    body = json.loads(response['body'])
    assert body['code'] == 'CONNECTION_NOT_FOUND'
