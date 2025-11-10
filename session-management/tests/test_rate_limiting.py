"""
Unit tests for rate limiting functionality.
Tests token bucket algorithm, window expiration, concurrent requests, and TTL cleanup.
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from shared.data_access import (
    RateLimitsRepository,
    RateLimitOperation,
    RateLimitExceededError,
    DynamoDBClient,
)
from shared.services import RateLimitService


class TestWithinLimitRequestAcceptance:
    """Test that requests within rate limit are accepted."""

    @pytest.fixture
    def mock_dynamodb_client(self):
        """Create mock DynamoDB client."""
        return Mock(spec=DynamoDBClient)

    @pytest.fixture
    def rate_limits_repo(self, mock_dynamodb_client):
        """Create RateLimitsRepository with mock client."""
        return RateLimitsRepository('RateLimits-test', mock_dynamodb_client)

    def test_first_request_accepted(self, rate_limits_repo, mock_dynamodb_client):
        """Test that first request is always accepted."""
        # Arrange
        mock_dynamodb_client.get_item.return_value = None  # No existing record
        mock_dynamodb_client.put_item.return_value = None

        # Act
        result = rate_limits_repo.check_rate_limit(
            operation=RateLimitOperation.SESSION_CREATE,
            identifier_type='user',
            identifier_value='user-123'
        )

        # Assert
        assert result is True
        mock_dynamodb_client.put_item.assert_called_once()

    def test_request_within_limit_accepted(self, rate_limits_repo, mock_dynamodb_client):
        """Test that request within limit is accepted."""
        # Arrange
        current_time = int(time.time() * 1000)
        mock_dynamodb_client.get_item.return_value = {
            'identifier': 'session_create:user:user-123',
            'count': 10,
            'windowStart': current_time - 1000,  # 1 second ago
            'expiresAt': int(time.time()) + 3600
        }
        mock_dynamodb_client.atomic_increment.return_value = 11

        # Act
        with patch('time.time', return_value=current_time / 1000):
            result = rate_limits_repo.check_rate_limit(
                operation=RateLimitOperation.SESSION_CREATE,
                identifier_type='user',
                identifier_value='user-123'
            )

        # Assert
        assert result is True
        mock_dynamodb_client.atomic_increment.assert_called_once()

    def test_multiple_operations_tracked_separately(self, rate_limits_repo, mock_dynamodb_client):
        """Test that different operations are tracked separately."""
        # Arrange
        current_time = int(time.time() * 1000)
        
        # Mock different records for different operations
        def get_item_side_effect(table_name, key):
            identifier = key['identifier']
            if 'session_create' in identifier:
                return {
                    'identifier': identifier,
                    'count': 5,
                    'windowStart': current_time - 1000,
                    'expiresAt': int(time.time()) + 3600
                }
            elif 'listener_join' in identifier:
                return {
                    'identifier': identifier,
                    'count': 2,
                    'windowStart': current_time - 1000,
                    'expiresAt': int(time.time()) + 60
                }
            return None

        mock_dynamodb_client.get_item.side_effect = get_item_side_effect
        mock_dynamodb_client.atomic_increment.return_value = 6

        # Act - Check session creation
        with patch('time.time', return_value=current_time / 1000):
            result1 = rate_limits_repo.check_rate_limit(
                operation=RateLimitOperation.SESSION_CREATE,
                identifier_type='user',
                identifier_value='user-123'
            )

        # Act - Check listener join
        mock_dynamodb_client.atomic_increment.return_value = 3
        with patch('time.time', return_value=current_time / 1000):
            result2 = rate_limits_repo.check_rate_limit(
                operation=RateLimitOperation.LISTENER_JOIN,
                identifier_type='ip',
                identifier_value='192.168.1.1'
            )

        # Assert
        assert result1 is True
        assert result2 is True


class TestLimitExceededRejection:
    """Test that requests exceeding rate limit are rejected with 429 status."""

    @pytest.fixture
    def mock_dynamodb_client(self):
        """Create mock DynamoDB client."""
        return Mock(spec=DynamoDBClient)

    @pytest.fixture
    def rate_limits_repo(self, mock_dynamodb_client):
        """Create RateLimitsRepository with mock client."""
        return RateLimitsRepository('RateLimits-test', mock_dynamodb_client)

    def test_limit_exceeded_raises_exception(self, rate_limits_repo, mock_dynamodb_client):
        """Test that exceeding limit raises RateLimitExceededError."""
        # Arrange
        current_time = int(time.time() * 1000)
        mock_dynamodb_client.get_item.return_value = {
            'identifier': 'session_create:user:user-123',
            'count': 50,  # At limit
            'windowStart': current_time - 1000,
            'expiresAt': int(time.time()) + 3600
        }

        # Act & Assert
        with patch('time.time', return_value=current_time / 1000):
            with pytest.raises(RateLimitExceededError) as exc_info:
                rate_limits_repo.check_rate_limit(
                    operation=RateLimitOperation.SESSION_CREATE,
                    identifier_type='user',
                    identifier_value='user-123'
                )

        # Assert exception details
        assert exc_info.value.retry_after > 0
        assert 'Rate limit exceeded' in str(exc_info.value)

    def test_retry_after_value_correct(self, rate_limits_repo, mock_dynamodb_client):
        """Test that retry_after value is correctly calculated."""
        # Arrange
        current_time = int(time.time() * 1000)
        window_start = current_time - (30 * 60 * 1000)  # 30 minutes ago
        
        mock_dynamodb_client.get_item.return_value = {
            'identifier': 'session_create:user:user-123',
            'count': 50,
            'windowStart': window_start,
            'expiresAt': int(time.time()) + 3600
        }

        # Act & Assert
        with patch('time.time', return_value=current_time / 1000):
            with pytest.raises(RateLimitExceededError) as exc_info:
                rate_limits_repo.check_rate_limit(
                    operation=RateLimitOperation.SESSION_CREATE,
                    identifier_type='user',
                    identifier_value='user-123'
                )

        # Assert - retry_after should be approximately 30 minutes (1800 seconds)
        assert 1790 <= exc_info.value.retry_after <= 1810

    def test_listener_join_limit_exceeded(self, rate_limits_repo, mock_dynamodb_client):
        """Test listener join rate limit (10 per minute)."""
        # Arrange
        current_time = int(time.time() * 1000)
        mock_dynamodb_client.get_item.return_value = {
            'identifier': 'listener_join:ip:192.168.1.1',
            'count': 10,  # At limit
            'windowStart': current_time - 1000,
            'expiresAt': int(time.time()) + 60
        }

        # Act & Assert
        with patch('time.time', return_value=current_time / 1000):
            with pytest.raises(RateLimitExceededError) as exc_info:
                rate_limits_repo.check_rate_limit(
                    operation=RateLimitOperation.LISTENER_JOIN,
                    identifier_type='ip',
                    identifier_value='192.168.1.1'
                )

        # Assert - retry_after should be less than 60 seconds
        assert exc_info.value.retry_after < 60

    def test_heartbeat_limit_exceeded(self, rate_limits_repo, mock_dynamodb_client):
        """Test heartbeat rate limit (2 per minute)."""
        # Arrange
        current_time = int(time.time() * 1000)
        mock_dynamodb_client.get_item.return_value = {
            'identifier': 'heartbeat:connection:conn-123',
            'count': 2,  # At limit
            'windowStart': current_time - 1000,
            'expiresAt': int(time.time()) + 60
        }

        # Act & Assert
        with patch('time.time', return_value=current_time / 1000):
            with pytest.raises(RateLimitExceededError):
                rate_limits_repo.check_rate_limit(
                    operation=RateLimitOperation.HEARTBEAT,
                    identifier_type='connection',
                    identifier_value='conn-123'
                )


class TestWindowResetBehavior:
    """Test window expiration and counter reset."""

    @pytest.fixture
    def mock_dynamodb_client(self):
        """Create mock DynamoDB client."""
        return Mock(spec=DynamoDBClient)

    @pytest.fixture
    def rate_limits_repo(self, mock_dynamodb_client):
        """Create RateLimitsRepository with mock client."""
        return RateLimitsRepository('RateLimits-test', mock_dynamodb_client)

    def test_expired_window_resets_counter(self, rate_limits_repo, mock_dynamodb_client):
        """Test that expired window resets counter."""
        # Arrange
        current_time = int(time.time() * 1000)
        window_start = current_time - (3700 * 1000)  # 3700 seconds ago (> 1 hour)
        
        mock_dynamodb_client.get_item.return_value = {
            'identifier': 'session_create:user:user-123',
            'count': 50,  # Was at limit
            'windowStart': window_start,
            'expiresAt': int(time.time()) + 3600
        }
        mock_dynamodb_client.put_item.return_value = None

        # Act
        with patch('time.time', return_value=current_time / 1000):
            result = rate_limits_repo.check_rate_limit(
                operation=RateLimitOperation.SESSION_CREATE,
                identifier_type='user',
                identifier_value='user-123'
            )

        # Assert
        assert result is True
        # Should create new window with count=1
        mock_dynamodb_client.put_item.assert_called_once()
        call_args = mock_dynamodb_client.put_item.call_args
        new_item = call_args[1]['item']
        assert new_item['count'] == 1
        assert new_item['windowStart'] == current_time

    def test_window_reset_after_exact_duration(self, rate_limits_repo, mock_dynamodb_client):
        """Test window reset after exact duration."""
        # Arrange
        current_time = int(time.time() * 1000)
        window_start = current_time - (60 * 1000)  # Exactly 60 seconds ago
        
        mock_dynamodb_client.get_item.return_value = {
            'identifier': 'listener_join:ip:192.168.1.1',
            'count': 10,
            'windowStart': window_start,
            'expiresAt': int(time.time()) + 60
        }
        mock_dynamodb_client.put_item.return_value = None

        # Act
        with patch('time.time', return_value=current_time / 1000):
            result = rate_limits_repo.check_rate_limit(
                operation=RateLimitOperation.LISTENER_JOIN,
                identifier_type='ip',
                identifier_value='192.168.1.1'
            )

        # Assert
        assert result is True
        mock_dynamodb_client.put_item.assert_called_once()

    def test_new_window_has_correct_ttl(self, rate_limits_repo, mock_dynamodb_client):
        """Test that new window has correct TTL for cleanup."""
        # Arrange
        current_time = int(time.time() * 1000)
        window_start = current_time - (3700 * 1000)  # Expired window
        
        mock_dynamodb_client.get_item.return_value = {
            'identifier': 'session_create:user:user-123',
            'count': 50,
            'windowStart': window_start,
            'expiresAt': int(time.time()) + 3600
        }
        mock_dynamodb_client.put_item.return_value = None

        # Act
        with patch('time.time', return_value=current_time / 1000):
            rate_limits_repo.check_rate_limit(
                operation=RateLimitOperation.SESSION_CREATE,
                identifier_type='user',
                identifier_value='user-123'
            )

        # Assert
        call_args = mock_dynamodb_client.put_item.call_args
        new_item = call_args[1]['item']
        
        # TTL should be window_start + window_duration + 1 hour buffer
        expected_ttl = int(current_time / 1000) + 3600 + 3600  # 1 hour window + 1 hour buffer
        assert new_item['expiresAt'] == expected_ttl


class TestConcurrentRequestHandling:
    """Test concurrent request handling with atomic operations."""

    @pytest.fixture
    def mock_dynamodb_client(self):
        """Create mock DynamoDB client."""
        return Mock(spec=DynamoDBClient)

    @pytest.fixture
    def rate_limits_repo(self, mock_dynamodb_client):
        """Create RateLimitsRepository with mock client."""
        return RateLimitsRepository('RateLimits-test', mock_dynamodb_client)

    def test_atomic_increment_prevents_race_condition(self, rate_limits_repo, mock_dynamodb_client):
        """Test that atomic increment prevents race conditions."""
        # Arrange
        current_time = int(time.time() * 1000)
        mock_dynamodb_client.get_item.return_value = {
            'identifier': 'session_create:user:user-123',
            'count': 45,
            'windowStart': current_time - 1000,
            'expiresAt': int(time.time()) + 3600
        }
        mock_dynamodb_client.atomic_increment.return_value = 46

        # Act
        with patch('time.time', return_value=current_time / 1000):
            result = rate_limits_repo.check_rate_limit(
                operation=RateLimitOperation.SESSION_CREATE,
                identifier_type='user',
                identifier_value='user-123'
            )

        # Assert
        assert result is True
        # Verify atomic increment was used
        mock_dynamodb_client.atomic_increment.assert_called_once_with(
            table_name='RateLimits-test',
            key={'identifier': 'session_create:user:user-123'},
            attribute_name='count',
            increment_value=1
        )

    def test_multiple_concurrent_requests_tracked_correctly(
        self, rate_limits_repo, mock_dynamodb_client
    ):
        """Test that multiple concurrent requests are tracked correctly."""
        # Arrange
        current_time = int(time.time() * 1000)
        counts = [45, 46, 47, 48, 49]
        
        mock_dynamodb_client.get_item.return_value = {
            'identifier': 'session_create:user:user-123',
            'count': 45,
            'windowStart': current_time - 1000,
            'expiresAt': int(time.time()) + 3600
        }
        
        # Simulate atomic increments
        mock_dynamodb_client.atomic_increment.side_effect = [46, 47, 48, 49, 50]

        # Act - Simulate 5 concurrent requests
        results = []
        with patch('time.time', return_value=current_time / 1000):
            for i in range(5):
                try:
                    result = rate_limits_repo.check_rate_limit(
                        operation=RateLimitOperation.SESSION_CREATE,
                        identifier_type='user',
                        identifier_value='user-123'
                    )
                    results.append(result)
                except RateLimitExceededError:
                    results.append(False)

        # Assert - All 5 should succeed (45 + 5 = 50, which is the limit)
        assert all(results)
        assert mock_dynamodb_client.atomic_increment.call_count == 5


class TestTTLBasedCleanup:
    """Test TTL-based automatic cleanup."""

    @pytest.fixture
    def mock_dynamodb_client(self):
        """Create mock DynamoDB client."""
        return Mock(spec=DynamoDBClient)

    @pytest.fixture
    def rate_limits_repo(self, mock_dynamodb_client):
        """Create RateLimitsRepository with mock client."""
        return RateLimitsRepository('RateLimits-test', mock_dynamodb_client)

    def test_rate_limit_record_has_ttl(self, rate_limits_repo, mock_dynamodb_client):
        """Test that rate limit records have TTL attribute."""
        # Arrange
        current_time = int(time.time() * 1000)
        mock_dynamodb_client.get_item.return_value = None
        mock_dynamodb_client.put_item.return_value = None

        # Act
        with patch('time.time', return_value=current_time / 1000):
            rate_limits_repo.check_rate_limit(
                operation=RateLimitOperation.SESSION_CREATE,
                identifier_type='user',
                identifier_value='user-123'
            )

        # Assert
        call_args = mock_dynamodb_client.put_item.call_args
        item = call_args[1]['item']
        assert 'expiresAt' in item
        assert item['expiresAt'] > int(time.time())

    def test_ttl_includes_buffer_time(self, rate_limits_repo, mock_dynamodb_client):
        """Test that TTL includes 1-hour buffer beyond window duration."""
        # Arrange
        current_time = int(time.time() * 1000)
        mock_dynamodb_client.get_item.return_value = None
        mock_dynamodb_client.put_item.return_value = None

        # Act - Session creation (1 hour window)
        with patch('time.time', return_value=current_time / 1000):
            rate_limits_repo.check_rate_limit(
                operation=RateLimitOperation.SESSION_CREATE,
                identifier_type='user',
                identifier_value='user-123'
            )

        # Assert
        call_args = mock_dynamodb_client.put_item.call_args
        item = call_args[1]['item']
        
        # TTL should be window_start + 1 hour window + 1 hour buffer = 2 hours
        expected_ttl = int(current_time / 1000) + 3600 + 3600
        assert item['expiresAt'] == expected_ttl

    def test_listener_join_ttl_shorter_than_session_create(
        self, rate_limits_repo, mock_dynamodb_client
    ):
        """Test that listener join TTL is shorter (1 minute window)."""
        # Arrange
        current_time = int(time.time() * 1000)
        mock_dynamodb_client.get_item.return_value = None
        mock_dynamodb_client.put_item.return_value = None

        # Act - Listener join (1 minute window)
        with patch('time.time', return_value=current_time / 1000):
            rate_limits_repo.check_rate_limit(
                operation=RateLimitOperation.LISTENER_JOIN,
                identifier_type='ip',
                identifier_value='192.168.1.1'
            )

        # Assert
        call_args = mock_dynamodb_client.put_item.call_args
        item = call_args[1]['item']
        
        # TTL should be window_start + 1 minute window + 1 hour buffer
        expected_ttl = int(current_time / 1000) + 60 + 3600
        assert item['expiresAt'] == expected_ttl


class TestRateLimitService:
    """Test RateLimitService integration."""

    @pytest.fixture
    def mock_rate_limits_repo(self):
        """Create mock RateLimitsRepository."""
        return Mock(spec=RateLimitsRepository)

    @pytest.fixture
    def rate_limit_service(self, mock_rate_limits_repo):
        """Create RateLimitService with mock repository."""
        return RateLimitService(mock_rate_limits_repo)

    def test_check_session_creation_limit_success(
        self, rate_limit_service, mock_rate_limits_repo
    ):
        """Test successful session creation rate limit check."""
        # Arrange
        mock_rate_limits_repo.check_rate_limit.return_value = True

        # Act
        rate_limit_service.check_session_creation_limit('user-123')

        # Assert
        mock_rate_limits_repo.check_rate_limit.assert_called_once_with(
            operation=RateLimitOperation.SESSION_CREATE,
            identifier_type='user',
            identifier_value='user-123'
        )

    def test_check_session_creation_limit_exceeded(
        self, rate_limit_service, mock_rate_limits_repo
    ):
        """Test session creation rate limit exceeded."""
        # Arrange
        mock_rate_limits_repo.check_rate_limit.side_effect = RateLimitExceededError(
            'Rate limit exceeded', retry_after=1800
        )

        # Act & Assert
        with pytest.raises(RateLimitExceededError) as exc_info:
            rate_limit_service.check_session_creation_limit('user-123')

        assert exc_info.value.retry_after == 1800

    def test_check_listener_join_limit_success(
        self, rate_limit_service, mock_rate_limits_repo
    ):
        """Test successful listener join rate limit check."""
        # Arrange
        mock_rate_limits_repo.check_rate_limit.return_value = True

        # Act
        rate_limit_service.check_listener_join_limit('192.168.1.1')

        # Assert
        mock_rate_limits_repo.check_rate_limit.assert_called_once_with(
            operation=RateLimitOperation.LISTENER_JOIN,
            identifier_type='ip',
            identifier_value='192.168.1.1'
        )

    def test_check_heartbeat_limit_success(
        self, rate_limit_service, mock_rate_limits_repo
    ):
        """Test successful heartbeat rate limit check."""
        # Arrange
        mock_rate_limits_repo.check_rate_limit.return_value = True

        # Act
        rate_limit_service.check_heartbeat_limit('conn-123')

        # Assert
        mock_rate_limits_repo.check_rate_limit.assert_called_once_with(
            operation=RateLimitOperation.HEARTBEAT,
            identifier_type='connection',
            identifier_value='conn-123'
        )

    def test_get_rate_limit_status(self, rate_limit_service, mock_rate_limits_repo):
        """Test getting rate limit status."""
        # Arrange
        expected_status = {
            'count': 15,
            'limit': 50,
            'reset_in_seconds': 1800,
            'window_duration': 3600
        }
        mock_rate_limits_repo.get_rate_limit_status.return_value = expected_status

        # Act
        status = rate_limit_service.get_rate_limit_status(
            operation=RateLimitOperation.SESSION_CREATE,
            identifier_type='user',
            identifier_value='user-123'
        )

        # Assert
        assert status == expected_status
        mock_rate_limits_repo.get_rate_limit_status.assert_called_once()


class TestGracefulDegradation:
    """Test graceful degradation when rate limiting fails."""

    @pytest.fixture
    def mock_dynamodb_client(self):
        """Create mock DynamoDB client."""
        return Mock(spec=DynamoDBClient)

    @pytest.fixture
    def rate_limits_repo(self, mock_dynamodb_client):
        """Create RateLimitsRepository with mock client."""
        return RateLimitsRepository('RateLimits-test', mock_dynamodb_client)

    def test_dynamodb_error_allows_request(self, rate_limits_repo, mock_dynamodb_client):
        """Test that DynamoDB errors allow request (fail open)."""
        # Arrange
        mock_dynamodb_client.get_item.side_effect = ClientError(
            {'Error': {'Code': 'InternalServerError', 'Message': 'Server error'}},
            'GetItem'
        )

        # Act
        result = rate_limits_repo.check_rate_limit(
            operation=RateLimitOperation.SESSION_CREATE,
            identifier_type='user',
            identifier_value='user-123'
        )

        # Assert - Should allow request despite error
        assert result is True

    def test_unexpected_error_allows_request(self, rate_limits_repo, mock_dynamodb_client):
        """Test that unexpected errors allow request."""
        # Arrange
        mock_dynamodb_client.get_item.side_effect = Exception('Unexpected error')

        # Act
        result = rate_limits_repo.check_rate_limit(
            operation=RateLimitOperation.SESSION_CREATE,
            identifier_type='user',
            identifier_value='user-123'
        )

        # Assert - Should allow request despite error
        assert result is True

