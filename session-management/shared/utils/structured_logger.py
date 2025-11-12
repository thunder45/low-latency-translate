"""
Structured logging utility for JSON-formatted log entries.

Provides consistent logging format across all Lambda functions with:
- JSON-formatted log entries
- Timestamp, level, correlationId
- Sanitized user context
- Stack traces for errors
"""
import json
import logging
import hashlib
import time
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from decimal import Decimal


def decimal_default(obj):
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class StructuredLogger:
    """
    Structured logger that outputs JSON-formatted log entries.
    
    Provides methods for logging with consistent structure including:
    - Timestamp in ISO 8601 format
    - Log level
    - Correlation ID (session ID or connection ID)
    - Operation name
    - Sanitized user context
    - Stack traces for errors
    """
    
    def __init__(self, logger: logging.Logger, component: str):
        """
        Initialize structured logger.
        
        Args:
            logger: Python logger instance
            component: Component name (e.g., 'ConnectionHandler', 'HeartbeatHandler')
        """
        self.logger = logger
        self.component = component
    
    def _sanitize_user_context(self, user_id: Optional[str] = None, ip_address: Optional[str] = None) -> Dict[str, str]:
        """
        Sanitize user context for logging.
        
        Args:
            user_id: User ID (will be included as-is if provided)
            ip_address: IP address (will be hashed)
            
        Returns:
            Dictionary with sanitized user context
        """
        context = {}
        
        if user_id:
            context['userId'] = user_id
        
        if ip_address and ip_address != 'unknown':
            # Hash IP address for privacy
            hashed_ip = hashlib.sha256(ip_address.encode()).hexdigest()[:16]
            context['ipAddressHash'] = hashed_ip
        
        return context
    
    def _format_log_entry(
        self,
        level: str,
        message: str,
        correlation_id: Optional[str] = None,
        operation: Optional[str] = None,
        duration_ms: Optional[int] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        error_code: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format log entry as JSON.
        
        Args:
            level: Log level (INFO, WARNING, ERROR, etc.)
            message: Log message
            correlation_id: Correlation ID (session ID or connection ID)
            operation: Operation name
            duration_ms: Operation duration in milliseconds
            user_id: User ID
            ip_address: IP address (will be hashed)
            error_code: Error code for errors
            extra: Additional fields to include
            
        Returns:
            JSON-formatted log entry
        """
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'level': level,
            'component': self.component,
            'message': message
        }
        
        if correlation_id:
            log_entry['correlationId'] = correlation_id
        
        if operation:
            log_entry['operation'] = operation
        
        if duration_ms is not None:
            log_entry['durationMs'] = duration_ms
        
        if error_code:
            log_entry['errorCode'] = error_code
        
        # Add sanitized user context
        user_context = self._sanitize_user_context(user_id, ip_address)
        if user_context:
            log_entry['userContext'] = user_context
        
        # Add extra fields
        if extra:
            log_entry.update(extra)
        
        return json.dumps(log_entry, default=decimal_default)
    
    def info(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        operation: Optional[str] = None,
        duration_ms: Optional[int] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        **extra
    ):
        """
        Log INFO level message.
        
        Args:
            message: Log message
            correlation_id: Correlation ID
            operation: Operation name
            duration_ms: Operation duration
            user_id: User ID
            ip_address: IP address
            **extra: Additional fields
        """
        log_entry = self._format_log_entry(
            level='INFO',
            message=message,
            correlation_id=correlation_id,
            operation=operation,
            duration_ms=duration_ms,
            user_id=user_id,
            ip_address=ip_address,
            extra=extra
        )
        self.logger.info(log_entry)
    
    def warning(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        operation: Optional[str] = None,
        error_code: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        **extra
    ):
        """
        Log WARNING level message.
        
        Args:
            message: Log message
            correlation_id: Correlation ID
            operation: Operation name
            error_code: Error code
            user_id: User ID
            ip_address: IP address
            **extra: Additional fields
        """
        log_entry = self._format_log_entry(
            level='WARNING',
            message=message,
            correlation_id=correlation_id,
            operation=operation,
            error_code=error_code,
            user_id=user_id,
            ip_address=ip_address,
            extra=extra
        )
        self.logger.warning(log_entry)
    
    def error(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        operation: Optional[str] = None,
        error_code: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        exc_info: bool = False,
        **extra
    ):
        """
        Log ERROR level message.
        
        Args:
            message: Log message
            correlation_id: Correlation ID
            operation: Operation name
            error_code: Error code
            user_id: User ID
            ip_address: IP address
            exc_info: Include exception info (stack trace)
            **extra: Additional fields
        """
        log_entry = self._format_log_entry(
            level='ERROR',
            message=message,
            correlation_id=correlation_id,
            operation=operation,
            error_code=error_code,
            user_id=user_id,
            ip_address=ip_address,
            extra=extra
        )
        self.logger.error(log_entry, exc_info=exc_info)
    
    def debug(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        operation: Optional[str] = None,
        **extra
    ):
        """
        Log DEBUG level message.
        
        Args:
            message: Log message
            correlation_id: Correlation ID
            operation: Operation name
            **extra: Additional fields
        """
        log_entry = self._format_log_entry(
            level='DEBUG',
            message=message,
            correlation_id=correlation_id,
            operation=operation,
            extra=extra
        )
        self.logger.debug(log_entry)


def get_structured_logger(component: str) -> StructuredLogger:
    """
    Get a structured logger instance for a component.
    
    Args:
        component: Component name
        
    Returns:
        StructuredLogger instance
    """
    logger = logging.getLogger(component)
    return StructuredLogger(logger, component)
