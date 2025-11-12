"""
Circuit breaker pattern for resilient operations.
"""

import time
import logging
from enum import Enum
from typing import Callable, TypeVar, Any
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"      # Normal operation, requests pass through
    OPEN = "OPEN"          # Circuit is open, requests fail fast
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.
    
    Implements the circuit breaker pattern with three states:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests fail fast
    - HALF_OPEN: Testing if service recovered
    
    State transitions:
    - CLOSED -> OPEN: When failure count reaches threshold
    - OPEN -> HALF_OPEN: After timeout period
    - HALF_OPEN -> CLOSED: When test request succeeds
    - HALF_OPEN -> OPEN: When test request fails
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout: float = 30.0,
        expected_exception: type = Exception
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Name of the circuit breaker for logging
            failure_threshold: Number of failures before opening circuit (default: 5)
            timeout: Seconds to wait before attempting recovery (default: 30.0)
            expected_exception: Exception type to count as failure (default: Exception)
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: float = 0
        self.state = CircuitState.CLOSED
        
        logger.info(
            f"Circuit breaker '{name}' initialized",
            extra={
                'circuit_breaker': name,
                'failure_threshold': failure_threshold,
                'timeout': timeout,
                'state': self.state.value
            }
        )
    
    def call(self, operation: Callable[[], T]) -> T:
        """
        Execute operation with circuit breaker protection.
        
        Args:
            operation: Callable to execute
            
        Returns:
            Result of the operation
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: If operation fails
        """
        # Check if we should transition from OPEN to HALF_OPEN
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.timeout:
                self._transition_to_half_open()
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is open. "
                    f"Retry after {self.timeout - (time.time() - self.last_failure_time):.1f}s"
                )
        
        try:
            result = operation()
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure(e)
            raise
    
    def _on_success(self) -> None:
        """Handle successful operation."""
        if self.state == CircuitState.HALF_OPEN:
            self._transition_to_closed()
        
        # Reset failure count on success
        if self.failure_count > 0:
            logger.info(
                f"Circuit breaker '{self.name}' - operation succeeded, resetting failure count",
                extra={
                    'circuit_breaker': self.name,
                    'previous_failure_count': self.failure_count,
                    'state': self.state.value
                }
            )
            self.failure_count = 0
    
    def _on_failure(self, exception: Exception) -> None:
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        logger.warning(
            f"Circuit breaker '{self.name}' - operation failed",
            extra={
                'circuit_breaker': self.name,
                'failure_count': self.failure_count,
                'failure_threshold': self.failure_threshold,
                'state': self.state.value,
                'error': str(exception)
            }
        )
        
        # Transition to OPEN if threshold reached
        if self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            self._transition_to_open()
        elif self.state == CircuitState.HALF_OPEN:
            # Failed during test, go back to OPEN
            self._transition_to_open()
    
    def _transition_to_open(self) -> None:
        """Transition circuit breaker to OPEN state."""
        self.state = CircuitState.OPEN
        logger.error(
            f"Circuit breaker '{self.name}' opened",
            extra={
                'circuit_breaker': self.name,
                'failure_count': self.failure_count,
                'failure_threshold': self.failure_threshold,
                'timeout': self.timeout,
                'state': self.state.value
            }
        )
    
    def _transition_to_half_open(self) -> None:
        """Transition circuit breaker to HALF_OPEN state."""
        self.state = CircuitState.HALF_OPEN
        logger.info(
            f"Circuit breaker '{self.name}' half-opened for testing",
            extra={
                'circuit_breaker': self.name,
                'state': self.state.value
            }
        )
    
    def _transition_to_closed(self) -> None:
        """Transition circuit breaker to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        logger.info(
            f"Circuit breaker '{self.name}' closed - service recovered",
            extra={
                'circuit_breaker': self.name,
                'state': self.state.value
            }
        )
    
    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        logger.info(
            f"Circuit breaker '{self.name}' manually reset",
            extra={
                'circuit_breaker': self.name,
                'previous_state': self.state.value,
                'previous_failure_count': self.failure_count
            }
        )
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
    
    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        return self.state == CircuitState.OPEN
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit breaker is closed."""
        return self.state == CircuitState.CLOSED
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit breaker is half-open."""
        return self.state == CircuitState.HALF_OPEN


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    timeout: float = 30.0,
    expected_exception: type = Exception
):
    """
    Decorator for applying circuit breaker pattern to functions.
    
    Args:
        name: Name of the circuit breaker for logging
        failure_threshold: Number of failures before opening circuit (default: 5)
        timeout: Seconds to wait before attempting recovery (default: 30.0)
        expected_exception: Exception type to count as failure (default: Exception)
        
    Returns:
        Decorated function with circuit breaker protection
        
    Example:
        @circuit_breaker(name='dynamodb', failure_threshold=5, timeout=30)
        def query_database():
            # Database operation
            pass
    """
    # Create a shared circuit breaker instance for this decorator
    breaker = CircuitBreaker(
        name=name,
        failure_threshold=failure_threshold,
        timeout=timeout,
        expected_exception=expected_exception
    )
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return breaker.call(lambda: func(*args, **kwargs))
        
        # Attach circuit breaker instance to wrapper for testing/monitoring
        wrapper.circuit_breaker = breaker
        
        return wrapper
    return decorator
