# Implementation Plan

- [x] 1. Fix Validator.sanitizeInput implementation
  - Update `frontend-client-apps/shared/utils/Validator.ts`
  - Change sanitizeInput to remove HTML tags instead of encoding
  - Use `.replace(/<[^>]*>/g, '')` to strip all tags
  - _Requirements: 2.1_

- [x] 2. Fix ErrorHandler to accept ErrorType enum
  - Update `frontend-client-apps/shared/utils/ErrorHandler.ts`
  - Add method overload to accept ErrorType directly
  - Create `createErrorFromType` helper method
  - Map each ErrorType to appropriate AppError properties
  - _Requirements: 4.1, 4.2, 4.3_

- [x] 3. Fix WebSocketClient URL construction
  - Update `frontend-client-apps/shared/websocket/WebSocketClient.ts`
  - Modify `buildUrl` to only add query string if params exist
  - Return base URL when no query parameters
  - _Requirements: 5.1, 5.2_

- [x] 4. Fix storage tests to use await
  - Update `frontend-client-apps/shared/utils/__tests__/storage.test.ts`
  - Add `await` to all `storage.get()` calls
  - Add `await` to all `storage.set()` calls
  - Add `await` to all `storage.remove()` calls
  - Add `await` to all `storage.clear()` calls
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 5. Fix ErrorHandler tests expectations
  - Update `frontend-client-apps/shared/utils/__tests__/ErrorHandler.test.ts`
  - Update all test calls to use ErrorType enum as first parameter
  - Update assertions to check for correct error type
  - Update assertions to check for correct user messages
  - _Requirements: 4.4_

- [x] 6. Fix WebSocketClient tests expectations
  - Update `frontend-client-apps/shared/websocket/__tests__/WebSocketClient.test.ts`
  - Update URL expectations to account for query parameters
  - Fix test setup to provide proper config
  - _Requirements: 5.3_

- [x] 7. Fix connection refresh tests
  - Update `frontend-client-apps/shared/__tests__/integration/connection-refresh.test.ts`
  - Add null checks before accessing array elements
  - Use optional chaining for event handler access
  - Add expect().toBeDefined() assertions
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 8. Fix integration test syntax errors
  - Check `frontend-client-apps/speaker-app/src/__tests__/integration/speaker-flow.test.tsx`
  - Check `frontend-client-apps/listener-app/src/__tests__/integration/listener-flow.test.tsx`
  - Verify TypeScript/Babel configuration
  - Fix any configuration issues or use type inference workaround
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 9. Run full test suite verification
  - Execute `npm test` in frontend-client-apps directory
  - Verify all tests pass (0 failures)
  - Check test output for any warnings
  - _Requirements: 7.1, 7.2, 7.3_
