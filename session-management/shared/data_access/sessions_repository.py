"""
Repository for Sessions table operations.
"""
import time
import logging
from typing import Dict, Optional, Any

from .dynamodb_client import DynamoDBClient
from .exceptions import ItemNotFoundError, ConditionalCheckFailedError

logger = logging.getLogger(__name__)


class SessionsRepository:
    """
    Repository for managing session records in DynamoDB.
    """

    def __init__(self, table_name: str, dynamodb_client: Optional[DynamoDBClient] = None):
        """
        Initialize Sessions repository.

        Args:
            table_name: Name of the Sessions table
            dynamodb_client: Optional DynamoDB client instance
        """
        self.table_name = table_name
        self.client = dynamodb_client or DynamoDBClient()

    def create_session(
        self,
        session_id: str,
        speaker_connection_id: str,
        speaker_user_id: str,
        source_language: str,
        quality_tier: str,
        session_max_duration_hours: int = 2
    ) -> Dict[str, Any]:
        """
        Create a new session record.

        Args:
            session_id: Unique session identifier
            speaker_connection_id: WebSocket connection ID of the speaker
            speaker_user_id: User ID of the speaker
            source_language: Source language code
            quality_tier: Quality tier (standard or premium)
            session_max_duration_hours: Maximum session duration in hours

        Returns:
            Created session item

        Raises:
            ConditionalCheckFailedError: If session ID already exists
        """
        current_time = int(time.time() * 1000)
        expires_at = int(time.time()) + (session_max_duration_hours * 3600)

        session_item = {
            'sessionId': session_id,
            'speakerConnectionId': speaker_connection_id,
            'speakerUserId': speaker_user_id,
            'sourceLanguage': source_language,
            'qualityTier': quality_tier,
            'createdAt': current_time,
            'isActive': True,
            'listenerCount': 0,
            'expiresAt': expires_at
        }

        # Ensure session ID doesn't already exist
        self.client.put_item(
            table_name=self.table_name,
            item=session_item,
            condition_expression='attribute_not_exists(sessionId)'
        )

        logger.info(f"Created session {session_id}")
        return session_item

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session item or None if not found
        """
        return self.client.get_item(
            table_name=self.table_name,
            key={'sessionId': session_id}
        )

    def update_speaker_connection(
        self,
        session_id: str,
        new_connection_id: str
    ) -> None:
        """
        Update speaker connection ID (for connection refresh).

        Args:
            session_id: Session identifier
            new_connection_id: New WebSocket connection ID

        Raises:
            ConditionalCheckFailedError: If session doesn't exist or is inactive
        """
        self.client.update_item(
            table_name=self.table_name,
            key={'sessionId': session_id},
            update_expression='SET speakerConnectionId = :conn',
            condition_expression='attribute_exists(sessionId) AND isActive = :true',
            expression_attribute_values={
                ':conn': new_connection_id,
                ':true': True
            }
        )
        logger.info(f"Updated speaker connection for session {session_id}")

    def increment_listener_count(self, session_id: str) -> int:
        """
        Atomically increment listener count.

        Args:
            session_id: Session identifier

        Returns:
            New listener count

        Raises:
            ConditionalCheckFailedError: If session doesn't exist or is inactive
        """
        new_count = self.client.atomic_increment(
            table_name=self.table_name,
            key={'sessionId': session_id},
            attribute_name='listenerCount',
            increment_value=1,
            condition_expression='attribute_exists(sessionId) AND isActive = :true',
            expression_attribute_values={':true': True}
        )
        logger.info(f"Incremented listener count for session {session_id} to {new_count}")
        return new_count

    def decrement_listener_count(self, session_id: str) -> int:
        """
        Atomically decrement listener count with floor of 0.

        Args:
            session_id: Session identifier

        Returns:
            New listener count
        """
        new_count = self.client.atomic_decrement_with_floor(
            table_name=self.table_name,
            key={'sessionId': session_id},
            attribute_name='listenerCount',
            decrement_value=1,
            floor_value=0
        )
        logger.info(f"Decremented listener count for session {session_id} to {new_count}")
        return new_count

    def mark_session_inactive(self, session_id: str) -> None:
        """
        Mark session as inactive (when speaker disconnects).

        Args:
            session_id: Session identifier
        """
        self.client.update_item(
            table_name=self.table_name,
            key={'sessionId': session_id},
            update_expression='SET isActive = :false',
            expression_attribute_values={':false': False}
        )
        logger.info(f"Marked session {session_id} as inactive")

    def session_exists(self, session_id: str) -> bool:
        """
        Check if session exists.

        Args:
            session_id: Session identifier

        Returns:
            True if session exists, False otherwise
        """
        session = self.get_session(session_id)
        return session is not None

    def is_session_active(self, session_id: str) -> bool:
        """
        Check if session is active.

        Args:
            session_id: Session identifier

        Returns:
            True if session exists and is active, False otherwise
        """
        session = self.get_session(session_id)
        return session is not None and session.get('isActive', False)
