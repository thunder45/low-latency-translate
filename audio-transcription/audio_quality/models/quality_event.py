"""
Quality event data model.

This module defines the QualityEvent dataclass for representing
quality degradation events that can be published to EventBridge.
"""

import json
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class QualityEvent:
    """Quality degradation event."""
    
    event_type: str  # 'snr_low', 'clipping', 'echo', 'silence'
    stream_id: str
    timestamp: float
    severity: str    # 'warning', 'error'
    metrics: Dict[str, Any]
    message: str
    
    # Valid event types
    VALID_EVENT_TYPES = ['snr_low', 'clipping', 'echo', 'silence']
    
    # Valid severity levels
    VALID_SEVERITIES = ['warning', 'error']
    
    def __post_init__(self):
        """Validates event values."""
        if self.event_type not in self.VALID_EVENT_TYPES:
            raise ValueError(
                f'Invalid event type: {self.event_type}. '
                f'Must be one of {self.VALID_EVENT_TYPES}'
            )
        
        if self.severity not in self.VALID_SEVERITIES:
            raise ValueError(
                f'Invalid severity: {self.severity}. '
                f'Must be one of {self.VALID_SEVERITIES}'
            )
        
        if not self.stream_id:
            raise ValueError('Stream ID must not be empty')
        
        if self.timestamp < 0:
            raise ValueError('Timestamp must be non-negative')
        
        if not self.message:
            raise ValueError('Message must not be empty')
    
    def to_eventbridge_entry(self) -> Dict[str, Any]:
        """
        Converts to EventBridge event entry.
        
        Returns:
            Dictionary formatted for EventBridge PutEvents API.
        """
        return {
            'Source': 'audio.quality.validator',
            'DetailType': f'audio.quality.{self.event_type}',
            'Detail': json.dumps({
                'streamId': self.stream_id,
                'timestamp': self.timestamp,
                'severity': self.severity,
                'metrics': self.metrics,
                'message': self.message
            })
        }
