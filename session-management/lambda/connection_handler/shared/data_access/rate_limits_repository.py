"""
Repository for RateLimits table operations using token bucket algorithm.
"""
import time
import logging
from typing import Optional
from enum import Enum

from .dynamodb_client import DynamoDBClient
from .exceptions import DynamoDBError, RateLimitExceededError

logger = logging.getLogger(__name__)


class RateLimitOperation(Enum):
    """Rate limit operation types."""
    SESSION_CREATE = 'session_create'
    LISTENER_JOIN = 'listener_join'
    CONNECTION_ATTEMPT = 'connection_attempt'
    HEARTBEAT = 'heartbeat'


class RateLimitsRepository:
    """
    Repository for managing rate limits using token bucket algorithm.
    
    The token bucket algorithm allows a certain number of requests within
    a time window. Each request consumes a token, and tokens are replenished
    when the window resets.
    """

    def __init__(self, table_name: str, dynamodb_client: Optional[DynamoDBClient] = None):
        """
        Initialize RateLimits repository.

        Args:
            table_name: Name of the RateLimits table
            dynamodb_client: Optional DynamoDB client instance
        """
        self.table_name = table_name
        self.client = dynamodb_client or DynamoDBClient()

    def _get_identifier(
        self,
        operation: RateLimitOperation,
        identifier_type: str,
        identifier_value: str
    ) -> str:
        """
        Generate rate limit identifier.

        Args:
            operation: Rate limit operation type
            identifier_type: Type of identifier (user, ip, connection)
            identifier_value: Value of the identifier

        Returns:
            Formatted identifier string
        """
        return f"{operation.value}:{identifier_type}:{identifier_value}"

    def _get_window_duration(self, operation: RateLimitOperation) -> int:
        """
        Get window duration in seconds for operation type.

        Args:
            operation: Rate limit operation type

        Returns:
            Window duration in seconds
        """
        # Import here to avoid circular dependency
        from shared.config.constants import (
            RATE_LIMIT_SESSIONS_PER_HOUR,
            RATE_LIMIT_LISTENER_JOINS_PER_MIN,
            RATE_LIMIT_CONNECTION_ATTEMPTS_PER_MIN,
            RATE_LIMIT_HEARTBEATS_PER_MIN
        )

        if operation == RateLimitOperation.SESSION_CREATE:
            return 3600  # 1 hour
        elif operation in [
            RateLimitOperation.LISTENER_JOIN,
            RateLimitOperation.CONNECTION_ATTEMPT,
            RateLimitOperation.HEARTBEAT
        ]:
            return 60  # 1 minute
        else:
            return 60  # Default to 1 minute

    def _get_limit(self, operation: RateLimitOperation) -> int:
        """
        Get rate limit for operation type.

        Args:
            operation: Rate limit operation type

        Returns:
            Maximum number of requests allowed in window
        """
        # Import here to avoid circular dependency
        from shared.config.constants import (
            RATE_LIMIT_SESSIONS_PER_HOUR,
            RATE_LIMIT_LISTENER_JOINS_PER_MIN,
            RATE_LIMIT_CONNECTION_ATTEMPTS_PER_MIN,
            RATE_LIMIT_HEARTBEATS_PER_MIN
        )

        limits = {
            RateLimitOperation.SESSION_CREATE: RATE_LIMIT_SESSIONS_PER_HOUR,
            RateLimitOperation.LISTENER_JOIN: RATE_LIMIT_LISTENER_JOINS_PER_MIN,
            RateLimitOperation.CONNECTION_ATTEMPT: RATE_LIMIT_CONNECTION_ATTEMPTS_PER_MIN,
            RateLimitOperation.HEARTBEAT: RATE_LIMIT_HEARTBEATS_PER_MIN
        }
        return limits.get(operation, 10)  # Default to 10 if not found

    def check_rate_limit(
        self,
        operation: RateLimitOperation,
        identifier_type: str,
        identifier_value: str
    ) -> bool:
        """
        Check if request is within rate limit using token bucket algorithm.

        Args:
            operation: Rate limit operation type
            identifier_type: Type of identifier (user, ip, connection)
            identifier_value: Value of the identifier

        Returns:
            True if within limit, False otherwise

        Raises:
            RateLimitExceededError: If rate limit is exceeded
            DynamoDBError: On DynamoDB errors
        """
        identifier = self._get_identifier(operation, identifier_type, identifier_value)
        current_time = int(time.time() * 1000)  # milliseconds
        window_duration = self._get_window_duration(operation)
        limit = self._get_limit(operation)

        try:
            # Try to get existing rate limit record
            rate_limit = self.client.get_item(
                table_name=self.table_name,
                key={'identifier': identifier}
            )

            if rate_limit:
                window_start = rate_limit.get('windowStart', 0)
                count = rate_limit.get('count', 0)
                
                # Check if we're still in the same window
                window_elapsed = (current_time - window_start) / 1000  # seconds
                
                if window_elapsed < window_duration:
                    # Still in same window
                    if count >= limit:
                        # Rate limit exceeded
                        retry_after = int(window_duration - window_elapsed)
                        logger.warning(
                            f"Rate limit exceeded for {identifier}: "
                            f"{count}/{limit} in window, retry after {retry_after}s"
                        )
                        raise RateLimitExceededError(
                            f"Rate limit exceeded. Retry after {retry_after} seconds.",
                            retry_after=retry_after
                        )
                    
                    # Increment counter
                    self._increment_counter(identifier)
                    logger.debug(f"Rate limit check passed for {identifier}: {count + 1}/{limit}")
                    return True
                else:
                    # Window expired, reset counter
                    self._reset_counter(identifier, current_time, window_duration)
                    logger.debug(f"Rate limit window reset for {identifier}")
                    return True
            else:
                # No existing record, create new one
                self._reset_counter(identifier, current_time, window_duration)
                logger.debug(f"Rate limit initialized for {identifier}")
                return True

        except RateLimitExceededError:
            # Re-raise rate limit errors
            raise
        except Exception as e:
            logger.error(f"Error checking rate limit for {identifier}: {e}")
            # On error, allow the request (fail open for availability)
            logger.warning(f"Rate limiting disabled due to error, allowing request")
            return True

    def _increment_counter(self, identifier: str) -> None:
        """
        Increment rate limit counter.

        Args:
            identifier: Rate limit identifier
        """
        self.client.atomic_increment(
            table_name=self.table_name,
            key={'identifier': identifier},
            attribute_name='count',
            increment_value=1
        )

    def _reset_counter(
        self,
        identifier: str,
        window_start: int,
        window_duration: int
    ) -> None:
        """
        Reset rate limit counter for new window.

        Args:
            identifier: Rate limit identifier
            window_start: Window start timestamp in milliseconds
            window_duration: Window duration in seconds
        """
        # Calculate TTL (window start + duration + 1 hour buffer)
        expires_at = int(window_start / 1000) + window_duration + 3600

        item = {
            'identifier': identifier,
            'count': 1,
            'windowStart': window_start,
            'expiresAt': expires_at
        }

        self.client.put_item(
            table_name=self.table_name,
            item=item
        )

    def get_rate_limit_status(
        self,
        operation: RateLimitOperation,
        identifier_type: str,
        identifier_value: str
    ) -> dict:
        """
        Get current rate limit status for debugging/monitoring.

        Args:
            operation: Rate limit operation type
            identifier_type: Type of identifier (user, ip, connection)
            identifier_value: Value of the identifier

        Returns:
            Dict with current count, limit, and time until reset
        """
        identifier = self._get_identifier(operation, identifier_type, identifier_value)
        current_time = int(time.time() * 1000)
        window_duration = self._get_window_duration(operation)
        limit = self._get_limit(operation)

        rate_limit = self.client.get_item(
            table_name=self.table_name,
            key={'identifier': identifier}
        )

        if not rate_limit:
            return {
                'count': 0,
                'limit': limit,
                'reset_in_seconds': 0,
                'window_duration': window_duration
            }

        window_start = rate_limit.get('windowStart', 0)
        count = rate_limit.get('count', 0)
        window_elapsed = (current_time - window_start) / 1000

        reset_in = max(0, int(window_duration - window_elapsed))

        return {
            'count': count,
            'limit': limit,
            'reset_in_seconds': reset_in,
            'window_duration': window_duration
        }

