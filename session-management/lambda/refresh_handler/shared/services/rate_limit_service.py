"""
Rate limiting service for enforcing request limits.
"""
import os
import logging
from typing import Optional

from shared.data_access import (
    RateLimitsRepository,
    RateLimitOperation,
    RateLimitExceededError,
)

logger = logging.getLogger(__name__)


class RateLimitService:
    """
    Service for checking and enforcing rate limits.
    """

    def __init__(self, rate_limits_repo: Optional[RateLimitsRepository] = None):
        """
        Initialize rate limit service.

        Args:
            rate_limits_repo: Optional RateLimitsRepository instance
        """
        if rate_limits_repo is None:
            table_name = os.environ.get('RATE_LIMITS_TABLE', 'RateLimits')
            rate_limits_repo = RateLimitsRepository(table_name)
        
        self.rate_limits_repo = rate_limits_repo

    def check_session_creation_limit(self, user_id: str) -> None:
        """
        Check rate limit for session creation.

        Args:
            user_id: User ID from JWT token

        Raises:
            RateLimitExceededError: If rate limit exceeded
        """
        try:
            self.rate_limits_repo.check_rate_limit(
                operation=RateLimitOperation.SESSION_CREATE,
                identifier_type='user',
                identifier_value=user_id
            )
            logger.info(f"Session creation rate limit check passed for user {user_id}")
        except RateLimitExceededError as e:
            logger.warning(
                f"Session creation rate limit exceeded for user {user_id}: "
                f"retry after {e.retry_after}s"
            )
            raise

    def check_listener_join_limit(self, ip_address: str) -> None:
        """
        Check rate limit for listener joins.

        Args:
            ip_address: Client IP address

        Raises:
            RateLimitExceededError: If rate limit exceeded
        """
        try:
            self.rate_limits_repo.check_rate_limit(
                operation=RateLimitOperation.LISTENER_JOIN,
                identifier_type='ip',
                identifier_value=ip_address
            )
            logger.info(f"Listener join rate limit check passed for IP {ip_address}")
        except RateLimitExceededError as e:
            logger.warning(
                f"Listener join rate limit exceeded for IP {ip_address}: "
                f"retry after {e.retry_after}s"
            )
            raise

    def check_connection_attempt_limit(self, ip_address: str) -> None:
        """
        Check rate limit for connection attempts.

        Args:
            ip_address: Client IP address

        Raises:
            RateLimitExceededError: If rate limit exceeded
        """
        try:
            self.rate_limits_repo.check_rate_limit(
                operation=RateLimitOperation.CONNECTION_ATTEMPT,
                identifier_type='ip',
                identifier_value=ip_address
            )
            logger.info(f"Connection attempt rate limit check passed for IP {ip_address}")
        except RateLimitExceededError as e:
            logger.warning(
                f"Connection attempt rate limit exceeded for IP {ip_address}: "
                f"retry after {e.retry_after}s"
            )
            raise

    def check_heartbeat_limit(self, connection_id: str) -> None:
        """
        Check rate limit for heartbeat messages.

        Args:
            connection_id: WebSocket connection ID

        Raises:
            RateLimitExceededError: If rate limit exceeded
        """
        try:
            self.rate_limits_repo.check_rate_limit(
                operation=RateLimitOperation.HEARTBEAT,
                identifier_type='connection',
                identifier_value=connection_id
            )
            logger.debug(f"Heartbeat rate limit check passed for connection {connection_id}")
        except RateLimitExceededError as e:
            logger.warning(
                f"Heartbeat rate limit exceeded for connection {connection_id}: "
                f"retry after {e.retry_after}s"
            )
            raise

    def get_rate_limit_status(
        self,
        operation: RateLimitOperation,
        identifier_type: str,
        identifier_value: str
    ) -> dict:
        """
        Get current rate limit status for monitoring.

        Args:
            operation: Rate limit operation type
            identifier_type: Type of identifier (user, ip, connection)
            identifier_value: Value of the identifier

        Returns:
            Dict with current count, limit, and time until reset
        """
        return self.rate_limits_repo.get_rate_limit_status(
            operation=operation,
            identifier_type=identifier_type,
            identifier_value=identifier_value
        )

