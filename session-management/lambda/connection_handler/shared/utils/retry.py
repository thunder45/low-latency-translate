"""
Retry logic with exponential backoff for resilient operations.
"""

import time
import random
import logging
from functools import wraps
from typing import Callable, TypeVar, Any

from shared.data_access.exceptions import RetryableError

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: bool = True
):
    """
    Decorator for retrying operations with exponential backoff.
    
    Implements exponential backoff with optional jitter to prevent thundering herd.
    Only retries on RetryableError exceptions.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 30.0)
        jitter: Whether to add random jitter to delay (default: True)
        
    Returns:
        Decorated function that retries on RetryableError
        
    Example:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def risky_operation():
            # Operation that may raise RetryableError
            pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    
                    # Log successful retry if not first attempt
                    if attempt > 0:
                        logger.info(
                            f"Operation succeeded after {attempt} retries",
                            extra={
                                'function': func.__name__,
                                'attempt': attempt,
                                'max_retries': max_retries
                            }
                        )
                    
                    return result
                    
                except RetryableError as e:
                    last_exception = e
                    
                    # If this was the last attempt, raise the exception
                    if attempt == max_retries:
                        logger.error(
                            f"Operation failed after {max_retries} retries",
                            extra={
                                'function': func.__name__,
                                'max_retries': max_retries,
                                'error': str(e)
                            }
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    
                    # Add jitter to prevent thundering herd
                    if jitter:
                        jitter_amount = random.uniform(0, 0.1 * delay)
                        delay += jitter_amount
                    
                    logger.warning(
                        f"Retry attempt {attempt + 1}/{max_retries} after {delay:.2f}s",
                        extra={
                            'function': func.__name__,
                            'attempt': attempt + 1,
                            'max_retries': max_retries,
                            'delay_seconds': delay,
                            'error': str(e)
                        }
                    )
                    
                    time.sleep(delay)
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            
        return wrapper
    return decorator


def retry_operation(
    operation: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: bool = True
) -> T:
    """
    Retry an operation with exponential backoff (functional approach).
    
    This is a functional alternative to the decorator for cases where
    you want to retry a specific operation without decorating a function.
    
    Args:
        operation: Callable to retry
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 30.0)
        jitter: Whether to add random jitter to delay (default: True)
        
    Returns:
        Result of the operation
        
    Raises:
        RetryableError: If all retries fail
        
    Example:
        result = retry_operation(
            lambda: dynamodb.get_item(Key={'id': '123'}),
            max_retries=3
        )
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            result = operation()
            
            # Log successful retry if not first attempt
            if attempt > 0:
                logger.info(
                    f"Operation succeeded after {attempt} retries",
                    extra={
                        'attempt': attempt,
                        'max_retries': max_retries
                    }
                )
            
            return result
            
        except RetryableError as e:
            last_exception = e
            
            # If this was the last attempt, raise the exception
            if attempt == max_retries:
                logger.error(
                    f"Operation failed after {max_retries} retries",
                    extra={
                        'max_retries': max_retries,
                        'error': str(e)
                    }
                )
                raise
            
            # Calculate delay with exponential backoff
            delay = min(base_delay * (2 ** attempt), max_delay)
            
            # Add jitter to prevent thundering herd
            if jitter:
                jitter_amount = random.uniform(0, 0.1 * delay)
                delay += jitter_amount
            
            logger.warning(
                f"Retry attempt {attempt + 1}/{max_retries} after {delay:.2f}s",
                extra={
                    'attempt': attempt + 1,
                    'max_retries': max_retries,
                    'delay_seconds': delay,
                    'error': str(e)
                }
            )
            
            time.sleep(delay)
    
    # This should never be reached, but just in case
    if last_exception:
        raise last_exception
