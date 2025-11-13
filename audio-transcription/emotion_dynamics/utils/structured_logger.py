"""
Structured logging utilities for emotion dynamics detection.

This module provides JSON-formatted logging with correlation ID tracking
for CloudWatch Logs integration and analysis.
"""

import json
import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    
    Formats log records as JSON with consistent fields including:
    - timestamp: ISO 8601 timestamp
    - level: Log level (DEBUG, INFO, WARNING, ERROR)
    - correlation_id: Correlation ID from extra fields
    - component: Logger name
    - message: Log message
    - Additional fields from extra dict
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON-formatted log string
        """
        # Build base log entry
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'component': record.name,
            'message': record.getMessage()
        }
        
        # Add correlation ID if present
        if hasattr(record, 'correlation_id'):
            log_entry['correlation_id'] = record.correlation_id
        
        # Add extra fields from record
        # Skip standard logging attributes
        skip_fields = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'message', 'pathname', 'process', 'processName', 'relativeCreated',
            'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info'
        }
        
        for key, value in record.__dict__.items():
            if key not in skip_fields and not key.startswith('_'):
                # Handle non-serializable types
                try:
                    json.dumps(value)
                    log_entry[key] = value
                except (TypeError, ValueError):
                    log_entry[key] = str(value)
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Convert to JSON
        try:
            return json.dumps(log_entry)
        except Exception as e:
            # Fallback to simple format if JSON serialization fails
            return f"{{\"error\": \"Failed to serialize log: {e}\", \"message\": \"{record.getMessage()}\"}}"


class StructuredLogger:
    """
    Structured logger with correlation ID support.
    
    Provides convenience methods for logging with automatic correlation ID
    injection and structured field formatting.
    """
    
    def __init__(
        self,
        name: str,
        level: int = logging.INFO,
        use_json: bool = True
    ):
        """
        Initialize structured logger.
        
        Args:
            name: Logger name (typically module name)
            level: Logging level (default: INFO)
            use_json: Whether to use JSON formatting (default: True)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Configure handler if not already configured
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            
            if use_json:
                formatter = StructuredFormatter()
            else:
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
            
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def debug(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Log debug message with structured fields.
        
        Args:
            message: Log message
            correlation_id: Optional correlation ID
            **kwargs: Additional structured fields
        """
        extra = self._build_extra(correlation_id, kwargs)
        self.logger.debug(message, extra=extra)
    
    def info(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Log info message with structured fields.
        
        Args:
            message: Log message
            correlation_id: Optional correlation ID
            **kwargs: Additional structured fields
        """
        extra = self._build_extra(correlation_id, kwargs)
        self.logger.info(message, extra=extra)
    
    def warning(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Log warning message with structured fields.
        
        Args:
            message: Log message
            correlation_id: Optional correlation ID
            **kwargs: Additional structured fields
        """
        extra = self._build_extra(correlation_id, kwargs)
        self.logger.warning(message, extra=extra)
    
    def error(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        exc_info: bool = False,
        **kwargs
    ) -> None:
        """
        Log error message with structured fields.
        
        Args:
            message: Log message
            correlation_id: Optional correlation ID
            exc_info: Whether to include exception info
            **kwargs: Additional structured fields
        """
        extra = self._build_extra(correlation_id, kwargs)
        self.logger.error(message, extra=extra, exc_info=exc_info)
    
    def _build_extra(
        self,
        correlation_id: Optional[str],
        fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build extra fields dict for logging.
        
        Args:
            correlation_id: Optional correlation ID
            fields: Additional fields
            
        Returns:
            Extra fields dict
        """
        extra = fields.copy()
        
        if correlation_id:
            extra['correlation_id'] = correlation_id
        
        return extra


def configure_structured_logging(
    level: int = logging.INFO,
    use_json: bool = True
) -> None:
    """
    Configure structured logging for the entire application.
    
    Sets up JSON formatting and CloudWatch Logs integration for all loggers.
    
    Args:
        level: Logging level (default: INFO)
        use_json: Whether to use JSON formatting (default: True)
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add structured handler
    handler = logging.StreamHandler(sys.stdout)
    
    if use_json:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Log configuration
    root_logger.info(
        f"Configured structured logging: level={logging.getLevelName(level)}, json={use_json}"
    )


def log_volume_detection(
    logger: logging.Logger,
    correlation_id: str,
    volume_level: str,
    db_value: float,
    latency_ms: int
) -> None:
    """
    Log volume detection result with structured fields.
    
    Args:
        logger: Logger instance
        correlation_id: Correlation ID
        volume_level: Detected volume level
        db_value: Decibel value
        latency_ms: Detection latency in milliseconds
    """
    logger.info(
        f"Volume detection completed: level={volume_level}, db={db_value:.2f}",
        extra={
            'correlation_id': correlation_id,
            'operation': 'volume_detection',
            'volume_level': volume_level,
            'db_value': db_value,
            'latency_ms': latency_ms
        }
    )


def log_rate_detection(
    logger: logging.Logger,
    correlation_id: str,
    rate_classification: str,
    wpm: float,
    onset_count: int,
    latency_ms: int
) -> None:
    """
    Log speaking rate detection result with structured fields.
    
    Args:
        logger: Logger instance
        correlation_id: Correlation ID
        rate_classification: Rate classification
        wpm: Words per minute
        onset_count: Number of detected onsets
        latency_ms: Detection latency in milliseconds
    """
    logger.info(
        f"Rate detection completed: classification={rate_classification}, wpm={wpm:.1f}",
        extra={
            'correlation_id': correlation_id,
            'operation': 'rate_detection',
            'rate_classification': rate_classification,
            'wpm': wpm,
            'onset_count': onset_count,
            'latency_ms': latency_ms
        }
    )


def log_ssml_generation(
    logger: logging.Logger,
    correlation_id: str,
    ssml_length: int,
    has_dynamics: bool,
    latency_ms: int
) -> None:
    """
    Log SSML generation result with structured fields.
    
    Args:
        logger: Logger instance
        correlation_id: Correlation ID
        ssml_length: Length of generated SSML
        has_dynamics: Whether dynamics were applied
        latency_ms: Generation latency in milliseconds
    """
    logger.info(
        f"SSML generation completed: length={ssml_length}, dynamics={has_dynamics}",
        extra={
            'correlation_id': correlation_id,
            'operation': 'ssml_generation',
            'ssml_length': ssml_length,
            'has_dynamics': has_dynamics,
            'latency_ms': latency_ms
        }
    )


def log_polly_synthesis(
    logger: logging.Logger,
    correlation_id: str,
    audio_size_bytes: int,
    voice_id: str,
    text_type: str,
    latency_ms: int
) -> None:
    """
    Log Polly synthesis result with structured fields.
    
    Args:
        logger: Logger instance
        correlation_id: Correlation ID
        audio_size_bytes: Size of synthesized audio in bytes
        voice_id: Polly voice ID used
        text_type: Text type (ssml or text)
        latency_ms: Synthesis latency in milliseconds
    """
    logger.info(
        f"Polly synthesis completed: size={audio_size_bytes} bytes, voice={voice_id}",
        extra={
            'correlation_id': correlation_id,
            'operation': 'polly_synthesis',
            'audio_size_bytes': audio_size_bytes,
            'voice_id': voice_id,
            'text_type': text_type,
            'latency_ms': latency_ms
        }
    )


def log_error(
    logger: logging.Logger,
    correlation_id: str,
    component: str,
    error_type: str,
    error_message: str,
    exc_info: bool = True
) -> None:
    """
    Log error with structured fields and context.
    
    Args:
        logger: Logger instance
        correlation_id: Correlation ID
        component: Component where error occurred
        error_type: Type of error
        error_message: Error message
        exc_info: Whether to include exception info
    """
    logger.error(
        f"{component} error: {error_message}",
        extra={
            'correlation_id': correlation_id,
            'component': component,
            'error_type': error_type,
            'error_message': error_message
        },
        exc_info=exc_info
    )
