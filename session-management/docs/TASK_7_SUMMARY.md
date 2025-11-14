# Task 7: Implement Connection Timeout Handling

## Task Description
Implemented connection timeout detection and cleanup to automatically close idle WebSocket connections and free up resources.

## Task Instructions
Add timeout detection to identify and close connections idle for >120 seconds:
- Create timeout_handler Lambda triggered by EventBridge (every 60 seconds)
- Query all connections and check lastActivityTime
- Send connectionTimeout message before closing
- Trigger disconnect handler for cleanup
- Emit CloudWatch metrics for timeouts

## Task Tests
```bash
python -m pytest tests/unit/test_timeout_handler.py -v
```

**Results**: 15 tests passed in 0.39s
- ✅ Send timeout message tests (3 tests)
- ✅ Close connection tests (3 tests)
- ✅ Trigger disconnect handler tests (2 tests)
- ✅ Check and close idle connections tests (4 tests)
- ✅ Lambda handler tests (3 tests)

**Coverage**: 100% of timeout handler functions

## Task Solution

### Files Created
1. **session-management/lambda/timeout_handler/__init__.py** - Module initialization
2. **session-management/lambda/timeout_handler/handler.py** - Timeout handler Lambda (300+ lines)
3. **session-management/tests/unit/test_timeout_handler.py** - Comprehensive unit tests (15 tests)

### Files Modified
1. **session-management/shared/data_access/connections_repository.py**
   - Added `scan_all_connections()` method to query all connections

### Key Implementation Decisions

**1. Periodic Trigger Approach**
- EventBridge scheduled rule triggers Lambda every 60 seconds
- Scans all connections to check for idle ones
- More efficient than per-connection timers
- Rationale: Centralized timeout management, easier to monitor

**2. Idle Timeout Threshold**
- Default: 120 seconds (2 minutes)
- Configurable via CONNECTION_IDLE_TIMEOUT_SECONDS environment variable
- Uses lastActivityTime or connectedAt as fallback
- Rationale: Balance between keeping connections alive and freeing resources

**3. Graceful Shutdown Flow**
1. Send connectionTimeout message to client (best effort)
2. Close WebSocket connection via API Gateway Management API
3. Trigger disconnect handler Lambda for cleanup (async)
4. Emit CloudWatch metrics

**4. Error Handling**
- GoneException (connection already closed) treated as success
- Failed message sends logged but don't block connection close
- Disconnect handler invoked asynchronously (fire-and-forget)
- Rationale: Ensure cleanup happens even if client is unresponsive

**5. Metrics and Observability**
- ConnectionTimeout metric (by role and reason)
- ConnectionsChecked, IdleConnectionsDetected, ConnectionsClosed
- Structured logging with correlation IDs
- Separate tracking for speaker vs listener timeouts

### Message Format

**connectionTimeout Message**:
```json
{
  "type": "connectionTimeout",
  "message": "Connection closed due to inactivity",
  "idleSeconds": 120,
  "timestamp": 1699500000000
}
```

### Integration Points

**1. EventBridge Rule** (to be added in CDK - Task 10):
- Schedule: rate(1 minute)
- Target: timeout_handler Lambda
- Permissions: lambda:InvokeFunction

**2. IAM Permissions** (to be added in CDK - Task 10):
- execute-api:ManageConnections (API Gateway Management API)
- execute-api:Invoke (API Gateway Management API)
- dynamodb:Scan (Connections table)
- lambda:InvokeFunction (disconnect_handler)

**3. Environment Variables**:
- CONNECTION_IDLE_TIMEOUT_SECONDS (default: 120)
- API_GATEWAY_ENDPOINT (required)
- CONNECTIONS_TABLE (required)
- DISCONNECT_HANDLER_FUNCTION (required)

### Performance Considerations

**1. Scan Efficiency**
- Current implementation scans all connections
- For production with >1000 connections, should use pagination
- Consider adding lastActivityTime GSI for efficient queries
- Rationale: Simple implementation for MVP, optimize later if needed

**2. Lambda Configuration**
- Memory: 256 MB (sufficient for scanning and API calls)
- Timeout: 60 seconds (matches trigger interval)
- Concurrency: 1 (only one instance should run at a time)

**3. Async Disconnect Handler**
- Invoked asynchronously to avoid blocking timeout check
- Ensures cleanup happens even if timeout handler times out
- Rationale: Separation of concerns, better reliability

### CloudWatch Metrics

**Emitted Metrics**:
- `ConnectionTimeout` (Count, dimensions: Role, Reason)
- `ConnectionsChecked` (Count)
- `IdleConnectionsDetected` (Count)
- `ConnectionsClosed` (Count)

**Recommended Alarms**:
- Warning: IdleConnectionsDetected >10/minute (may indicate client issues)
- Critical: ConnectionsClosed >50/minute (may indicate system issues)

### Testing Strategy

**Unit Tests**:
- Message sending (success, GoneException, errors)
- Connection closing (success, already gone, errors)
- Disconnect handler triggering
- Idle connection detection logic
- Lambda handler (success, missing config, errors)

**Integration Tests** (to be added in Task 11):
- End-to-end timeout flow with real connections
- Verify disconnect handler is triggered
- Verify session cleanup occurs
- Test with multiple idle connections

### Next Steps

1. Add EventBridge rule in CDK (Task 10)
2. Add IAM permissions in CDK (Task 10)
3. Configure environment variables in CDK (Task 10)
4. Integration testing (Task 11)
5. Monitor timeout metrics in production
