# Design Document

## Overview

This design addresses the systematic resolution of 106 TypeScript compilation errors across the speaker-app (44 errors) and listener-app (62 errors) in the frontend-client-apps workspace. The errors fall into distinct categories that require targeted fixes:

1. **Integration Test API Mismatches** (41 errors): Tests reference outdated service APIs
2. **Component Prop Type Mismatches** (15 errors): Components use props not defined in their interfaces
3. **Service Implementation Type Errors** (12 errors): Incorrect usage of ErrorHandler and PreferenceStore
4. **JSX Style Prop Errors** (5 errors): Invalid 'jsx' prop on `<style>` elements
5. **Notification Type Enum Mismatches** (6 errors): Deprecated enum values in comparisons
6. **Unused Variable Warnings** (17 errors): Imported but unused variables
7. **Language Data Type Inconsistencies** (10 errors): Object vs string type mismatches

The design follows a bottom-up approach: fix shared library issues first, then fix app-specific issues, ensuring each layer builds on a solid foundation.

## Architecture

### Error Resolution Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    Error Resolution Flow                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: Shared Library Type Definitions                   │
│  - Fix AccessibleButton props interface                     │
│  - Verify ErrorHandler.handle() signature                   │
│  - Verify PreferenceStore API pattern                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 2: Component Prop Interfaces                         │
│  - Update SessionDisplay props                              │
│  - Update AudioVisualizer props                             │
│  - Update SessionJoiner props                               │
│  - Update SpeakerStatus props                               │
│  - Update BufferIndicator props                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 3: Service Layer Fixes                               │
│  - Fix ErrorHandler.handle() calls                          │
│  - Fix PreferenceStore instantiation                        │
│  - Add null checks for AuthService                          │
│  - Fix ErrorType enum references                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 4: JSX and Style Fixes                               │
│  - Remove invalid 'jsx' prop from style elements            │
│  - Fix notification type enum comparisons                   │
│  - Fix language data type consistency                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 5: Integration Test Updates                          │
│  - Update speaker-flow.test.tsx API calls                   │
│  - Update listener-flow.test.tsx API calls                  │
│  - Remove unused imports                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 6: Cleanup and Verification                          │
│  - Remove all unused variables                              │
│  - Verify zero TypeScript errors                            │
│  - Verify successful builds                                 │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Shared Library Type Definitions

#### AccessibleButton Props Interface

**Current Issue**: Component uses `ariaPressed` prop but interface defines `pressed` prop.

**Solution**: Add `ariaPressed` as an alias or update usage to match interface.

```typescript
// Option 1: Add ariaPressed to interface (preferred - maintains backward compatibility)
interface AccessibleButtonProps {
  onClick: () => void;
  label: string;
  ariaLabel?: string;
  pressed?: boolean;
  ariaPressed?: boolean;  // Add this
  disabled?: boolean;
  variant?: 'primary' | 'secondary' | 'danger';
  icon?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;  // Also add className support
}

// Update component to handle both props
export function AccessibleButton({
  onClick,
  label,
  ariaLabel,
  pressed,
  ariaPressed,  // Add this
  disabled = false,
  variant = 'primary',
  icon,
  children,
  className  // Add this
}: AccessibleButtonProps) {
  // Use ariaPressed if provided, otherwise fall back to pressed
  const isPressedState = ariaPressed !== undefined ? ariaPressed : pressed;
  
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel || label}
      aria-pressed={isPressedState !== undefined ? isPressedState : undefined}
      className={className}  // Apply className
      // ... rest of implementation
    >
      {icon && <span aria-hidden='true'>{icon}</span>}
      {children || label}
    </button>
  );
}
```

#### ErrorHandler API Pattern

**Current Issue**: Services call `ErrorHandler.handleError()` but the method is named `ErrorHandler.handle()`.

**Analysis**: The ErrorHandler class has a static `handle()` method, not `handleError()`.

**Solution**: Update all service calls to use `ErrorHandler.handle()`.

```typescript
// Current (incorrect):
ErrorHandler.handleError(error, ErrorType.WEBSOCKET_ERROR);

// Fixed:
const appError = ErrorHandler.handle(error, { context: 'WebSocket connection' });
```

#### PreferenceStore API Pattern

**Current Issue**: Services call `PreferenceStore.getInstance()` but PreferenceStore exports a singleton instance.

**Analysis**: PreferenceStore exports `preferenceStore` as a singleton, not a `getInstance()` method.

**Solution**: Import and use the singleton instance directly.

```typescript
// Current (incorrect):
const store = PreferenceStore.getInstance();

// Fixed:
import { preferenceStore } from '@frontend/shared/services/PreferenceStore';
// Use preferenceStore directly
await preferenceStore.saveVolume(userId, volume);
```

### 2. Component Prop Interface Updates

#### SessionDisplay Props

**Location**: `speaker-app/src/components/SessionDisplay.tsx`

**Issue**: Component rendered without required `listenerCount` and `languageDistribution` props.

**Solution**: Add missing props to component usage.

```typescript
interface SessionDisplayProps {
  sessionId: string;
  listenerCount: number;
  languageDistribution: Record<string, number>;
}

// Usage fix:
<SessionDisplay 
  sessionId={sessionId}
  listenerCount={listenerCount}
  languageDistribution={languageDistribution}
/>
```

#### AudioVisualizer Props

**Location**: `speaker-app/src/components/AudioVisualizer.tsx`

**Issue**: Component receives `getInputLevel` function but expects `inputLevel` number.

**Solution**: Change prop from function to number.

```typescript
// Current (incorrect):
<AudioVisualizer
  isTransmitting={isTransmitting}
  getInputLevel={() => audioProcessor.getInputLevel()}
/>

// Fixed:
<AudioVisualizer
  isTransmitting={isTransmitting}
  inputLevel={audioProcessor.getInputLevel()}
/>
```

#### SessionJoiner Props

**Location**: `listener-app/src/components/SessionJoiner.tsx`

**Issue**: Component uses `onSessionJoined` prop not defined in interface.

**Solution**: Add `onSessionJoined` to SessionJoinerProps interface.

```typescript
interface SessionJoinerProps {
  onSessionJoined: (sessionId: string, targetLanguage: string) => Promise<void>;
  onSendMessage?: (message: any) => void;
}
```

#### SpeakerStatus Props

**Location**: `listener-app/src/components/SpeakerStatus.tsx`

**Issue**: Component uses `isPaused` and `isMuted` props not defined in interface.

**Solution**: Add missing props to SpeakerStatusProps interface.

```typescript
interface SpeakerStatusProps {
  isPaused: boolean;
  isMuted: boolean;
}
```

#### BufferIndicator Props

**Location**: `listener-app/src/components/BufferIndicator.tsx`

**Issue**: Component rendered without required `bufferOverflow` prop.

**Solution**: Add `bufferOverflow` prop to component usage.

```typescript
<BufferIndicator
  bufferedDuration={bufferedDuration}
  isBuffering={isBuffering}
  bufferOverflow={bufferOverflow}  // Add this
/>
```

### 3. Service Layer Type Safety

#### ErrorHandler Usage Pattern

**Issue**: Services pass `ErrorType` enum as second parameter, but `handle()` expects `context` object.

**Solution**: Update all ErrorHandler calls to use correct signature.

```typescript
// Current (incorrect):
ErrorHandler.handleError(error, ErrorType.WEBSOCKET_ERROR);

// Fixed:
const appError = ErrorHandler.handle(error, {
  component: 'SpeakerService',
  operation: 'connect',
  errorType: ErrorType.WEBSOCKET_ERROR
});
```

#### PreferenceStore Instantiation

**Issue**: Services call `PreferenceStore.getInstance()` which doesn't exist.

**Solution**: Import and use the singleton instance.

```typescript
// Current (incorrect):
const preferenceStore = PreferenceStore.getInstance();

// Fixed:
import { preferenceStore } from '@frontend/shared/services/PreferenceStore';
// Use preferenceStore directly
```

#### AuthService Null Safety

**Location**: `shared/services/AuthService.ts` line 156

**Issue**: Object is possibly 'null' without null check.

**Solution**: Add null check or non-null assertion.

```typescript
// Option 1: Null check (safer)
if (result !== null) {
  // Use result
}

// Option 2: Non-null assertion (if guaranteed non-null)
const value = result!.property;
```

#### ErrorType Enum References

**Issue**: Services reference `ErrorType.AUTHENTICATION_ERROR` and `ErrorType.AUDIO_ERROR` which don't exist.

**Solution**: Use correct ErrorType enum values.

```typescript
// Current (incorrect):
ErrorType.AUTHENTICATION_ERROR
ErrorType.AUDIO_ERROR

// Fixed (use existing enum values):
ErrorType.AUTH_FAILED
ErrorType.AUDIO_PROCESSING_ERROR
```

### 4. JSX and Style Fixes

#### Style Element Props

**Issue**: Components use `<style jsx={true}>` but React doesn't support `jsx` prop on style elements.

**Solution**: Remove `jsx` prop from style elements.

```typescript
// Current (incorrect):
<style jsx={true}>
  {`
    .component { ... }
  `}
</style>

// Fixed:
<style>
  {`
    .component { ... }
  `}
</style>
```

**Affected Files**:
- `listener-app/src/components/BufferIndicator.tsx` (line 78)
- `listener-app/src/components/LanguageSelector.tsx` (line 124)
- `listener-app/src/components/PlaybackControls.tsx` (line 145)
- `listener-app/src/components/SessionJoiner.tsx` (line 106)
- `listener-app/src/components/SpeakerStatus.tsx` (line 106)

#### Notification Type Enum Alignment

**Issue**: Components compare against deprecated notification type values.

**Solution**: Update to use current NotificationType enum values.

```typescript
// Current (incorrect) - BroadcastControlsContainer:
if (notification.type === 'listenerJoined' || notification.type === 'listenerLeft')

// Fixed (use correct enum values):
if (notification.type === NotificationType.LISTENER_JOINED || 
    notification.type === NotificationType.LISTENER_LEFT)

// Current (incorrect) - PlaybackControlsContainer:
if (notification.type === 'speakerPaused')
else if (notification.type === 'speakerResumed')
else if (notification.type === 'speakerMuted')
else if (notification.type === 'speakerUnmuted')

// Fixed:
if (notification.type === NotificationType.BROADCAST_PAUSED)
else if (notification.type === NotificationType.BROADCAST_RESUMED)
else if (notification.type === NotificationType.BROADCAST_MUTED)
else if (notification.type === NotificationType.BROADCAST_UNMUTED)
```

### 5. Integration Test Updates

#### Speaker Flow Test Updates

**Location**: `speaker-app/src/__tests__/integration/speaker-flow.test.tsx`

**Issues**:
1. Service config includes non-existent `authToken` property
2. Tests call non-existent methods: `createSession()`, `startAudioTransmission()`, `pauseBroadcast()`, `resumeBroadcast()`
3. Tests access non-existent `session` property (should be `sessionId`)
4. Tests access non-existent `issue` property on QualityWarning

**Solution**: Update tests to match current service API.

```typescript
// Config fix:
const service = new SpeakerService({
  wsUrl: 'ws://localhost:3000',
  // Remove authToken - not in SpeakerServiceConfig
});

// Method call fixes:
// Instead of: await service.createSession(...)
// Use current API pattern from SpeakerService

// State property fixes:
// Instead of: state.session.sessionId
// Use: state.sessionId

// QualityWarning fix:
// Ensure QualityWarning objects include 'issue' property
```

#### Listener Flow Test Updates

**Location**: `listener-app/src/__tests__/integration/listener-flow.test.tsx`

**Issues**:
1. Service config missing required `sessionId` and `targetLanguage` properties
2. Tests call non-existent methods: `joinSession()`, `pausePlayback()`, `resumePlayback()`, `setMuted()`, `disconnect()`
3. Tests access non-existent `session` property (should be `sessionId`)

**Solution**: Update tests to match current service API.

```typescript
// Config fix:
const service = new ListenerService({
  wsUrl: 'ws://localhost:3000',
  sessionId: 'test-session-123',
  targetLanguage: 'es'
});

// Method call fixes:
// Update to use current ListenerService API

// State property fixes:
// Instead of: state.session.sessionId
// Use: state.sessionId
```

### 6. Language Data Type Consistency

**Issue**: ListenerApp passes language objects `{ code: string, name: string }` but LanguageSelector expects string codes.

**Solution**: Extract language codes before passing to LanguageSelector.

```typescript
// Current (incorrect):
const languages = [
  { code: 'en', name: 'English' },
  { code: 'es', name: 'Spanish' },
  // ...
];
<LanguageSelector languages={languages} />

// Fixed:
const languageCodes = languages.map(lang => lang.code);
<LanguageSelector languages={languageCodes} />

// Or update LanguageSelector to accept language objects
```

### 7. Unused Variable Cleanup

**Strategy**: Remove all unused imports and variable declarations.

**Categories**:
1. **Unused imports**: `render`, `screen`, `fireEvent`, `useEffect` imported but never used
2. **Unused variables**: `inputVolume`, `playbackVolume`, `onAudioChunk`, `maxDuration`, `state`, `message`, `appError`

**Solution**: Remove or use these variables.

```typescript
// Remove unused imports:
// Before:
import { render, screen, fireEvent } from '@testing-library/react';

// After (if not used):
// Remove the import entirely

// Remove unused variables:
// Before:
const inputVolume = 75;
const playbackVolume = 80;

// After (if not used):
// Remove the declarations
```

## Data Models

### ErrorHandler Call Pattern

```typescript
// Standard error handling pattern
try {
  // Operation that might fail
  await riskyOperation();
} catch (error) {
  const appError = ErrorHandler.handle(error, {
    component: 'ServiceName',
    operation: 'operationName',
    additionalContext: 'value'
  });
  
  // Handle the error
  console.error(appError.message);
  // Show user message: appError.userMessage
}
```

### PreferenceStore Usage Pattern

```typescript
import { preferenceStore } from '@frontend/shared/services/PreferenceStore';

// Save preference
await preferenceStore.saveVolume(userId, volume);

// Get preference
const savedVolume = await preferenceStore.getVolume(userId);
if (savedVolume !== null) {
  setVolume(savedVolume);
} else {
  setVolume(preferenceStore.getDefaultVolume());
}
```

### Component Prop Patterns

```typescript
// AccessibleButton with all props
<AccessibleButton
  onClick={handleClick}
  label="Button Text"
  ariaLabel="Accessible label"
  ariaPressed={isPressed}
  className="custom-class"
  variant="primary"
  disabled={false}
>
  Button Content
</AccessibleButton>

// SessionDisplay with required props
<SessionDisplay
  sessionId={sessionId}
  listenerCount={listenerCount}
  languageDistribution={languageDistribution}
/>

// AudioVisualizer with number prop
<AudioVisualizer
  isTransmitting={isTransmitting}
  inputLevel={currentInputLevel}
/>
```

## Error Handling

### TypeScript Compilation Errors

**Strategy**: Fix errors in order of dependency:
1. Shared library first (affects both apps)
2. Component interfaces (affects component usage)
3. Service implementations (affects business logic)
4. Integration tests (affects test suite)

### Null Safety Errors

**Pattern**: Add explicit null checks or non-null assertions.

```typescript
// Null check pattern
if (value !== null && value !== undefined) {
  // Safe to use value
  processValue(value);
}

// Non-null assertion (use only when guaranteed non-null)
const result = getValue()!;
```

### Type Mismatch Errors

**Pattern**: Ensure types match at call sites.

```typescript
// Function expects string, but receives string | null
function processLanguage(code: string) { ... }

// Fix with null check:
if (languageCode !== null) {
  processLanguage(languageCode);
}

// Or provide default:
processLanguage(languageCode ?? 'en');
```

## Testing Strategy

### Verification Approach

1. **Incremental Verification**: After each phase, run TypeScript compiler to verify error count decreases
2. **Build Verification**: After all fixes, run full build to ensure zero errors
3. **Component Testing**: Verify components render without errors
4. **Integration Testing**: Verify updated tests pass

### Test Commands

```bash
# Check TypeScript errors without building
npm run type-check --workspace=speaker-app
npm run type-check --workspace=listener-app

# Build individual workspaces
npm run build:shared
npm run build:speaker
npm run build:listener

# Build all workspaces
npm run build:all

# Run tests
npm run test --workspace=speaker-app
npm run test --workspace=listener-app
```

### Success Criteria

- Zero TypeScript compilation errors in all workspaces
- All builds complete successfully
- dist/ directories contain compiled output
- No regression in existing functionality

## Implementation Notes

### Order of Operations

1. **Shared Library Fixes First**: These affect both apps, so fix them first to reduce cascading errors
2. **Component Interfaces Next**: Update prop interfaces before fixing usage sites
3. **Service Layer**: Fix service implementations after interfaces are correct
4. **Integration Tests Last**: Update tests after all production code is fixed

### Risk Mitigation

1. **Incremental Changes**: Make small, focused changes and verify after each
2. **Type Safety**: Maintain strict TypeScript checking throughout
3. **Backward Compatibility**: Ensure fixes don't break existing functionality
4. **Test Coverage**: Update tests to match new APIs

### Performance Considerations

- No performance impact expected - these are type-level fixes only
- Build times should remain the same or improve slightly with fewer errors

## Deployment Considerations

### Build Process

- All fixes are compile-time only
- No runtime behavior changes expected
- Existing build pipeline remains unchanged

### Rollout Strategy

1. Fix all TypeScript errors in development
2. Verify builds succeed locally
3. Commit changes and verify CI/CD pipeline succeeds
4. Deploy to staging for integration testing
5. Deploy to production after verification

## Future Enhancements

### Type Safety Improvements

1. **Stricter Type Checking**: Enable additional TypeScript strict flags
2. **Prop Validation**: Add runtime prop validation with PropTypes or Zod
3. **API Type Generation**: Generate TypeScript types from backend API schemas
4. **Test Type Safety**: Improve type safety in test files

### Code Quality

1. **ESLint Rules**: Add rules to catch unused variables automatically
2. **Pre-commit Hooks**: Run TypeScript checks before commits
3. **CI/CD Integration**: Fail builds on TypeScript errors
4. **Documentation**: Document component prop interfaces and service APIs
