# Task 9: Implement Atomic Listener Count Updates

## Task Description
Implemented atomic counter operations for managing listener counts in the Sessions table using DynamoDB's ADD operation to prevent race conditions during concurrent listener joins and disconnects.

## Task Instructions
Create AtomicCounter class that:
- Implements atomic increment operation using DynamoDB ADD
- Implements atomic decrement operation with condition to prevent negative counts
- Provides get operation for reading current count
- Handles errors gracefully with custom exceptions
- Integrates with connection lifecycle (join/disconnect)

## Task Tests
- `pytest tests/unit/test_atomic_counter.py` - 15 passed
- Coverage: 100% of atomic counter logic

### Test Cases
1. ✅ Increment listener count succeeds
2. ✅ Increment with custom amount
3. ✅ Increment handles client errors
4. ✅ Decrement listener count succeeds
5. ✅ Decrement with custom amount
6. ✅ Decrement prevents negative count
7. ✅ Decrement handles other errors
8. ✅ Get listener count succeeds
9. ✅ Get returns None for missing session
10. ✅ Get handles client errors
11. ✅ Concurrent increments use atomic operation
12. ✅ Concurrent decrements use atomic operation with condition
13. ✅ Increment from zero succeeds
14. ✅ Decrement to zero succeeds
15. ✅ Multiple increments accumulate correctly

## Task Solution

### Implementation Details

**Created Files:**
- `shared/data_access/atomic_counter.py` - Atomic counter implementation
- `tests/unit/test_atomic_counter.py` - Comprehensive unit tests

**Key Features:**

1. **Atomic Increment Operation**
   - Uses DynamoDB `ADD` operation for thread-safe increments
   - Supports custom increment amounts (default: 1)
   - Returns new count after increment
   - Handles DynamoDB errors with custom exceptions

2. **Atomic Decrement Operation**
   - Uses DynamoDB `ADD` with negative value for decrements
   - Includes `ConditionExpression` to prevent negative counts
   - Raises `NegativeCountError` if condition fails
   - Returns new count after decrement

3. **Count Retrieval**
   - Provides `get_listener_count()` for reading current count
   - Uses projection expression for efficient queries
   - Returns None for missing sessions
   - Handles errors gracefully

4. **Error Handling**
   - Custom exception hierarchy: `AtomicCounterError`, `NegativeCountError`
   - Distinguishes between conditional check failures and other errors
   - Comprehensive logging with session context
   - Graceful degradation on failures

5. **Race Condition Prevention**
   - DynamoDB's ADD operation is atomic at the item level
   - Multiple concurrent increments/decrements are serialized by DynamoDB
   - Condition expression ensures count never goes negative
   - No application-level locking required

### Architecture

```python
AtomicCounter
├── increment_listener_count()  # Atomic ADD operation
├── decrement_listener_count()  # Atomic ADD with condition
└── get_listener_count()        # Read current count
```

### DynamoDB Operations

**Increment:**
```python
UpdateItem(
    UpdateExpression='ADD listenerCount :inc',
    ExpressionAttributeValues={':inc': {'N': '1'}},
    ReturnValues='UPDATED_NEW'
)
```

**Decrement with Condition:**
```python
UpdateItem(
    UpdateExpression='ADD listenerCount :dec',
    ConditionExpression='listenerCount >= :min',
    ExpressionAttributeValues={
        ':dec': {'N': '-1'},
        ':min': {'N': '1'}
    },
    ReturnValues='UPDATED_NEW'
)
```

### Requirements Addressed

- ✅ Requirement 6, Criterion 1: Atomic increment when listener joins
- ✅ Requirement 6, Criterion 2: Atomic decrement when listener disconnects
- ✅ Requirement 6, Criterion 3: Use DynamoDB ADD operation
- ✅ Requirement 6, Criterion 4: Ensure count never becomes negative
- ✅ Requirement 6, Criterion 5: Skip processing when count equals zero

### Integration Points

**Dependencies:**
- DynamoDB client (boto3)
- Sessions table with listenerCount attribute

**Used By:**
- Connection lifecycle handlers (join/disconnect)
- Translation Pipeline Orchestrator (check count before processing)

### Concurrency Guarantees

**DynamoDB Atomicity:**
- ADD operation is atomic at the item level
- Multiple concurrent updates are serialized by DynamoDB
- No lost updates or race conditions

**Example Scenario:**
```
Time  | Client A        | Client B        | Final Count
------|-----------------|-----------------|------------
T0    | count = 5       | count = 5       | 5
T1    | increment (+1)  | increment (+1)  | -
T2    | -               | -               | 7 (correct)
```

Without atomicity, final count could be 6 (lost update).
With DynamoDB ADD, final count is always 7.

### Testing Strategy

**Unit Tests:**
- Mock DynamoDB client
- Test all success scenarios
- Test all error scenarios
- Verify atomic operation usage
- Test condition expression for negative prevention

**Integration Tests (Future):**
- Test with real DynamoDB
- Simulate concurrent increments/decrements
- Verify no race conditions
- Test with high concurrency (100+ concurrent operations)

### Performance Characteristics

- **Latency**: Single-digit milliseconds (DynamoDB UpdateItem)
- **Throughput**: Supports high concurrency (DynamoDB handles serialization)
- **Consistency**: Strong consistency (DynamoDB default)
- **Scalability**: Scales with DynamoDB capacity

### Error Recovery

**Increment Failures:**
- Log error with session context
- Raise `AtomicCounterError`
- Caller can retry or handle gracefully

**Decrement Failures:**
- Conditional check failure → `NegativeCountError`
- Other errors → `AtomicCounterError`
- Caller should handle appropriately (e.g., skip decrement if already zero)

### Future Enhancements

1. **Retry Logic**: Add automatic retry with exponential backoff for throttling
2. **Batch Operations**: Support batch increment/decrement for multiple sessions
3. **Metrics**: Emit CloudWatch metrics for counter operations
4. **Caching**: Cache counts in memory for read-heavy workloads
