"""
Unit tests for data access layer.
Tests atomic operations, conditional updates, batch operations, and TTL handling.
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from shared.data_access.dynamodb_client import DynamoDBClient
from shared.data_access.sessions_repository import SessionsRepository
from shared.data_access.connections_repository import ConnectionsRepository
from shared.data_access.exceptions import (
    ConditionalCheckFailedError,
    DynamoDBError
)


class TestAtomicCounterOperations:
    """Test atomic counter operations with concurrent updates."""

    @pytest.fixture
    def mock_dynamodb_client(self):
        """Create mock DynamoDB client."""
        client = Mock(spec=DynamoDBClient)
        return client

    @pytest.fixture
    def sessions_repo(self, mock_dynamodb_client):
        """Create SessionsRepository with mock client."""
        return SessionsRepository('Sessions-test', mock_dynamodb_client)

    def test_atomic_increment_listener_count(self, sessions_repo, mock_dynamodb_client):
        """Test atomic increment of listener count."""
        # Arrange
        session_id = 'test-session-123'
        mock_dynamodb_client.atomic_increment.return_value = 5

        # Act
        new_count = sessions_repo.increment_listener_count(session_id)

        # Assert
        assert new_count == 5
        mock_dynamodb_client.atomic_increment.assert_called_once_with(
            table_name='Sessions-test',
            key={'sessionId': session_id},
            attribute_name='listenerCount',
            increment_value=1,
            condition_expression='attribute_exists(sessionId) AND isActive = :true',
            expression_attribute_values={':true': True}
        )

    def test_atomic_decrement_listener_count(self, sessions_repo, mock_dynamodb_client):
        """Test atomic decrement of listener count with floor."""
        # Arrange
        session_id = 'test-session-123'
        mock_dynamodb_client.atomic_decrement_with_floor.return_value = 3

        # Act
        new_count = sessions_repo.decrement_listener_count(session_id)

        # Assert
        assert new_count == 3
        mock_dynamodb_client.atomic_decrement_with_floor.assert_called_once_with(
            table_name='Sessions-test',
            key={'sessionId': session_id},
            attribute_name='listenerCount',
            decrement_value=1,
            floor_value=0
        )

    def test_atomic_decrement_prevents_negative_count(self):
        """Test that atomic decrement prevents negative listener count."""
        # Arrange
        client = DynamoDBClient()
        mock_table = Mock()
        client.get_table = Mock(return_value=mock_table)

        # Simulate conditional check failure (count already at floor)
        mock_table.update_item.side_effect = [
            ClientError(
                {'Error': {'Code': 'ConditionalCheckFailedException'}},
                'UpdateItem'
            ),
            {'Attributes': {'listenerCount': 0}}
        ]

        # Act
        result = client.atomic_decrement_with_floor(
            table_name='Sessions-test',
            key={'sessionId': 'test-123'},
            attribute_name='listenerCount',
            decrement_value=1,
            floor_value=0
        )

        # Assert
        assert result == 0
        assert mock_table.update_item.call_count == 2


class TestConditionalUpdateRaceConditions:
    """Test conditional update race condition handling."""

    @pytest.fixture
    def mock_dynamodb_client(self):
        """Create mock DynamoDB client."""
        client = Mock(spec=DynamoDBClient)
        return client

    @pytest.fixture
    def sessions_repo(self, mock_dynamodb_client):
        """Create SessionsRepository with mock client."""
        return SessionsRepository('Sessions-test', mock_dynamodb_client)

    def test_create_session_prevents_duplicate_id(self, sessions_repo, mock_dynamodb_client):
        """Test that creating session with existing ID fails."""
        # Arrange
        mock_dynamodb_client.put_item.side_effect = ConditionalCheckFailedError(
            "Conditional check failed"
        )

        # Act & Assert
        with pytest.raises(ConditionalCheckFailedError):
            sessions_repo.create_session(
                session_id='existing-session-123',
                speaker_connection_id='conn-123',
                speaker_user_id='user-123',
                source_language='en',
                quality_tier='standard'
            )

    def test_update_speaker_connection_requires_active_session(
        self, sessions_repo, mock_dynamodb_client
    ):
        """Test that updating speaker connection requires active session."""
        # Arrange
        mock_dynamodb_client.update_item.side_effect = ConditionalCheckFailedError(
            "Conditional check failed"
        )

        # Act & Assert
        with pytest.raises(ConditionalCheckFailedError):
            sessions_repo.update_speaker_connection(
                session_id='inactive-session-123',
                new_connection_id='new-conn-456'
            )

    def test_increment_listener_count_requires_active_session(
        self, sessions_repo, mock_dynamodb_client
    ):
        """Test that incrementing listener count requires active session."""
        # Arrange
        mock_dynamodb_client.atomic_increment.side_effect = ConditionalCheckFailedError(
            "Conditional check failed"
        )

        # Act & Assert
        with pytest.raises(ConditionalCheckFailedError):
            sessions_repo.increment_listener_count('inactive-session-123')

    def test_conditional_update_with_race_condition(self):
        """Test handling of race condition in conditional update."""
        # Arrange
        client = DynamoDBClient()
        mock_table = Mock()
        client.get_table = Mock(return_value=mock_table)

        # Simulate race condition - first call fails, second succeeds
        mock_table.update_item.side_effect = [
            ClientError(
                {'Error': {'Code': 'ConditionalCheckFailedException'}},
                'UpdateItem'
            )
        ]

        # Act & Assert
        with pytest.raises(ConditionalCheckFailedError):
            client.update_item(
                table_name='Sessions-test',
                key={'sessionId': 'test-123'},
                update_expression='SET isActive = :false',
                condition_expression='attribute_exists(sessionId)',
                expression_attribute_values={':false': False}
            )


class TestBatchOperations:
    """Test batch operation error handling."""

    @pytest.fixture
    def mock_dynamodb_client(self):
        """Create mock DynamoDB client."""
        client = Mock(spec=DynamoDBClient)
        return client

    @pytest.fixture
    def connections_repo(self, mock_dynamodb_client):
        """Create ConnectionsRepository with mock client."""
        return ConnectionsRepository('Connections-test', mock_dynamodb_client)

    def test_batch_delete_connections_success(self, connections_repo, mock_dynamodb_client):
        """Test successful batch deletion of connections."""
        # Arrange
        connection_ids = ['conn-1', 'conn-2', 'conn-3']
        mock_dynamodb_client.batch_delete.return_value = None

        # Act
        connections_repo.batch_delete_connections(connection_ids)

        # Assert
        expected_keys = [{'connectionId': cid} for cid in connection_ids]
        mock_dynamodb_client.batch_delete.assert_called_once_with(
            table_name='Connections-test',
            keys=expected_keys
        )

    def test_batch_delete_empty_list(self, connections_repo, mock_dynamodb_client):
        """Test batch delete with empty list does nothing."""
        # Act
        connections_repo.batch_delete_connections([])

        # Assert
        mock_dynamodb_client.batch_delete.assert_not_called()

    def test_batch_delete_handles_errors(self):
        """Test batch delete error handling."""
        # Arrange
        client = DynamoDBClient()
        mock_table = Mock()
        client.get_table = Mock(return_value=mock_table)

        # Simulate batch writer error
        mock_batch_writer = MagicMock()
        mock_batch_writer.__enter__.side_effect = ClientError(
            {'Error': {'Code': 'InternalServerError', 'Message': 'Server error'}},
            'BatchWriteItem'
        )
        mock_table.batch_writer.return_value = mock_batch_writer

        # Act & Assert
        with pytest.raises(DynamoDBError):
            client.batch_delete(
                table_name='Connections-test',
                keys=[{'connectionId': 'conn-1'}]
            )

    def test_delete_all_session_connections(self, connections_repo, mock_dynamodb_client):
        """Test deleting all connections for a session."""
        # Arrange
        session_id = 'test-session-123'
        mock_connections = [
            {'connectionId': 'conn-1', 'sessionId': session_id},
            {'connectionId': 'conn-2', 'sessionId': session_id},
            {'connectionId': 'conn-3', 'sessionId': session_id}
        ]
        mock_dynamodb_client.query.return_value = mock_connections

        # Act
        deleted_count = connections_repo.delete_all_session_connections(session_id)

        # Assert
        assert deleted_count == 3
        mock_dynamodb_client.batch_delete.assert_called_once()


class TestTTLAttributeSetting:
    """Test TTL attribute setting."""

    @pytest.fixture
    def sessions_repo(self):
        """Create SessionsRepository with mock client."""
        mock_client = Mock(spec=DynamoDBClient)
        return SessionsRepository('Sessions-test', mock_client)

    @pytest.fixture
    def connections_repo(self):
        """Create ConnectionsRepository with mock client."""
        mock_client = Mock(spec=DynamoDBClient)
        return ConnectionsRepository('Connections-test', mock_client)

    def test_session_creation_sets_expires_at(self, sessions_repo):
        """Test that session creation sets expiresAt TTL attribute."""
        # Arrange
        current_time = int(time.time())
        session_max_duration_hours = 2

        # Act
        with patch('time.time', return_value=current_time):
            sessions_repo.create_session(
                session_id='test-session-123',
                speaker_connection_id='conn-123',
                speaker_user_id='user-123',
                source_language='en',
                quality_tier='standard',
                session_max_duration_hours=session_max_duration_hours
            )

        # Assert
        call_args = sessions_repo.client.put_item.call_args
        session_item = call_args[1]['item']
        
        assert 'expiresAt' in session_item
        expected_expires_at = current_time + (session_max_duration_hours * 3600)
        assert session_item['expiresAt'] == expected_expires_at

    def test_connection_creation_sets_ttl(self, connections_repo):
        """Test that connection creation sets ttl attribute."""
        # Arrange
        current_time = int(time.time())
        session_max_duration_hours = 2

        # Act
        with patch('time.time', return_value=current_time):
            connections_repo.create_connection(
                connection_id='conn-123',
                session_id='session-123',
                role='listener',
                target_language='es',
                session_max_duration_hours=session_max_duration_hours
            )

        # Assert
        call_args = connections_repo.client.put_item.call_args
        connection_item = call_args[1]['item']
        
        assert 'ttl' in connection_item
        # TTL should be session duration + 1 hour buffer
        expected_ttl = current_time + ((session_max_duration_hours + 1) * 3600)
        assert connection_item['ttl'] == expected_ttl

    def test_ttl_values_are_unix_timestamps(self, sessions_repo, connections_repo):
        """Test that TTL values are valid Unix timestamps."""
        # Arrange
        current_time = int(time.time())

        # Act - Create session
        with patch('time.time', return_value=current_time):
            sessions_repo.create_session(
                session_id='test-session-123',
                speaker_connection_id='conn-123',
                speaker_user_id='user-123',
                source_language='en',
                quality_tier='standard'
            )

        # Assert - Session expiresAt
        session_call_args = sessions_repo.client.put_item.call_args
        session_item = session_call_args[1]['item']
        expires_at = session_item['expiresAt']
        
        # Should be a reasonable future timestamp (within 3 hours)
        assert expires_at > current_time
        assert expires_at <= current_time + (3 * 3600)

        # Act - Create connection
        with patch('time.time', return_value=current_time):
            connections_repo.create_connection(
                connection_id='conn-123',
                session_id='session-123',
                role='listener'
            )

        # Assert - Connection ttl
        connection_call_args = connections_repo.client.put_item.call_args
        connection_item = connection_call_args[1]['item']
        ttl = connection_item['ttl']
        
        # Should be a reasonable future timestamp (within 4 hours)
        assert ttl > current_time
        assert ttl <= current_time + (4 * 3600)

    def test_ttl_buffer_for_connections(self, connections_repo):
        """Test that connection TTL includes 1-hour buffer beyond session duration."""
        # Arrange
        current_time = int(time.time())
        session_max_duration_hours = 2

        # Act
        with patch('time.time', return_value=current_time):
            connections_repo.create_connection(
                connection_id='conn-123',
                session_id='session-123',
                role='listener',
                session_max_duration_hours=session_max_duration_hours
            )

        # Assert
        call_args = connections_repo.client.put_item.call_args
        connection_item = call_args[1]['item']
        
        # TTL should be session duration + 1 hour buffer
        expected_ttl = current_time + ((session_max_duration_hours + 1) * 3600)
        assert connection_item['ttl'] == expected_ttl
