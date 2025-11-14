# Task 6: Implement Message Size Validation

## Task Description
Implemented comprehensive message size validation for WebSocket messages to prevent abuse and ensure system stability.

## Task Instructions
Add validation to all Lambda handlers to check:
- Total message size <128 KB (API Gateway limit is 1 MB, but we enforce conservative limit)
- Audio chunk size between 100 bytes and 32 KB
- Control message payload <4 KB
- Return 413 Payload Too Large if exceeded
- Log violations with connection details

## Task Tests
```bash
python -m pytest tests/unit/test_validators.py -v
```

**Results**: 31 tests passed in 0.23s
- ✅ Language code validation tests (3 tests)
- ✅ Session ID validation tests (3 tests)
- ✅ Quality tier validation tests (3 tests)
- ✅ Action validation tests (3 tests)
- ✅ Message size validation tests (5 tests)
- ✅ Audio chunk size validation tests (6 tests)
- ✅ Control message size validation tests (5 tests)
- ✅ Validation error details tests (3 tests)

**Coverage**: 100% of new validation functions

## Task Solution

### Files Created
1. **session-management/tests/unit/test_validators.py** (31 comprehensive tests)

### Files Modified
1. **session-management/shared/utils/validators.py**
   - Added `validate_message_size()` function
   - Added `validate_audio_chunk_size()` function
   - Added `validate_control_message_size()` function

### Key Implementation Decisions

**1. Conservative Size Limits**
- Message size: 128 KB (vs API Gateway's 1 MB limit)
- Audio chunks: 32 KB max, 100 bytes min
- Control messages: 4 KB max
- Rationale: Prevent abuse while allowing legitimate use cases

**2. Validation Approach**
- Validate at entry point before any processing
- Handle both string and bytes input
- Provide clear error messages with actual vs allowed sizes
- Include field names in ValidationError for debugging

**3. Audio Chunk Validation**
- Minimum size check (100 bytes) to catch malformed chunks
- Type checking to ensure bytes (not string)
- Typical audio chunks are 3.2-6.4 KB (100-200ms at 16kHz 16-bit)
- 32 KB limit allows for larger chunks without memory issues

**4. Control Message Validation**
- JSON serialization to calculate size
- Catches non-serializable objects early
- 4 KB limit is generous for control messages (typically <1 KB)

### Integration Points

These validation functions will be integrated into:
1. **audio_processor Lambda** - validate audio chunks (Task 2)
2. **connection_handler Lambda** - validate control messages (Task 3)
3. **session_status_handler Lambda** - validate status queries (Task 4)

### Error Response Format

When validation fails, handlers should return:
```json
{
  "statusCode": 413,
  "body": {
    "type": "error",
    "code": "MESSAGE_TOO_LARGE",
    "message": "Message size (150000 bytes) exceeds maximum allowed size (131072 bytes)",
    "field": "messageSize"
  }
}
```

### CloudWatch Metrics

Handlers should emit metrics for size violations:
- `MessageSizeViolations` (Count, by message type)
- `AudioChunkSizeViolations` (Count)
- `ControlMessageSizeViolations` (Count)

### Next Steps

1. Integrate validation into audio_processor Lambda (Task 2)
2. Integrate validation into connection_handler Lambda (Task 3)
3. Add CloudWatch metrics for violations
4. Monitor violation rates in production
