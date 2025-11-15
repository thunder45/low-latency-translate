# WebSocket Audio Integration Fixes

## Overview

This spec addresses all integration gaps and issues identified in the comprehensive code review of the WebSocket Audio Integration implementation. While the core infrastructure is exceptionally well-built (85-90% complete), there are specific integration points that need to be completed for end-to-end functionality.

## Status

**Current State**: Spec Complete - Ready for Implementation

**Estimated Timeline**: 5-7 days

**Risk Level**: LOW - Fixes are straightforward with excellent foundation in place

## Issues Addressed

### Critical Priority (Blocks All Functionality)

1. ✅ **Import Error**: Missing `get_structured_logger()` factory function
2. ✅ **Missing Integration**: Translation Pipeline Lambda client not implemented  
3. ✅ **Incomplete Integration**: Transcribe streaming has TODOs
4. ✅ **Infrastructure Gap**: sendAudio route missing from CDK

### High Priority (Improves Reliability)

5. ✅ **Missing Integration**: Emotion detection not connected to audio processing
6. ✅ **Test Quality**: 18% coverage vs 80% requirement, import errors

### Medium Priority (Production Readiness)

7. ✅ **Cross-Module Issues**: Inconsistent table names, error codes, message formats
8. ✅ **Code Duplication**: No shared Lambda layer for common utilities

## Documents

- **[requirements.md](requirements.md)**: 15 requirements covering all fix categories
- **[design.md](design.md)**: Detailed implementation design with code examples
- **[tasks.md](tasks.md)**: 9 phases with 50+ actionable sub-tasks

## Implementation Phases

### Phase 1: Critical Fixes (Day 1)
- Fix structured logger import error
- Verify all tests run without import errors

### Phase 2-3: Core Integration (Days 2-3)
- Implement Translation Pipeline Lambda client
- Complete Transcribe streaming integration
- Add sendAudio route to CDK

### Phase 4: Emotion Detection (Day 4)
- Integrate EmotionDynamicsOrchestrator
- Cache emotion data for transcripts
- Include emotion in Translation Pipeline payload

### Phase 5: Test Coverage (Day 5)
- Add unit tests for all new components
- Add integration tests for E2E flow
- Achieve 80%+ coverage

### Phase 6: Production Readiness (Day 6)
- Synchronize cross-module dependencies
- Create shared Lambda layer
- Standardize error codes and messages

### Phase 7: Deployment (Day 7)
- Update documentation
- Deploy to staging
- Validate performance and security
- Prepare for production

## Success Criteria

**Critical Fixes Complete**:
- ✅ All tests pass without import errors
- ✅ Audio chunks reach Transcribe via sendAudio route
- ✅ Transcriptions forwarded to Translation Pipeline
- ✅ End-to-end flow works from audio to translation

**High Priority Complete**:
- ✅ Emotion data included in translations
- ✅ Test coverage >80%
- ✅ All unit tests passing

**Medium Priority Complete**:
- ✅ Cross-module dependencies synchronized
- ✅ Shared Lambda layer deployed
- ✅ Error codes standardized
- ✅ Documentation updated

## Getting Started

To begin implementing this spec:

1. **Review the requirements**: Read [requirements.md](requirements.md) to understand all acceptance criteria
2. **Study the design**: Read [design.md](design.md) for implementation details and code examples
3. **Start with tasks**: Open [tasks.md](tasks.md) and begin with Phase 1, Task 1

## Key Integration Points

### 1. Structured Logger Factory
```python
# session-management/shared/utils/structured_logger.py
def get_structured_logger(component: str, **kwargs) -> StructuredLogger:
    return StructuredLogger(component, **kwargs)
```

### 2. Translation Pipeline Client
```python
# audio-transcription/shared/services/lambda_translation_pipeline.py
class LambdaTranslationPipeline:
    def process(self, text, session_id, source_language, emotion_dynamics):
        # Forward to Translation Pipeline Lambda
```

### 3. Transcribe Streaming
```python
# audio-transcription/lambda/audio_processor/handler.py
class TranscribeStreamHandler:
    async def initialize_stream(self):
        # Initialize AWS Transcribe Streaming API
    
    async def send_audio_chunk(self, audio_data):
        # Send audio to Transcribe
    
    async def _process_events(self):
        # Process transcription events
```

### 4. sendAudio Route
```python
# session-management/infrastructure/stacks/session_management_stack.py
send_audio_route = apigwv2.CfnRoute(
    self, "SendAudioRoute",
    api_id=api.ref,
    route_key="sendAudio",
    target=f"integrations/{send_audio_integration.ref}"
)
```

### 5. Emotion Detection
```python
# audio-transcription/lambda/audio_processor/handler.py
emotion_orchestrator = EmotionDynamicsOrchestrator()

async def process_audio_chunk_with_emotion(session_id, audio_data):
    emotion_data = emotion_orchestrator.process_audio_chunk(audio_array, sample_rate)
    emotion_cache[session_id] = emotion_data
```

## Testing Strategy

### Unit Tests
- Structured logger factory function
- Translation Pipeline client (success, retry, failure)
- Transcribe stream handler (init, send, process, close)
- Emotion integration (extract, cache, error handling)

### Integration Tests
- End-to-end audio flow (audio → Transcribe → Translation)
- Emotion data inclusion in payload
- No audio loss or duplication
- Latency <5 seconds

### Coverage Target
- Minimum 80% across all components
- 100% for new components

## Deployment Strategy

1. **Dev Environment**: Deploy after each phase for incremental testing
2. **Staging Environment**: Deploy complete solution for 24-hour monitoring
3. **Production Environment**: Deploy after staging validation with canary rollout

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Transcribe SDK complexity | Start simple, add features incrementally, extensive testing |
| Emotion detection performance | Make optional via feature flag, monitor latency |
| Cross-stack CDK dependencies | Test CDK synth locally, use explicit dependencies |
| Test coverage gaps | Add tests incrementally, run coverage reports frequently |

## Related Specs

- **[websocket-audio-integration](../websocket-audio-integration/)**: Original implementation spec (85-90% complete)
- This spec completes the remaining 10-15% integration work

## Questions?

For questions about this spec:
1. Review the design document for implementation details
2. Check the tasks document for specific sub-task breakdowns
3. Refer to the original websocket-audio-integration spec for context

## Next Steps

**Ready to start?** Open [tasks.md](tasks.md) and begin with Phase 1, Task 1: Fix structured logger import error.

