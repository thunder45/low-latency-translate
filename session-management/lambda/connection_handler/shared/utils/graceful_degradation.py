"""
Graceful degradation utilities for handling service unavailability.
"""

import logging
from typing import Optional, Callable, TypeVar, Any
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


class DegradedModeError(Exception):
    """Exception raised when system is operating in degraded mode."""
    pass


class ServiceUnavailableError(Exception):
    """Exception raised when a critical service is unavailable."""
    pass


def with_fallback(
    fallback_value: Any = None,
    fallback_function: Optional[Callable] = None,
    log_degradation: bool = True
):
    """
    Decorator for graceful degradation with fallback behavior.
    
    When the decorated function raises an exception, either returns
    a fallback value or calls a fallback function.
    
    Args:
        fallback_value: Value to return on failure (default: None)
        fallback_function: Function to call on failure (takes exception as arg)
        log_degradation: Whether to log degradation events (default: True)
        
    Returns:
        Decorated function with fallback behavior
        
    Example:
        @with_fallback(fallback_value=False)
        def check_rate_limit(user_id):
            # May fail if RateLimits table unavailable
            return rate_limiter.check(user_id)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_degradation:
                    logger.warning(
                        f"Graceful degradation: {func.__name__} failed, using fallback",
                        extra={
                            'function': func.__name__,
                            'error': str(e),
                            'error_type': type(e).__name__,
                            'has_fallback_function': fallback_function is not None,
                            'fallback_value': fallback_value
                        }
                    )
                
                if fallback_function:
                    return fallback_function(e)
                else:
                    return fallback_value
        
        return wrapper
    return decorator


def handle_dynamodb_unavailable(operation_name: str) -> dict:
    """
    Handle DynamoDB unavailability with 503 response.
    
    Args:
        operation_name: Name of the operation that failed
        
    Returns:
        Error response dict with 503 status
    """
    logger.error(
        f"DynamoDB unavailable for operation: {operation_name}",
        extra={
            'operation': operation_name,
            'degraded_mode': True,
            'service': 'DynamoDB'
        }
    )
    
    return {
        'statusCode': 503,
        'body': {
            'type': 'error',
            'code': 'SERVICE_UNAVAILABLE',
            'message': 'Database service temporarily unavailable. Please try again later.',
            'service': 'DynamoDB',
            'retryable': True
        }
    }


def handle_cognito_unavailable(
    allow_anonymous: bool = False,
    operation_name: str = 'authentication'
) -> dict:
    """
    Handle Cognito unavailability.
    
    For speaker connections: Reject with 503
    For listener connections: Allow if allow_anonymous=True
    
    Args:
        allow_anonymous: Whether to allow anonymous access (default: False)
        operation_name: Name of the operation that failed
        
    Returns:
        Error response dict or None if anonymous allowed
    """
    logger.error(
        f"Cognito unavailable for operation: {operation_name}",
        extra={
            'operation': operation_name,
            'degraded_mode': True,
            'service': 'Cognito',
            'allow_anonymous': allow_anonymous
        }
    )
    
    if allow_anonymous:
        logger.warning(
            "Allowing anonymous access due to Cognito unavailability",
            extra={
                'operation': operation_name,
                'degraded_mode': True
            }
        )
        return None
    
    return {
        'statusCode': 503,
        'body': {
            'type': 'error',
            'code': 'SERVICE_UNAVAILABLE',
            'message': 'Authentication service temporarily unavailable. Please try again later.',
            'service': 'Cognito',
            'retryable': True
        }
    }


def disable_rate_limiting_temporarily(reason: str) -> None:
    """
    Log that rate limiting is temporarily disabled.
    
    Args:
        reason: Reason for disabling rate limiting
    """
    logger.warning(
        "Rate limiting temporarily disabled",
        extra={
            'degraded_mode': True,
            'reason': reason,
            'service': 'RateLimiting'
        }
    )


class GracefulDegradationManager:
    """
    Manager for tracking and coordinating graceful degradation.
    
    Tracks which services are in degraded mode and provides
    centralized logging and monitoring.
    """
    
    def __init__(self):
        """Initialize graceful degradation manager."""
        self.degraded_services = set()
        self.degradation_reasons = {}
    
    def mark_degraded(self, service: str, reason: str) -> None:
        """
        Mark a service as degraded.
        
        Args:
            service: Name of the service
            reason: Reason for degradation
        """
        if service not in self.degraded_services:
            self.degraded_services.add(service)
            self.degradation_reasons[service] = reason
            
            logger.error(
                f"Service '{service}' entered degraded mode",
                extra={
                    'service': service,
                    'reason': reason,
                    'degraded_mode': True,
                    'degraded_services': list(self.degraded_services)
                }
            )
    
    def mark_recovered(self, service: str) -> None:
        """
        Mark a service as recovered.
        
        Args:
            service: Name of the service
        """
        if service in self.degraded_services:
            self.degraded_services.remove(service)
            reason = self.degradation_reasons.pop(service, 'unknown')
            
            logger.info(
                f"Service '{service}' recovered from degraded mode",
                extra={
                    'service': service,
                    'previous_reason': reason,
                    'degraded_mode': False,
                    'degraded_services': list(self.degraded_services)
                }
            )
    
    def is_degraded(self, service: str) -> bool:
        """
        Check if a service is in degraded mode.
        
        Args:
            service: Name of the service
            
        Returns:
            True if service is degraded, False otherwise
        """
        return service in self.degraded_services
    
    def get_degraded_services(self) -> list:
        """
        Get list of degraded services.
        
        Returns:
            List of service names in degraded mode
        """
        return list(self.degraded_services)
    
    def get_degradation_reason(self, service: str) -> Optional[str]:
        """
        Get degradation reason for a service.
        
        Args:
            service: Name of the service
            
        Returns:
            Degradation reason or None if not degraded
        """
        return self.degradation_reasons.get(service)
    
    def is_any_degraded(self) -> bool:
        """
        Check if any service is in degraded mode.
        
        Returns:
            True if any service is degraded, False otherwise
        """
        return len(self.degraded_services) > 0


# Global instance for application-wide degradation tracking
degradation_manager = GracefulDegradationManager()


def check_service_health(service: str) -> dict:
    """
    Check health status of a service.
    
    Args:
        service: Name of the service to check
        
    Returns:
        Health status dict with service name, status, and reason
    """
    is_degraded = degradation_manager.is_degraded(service)
    
    return {
        'service': service,
        'status': 'degraded' if is_degraded else 'healthy',
        'reason': degradation_manager.get_degradation_reason(service) if is_degraded else None
    }


def get_system_health() -> dict:
    """
    Get overall system health status.
    
    Returns:
        System health dict with overall status and service details
    """
    degraded_services = degradation_manager.get_degraded_services()
    
    return {
        'status': 'degraded' if degraded_services else 'healthy',
        'degraded_services': degraded_services,
        'degradation_details': {
            service: degradation_manager.get_degradation_reason(service)
            for service in degraded_services
        }
    }
