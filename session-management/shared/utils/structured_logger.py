"""
Structured JSON logging for Lambda functions.

This module provides a structured logger that outputs JSON-formatted
logs with correlation IDs, context, and standardized fields for
CloudWatch Logs Insights queries.
"""

import json
import logging
import time
from typing import Any, Dict, Optional
from datetime import datetime
from decimal import Decimal


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class StructuredLogger:
    """
    Structured JSON logger for Lambda functions.
    
    Outputs logs in JSON format with:
    - Timestamp (ISO 8601)
    - Log level
    - Correlation IDs (sessionId, connectionId, requestId)
    - Component and operation
    - Message and additional context
    """
    
    def __init__(
        self,
        component: str,
        session_id: Optional[str] = None,
        connection_id: Optional[str] = None,
        request_id: Optional[str] = None
    ):
        """
        Initialize structured logger.
        
        Args:
            component: Component name (e.g., 'ConnectionHandler', 'AudioProcessor')
            session_id: Session identifier for correlation
            connection_id: Connection identifier for correlation
            request_id: Request identifier from Lambda context
        """
        self.component = component
        self.session_id = session_id
        self.connection_id = connection_id
        self.request_id = request_id
        self.logger = logging.getLogger(component)
        
        # Set log level from environment or default to INFO
        import os
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.logger.setLevel(getattr(logging, log_level))
    
    def _format_log(
        self,
        level: str,
        message: str,
        operation: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Format log entry as JSON.
        
        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR)
            message: Log message
            operation: Operation being performed
            **kwargs: Additional context fields
            
        Returns:
            JSON-formatted log string
        """
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': level,
            'component': self.component,
            'message': message
        }
        
        # Add correlation IDs if available
        if self.session_id:
            log_entry['sessionId'] = self.session_id
        if self.connection_id:
            log_entry['connectionId'] = self.connection_id
        if self.request_id:
            log_entry['requestId'] = self.request_id
        
        # Add operation if provided
        if operation:
            log_entry['operation'] = operation
        
        # Add additional context
        if kwargs:
            log_entry['context'] = kwargs
        
        return json.dumps(log_entry, cls=DecimalEncoder)
    
    def debug(
        self,
        message: str,
        operation: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Log debug message.
        
        Args:
            message: Log message
            operation: Operation being performed
            **kwargs: Additional context
        """
        self.logger.debug(
            self._format_log('DEBUG', message, operation, **kwargs)
        )
    
    def info(
        self,
        message: str,
        operation: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Log info message.
        
        Args:
            message: Log message
            operation: Operation being performed
            **kwargs: Additional context
        """
        self.logger.info(
            self._format_log('INFO', message, operation, **kwargs)
        )
    
    def warning(
        self,
        message: str,
        operation: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Log warning message.
        
        Args:
            message: Log message
            operation: Operation being performed
            **kwargs: Additional context
        """
        self.logger.warning(
            self._format_log('WARNING', message, operation, **kwargs)
        )
    
    def error(
        self,
        message: str,
        operation: Optional[str] = None,
        error: Optional[Exception] = None,
        **kwargs
    ) -> None:
        """
        Log error message.
        
        Args:
            message: Log message
            operation: Operation being performed
            error: Exception object if available
            **kwargs: Additional context
        """
        if error:
            kwargs['error_type'] = type(error).__name__
            kwargs['error_message'] = str(error)
        
        self.logger.error(
            self._format_log('ERROR', message, operation, **kwargs)
        )
    
    def log_websocket_message(
        self,
        direction: str,
        message_type: str,
        message_size: int
    ) -> None:
        """
        Log WebSocket message at DEBUG level.
        
        Args:
            direction: 'inbound' or 'outbound'
            message_type: Type of message (sendAudio, pauseBroadcast, etc.)
            message_size: Size of message in bytes
        """
        self.debug(
            f'WebSocket message {direction}',
            operation='websocket_message',
            direction=direction,
            message_type=message_type,
            message_size=message_size
        )
    
    def log_transcribe_event(
        self,
        event_type: str,
        **kwargs
    ) -> None:
        """
        Log Transcribe event at DEBUG level.
        
        Args:
            event_type: Type of event (partial, final, error)
            **kwargs: Event details
        """
        self.debug(
            f'Transcribe event: {event_type}',
            operation='transcribe_event',
            event_type=event_type,
            **kwargs
        )
    
    def log_state_change(
        self,
        state_type: str,
        old_value: Any,
        new_value: Any
    ) -> None:
        """
        Log state change at INFO level.
        
        Args:
            state_type: Type of state (broadcastState, connectionState, etc.)
            old_value: Previous value
            new_value: New value
        """
        self.info(
            f'State change: {state_type}',
            operation='state_change',
            state_type=state_type,
            old_value=str(old_value),
            new_value=str(new_value)
        )
    
    def log_performance(
        self,
        operation: str,
        duration_ms: float,
        **kwargs
    ) -> None:
        """
        Log performance metric at DEBUG level.
        
        Args:
            operation: Operation name
            duration_ms: Duration in milliseconds
            **kwargs: Additional context
        """
        self.debug(
            f'Performance: {operation}',
            operation='performance',
            operation_name=operation,
            duration_ms=duration_ms,
            **kwargs
        )


class LoggingContext:
    """
    Context manager for logging operation duration.
    
    Automatically logs operation start, end, and duration.
    """
    
    def __init__(
        self,
        logger: StructuredLogger,
        operation: str,
        **kwargs
    ):
        """
        Initialize logging context.
        
        Args:
            logger: StructuredLogger instance
            operation: Operation name
            **kwargs: Additional context
        """
        self.logger = logger
        self.operation = operation
        self.context = kwargs
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        """Log operation start."""
        self.start_time = time.time()
        self.logger.debug(
            f'Starting operation: {self.operation}',
            operation=self.operation,
            **self.context
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Log operation end and duration."""
        if self.start_time is not None:
            duration_ms = (time.time() - self.start_time) * 1000
            
            if exc_type is not None:
                self.logger.error(
                    f'Operation failed: {self.operation}',
                    operation=self.operation,
                    error=exc_val,
                    duration_ms=duration_ms,
                    **self.context
                )
            else:
                self.logger.debug(
                    f'Completed operation: {self.operation}',
                    operation=self.operation,
                    duration_ms=duration_ms,
                    **self.context
                )


def get_structured_logger(
    component: str,
    correlation_id: Optional[str] = None,
    session_id: Optional[str] = None,
    connection_id: Optional[str] = None,
    request_id: Optional[str] = None,
    **kwargs
) -> StructuredLogger:
    """
    Factory function for creating StructuredLogger instances.
    
    This function provides a convenient way to create logger instances
    with consistent configuration across all Lambda handlers.
    
    Args:
        component: Name of the component (e.g., 'ConnectionHandler', 'AudioProcessor')
        correlation_id: Optional correlation ID for request tracing (alias for request_id)
        session_id: Optional session ID for context
        connection_id: Optional connection ID for context
        request_id: Optional request ID from Lambda context
        **kwargs: Additional keyword arguments (reserved for future use)
        
    Returns:
        Configured StructuredLogger instance
        
    Example:
        >>> logger = get_structured_logger('AudioProcessor')
        >>> logger.info('Processing audio chunk')
        
        >>> logger = get_structured_logger(
        ...     'ConnectionHandler',
        ...     session_id='golden-eagle-427',
        ...     connection_id='abc123'
        ... )
        >>> logger.info('Connection established')
    """
    # Use correlation_id as request_id if provided (for backward compatibility)
    if correlation_id and not request_id:
        request_id = correlation_id
    
    return StructuredLogger(
        component=component,
        session_id=session_id,
        connection_id=connection_id,
        request_id=request_id
    )


def configure_lambda_logging():
    """
    Configure logging for Lambda environment.
    
    Sets up root logger to output to stdout with appropriate format.
    Should be called at module level in Lambda handlers.
    """
    import os
    
    # Get log level from environment
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(message)s',  # Just the message, we format as JSON
        force=True
    )
    
    # Disable boto3 debug logging unless explicitly enabled
    if log_level != 'DEBUG':
        logging.getLogger('boto3').setLevel(logging.WARNING)
        logging.getLogger('botocore').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
