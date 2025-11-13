# Bug Fix Implementation Plan

## Overview

This implementation plan addresses the 7 critical bugs discovered through unit and integration testing. Each task focuses on fixing a specific bug and validating the fix with existing tests.

## Tasks

- [x] 1. Fix SNR Calculator Algorithm
- [x] 1.1 Update calculate_snr method with improved noise floor estimation
  - Implement frame-based RMS calculation (100ms frames)
  - Use percentile-based noise floor estimation (bottom 10% of frames)
  - Separate signal and noise power calculations
  - Update SNR formula to use power ratio instead of amplitude ratio
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 1.2 Validate SNR calculator fixes
  - Run `pytest tests/unit/test_snr_calculator.py -v`
  - Verify all 6 tests pass
  - Confirm clean signal returns SNR >40 dB
  - Confirm noisy signal returns SNR 0-20 dB
  - Confirm very noisy signal returns SNR <10 dB
  - _Requirements: 1.1, 1.2, 1.3_

- [-] 2. Fix Echo Detector False Positives and Delay Measurement
- [x] 2.1 Update detect_echo method with corrected autocorrelation
  - Add audio normalization to [-1, 1] range
  - Use scipy.signal.correlate for accurate autocorrelation
  - Normalize autocorrelation by zero-lag value
  - Increase false positive threshold from 0.01 to 0.3
  - Fix delay calculation: (delay_samples * 1000) / sample_rate
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [x] 2.2 Validate echo detector fixes
  - Run `pytest tests/unit/test_echo_detector.py -v`
  - Verify all 11 tests pass
  - Confirm clean signal has no echo (has_echo=False)
  - Confirm 100ms echo detected with 90-110ms delay
  - Confirm different delays measured accurately
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 3. Fix Silence Detector State Management
- [x] 3.1 Update detect_silence method with proper state tracking
  - Add last_timestamp instance variable
  - Properly initialize silence_start_time on first silent chunk
  - Maintain silence_start_time across calls until audio returns
  - Calculate duration as (current_timestamp - silence_start_time)
  - Reset silence_start_time when audio energy returns
  - Add reset() method to clear state
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3.2 Validate silence detector fixes
  - Run `pytest tests/unit/test_silence_detector.py -v`
  - Verify all 11 tests pass
  - Confirm 6 seconds of silence triggers is_silent=True
  - Confirm duration accumulates across multiple calls
  - Confirm state resets when audio returns
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 4. Fix Clipping Detector Threshold Logic
- [x] 4.1 Update detect_clipping method with corrected threshold logic
  - Add empty array handling (return 0% without exception)
  - Verify threshold calculation: max_amplitude * (threshold_percent / 100.0)
  - Use >= comparison for threshold check
  - Use np.abs() to catch both positive and negative clipping
  - Ensure clipped_count is returned as int
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 4.2 Validate clipping detector fixes
  - Run `pytest tests/unit/test_clipping_detector.py -v`
  - Verify all 10 tests pass
  - Confirm samples at threshold are counted as clipped
  - Confirm empty array returns 0% without error
  - Confirm percentage calculation is accurate
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 5. Fix Metrics Emitter Implementation
- [x] 5.1 Update emit_metrics method to actually call CloudWatch
  - Ensure metric_data array is properly constructed
  - Add timestamps to each metric
  - Verify put_metric_data is called with correct parameters
  - Add try-except for graceful error handling
  - Log errors without raising exceptions
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 5.2 Validate metrics emitter fixes
  - Run `pytest tests/integration/test_lambda_audio_quality_integration.py::TestLambdaAudioQualityIntegration::test_lambda_integration_metrics_emission -v`
  - Verify CloudWatch put_metric_data is called
  - Verify namespace is 'AudioQuality'
  - Verify MetricData contains SNR and ClippingPercentage
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 6. Fix Speaker Notifier WebSocket Integration
- [x] 6.1 Update notify_speaker method to actually send messages
  - Verify rate limiting logic doesn't prevent first message
  - Ensure send_message is called with correct parameters
  - Update notification_history AFTER successful send
  - Add try-except for graceful error handling
  - Add logging for sent notifications
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 6.2 Validate speaker notifier fixes
  - Run `pytest tests/unit/test_speaker_notifier.py -v`
  - Verify all 11 tests pass
  - Confirm messages are sent via WebSocket
  - Confirm rate limiting works correctly
  - Confirm notification format is correct
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 7. Fix QualityMetrics Field Name
- [x] 7.1 Add duration_s property to QualityMetrics
  - Add @property decorator for duration_s
  - Return silence_duration_s value
  - Maintain backward compatibility
  - _Requirements: 7.1, 7.2, 7.3_

- [x] 7.2 Validate QualityMetrics fixes
  - Run `pytest tests/integration/test_quality_validation_pipeline.py::TestQualityValidationPipeline::test_quality_validation_pipeline_metrics_structure -v`
  - Verify duration_s attribute is accessible
  - Verify no AttributeError is raised
  - _Requirements: 7.1, 7.2, 7.3_

- [x] 8. Run Full Test Suite
- [x] 8.1 Run all unit tests
  - Run `pytest tests/unit/ -v`
  - Verify >90% of unit tests pass
  - Document any remaining failures
  - _All requirements_

- [x] 8.2 Run all integration tests
  - Run `pytest tests/integration/ -v`
  - Verify >80% of integration tests pass
  - Document any remaining failures
  - _All requirements_

- [x] 8.3 Generate test coverage report
  - Run `pytest tests/ --cov=audio_quality --cov-report=html`
  - Verify coverage meets 80% threshold
  - Identify any uncovered code paths
  - _All requirements_

## Implementation Notes

### Testing Strategy

- Fix bugs in priority order (3, 4, 5, 1, 2, 6, 7)
- Run specific test file after each fix to validate
- Don't proceed to next bug until current tests pass
- Run full test suite at the end

### Validation Criteria

Each bug fix is considered complete when:
1. The specific unit tests for that component pass
2. No new test failures are introduced
3. The fix addresses the root cause identified in the design

### Rollback Plan

If a fix introduces new failures:
1. Revert the change
2. Re-analyze the root cause
3. Update the design document
4. Implement alternative solution
