"""
Repository for RateLimits table operations.
"""
import time
import logging
from typing import Dict, Optional, Any

from .dynamodb_client import DynamoDBClient
from .exceptions import ConditionalCheckFailedError

logger = logging.getLogger(__name__)


class RateLimitsRepository:
    """
    Repository for managing rate limit records in DynamoDB.
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

    def check_rate_limit(
        self,
        operation: str,
        identifier_type: str,
        identifier_value: str,
        limit: int,
        window_seconds: int
    ) -> tuple[bool, Optional[int]]:
        """
        Check if rate limit is exceeded and increment counter.

        Args:
            operation: Operation type (e.g., 'session_create', 'listener_join')
            identifier_type: Type of identifier (e.g., 'user', 'ip')
            identifier_value: Identifier value (e.g., user ID, IP address)
            limit: Maximum requests allowed in window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
            - is_allowed: True if request is allowed, False if rate limit exceeded
            - retry_after_seconds: Seconds to wait before retry (None if allowed)
        """
        identifier = f"{operation}:{identifier_type}:{identifier_value}"
        current_time = int(time.time() * 1000)

        # Get existing rate limit record
        rate_limit = self.client.get_item(
            table_name=self.table_name,
            key={'identifier': identifier}
        )

        if rate_limit:
            window_start = rate_limit.get('windowStart', 0)
            count = rate_limit.get('count', 0)
            window_age_ms = current_time - window_start

            # Check if window has expired
            if window_age_ms > (window_seconds * 1000):
                # Window expired, reset counter
                self._reset_rate_limit(identifier, current_time, window_seconds)
                return True, None

            # Window still active, check limit
            if count >= limit:
                # Rate limit exceeded
                remaining_ms = (window_seconds * 1000) - window_age_ms
                retry_after = int(remaining_ms / 1000) + 1
                logger.warning(
                    f"Rate limit exceeded for {identifier}: "
                    f"{count}/{limit} in window"
                )
                return False, retry_after

            # Increment counter
            self._increment_rate_limit(identifier)
            return True, None
        else:
            # No existing record, create new one
            self._reset_rate_limit(identifier, current_time, window_seconds)
            return True, None

    def _reset_rate_limit(
        self,
        identifier: str,
        window_start: int,
        window_seconds: int
    ) -> None:
        """
        Reset rate limit counter for a new window.

        Args:
            identifier: Rate limit identifier
            window_start: Window start timestamp in milliseconds
            window_seconds: Window duration in seconds
        """
        expires_at = int(time.time()) + window_seconds + 3600  # +1 hour buffer

        rate_limit_item = {
            'identifier': identifier,
            'count': 1,
            'windowStart': window_start,
            'expiresAt': expires_at
        }

        self.client.put_item(
            table_name=self.table_name,
            item=rate_limit_item
        )

    def _increment_rate_limit(self, identifier: str) -> None:
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

    def get_rate_limit(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Get rate limit record.

        Args:
            identifier: Rate limit identifier

        Returns:
            Rate limit item or None if not found
        """
        return self.client.get_item(
            table_name=self.table_name,
            key={'identifier': identifier}
        )

    def delete_rate_limit(self, identifier: str) -> None:
        """
        Delete rate limit record.

        Args:
            identifier: Rate limit identifier
        """
        self.client.delete_item(
            table_name=self.table_name,
            key={'identifier': identifier}
        )
        logger.info(f"Deleted rate limit {identifier}")
