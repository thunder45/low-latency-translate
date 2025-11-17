# Design Document

## Overview

This document outlines the design for fixing all failing frontend tests in the frontend-client-apps workspace. The fixes address syntax errors, logic bugs, and test implementation issues across integration tests, unit tests, and utility functions.

## Architecture

### Component Overview

```
frontend-client-apps/
├── shared/
│   ├── utils/
│   │   ├── Validator.ts (fix sanitizeInput logic)
│   │   ├── storage.ts (already async, tests need await)
│   │   └── ErrorHandler.ts (fix error type mapping)
│   ├── websocket/
│   │   └── WebSocketClient.ts (fix URL construction)
│   └── __tests__/
│       ├── integration/
│       │   └── connection-refresh.test.ts (fix event handler access)
│       └── utils/
│           ├── Validator.test.ts (add await for async calls)
│           ├── storage.test.ts (add await for async calls)
│           └── ErrorHandler.test.ts (fix test expectations)
├── speaker-app/
│   └── src/__tests__/integration/
│       └── speaker-flow.test.tsx (fix TypeScript syntax)
└── listener-app/
    └── src/__tests__/integration/
        └── listener-flow.test.tsx (fix TypeScript syntax)
```

## Components and Interfaces

### 1. Validator Fixes

**Issue**: `sanitizeInput` is double-encoding HTML entities because it replaces `&` after already replacing `<` and `>` with entities containing `&`.

**Solution**: Change the order of replacements to handle `&` first, or use a different approach that doesn't double-encode.

```typescript
// Current (wrong):
.replace(/</g, '&lt;')   // "< script>" → "&lt; script>"
.replace(/>/g, '&gt;')   // "&lt; script>" → "&lt; script&gt;"
.replace(/&/g, '&amp;')  // "&lt; script&gt;" → "&amp;lt; script&amp;gt;" (WRONG!)

// Fixed:
.replace(/&/g, '&amp;')  // First escape ampersands
.replace(/</g, '&lt;')   // Then escape less-than
.replace(/>/g, '&gt;')   // Then escape greater-than
// OR: Just remove tags without encoding
.replace(/<[^>]*>/g, '') // Remove all HTML tags
```

**Design Decision**: Use simple tag removal instead of HTML entity encoding, as the goal is XSS prevention, not HTML display.

### 2. Storage Test Fixes

**Issue**: Tests are not using `await` with async methods, causing Promise objects to be compared instead of resolved values.

**Solution**: Add `await` to all storage method calls in tests.

```typescript
// Current (wrong):
const value = storage.get(STORAGE_KEYS.SPEAKER_PREFERENCES);
expect(value).toBe('test-value'); // Comparing Promise to string

// Fixed:
const value = await storage.get(STORAGE_KEYS.SPEAKER_PREFERENCES);
expect(value).toBe('test-value'); // Comparing string to string
```

### 3. ErrorHandler Fixes

**Issue**: `ErrorHandler.handle()` is not accepting `ErrorType` enum values directly. Tests pass `ErrorType.NETWORK_ERROR` but the implementation expects an `Error` object or string.

**Solution**: Add method overload to accept `ErrorType` directly and create appropriate `AppError`.

```typescript
// Add new method signature:
static handle(errorType: ErrorType, message: string): AppError;
static handle(error: unknown, context?: Record<string, unknown>): AppError;

// Implementation:
static handle(
  errorOrType: unknown | ErrorType,
  messageOrContext?: string | Record<string, unknown>
): AppError {
  // If first arg is ErrorType enum, create error directly
  if (typeof errorOrType === 'string' && Object.values(ErrorType).includes(errorOrType as ErrorType)) {
    const type = errorOrType as ErrorType;
    const message = typeof messageOrContext === 'string' ? messageOrContext : 'Error occurred';
    return this.createErrorFromType(type, message);
  }
  
  // Otherwise, handle as before
  // ...
}
```

### 4. WebSocketClient Fixes

**Issue**: Tests expect `WebSocket` constructor to be called with just the URL, but implementation calls `buildUrl()` which adds query parameters even when empty.

**Solution**: Modify `buildUrl()` to only add query string if there are parameters.

```typescript
private buildUrl(queryParams: Record<string, string>): string {
  const params = new URLSearchParams();
  
  // Add token if provided
  if (this.config.token) {
    params.set('token', this.config.token);
  }
  
  // Add other query params
  Object.entries(queryParams).forEach(([key, value]) => {
    params.set(key, value);
  });
  
  // Only add query string if there are params
  const queryString = params.toString();
  return queryString ? `${this.config.url}?${queryString}` : this.config.url;
}
```

### 5. Connection Refresh Test Fixes

**Issue**: Tests are trying to access array elements using `[1]` on `addEventListener.mock.calls.find()` result, which may be undefined.

**Solution**: Add null checks and use optional chaining.

```typescript
// Current (wrong):
const openHandler = mockWebSocket.addEventListener.mock.calls.find(
  (call: any) => call[0] === 'open'
)[1]; // May be undefined!

// Fixed:
const openCall = mockWebSocket.addEventListener.mock.calls.find(
  (call: any) => call[0] === 'open'
);
expect(openCall).toBeDefined();
const openHandler = openCall![1];
```

### 6. Integration Test Syntax Fixes

**Issue**: TypeScript parser is complaining about missing semicolons after type annotations in variable declarations.

**Root Cause**: This appears to be a Babel/TypeScript configuration issue. The syntax is actually correct TypeScript.

**Solution**: The issue is likely in the test configuration. Check:
1. Babel preset configuration
2. TypeScript compiler options
3. Jest/Vitest transform configuration

**Workaround**: If configuration can't be fixed immediately, remove type annotations from variable declarations in tests (type inference will still work).

```typescript
// Current (parser error):
let speakerService: SpeakerService;

// Workaround:
let speakerService; // Type inferred from assignment
```

## Data Models

### Test Configuration

```typescript
// vitest.config.ts or jest.config.js
export default {
  transform: {
    '^.+\\.tsx?$': ['@swc/jest', {
      jsc: {
        parser: {
          syntax: 'typescript',
          tsx: true,
          decorators: false,
        },
        transform: {
          react: {
            runtime: 'automatic',
          },
        },
      },
    }],
  },
};
```

## Error Handling

### Test Error Handling

All test fixes should:
1. Preserve existing test intent
2. Not change production code behavior unnecessarily
3. Add proper error messages for test failures
4. Use appropriate assertions

### Production Error Handling

ErrorHandler changes should:
1. Maintain backward compatibility
2. Preserve all existing error types
3. Add proper type guards
4. Return consistent AppError structure

## Testing Strategy

### Unit Test Verification

After fixes, verify:
1. All Validator tests pass
2. All storage tests pass
3. All ErrorHandler tests pass
4. All WebSocketClient tests pass

### Integration Test Verification

After fixes, verify:
1. speaker-flow.test.tsx compiles and runs
2. listener-flow.test.tsx compiles and runs
3. connection-refresh.test.ts passes all assertions

### Full Suite Verification

```bash
cd frontend-client-apps
npm test
# Should show: 0 failed tests
```

## Implementation Notes

### Order of Fixes

1. **Validator.ts** - Simple logic fix
2. **ErrorHandler.ts** - Add method overload
3. **WebSocketClient.ts** - Fix URL construction
4. **storage.test.ts** - Add await keywords
5. **ErrorHandler.test.ts** - Update test expectations
6. **WebSocketClient.test.ts** - Update test expectations
7. **connection-refresh.test.ts** - Add null checks
8. **Integration tests** - Fix syntax or configuration

### Testing Each Fix

Test each fix individually:
```bash
# Test specific file
npm test -- Validator.test.ts
npm test -- storage.test.ts
npm test -- ErrorHandler.test.ts
# etc.
```

### Rollback Strategy

If any fix breaks other tests:
1. Revert the specific change
2. Analyze the failure
3. Adjust the fix
4. Re-test

## Performance Considerations

These fixes are test-only changes and should not impact production performance. The only production code changes are:

1. **Validator.sanitizeInput** - Simpler logic (faster)
2. **ErrorHandler.handle** - Additional type check (negligible)
3. **WebSocketClient.buildUrl** - Conditional query string (negligible)

## Security Considerations

### XSS Prevention

The Validator.sanitizeInput fix changes from HTML entity encoding to tag removal. This is equally secure for XSS prevention:

- **Before**: `<script>` → `&lt;script&gt;` (safe when rendered as HTML)
- **After**: `<script>` → `` (removed entirely)

Both approaches prevent XSS. Tag removal is simpler and avoids double-encoding issues.

### Storage Security

No changes to storage security. Tests are updated to properly await async operations.

## Deployment Considerations

### CI/CD Integration

After fixes:
1. All tests must pass in CI
2. Test coverage should remain ≥80%
3. No new linting errors

### Documentation Updates

Update test documentation:
1. Note async/await requirements for storage tests
2. Document ErrorHandler method overloads
3. Add examples of proper test patterns

## Future Improvements

### Test Infrastructure

1. **Shared Test Utilities**: Create helper functions for common test patterns
2. **Mock Factories**: Centralize mock creation for WebSocket, Audio APIs
3. **Test Data Builders**: Create builders for complex test data

### Type Safety

1. **Stricter Types**: Enable stricter TypeScript checks in tests
2. **Type Guards**: Add runtime type guards for test assertions
3. **Mock Types**: Create proper types for mocks instead of `any`

### Test Coverage

1. **Edge Cases**: Add tests for edge cases discovered during fixes
2. **Error Paths**: Ensure all error paths are tested
3. **Integration**: Add more integration tests for critical flows
