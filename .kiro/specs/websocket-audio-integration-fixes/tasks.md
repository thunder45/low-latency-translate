# WebSocket Audio Integration Fixes - Implementation Plan

## Overview

This implementation plan systematically addresses all issues identified in the comprehensive code review. The plan is organized by priority: Critical (blocks functionality) → High (improves reliability) → Medium (production readiness).

**Estimated Timeline**: 5-7 days
**Risk Level**: LOW - Fixes are straightforward with excellent foundation in place

## Task List

### Phase 1: Critical Priority Fixes (Day 1)

- [x] 1. Fix structured logger import error
  - Add `get_structured_logger()` factory function to structured_logger.py
  - Verify function signature matches all import statements
  - Test with all Lambda handlers that import it
  - Run session-management tests to verify import errors resolved
  - _Requirements: 1_
  - _Estimated Time: 1 hour_

- [x] 1.1 Implement factory function
  - Add `get_structured_logger()` function to `session-management/shared/utils/structured_logger.py`
  - Accept component name and optional parameters (correlation_id, session_id, connection_id)
  - Return configured StructuredLogger instance
  - Add comprehensive docstring with examples
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 1.2 Add unit tests for factory function
  - Test basic instance creation with component name
  - Test with optional correlation_id parameter
  - Test with optional session_id parameter
  - Test with optional connection_id parameter
  - Test with multiple optional parameters
  - Verify backward compatibility with existing StructuredLogger usage
  - _Requirements: 1.4, 1.5_

- [x] 1.3 Verify import error resolution
  - Run `pytest session-management/tests/` to verify no import errors
  - Check all Lambda handlers import successfully
  - Verify connection_handler, session_status_handler, timeout_handler all work
  - Document resolution in task summary
  - _Requirements: 1.4_

### Phase 2: Translation Pipeline Integration (Days 2-3)

- [x] 2. Implement Lambda Translation Pipeline client
  - Create `audio-transcription/shared/services/lambda_translation_pipeline.py`
  - Implement LambdaTranslationPipeline class with Protocol interface
  - Add retry logic with exponential backoff (2 retries, 100ms delay)
  - Include emotion dynamics in payload
  - Handle errors gracefully without blocking audio processing
  - _Requirements: 2_
  - _Estimated Time: 4-6 hours_

- [x] 2.1 Create LambdaTranslationPipeline class
  - Initialize with function_name and optional lambda_client (for testing)
  - Implement `process()` method accepting text, session_id, source_language, etc.
  - Use InvocationType='Event' for asynchronous invocation
  - Construct payload with all required fields including emotionDynamics
  - Add `_get_default_emotion()` method for fallback emotion values
  - Return boolean indicating success/failure
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 2.2 Add retry logic and error handling
  - Implement retry loop with max 2 retries
  - Add 100ms delay between retry attempts
  - Handle ClientError exceptions from boto3
  - Log failures with session_id and error details
  - Return False on failure but don't raise exceptions
  - _Requirements: 2.4, 2.5_

- [x] 2.3 Add unit tests for Translation Pipeline client
  - Test successful invocation with mock Lambda client
  - Test retry logic with transient failures
  - Test failure after max retries
  - Test payload construction with all required fields
  - Test default emotion values when not provided
  - Test emotion data retrieval from cache
  - Verify asynchronous invocation (InvocationType='Event')
  - Verify correct payload format matches Translation Pipeline expectations
  - _Requirements: 11.1_

- [x] 2.4 Integrate with audio_processor handler
  - Import LambdaTranslationPipeline in audio_processor/handler.py
  - Initialize at module level with TRANSLATION_PIPELINE_FUNCTION_NAME env var
  - Pass to TranscribeStreamHandler constructor
  - Update environment variables in CDK stack
  - _Requirements: 2.3_

### Phase 3: Transcribe Streaming Integration (Days 2-3)

- [x] 3. Complete Transcribe streaming integration
  - Remove all TODO comments from audio_processor/handler.py
  - Implement TranscribeStreamHandler initialization
  - Implement event loop for processing Transcribe events
  - Forward transcriptions to Translation Pipeline
  - Handle stream lifecycle (init, reconnect, close)
  - _Requirements: 3_
  - _Estimated Time: 1-2 days_

- [x] 3.1 Implement TranscribeStreamHandler initialization
  - Add `initialize_stream()` async method
  - Create TranscribeStreamingClient with region configuration
  - Configure stream with sourceLanguage, media encoding PCM, sample rate 16000 Hz
  - Enable partial results with stability scores
  - Start event loop task in background
  - Set is_active flag to True
  - _Requirements: 3.1, 3.2_

- [x] 3.2 Implement send_audio_chunk method
  - Validate stream is initialized and active
  - Add audio chunk to buffer if stream backpressured
  - Send buffered chunks to Transcribe stream
  - Handle buffer overflow by dropping oldest chunks
  - Emit CloudWatch metrics for buffer operations
  - _Requirements: 3.3_

- [x] 3.3 Implement event loop processing
  - Create `_process_events()` async method
  - Iterate over stream.output_stream events
  - Handle TranscriptEvent instances
  - Extract transcript text, is_partial flag, stability_score
  - Forward to Translation Pipeline via LambdaTranslationPipeline
  - Handle errors and attempt reconnection
  - _Requirements: 3.4_

- [x] 3.4 Implement transcript event handling
  - Create `_handle_transcript_event()` async method
  - Extract alternatives from transcript results
  - Get transcript text and stability score
  - Retrieve cached emotion data for session
  - Call translation_pipeline.process() with all data
  - Log successful forwarding at DEBUG level
  - _Requirements: 3.5_

- [x] 3.5 Implement stream lifecycle management
  - Add `close_stream()` async method
  - Cancel event loop task gracefully
  - End Transcribe input stream
  - Clear audio buffer
  - Set is_active flag to False
  - _Requirements: 3.5_

- [x] 3.6 Add module-level handler management
  - Create dictionary to store TranscribeStreamHandler instances by session_id
  - Implement `get_or_create_transcribe_handler()` function
  - Initialize handler with session_id, source_language, translation_pipeline
  - Reuse existing handler for same session
  - Clean up handlers on session end
  - _Requirements: 3.5_

- [x] 3.7 Add unit tests for Transcribe integration
  - Test stream initialization success and failure
  - Test send_audio_chunk with valid stream
  - Test send_audio_chunk with inactive stream (should raise error)
  - Test event loop processing with mock events
  - Test transcript event handling and forwarding
  - Test stream close and cleanup
  - _Requirements: 11.2_

### Phase 4: Infrastructure Fix (Day 2)

- [x] 4. Add sendAudio route to CDK configuration
  - Update `session-management/infrastructure/stacks/session_management_stack.py`
  - Add sendAudio route configuration to WebSocket API
  - Map route to audio_processor Lambda integration
  - Configure binary frame support with CONVERT_TO_BINARY
  - Set integration timeout to 60 seconds
  - _Requirements: 4_
  - _Estimated Time: 2 hours_

- [x] 4.1 Create cross-stack reference
  - Import AudioTranscriptionStack in session_management_stack.py
  - Accept audio_transcription_stack parameter in constructor
  - Reference audio_processor_function from audio_transcription_stack
  - Store reference as instance variable
  - _Requirements: 4.1, 4.2_

- [x] 4.2 Add sendAudio route configuration
  - Create Lambda integration for audio_processor function
  - Create CfnRoute with route_key="sendAudio"
  - Set target to integration reference
  - Configure content_handling_strategy="CONVERT_TO_BINARY"
  - Set timeout_in_millis=60000
  - _Requirements: 4.3, 4.4_

- [x] 4.3 Update CDK app to pass stack references
  - Modify infrastructure/app.py to create stacks in correct order
  - Create AudioTranscriptionStack first
  - Pass audio_transcription_stack to SessionManagementStack constructor
  - Verify CDK synth generates correct CloudFormation
  - _Requirements: 4.5_

- [x] 4.4 Verify route deployment
  - Deploy CDK stack to dev environment
  - Verify sendAudio route appears in API Gateway console
  - Test route with sample WebSocket message
  - Verify audio_processor Lambda is invoked
  - _Requirements: 12.2_

### Phase 5: Emotion Detection Integration (Day 4)

- [x] 5. Integrate emotion detection with audio processing
  - Import EmotionDynamicsOrchestrator in audio_processor/handler.py
  - Initialize orchestrator at module level
  - Extract emotion dynamics from audio chunks
  - Cache emotion data for correlation with transcripts
  - Include emotion data in Translation Pipeline payload
  - _Requirements: 5_
  - _Estimated Time: 4-6 hours_

- [x] 5.1 Initialize emotion orchestrator
  - Import EmotionDynamicsOrchestrator from emotion_dynamics module
  - Create module-level instance
  - Create emotion_cache dictionary for storing emotion data by session_id
  - Add ENABLE_EMOTION_DETECTION environment variable check
  - _Requirements: 5.1_

- [x] 5.2 Implement emotion extraction
  - Create `process_audio_chunk_with_emotion()` async function
  - Convert audio bytes to numpy array
  - Call emotion_orchestrator.process_audio_chunk() with audio array and sample rate
  - Extract volume, speaking_rate, energy from result
  - Cache emotion data with session_id and timestamp
  - _Requirements: 5.2_

- [x] 5.3 Handle emotion extraction errors
  - Wrap emotion extraction in try-except block
  - Log errors at ERROR level with session_id
  - Use default neutral emotion values on failure (volume=0.5, rate=1.0, energy=0.5)
  - Continue audio processing even if emotion extraction fails
  - Emit CloudWatch metric for emotion extraction failures
  - _Requirements: 5.4_

- [x] 5.4 Update TranscribeStreamHandler to use emotion data
  - Pass emotion_orchestrator to TranscribeStreamHandler constructor
  - Add method to retrieve cached emotion data for session
  - Include emotion data when forwarding to Translation Pipeline
  - Clear emotion cache on session end
  - _Requirements: 5.3_

- [x] 5.5 Add unit tests for emotion integration
  - Test emotion extraction with valid audio data
  - Test emotion caching by session_id
  - Test error handling with invalid audio data
  - Test default emotion values on extraction failure
  - Test emotion data included in Translation Pipeline payload
  - _Requirements: 11.3_

- [x] 5.6 Add CloudWatch metrics for emotion detection
  - Emit EmotionExtractionLatency metric (milliseconds)
  - Emit EmotionExtractionErrors metric (count)
  - Emit EmotionCacheSize metric (count)
  - Add metrics to audio processing dashboard
  - _Requirements: 5.5_

### Phase 6: Test Coverage Improvements (Day 5)

- [ ] 6. Improve test coverage to 80%+
  - Add unit tests for all new components
  - Add integration tests for end-to-end flow
  - Fix any remaining test failures
  - Verify coverage meets 80% requirement
  - _Requirements: 6_
  - _Estimated Time: 1 day_

- [ ] 6.1 Add unit tests for WebSocket services
  - Test WebSocketParser with various message formats
  - Test ConnectionValidator with valid and invalid connections
  - Test AudioRateLimiter with various chunk rates
  - Test AudioFormatValidator with valid and invalid formats
  - Test AudioBuffer with overflow scenarios
  - _Requirements: 6.4_

- [ ] 6.2 Add unit tests for validators
  - Test validate_message_size with various sizes
  - Test validate_audio_chunk_size with edge cases
  - Test validate_control_message_size with large payloads
  - Test all validation error messages
  - _Requirements: 6.4_

- [ ] 6.3 Add unit tests for handlers
  - Test connection_handler with all control actions
  - Test session_status_handler with various listener counts
  - Test timeout_handler with idle connections
  - Test error handling in all handlers
  - _Requirements: 6.4_

- [ ] 6.4 Add integration tests for E2E flow
  - Create `test_e2e_audio_flow.py` in audio-transcription/tests/integration/
  - Test complete flow: audio → Transcribe → Translation Pipeline
  - Mock DynamoDB, Lambda, and Transcribe services
  - Test Translation Pipeline invocation with correct payload structure
  - Verify sessionId, sourceLanguage, transcriptText, emotionDynamics in payload
  - Verify no audio loss or duplication
  - Verify emotion data included in payload
  - Verify latency <5 seconds
  - _Requirements: 9_

- [ ] 6.5 Run full test suite and verify coverage
  - Run `pytest session-management/tests/ --cov=session-management --cov-report=html`
  - Run `pytest audio-transcription/tests/ --cov=audio-transcription --cov-report=html`
  - Verify coverage >80% for both components
  - Fix any failing tests
  - Document coverage results in task summary
  - _Requirements: 6.1, 6.2, 6.3, 6.5_

### Phase 7: Cross-Module Synchronization (Day 6)

- [ ] 7. Synchronize cross-module dependencies
  - Standardize DynamoDB table names across modules
  - Standardize error codes and message formats
  - Create shared Lambda layer for common utilities
  - Update environment variables for consistency
  - _Requirements: 7, 8_
  - _Estimated Time: 0.5 day_

- [ ] 7.1 Standardize DynamoDB table names
  - Create `shared/config/table_names.py` with constants
  - Update session-management to use constants
  - Update audio-transcription to use constants
  - Verify all references use consistent names
  - _Requirements: 7.1_

- [ ] 7.2 Standardize error codes
  - Create `shared/utils/error_codes.py` with enumeration
  - Define all error codes (INVALID_AUDIO_FORMAT, MESSAGE_TOO_LARGE, etc.)
  - Update all Lambda handlers to use error code constants
  - Update error response formatting for consistency
  - Document all error codes in reference document
  - _Requirements: 10_

- [ ] 7.3 Standardize message formats
  - Create `shared/models/websocket_messages.py` with message schemas
  - Define schemas for all WebSocket message types
  - Add validation functions for each message type
  - Update handlers to use schema validation
  - _Requirements: 7.3_

- [ ] 7.4 Create shared Lambda layer
  - Create `shared-layer/` directory structure
  - Move structured_logger, metrics_emitter, validators to layer
  - Create layer deployment package
  - Add layer to CDK stack configuration
  - Attach layer to all Lambda functions
  - _Requirements: 8_

- [ ] 7.5 Update Lambda functions to use layer
  - Remove duplicated utilities from Lambda function directories
  - Update imports to reference layer modules
  - Test all Lambda functions with layer attached
  - Verify no import errors
  - _Requirements: 8.3, 8.5_

- [ ] 7.6 Standardize environment variables
  - Create environment variable naming convention document
  - Update all Lambda functions to use consistent names
  - Update CDK stack to set environment variables consistently
  - Verify all functions have required environment variables
  - _Requirements: 7.4_

### Phase 8: Documentation and Validation (Day 7)

- [ ] 8. Update documentation and validate deployment
  - Document all integration points
  - Create troubleshooting guide
  - Validate performance targets
  - Validate security controls
  - Create deployment checklist
  - _Requirements: 13, 14, 15_
  - _Estimated Time: 0.5 day_

- [ ] 8.1 Document integration points
  - Document audio_processor → Transcribe integration
  - Document Transcribe → Translation Pipeline integration
  - Create sequence diagrams for message flow
  - Document error handling and retry logic
  - Document emotion detection integration
  - _Requirements: 13.1, 13.2, 13.3, 13.4_

- [ ] 8.2 Create troubleshooting guide
  - Document common integration issues and solutions
  - Document how to debug Transcribe stream failures
  - Document how to debug Translation Pipeline invocation failures
  - Document how to debug emotion detection issues
  - Include CloudWatch Logs Insights queries for debugging
  - _Requirements: 13.5_

- [ ] 8.3 Validate performance targets
  - Test audio processing latency (target: p95 <50ms)
  - Test transcription forwarding latency (target: p95 <100ms)
  - Test end-to-end latency (target: p95 <5 seconds)
  - Test control message latency (target: p95 <100ms)
  - Document performance test results
  - _Requirements: 14_

- [ ] 8.4 Validate security controls
  - Test role validation (speakers vs listeners)
  - Test rate limiting for audio chunks
  - Test message size validation
  - Test connection timeout handling
  - Document security validation results
  - _Requirements: 15_

- [ ] 8.5 Create deployment checklist
  - List all CDK stacks to deploy
  - List all environment variables to configure
  - List all IAM permissions to verify
  - List all CloudWatch alarms to enable
  - List all smoke tests to run post-deployment
  - _Requirements: 12_

### Phase 9: Deployment and Verification (Day 7)

- [ ] 9. Deploy to staging and verify
  - Deploy all CDK stacks to staging environment
  - Run smoke tests
  - Monitor CloudWatch metrics for 24 hours
  - Fix any issues discovered
  - Prepare for production deployment
  - _Requirements: 12_
  - _Estimated Time: 0.5 day_

- [ ] 9.1 Deploy CDK stacks to staging
  - Deploy audio-transcription stack
  - Deploy session-management stack
  - Deploy shared Lambda layer
  - Verify all resources created successfully
  - _Requirements: 12.1, 12.2_

- [ ] 9.2 Run smoke tests
  - Test speaker connection and session creation
  - Test audio chunk sending via sendAudio route
  - Test Transcribe stream initialization
  - Test transcription forwarding to Translation Pipeline
  - Test emotion data inclusion
  - Test control messages (pause, resume, mute)
  - Test session status queries
  - _Requirements: 12.3_

- [ ] 9.3 Monitor CloudWatch metrics
  - Check AudioChunksReceived metric
  - Check AudioProcessingLatency metric
  - Check TranscribeStreamInitLatency metric
  - Check TranscriptionForwardingLatency metric
  - Check EmotionExtractionLatency metric
  - Check error metrics (LambdaErrors, TranscribeErrors)
  - _Requirements: 12.4_

- [ ] 9.4 Verify CloudWatch alarms
  - Verify critical alarms are enabled
  - Verify warning alarms are enabled
  - Test alarm triggering with simulated failures
  - Verify alarm notifications reach on-call
  - _Requirements: 12.4_

- [ ] 9.5 Document deployment results
  - Document any issues encountered during deployment
  - Document resolutions for issues
  - Document performance metrics observed
  - Document any configuration changes made
  - Create deployment summary document
  - _Requirements: 13_

## Notes

### Priority Rationale

**Critical First**: Import errors and missing integrations block all functionality. These must be fixed before anything else works.

**High Priority Second**: Emotion detection and test coverage improve reliability and maintainability but don't block basic functionality.

**Medium Priority Third**: Cross-module synchronization and shared layers improve production readiness but system works without them.

### Testing Strategy

- **Unit tests**: Required for all new components (factory function, Translation Pipeline client, Transcribe handler, emotion integration)
- **Integration tests**: Required for end-to-end flow validation
- **Coverage target**: 80% minimum across all components
- **Test execution**: Run after each phase to catch issues early

### Deployment Strategy

1. **Dev environment**: Deploy after each phase for incremental testing
2. **Staging environment**: Deploy complete solution for 24-hour monitoring
3. **Production environment**: Deploy after staging validation with canary rollout

### Success Criteria

**Phase 1 Complete**:
- ✅ All tests run without import errors
- ✅ All Lambda handlers can be imported successfully

**Phase 2-3 Complete**:
- ✅ Audio chunks reach Transcribe via sendAudio route
- ✅ Transcriptions forwarded to Translation Pipeline
- ✅ End-to-end flow works

**Phase 5 Complete**:
- ✅ Emotion data extracted from audio
- ✅ Emotion data included in translations

**Phase 6 Complete**:
- ✅ Test coverage >80%
- ✅ All tests passing

**Phase 7-9 Complete**:
- ✅ Cross-module dependencies synchronized
- ✅ Shared Lambda layer deployed
- ✅ Documentation complete
- ✅ Deployed to staging and validated

### Risk Mitigation

**Risk**: Transcribe streaming SDK complexity
**Mitigation**: Start with simple implementation, add features incrementally, extensive testing

**Risk**: Emotion detection performance impact
**Mitigation**: Make emotion detection optional via feature flag, monitor latency metrics

**Risk**: Cross-stack CDK dependencies
**Mitigation**: Test CDK synth locally before deployment, use explicit stack dependencies

**Risk**: Test coverage gaps
**Mitigation**: Add tests incrementally with each phase, run coverage reports frequently

