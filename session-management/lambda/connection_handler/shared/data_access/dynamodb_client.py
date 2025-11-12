"""
DynamoDB client with atomic operations and error handling.
"""
import time
import random
import logging
from typing import Dict, List, Optional, Any
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from .exceptions import (
    DynamoDBError,
    ItemNotFoundError,
    ConditionalCheckFailedError,
    RetryableError,
)

logger = logging.getLogger(__name__)


class DynamoDBClient:
    """
    DynamoDB client with atomic operations, retry logic, and error handling.
    """

    def __init__(self, region: str = 'us-east-1'):
        """
        Initialize DynamoDB client.

        Args:
            region: AWS region for DynamoDB
        """
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.client = boto3.client('dynamodb', region_name=region)

    def get_table(self, table_name: str):
        """
        Get DynamoDB table resource.

        Args:
            table_name: Name of the table

        Returns:
            DynamoDB table resource
        """
        return self.dynamodb.Table(table_name)

    def get_item(
        self,
        table_name: str,
        key: Dict[str, Any],
        consistent_read: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get item from DynamoDB table.

        Args:
            table_name: Name of the table
            key: Primary key of the item
            consistent_read: Whether to use consistent read

        Returns:
            Item dict or None if not found

        Raises:
            DynamoDBError: On DynamoDB errors
        """
        try:
            table = self.get_table(table_name)
            response = table.get_item(
                Key=key,
                ConsistentRead=consistent_read
            )
            return response.get('Item')
        except ClientError as e:
            logger.error(f"Error getting item from {table_name}: {e}")
            raise DynamoDBError(f"Failed to get item: {e}")

    def put_item(
        self,
        table_name: str,
        item: Dict[str, Any],
        condition_expression: Optional[str] = None,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Put item into DynamoDB table.

        Args:
            table_name: Name of the table
            item: Item to put
            condition_expression: Optional condition expression
            expression_attribute_values: Optional expression attribute values
            expression_attribute_names: Optional expression attribute names

        Raises:
            ConditionalCheckFailedError: If condition check fails
            DynamoDBError: On other DynamoDB errors
        """
        try:
            table = self.get_table(table_name)
            kwargs = {'Item': item}

            if condition_expression:
                kwargs['ConditionExpression'] = condition_expression
            if expression_attribute_values:
                kwargs['ExpressionAttributeValues'] = expression_attribute_values
            if expression_attribute_names:
                kwargs['ExpressionAttributeNames'] = expression_attribute_names

            table.put_item(**kwargs)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ConditionalCheckFailedError("Conditional check failed")
            logger.error(f"Error putting item to {table_name}: {e}")
            raise DynamoDBError(f"Failed to put item: {e}")

    def update_item(
        self,
        table_name: str,
        key: Dict[str, Any],
        update_expression: str,
        condition_expression: Optional[str] = None,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None,
        return_values: str = 'NONE'
    ) -> Optional[Dict[str, Any]]:
        """
        Update item in DynamoDB table.

        Args:
            table_name: Name of the table
            key: Primary key of the item
            update_expression: Update expression
            condition_expression: Optional condition expression
            expression_attribute_values: Optional expression attribute values
            expression_attribute_names: Optional expression attribute names
            return_values: What to return (NONE, ALL_OLD, UPDATED_OLD, ALL_NEW, UPDATED_NEW)

        Returns:
            Updated attributes if return_values is not NONE

        Raises:
            ConditionalCheckFailedError: If condition check fails
            DynamoDBError: On other DynamoDB errors
        """
        try:
            table = self.get_table(table_name)
            kwargs = {
                'Key': key,
                'UpdateExpression': update_expression,
                'ReturnValues': return_values
            }

            if condition_expression:
                kwargs['ConditionExpression'] = condition_expression
            if expression_attribute_values:
                kwargs['ExpressionAttributeValues'] = expression_attribute_values
            if expression_attribute_names:
                kwargs['ExpressionAttributeNames'] = expression_attribute_names

            response = table.update_item(**kwargs)
            return response.get('Attributes')
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ConditionalCheckFailedError("Conditional check failed")
            logger.error(f"Error updating item in {table_name}: {e}")
            raise DynamoDBError(f"Failed to update item: {e}")

    def delete_item(
        self,
        table_name: str,
        key: Dict[str, Any],
        condition_expression: Optional[str] = None,
        expression_attribute_values: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Delete item from DynamoDB table.

        Args:
            table_name: Name of the table
            key: Primary key of the item
            condition_expression: Optional condition expression
            expression_attribute_values: Optional expression attribute values

        Raises:
            ConditionalCheckFailedError: If condition check fails
            DynamoDBError: On other DynamoDB errors
        """
        try:
            table = self.get_table(table_name)
            kwargs = {'Key': key}

            if condition_expression:
                kwargs['ConditionExpression'] = condition_expression
            if expression_attribute_values:
                kwargs['ExpressionAttributeValues'] = expression_attribute_values

            table.delete_item(**kwargs)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ConditionalCheckFailedError("Conditional check failed")
            logger.error(f"Error deleting item from {table_name}: {e}")
            raise DynamoDBError(f"Failed to delete item: {e}")

    def query(
        self,
        table_name: str,
        key_condition_expression: str,
        expression_attribute_values: Dict[str, Any],
        index_name: Optional[str] = None,
        filter_expression: Optional[str] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None,
        limit: Optional[int] = None,
        consistent_read: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Query DynamoDB table.

        Args:
            table_name: Name of the table
            key_condition_expression: Key condition expression
            expression_attribute_values: Expression attribute values
            index_name: Optional GSI name
            filter_expression: Optional filter expression
            expression_attribute_names: Optional expression attribute names
            limit: Optional limit on number of items
            consistent_read: Whether to use consistent read

        Returns:
            List of items

        Raises:
            DynamoDBError: On DynamoDB errors
        """
        try:
            table = self.get_table(table_name)
            kwargs = {
                'KeyConditionExpression': key_condition_expression,
                'ExpressionAttributeValues': expression_attribute_values,
                'ConsistentRead': consistent_read
            }

            if index_name:
                kwargs['IndexName'] = index_name
            if filter_expression:
                kwargs['FilterExpression'] = filter_expression
            if expression_attribute_names:
                kwargs['ExpressionAttributeNames'] = expression_attribute_names
            if limit:
                kwargs['Limit'] = limit

            response = table.query(**kwargs)
            return response.get('Items', [])
        except ClientError as e:
            logger.error(f"Error querying {table_name}: {e}")
            raise DynamoDBError(f"Failed to query table: {e}")

    def atomic_increment(
        self,
        table_name: str,
        key: Dict[str, Any],
        attribute_name: str,
        increment_value: int = 1,
        condition_expression: Optional[str] = None,
        expression_attribute_values: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Atomically increment a numeric attribute.

        Args:
            table_name: Name of the table
            key: Primary key of the item
            attribute_name: Name of the attribute to increment
            increment_value: Value to add (can be negative for decrement)
            condition_expression: Optional condition expression
            expression_attribute_values: Optional expression attribute values

        Returns:
            New value after increment

        Raises:
            ConditionalCheckFailedError: If condition check fails
            DynamoDBError: On other DynamoDB errors
        """
        try:
            update_expression = f'ADD {attribute_name} :inc'
            attr_values = {':inc': increment_value}

            if expression_attribute_values:
                attr_values.update(expression_attribute_values)

            result = self.update_item(
                table_name=table_name,
                key=key,
                update_expression=update_expression,
                condition_expression=condition_expression,
                expression_attribute_values=attr_values,
                return_values='ALL_NEW'
            )

            return int(result[attribute_name]) if result else 0
        except Exception as e:
            logger.error(f"Error incrementing {attribute_name} in {table_name}: {e}")
            raise

    def atomic_decrement_with_floor(
        self,
        table_name: str,
        key: Dict[str, Any],
        attribute_name: str,
        decrement_value: int = 1,
        floor_value: int = 0
    ) -> int:
        """
        Atomically decrement a numeric attribute with a floor value.

        Args:
            table_name: Name of the table
            key: Primary key of the item
            attribute_name: Name of the attribute to decrement
            decrement_value: Value to subtract
            floor_value: Minimum value (default 0)

        Returns:
            New value after decrement

        Raises:
            DynamoDBError: On DynamoDB errors
        """
        try:
            # First try to decrement with condition that value > floor
            try:
                update_expression = f'SET {attribute_name} = {attribute_name} - :dec'
                result = self.update_item(
                    table_name=table_name,
                    key=key,
                    update_expression=update_expression,
                    condition_expression=f'{attribute_name} > :floor',
                    expression_attribute_values={
                        ':dec': decrement_value,
                        ':floor': floor_value
                    },
                    return_values='ALL_NEW'
                )
                return int(result[attribute_name]) if result else floor_value
            except ConditionalCheckFailedError:
                # Value is already at or below floor, set to floor
                update_expression = f'SET {attribute_name} = :floor'
                result = self.update_item(
                    table_name=table_name,
                    key=key,
                    update_expression=update_expression,
                    expression_attribute_values={':floor': floor_value},
                    return_values='ALL_NEW'
                )
                return int(result[attribute_name]) if result else floor_value
        except Exception as e:
            logger.error(f"Error decrementing {attribute_name} in {table_name}: {e}")
            raise DynamoDBError(f"Failed to decrement attribute: {e}")

    def batch_write(
        self,
        table_name: str,
        items: List[Dict[str, Any]],
        operation: str = 'put'
    ) -> None:
        """
        Batch write items to DynamoDB table.

        Args:
            table_name: Name of the table
            items: List of items to write
            operation: 'put' or 'delete'

        Raises:
            DynamoDBError: On DynamoDB errors
        """
        try:
            table = self.get_table(table_name)

            with table.batch_writer() as batch:
                for item in items:
                    if operation == 'put':
                        batch.put_item(Item=item)
                    elif operation == 'delete':
                        batch.delete_item(Key=item)
                    else:
                        raise ValueError(f"Invalid operation: {operation}")

        except ClientError as e:
            logger.error(f"Error batch writing to {table_name}: {e}")
            raise DynamoDBError(f"Failed to batch write: {e}")

    def batch_delete(
        self,
        table_name: str,
        keys: List[Dict[str, Any]]
    ) -> None:
        """
        Batch delete items from DynamoDB table.

        Args:
            table_name: Name of the table
            keys: List of primary keys to delete

        Raises:
            DynamoDBError: On DynamoDB errors
        """
        self.batch_write(table_name, keys, operation='delete')

    def retry_with_backoff(
        self,
        operation,
        max_retries: int = 3,
        base_delay: float = 1.0
    ) -> Any:
        """
        Retry operation with exponential backoff.

        Args:
            operation: Callable to retry
            max_retries: Maximum retry attempts
            base_delay: Initial delay in seconds

        Returns:
            Operation result

        Raises:
            Last exception if all retries fail
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                return operation()
            except (RetryableError, ClientError) as e:
                last_exception = e

                # Check if error is retryable
                if isinstance(e, ClientError):
                    error_code = e.response['Error']['Code']
                    if error_code not in [
                        'ProvisionedThroughputExceededException',
                        'ThrottlingException',
                        'RequestLimitExceeded',
                        'InternalServerError',
                        'ServiceUnavailable'
                    ]:
                        # Not a retryable error
                        raise

                if attempt == max_retries - 1:
                    raise

                # Calculate delay with exponential backoff and jitter
                delay = base_delay * (2 ** attempt)
                jitter = random.uniform(0, 0.1 * delay)
                sleep_time = delay + jitter

                logger.warning(
                    f"Retry attempt {attempt + 1}/{max_retries} "
                    f"after {sleep_time:.2f}s: {str(e)}"
                )
                time.sleep(sleep_time)

        if last_exception:
            raise last_exception
