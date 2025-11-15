"""
WebSocket message schemas and validation.

This module provides standardized message schemas for all WebSocket
message types to ensure consistency across the system.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import json


@dataclass
class WebSocketMessage:
    """Base class for all WebSocket messages."""
    
    type: str
    timestamp: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class SessionCreatedMessage(WebSocketMessage):
    """Message sent when session is created."""
    
    sessionId: str
    sourceLanguage: str
    qualityTier: str
    expiresAt: int
    
    def __init__(self, sessionId: str, sourceLanguage: str, qualityTier: str, expiresAt: int, timestamp: int):
        super().__init__(type='sessionCreated', timestamp=timestamp)
        self.sessionId = sessionId
        self.sourceLanguage = sourceLanguage
        self.qualityTier = qualityTier
        self.expiresAt = expiresAt


@dataclass
class ListenerJoinedMessage(WebSocketMessage):
    """Message sent when listener joins session."""
    
    sessionId: str
    listenerCount: int
    targetLanguage: str
    
    def __init__(self, sessionId: str, listenerCount: int, targetLanguage: str, timestamp: int):
        super().__init__(type='listenerJoined', timestamp=timestamp)
        self.sessionId = sessionId
        self.listenerCount = listenerCount
        self.targetLanguage = targetLanguage


@dataclass
class SessionStatusMessage(WebSocketMessage):
    """Message sent with session status updates."""
    
    sessionId: str
    isActive: bool
    listenerCount: int
    languageDistribution: Dict[str, int]
    
    def __init__(self, sessionId: str, isActive: bool, listenerCount: int, 
                 languageDistribution: Dict[str, int], timestamp: int):
        super().__init__(type='sessionStatus', timestamp=timestamp)
        self.sessionId = sessionId
        self.isActive = isActive
        self.listenerCount = listenerCount
        self.languageDistribution = languageDistribution


@dataclass
class BroadcastControlMessage(WebSocketMessage):
    """Message sent when broadcast control changes."""
    
    sessionId: str
    isPaused: bool
    isMuted: bool
    volume: float
    
    def __init__(self, sessionId: str, isPaused: bool, isMuted: bool, volume: float, timestamp: int):
        super().__init__(type='broadcastControl', timestamp=timestamp)
        self.sessionId = sessionId
        self.isPaused = isPaused
        self.isMuted = isMuted
        self.volume = volume


@dataclass
class AudioQualityWarningMessage(WebSocketMessage):
    """Message sent when audio quality issues detected."""
    
    sessionId: str
    warningType: str  # 'clipping', 'echo', 'silence', 'low_snr'
    severity: str  # 'warning', 'critical'
    message: str
    recommendation: str
    
    def __init__(self, sessionId: str, warningType: str, severity: str, 
                 message: str, recommendation: str, timestamp: int):
        super().__init__(type='audioQualityWarning', timestamp=timestamp)
        self.sessionId = sessionId
        self.warningType = warningType
        self.severity = severity
        self.message = message
        self.recommendation = recommendation


@dataclass
class ConnectionRefreshMessage(WebSocketMessage):
    """Message sent when connection refresh is required."""
    
    sessionId: str
    newConnectionUrl: str
    expiresIn: int  # seconds until current connection expires
    
    def __init__(self, sessionId: str, newConnectionUrl: str, expiresIn: int, timestamp: int):
        super().__init__(type='connectionRefresh', timestamp=timestamp)
        self.sessionId = sessionId
        self.newConnectionUrl = newConnectionUrl
        self.expiresIn = expiresIn


@dataclass
class ErrorMessage(WebSocketMessage):
    """Message sent when error occurs."""
    
    code: str
    message: str
    details: Optional[str] = None
    correlationId: Optional[str] = None
    
    def __init__(self, code: str, message: str, timestamp: int, 
                 details: Optional[str] = None, correlationId: Optional[str] = None):
        super().__init__(type='error', timestamp=timestamp)
        self.code = code
        self.message = message
        self.details = details
        self.correlationId = correlationId


# Message validation functions

def validate_create_session_request(data: Dict[str, Any]) -> bool:
    """
    Validate createSession request message.
    
    Required fields:
    - action: 'createSession'
    - sourceLanguage: ISO 639-1 code
    - qualityTier: 'standard' or 'premium'
    
    Args:
        data: Message data dictionary
    
    Returns:
        True if valid, False otherwise
    """
    required_fields = ['action', 'sourceLanguage', 'qualityTier']
    return all(field in data for field in required_fields)


def validate_join_session_request(data: Dict[str, Any]) -> bool:
    """
    Validate joinSession request message.
    
    Required fields:
    - action: 'joinSession'
    - sessionId: Session identifier
    - targetLanguage: ISO 639-1 code
    
    Args:
        data: Message data dictionary
    
    Returns:
        True if valid, False otherwise
    """
    required_fields = ['action', 'sessionId', 'targetLanguage']
    return all(field in data for field in required_fields)


def validate_broadcast_control_request(data: Dict[str, Any]) -> bool:
    """
    Validate broadcast control request message.
    
    Required fields:
    - action: 'pause', 'resume', 'mute', 'unmute', or 'setVolume'
    - sessionId: Session identifier
    
    Optional fields:
    - volume: 0.0-1.0 (required for 'setVolume' action)
    
    Args:
        data: Message data dictionary
    
    Returns:
        True if valid, False otherwise
    """
    if 'action' not in data or 'sessionId' not in data:
        return False
    
    action = data['action']
    valid_actions = ['pause', 'resume', 'mute', 'unmute', 'setVolume']
    
    if action not in valid_actions:
        return False
    
    # setVolume requires volume parameter
    if action == 'setVolume':
        if 'volume' not in data:
            return False
        volume = data['volume']
        if not isinstance(volume, (int, float)) or not (0.0 <= volume <= 1.0):
            return False
    
    return True


def validate_get_session_status_request(data: Dict[str, Any]) -> bool:
    """
    Validate getSessionStatus request message.
    
    Required fields:
    - action: 'getSessionStatus'
    - sessionId: Session identifier
    
    Args:
        data: Message data dictionary
    
    Returns:
        True if valid, False otherwise
    """
    required_fields = ['action', 'sessionId']
    return all(field in data for field in required_fields)


# Message type registry for validation
MESSAGE_VALIDATORS = {
    'createSession': validate_create_session_request,
    'joinSession': validate_join_session_request,
    'pause': validate_broadcast_control_request,
    'resume': validate_broadcast_control_request,
    'mute': validate_broadcast_control_request,
    'unmute': validate_broadcast_control_request,
    'setVolume': validate_broadcast_control_request,
    'getSessionStatus': validate_get_session_status_request,
}


def validate_message(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate WebSocket message.
    
    Args:
        data: Message data dictionary
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, 'Message must be a JSON object'
    
    if 'action' not in data:
        return False, 'Missing required field: action'
    
    action = data['action']
    
    if action not in MESSAGE_VALIDATORS:
        return False, f'Unknown action: {action}'
    
    validator = MESSAGE_VALIDATORS[action]
    
    if not validator(data):
        return False, f'Invalid message format for action: {action}'
    
    return True, None
