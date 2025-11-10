"""
Custom exceptions for data access layer.
"""


class DynamoDBError(Exception):
    """Base exception for DynamoDB operations."""
    pass


class ItemNotFoundError(DynamoDBError):
    """Exception raised when an item is not found in DynamoDB."""
    pass


class ConditionalCheckFailedError(DynamoDBError):
    """Exception raised when a conditional check fails."""
    pass


class RetryableError(DynamoDBError):
    """Exception raised for transient errors that can be retried."""
    pass
