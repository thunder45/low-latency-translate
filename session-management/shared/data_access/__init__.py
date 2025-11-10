"""
Data access layer for DynamoDB operations.
"""
from .dynamodb_client import DynamoDBClient
from .sessions_repository import SessionsRepository
from .connections_repository import ConnectionsRepository
from .rate_limits_repository import RateLimitsRepository
from .exceptions import (
    DynamoDBError,
    ItemNotFoundError,
    ConditionalCheckFailedError,
    RetryableError,
)

__all__ = [
    'DynamoDBClient',
    'SessionsRepository',
    'ConnectionsRepository',
    'RateLimitsRepository',
    'DynamoDBError',
    'ItemNotFoundError',
    'ConditionalCheckFailedError',
    'RetryableError',
]
