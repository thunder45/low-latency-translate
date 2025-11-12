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


class RateLimitExceededError(Exception):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, message: str, retry_after: int):
        """
        Initialize rate limit exceeded error.
        
        Args:
            message: Error message
            retry_after: Seconds until rate limit resets
        """
        super().__init__(message)
        self.retry_after = retry_after
