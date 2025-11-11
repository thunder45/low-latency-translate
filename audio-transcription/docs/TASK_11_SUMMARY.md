# Task 11: Integrate with AWS Transcribe Streaming API

## Task Description

Implemented integration with AWS Transcribe Streaming API to enable real-time transcription with partial results processing. This task creates the bridge between AWS Transcribe and the PartialResultProcessor, handling event streaming, stability score extraction, and client configuration.

## Task Instructions

### Task 11.1: Create async stream handler for Transcribe events
- Extend TranscriptResultStreamHandler
- Implement handle_transcript_event() async method
- Extract stability scores with null safety
- Call PartialResultProcessor methods
- Requirements: 2.1, 2.2, 7.6

### Task 11.2: Configure Transcribe client with partial results enabled
- Set enable_partial_results_stabilization=True
- Set partial_results_stability='high'
- Configure language code and media parameters
- Requirements: 2.1

## Task Tests

All tests passing with 91.51% coverage:

```bash
python -m pytest tests/ -v --cov=shared --cov-report=term-missing --cov-fail-under=80
```

**Test Results:**
- Total tests: 225 passed
- New tests added: 28 (13 for stream handler, 15 for client config)
- Coverage: 91.51% (exceeds 80% requirement)

**New Test Files:**
- `tests/unit/test_transcribe_stream_handler.py` - 13 tests
- `tests/unit/test_transcribe_client.py` - 15 tests

**Test Coverage:**
- TranscribeStreamHandler: 88% coverage
- TranscribeClientConfig: 100% coverage
- TranscribeClientManager: 100% coverage

## Task Solution

### 1. Created TranscribeStreamHandler (Task 11.1)

**File:** `shared/services/transcribe_stream_handler.py`

**Key Features:**
- Extends `TranscriptResultStreamHandler` from amazon-transcribe SDK
- Async event handling with `handle_transcript_event()` method
- Defensive null checks for all event fields
- Stability score extraction with validation and clamping
- Routes partial results to `processor.process_partial()`
- Routes final results to `processor.process_final()`
- Generates result_id if missing from event
- Handles missing stability scores gracefully

**Implementation Highlights:**

```python
class TranscribeStreamHandler(TranscriptResultStreamHandler):
    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        # Extract results with null safety
        if not hasattr(transcript_event, 'transcript'):
            return
        
        # Process each result
        for result in transcript_event.transcript.results:
            await self._process_result(result)
    
    def _extract_stability_score(self, alternative) -> Optional[float]:
        # Extract with null safety and validation
        # Clamp to [0.0, 1.0] range
        # Return None if unavailable
```

**Null Safety Features:**
- Checks for missing transcript attribute
- Handles empty results array
- Generates result_id if missing
- Skips empty text
- Validates stability score range
- Clamps out-of-range values

### 2. Created Transcribe Client Configuration (Task 11.2)

**File:** `shared/services/transcribe_client.py`

**Key Components:**

#### TranscribeClientConfig
- Encapsulates all Transcribe configuration parameters
- Validates language code, sample rate, encoding, stability level
- Supports 4 sample rates: 8000, 16000, 24000, 48000 Hz
- Supports 3 encodings: pcm, ogg-opus, flac
- Supports 3 stability levels: low, medium, high
- Defaults to partial results enabled with 'high' stability

#### TranscribeClientManager
- Manages client lifecycle
- Creates TranscribeStreamingClient instances
- Starts transcription streams with correct configuration
- Provides stream request parameters

#### Convenience Function
- `create_transcribe_client_for_session()` - One-line client creation
- Returns tuple of (client, manager)
- Sensible defaults for quick setup

**Configuration Example:**

```python
# Create client with defaults
client, manager = create_transcribe_client_for_session('en-US')

# Create handler
handler = TranscribeStreamHandler(
    output_stream=stream,
    processor=processor,
    session_id='golden-eagle-427',
    source_language='en'
)

# Start stream
stream = await manager.start_stream(client, handler)
```

**Stream Configuration:**
```python
{
    'language_code': 'en-US',
    'media_sample_rate_hz': 16000,
    'media_encoding': 'pcm',
    'enable_partial_results_stabilization': True,
    'partial_results_stability': 'high'
}
```

### 3. Updated Dependencies

**File:** `requirements.txt`

Added amazon-transcribe SDK:
```
amazon-transcribe>=0.6.0
```

This provides:
- `TranscribeStreamingClient` - Client for streaming API
- `TranscriptResultStreamHandler` - Base handler class
- `TranscriptEvent` - Event type definitions

### Integration Flow

```
AWS Transcribe Streaming API
    ↓
TranscribeStreamHandler.handle_transcript_event()
    ↓
Extract metadata with null safety
    ↓
Create PartialResult or FinalResult
    ↓
Route to PartialResultProcessor
    ↓
processor.process_partial() or processor.process_final()
```

### Error Handling

**Defensive Programming:**
- All event fields checked with `hasattr()` and null checks
- Missing result_id generates timestamp-based ID
- Empty text skipped with debug log
- Invalid stability scores clamped to [0.0, 1.0]
- Exceptions caught and logged, processing continues

**Validation:**
- Language code format validation
- Sample rate must be in [8000, 16000, 24000, 48000]
- Encoding must be in ['pcm', 'ogg-opus', 'flac']
- Stability level must be in ['low', 'medium', 'high']

### Design Decisions

**1. Async/Await Pattern**
- Handler methods are async to support async processor methods
- Allows non-blocking event processing
- Compatible with Lambda async/sync bridge

**2. Null Safety First**
- Every field checked before access
- Graceful degradation for missing data
- Continues processing even with malformed events

**3. Stability Score Handling**
- Extracts from first item in alternatives
- Validates type and range
- Clamps out-of-range values instead of rejecting
- Returns None if unavailable (triggers time-based fallback)

**4. Configuration Validation**
- Validates at initialization time
- Fails fast with descriptive errors
- Prevents runtime errors from invalid config

### Testing Strategy

**Unit Tests:**
- Mock AWS Transcribe events
- Test all null safety paths
- Test stability score extraction edge cases
- Test configuration validation
- Test client creation and stream starting

**Test Coverage:**
- Partial results with/without stability
- Final results
- Missing/malformed event fields
- Stability score edge cases (negative, out of range, invalid type)
- Configuration validation (all valid/invalid combinations)

### Files Created

1. `shared/services/transcribe_stream_handler.py` (294 lines)
2. `shared/services/transcribe_client.py` (300 lines)
3. `tests/unit/test_transcribe_stream_handler.py` (13 tests)
4. `tests/unit/test_transcribe_client.py` (15 tests)

### Files Modified

1. `requirements.txt` - Added amazon-transcribe dependency

### Requirements Addressed

**Requirement 2.1:** Subscribe to AWS Transcribe Streaming API with partial results enabled
- ✅ TranscribeClientManager configures client with partial results enabled
- ✅ Stream started with enable_partial_results_stabilization=True

**Requirement 2.2:** Distinguish between partial and final results
- ✅ TranscribeStreamHandler checks IsPartial flag
- ✅ Routes to appropriate processor method

**Requirement 7.6:** Handle missing stability scores
- ✅ _extract_stability_score() returns None if unavailable
- ✅ Processor falls back to time-based buffering

### Next Steps

This task completes the AWS Transcribe integration layer. The next tasks (12-17) will:
- Integrate with Lambda function (Task 12)
- Implement CloudWatch metrics and logging (Task 13)
- Update DynamoDB session schema (Task 14)
- Update infrastructure configuration (Task 15)
- Create deployment and rollout plan (Task 16)
- Perform performance and quality validation (Task 17)

### Usage Example

```python
from shared.services.transcribe_client import create_transcribe_client_for_session
from shared.services.transcribe_stream_handler import TranscribeStreamHandler
from shared.services.partial_result_processor import PartialResultProcessor

# Initialize processor
processor = PartialResultProcessor(
    session_id='golden-eagle-427',
    source_language='en'
)

# Create Transcribe client
client, manager = create_transcribe_client_for_session(
    language_code='en-US',
    sample_rate_hz=16000,
    encoding='pcm'
)

# Create handler
handler = TranscribeStreamHandler(
    output_stream=output_stream,
    processor=processor,
    session_id='golden-eagle-427',
    source_language='en'
)

# Start streaming
stream = await manager.start_stream(client, handler)

# Send audio chunks
await stream.send_audio_event(audio_chunk=audio_data)

# Events automatically handled by TranscribeStreamHandler
# which routes to PartialResultProcessor
```

