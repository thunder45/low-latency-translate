"""
Data access layer for DynamoDB operations.
"""
from .dynamodb_client import DynamoDBClient
from .sessions_repository import SessionsRepository
from .connections_repository import ConnectionsRepository
from .rate_limits_repository import RateLimitsRepository, RateLimitOperation
from .exceptions import (
    DynamoDBError,
    ItemNotFoundError,
    ConditionalCheckFailedError,
    RetryableError,
    RateLimitExceededError,
)

__all__ = [
    'DynamoDBClient',
    'SessionsRepository',
    'ConnectionsRepository',
    'RateLimitsRepository',
    'RateLimitOperation',
    'DynamoDBError',
    'ItemNotFoundError',
    'ConditionalCheckFailedError',
    'RetryableError',
    'RateLimitExceededError',
]
