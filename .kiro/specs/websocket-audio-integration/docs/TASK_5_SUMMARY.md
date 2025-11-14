# Task 5: Add Broadcast State to Session Data Model

## Task Description

Added BroadcastState model to track speaker broadcast control state (pause, mute, volume) and integrated it with the Session data model in DynamoDB.

## Task Instructions

From requirements and design:
- Create BroadcastState dataclass with fields: isActive, isPaused, isMuted, volume, lastStateChange
- Add validation for volume (0.0-1.0 range)
- Provide methods for state transitions (pause, resume, mute, unmute, set_volume)
- Integrate with SessionsRepository for DynamoDB storage
- Add backward compatibility for existing sessions

## Task Tests

```bash
cd session-management
python -m pytest tests/unit/test_broadcast_state.py -v
```

**Results**: 14 tests passed

**Test Coverage**:
- Default state creation
- Custom state creation with validation
- Volume validation (valid and invalid ranges)
- State transition methods (pause, resume, mute, unmute, set_volume)
- Broadcasting status check
- Serialization (to_dict, from_dict)
- Round-trip serialization
- Backward compatibility with missing fields

## Task Solution

### Files Created

1. **session-management/shared/models/__init__.py**
   - Package initialization for models
   - Exports BroadcastState

2. **session-management/shared/models/broadcast_state.py**
   - BroadcastState dataclass with 5 fields
   - Validation in `__post_init__` for volume range
   - State transition methods (immutable pattern)
   - Serialization methods (to_dict, from_dict)
   - Helper method `is_broadcasting()` for checking active state
   - Default factory method

3. **session-management/tests/unit/test_broadcast_state.py**
   - Comprehensive unit tests (14 tests)
   - Tests all state transitions
   - Tests validation logic
   - Tests serialization round-trip

### Files Modified

1. **session-management/shared/data_access/sessions_repository.py**
   - Added import for BroadcastState
   - Modified `create_session()` to initialize broadcastState field
   - Added `get_broadcast_state()` method
   - Added `update_broadcast_state()` method
   - Added convenience methods:
     - `pause_broadcast()`
     - `resume_broadcast()`
     - `mute_broadcast()`
     - `unmute_broadcast()`
     - `set_broadcast_volume()`

### Key Implementation Decisions

1. **Immutable State Pattern**: All state transition methods return new BroadcastState instances rather than modifying in place. This ensures thread safety and makes state changes explicit.

2. **Automatic Timestamp**: `lastStateChange` is automatically set to current time in `__post_init__` if not provided (value is 0).

3. **Backward Compatibility**: `get_broadcast_state()` returns default state if broadcastState field doesn't exist in DynamoDB, ensuring compatibility with existing sessions.

4. **Volume Validation**: Volume is validated both in `__post_init__` and in `set_volume()` to ensure it's always in the 0.0-1.0 range.

5. **Repository Integration**: Added high-level methods to SessionsRepository for common operations (pause, resume, mute, etc.) to encapsulate the get-modify-update pattern.

### Data Model

**BroadcastState Structure**:
```python
{
    'isActive': bool,      # Whether broadcasting is active
    'isPaused': bool,      # Whether broadcast is paused
    'isMuted': bool,       # Whether broadcast is muted
    'volume': float,       # Volume level (0.0-1.0)
    'lastStateChange': int # Unix timestamp in milliseconds
}
```

**Session Record (Updated)**:
```python
{
    'sessionId': str,
    'speakerConnectionId': str,
    'speakerUserId': str,
    'sourceLanguage': str,
    'qualityTier': str,
    'createdAt': int,
    'isActive': bool,
    'listenerCount': int,
    'expiresAt': int,
    'partialResultsEnabled': bool,
    'minStabilityThreshold': Decimal,
    'maxBufferTimeout': Decimal,
    'broadcastState': {      # NEW FIELD
        'isActive': bool,
        'isPaused': bool,
        'isMuted': bool,
        'volume': float,
        'lastStateChange': int
    }
}
```

### Usage Examples

```python
from shared.models.broadcast_state import BroadcastState
from shared.data_access.sessions_repository import SessionsRepository

# Create repository
repo = SessionsRepository(table_name='Sessions')

# Create session (broadcastState initialized automatically)
session = repo.create_session(
    session_id='golden-eagle-427',
    speaker_connection_id='conn-123',
    speaker_user_id='user-456',
    source_language='en',
    quality_tier='standard'
)

# Pause broadcast
new_state = repo.pause_broadcast('golden-eagle-427')
print(f"Paused: {new_state.isPaused}")  # True

# Resume broadcast
new_state = repo.resume_broadcast('golden-eagle-427')
print(f"Paused: {new_state.isPaused}")  # False

# Set volume
new_state = repo.set_broadcast_volume('golden-eagle-427', 0.7)
print(f"Volume: {new_state.volume}")  # 0.7

# Check if broadcasting
state = repo.get_broadcast_state('golden-eagle-427')
if state.is_broadcasting():
    print("Currently broadcasting")
```

## Requirements Addressed

- **Requirement 6**: Pause broadcast control (isPaused field and pause/resume methods)
- **Requirement 7**: Resume broadcast control (resume method)
- **Requirement 8**: Mute broadcast control (isMuted field and mute/unmute methods)
- **Requirement 9**: Volume control (volume field and set_volume method)
- **Requirement 10**: Speaker state change (comprehensive state model with lastStateChange tracking)

## Next Steps

This completes Task 5. The BroadcastState model is now ready to be used by:
- Task 3: Connection handler for speaker control messages
- Task 2: Audio processor to check broadcast state before processing audio
- Task 4: Session status handler to include broadcast state in status responses

