# WebSocket Test Mocking Improvements Specification

## Status: 📋 READY FOR IMPLEMENTATION

**Created:** November 17, 2025

## Overview

This specification addresses the remaining 16 test failures in the frontend test suite by improving WebSocket test mocking infrastructure. The failures are primarily due to complex WebSocket async behavior, timeout issues, and insufficient mock implementations.

## Objectives

### Primary Goal
Achieve 100% test pass rate (119/119 tests passing) by fixing all remaining WebSocket-related test failures.

### Success Metrics
- **Test Pass Rate:** 100% (currently 86.6%)
- **Test Failures:** 0 (currently 16)
- **Test Timeouts:** 0
- **Test Execution Time:** <30 seconds total

## Problem Statement

After the initial frontend-test-fixes effort, 16 tests remain failing:

**Breakdown by Category:**
- WebSocket connection/reconnection: 4 failures
- ListenerService event handling: 8 failures
- Integration tests: 2 failures
- Keyboard shortcuts: 1 failure
- Validator: 1 failure

**Root Causes:**
1. Insufficient WebSocket mocking (no async simulation)
2. Missing emit() method on wsClient mock
3. Incorrect state transition expectations
4. Event dispatching issues in test environment
5. Space normalization inconsistency

## Solution Approach

### 1. Create Sophisticated MockWebSocket Class
- Properly simulate async connection behavior
- Support both property handlers and addEventListener
- Provide test helpers for event triggering
- Reusable across all WebSocket tests

### 2. Add EventEmitter Pattern to Mocks
- Create MockWebSocketClient with emit() method
- Enable proper event-driven testing
- Support all WebSocket event types

### 3. Fix State Management
- Ensure correct state transitions (connected → disconnected → failed)
- Properly handle heartbeat timeouts
- Correctly track reconnection attempts

### 4. Improve Test Patterns
- Use proper async/await
- Add vi.waitFor for async assertions
- Dispatch events on correct targets (document vs window)

## Requirements Summary

1. ✅ Fix WebSocketClient connection tests (4 tests)
2. ✅ Fix WebSocketClient heartbeat and reconnection tests (2 tests)
3. ✅ Fix connection refresh integration test (1 test)
4. ✅ Fix ListenerService WebSocket event tests (5 tests)
5. ✅ Fix speaker flow integration test (1 test)
6. ✅ Fix listener flow language switch test (1 test)
7. ✅ Fix listener flow buffer management test (1 test)
8. ✅ Fix keyboard shortcuts integration test (1 test)
9. ✅ Fix Validator sanitize input test (1 test)
10. ✅ Achieve 100% test suite stability

## Implementation Plan

**Total Tasks:** 15

**Estimated Effort:** 4-6 hours

**Task Breakdown:**
1. Create MockWebSocket class (foundation)
2. Fix WebSocketClient tests (4 tasks)
3. Fix ListenerService tests (4 tasks)
4. Fix integration tests (3 tasks)
5. Fix remaining issues (2 tasks)
6. Full suite verification (1 task)

## Testing Strategy

### Incremental Testing
Test after each fix to ensure no regressions:
```bash
# After each task
npm test -- <test-file>

# Verify no regressions
npm test
```

### Success Criteria
- All 119 tests passing
- No timeouts
- Execution time <30 seconds
- No warnings or errors

## Documentation

- **Requirements:** `.kiro/specs/websocket-test-mocking-improvements/requirements.md`
- **Design:** `.kiro/specs/websocket-test-mocking-improvements/design.md`
- **Tasks:** `.kiro/specs/websocket-test-mocking-improvements/tasks.md`

## Related Specifications

- `frontend-test-fixes` - Initial test fixes (completed)
- `frontend-build-and-configuration` - Build system setup
- `frontend-typescript-error-resolution` - TypeScript configuration

## Next Steps

1. Open `.kiro/specs/websocket-test-mocking-improvements/tasks.md`
2. Click "Start task" next to Task 1
3. Follow the implementation plan sequentially
4. Test after each task
5. Verify full suite passes after Task 15

---

**Specification Owner:** Development Team  
**Created:** November 17, 2025  
**Status:** Ready for Implementation
