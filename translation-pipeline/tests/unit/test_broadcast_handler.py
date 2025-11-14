"""
Unit tests for BroadcastHandler.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from shared.services.broadcast_handler import (
    BroadcastHandler,
    BroadcastResult
)


@pytest.fixture
def mock_api_gateway_client():
    """Create mock API Gateway Management API client."""
    client = Mock()
    client.post_to_connection = AsyncMock()
    client.exceptions = Mock()
    client.exceptions.GoneException = type('GoneException', (Exception,), {})
    client.exceptions.LimitExceededException = type('LimitExceededException', (Exception,), {})
    return client


@pytest.fixture
def mock_connections_repository():
    """Create mock connections repository."""
    repo = Mock()
    repo.get_listeners_by_language = AsyncMock()
    repo.remove_connection = AsyncMock()
    return repo


@pytest.fixture
def broadcast_handler(mock_api_gateway_client, mock_connections_repository):
    """Create BroadcastHandler instance."""
    return BroadcastHandler(
        api_gateway_client=mock_api_gateway_client,
        connections_repository=mock_connections_repository,
        max_concurrent_broadcasts=100,
        max_retries=2,
        retry_backoff_ms=100
    )


class TestBroadcastHandler:
    """Test suite for BroadcastHandler."""
    
    @pytest.mark.asyncio
    async def test_broadcast_to_language_with_no_listeners_returns_zero_counts(
        self, broadcast_handler, mock_connections_repository
    ):
        """Test broadcasting when no listeners exist."""
        # Arrange
        mock_connections_repository.get_listeners_by_language.return_value = []
        
        # Act
        result = await broadcast_handler.broadcast_to_language(
            session_id='test-session',
            target_language='es',
            audio_data=b'audio_data'
        )
        
        # Assert
        assert result.success_count == 0
        assert result.failure_count == 0
        assert result.stale_connections_removed == 0
        assert result.language == 'es'
    
    @pytest.mark.asyncio
    async def test_broadcast_to_language_with_single_listener_succeeds(
        self, broadcast_handler, mock_connections_repository, mock_api_gateway_client
    ):
        """Test successful broadcast to single listener."""
        # Arrange
        mock_connections_repository.get_listeners_by_language.return_value = ['conn1']
        mock_api_gateway_client.post_to_connection.return_value = None
        
        # Act
        result = await broadcast_handler.broadcast_to_language(
            session_id='test-session',
            target_language='es',
            audio_data=b'audio_data'
        )
        
        # Assert
        assert result.success_count == 1
        assert result.failure_count == 0
        assert result.stale_connections_removed == 0
        mock_api_gateway_client.post_to_connection.assert_called_once_with(
            ConnectionId='conn1',
            Data=b'audio_data'
        )
    
    @pytest.mark.asyncio
    async def test_broadcast_to_language_with_multiple_listeners_succeeds(
        self, broadcast_handler, mock_connections_repository, mock_api_gateway_client
    ):
        """Test successful broadcast to multiple listeners."""
        # Arrange
        connection_ids = [f'conn{i}' for i in range(10)]
        mock_connections_repository.get_listeners_by_language.return_value = connection_ids
        mock_api_gateway_client.post_to_connection.return_value = None
        
        # Act
        result = await broadcast_handler.broadcast_to_language(
            session_id='test-session',
            target_language='es',
            audio_data=b'audio_data'
        )
        
        # Assert
        assert result.success_count == 10
        assert result.failure_count == 0
        assert result.stale_connections_removed == 0
        assert mock_api_gateway_client.post_to_connection.call_count == 10
    
    @pytest.mark.asyncio
    async def test_broadcast_handles_gone_exception_and_removes_connection(
        self, broadcast_handler, mock_connections_repository, mock_api_gateway_client
    ):
        """Test handling of GoneException for stale connections."""
        # Arrange
        mock_connections_repository.get_listeners_by_language.return_value = ['conn1']
        mock_api_gateway_client.post_to_connection.side_effect = (
            mock_api_gateway_client.exceptions.GoneException()
        )
        
        # Act
        result = await broadcast_handler.broadcast_to_language(
            session_id='test-session',
            target_language='es',
            audio_data=b'audio_data'
        )
        
        # Assert
        assert result.success_count == 0
        assert result.failure_count == 0
        assert result.stale_connections_removed == 1
        mock_connections_repository.remove_connection.assert_called_once_with(
            'conn1', 'test-session'
        )
    
    @pytest.mark.asyncio
    async def test_broadcast_retries_on_limit_exceeded_exception(
        self, broadcast_handler, mock_connections_repository, mock_api_gateway_client
    ):
        """Test retry logic for LimitExceededException."""
        # Arrange
        mock_connections_repository.get_listeners_by_language.return_value = ['conn1']
        mock_api_gateway_client.post_to_connection.side_effect = [
            mock_api_gateway_client.exceptions.LimitExceededException(),
            None  # Success on retry
        ]
        
        # Act
        result = await broadcast_handler.broadcast_to_language(
            session_id='test-session',
            target_language='es',
            audio_data=b'audio_data'
        )
        
        # Assert
        assert result.success_count == 1
        assert result.failure_count == 0
        assert mock_api_gateway_client.post_to_connection.call_count == 2
    
    @pytest.mark.asyncio
    async def test_broadcast_fails_after_max_retries(
        self, broadcast_handler, mock_connections_repository, mock_api_gateway_client
    ):
        """Test failure after exhausting retry attempts."""
        # Arrange
        mock_connections_repository.get_listeners_by_language.return_value = ['conn1']
        mock_api_gateway_client.post_to_connection.side_effect = (
            mock_api_gateway_client.exceptions.LimitExceededException()
        )
        
        # Act
        result = await broadcast_handler.broadcast_to_language(
            session_id='test-session',
            target_language='es',
            audio_data=b'audio_data'
        )
        
        # Assert
        assert result.success_count == 0
        assert result.failure_count == 1
        assert mock_api_gateway_client.post_to_connection.call_count == 3  # Initial + 2 retries
    
    @pytest.mark.asyncio
    async def test_broadcast_with_mixed_results(
        self, broadcast_handler, mock_connections_repository, mock_api_gateway_client
    ):
        """Test broadcast with mix of success, failure, and stale connections."""
        # Arrange
        mock_connections_repository.get_listeners_by_language.return_value = [
            'conn1', 'conn2', 'conn3'
        ]
        
        # conn1: success, conn2: stale, conn3: failure after retries
        mock_api_gateway_client.post_to_connection.side_effect = [
            None,  # conn1 success
            mock_api_gateway_client.exceptions.GoneException(),  # conn2 stale
            mock_api_gateway_client.exceptions.LimitExceededException(),  # conn3 fail
            mock_api_gateway_client.exceptions.LimitExceededException(),  # conn3 retry 1
            mock_api_gateway_client.exceptions.LimitExceededException(),  # conn3 retry 2
        ]
        
        # Act
        result = await broadcast_handler.broadcast_to_language(
            session_id='test-session',
            target_language='es',
            audio_data=b'audio_data'
        )
        
        # Assert
        assert result.success_count == 1
        assert result.failure_count == 1
        assert result.stale_connections_removed == 1
    
    @pytest.mark.asyncio
    async def test_broadcast_respects_concurrency_limit(
        self, mock_api_gateway_client, mock_connections_repository
    ):
        """Test that concurrent broadcasts respect semaphore limit."""
        # Arrange
        max_concurrent = 5
        handler = BroadcastHandler(
            api_gateway_client=mock_api_gateway_client,
            connections_repository=mock_connections_repository,
            max_concurrent_broadcasts=max_concurrent
        )
        
        connection_ids = [f'conn{i}' for i in range(20)]
        mock_connections_repository.get_listeners_by_language.return_value = connection_ids
        
        # Track concurrent calls
        concurrent_calls = []
        max_concurrent_observed = 0
        
        async def track_concurrent_call(*args, **kwargs):
            concurrent_calls.append(1)
            current_concurrent = len(concurrent_calls)
            nonlocal max_concurrent_observed
            max_concurrent_observed = max(max_concurrent_observed, current_concurrent)
            await asyncio.sleep(0.01)  # Simulate work
            concurrent_calls.pop()
        
        mock_api_gateway_client.post_to_connection.side_effect = track_concurrent_call
        
        # Act
        await handler.broadcast_to_language(
            session_id='test-session',
            target_language='es',
            audio_data=b'audio_data'
        )
        
        # Assert
        assert max_concurrent_observed <= max_concurrent
    
    @pytest.mark.asyncio
    async def test_broadcast_handles_repository_query_failure(
        self, broadcast_handler, mock_connections_repository
    ):
        """Test handling of repository query failures."""
        # Arrange
        mock_connections_repository.get_listeners_by_language.side_effect = Exception(
            'DynamoDB error'
        )
        
        # Act
        result = await broadcast_handler.broadcast_to_language(
            session_id='test-session',
            target_language='es',
            audio_data=b'audio_data'
        )
        
        # Assert
        assert result.success_count == 0
        assert result.failure_count == 0
        assert result.stale_connections_removed == 0
    
    @pytest.mark.asyncio
    async def test_broadcast_handles_connection_removal_failure(
        self, broadcast_handler, mock_connections_repository, mock_api_gateway_client
    ):
        """Test handling of connection removal failures."""
        # Arrange
        mock_connections_repository.get_listeners_by_language.return_value = ['conn1']
        mock_api_gateway_client.post_to_connection.side_effect = (
            mock_api_gateway_client.exceptions.GoneException()
        )
        mock_connections_repository.remove_connection.side_effect = Exception(
            'DynamoDB error'
        )
        
        # Act
        result = await broadcast_handler.broadcast_to_language(
            session_id='test-session',
            target_language='es',
            audio_data=b'audio_data'
        )
        
        # Assert
        # Should still count as stale connection even if removal fails
        assert result.stale_connections_removed == 1
    
    @pytest.mark.asyncio
    async def test_broadcast_result_includes_duration(
        self, broadcast_handler, mock_connections_repository, mock_api_gateway_client
    ):
        """Test that broadcast result includes duration metric."""
        # Arrange
        mock_connections_repository.get_listeners_by_language.return_value = ['conn1']
        mock_api_gateway_client.post_to_connection.return_value = None
        
        # Act
        result = await broadcast_handler.broadcast_to_language(
            session_id='test-session',
            target_language='es',
            audio_data=b'audio_data'
        )
        
        # Assert
        assert result.total_duration_ms > 0
        assert isinstance(result.total_duration_ms, float)
    
    @pytest.mark.asyncio
    async def test_broadcast_with_large_listener_count(
        self, broadcast_handler, mock_connections_repository, mock_api_gateway_client
    ):
        """Test broadcast with 100 listeners (target requirement)."""
        # Arrange
        connection_ids = [f'conn{i}' for i in range(100)]
        mock_connections_repository.get_listeners_by_language.return_value = connection_ids
        mock_api_gateway_client.post_to_connection.return_value = None
        
        # Act
        result = await broadcast_handler.broadcast_to_language(
            session_id='test-session',
            target_language='es',
            audio_data=b'audio_data'
        )
        
        # Assert
        assert result.success_count == 100
        assert result.failure_count == 0
        assert result.total_duration_ms < 2000  # Should complete within 2 seconds
    
    @pytest.mark.asyncio
    async def test_broadcast_exponential_backoff(
        self, broadcast_handler, mock_connections_repository, mock_api_gateway_client
    ):
        """Test exponential backoff timing for retries."""
        # Arrange
        mock_connections_repository.get_listeners_by_language.return_value = ['conn1']
        
        call_times = []
        
        async def track_call_time(*args, **kwargs):
            call_times.append(asyncio.get_event_loop().time())
            raise mock_api_gateway_client.exceptions.LimitExceededException()
        
        mock_api_gateway_client.post_to_connection.side_effect = track_call_time
        
        # Act
        await broadcast_handler.broadcast_to_language(
            session_id='test-session',
            target_language='es',
            audio_data=b'audio_data'
        )
        
        # Assert
        assert len(call_times) == 3  # Initial + 2 retries
        # Check backoff timing (100ms, 200ms)
        if len(call_times) >= 2:
            first_backoff = call_times[1] - call_times[0]
            assert 0.08 < first_backoff < 0.15  # ~100ms with tolerance
        if len(call_times) >= 3:
            second_backoff = call_times[2] - call_times[1]
            assert 0.18 < second_backoff < 0.25  # ~200ms with tolerance
