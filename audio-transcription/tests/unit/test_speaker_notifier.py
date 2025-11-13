"""Unit tests for SpeakerNotifier."""

import time
import pytest
from unittest.mock import Mock, MagicMock
from audio_quality.notifiers.speaker_notifier import SpeakerNotifier


class TestSpeakerNotifier:
    """Test suite for SpeakerNotifier."""
    
    @pytest.fixture
    def mock_websocket_manager(self):
        """Fixture for mock WebSocket manager."""
        manager = Mock()
        manager.send_message = MagicMock()
        manager.sent_messages = []
        
        # Track sent messages
        def track_message(connection_id, message):
            manager.sent_messages.append({
                'connection_id': connection_id,
                'message': message
            })
        
        manager.send_message.side_effect = track_message
        return manager
    
    @pytest.fixture
    def notifier(self, mock_websocket_manager):
        """Fixture for SpeakerNotifier instance."""
        return SpeakerNotifier(mock_websocket_manager)
    
    def test_notification_message_sending_via_websocket(self, notifier, mock_websocket_manager):
        """Test notification message sending via WebSocket."""
        connection_id = 'conn-123'
        issue_type = 'snr_low'
        details = {'snr': 15.2, 'threshold': 20.0}
        
        notifier.notify_speaker(connection_id, issue_type, details)
        
        # Verify message was sent
        assert len(mock_websocket_manager.sent_messages) == 1, "Should send one message"
        
        sent = mock_websocket_manager.sent_messages[0]
        assert sent['connection_id'] == connection_id, "Should send to correct connection"
        assert sent['message']['type'] == 'audio_quality_warning', "Should have correct message type"
        assert sent['message']['issue'] == issue_type, "Should include issue type"
        assert sent['message']['details'] == details, "Should include details"
    
    def test_rate_limiting_effectiveness(self, notifier, mock_websocket_manager):
        """Test rate limiting effectiveness (1 per minute per issue type)."""
        connection_id = 'conn-123'
        issue_type = 'snr_low'
        
        # Send 10 notifications rapidly
        for i in range(10):
            notifier.notify_speaker(connection_id, issue_type, {'snr': 15.0 - i * 0.1})
        
        # Should only send 1 notification due to rate limiting
        assert len(mock_websocket_manager.sent_messages) == 1, \
            f"Rate limiting should prevent flooding, got {len(mock_websocket_manager.sent_messages)} messages"
    
    def test_rate_limiting_per_issue_type(self, notifier, mock_websocket_manager):
        """Test that rate limiting is per issue type."""
        connection_id = 'conn-123'
        
        # Send different issue types
        notifier.notify_speaker(connection_id, 'snr_low', {'snr': 15.0})
        notifier.notify_speaker(connection_id, 'clipping', {'percentage': 5.0})
        notifier.notify_speaker(connection_id, 'echo', {'echo_db': -10.0})
        notifier.notify_speaker(connection_id, 'silence', {'duration': 6.0})
        
        # Should send one message per issue type
        assert len(mock_websocket_manager.sent_messages) == 4, \
            "Should send one message per issue type"
        
        issue_types = [msg['message']['issue'] for msg in mock_websocket_manager.sent_messages]
        assert 'snr_low' in issue_types, "Should include snr_low"
        assert 'clipping' in issue_types, "Should include clipping"
        assert 'echo' in issue_types, "Should include echo"
        assert 'silence' in issue_types, "Should include silence"
    
    def test_rate_limiting_allows_notification_after_timeout(self, notifier, mock_websocket_manager):
        """Test that rate limiting allows notification after timeout period."""
        connection_id = 'conn-123'
        issue_type = 'snr_low'
        
        # Send first notification
        notifier.notify_speaker(connection_id, issue_type, {'snr': 15.0})
        assert len(mock_websocket_manager.sent_messages) == 1, "Should send first notification"
        
        # Manually advance time by 61 seconds (beyond rate limit)
        key = f"{connection_id}:{issue_type}"
        notifier.notification_history[key] = time.time() - 61
        
        # Send second notification
        notifier.notify_speaker(connection_id, issue_type, {'snr': 14.0})
        
        # Should send second notification after rate limit expires
        assert len(mock_websocket_manager.sent_messages) == 2, \
            "Should allow notification after rate limit expires"
    
    def test_notification_format_and_content(self, notifier, mock_websocket_manager):
        """Test notification format and content."""
        connection_id = 'conn-123'
        issue_type = 'snr_low'
        details = {'snr': 15.2, 'threshold': 20.0}
        
        notifier.notify_speaker(connection_id, issue_type, details)
        
        message = mock_websocket_manager.sent_messages[0]['message']
        
        # Verify message structure
        assert 'type' in message, "Message should have type field"
        assert 'issue' in message, "Message should have issue field"
        assert 'message' in message, "Message should have message field"
        assert 'details' in message, "Message should have details field"
        assert 'timestamp' in message, "Message should have timestamp field"
        
        # Verify message content
        assert message['type'] == 'audio_quality_warning', "Type should be audio_quality_warning"
        assert message['issue'] == issue_type, "Issue should match"
        assert isinstance(message['message'], str), "Message should be a string"
        assert len(message['message']) > 0, "Message should not be empty"
        assert message['details'] == details, "Details should match"
    
    def test_notification_messages_for_all_issue_types(self, notifier, mock_websocket_manager):
        """Test notification messages for all issue types."""
        connection_id = 'conn-123'
        
        test_cases = [
            ('snr_low', {'snr': 15.2}, 'SNR'),
            ('clipping', {'percentage': 5.0}, 'clipping'),
            ('echo', {'echo_db': -10.0}, 'echo'),
            ('silence', {'duration': 6.0}, 'silence')
        ]
        
        for issue_type, details, expected_keyword in test_cases:
            # Clear previous messages
            mock_websocket_manager.sent_messages.clear()
            notifier.notification_history.clear()
            
            notifier.notify_speaker(connection_id, issue_type, details)
            
            assert len(mock_websocket_manager.sent_messages) == 1, \
                f"Should send message for {issue_type}"
            
            message = mock_websocket_manager.sent_messages[0]['message']
            assert expected_keyword.lower() in message['message'].lower(), \
                f"Message for {issue_type} should mention {expected_keyword}"
    
    def test_notification_includes_remediation_steps(self, notifier, mock_websocket_manager):
        """Test that notifications include remediation steps."""
        test_cases = [
            ('snr_low', {'snr': 15.2}, ['microphone', 'noise']),
            ('clipping', {'percentage': 5.0}, ['volume', 'reduce']),
            ('echo', {'echo_db': -10.0}, ['echo cancellation', 'headphones']),
            ('silence', {'duration': 6.0}, ['muted', 'microphone'])
        ]
        
        for issue_type, details, expected_keywords in test_cases:
            # Clear previous messages
            mock_websocket_manager.sent_messages.clear()
            notifier.notification_history.clear()
            
            notifier.notify_speaker('conn-123', issue_type, details)
            
            message = mock_websocket_manager.sent_messages[0]['message']['message'].lower()
            
            # Check that at least one remediation keyword is present
            has_remediation = any(keyword.lower() in message for keyword in expected_keywords)
            assert has_remediation, \
                f"Message for {issue_type} should include remediation steps: {expected_keywords}"
    
    def test_rate_limiting_per_connection(self, notifier, mock_websocket_manager):
        """Test that rate limiting is per connection."""
        issue_type = 'snr_low'
        
        # Send notifications to different connections
        notifier.notify_speaker('conn-123', issue_type, {'snr': 15.0})
        notifier.notify_speaker('conn-456', issue_type, {'snr': 14.0})
        notifier.notify_speaker('conn-789', issue_type, {'snr': 13.0})
        
        # Should send one message per connection
        assert len(mock_websocket_manager.sent_messages) == 3, \
            "Should send one message per connection"
        
        connection_ids = [msg['connection_id'] for msg in mock_websocket_manager.sent_messages]
        assert 'conn-123' in connection_ids, "Should include conn-123"
        assert 'conn-456' in connection_ids, "Should include conn-456"
        assert 'conn-789' in connection_ids, "Should include conn-789"
    
    def test_notification_timestamp_is_current(self, notifier, mock_websocket_manager):
        """Test that notification timestamp is current."""
        before_time = time.time()
        
        notifier.notify_speaker('conn-123', 'snr_low', {'snr': 15.0})
        
        after_time = time.time()
        
        message = mock_websocket_manager.sent_messages[0]['message']
        timestamp = message['timestamp']
        
        assert before_time <= timestamp <= after_time, \
            "Timestamp should be current time"
    
    def test_notification_with_empty_details(self, notifier, mock_websocket_manager):
        """Test notification with empty details."""
        notifier.notify_speaker('conn-123', 'snr_low', {})
        
        assert len(mock_websocket_manager.sent_messages) == 1, "Should send message even with empty details"
        message = mock_websocket_manager.sent_messages[0]['message']
        assert message['details'] == {}, "Should include empty details"
    
    def test_rate_limit_configuration(self):
        """Test that rate limit can be configured."""
        mock_manager = Mock()
        mock_manager.send_message = MagicMock()
        mock_manager.sent_messages = []
        
        # Create notifier with custom rate limit
        notifier = SpeakerNotifier(mock_manager)
        notifier.rate_limit_seconds = 30  # 30 seconds instead of 60
        
        assert notifier.rate_limit_seconds == 30, "Rate limit should be configurable"
