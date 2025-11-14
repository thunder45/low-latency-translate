"""
Unit tests for AtomicCounter.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from botocore.exceptions import ClientError
from shared.data_access.atomic_counter import (
    AtomicCounter,
    AtomicCounterError,
    NegativeCountError
)


@pytest.fixture
def mock_dynamodb_client():
    """Create mock DynamoDB client."""
    client = Mock()
    client.update_item = Mock()
    client.get_item = Mock()
    return client


@pytest.fixture
def atomic_counter(mock_dynamodb_client):
    """Create AtomicCounter instance."""
    return AtomicCounter(
        dynamodb_client=mock_dynamodb_client,
        table_name='Sessions'
    )


class TestAtomicCounter:
    """Test suite for AtomicCounter."""
    
    @pytest.mark.asyncio
    async def test_increment_listener_count_succeeds(
        self, atomic_counter, mock_dynamodb_client
    ):
        """Test successful listener count increment."""
        # Arrange
        mock_dynamodb_client.update_item.return_value = {
            'Attributes': {
                'listenerCount': {'N': '5'}
            }
        }
        
        # Act
        new_count = await atomic_counter.increment_listener_count('test-session')
        
        # Assert
        assert new_count == 5
        mock_dynamodb_client.update_item.assert_called_once_with(
            TableName='Sessions',
            Key={'sessionId': {'S': 'test-session'}},
            UpdateExpression='ADD listenerCount :inc',
            ExpressionAttributeValues={':inc': {'N': '1'}},
            ReturnValues='UPDATED_NEW'
        )
    
    @pytest.mark.asyncio
    async def test_increment_listener_count_with_custom_amount(
        self, atomic_counter, mock_dynamodb_client
    ):
        """Test increment with custom amount."""
        # Arrange
        mock_dynamodb_client.update_item.return_value = {
            'Attributes': {
                'listenerCount': {'N': '10'}
            }
        }
        
        # Act
        new_count = await atomic_counter.increment_listener_count(
            'test-session', increment_by=5
        )
        
        # Assert
        assert new_count == 10
        mock_dynamodb_client.update_item.assert_called_once()
        call_args = mock_dynamodb_client.update_item.call_args[1]
        assert call_args['ExpressionAttributeValues'][':inc']['N'] == '5'
    
    @pytest.mark.asyncio
    async def test_increment_listener_count_handles_client_error(
        self, atomic_counter, mock_dynamodb_client
    ):
        """Test error handling for increment operation."""
        # Arrange
        mock_dynamodb_client.update_item.side_effect = ClientError(
            {'Error': {'Code': 'ProvisionedThroughputExceededException'}},
            'UpdateItem'
        )
        
        # Act & Assert
        with pytest.raises(AtomicCounterError) as exc_info:
            await atomic_counter.increment_listener_count('test-session')
        
        assert 'ProvisionedThroughputExceededException' in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_decrement_listener_count_succeeds(
        self, atomic_counter, mock_dynamodb_client
    ):
        """Test successful listener count decrement."""
        # Arrange
        mock_dynamodb_client.update_item.return_value = {
            'Attributes': {
                'listenerCount': {'N': '4'}
            }
        }
        
        # Act
        new_count = await atomic_counter.decrement_listener_count('test-session')
        
        # Assert
        assert new_count == 4
        mock_dynamodb_client.update_item.assert_called_once_with(
            TableName='Sessions',
            Key={'sessionId': {'S': 'test-session'}},
            UpdateExpression='ADD listenerCount :dec',
            ConditionExpression='listenerCount >= :min',
            ExpressionAttributeValues={
                ':dec': {'N': '-1'},
                ':min': {'N': '1'}
            },
            ReturnValues='UPDATED_NEW'
        )
    
    @pytest.mark.asyncio
    async def test_decrement_listener_count_with_custom_amount(
        self, atomic_counter, mock_dynamodb_client
    ):
        """Test decrement with custom amount."""
        # Arrange
        mock_dynamodb_client.update_item.return_value = {
            'Attributes': {
                'listenerCount': {'N': '5'}
            }
        }
        
        # Act
        new_count = await atomic_counter.decrement_listener_count(
            'test-session', decrement_by=3
        )
        
        # Assert
        assert new_count == 5
        call_args = mock_dynamodb_client.update_item.call_args[1]
        assert call_args['ExpressionAttributeValues'][':dec']['N'] == '-3'
        assert call_args['ExpressionAttributeValues'][':min']['N'] == '3'
    
    @pytest.mark.asyncio
    async def test_decrement_listener_count_prevents_negative(
        self, atomic_counter, mock_dynamodb_client
    ):
        """Test that decrement prevents negative count."""
        # Arrange
        mock_dynamodb_client.update_item.side_effect = ClientError(
            {'Error': {'Code': 'ConditionalCheckFailedException'}},
            'UpdateItem'
        )
        
        # Act & Assert
        with pytest.raises(NegativeCountError) as exc_info:
            await atomic_counter.decrement_listener_count('test-session')
        
        assert 'cannot be negative' in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_decrement_listener_count_handles_other_errors(
        self, atomic_counter, mock_dynamodb_client
    ):
        """Test error handling for decrement operation."""
        # Arrange
        mock_dynamodb_client.update_item.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException'}},
            'UpdateItem'
        )
        
        # Act & Assert
        with pytest.raises(AtomicCounterError) as exc_info:
            await atomic_counter.decrement_listener_count('test-session')
        
        assert 'ResourceNotFoundException' in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_listener_count_succeeds(
        self, atomic_counter, mock_dynamodb_client
    ):
        """Test successful listener count retrieval."""
        # Arrange
        mock_dynamodb_client.get_item.return_value = {
            'Item': {
                'listenerCount': {'N': '10'}
            }
        }
        
        # Act
        count = await atomic_counter.get_listener_count('test-session')
        
        # Assert
        assert count == 10
        mock_dynamodb_client.get_item.assert_called_once_with(
            TableName='Sessions',
            Key={'sessionId': {'S': 'test-session'}},
            ProjectionExpression='listenerCount'
        )
    
    @pytest.mark.asyncio
    async def test_get_listener_count_returns_none_for_missing_session(
        self, atomic_counter, mock_dynamodb_client
    ):
        """Test get_listener_count returns None for missing session."""
        # Arrange
        mock_dynamodb_client.get_item.return_value = {}
        
        # Act
        count = await atomic_counter.get_listener_count('test-session')
        
        # Assert
        assert count is None
    
    @pytest.mark.asyncio
    async def test_get_listener_count_handles_client_error(
        self, atomic_counter, mock_dynamodb_client
    ):
        """Test error handling for get operation."""
        # Arrange
        mock_dynamodb_client.get_item.side_effect = ClientError(
            {'Error': {'Code': 'InternalServerError'}},
            'GetItem'
        )
        
        # Act
        count = await atomic_counter.get_listener_count('test-session')
        
        # Assert
        assert count is None
    
    @pytest.mark.asyncio
    async def test_concurrent_increments_use_atomic_operation(
        self, atomic_counter, mock_dynamodb_client
    ):
        """Test that increments use atomic ADD operation."""
        # Arrange
        mock_dynamodb_client.update_item.return_value = {
            'Attributes': {'listenerCount': {'N': '1'}}
        }
        
        # Act
        await atomic_counter.increment_listener_count('test-session')
        
        # Assert
        call_args = mock_dynamodb_client.update_item.call_args[1]
        assert call_args['UpdateExpression'] == 'ADD listenerCount :inc'
        # ADD operation is atomic in DynamoDB
    
    @pytest.mark.asyncio
    async def test_concurrent_decrements_use_atomic_operation(
        self, atomic_counter, mock_dynamodb_client
    ):
        """Test that decrements use atomic ADD operation with condition."""
        # Arrange
        mock_dynamodb_client.update_item.return_value = {
            'Attributes': {'listenerCount': {'N': '0'}}
        }
        
        # Act
        await atomic_counter.decrement_listener_count('test-session')
        
        # Assert
        call_args = mock_dynamodb_client.update_item.call_args[1]
        assert call_args['UpdateExpression'] == 'ADD listenerCount :dec'
        assert 'ConditionExpression' in call_args
        # ADD with condition is atomic in DynamoDB
    
    @pytest.mark.asyncio
    async def test_increment_from_zero_succeeds(
        self, atomic_counter, mock_dynamodb_client
    ):
        """Test incrementing from zero count."""
        # Arrange
        mock_dynamodb_client.update_item.return_value = {
            'Attributes': {'listenerCount': {'N': '1'}}
        }
        
        # Act
        new_count = await atomic_counter.increment_listener_count('test-session')
        
        # Assert
        assert new_count == 1
    
    @pytest.mark.asyncio
    async def test_decrement_to_zero_succeeds(
        self, atomic_counter, mock_dynamodb_client
    ):
        """Test decrementing to zero count."""
        # Arrange
        mock_dynamodb_client.update_item.return_value = {
            'Attributes': {'listenerCount': {'N': '0'}}
        }
        
        # Act
        new_count = await atomic_counter.decrement_listener_count('test-session')
        
        # Assert
        assert new_count == 0
    
    @pytest.mark.asyncio
    async def test_multiple_increments_accumulate(
        self, atomic_counter, mock_dynamodb_client
    ):
        """Test multiple increments accumulate correctly."""
        # Arrange
        mock_dynamodb_client.update_item.side_effect = [
            {'Attributes': {'listenerCount': {'N': '1'}}},
            {'Attributes': {'listenerCount': {'N': '2'}}},
            {'Attributes': {'listenerCount': {'N': '3'}}}
        ]
        
        # Act
        count1 = await atomic_counter.increment_listener_count('test-session')
        count2 = await atomic_counter.increment_listener_count('test-session')
        count3 = await atomic_counter.increment_listener_count('test-session')
        
        # Assert
        assert count1 == 1
        assert count2 == 2
        assert count3 == 3
        assert mock_dynamodb_client.update_item.call_count == 3
