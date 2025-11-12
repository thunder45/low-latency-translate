"""
Speaker notifier.

This module provides the SpeakerNotifier class for sending audio quality
warnings to speakers via WebSocket. Implements rate limiting to prevent
notification flooding.
"""

import time
import logging
from typing import Dict, Any, Optional


logger = logging.getLogger(__name__)


class SpeakerNotifier:
    """
    Sends quality warnings to speakers via WebSocket.
    
    Notifies speakers of audio quality issues including SNR, clipping,
    echo, and silence detection. Implements rate limiting to prevent
    notification flooding (1 notification per issue type per 60 seconds).
    """
    
    def __init__(
        self,
        websocket_client,
        rate_limit_seconds: int = 60
    ):
        """
        Initializes the speaker notifier.
        
        Args:
            websocket_client: WebSocket client for sending messages
                             (e.g., API Gateway Management API client)
            rate_limit_seconds: Rate limit window in seconds (default: 60)
        """
        self.websocket = websocket_client
        self.rate_limit_seconds = rate_limit_seconds
        
        # Track last notification time per connection and issue type
        # Key format: "{connection_id}:{issue_type}"
        self.notification_history: Dict[str, float] = {}
    
    def notify_speaker(
        self,
        connection_id: str,
        issue_type: str,
        details: Dict[str, Any]
    ) -> bool:
        """
        Sends quality warning to speaker.
        
        Warning messages include:
        - Issue type (SNR, clipping, echo, silence)
        - Current metric value
        - Suggested remediation steps
        
        Rate limiting: Max 1 notification per issue type per 60 seconds.
        If rate limit is exceeded, the notification is skipped and False is returned.
        
        Args:
            connection_id: WebSocket connection ID
            issue_type: Type of quality issue (snr_low, clipping, echo, silence)
            details: Issue details and metrics
            
        Returns:
            True if notification was sent, False if skipped due to rate limit
        """
        # Check rate limit
        key = f'{connection_id}:{issue_type}'
        current_time = time.time()
        last_notification = self.notification_history.get(key, 0)
        
        if current_time - last_notification < self.rate_limit_seconds:
            logger.debug(
                f'Skipping notification due to rate limit: {issue_type} '
                f'for connection {connection_id}'
            )
            return False
        
        # Format warning message
        message = self._format_warning(issue_type, details)
        
        # Create WebSocket message
        websocket_message = {
            'type': 'audio_quality_warning',
            'issue': issue_type,
            'message': message,
            'details': details,
            'timestamp': current_time
        }
        
        # Send via WebSocket
        try:
            self._send_message(connection_id, websocket_message)
            
            # Update notification history
            self.notification_history[key] = current_time
            
            logger.info(
                f'Sent quality warning: {issue_type} to connection {connection_id}'
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f'Failed to send quality warning to connection {connection_id}: {e}',
                exc_info=True
            )
            return False
    
    def _format_warning(self, issue_type: str, details: Dict[str, Any]) -> str:
        """
        Formats user-friendly warning messages with remediation steps.
        
        Args:
            issue_type: Type of quality issue
            details: Issue details including metric values
            
        Returns:
            User-friendly warning message with remediation steps
        """
        # Helper function to format metric values
        def format_metric(key: str, precision: int = 1) -> str:
            value = details.get(key)
            if value is None:
                return 'N/A'
            try:
                return f'{float(value):.{precision}f}'
            except (ValueError, TypeError):
                return str(value)
        
        warnings = {
            'snr_low': (
                f"Audio quality is low (SNR: {format_metric('snr', 1)} dB). "
                f"Try moving closer to your microphone or reducing background noise."
            ),
            'clipping': (
                f"Audio is clipping ({format_metric('percentage', 1)}%). "
                f"Please reduce your microphone volume or move further away."
            ),
            'echo': (
                f"Echo detected (level: {format_metric('echo_db', 1)} dB). "
                f"Enable echo cancellation in your browser or use headphones."
            ),
            'silence': (
                f"No audio detected for {format_metric('duration', 0)} seconds. "
                f"Check if your microphone is muted or disconnected."
            )
        }
        
        return warnings.get(
            issue_type,
            f"Audio quality issue detected: {issue_type}"
        )
    
    def _send_message(
        self,
        connection_id: str,
        message: Dict[str, Any]
    ) -> None:
        """
        Sends message via WebSocket.
        
        This method handles the actual WebSocket communication. The implementation
        depends on the WebSocket client being used (e.g., API Gateway Management API).
        
        Args:
            connection_id: WebSocket connection ID
            message: Message to send (will be JSON-serialized)
            
        Raises:
            Exception: If message sending fails
        """
        # For API Gateway WebSocket API, use post_to_connection
        # The websocket client should be an API Gateway Management API client
        import json
        
        try:
            self.websocket.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps(message).encode('utf-8')
            )
        except AttributeError:
            # If websocket client doesn't have post_to_connection,
            # it might be a mock or different implementation
            # Try calling a generic send_message method
            if hasattr(self.websocket, 'send_message'):
                self.websocket.send_message(connection_id, message)
            else:
                raise TypeError(
                    'WebSocket client must have post_to_connection or send_message method'
                )
    
    def clear_history(self, connection_id: Optional[str] = None) -> None:
        """
        Clears notification history.
        
        Useful for testing or when a connection is closed.
        
        Args:
            connection_id: If provided, clears history only for this connection.
                          If None, clears all history.
        """
        if connection_id is None:
            self.notification_history.clear()
            logger.debug('Cleared all notification history')
        else:
            # Remove all entries for this connection
            keys_to_remove = [
                key for key in self.notification_history.keys()
                if key.startswith(f'{connection_id}:')
            ]
            for key in keys_to_remove:
                del self.notification_history[key]
            
            logger.debug(
                f'Cleared notification history for connection {connection_id}'
            )
