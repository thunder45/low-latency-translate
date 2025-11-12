# Task 9: Implement Speaker Notifications

## Task Description

Implemented the SpeakerNotifier class to send audio quality warnings to speakers via WebSocket with rate limiting to prevent notification flooding.

## Task Instructions

**Task 9.1: Create SpeakerNotifier class**
- Implement `notifiers/speaker_notifier.py` with SpeakerNotifier class
- Implement notify_speaker method to send warnings via WebSocket
- Implement rate limiting (1 notification per issue type per 60 seconds)
- Implement _format_warning method with user-friendly messages and remediation steps
- Requirements: 7.1, 7.2, 7.3, 7.4, 7.5

## Task Tests

### Demo Execution
```bash
python -m audio_quality.examples.demo_speaker_notifier
```

**Results:**
- ✅ Basic notification sending works correctly
- ✅ Rate limiting prevents notification flooding (1 per issue type per 60 seconds)
- ✅ Multiple issue types can be sent independently
- ✅ Warning messages are formatted with user-friendly text and remediation steps
- ✅ Connection cleanup works correctly

**Demo Output:**
```
=== Demo: Basic Notification ===
Notification sent: True
WebSocket calls: 1

=== Demo: Rate Limiting ===
First notification sent: True
Second notification sent (immediate): False
Third notification sent (after wait): True
Total WebSocket calls: 2

=== Demo: Multiple Issue Types ===
snr_low: True
clipping: True
echo: True
silence: True
Total notifications sent: 4

=== Demo: Warning Message Formatting ===
snr_low: Audio quality is low (SNR: 15.2 dB). Try moving closer to your microphone...
clipping: Audio is clipping (5.2%). Please reduce your microphone volume...
echo: Echo detected (level: -12.5 dB). Enable echo cancellation...
silence: No audio detected for 6 seconds. Check if your microphone is muted...

=== Demo: Connection Cleanup ===
Notification history entries: 3
After clearing conn-1: 2
After clearing all: 0
```

## Task Solution

### Implementation Overview

Created `audio_quality/notifiers/speaker_notifier.py` with the following components:

**SpeakerNotifier Class:**
- Sends quality warnings to speakers via WebSocket
- Implements rate limiting (1 notification per issue type per 60 seconds)
- Formats user-friendly warning messages with remediation steps
- Supports connection cleanup for testing and disconnection handling

### Key Features

**1. Rate Limiting (Requirement 7.5)**
- Tracks last notification time per connection and issue type
- Key format: `{connection_id}:{issue_type}`
- Prevents notification flooding by limiting to 1 per issue type per 60 seconds
- Returns False if rate limit is exceeded

**2. User-Friendly Warning Messages (Requirements 7.1, 7.2, 7.3, 7.4)**
- SNR Low: "Audio quality is low (SNR: X dB). Try moving closer to your microphone or reducing background noise."
- Clipping: "Audio is clipping (X%). Please reduce your microphone volume or move further away."
- Echo: "Echo detected (level: X dB). Enable echo cancellation in your browser or use headphones."
- Silence: "No audio detected for X seconds. Check if your microphone is muted or disconnected."

**3. WebSocket Integration**
- Supports API Gateway Management API client (post_to_connection method)
- Fallback to generic send_message method for other implementations
- JSON-serializes messages before sending
- Handles errors gracefully with logging

**4. Message Format**
```json
{
  "type": "audio_quality_warning",
  "issue": "snr_low",
  "message": "Audio quality is low (SNR: 15.2 dB). Try moving closer...",
  "details": {
    "snr": 15.2,
    "threshold": 20.0
  },
  "timestamp": 1762984267.780084
}
```

### Files Created

1. **audio_quality/notifiers/speaker_notifier.py** (220 lines)
   - SpeakerNotifier class implementation
   - Rate limiting logic
   - Warning message formatting
   - WebSocket communication

2. **audio_quality/examples/demo_speaker_notifier.py** (189 lines)
   - Comprehensive demo script
   - Shows basic notification sending
   - Demonstrates rate limiting behavior
   - Shows multiple issue types
   - Demonstrates warning message formatting
   - Shows connection cleanup

### Files Modified

1. **audio_quality/notifiers/__init__.py**
   - Added SpeakerNotifier to exports

### Design Decisions

**Rate Limiting Implementation:**
- Used dictionary with composite key (`connection_id:issue_type`) for efficient lookups
- Stores timestamp of last notification for each key
- Simple time-based check prevents flooding

**Warning Message Formatting:**
- Helper function `format_metric()` handles missing or invalid values gracefully
- Returns 'N/A' for missing values instead of raising errors
- Supports different precision levels for different metrics

**WebSocket Client Abstraction:**
- Supports API Gateway Management API (post_to_connection)
- Fallback to generic send_message method
- Raises TypeError if neither method is available
- Allows for easy testing with mock clients

**Error Handling:**
- Logs errors but doesn't raise exceptions
- Returns False on failure to allow caller to handle gracefully
- Prevents notification failures from blocking audio processing

### Requirements Coverage

✅ **Requirement 7.1**: Sends SNR warning when threshold violated  
✅ **Requirement 7.2**: Sends clipping warning when threshold exceeded  
✅ **Requirement 7.3**: Sends echo warning when detected above threshold  
✅ **Requirement 7.4**: Includes issue type and remediation steps in messages  
✅ **Requirement 7.5**: Limits warnings to 1 per issue type per 60 seconds  

### Integration Points

**With AudioQualityAnalyzer:**
```python
# After analyzing audio quality
if metrics.snr_db < config.snr_threshold_db:
    notifier.notify_speaker(
        connection_id,
        'snr_low',
        {'snr': metrics.snr_db, 'threshold': config.snr_threshold_db}
    )
```

**With Lambda Handler:**
```python
# Initialize notifier (reuse across invocations)
if not hasattr(lambda_handler, 'notifier'):
    lambda_handler.notifier = SpeakerNotifier(
        websocket_client=apigateway_management_client,
        rate_limit_seconds=60
    )

# Use in handler
lambda_handler.notifier.notify_speaker(connection_id, issue_type, details)
```

### Testing Strategy

**Demo Script Coverage:**
- Basic notification sending
- Rate limiting behavior
- Multiple issue types
- Warning message formatting
- Connection cleanup

**Future Unit Tests (Task 15.6):**
- Test notification message sending via WebSocket
- Test rate limiting effectiveness (1 per minute per issue type)
- Verify notification format and content
- Test error handling

### Performance Considerations

**Memory Usage:**
- Notification history grows with number of connections and issue types
- Maximum entries: `connections × 4 issue types`
- For 50 connections: ~200 entries (negligible memory)

**Processing Overhead:**
- Dictionary lookup: O(1)
- Time comparison: O(1)
- Message formatting: O(1)
- Total overhead: <1ms per notification check

**Rate Limiting Efficiency:**
- No cleanup of old entries (acceptable for short-lived Lambda)
- For long-running processes, could add periodic cleanup
- Current implementation suitable for Lambda use case

### Next Steps

1. **Task 10**: Implement optional audio processing (high-pass filter, noise gate)
2. **Task 11**: Integrate with Lambda function
3. **Task 15.6**: Write unit tests for speaker notifier

### Notes

- WebSocket client must be provided by caller (API Gateway Management API)
- Rate limiting is per-connection and per-issue-type (independent limits)
- Notification history is not persisted (resets on Lambda cold start)
- Clear history on connection disconnect to prevent memory growth
