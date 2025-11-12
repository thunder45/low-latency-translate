"""
Demo script for SpeakerNotifier.

This script demonstrates how to use the SpeakerNotifier class
to send audio quality warnings to speakers via WebSocket.
"""

import time
from unittest.mock import Mock

from audio_quality.notifiers.speaker_notifier import SpeakerNotifier


def demo_basic_notification():
    """Demonstrates basic notification sending."""
    print('=== Demo: Basic Notification ===\n')
    
    # Create mock WebSocket client
    mock_websocket = Mock()
    
    # Initialize notifier
    notifier = SpeakerNotifier(
        websocket_client=mock_websocket,
        rate_limit_seconds=60
    )
    
    # Send SNR warning
    connection_id = 'conn-123'
    issue_type = 'snr_low'
    details = {'snr': 15.2, 'threshold': 20.0}
    
    success = notifier.notify_speaker(connection_id, issue_type, details)
    
    print(f'Notification sent: {success}')
    print(f'WebSocket calls: {mock_websocket.post_to_connection.call_count}')
    
    # Verify message format
    if mock_websocket.post_to_connection.called:
        call_args = mock_websocket.post_to_connection.call_args
        print(f'\nConnection ID: {call_args.kwargs["ConnectionId"]}')
        print(f'Message data: {call_args.kwargs["Data"].decode("utf-8")}')
    
    print()


def demo_rate_limiting():
    """Demonstrates rate limiting behavior."""
    print('=== Demo: Rate Limiting ===\n')
    
    # Create mock WebSocket client
    mock_websocket = Mock()
    
    # Initialize notifier with short rate limit for demo
    notifier = SpeakerNotifier(
        websocket_client=mock_websocket,
        rate_limit_seconds=2  # 2 seconds for demo
    )
    
    connection_id = 'conn-456'
    issue_type = 'clipping'
    
    # Send first notification
    details1 = {'percentage': 5.2}
    success1 = notifier.notify_speaker(connection_id, issue_type, details1)
    print(f'First notification sent: {success1}')
    
    # Try to send second notification immediately (should be rate limited)
    details2 = {'percentage': 5.5}
    success2 = notifier.notify_speaker(connection_id, issue_type, details2)
    print(f'Second notification sent (immediate): {success2}')
    
    # Wait for rate limit to expire
    print('Waiting 2 seconds for rate limit to expire...')
    time.sleep(2.1)
    
    # Send third notification (should succeed)
    details3 = {'percentage': 6.0}
    success3 = notifier.notify_speaker(connection_id, issue_type, details3)
    print(f'Third notification sent (after wait): {success3}')
    
    print(f'\nTotal WebSocket calls: {mock_websocket.post_to_connection.call_count}')
    print('Expected: 2 (first and third notifications)\n')


def demo_multiple_issue_types():
    """Demonstrates handling multiple issue types."""
    print('=== Demo: Multiple Issue Types ===\n')
    
    # Create mock WebSocket client
    mock_websocket = Mock()
    
    # Initialize notifier
    notifier = SpeakerNotifier(
        websocket_client=mock_websocket,
        rate_limit_seconds=60
    )
    
    connection_id = 'conn-789'
    
    # Send different types of warnings
    warnings = [
        ('snr_low', {'snr': 15.2}),
        ('clipping', {'percentage': 5.2}),
        ('echo', {'echo_db': -12.5}),
        ('silence', {'duration': 6.0})
    ]
    
    for issue_type, details in warnings:
        success = notifier.notify_speaker(connection_id, issue_type, details)
        print(f'{issue_type}: {success}')
    
    print(f'\nTotal notifications sent: {mock_websocket.post_to_connection.call_count}')
    print('Expected: 4 (one for each issue type)\n')


def demo_warning_messages():
    """Demonstrates warning message formatting."""
    print('=== Demo: Warning Message Formatting ===\n')
    
    # Create mock WebSocket client
    mock_websocket = Mock()
    
    # Initialize notifier
    notifier = SpeakerNotifier(
        websocket_client=mock_websocket,
        rate_limit_seconds=60
    )
    
    # Test different warning messages
    test_cases = [
        ('snr_low', {'snr': 15.2}),
        ('clipping', {'percentage': 5.2}),
        ('echo', {'echo_db': -12.5}),
        ('silence', {'duration': 6.0})
    ]
    
    for issue_type, details in test_cases:
        message = notifier._format_warning(issue_type, details)
        print(f'{issue_type}:')
        print(f'  {message}\n')


def demo_connection_cleanup():
    """Demonstrates clearing notification history."""
    print('=== Demo: Connection Cleanup ===\n')
    
    # Create mock WebSocket client
    mock_websocket = Mock()
    
    # Initialize notifier
    notifier = SpeakerNotifier(
        websocket_client=mock_websocket,
        rate_limit_seconds=60
    )
    
    # Send notifications for multiple connections
    notifier.notify_speaker('conn-1', 'snr_low', {'snr': 15.0})
    notifier.notify_speaker('conn-2', 'clipping', {'percentage': 5.0})
    notifier.notify_speaker('conn-3', 'echo', {'echo_db': -12.0})
    
    print(f'Notification history entries: {len(notifier.notification_history)}')
    
    # Clear history for specific connection
    notifier.clear_history('conn-1')
    print(f'After clearing conn-1: {len(notifier.notification_history)}')
    
    # Clear all history
    notifier.clear_history()
    print(f'After clearing all: {len(notifier.notification_history)}\n')


def main():
    """Runs all demo scenarios."""
    print('SpeakerNotifier Demo\n')
    print('=' * 60)
    print()
    
    demo_basic_notification()
    demo_rate_limiting()
    demo_multiple_issue_types()
    demo_warning_messages()
    demo_connection_cleanup()
    
    print('=' * 60)
    print('Demo complete!')


if __name__ == '__main__':
    main()
