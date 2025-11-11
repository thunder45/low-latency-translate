# Task 14: Update DynamoDB Session Schema

## Task Description

Updated the DynamoDB Sessions table schema to include partial result configuration fields, enabling per-session control of partial result processing parameters.

## Task Instructions

### Task 14.1: Add partial result configuration fields to Sessions table

Add the following fields to the Sessions table:
- `partialResultsEnabled`: Boolean field to enable/disable partial results
- `minStabilityThreshold`: Float field for minimum stability threshold (0.70-0.95)
- `maxBufferTimeout`: Float field for maximum buffer timeout (2.0-10.0 seconds)

No migration needed as DynamoDB is schemaless.

### Task 14.2: Update session creation API to accept configuration parameters

Update the session creation API to:
- Parse `partialResults`, `minStability`, and `maxBufferTimeout` query parameters
- Validate configuration using range checks
- Store configuration in DynamoDB session item
- Return error for invalid configuration

## Task Tests

### Unit Tests
```bash
python -m pytest session-management/tests/test_connection_handler.py::test_create_session_success -v
```

**Result**: PASSED

### All Tests
```bash
python -m pytest session-management/tests/ -v
```

**Result**: 165 passed, 6 failed (E2E tests unrelated to this task)

The 6 failing E2E tests are pre-existing failures related to heartbeat handler validation, not related to the schema changes.

## Task Solution

### 1. Updated SessionsRepository

**File**: `session-management/shared/data_access/sessions_repository.py`

**Changes**:
- Added `Decimal` import for DynamoDB numeric type compatibility
- Extended `create_session()` method signature with three new parameters:
  - `partial_results_enabled: bool = True`
  - `min_stability_threshold: float = 0.85`
  - `max_buffer_timeout: float = 5.0`
- Added new fields to session item dictionary
- Converted float values to `Decimal` type for DynamoDB compatibility
- Updated logging to include partial results status

**Key Implementation Detail**: DynamoDB requires `Decimal` type for numeric values, not Python `float`. Used `Decimal(str(value))` conversion to ensure precision.

### 2. Updated Connection Handler

**File**: `session-management/lambda/connection_handler/handler.py`

**Changes**:
- Added query parameter extraction for partial results configuration:
  - `partialResults` (default: 'true')
  - `minStability` (default: '0.85')
  - `maxBufferTimeout` (default: '5.0')
- Implemented validation logic:
  - Convert string parameters to float
  - Validate `minStability` range (0.70-0.95)
  - Validate `maxBufferTimeout` range (2.0-10.0)
  - Return 400 error with descriptive message for invalid values
- Updated `sessions_repo.create_session()` call with new parameters
- Enhanced success response to include configuration values

**Validation Logic**:
```python
try:
    min_stability_threshold = float(min_stability)
    max_buffer_timeout_seconds = float(max_buffer_timeout)
    
    if not 0.70 <= min_stability_threshold <= 0.95:
        raise ValueError(...)
    
    if not 2.0 <= max_buffer_timeout_seconds <= 10.0:
        raise ValueError(...)
except ValueError as e:
    return error_response(400, 'INVALID_CONFIGURATION', str(e))
```

### 3. Schema Changes

**Sessions Table Schema** (extended):
```python
{
    'sessionId': 'golden-eagle-427',
    'speakerConnectionId': 'conn-123',
    'speakerUserId': 'user-123',
    'sourceLanguage': 'en',
    'qualityTier': 'standard',
    'createdAt': 1699500000000,
    'isActive': True,
    'listenerCount': 0,
    'expiresAt': 1699510800000,
    # NEW FIELDS
    'partialResultsEnabled': True,
    'minStabilityThreshold': Decimal('0.85'),
    'maxBufferTimeout': Decimal('5.0')
}
```

### 4. API Changes

**Session Creation Request** (query parameters):
```
wss://api.example.com?action=createSession&sourceLanguage=en&qualityTier=standard&partialResults=true&minStability=0.85&maxBufferTimeout=5.0
```

**Session Creation Response** (enhanced):
```json
{
    "type": "sessionCreated",
    "sessionId": "golden-eagle-427",
    "sourceLanguage": "en",
    "qualityTier": "standard",
    "partialResultsEnabled": true,
    "minStabilityThreshold": 0.85,
    "maxBufferTimeout": 5.0,
    "connectionId": "conn-123",
    "timestamp": 1699500000000
}
```

### Design Decisions

1. **Default Values**: Chose sensible defaults (enabled=true, stability=0.85, timeout=5.0) based on design document recommendations

2. **Decimal Type**: Used `Decimal` for numeric fields to comply with DynamoDB requirements and avoid precision issues

3. **Validation at API Layer**: Implemented validation in the connection handler rather than repository to provide better error messages to clients

4. **Backward Compatibility**: Default values ensure existing code continues to work without changes

5. **No Migration Required**: DynamoDB's schemaless nature means new fields are simply added to new items; existing items remain valid

### Testing Notes

- All connection handler tests pass with new schema
- Session creation test validates new fields are stored correctly
- Validation tests confirm proper error handling for invalid ranges
- E2E test failures are pre-existing and unrelated to schema changes

### Requirements Addressed

- **Requirement 6.1**: Configuration parameter for minimum stability threshold (0.70-0.95) ✓
- **Requirement 6.2**: Configuration parameter for maximum buffer timeout (2-10 seconds) ✓
- **Requirement 6.3**: Configuration parameter to enable/disable partial result processing per session ✓
- **Requirement 6.5**: Validation of configuration parameters with descriptive error messages ✓
