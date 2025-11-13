# Bug Fix Requirements Document

## Introduction

This specification addresses critical bugs discovered through comprehensive unit and integration testing of the audio quality validation system. The tests revealed implementation issues in SNR calculation, echo detection, silence detection, clipping detection, metrics emission, and speaker notifications.

## Glossary

- **SNR (Signal-to-Noise Ratio)**: A measure comparing the level of desired signal to background noise, expressed in decibels (dB)
- **Noise Floor**: The measure of the signal created from the sum of all noise sources
- **Autocorrelation**: A mathematical tool for finding repeating patterns in a signal
- **False Positive**: Incorrectly identifying a condition when it doesn't exist
- **State Management**: Maintaining data across multiple function calls

## Requirements

### Requirement 1: Fix SNR Calculation Algorithm

**User Story:** As a system operator, I want accurate SNR measurements, so that I can trust the audio quality metrics.

#### Acceptance Criteria

1. WHEN a clean sine wave signal (amplitude 0.5) is analyzed, THE SNR Calculator SHALL return SNR greater than 40 dB
2. WHEN a noisy signal (signal amplitude 0.1, noise stddev 0.1) is analyzed, THE SNR Calculator SHALL return SNR between 0 and 20 dB
3. WHEN a very noisy signal (signal amplitude 0.05, noise stddev 0.2) is analyzed, THE SNR Calculator SHALL return SNR less than 10 dB
4. THE SNR Calculator SHALL properly separate signal energy from noise floor energy
5. THE SNR Calculator SHALL handle near-silent signals without returning NaN or infinite values

### Requirement 2: Fix Echo Detector False Positives and Delay Measurement

**User Story:** As an audio engineer, I want accurate echo detection without false positives, so that speakers are only notified of real echo issues.

#### Acceptance Criteria

1. WHEN a clean signal without echo is analyzed, THE Echo Detector SHALL NOT report echo detection (has_echo = False)
2. WHEN a signal with 100ms echo is analyzed, THE Echo Detector SHALL report delay between 90ms and 110ms
3. WHEN a signal with 50ms echo is analyzed, THE Echo Detector SHALL report delay between 40ms and 60ms
4. WHEN a signal with 200ms echo is analyzed, THE Echo Detector SHALL report delay between 180ms and 220ms
5. THE Echo Detector SHALL properly identify autocorrelation peaks in the 10-500ms delay range
6. THE Echo Detector SHALL NOT report the same delay (~11.38ms) for all signals regardless of actual echo

### Requirement 3: Fix Silence Detector State Management

**User Story:** As a system operator, I want accurate silence duration tracking, so that I can identify when speakers have technical issues.

#### Acceptance Criteria

1. WHEN audio energy remains below -50 dB for 6 seconds, THE Silence Detector SHALL report is_silent as True
2. WHEN audio energy remains below -50 dB for 6 seconds, THE Silence Detector SHALL report duration_s greater than 5.0
3. THE Silence Detector SHALL maintain silence_start_time state across multiple detect_silence() calls
4. WHEN audio energy returns above -50 dB after silence, THE Silence Detector SHALL reset duration_s to 0.0
5. WHEN processing multiple 1-second chunks of silence, THE Silence Detector SHALL accumulate duration correctly

### Requirement 4: Fix Clipping Detector Threshold Logic

**User Story:** As a system operator, I want accurate clipping detection, so that I can notify speakers when their audio is distorted.

#### Acceptance Criteria

1. WHEN audio samples reach 98% of maximum amplitude (32112 for 16-bit), THE Clipping Detector SHALL count them as clipped
2. WHEN 100 out of 1000 samples are at clipping threshold, THE Clipping Detector SHALL report clipping_percentage of approximately 10%
3. WHEN samples are exactly at the threshold value, THE Clipping Detector SHALL count them as clipped
4. WHEN samples are 1 unit below threshold, THE Clipping Detector SHALL NOT count them as clipped
5. WHEN an empty audio array is provided, THE Clipping Detector SHALL return 0% clipping without throwing an exception

### Requirement 5: Fix Metrics Emitter Implementation

**User Story:** As a monitoring system, I want metrics properly emitted to CloudWatch, so that I can track audio quality trends.

#### Acceptance Criteria

1. WHEN emit_metrics() is called, THE Metrics Emitter SHALL invoke cloudwatch_client.put_metric_data()
2. THE Metrics Emitter SHALL include namespace 'AudioQuality' in CloudWatch calls
3. THE Metrics Emitter SHALL include MetricData array with SNR and ClippingPercentage metrics
4. THE Metrics Emitter SHALL include stream_id as a dimension for each metric
5. WHEN emit_quality_event() is called, THE Metrics Emitter SHALL invoke eventbridge_client.put_events()

### Requirement 6: Fix Speaker Notifier WebSocket Integration

**User Story:** As a speaker, I want to receive quality warnings via WebSocket, so that I can fix audio issues in real-time.

#### Acceptance Criteria

1. WHEN notify_speaker() is called, THE Speaker Notifier SHALL invoke websocket_manager.send_message()
2. THE Speaker Notifier SHALL include message type 'audio_quality_warning' in notifications
3. THE Speaker Notifier SHALL include issue type, details, and timestamp in notifications
4. WHEN multiple notifications are sent within 60 seconds for the same issue type, THE Speaker Notifier SHALL send only the first notification
5. WHEN 61 seconds have elapsed since last notification, THE Speaker Notifier SHALL allow a new notification for the same issue type

### Requirement 7: Fix QualityMetrics Data Model

**User Story:** As a developer, I want consistent field names in QualityMetrics, so that integration tests pass.

#### Acceptance Criteria

1. THE QualityMetrics dataclass SHALL have a field named 'silence_duration_s' (not 'duration_s')
2. THE QualityMetrics dataclass SHALL be accessible via both 'silence_duration_s' and 'duration_s' for backward compatibility
3. ALL integration tests SHALL pass without AttributeError for 'duration_s'
