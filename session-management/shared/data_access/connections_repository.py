"""
Repository for Connections table operations.
"""
import time
import logging
from typing import Dict, List, Optional, Any

from .dynamodb_client import DynamoDBClient
from .exceptions import ItemNotFoundError

logger = logging.getLogger(__name__)


class ConnectionsRepository:
    """
    Repository for managing connection records in DynamoDB.
    """

    def __init__(self, table_name: str, dynamodb_client: Optional[DynamoDBClient] = None):
        """
        Initialize Connections repository.

        Args:
            table_name: Name of the Connections table
            dynamodb_client: Optional DynamoDB client instance
        """
        self.table_name = table_name
        self.client = dynamodb_client or DynamoDBClient()

    def create_connection(
        self,
        connection_id: str,
        session_id: str,
        role: str,
        target_language: Optional[str] = None,
        ip_address: Optional[str] = None,
        session_max_duration_hours: int = 2
    ) -> Dict[str, Any]:
        """
        Create a new connection record.

        Args:
            connection_id: WebSocket connection ID
            session_id: Session identifier
            role: Connection role (speaker or listener)
            target_language: Target language code (for listeners)
            ip_address: Client IP address
            session_max_duration_hours: Maximum session duration in hours

        Returns:
            Created connection item
        """
        current_time = int(time.time() * 1000)
        ttl = int(time.time()) + ((session_max_duration_hours + 1) * 3600)  # +1 hour buffer

        connection_item = {
            'connectionId': connection_id,
            'sessionId': session_id,
            'role': role,
            'connectedAt': current_time,
            'ttl': ttl
        }

        if target_language:
            connection_item['targetLanguage'] = target_language

        if ip_address:
            connection_item['ipAddress'] = ip_address

        self.client.put_item(
            table_name=self.table_name,
            item=connection_item
        )

        logger.info(f"Created connection {connection_id} for session {session_id}")
        return connection_item

    def get_connection(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """
        Get connection by ID.

        Args:
            connection_id: Connection identifier

        Returns:
            Connection item or None if not found
        """
        return self.client.get_item(
            table_name=self.table_name,
            key={'connectionId': connection_id}
        )

    def delete_connection(self, connection_id: str) -> None:
        """
        Delete connection record.

        Args:
            connection_id: Connection identifier
        """
        self.client.delete_item(
            table_name=self.table_name,
            key={'connectionId': connection_id}
        )
        logger.info(f"Deleted connection {connection_id}")

    def get_connections_by_session(
        self,
        session_id: str,
        target_language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all connections for a session, optionally filtered by target language.

        Args:
            session_id: Session identifier
            target_language: Optional target language filter

        Returns:
            List of connection items
        """
        if target_language:
            # Query using GSI with both sessionId and targetLanguage
            key_condition = 'sessionId = :sid AND targetLanguage = :lang'
            attr_values = {
                ':sid': session_id,
                ':lang': target_language
            }
        else:
            # Query using GSI with only sessionId
            key_condition = 'sessionId = :sid'
            attr_values = {':sid': session_id}

        connections = self.client.query(
            table_name=self.table_name,
            index_name='sessionId-targetLanguage-index',
            key_condition_expression=key_condition,
            expression_attribute_values=attr_values
        )

        return connections

    def get_listener_connections(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all listener connections for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of listener connection items
        """
        connections = self.client.query(
            table_name=self.table_name,
            index_name='sessionId-targetLanguage-index',
            key_condition_expression='sessionId = :sid',
            filter_expression='#role = :role',
            expression_attribute_names={'#role': 'role'},
            expression_attribute_values={
                ':sid': session_id,
                ':role': 'listener'
            }
        )

        return connections

    def get_unique_languages_for_session(self, session_id: str) -> List[str]:
        """
        Get unique target languages for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of unique language codes
        """
        connections = self.get_listener_connections(session_id)
        languages = set(
            conn.get('targetLanguage')
            for conn in connections
            if conn.get('targetLanguage')
        )
        return list(languages)

    def batch_delete_connections(self, connection_ids: List[str]) -> None:
        """
        Batch delete multiple connections.

        Args:
            connection_ids: List of connection IDs to delete
        """
        if not connection_ids:
            return

        keys = [{'connectionId': conn_id} for conn_id in connection_ids]
        self.client.batch_delete(
            table_name=self.table_name,
            keys=keys
        )
        logger.info(f"Batch deleted {len(connection_ids)} connections")

    def delete_all_session_connections(self, session_id: str) -> int:
        """
        Delete all connections for a session.

        Args:
            session_id: Session identifier

        Returns:
            Number of connections deleted
        """
        connections = self.get_connections_by_session(session_id)
        connection_ids = [conn['connectionId'] for conn in connections]

        if connection_ids:
            self.batch_delete_connections(connection_ids)

        return len(connection_ids)

    def scan_all_connections(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Scan all connections in the table.
        
        Note: This is used by the timeout handler to check for idle connections.
        In production with many connections, this should use pagination.
        
        Args:
            limit: Optional limit on number of items to return
            
        Returns:
            List of all connection items
        """
        connections = self.client.scan(
            table_name=self.table_name,
            limit=limit
        )
        
        logger.info(f"Scanned {len(connections)} connections")
        return connections
