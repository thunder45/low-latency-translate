"""
Connections Repository for querying listener connections.

This repository provides methods to query the Connections DynamoDB table
using the sessionId-targetLanguage GSI for efficient language-based queries.
"""

import logging
from typing import List, Set

logger = logging.getLogger(__name__)


class ConnectionsRepository:
    """
    Repository for querying listener connections by session and language.
    
    Uses the sessionId-targetLanguage-index GSI for efficient queries.
    """
    
    def __init__(self, table_name: str, dynamodb_client):
        """
        Initialize connections repository.
        
        Args:
            table_name: DynamoDB Connections table name
            dynamodb_client: boto3 DynamoDB client
        """
        self.table_name = table_name
        self.dynamodb = dynamodb_client
        self.gsi_name = "sessionId-targetLanguage-index"
    
    async def get_unique_target_languages(self, session_id: str) -> List[str]:
        """
        Get unique target languages for a session.
        
        Queries the GSI to find all listener connections for the session
        and extracts unique target languages.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of unique target language codes
        """
        try:
            response = self.dynamodb.query(
                TableName=self.table_name,
                IndexName=self.gsi_name,
                KeyConditionExpression='sessionId = :sid',
                FilterExpression='#role = :role',
                ExpressionAttributeNames={
                    '#role': 'role'
                },
                ExpressionAttributeValues={
                    ':sid': {'S': session_id},
                    ':role': {'S': 'listener'}
                },
                ProjectionExpression='targetLanguage'
            )
            
            # Extract unique languages
            languages = set()
            for item in response.get('Items', []):
                if 'targetLanguage' in item:
                    languages.add(item['targetLanguage']['S'])
            
            logger.info(
                f"Found {len(languages)} unique target languages for session {session_id}: "
                f"{languages}"
            )
            
            return list(languages)
            
        except Exception as e:
            logger.error(
                f"Failed to get unique target languages for session {session_id}: {e}",
                exc_info=True
            )
            return []
    
    async def get_listeners_for_language(
        self,
        session_id: str,
        target_language: str
    ) -> List[str]:
        """
        Get all listener connection IDs for a specific language.
        
        Queries the GSI with both sessionId and targetLanguage conditions.
        
        Args:
            session_id: Session identifier
            target_language: Target language code
            
        Returns:
            List of connection IDs
        """
        try:
            response = self.dynamodb.query(
                TableName=self.table_name,
                IndexName=self.gsi_name,
                KeyConditionExpression='sessionId = :sid AND targetLanguage = :lang',
                FilterExpression='#role = :role',
                ExpressionAttributeNames={
                    '#role': 'role'
                },
                ExpressionAttributeValues={
                    ':sid': {'S': session_id},
                    ':lang': {'S': target_language},
                    ':role': {'S': 'listener'}
                },
                ProjectionExpression='connectionId'
            )
            
            # Extract connection IDs
            connection_ids = []
            for item in response.get('Items', []):
                if 'connectionId' in item:
                    connection_ids.append(item['connectionId']['S'])
            
            logger.info(
                f"Found {len(connection_ids)} listeners for session {session_id}, "
                f"language {target_language}"
            )
            
            return connection_ids
            
        except Exception as e:
            logger.error(
                f"Failed to get listeners for session {session_id}, "
                f"language {target_language}: {e}",
                exc_info=True
            )
            return []
    
    async def remove_connection(self, connection_id: str) -> bool:
        """
        Remove a stale connection from the table.
        
        Args:
            connection_id: Connection ID to remove
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.dynamodb.delete_item(
                TableName=self.table_name,
                Key={
                    'connectionId': {'S': connection_id}
                }
            )
            
            logger.info(f"Removed stale connection: {connection_id}")
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to remove connection {connection_id}: {e}",
                exc_info=True
            )
            return False
