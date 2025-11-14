"""
Atomic Counter for DynamoDB listener count updates.

This module provides atomic increment and decrement operations for the
listenerCount attribute in the Sessions table, preventing race conditions
during concurrent listener joins and disconnects.
"""

import logging
from typing import Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class AtomicCounterError(Exception):
    """Base exception for atomic counter operations."""
    pass


class NegativeCountError(AtomicCounterError):
    """Raised when attempting to decrement below zero."""
    pass


class AtomicCounter:
    """
    Atomic counter for DynamoDB listener count management.
    
    Uses DynamoDB's ADD operation for atomic increments and decrements,
    ensuring thread-safe updates even with concurrent operations.
    """
    
    def __init__(self, dynamodb_client, table_name: str):
        """
        Initialize atomic counter.
        
        Args:
            dynamodb_client: Boto3 DynamoDB client
            table_name: Name of the Sessions table
        """
        self.dynamodb_client = dynamodb_client
        self.table_name = table_name
    
    async def increment_listener_count(
        self,
        session_id: str,
        increment_by: int = 1
    ) -> int:
        """
        Atomically increment listener count for a session.
        
        Args:
            session_id: Session identifier
            increment_by: Amount to increment (default: 1)
            
        Returns:
            New listener count after increment
            
        Raises:
            AtomicCounterError: If update fails
        """
        try:
            response = self.dynamodb_client.update_item(
                TableName=self.table_name,
                Key={'sessionId': {'S': session_id}},
                UpdateExpression='ADD listenerCount :inc',
                ExpressionAttributeValues={
                    ':inc': {'N': str(increment_by)}
                },
                ReturnValues='UPDATED_NEW'
            )
            
            new_count = int(response['Attributes']['listenerCount']['N'])
            
            logger.info(
                f"Incremented listener count for session {session_id}: "
                f"new count = {new_count}"
            )
            
            return new_count
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(
                f"Failed to increment listener count for session {session_id}: "
                f"{error_code} - {e}",
                exc_info=True
            )
            raise AtomicCounterError(
                f"Failed to increment listener count: {error_code}"
            ) from e
    
    async def decrement_listener_count(
        self,
        session_id: str,
        decrement_by: int = 1
    ) -> int:
        """
        Atomically decrement listener count for a session.
        
        Ensures count never goes below zero by using a condition expression.
        
        Args:
            session_id: Session identifier
            decrement_by: Amount to decrement (default: 1)
            
        Returns:
            New listener count after decrement
            
        Raises:
            NegativeCountError: If decrement would result in negative count
            AtomicCounterError: If update fails for other reasons
        """
        try:
            response = self.dynamodb_client.update_item(
                TableName=self.table_name,
                Key={'sessionId': {'S': session_id}},
                UpdateExpression='ADD listenerCount :dec',
                ConditionExpression='listenerCount >= :min',
                ExpressionAttributeValues={
                    ':dec': {'N': str(-decrement_by)},
                    ':min': {'N': str(decrement_by)}
                },
                ReturnValues='UPDATED_NEW'
            )
            
            new_count = int(response['Attributes']['listenerCount']['N'])
            
            logger.info(
                f"Decremented listener count for session {session_id}: "
                f"new count = {new_count}"
            )
            
            return new_count
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'ConditionalCheckFailedException':
                logger.warning(
                    f"Cannot decrement listener count for session {session_id}: "
                    f"would result in negative count"
                )
                raise NegativeCountError(
                    f"Listener count cannot be negative for session {session_id}"
                ) from e
            
            logger.error(
                f"Failed to decrement listener count for session {session_id}: "
                f"{error_code} - {e}",
                exc_info=True
            )
            raise AtomicCounterError(
                f"Failed to decrement listener count: {error_code}"
            ) from e
    
    async def get_listener_count(self, session_id: str) -> Optional[int]:
        """
        Get current listener count for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Current listener count, or None if session not found
        """
        try:
            response = self.dynamodb_client.get_item(
                TableName=self.table_name,
                Key={'sessionId': {'S': session_id}},
                ProjectionExpression='listenerCount'
            )
            
            if 'Item' not in response:
                logger.warning(f"Session {session_id} not found")
                return None
            
            count = int(response['Item']['listenerCount']['N'])
            return count
            
        except ClientError as e:
            logger.error(
                f"Failed to get listener count for session {session_id}: {e}",
                exc_info=True
            )
            return None
