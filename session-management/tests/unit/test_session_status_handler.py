"""
Unit tests for session status handler.
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

# Import handler functions
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'session_status_handler'))

import handler as session_status_handler

lambda_handler = session_status_handler.lambda_handler
handle_get_session_status = session_status_handler.handle_get_session_status
get_session_status = session_status_handler.get_session_status
aggregate_language_distribution = session_status_handler.aggregate_language_distribution
handle_periodic_updates = session_status_handler.handle_periodic_updates
get_all_active_sessions = session_status_handler.get_all_active_sessions
send_status_to_speaker = session_status_handler.send_status_to_speaker


@pytest.fixture
def mock_sessions_repo():
    """Mock sessions repository."""
    with patch('handler.sessions_repo') as mock:
        yield mock


@pytest.fixture
def mock_connections_repo():
    """Mock connections repository."""
    with patch('handler.connections_repo') as mock:
        yield mock


@pytest.fixture
def mock_metrics_publisher():
    """Mock metrics publisher."""
    with patch('handler.metrics_publisher') as mock:
        yield mock


@pytest.fixture
def sample_session():
    """Sample session record."""
    return {
        'sessionId': 'golden-eagle-427',
        'speakerConnectionId': 'speaker-conn-123',
        'speakerUserId': 'user-123',
        'sourceLanguage': 'en',
        'qualityTier': 'standard',
        'createdAt': 1699500000000,
        'isActive': True,
        'listenerCount': 42,
        'broadcastState': {
            'isActive': True,
            'isPaused': False,
            'isMuted': False,
            'volume': Decimal('1.0'),
            'lastStateChange': 1699500000000
        }
    }


@pytest.fixture
def sample_listener_connections():
    """Sample listener connections."""
    return [
        {
            'connectionId': 'listener-1',
            'sessionId': 'golden-eagle-427',
            'role': 'listener',
            'targetLanguage': 'es',
            'connectedAt': 1699500000000
        },
        {
            'connectionId': 'listener-2',
            'sessionId': 'golden-eagle-427',
            'role': 'listener',
            'targetLanguage': 'es',
            'connectedAt': 1699500000000
        },
        {
            'connectionId': 'listener-3',
            'sessionId': 'golden-eagle-427',
            'role': 'listener',
            'targetLanguage': 'fr',
            'connectedAt': 1699500000000
        },
        {
            'connectionId': 'listener-4',
            'sessionId': 'golden-eagle-427',
            'role': 'listener',
            'targetLanguage': 'de',
            'connectedAt': 1699500000000
        }
    ]


class TestLambdaHandler:
    """Tests for lambda_handler function."""
    
    def test_lambda_handler_with_websocket_event(
        self,
        mock_sessions_repo,
        mock_connections_repo,
        mock_metrics_publisher,
        sample_session,
        sample_listener_connections
    ):
        """Test lambda handler with WebSocket MESSAGE event."""
        # Arrange
        event = {
            'requestContext': {
                'connectionId': 'speaker-conn-123',
                'eventType': 'MESSAGE'
            },
            'body': json.dumps({'action': 'getSessionStatus'})
        }
        context = Mock()
        
        mock_connections_repo.get_connection.return_value = {
            'connectionId': 'speaker-conn-123',
            'sessionId': 'golden-eagle-427',
            'role': 'speaker'
        }
        mock_sessions_repo.get_session.return_value = sample_session
        mock_connections_repo.get_listener_connections.return_value = sample_listener_connections
        
        # Act
        response = lambda_handler(event, context)
        
        # Assert
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['type'] == 'sessionStatus'
        assert body['sessionId'] == 'golden-eagle-427'
        assert body['listenerCount'] == 4
        assert 'languageDistribution' in body
        assert 'sessionDuration' in body
        assert 'broadcastState' in body
        assert body['updateReason'] == 'requested'
    
    def test_lambda_handler_with_eventbridge_event(
        self,
        mock_sessions_repo,
        mock_connections_repo
    ):
        """Test lambda handler with EventBridge scheduled event."""
        # Arrange
        event = {
            'source': 'aws.events',
            'detail-type': 'Scheduled Event'
        }
        context = Mock()
        
        with patch('handler.get_all_active_sessions') as mock_get_sessions:
            mock_get_sessions.return_value = []
            
            # Act
            response = lambda_handler(event, context)
            
            # Assert
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert 'updatesSent' in body
            assert 'updatesFailed' in body
    
    def test_lambda_handler_with_invalid_json(self):
        """Test lambda handler with invalid JSON in body."""
        # Arrange
        event = {
            'requestContext': {
                'connectionId': 'conn-123',
                'eventType': 'MESSAGE'
            },
            'body': 'invalid json'
        }
        context = Mock()
        
        # Act
        response = lambda_handler(event, context)
        
        # Assert
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['code'] == 'INVALID_MESSAGE'
    
    def test_lambda_handler_with_invalid_action(self):
        """Test lambda handler with invalid action."""
        # Arrange
        event = {
            'requestContext': {
                'connectionId': 'conn-123',
                'eventType': 'MESSAGE'
            },
            'body': json.dumps({'action': 'invalidAction'})
        }
        context = Mock()
        
        # Act
        response = lambda_handler(event, context)
        
        # Assert
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['code'] == 'INVALID_ACTION'


class TestHandleGetSessionStatus:
    """Tests for handle_get_session_status function."""
    
    def test_handle_get_session_status_success(
        self,
        mock_sessions_repo,
        mock_connections_repo,
        mock_metrics_publisher,
        sample_session,
        sample_listener_connections
    ):
        """Test successful session status query."""
        # Arrange
        connection_id = 'speaker-conn-123'
        
        mock_connections_repo.get_connection.return_value = {
            'connectionId': connection_id,
            'sessionId': 'golden-eagle-427',
            'role': 'speaker'
        }
        mock_sessions_repo.get_session.return_value = sample_session
        mock_connections_repo.get_listener_connections.return_value = sample_listener_connections
        
        # Act
        response = handle_get_session_status(connection_id)
        
        # Assert
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['type'] == 'sessionStatus'
        assert body['sessionId'] == 'golden-eagle-427'
        assert body['listenerCount'] == 4
        assert body['updateReason'] == 'requested'
        mock_metrics_publisher.emit_status_query_latency.assert_called_once()
    
    def test_handle_get_session_status_connection_not_found(
        self,
        mock_connections_repo,
        mock_metrics_publisher
    ):
        """Test session status query with connection not found."""
        # Arrange
        connection_id = 'nonexistent-conn'
        mock_connections_repo.get_connection.return_value = None
        
        # Act
        response = handle_get_session_status(connection_id)
        
        # Assert
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['code'] == 'CONNECTION_NOT_FOUND'
        mock_metrics_publisher.emit_connection_error.assert_called_with('CONNECTION_NOT_FOUND')
    
    def test_handle_get_session_status_unauthorized_role(
        self,
        mock_connections_repo,
        mock_metrics_publisher
    ):
        """Test session status query with listener role (unauthorized)."""
        # Arrange
        connection_id = 'listener-conn-123'
        
        mock_connections_repo.get_connection.return_value = {
            'connectionId': connection_id,
            'sessionId': 'golden-eagle-427',
            'role': 'listener'
        }
        
        # Act
        response = handle_get_session_status(connection_id)
        
        # Assert
        assert response['statusCode'] == 403
        body = json.loads(response['body'])
        assert body['code'] == 'UNAUTHORIZED_ACTION'
        mock_metrics_publisher.emit_connection_error.assert_called_with('UNAUTHORIZED_ACTION')
    
    def test_handle_get_session_status_session_not_found(
        self,
        mock_sessions_repo,
        mock_connections_repo,
        mock_metrics_publisher
    ):
        """Test session status query with session not found."""
        # Arrange
        connection_id = 'speaker-conn-123'
        
        mock_connections_repo.get_connection.return_value = {
            'connectionId': connection_id,
            'sessionId': 'nonexistent-session',
            'role': 'speaker'
        }
        
        with patch('handler.get_session_status') as mock_get_status:
            mock_get_status.return_value = None
            
            # Act
            response = handle_get_session_status(connection_id)
            
            # Assert
            assert response['statusCode'] == 404
            body = json.loads(response['body'])
            assert body['code'] == 'SESSION_NOT_FOUND'
            mock_metrics_publisher.emit_connection_error.assert_called_with('SESSION_NOT_FOUND')


class TestGetSessionStatus:
    """Tests for get_session_status function."""
    
    def test_get_session_status_success(
        self,
        mock_sessions_repo,
        mock_connections_repo,
        sample_session,
        sample_listener_connections
    ):
        """Test successful session status retrieval."""
        # Arrange
        session_id = 'golden-eagle-427'
        mock_sessions_repo.get_session.return_value = sample_session
        mock_connections_repo.get_listener_connections.return_value = sample_listener_connections
        
        # Act
        status = get_session_status(session_id)
        
        # Assert
        assert status is not None
        assert status['type'] == 'sessionStatus'
        assert status['sessionId'] == session_id
        assert status['listenerCount'] == 4
        assert 'languageDistribution' in status
        assert 'sessionDuration' in status
        assert 'broadcastState' in status
        assert 'timestamp' in status
        
        # Verify broadcast state is properly converted
        assert isinstance(status['broadcastState']['volume'], float)
    
    def test_get_session_status_with_no_listeners(
        self,
        mock_sessions_repo,
        mock_connections_repo,
        sample_session
    ):
        """Test session status with no listeners."""
        # Arrange
        session_id = 'golden-eagle-427'
        mock_sessions_repo.get_session.return_value = sample_session
        mock_connections_repo.get_listener_connections.return_value = []
        
        # Act
        status = get_session_status(session_id)
        
        # Assert
        assert status is not None
        assert status['listenerCount'] == 0
        assert status['languageDistribution'] == {}
    
    def test_get_session_status_session_not_found(
        self,
        mock_sessions_repo
    ):
        """Test session status with session not found."""
        # Arrange
        session_id = 'nonexistent-session'
        mock_sessions_repo.get_session.return_value = None
        
        # Act
        status = get_session_status(session_id)
        
        # Assert
        assert status is None
    
    def test_get_session_status_inactive_session(
        self,
        mock_sessions_repo,
        sample_session
    ):
        """Test session status with inactive session."""
        # Arrange
        session_id = 'golden-eagle-427'
        sample_session['isActive'] = False
        mock_sessions_repo.get_session.return_value = sample_session
        
        # Act
        status = get_session_status(session_id)
        
        # Assert
        assert status is None
    
    def test_get_session_status_with_500_listeners(
        self,
        mock_sessions_repo,
        mock_connections_repo,
        sample_session
    ):
        """Test session status performance with 500 listeners."""
        # Arrange
        session_id = 'golden-eagle-427'
        
        # Create 500 listener connections with various languages
        languages = ['es', 'fr', 'de', 'pt', 'it']
        listener_connections = []
        for i in range(500):
            listener_connections.append({
                'connectionId': f'listener-{i}',
                'sessionId': session_id,
                'role': 'listener',
                'targetLanguage': languages[i % len(languages)],
                'connectedAt': 1699500000000
            })
        
        mock_sessions_repo.get_session.return_value = sample_session
        mock_connections_repo.get_listener_connections.return_value = listener_connections
        
        # Act
        import time
        start_time = time.time()
        status = get_session_status(session_id)
        duration_ms = (time.time() - start_time) * 1000
        
        # Assert
        assert status is not None
        assert status['listenerCount'] == 500
        assert len(status['languageDistribution']) == 5
        assert sum(status['languageDistribution'].values()) == 500
        
        # Verify performance (should be well under 500ms)
        assert duration_ms < 500, f"Status query took {duration_ms}ms, expected < 500ms"


class TestAggregateLanguageDistribution:
    """Tests for aggregate_language_distribution function."""
    
    def test_aggregate_language_distribution_multiple_languages(
        self,
        sample_listener_connections
    ):
        """Test language distribution aggregation with multiple languages."""
        # Act
        distribution = aggregate_language_distribution(sample_listener_connections)
        
        # Assert
        assert distribution == {
            'es': 2,
            'fr': 1,
            'de': 1
        }
    
    def test_aggregate_language_distribution_single_language(self):
        """Test language distribution with single language."""
        # Arrange
        connections = [
            {'connectionId': 'listener-1', 'targetLanguage': 'es'},
            {'connectionId': 'listener-2', 'targetLanguage': 'es'},
            {'connectionId': 'listener-3', 'targetLanguage': 'es'}
        ]
        
        # Act
        distribution = aggregate_language_distribution(connections)
        
        # Assert
        assert distribution == {'es': 3}
    
    def test_aggregate_language_distribution_empty_connections(self):
        """Test language distribution with no connections."""
        # Act
        distribution = aggregate_language_distribution([])
        
        # Assert
        assert distribution == {}
    
    def test_aggregate_language_distribution_with_empty_language(self):
        """Test language distribution with empty language (handled gracefully)."""
        # Arrange
        connections = [
            {'connectionId': 'listener-1', 'targetLanguage': 'es'},
            {'connectionId': 'listener-2', 'targetLanguage': ''},
            {'connectionId': 'listener-3', 'targetLanguage': 'fr'}
        ]
        
        # Act
        distribution = aggregate_language_distribution(connections)
        
        # Assert
        assert distribution == {
            'es': 1,
            'fr': 1,
            'unknown': 1
        }
    
    def test_aggregate_language_distribution_with_missing_language(self):
        """Test language distribution with missing targetLanguage field."""
        # Arrange
        connections = [
            {'connectionId': 'listener-1', 'targetLanguage': 'es'},
            {'connectionId': 'listener-2'},  # Missing targetLanguage
            {'connectionId': 'listener-3', 'targetLanguage': 'fr'}
        ]
        
        # Act
        distribution = aggregate_language_distribution(connections)
        
        # Assert
        assert distribution == {
            'es': 1,
            'fr': 1,
            'unknown': 1
        }


class TestHandlePeriodicUpdates:
    """Tests for handle_periodic_updates function."""
    
    def test_handle_periodic_updates_with_active_sessions(
        self,
        mock_sessions_repo,
        mock_connections_repo,
        mock_metrics_publisher,
        sample_session,
        sample_listener_connections
    ):
        """Test periodic updates with active sessions."""
        # Arrange
        event = {
            'source': 'aws.events',
            'detail-type': 'Scheduled Event'
        }
        context = Mock()
        
        active_sessions = [sample_session]
        
        with patch('handler.get_all_active_sessions') as mock_get_sessions:
            with patch('handler.send_status_to_speaker') as mock_send:
                mock_get_sessions.return_value = active_sessions
                mock_sessions_repo.get_session.return_value = sample_session
                mock_connections_repo.get_listener_connections.return_value = sample_listener_connections
                mock_send.return_value = True
                
                # Act
                response = handle_periodic_updates(event, context)
                
                # Assert
                assert response['statusCode'] == 200
                body = json.loads(response['body'])
                assert body['updatesSent'] == 1
                assert body['updatesFailed'] == 0
                mock_metrics_publisher.emit_periodic_status_updates_sent.assert_called_with(1)
    
    def test_handle_periodic_updates_with_no_active_sessions(
        self,
        mock_metrics_publisher
    ):
        """Test periodic updates with no active sessions."""
        # Arrange
        event = {
            'source': 'aws.events',
            'detail-type': 'Scheduled Event'
        }
        context = Mock()
        
        with patch('handler.get_all_active_sessions') as mock_get_sessions:
            mock_get_sessions.return_value = []
            
            # Act
            response = handle_periodic_updates(event, context)
            
            # Assert
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['updatesSent'] == 0
            assert body['updatesFailed'] == 0
            mock_metrics_publisher.emit_periodic_status_updates_sent.assert_called_with(0)
    
    def test_handle_periodic_updates_with_send_failures(
        self,
        mock_sessions_repo,
        mock_connections_repo,
        sample_session,
        sample_listener_connections
    ):
        """Test periodic updates with some send failures."""
        # Arrange
        event = {
            'source': 'aws.events',
            'detail-type': 'Scheduled Event'
        }
        context = Mock()
        
        active_sessions = [sample_session, sample_session.copy()]
        active_sessions[1]['sessionId'] = 'another-session'
        active_sessions[1]['speakerConnectionId'] = 'speaker-conn-456'
        
        with patch('handler.get_all_active_sessions') as mock_get_sessions:
            with patch('handler.send_status_to_speaker') as mock_send:
                mock_get_sessions.return_value = active_sessions
                mock_sessions_repo.get_session.return_value = sample_session
                mock_connections_repo.get_listener_connections.return_value = sample_listener_connections
                
                # First send succeeds, second fails
                mock_send.side_effect = [True, False]
                
                # Act
                response = handle_periodic_updates(event, context)
                
                # Assert
                assert response['statusCode'] == 200
                body = json.loads(response['body'])
                assert body['updatesSent'] == 1
                assert body['updatesFailed'] == 1


class TestSendStatusToSpeaker:
    """Tests for send_status_to_speaker function."""
    
    def test_send_status_to_speaker_success(self):
        """Test successful status send to speaker."""
        # Arrange
        connection_id = 'speaker-conn-123'
        status = {
            'type': 'sessionStatus',
            'sessionId': 'golden-eagle-427',
            'listenerCount': 10
        }
        
        with patch.dict(os.environ, {'API_GATEWAY_ENDPOINT': 'https://test.execute-api.us-east-1.amazonaws.com/prod'}):
            with patch('boto3.client') as mock_boto_client:
                mock_client = Mock()
                mock_boto_client.return_value = mock_client
                
                # Act
                result = send_status_to_speaker(connection_id, status)
                
                # Assert
                assert result is True
                mock_client.post_to_connection.assert_called_once()
    
    def test_send_status_to_speaker_connection_gone(
        self,
        mock_connections_repo
    ):
        """Test status send with connection gone."""
        # Arrange
        connection_id = 'speaker-conn-123'
        status = {'type': 'sessionStatus'}
        
        with patch.dict(os.environ, {'API_GATEWAY_ENDPOINT': 'https://test.execute-api.us-east-1.amazonaws.com/prod'}):
            with patch('boto3.client') as mock_boto_client:
                mock_client = Mock()
                mock_boto_client.return_value = mock_client
                
                # Simulate GoneException
                from botocore.exceptions import ClientError
                mock_client.exceptions.GoneException = type('GoneException', (ClientError,), {})
                mock_client.post_to_connection.side_effect = mock_client.exceptions.GoneException(
                    {'Error': {'Code': 'GoneException'}},
                    'post_to_connection'
                )
                
                # Act
                result = send_status_to_speaker(connection_id, status)
                
                # Assert
                assert result is False
                mock_connections_repo.delete_connection.assert_called_with(connection_id)
    
    def test_send_status_to_speaker_no_endpoint(self):
        """Test status send with no API Gateway endpoint configured."""
        # Arrange
        connection_id = 'speaker-conn-123'
        status = {'type': 'sessionStatus'}
        
        with patch.dict(os.environ, {'API_GATEWAY_ENDPOINT': ''}):
            # Act
            result = send_status_to_speaker(connection_id, status)
            
            # Assert
            assert result is False
