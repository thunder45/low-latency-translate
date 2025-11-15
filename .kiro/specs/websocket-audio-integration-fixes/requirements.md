# WebSocket Audio Integration Fixes Requirements

## Introduction

This specification addresses the integration gaps and issues identified in the comprehensive code review of the WebSocket Audio Integration implementation. While the core infrastructure is exceptionally well-built (85-90% complete), there are critical integration points and test coverage issues that prevent the system from functioning end-to-end.

The review identified four categories of issues:
1. **Critical Priority**: Blocks all functionality (import errors, missing integrations, infrastructure gaps)
2. **High Priority**: Improves reliability (emotion detection integration, test coverage)
3. **Medium Priority**: Production readiness (cross-module dependencies, standardization)
4. **Test Quality**: Coverage and execution issues

This spec provides a systematic approach to resolving all identified issues and achieving production readiness.

## Glossary

- **System**: The WebSocket Audio Integration Fixes component
- **Structured Logger**: Logging utility requiring factory function implementation
- **Translation Pipeline Client**: Lambda client for forwarding transcriptions to translation service
- **Transcribe Streaming Integration**: AWS Transcribe Streaming API connection and event processing
- **sendAudio Route**: WebSocket route for receiving audio chunks from speakers
- **Emotion Detection**: Audio dynamics extraction for preserving speaker emotion
- **Test Coverage**: Percentage of code exercised by automated tests
- **Cross-Module Dependencies**: Shared configurations and utilities across components
- **Lambda Layer**: Shared code package deployed across multiple Lambda functions
- **Import Error**: Python module import failure preventing code execution
- **Factory Function**: Function that creates and returns instances of a class
- **Protocol**: Python typing construct defining interface contracts
- **Integration Gap**: Missing connection between implemented components

## Requirements

### Requirement 1: Fix Structured Logger Import Error

**User Story:** As a developer, I want the structured logger to be importable, so that all Lambda handlers can execute without import errors

#### Acceptance Criteria

1. WHEN THE System imports get_structured_logger from shared.utils.structured_logger, THE System SHALL successfully import the factory function
2. WHEN THE factory function is called with a component name, THE System SHALL return a StructuredLogger instance
3. WHEN THE StructuredLogger instance is created, THE System SHALL configure it with the provided component name and optional parameters
4. WHEN THE tests import the structured logger, THE System SHALL execute without ImportError exceptions
5. WHEN THE factory function is implemented, THE System SHALL maintain backward compatibility with existing StructuredLogger usage

### Requirement 2: Implement Translation Pipeline Lambda Client

**User Story:** As a system operator, I want transcriptions to be forwarded to the Translation Pipeline, so that the end-to-end audio-to-translation flow is complete

#### Acceptance Criteria

1. WHEN THE System receives a transcription result from Transcribe, THE System SHALL forward it to the Translation Pipeline Lambda via boto3 Lambda client
2. WHEN THE Lambda client invokes the Translation Pipeline, THE System SHALL use InvocationType='Event' for asynchronous invocation
3. WHEN THE payload is constructed, THE System SHALL include sessionId, sourceLanguage, transcriptText, isPartial, stabilityScore, timestamp, and emotionDynamics
4. WHEN THE invocation fails, THE System SHALL retry up to 2 times with 100ms delay between attempts
5. WHEN THE Translation Pipeline is unavailable after retries, THE System SHALL log the failure and continue processing subsequent transcriptions

### Requirement 3: Complete Transcribe Streaming Integration

**User Story:** As a speaker, I want my audio to be transcribed in real-time, so that listeners receive translated content with minimal latency

#### Acceptance Criteria

1. WHEN THE first audio chunk arrives for a session, THE System SHALL initialize an AWS Transcribe Streaming API connection using amazon-transcribe-streaming-sdk
2. WHEN THE Transcribe stream is initialized, THE System SHALL configure it with sourceLanguage, media encoding PCM, sample rate 16000 Hz, and partial results enabled
3. WHEN THE audio chunks are received, THE System SHALL send them to the active Transcribe stream via the stream handler
4. WHEN THE Transcribe stream emits TranscriptEvent, THE System SHALL process the event in an asynchronous event loop
5. WHEN THE transcription results are extracted, THE System SHALL forward them to the Translation Pipeline via LambdaTranslationPipeline client

### Requirement 4: Add sendAudio Route to CDK Configuration

**User Story:** As a system administrator, I want the sendAudio route to be configured in API Gateway, so that audio chunks can reach the audio_processor Lambda

#### Acceptance Criteria

1. THE System SHALL configure a custom route named sendAudio in the API Gateway WebSocket API CDK stack
2. WHEN THE route is configured, THE System SHALL map it to the audio_processor Lambda function integration
3. WHEN THE integration is created, THE System SHALL set the integration timeout to 60 seconds
4. WHEN THE route is deployed, THE System SHALL configure binary WebSocket frame support with content handling CONVERT_TO_BINARY
5. WHEN THE CDK stack is synthesized, THE System SHALL include the sendAudio route in the CloudFormation template

### Requirement 5: Integrate Emotion Detection with Audio Processing

**User Story:** As a speaker, I want my emotional expression to be preserved in translations, so that listeners receive natural-sounding audio

#### Acceptance Criteria

1. WHEN THE audio_processor receives audio chunks, THE System SHALL extract emotion dynamics using EmotionDynamicsOrchestrator
2. WHEN THE emotion dynamics are extracted, THE System SHALL include volume level, speaking rate, and energy metrics
3. WHEN THE transcription is forwarded to Translation Pipeline, THE System SHALL include the emotion dynamics in the payload
4. WHEN THE emotion detection fails, THE System SHALL log the error and continue with default neutral emotion values
5. WHEN THE emotion detection is integrated, THE System SHALL emit CloudWatch metrics for emotion extraction latency

### Requirement 6: Fix Test Coverage and Import Errors

**User Story:** As a developer, I want all tests to pass with adequate coverage, so that the codebase is reliable and maintainable

#### Acceptance Criteria

1. WHEN THE tests are executed, THE System SHALL achieve minimum 80% code coverage across all components
2. WHEN THE session-management tests are run, THE System SHALL execute without import errors
3. WHEN THE audio-transcription tests are run, THE System SHALL execute without import errors
4. WHEN THE new unit tests are added, THE System SHALL cover WebSocket services, validators, and handlers
5. WHEN THE test suite completes, THE System SHALL report zero import failures and zero test failures

### Requirement 7: Synchronize Cross-Module Dependencies

**User Story:** As a system operator, I want consistent configurations across modules, so that the system operates reliably

#### Acceptance Criteria

1. WHEN THE DynamoDB table names are referenced, THE System SHALL use consistent names across session-management and audio-transcription modules
2. WHEN THE error codes are defined, THE System SHALL use standardized error codes across all Lambda handlers
3. WHEN THE message formats are defined, THE System SHALL use consistent JSON schemas across all WebSocket messages
4. WHEN THE environment variables are configured, THE System SHALL use consistent naming conventions across all Lambda functions
5. WHEN THE shared utilities are needed, THE System SHALL use a common Lambda layer for shared code

### Requirement 8: Create Shared Lambda Layer

**User Story:** As a developer, I want shared utilities in a Lambda layer, so that code is not duplicated across functions

#### Acceptance Criteria

1. THE System SHALL create a Lambda layer containing shared utilities (structured_logger, metrics_emitter, validators)
2. WHEN THE Lambda layer is created, THE System SHALL include it in the CDK stack configuration
3. WHEN THE Lambda functions are deployed, THE System SHALL attach the shared layer to all functions that need it
4. WHEN THE layer is updated, THE System SHALL version it appropriately to prevent breaking changes
5. WHEN THE layer is deployed, THE System SHALL verify that all Lambda functions can import from it successfully

### Requirement 9: Add End-to-End Integration Tests

**User Story:** As a developer, I want comprehensive integration tests, so that the complete audio-to-translation flow is validated

#### Acceptance Criteria

1. WHEN THE integration tests are executed, THE System SHALL test the complete flow from audio reception to translation forwarding
2. WHEN THE audio chunks are sent via WebSocket, THE System SHALL verify they reach the audio_processor Lambda
3. WHEN THE Transcribe stream is initialized, THE System SHALL verify transcription events are processed
4. WHEN THE transcriptions are generated, THE System SHALL verify they are forwarded to the Translation Pipeline
5. WHEN THE integration tests complete, THE System SHALL verify no audio loss, no duplication, and latency <5 seconds

### Requirement 10: Standardize Error Codes and Messages

**User Story:** As a developer, I want standardized error codes, so that error handling is consistent across the system

#### Acceptance Criteria

1. THE System SHALL define a centralized error code enumeration in shared utilities
2. WHEN THE errors occur, THE System SHALL use error codes from the centralized enumeration
3. WHEN THE error responses are returned, THE System SHALL include error code, message, and details in consistent format
4. WHEN THE errors are logged, THE System SHALL include error code and correlation IDs
5. WHEN THE error codes are documented, THE System SHALL maintain a reference document listing all codes and meanings

### Requirement 11: Add Unit Tests for New Components

**User Story:** As a developer, I want unit tests for all new components, so that code quality is maintained

#### Acceptance Criteria

1. WHEN THE LambdaTranslationPipeline is implemented, THE System SHALL include unit tests covering success and failure scenarios
2. WHEN THE TranscribeStreamHandler is completed, THE System SHALL include unit tests for stream initialization, event processing, and error handling
3. WHEN THE emotion detection integration is added, THE System SHALL include unit tests for emotion extraction and error cases
4. WHEN THE factory function is implemented, THE System SHALL include unit tests verifying correct instance creation
5. WHEN THE unit tests are executed, THE System SHALL achieve 100% coverage for new components

### Requirement 12: Verify CDK Infrastructure Deployment

**User Story:** As a system administrator, I want to verify infrastructure is correctly deployed, so that the system is production-ready

#### Acceptance Criteria

1. WHEN THE CDK stack is deployed, THE System SHALL verify all Lambda functions are created with correct configurations
2. WHEN THE WebSocket routes are deployed, THE System SHALL verify all 10 routes (including sendAudio) are configured
3. WHEN THE IAM permissions are deployed, THE System SHALL verify all Lambda functions have required permissions
4. WHEN THE CloudWatch resources are deployed, THE System SHALL verify log groups, metrics, and alarms are created
5. WHEN THE EventBridge rule is deployed, THE System SHALL verify it triggers the session_status_handler Lambda every 30 seconds

### Requirement 13: Document Integration Points

**User Story:** As a developer, I want clear documentation of integration points, so that the system is maintainable

#### Acceptance Criteria

1. WHEN THE integration fixes are complete, THE System SHALL document the audio_processor to Transcribe integration
2. WHEN THE documentation is created, THE System SHALL document the Transcribe to Translation Pipeline integration
3. WHEN THE integration points are documented, THE System SHALL include sequence diagrams showing message flow
4. WHEN THE error handling is documented, THE System SHALL include retry logic and circuit breaker patterns
5. WHEN THE documentation is complete, THE System SHALL include troubleshooting guides for common integration issues

### Requirement 14: Performance Validation

**User Story:** As a system operator, I want to validate performance targets are met, so that the system meets latency requirements

#### Acceptance Criteria

1. WHEN THE audio processing is tested, THE System SHALL achieve p95 latency <50ms from WebSocket receipt to Transcribe stream send
2. WHEN THE transcription forwarding is tested, THE System SHALL achieve p95 latency <100ms from Transcribe event to Translation Pipeline invocation
3. WHEN THE end-to-end flow is tested, THE System SHALL achieve p95 latency <5 seconds from audio input to translation output
4. WHEN THE control messages are tested, THE System SHALL achieve p95 latency <100ms from receipt to acknowledgment
5. WHEN THE performance targets are not met, THE System SHALL emit CloudWatch alarms and log performance metrics

### Requirement 15: Security Validation

**User Story:** As a security administrator, I want to validate security controls are properly implemented, so that the system is secure

#### Acceptance Criteria

1. WHEN THE role validation is tested, THE System SHALL verify speakers cannot perform listener actions and vice versa
2. WHEN THE rate limiting is tested, THE System SHALL verify audio spam is prevented
3. WHEN THE message size validation is tested, THE System SHALL verify oversized messages are rejected
4. WHEN THE connection timeout is tested, THE System SHALL verify idle connections are cleaned up
5. WHEN THE security validation is complete, THE System SHALL document all security controls and their test results

