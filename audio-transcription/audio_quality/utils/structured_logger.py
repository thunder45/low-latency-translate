"""
Structured logging utilities for audio quality validation.

Provides JSON-formatted logging for CloudWatch integration and monitoring.
"""

import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime

from audio_quality.models.quality_metrics import QualityMetrics


logger = logging.getLogger(__name__)


def log_quality_metrics(
    stream_id: str,
    metrics: QualityMetrics,
    level: str = 'INFO'
) -> None:
    """
    Logs quality metrics in structured JSON format.
    
    Args:
        stream_id: Audio stream identifier
        metrics: Quality metrics to log
        level: Log level (DEBUG, INFO, WARNING, ERROR)
    """
    log_entry = {
        'event': 'quality_metrics',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'streamId': stream_id,
        'metrics': {
            'snr_db': round(float(metrics.snr_db), 2),
            'snr_rolling_avg': round(float(metrics.snr_rolling_avg), 2),
            'clipping_percentage': round(float(metrics.clipping_percentage), 2),
            'clipped_sample_count': int(metrics.clipped_sample_count),
            'is_clipping': bool(metrics.is_clipping),
            'echo_level_db': round(float(metrics.echo_level_db), 2),
            'echo_delay_ms': round(float(metrics.echo_delay_ms), 2),
            'has_echo': bool(metrics.has_echo),
            'is_silent': bool(metrics.is_silent),
            'silence_duration_s': round(float(metrics.silence_duration_s), 2),
            'energy_db': round(float(metrics.energy_db), 2)
        }
    }
    
    log_message = json.dumps(log_entry)
    
    if level == 'DEBUG':
        logger.debug(log_message)
    elif level == 'INFO':
        logger.info(log_message)
    elif level == 'WARNING':
        logger.warning(log_message)
    elif level == 'ERROR':
        logger.error(log_message)


def _convert_to_json_serializable(obj: Any) -> Any:
    """
    Converts numpy types to Python native types for JSON serialization.
    
    Args:
        obj: Object to convert
        
    Returns:
        JSON-serializable version of the object
    """
    import numpy as np
    
    if isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif isinstance(obj, dict):
        return {k: _convert_to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_to_json_serializable(item) for item in obj]
    else:
        return obj


def log_quality_issue(
    stream_id: str,
    issue_type: str,
    details: Dict[str, Any],
    severity: str = 'warning'
) -> None:
    """
    Logs quality issue detection in structured format.
    
    Args:
        stream_id: Audio stream identifier
        issue_type: Type of quality issue (snr_low, clipping, echo, silence)
        details: Issue-specific details
        severity: Issue severity (warning, error)
    """
    # Convert numpy types to Python types for JSON serialization
    serializable_details = _convert_to_json_serializable(details)
    
    log_entry = {
        'event': 'quality_issue',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'streamId': stream_id,
        'issueType': issue_type,
        'severity': severity,
        'details': serializable_details
    }
    
    log_message = json.dumps(log_entry)
    
    if severity == 'error':
        logger.error(log_message)
    else:
        logger.warning(log_message)


def log_analysis_operation(
    stream_id: str,
    operation: str,
    duration_ms: float,
    success: bool = True,
    error: Optional[str] = None
) -> None:
    """
    Logs audio quality analysis operation.
    
    Args:
        stream_id: Audio stream identifier
        operation: Operation name (analyze, calculate_snr, detect_clipping, etc.)
        duration_ms: Operation duration in milliseconds
        success: Whether operation succeeded
        error: Error message if operation failed
    """
    log_entry = {
        'event': 'analysis_operation',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'streamId': stream_id,
        'operation': operation,
        'duration_ms': round(duration_ms, 2),
        'success': success
    }
    
    if error:
        log_entry['error'] = error
    
    log_message = json.dumps(log_entry)
    
    if success:
        logger.debug(log_message)
    else:
        logger.error(log_message)


def log_notification_sent(
    connection_id: str,
    issue_type: str,
    rate_limited: bool = False
) -> None:
    """
    Logs speaker notification event.
    
    Args:
        connection_id: WebSocket connection ID
        issue_type: Type of quality issue
        rate_limited: Whether notification was rate limited
    """
    log_entry = {
        'event': 'notification_sent',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'connectionId': connection_id,
        'issueType': issue_type,
        'rateLimited': rate_limited
    }
    
    logger.info(json.dumps(log_entry))


def log_metrics_emission(
    stream_id: str,
    metric_count: int,
    success: bool = True,
    error: Optional[str] = None
) -> None:
    """
    Logs CloudWatch metrics emission.
    
    Args:
        stream_id: Audio stream identifier
        metric_count: Number of metrics emitted
        success: Whether emission succeeded
        error: Error message if emission failed
    """
    log_entry = {
        'event': 'metrics_emission',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'streamId': stream_id,
        'metricCount': metric_count,
        'success': success
    }
    
    if error:
        log_entry['error'] = error
    
    log_message = json.dumps(log_entry)
    
    if success:
        logger.debug(log_message)
    else:
        logger.error(log_message)


def log_configuration_loaded(config_dict: Dict[str, Any]) -> None:
    """
    Logs configuration loading event.
    
    Args:
        config_dict: Configuration dictionary
    """
    log_entry = {
        'event': 'configuration_loaded',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'config': config_dict
    }
    
    logger.info(json.dumps(log_entry))
