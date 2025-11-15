# WebSocket Audio Integration Fixes Design

## Overview

This design document provides a systematic approach to resolving all integration gaps and issues identified in the comprehensive code review. The implementation is 85-90% complete with excellent architecture and infrastructure, but requires specific integration fixes to achieve end-to-end functionality.

**Key Strategy**: Fix critical integration points first, then improve test coverage, then address production readiness items.

## Issue Categories and Priority

### Critical Priority (Blocks All Functionality)

1. **Import Error**: `get_structured_logger` function missing
2. **Missing Integration**: Translation Pipeline Lambda client not implemented
3. **Incomplete Integration**: Transcribe streaming has TODOs
4. **Infrastructure Gap**: sendAudio route missing from CDK

### High Priority (Improves Reliability)

5. **Missing Integration**: Emotion detection not connected to audio processing
6. **Test Quality**: 18% coverage vs 80% requirement, import errors

### Medium Priority (Production Readiness)

7. **Cross-Module Issues**: Inconsistent table names, error codes, message formats
8. **Code Duplication**: No shared Lambda layer for common utilities

## Architecture

### Current State vs Target State

**Current State**:
```
Audio Processor → [TODO: Transcribe Integration] → [TODO: Translation Client]
                                                    ↓
                                              Translation Pipeline
```

**Target State**:
```
Audio Processor → TranscribeStreamHandler → LambdaTranslationPipeline → Translation Pipeline
       ↓                                              ↑
EmotionDetection                              emotionDynamics included
```

### Integration Points to Fix

```
┌─────────────────────────────────────────────────────────────┐
│                    Integration Fixes                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Structured Logger Factory                               │
│     session-management/shared/utils/structured_logger.py    │
│     └─> Add: get_structured_logger() function              │
│                                                              │
│  2. Translation Pipeline Client                             │
│     audio-transcription/shared/services/                    │
│     └─> Create: lambda_translation_pipeline.py             │
│                                                              │
│  3. Transcribe Streaming Integration                        │
│     audio-transcription/lambda/audio_processor/handler.py   │
│     └─> Complete: TranscribeStreamHandler initialization   │
│     └─> Complete: Event loop processing                    │
│                                                              │
│  4. sendAudio Route Configuration                           │
│     session-management/infrastructure/stacks/               │
│     └─> Add: sendAudio route to CDK stack                  │
│                                                              │
│  5. Emotion Detection Integration                           │
│     audio-transcription/lambda/audio_processor/handler.py   │
│     └─> Add: EmotionDynamicsOrchestrator integration       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Structured Logger Factory Function

**File**: `session-management/shared/utils/structured_logger.py`

**Implementation**:

```python
def get_structured_logger(
    component: str,
    correlation_id: Optional[str] = None,
    session_id: Optional[str] = None,
    connection_id: Optional[str] = None,
    **kwargs
) -> StructuredLogger:
    """
    Factory function for creating StructuredLogger instances.
    
    This function provides a convenient way to create logger instances
    with consistent configuration across all Lambda handlers.
    
    Args:
        component: Name of the component (e.g., 'ConnectionHandler')
        correlation_id: Optional correlation ID for request tracing
        session_id: Optional session ID for context
        connection_id: Optional connection ID for context
        **kwargs: Additional keyword arguments passed to StructuredLogger
        
    Returns:
        Configured StructuredLogger instance
        
    Example:
        logger = get_structured_logger('AudioProcessor', session_id='abc-123')
        logger.info('Processing audio chunk')
    """
    return StructuredLogger(
        component=component,
        correlation_id=correlation_id,
        session_id=session_id,
        connection_id=connection_id,
        **kwargs
    )
```

**Impact**:
- Fixes all import errors in session-management tests
- Enables all Lambda handlers to execute
- Maintains backward compatibility

### 2. Lambda Translation Pipeline Client

**File**: `audio-transcription/shared/services/lambda_translation_pipeline.py`

**Implementation**:

```python
import json
import boto3
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError

class LambdaTranslationPipeline:
    """
    Lambda client for forwarding transcriptions to Translation Pipeline.
    
    This client implements the TranslationPipeline Protocol and provides
    asynchronous invocation of the Translation Pipeline Lambda function.
    """
    
    def __init__(
        self,
        function_name: str,
        lambda_client: Optional[boto3.client] = None
    ):
        """
        Initialize Lambda Translation Pipeline client.
        
        Args:
            function_name: Name of Translation Pipeline Lambda function
            lambda_client: Optional boto3 Lambda client (for testing)
        """
        self.function_name = function_name
        self.lambda_client = lambda_client or boto3.client('lambda')
        self.max_retries = 2
        self.retry_delay_ms = 100
        
    def process(
        self,
        text: str,
        session_id: str,
        source_language: str,
        is_partial: bool = False,
        stability_score: float = 1.0,
        timestamp: int = None,
        emotion_dynamics: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Forward transcription to Translation Pipeline.
        
        Args:
            text: Transcribed text
            session_id: Session identifier
            source_language: Source language code (ISO 639-1)
            is_partial: Whether this is a partial result
            stability_score: Transcription stability score (0.0-1.0)
            timestamp: Unix timestamp of transcription
            emotion_dynamics: Optional emotion data (volume, rate, energy)
            
        Returns:
            True if successfully forwarded, False otherwise
        """
        payload = {
            'sessionId': session_id,
            'sourceLanguage': source_language,
            'transcriptText': text,
            'isPartial': is_partial,
            'stabilityScore': stability_score,
            'timestamp': timestamp or int(time.time() * 1000),
            'emotionDynamics': emotion_dynamics or self._get_default_emotion()
        }
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.lambda_client.invoke(
                    FunctionName=self.function_name,
                    InvocationType='Event',  # Asynchronous
                    Payload=json.dumps(payload)
                )
                
                if response['StatusCode'] in [200, 202]:
                    return True
                    
            except ClientError as e:
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay_ms / 1000)
                    continue
                else:
                    # Log error and continue processing
                    logger.error(
                        f"Failed to invoke Translation Pipeline after {self.max_retries} retries",
                        extra={
                            'session_id': session_id,
                            'error': str(e),
                            'function_name': self.function_name
                        }
                    )
                    return False
                    
        return False
        
    def _get_default_emotion(self) -> Dict[str, Any]:
        """Get default neutral emotion values."""
        return {
            'volume': 0.5,
            'rate': 1.0,
            'energy': 0.5
        }
        
    def get_cached_emotion_data(self, session_id: str) -> Dict[str, Any]:
        """
        Get cached emotion data for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Emotion data dict or default values if not cached
        """
        return self.emotion_cache.get(session_id, self._get_default_emotion())
```

**Integration Point**:

```python
# In audio_processor/handler.py
from shared.services.lambda_translation_pipeline import LambdaTranslationPipeline

# Initialize at module level (outside handler)
translation_pipeline = LambdaTranslationPipeline(
    function_name=os.environ['TRANSLATION_PIPELINE_FUNCTION_NAME']
)

# Use in transcription event handler
def handle_transcription_event(event):
    translation_pipeline.process(
        text=event['transcript'],
        session_id=session_id,
        source_language=source_language,
        is_partial=event['is_partial'],
        stability_score=event.get('stability_score', 1.0),
        emotion_dynamics=emotion_data
    )
```

### 3. Complete Transcribe Streaming Integration

**File**: `audio-transcription/lambda/audio_processor/handler.py`

**Current State** (TODOs):
```python
# TODO: Send audio to Transcribe stream
# TODO: Create actual TranscribeStreamHandler
handler = None  # TODO: Create actual TranscribeStreamHandler
```

**Target Implementation**:

```python
import asyncio
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent

class TranscribeStreamHandler:
    """
    Manages AWS Transcribe Streaming API connections and event processing.
    """
    
    def __init__(
        self,
        session_id: str,
        source_language: str,
        translation_pipeline: LambdaTranslationPipeline,
        emotion_orchestrator: Optional[EmotionDynamicsOrchestrator] = None
    ):
        self.session_id = session_id
        self.source_language = source_language
        self.translation_pipeline = translation_pipeline
        self.emotion_orchestrator = emotion_orchestrator
        self.stream = None
        self.event_loop_task = None
        self.audio_buffer = AudioBuffer(max_size_seconds=5)
        self.is_active = False
        
    async def initialize_stream(self) -> bool:
        """
        Initialize Transcribe streaming connection.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.stream = await TranscribeStreamingClient(
                region=os.environ.get('AWS_REGION', 'us-east-1')
            ).start_stream_transcription(
                language_code=self.source_language,
                media_sample_rate_hz=16000,
                media_encoding='pcm',
                enable_partial_results_stabilization=True,
                partial_results_stability='high'
            )
            
            # Start event loop in background
            self.event_loop_task = asyncio.create_task(
                self._process_events()
            )
            
            self.is_active = True
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to initialize Transcribe stream: {e}",
                extra={'session_id': self.session_id}
            )
            return False
            
    async def send_audio_chunk(self, audio_data: bytes) -> None:
        """
        Send audio chunk to Transcribe stream.
        
        Args:
            audio_data: PCM audio data (16-bit, 16kHz, mono)
        """
        if not self.is_active or not self.stream:
            raise RuntimeError("Transcribe stream not initialized")
            
        # Add to buffer if stream is backpressured
        if not self.audio_buffer.add_chunk(audio_data):
            logger.warning(
                "Audio buffer overflow, dropping oldest chunks",
                extra={'session_id': self.session_id}
            )
            
        # Send buffered chunks to stream
        while self.audio_buffer.has_chunks():
            chunk = self.audio_buffer.get_chunk()
            await self.stream.input_stream.send_audio_event(
                audio_chunk=chunk
            )
            
    async def _process_events(self) -> None:
        """
        Process Transcribe events in async loop.
        """
        try:
            async for event in self.stream.output_stream:
                if isinstance(event, TranscriptEvent):
                    await self._handle_transcript_event(event)
                    
        except Exception as e:
            logger.error(
                f"Error in Transcribe event loop: {e}",
                extra={'session_id': self.session_id}
            )
            # Attempt reconnection
            await self._reconnect()
            
    async def _handle_transcript_event(self, event: TranscriptEvent) -> None:
        """
        Handle transcription event and forward to Translation Pipeline.
        """
        for result in event.transcript.results:
            if not result.alternatives:
                continue
                
            transcript = result.alternatives[0].transcript
            is_partial = result.is_partial
            stability_score = getattr(
                result.alternatives[0],
                'stability_score',
                1.0
            )
            
            # Get emotion dynamics if available
            emotion_data = None
            if self.emotion_orchestrator:
                # Emotion data would be extracted from audio chunks
                # and cached for correlation with transcripts
                emotion_data = self.emotion_orchestrator.get_cached_emotion(
                    self.session_id
                )
            
            # Forward to Translation Pipeline
            self.translation_pipeline.process(
                text=transcript,
                session_id=self.session_id,
                source_language=self.source_language,
                is_partial=is_partial,
                stability_score=stability_score,
                emotion_dynamics=emotion_data
            )
            
    async def close_stream(self) -> None:
        """Gracefully close Transcribe stream."""
        self.is_active = False
        
        if self.event_loop_task:
            self.event_loop_task.cancel()
            
        if self.stream:
            await self.stream.input_stream.end_stream()
            
        self.audio_buffer.clear()


# Module-level initialization
transcribe_handlers: Dict[str, TranscribeStreamHandler] = {}

def get_or_create_transcribe_handler(
    session_id: str,
    source_language: str
) -> TranscribeStreamHandler:
    """
    Get existing or create new Transcribe handler for session.
    """
    if session_id not in transcribe_handlers:
        transcribe_handlers[session_id] = TranscribeStreamHandler(
            session_id=session_id,
            source_language=source_language,
            translation_pipeline=translation_pipeline,
            emotion_orchestrator=emotion_orchestrator
        )
        
    return transcribe_handlers[session_id]
```

### 4. Add sendAudio Route to CDK

**File**: `session-management/infrastructure/stacks/session_management_stack.py`

**Implementation**:

```python
# In SessionManagementStack class

def _create_websocket_routes(self, api: apigwv2.CfnApi) -> None:
    """Create all WebSocket routes including sendAudio."""
    
    # ... existing routes ...
    
    # Add sendAudio route (CRITICAL - was missing)
    send_audio_integration = self._create_lambda_integration(
        api,
        self.audio_processor_function,  # Reference from audio-transcription stack
        "SendAudioIntegration"
    )
    
    send_audio_route = apigwv2.CfnRoute(
        self,
        "SendAudioRoute",
        api_id=api.ref,
        route_key="sendAudio",
        target=f"integrations/{send_audio_integration.ref}",
        route_response_selection_expression="$default"
    )
    
    # Configure binary frame support
    send_audio_integration.content_handling_strategy = "CONVERT_TO_BINARY"
    send_audio_integration.timeout_in_millis = 60000  # 60 seconds
```

**Cross-Stack Reference**:

```python
# In session_management_stack.py
from audio_transcription.infrastructure.stacks.audio_transcription_stack import AudioTranscriptionStack

class SessionManagementStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        audio_transcription_stack: AudioTranscriptionStack,
        **kwargs
    ):
        super().__init__(scope, id, **kwargs)
        
        # Reference audio_processor from other stack
        self.audio_processor_function = audio_transcription_stack.audio_processor_function
        
        # Create routes
        self._create_websocket_routes(self.websocket_api)
```

### 5. Integrate Emotion Detection

**File**: `audio-transcription/lambda/audio_processor/handler.py`

**Implementation**:

```python
from emotion_dynamics.orchestrator import EmotionDynamicsOrchestrator
import numpy as np

# Module-level initialization
emotion_orchestrator = EmotionDynamicsOrchestrator()

# Emotion cache for correlating with transcripts
emotion_cache: Dict[str, Dict[str, Any]] = {}

async def process_audio_chunk_with_emotion(
    session_id: str,
    audio_data: bytes
) -> None:
    """
    Process audio chunk with emotion detection.
    
    Args:
        session_id: Session identifier
        audio_data: PCM audio data
    """
    try:
        # Convert bytes to numpy array
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        sample_rate = 16000
        
        # Extract emotion dynamics
        emotion_data = emotion_orchestrator.process_audio_chunk(
            audio_array,
            sample_rate
        )
        
        # Cache emotion data for correlation with transcripts
        emotion_cache[session_id] = {
            'volume': emotion_data.get('volume', 0.5),
            'rate': emotion_data.get('speaking_rate', 1.0),
            'energy': emotion_data.get('energy', 0.5),
            'timestamp': int(time.time() * 1000)
        }
        
        # Send audio to Transcribe
        handler = get_or_create_transcribe_handler(session_id, source_language)
        await handler.send_audio_chunk(audio_data)
        
    except Exception as e:
        logger.error(
            f"Error processing audio with emotion: {e}",
            extra={'session_id': session_id}
        )
        # Continue with default emotion values
        emotion_cache[session_id] = {
            'volume': 0.5,
            'rate': 1.0,
            'energy': 0.5
        }
```

## Data Models

### Translation Pipeline Payload

```python
{
    "sessionId": "golden-eagle-427",
    "sourceLanguage": "en",
    "transcriptText": "Hello everyone",
    "isPartial": False,
    "stabilityScore": 0.95,
    "timestamp": 1699500000000,
    "emotionDynamics": {
        "volume": 0.7,      # 0.0-1.0 (quiet to loud)
        "rate": 1.2,        # 0.5-2.0 (slow to fast)
        "energy": 0.8       # 0.0-1.0 (low to high energy)
    }
}
```

### Emotion Cache Entry

```python
{
    "session_id": {
        "volume": 0.7,
        "rate": 1.2,
        "energy": 0.8,
        "timestamp": 1699500000000
    }
}
```

## Testing Strategy

### Unit Tests to Add

**1. Structured Logger Factory** (`test_structured_logger.py`):
```python
def test_get_structured_logger_creates_instance():
    logger = get_structured_logger('TestComponent')
    assert isinstance(logger, StructuredLogger)
    assert logger.component == 'TestComponent'

def test_get_structured_logger_with_correlation_id():
    logger = get_structured_logger('Test', correlation_id='abc-123')
    assert logger.correlation_id == 'abc-123'
```

**2. Lambda Translation Pipeline** (`test_lambda_translation_pipeline.py`):
```python
@mock_lambda
def test_lambda_translation_pipeline_success():
    client = LambdaTranslationPipeline('test-function')
    result = client.process(
        text='Hello',
        session_id='test-123',
        source_language='en'
    )
    assert result is True

@mock_lambda
def test_lambda_translation_pipeline_retry_on_failure():
    # Test retry logic with transient failures
    pass
```

**3. Transcribe Stream Handler** (`test_transcribe_stream_handler.py`):
```python
@pytest.mark.asyncio
async def test_transcribe_stream_initialization():
    handler = TranscribeStreamHandler('test-123', 'en', mock_pipeline)
    result = await handler.initialize_stream()
    assert result is True
    assert handler.is_active is True

@pytest.mark.asyncio
async def test_transcribe_event_processing():
    # Test event loop and transcript forwarding
    pass
```

**4. Emotion Integration** (`test_emotion_integration.py`):
```python
@pytest.mark.asyncio
async def test_audio_processing_with_emotion():
    audio_data = generate_test_audio()
    await process_audio_chunk_with_emotion('test-123', audio_data)
    assert 'test-123' in emotion_cache
    assert 'volume' in emotion_cache['test-123']
```

### Integration Tests to Add

**End-to-End Audio Flow** (`test_e2e_audio_flow.py`):
```python
@pytest.mark.integration
@mock_dynamodb
@mock_lambda
async def test_complete_audio_to_translation_flow():
    """
    Test complete flow:
    1. Send audio via WebSocket
    2. Verify Transcribe stream initialized
    3. Verify transcription generated
    4. Verify forwarded to Translation Pipeline
    5. Verify emotion data included
    """
    # Implementation
    pass
```

## Error Handling

### Import Error Resolution

**Before**:
```python
from shared.utils.structured_logger import get_structured_logger
# ImportError: cannot import name 'get_structured_logger'
```

**After**:
```python
from shared.utils.structured_logger import get_structured_logger
logger = get_structured_logger('ComponentName')
# Success - function exists and returns StructuredLogger instance
```

### Translation Pipeline Error Handling

```python
try:
    success = translation_pipeline.process(...)
    if not success:
        logger.warning("Translation Pipeline invocation failed after retries")
        # Continue processing - don't block on translation failures
except Exception as e:
    logger.error(f"Unexpected error forwarding to Translation Pipeline: {e}")
    # Continue processing
```

## Performance Considerations

### Latency Impact

**Current (with TODOs)**:
- Audio → [TODO] → Translation: ∞ (not working)

**Target (after fixes)**:
- Audio → Transcribe: <20ms
- Transcribe → Translation: <100ms
- Emotion extraction: <50ms
- **Total added latency: <170ms**

### Memory Impact

**Emotion Detection**:
- librosa + numpy: ~100MB
- Audio buffer: ~160KB
- **Total: Fits within 1024MB Lambda allocation**

## Deployment Strategy

### Phase 1: Critical Fixes (Day 1)

1. Add `get_structured_logger` function
2. Run all tests to verify import errors resolved
3. Deploy to dev environment

### Phase 2: Integration Implementation (Days 2-3)

1. Implement `LambdaTranslationPipeline`
2. Complete `TranscribeStreamHandler`
3. Add sendAudio route to CDK
4. Deploy to dev environment
5. Run integration tests

### Phase 3: Emotion Integration (Day 4)

1. Integrate `EmotionDynamicsOrchestrator`
2. Add emotion caching logic
3. Update Translation Pipeline payload
4. Deploy to dev environment
5. Verify emotion data in logs

### Phase 4: Test Coverage (Day 5)

1. Add unit tests for new components
2. Add integration tests for E2E flow
3. Run full test suite
4. Verify 80%+ coverage

### Phase 5: Production Readiness (Days 6-7)

1. Synchronize cross-module dependencies
2. Create shared Lambda layer
3. Standardize error codes
4. Update documentation
5. Deploy to staging
6. Run smoke tests
7. Deploy to production

## Rollback Plan

**If Critical Issues Occur**:
1. Revert CDK stack to previous version
2. Redeploy previous Lambda versions
3. Monitor for stability
4. Fix issues in dev environment
5. Redeploy with fixes

## Configuration

### Environment Variables to Add

**audio_processor Lambda**:
```python
TRANSLATION_PIPELINE_FUNCTION_NAME = 'TranslationProcessor'
ENABLE_EMOTION_DETECTION = 'true'
EMOTION_CACHE_TTL_SECONDS = '60'
```

### CDK Configuration

```python
# In audio_transcription_stack.py
audio_processor_function.add_environment(
    'TRANSLATION_PIPELINE_FUNCTION_NAME',
    translation_pipeline_function.function_name
)

# Grant invoke permission
translation_pipeline_function.grant_invoke(audio_processor_function)
```

## Success Criteria

### Critical Fixes Complete

- ✅ All tests pass without import errors
- ✅ Audio chunks reach Transcribe via sendAudio route
- ✅ Transcriptions forwarded to Translation Pipeline
- ✅ End-to-end flow works from audio to translation

### High Priority Complete

- ✅ Emotion data included in translations
- ✅ Test coverage >80%
- ✅ All unit tests passing

### Medium Priority Complete

- ✅ Cross-module dependencies synchronized
- ✅ Shared Lambda layer deployed
- ✅ Error codes standardized
- ✅ Documentation updated

## Summary

This design provides a systematic approach to resolving all identified issues in the WebSocket Audio Integration implementation. The fixes are:

- **Minimal**: Only addresses actual gaps, leverages existing infrastructure
- **Prioritized**: Critical issues first, then reliability, then polish
- **Testable**: Comprehensive unit and integration tests
- **Documented**: Clear integration points and error handling
- **Deployable**: Phased rollout with rollback plan

Once complete, the system will have:
- ✅ Working end-to-end audio-to-translation flow
- ✅ Emotion preservation in translations
- ✅ 80%+ test coverage
- ✅ Production-ready reliability
- ✅ Comprehensive documentation

