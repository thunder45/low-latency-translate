# Implementation Plan

- [x] 1. Set up project structure and core data models
- [x] 1.1 Create audio_quality package directory structure
  - Create `audio_quality/` directory with `__init__.py`
  - Create subdirectories: `validators/`, `analyzers/`, `processors/`, `notifiers/`, `models/`
  - _Requirements: 6.1, 6.2_

- [x] 1.2 Implement core data models
  - Create `models/quality_config.py` with QualityConfig dataclass and validation method
  - Create `models/quality_metrics.py` with QualityMetrics dataclass
  - Create `models/audio_format.py` with AudioFormat dataclass and is_valid method
  - Create `models/quality_event.py` with QualityEvent dataclass and to_eventbridge_entry method
  - Create `models/results.py` with ClippingResult, EchoResult, SilenceResult dataclasses
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 2. Implement audio format validation
- [x] 2.1 Create AudioFormatValidator class
  - Implement `validators/format_validator.py` with AudioFormatValidator class
  - Implement validate method that checks sample rate, bit depth, and channel count
  - Return ValidationResult with success status and error details
  - _Requirements: 6.1, 6.2_

- [ ] 3. Implement SNR calculation
- [ ] 3.1 Create SNRCalculator class
  - Implement `analyzers/snr_calculator.py` with SNRCalculator class
  - Implement calculate_snr method using RMS-based algorithm
  - Maintain rolling window of SNR values (5 seconds)
  - Update measurements at 500ms intervals
  - _Requirements: 1.1, 1.2, 1.4, 1.5_

- [ ] 4. Implement clipping detection
- [ ] 4.1 Create ClippingDetector class
  - Implement `analyzers/clipping_detector.py` with ClippingDetector class
  - Implement detect_clipping method that identifies samples at 98% of max amplitude
  - Calculate clipping percentage in 100ms windows
  - Return ClippingResult with percentage and clipped sample count
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ] 5. Implement echo detection
- [ ] 5.1 Create EchoDetector class
  - Implement `analyzers/echo_detector.py` with EchoDetector class
  - Implement detect_echo method using autocorrelation algorithm
  - Search for echo patterns in 10-500ms delay range
  - Measure echo level in dB relative to primary signal
  - Include threshold check to avoid false positives
  - Optionally downsample to 8 kHz for faster computation
  - Verify delay accuracy with downsampling
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 6. Implement silence detection
- [ ] 6.1 Create SilenceDetector class
  - Implement `analyzers/silence_detector.py` with SilenceDetector class
  - Implement detect_silence method that tracks RMS energy
  - Detect extended silence (>5 seconds below -50 dB)
  - Differentiate between natural pauses and technical issues
  - Reset timer when audio energy returns
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 7. Implement quality metrics aggregation
- [ ] 7.1 Create AudioQualityAnalyzer class
  - **Depends on**: Tasks 3, 4, 5, 6 (all analyzer components)
  - Implement `analyzers/quality_analyzer.py` with AudioQualityAnalyzer class
  - Initialize all detector components (SNR, clipping, echo, silence)
  - Implement analyze method that runs all detectors and returns QualityMetrics
  - Aggregate results from all detectors into single QualityMetrics object
  - _Requirements: 1.1, 2.1, 3.1, 8.1_

- [ ] 8. Implement metrics emission
- [ ] 8.1 Create QualityMetricsEmitter class
  - Implement `notifiers/metrics_emitter.py` with QualityMetricsEmitter class
  - Implement emit_metrics method to publish to CloudWatch
  - Implement emit_quality_event method to publish to EventBridge
  - Implement metric batching to reduce API calls (batch size: 20, flush interval: 5s)
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 9. Implement speaker notifications
- [ ] 9.1 Create SpeakerNotifier class
  - Implement `notifiers/speaker_notifier.py` with SpeakerNotifier class
  - Implement notify_speaker method to send warnings via WebSocket
  - Implement rate limiting (1 notification per issue type per 60 seconds)
  - Implement _format_warning method with user-friendly messages and remediation steps
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 10. Implement optional audio processing
- [ ] 10.1 Create AudioProcessor class
  - Implement `processors/audio_processor.py` with AudioProcessor class
  - Implement process method that applies optional enhancements
  - Implement _apply_high_pass method using scipy.signal.butter filter (80 Hz cutoff)
  - Implement _apply_noise_gate method with -40 dB threshold
  - _Requirements: 3.5_

- [ ] 11. Integrate with Lambda function
- [ ] 11.1 Update audio processor Lambda handler
  - Import audio quality components in existing Lambda function
  - Initialize AudioQualityAnalyzer with configuration from environment variables
  - Add quality analysis step before transcription
  - Emit metrics to CloudWatch after analysis
  - Send speaker notifications for threshold violations
  - _Requirements: 6.3, 6.4_

- [ ] 11.2 Add configuration loading
  - Implement load_config_from_env function to read environment variables
  - Validate configuration parameters on Lambda initialization
  - Handle configuration errors gracefully
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 12. Add error handling and graceful degradation
- [ ] 12.1 Implement error handling
  - Create custom exceptions: AudioFormatError, QualityAnalysisError
  - Implement analyze_with_fallback function for graceful degradation
  - Add try-catch blocks in Lambda handler
  - Return default metrics if analysis fails
  - _Requirements: 6.3_

- [ ] 13. Add monitoring and observability
- [ ] 13.1 Add structured logging
  - Implement log_quality_metrics function with JSON structured logging
  - Add logging statements for key operations
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 13.2 Add X-Ray tracing
  - Add X-Ray decorators to analyze_audio_quality function
  - Add subsegments for each detector (SNR, clipping, echo, silence)
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 14. Create infrastructure configuration
- [ ] 14.1 Add Lambda environment variables
  - Define environment variables in IaC (Terraform/CloudFormation)
  - Set default values for quality thresholds
  - Configure CloudWatch and EventBridge integration flags
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 14.2 Create CloudWatch dashboard
  - Define dashboard JSON with widgets for SNR, clipping, echo, silence
  - Add processing latency histogram
  - _Requirements: 5.1, 5.2_

- [ ] 14.3 Create CloudWatch alarms
  - Create alarm for low SNR (threshold: 15 dB, 2 evaluation periods)
  - Create alarm for high clipping (threshold: 5%, 3 evaluation periods)
  - Configure SNS topic for alarm notifications
  - _Requirements: 5.3_

- [ ]* 15. Write unit tests
- [ ]* 15.1 Write SNR calculator tests
  - Test SNR calculation with clean signal (expected: >40 dB)
  - Test SNR calculation with noisy signal (expected: 0-20 dB)
  - _Requirements: 1.1, 1.2_

- [ ]* 15.2 Write clipping detector tests
  - Test clipping detection with clipped signal
  - Verify clipped sample count and percentage calculation
  - _Requirements: 2.1, 2.2, 2.3_

- [ ]* 15.3 Write echo detector tests
  - Test echo detection with signal containing 100ms echo
  - Verify echo delay measurement accuracy
  - Test edge case with zero autocorrelation values
  - _Requirements: 3.1, 3.2, 3.3_

- [ ]* 15.4 Write silence detector tests
  - Test silence detection with extended silence (>5 seconds)
  - Test differentiation between speech pauses and technical issues
  - Verify silence duration tracking
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ]* 15.5 Write configuration validation tests
  - Test rejection of invalid SNR thresholds (<10 dB or >40 dB)
  - Test rejection of invalid clipping thresholds (>10%)
  - Test acceptance of valid configuration
  - _Requirements: 4.3, 4.4, 4.5_

- [ ]* 15.6 Write speaker notifier tests
  - Test notification message sending via WebSocket
  - Test rate limiting effectiveness (1 per minute per issue type)
  - Verify notification format and content
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ]* 16. Write integration tests
- [ ]* 16.1 Write quality validation pipeline test
  - Load test audio file with known quality issues
  - Run complete analysis pipeline
  - Verify all metrics are calculated correctly
  - Verify quality issues are detected
  - _Requirements: 1.1, 2.1, 3.1, 8.1_

- [ ]* 16.2 Write Lambda integration test
  - Mock WebSocket and AWS clients
  - Send audio chunk through Lambda handler
  - Verify quality analysis runs
  - Verify metrics are emitted
  - Verify speaker notifications are sent
  - _Requirements: 6.3, 6.4, 6.5_

- [ ]* 17. Write performance tests
- [ ]* 17.1 Write processing overhead test (analysis only)
  - Generate 1-second audio chunks
  - Measure analysis time over 100 iterations
  - Verify overhead stays below 5% of real-time duration
  - _Requirements: 6.5_

- [ ]* 17.2 Write concurrent stream processing test
  - Create 50 AudioQualityAnalyzer instances
  - Process 50 audio chunks concurrently
  - Verify all streams complete in under 1 second
  - _Requirements: 6.4_

- [ ]* 17.3 Write processing overhead test with enhancements
  - Enable high-pass filter and noise gate in AudioProcessor
  - Generate 1-second audio chunks
  - Measure total processing time (analysis + enhancements)
  - Verify overhead stays below 5% including optional processing
  - _Requirements: 3.5, 6.5_
