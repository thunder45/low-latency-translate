# Authentication Cleanup - Steering Document for Implementation

**Purpose**: Guide Kiro through implementing the authentication cleanup tasks in optimal sequence  
**Reference Documents**: requirements.md, design.md, tasks.md  
**Total Effort**: 16-21 hours over 5-6 days  
**Current Working Directory**: /Volumes/workplace/low-latency-translate

## Quick Reference

**Key Files Modified**:
- `frontend-client-apps/shared/services/TokenStorage.ts` - Encryption service
- `frontend-client-apps/speaker-app/src/components/AuthGuard.tsx` - Route protection
- `frontend-client-apps/shared/utils/SessionCreationOrchestrator.ts` - Session creation
- `session-management/lambda/authorizer/handler.py` - JWT validation

**Test Files to Create**:
- `frontend-client-apps/shared/__tests__/TokenStorage.test.ts`
- `frontend-client-apps/speaker-app/src/components/__tests__/AuthGuard.test.tsx`
- `frontend-client-apps/shared/__tests__/AuthError.test.ts`

**Important**: All test templates are in design.md. Use them as starting points.

---

## Phase 1: Setup & Quick Fixes (1-2 hours)

**Goal**: Remove orphaned code, create infrastructure, fix simple bugs  
**Tasks**: 1, 2 (with 2.6), 5, 6, 7, 7.5, 8  
**Risk**: Low

### Task Sequence

#### 1.1 Remove OAuth2 [15 min] - Task 1

```bash
# Navigate to project root
cd /Volumes/workplace/low-latency-translate

# Verify file has no references
grep -r "from.*AuthService\|import.*AuthService" frontend-client-apps/ \
  --include="*.ts" --include="*.tsx" \
  --exclude-dir=node_modules | grep -v CognitoAuthService

# Should return empty (only CognitoAuthService should appear)

# Delete the file
git rm frontend-client-apps/shared/services/AuthService.ts

# Verify tests still pass
cd frontend-client-apps
npm test

# Commit
git commit -m "Remove orphaned OAuth2 AuthService (Req 1)"
```

**Validation**: ✅ All tests pass, no import errors

---

#### 1.2 Create Constants File [30 min] - Task 2

**Create**: `frontend-client-apps/shared/constants/auth.ts`

**Use this exact content** (from design.md):
```typescript
/**
 * Authentication constants
 */
export const AUTH_CONSTANTS = {
  /** Time before expiry when tokens should be refreshed (5 minutes) */
  TOKEN_REFRESH_THRESHOLD_MS: 5 * 60 * 1000,
  
  /** Connection timeout for WebSocket (5 seconds) */
  CONNECTION_TIMEOUT_MS: 5000,
  
  /** Maximum number of authentication retry attempts */
  MAX_AUTH_RETRY_ATTEMPTS: 1,
  
  /** Minimum encryption key length (256-bit = 32 bytes) */
  ENCRYPTION_KEY_MIN_LENGTH: 32,
  
  /** PBKDF2 iterations for key derivation */
  PBKDF2_ITERATIONS: 100000,
  
  /** Encryption initialization vector length */
  ENCRYPTION_IV_LENGTH: 12,
  
  /** Application salt for PBKDF2 (can be public) */
  APPLICATION_SALT: 'low-latency-translate-v1',
} as const;

/**
 * WebSocket close codes
 * @see https://developer.mozilla.org/en-US/docs/Web/API/CloseEvent/code
 */
export enum WebSocketCloseCode {
  /** Normal closure; the connection successfully completed */
  NORMAL_CLOSURE = 1000,
  
  /** Abnormal closure; connection dropped without close frame */
  ABNORMAL_CLOSURE = 1006,
  
  /** Policy violation; used for authentication failures */
  POLICY_VIOLATION = 1008,
  
  /** Internal server error */
  SERVER_ERROR = 1011,
}

/**
 * Required environment variables (for documentation)
 */
export const REQUIRED_ENV_VARS = {
  BACKEND: ['USER_POOL_ID', 'CLIENT_ID', 'REGION'],
  FRONTEND: ['VITE_COGNITO_USER_POOL_ID', 'VITE_COGNITO_CLIENT_ID', 'VITE_AWS_REGION', 'VITE_ENCRYPTION_KEY'],
} as const;
```

**Also update** `frontend-client-apps/speaker-app/.env.example`:
```bash
# AWS Cognito Configuration
VITE_COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
VITE_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
VITE_AWS_REGION=us-east-1

# Encryption key for token storage (32+ characters)
VITE_ENCRYPTION_KEY=your-secure-32-character-key-here

# WebSocket API
VITE_WEBSOCKET_URL=wss://your-api-gateway-url
```

**Commit**:
```bash
git add frontend-client-apps/shared/constants/auth.ts
git add frontend-client-apps/speaker-app/.env.example
git commit -m "Create authentication constants and document env vars (Req 5.4, 6.1, 8.5)"
```

**Validation**: ✅ Constants file created, .env.example updated

---

#### 1.3 Fix Token Expiry Calculation [15 min] - Task 5

**File**: `frontend-client-apps/shared/utils/SessionCreationOrchestrator.ts`

**Find** (around line 115):
```typescript
const expiresAt = Date.now() + (tokens.expiresIn * 1000);
const timeUntilExpiry = expiresAt - Date.now();
```

**Replace with**:
```typescript
// Use stored expiresAt directly (absolute timestamp, not duration)
const timeUntilExpiry = tokens.expiresAt - Date.now();
```

**Validation**: Check interface definition confirms `expiresAt` is absolute timestamp

**Commit**:
```bash
git add frontend-client-apps/shared/utils/SessionCreationOrchestrator.ts
git commit -m "Fix token expiry calculation to use absolute timestamp (Req 8.1)"
```

---

#### 1.4 Add WebSocket State Validation [15 min] - Task 6

**File**: `frontend-client-apps/shared/utils/SessionCreationOrchestrator.ts`

**Find** the `sendCreationRequest` method, locate the send call:
```typescript
this.wsClient.send({
  action: 'createSession',
  sourceLanguage: this.config.sourceLanguage,
  qualityTier: this.config.qualityTier,
});
```

**Wrap in try-catch** (see design.md Component 4 for full example):
```typescript
try {
  // Validate connection state before sending
  if (!wsClient.isConnected()) {
    throw new Error('WebSocket not connected');
  }
  
  wsClient.send({
    action: 'createSession',
    sourceLanguage: this.config.sourceLanguage,
    qualityTier: this.config.qualityTier,
  });
} catch (error) {
  clearTimeout(timeoutId);
  reject(error);
}
```

**Commit**:
```bash
git commit -am "Add WebSocket state validation before send (Req 8.2, 6.6)"
```

---

#### 1.5 Remove Dynamic Imports [15 min] - Task 7

**File**: `frontend-client-apps/speaker-app/src/components/LoginForm.tsx`

**Find**:
```typescript
const { CognitoAuthService } = await import('../../../shared/services/CognitoAuthService');
const { TokenStorage } = await import('../../../shared/services/TokenStorage');
```

**Replace with static imports at top of file**:
```typescript
import { CognitoAuthService } from '../../../shared/services/CognitoAuthService';
import { TokenStorage } from '../../../shared/services/TokenStorage';
```

**Remove the await** from the function.

**Commit**:
```bash
git commit -am "Remove dynamic imports from authentication path (Req 5.5, 6.3)"
```

---

#### 1.6 Centralize TokenStorage Init [30 min] - Task 7.5

**File**: `frontend-client-apps/speaker-app/src/main.tsx`

**Add before rendering**:
```typescript
import { tokenStorage } from '../shared/services/TokenStorage';
import { getConfig } from '../shared/utils/config';

async function initializeApp() {
  try {
    const config = getConfig();
    await tokenStorage.initialize(config.encryptionKey);
    console.log('[App] TokenStorage initialized');
  } catch (error) {
    console.error('[App] Failed to initialize TokenStorage:', error);
    // Still render app, components will handle initialization if needed
  }
}

// Initialize before rendering
initializeApp().then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}).catch(error => {
  console.error('[App] Initialization failed:', error);
  // Render error state or fallback
});
```

**Then remove duplicate initializations** from LoginForm.tsx (keep the tokenStorage.initialize call but it will be a no-op if already initialized).

**Commit**:
```bash
git commit -am "Centralize TokenStorage initialization in app startup (Req 6.2, 6.8)"
```

---

#### 1.7 Use Close Code Enum [15 min] - Task 8

**File**: `frontend-client-apps/shared/websocket/WebSocketClient.ts`

**Add import at top**:
```typescript
import { WebSocketCloseCode } from '../constants/auth';
```

**Find and replace**:
```typescript
// Before:
if (event.code === 1008) {

// After:
if (event.code === WebSocketCloseCode.POLICY_VIOLATION) {
```

**Replace all occurrences**: 1000 → NORMAL_CLOSURE, 1006 → ABNORMAL_CLOSURE, 1008 → POLICY_VIOLATION

**Commit**:
```bash
git commit -am "Use WebSocketCloseCode enum instead of magic numbers (Req 5.6, 8.4)"
```

---

### Phase 1 Checkpoint

**Validation Commands**:
```bash
cd frontend-client-apps

# Verify all tests still pass
npm test

# Check for any remaining magic numbers
grep -r "5 \* 60 \* 1000\|300000" shared/ speaker-app/src/ --include="*.ts" --include="*.tsx"

# Should find very few or none
```

**Expected State**:
- ✅ AuthService.ts deleted
- ✅ Constants file created
- ✅ Token expiry bug fixed
- ✅ WebSocket state validation added
- ✅ Dynamic imports removed
- ✅ TokenStorage centralized
- ✅ Close codes use enum
- ✅ All tests passing

**Commit message for phase**:
```bash
git commit --allow-empty -m "Phase 1 complete: Setup and quick fixes"
```

---

## Phase 2: Security Implementation (2-3 hours)

**Goal**: Implement PBKDF2 and concurrent refresh protection  
**Tasks**: 3 (all sub-tasks), 4 (all sub-tasks)  
**Risk**: Medium (security-critical code)

### Task Sequence

#### 2.1 Implement PBKDF2 in TokenStorage [2 hours] - Task 3

**File**: `frontend-client-apps/shared/services/TokenStorage.ts`

**Step 1**: Add constants import:
```typescript
import { AUTH_CONSTANTS } from '../constants/auth';
```

**Step 2**: Add deriveKey method (before initialize):
```typescript
/**
 * Derive encryption key from passphrase using PBKDF2
 */
private async deriveKey(passphrase: string, salt: Uint8Array): Promise<CryptoKey> {
  const encoder = new TextEncoder();
  
  // Import passphrase as key material
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    encoder.encode(passphrase),
    'PBKDF2',
    false,
    ['deriveKey']
  );
  
  // Derive encryption key
  return crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt,
      iterations: AUTH_CONSTANTS.PBKDF2_ITERATIONS,
      hash: 'SHA-256',
    },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  );
}
```

**Step 3**: Update initialize method:
```typescript
async initialize(keyString: string): Promise<void> {
  if (!keyString || keyString.length < AUTH_CONSTANTS.ENCRYPTION_KEY_MIN_LENGTH) {
    throw new StorageError(
      STORAGE_ERROR_CODES.MISSING_KEY,
      `Encryption key must be at least ${AUTH_CONSTANTS.ENCRYPTION_KEY_MIN_LENGTH} characters`
    );
  }

  try {
    // Use fixed application salt
    const salt = new TextEncoder().encode(AUTH_CONSTANTS.APPLICATION_SALT);
    this.encryptionKey = await this.deriveKey(keyString, salt);
  } catch (error) {
    throw new StorageError(
      STORAGE_ERROR_CODES.ENCRYPTION_FAILED,
      `Failed to initialize encryption: ${error instanceof Error ? error.message : 'Unknown error'}`
    );
  }
}
```

**Step 4**: Add token validation in storeTokens:
```typescript
async storeTokens(tokens: AuthTokens): Promise<void> {
  // ... existing storage check ...

  try {
    // Validate tokens
    if (!tokens.idToken || !tokens.accessToken || !tokens.refreshToken) {
      throw new StorageError(
        STORAGE_ERROR_CODES.INVALID_DATA,
        'Invalid tokens: missing required fields'
      );
    }

    // Validate expiresAt is absolute timestamp in future
    if (!tokens.expiresAt || tokens.expiresAt <= Date.now()) {
      throw new StorageError(
        STORAGE_ERROR_CODES.INVALID_DATA,
        'Invalid tokens: expiresAt must be in the future'
      );
    }

    // ... rest of encryption logic ...
  }
}
```

**Commit**:
```bash
git commit -am "Implement PBKDF2 key derivation and token validation (Req 5.1, 5.2, 5.9)"
```

---

#### 2.2 Add Concurrent Refresh Protection [45 min] - Task 4

**File**: `frontend-client-apps/speaker-app/src/components/AuthGuard.tsx`

**Step 1**: Add useRef at top of component:
```typescript
const refreshPromiseRef = useRef<Promise<boolean> | null>(null);
```

**Step 2**: Replace refreshTokens function:
```typescript
/**
 * Refresh authentication tokens with concurrent protection
 */
const refreshTokens = async (refreshToken: string): Promise<boolean> => {
  // Return existing promise if refresh already in progress
  if (refreshPromiseRef.current) {
    console.log('[AuthGuard] Refresh already in progress, reusing promise');
    return refreshPromiseRef.current;
  }

  // Create new refresh promise
  refreshPromiseRef.current = performRefresh(refreshToken);

  try {
    return await refreshPromiseRef.current;
  } finally {
    refreshPromiseRef.current = null;
  }
};

/**
 * Perform actual token refresh
 */
const performRefresh = async (refreshToken: string): Promise<boolean> => {
  try {
    const config = getConfig();

    if (!config.cognito) {
      console.error('[AuthGuard] Cognito not configured');
      return false;
    }

    const authService = new CognitoAuthService({
      userPoolId: config.cognito.userPoolId,
      clientId: config.cognito.clientId,
      region: config.awsRegion,
    });

    const tokens = await authService.refreshTokens(refreshToken);
    const tokenStorage = TokenStorage.getInstance();
    await tokenStorage.initialize(config.encryptionKey);

    await tokenStorage.storeTokens({
      accessToken: tokens.accessToken,
      idToken: tokens.idToken,
      refreshToken: tokens.refreshToken,
      expiresAt: Date.now() + tokens.expiresIn * 1000,
    });

    // Schedule next refresh
    scheduleTokenRefresh(
      new Date(Date.now() + tokens.expiresIn * 1000),
      tokens.refreshToken
    );

    return true;
  } catch (error) {
    console.error('[AuthGuard] Token refresh failed:', error);
    
    // Clear stored tokens on refresh failure
    try {
      const config = getConfig();
      const tokenStorage = TokenStorage.getInstance();
      await tokenStorage.initialize(config.encryptionKey);
      await tokenStorage.clearTokens();
    } catch (clearError) {
      console.error('[AuthGuard] Failed to clear tokens:', clearError);
    }
    
    return false;
  }
};
```

**Commit**:
```bash
git commit -am "Add concurrent refresh protection to AuthGuard (Req 5.3, 3.6)"
```

---

### Phase 2 Checkpoint

**Validation Commands**:
```bash
# Run tests
npm test

# Check PBKDF2 is imported
grep -n "PBKDF2" frontend-client-apps/shared/services/TokenStorage.ts

# Check concurrent protection
grep -n "refreshPromiseRef" frontend-client-apps/speaker-app/src/components/AuthGuard.tsx

# Both should return results
```

**Expected State**:
- ✅ PBKDF2 key derivation implemented
- ✅ Token validation before storage
- ✅ Concurrent refresh protection added
- ✅ All constants imported and used
- ✅ Tests still passing

---

## Phase 3: Test Security Changes (4-5 hours)

**Goal**: Validate TokenStorage encryption and security  
**Tasks**: 10.1-10.6  
**Risk**: Low (only adding tests)

### Implementation Guide

**Create**: `frontend-client-apps/shared/__tests__/TokenStorage.test.ts`

**Use the complete test template from design.md** (search for "TokenStorage.test.ts" in design.md)

**Key Tests to Include** (checklist):
- [ ] Test PBKDF2 key derivation
- [ ] Test encryption produces different output
- [ ] Test decryption returns original input
- [ ] Test unique IV per encryption
- [ ] Test expired token rejection
- [ ] Test missing field rejection
- [ ] Test corrupted data handling
- [ ] Test localStorage unavailable
- [ ] Test concurrent operations
- [ ] Test clearTokens()
- [ ] Test hasTokens()
- [ ] Test isTokenExpired()

**Run tests**:
```bash
# Run TokenStorage tests specifically
npm test TokenStorage.test.ts

# Run with coverage
npm test TokenStorage.test.ts -- --coverage

# Target: 100% coverage for TokenStorage.ts
```

**Commit**:
```bash
git add frontend-client-apps/shared/__tests__/TokenStorage.test.ts
git commit -m "Add comprehensive TokenStorage tests (Req 2.1-2.10)"
```

**Validation**: ✅ TokenStorage.ts has 100% test coverage

---

## Phase 4: Test Route Protection (3-4 hours)

**Goal**: Validate AuthGuard route protection and token refresh  
**Tasks**: 11.1-11.5  
**Risk**: Low (only adding tests)

### Implementation Guide

**Create**: `frontend-client-apps/speaker-app/src/components/__tests__/AuthGuard.test.tsx`

**Use the complete test template from design.md** (search for "AuthGuard.test.tsx" in design.md)

**Key Tests to Include** (checklist):
- [ ] Test unauthenticated redirect
- [ ] Test authenticated access
- [ ] Test loading state
- [ ] Test token refresh on expiry
- [ ] Test refresh scheduling (5 min before)
- [ ] Test concurrent refresh prevention
- [ ] Test timer cleanup on unmount
- [ ] Test refresh failure handling

**Run tests**:
```bash
npm test AuthGuard.test.tsx -- --coverage
# Target: 100% coverage for AuthGuard.tsx
```

**Commit**:
```bash
git add frontend-client-apps/speaker-app/src/components/__tests__/AuthGuard.test.tsx
git commit -m "Add comprehensive AuthGuard tests (Req 3.1-3.10)"
```

**Validation**: ✅ AuthGuard.tsx has 100% test coverage

---

## Phase 5: Test Error Handling (2-3 hours)

**Goal**: Validate error handling utilities  
**Tasks**: 12.1-12.5, 13  
**Risk**: Low

### Implementation Guide

**Create**: `frontend-client-apps/shared/__tests__/AuthError.test.ts`

**Use the template from design.md**

**Key Tests** (checklist):
- [ ] Test error creation with all codes
- [ ] Test user message generation
- [ ] Test original error chaining
- [ ] Test isAuthError type guard
- [ ] Test toAuthError conversion
- [ ] Test shouldReAuthenticate helper
- [ ] Test isRetryableError helper
- [ ] Test JSON serialization

**Update**: `frontend-client-apps/shared/__tests__/SessionCreationOrchestrator.test.ts`

**Add tests for bug fixes**:
- [ ] Test uses expiresAt directly (not recalculated)
- [ ] Test WebSocket state check before send
- [ ] Test error thrown if not connected

**Commit**:
```bash
git add frontend-client-apps/shared/__tests__/AuthError.test.ts
git commit -m "Add AuthError tests (Req 4.1-4.5)"

git add frontend-client-apps/shared/__tests__/SessionCreationOrchestrator.test.ts
git commit -m "Add bug fix tests to SessionCreationOrchestrator (Req 8.1, 8.2)"
```

**Validation**: ✅ All error handling tested

---

## Phase 6: Validation (2 hours)

**Goal**: Verify all requirements met  
**Tasks**: 14, 15, 16  
**Risk**: None (validation only)

### 6.1 Validate Test Coverage [30 min] - Task 14

```bash
cd frontend-client-apps

# Run all tests with coverage
npm test -- --coverage

# Check specific files
npm test -- --coverage \
  shared/services/TokenStorage.ts \
  speaker-app/src/components/AuthGuard.tsx \
  shared/utils/AuthError.ts

# Verify:
# - TokenStorage.ts: 100% coverage
# - AuthGuard.tsx: 100% coverage
# - AuthError.ts: >80% coverage
# - Overall auth components: >90% coverage
```

**If coverage < target**: Add missing tests before proceeding

---

### 6.2 End-to-End Testing [1 hour] - Task 15

**Manual Test Checklist**:

```bash
# Start dev server
cd frontend-client-apps/speaker-app
npm run dev
```

**Test Scenarios**:
1. ✅ Login with valid credentials → Success
2. ✅ Login with invalid credentials → Error message shown
3. ✅ Token refresh during session → Seamless (no logout)
4. ✅ Page reload → Session persisted
5. ✅ Token expires → Auto-refresh triggered
6. ✅ Refresh fails → Redirect to login
7. ✅ Network error → Appropriate error message
8. ✅ WebSocket connection → Succeeds with token
9. ✅ Session creation → Works end-to-end

**Document results** in test report

---

### 6.3 Performance Validation [30 min] - Task 16

**Measure key operations**:

```javascript
// Add timing code temporarily for measurement

// 1. PBKDF2 key derivation
console.time('PBKDF2');
await tokenStorage.initialize(key);
console.timeEnd('PBKDF2');
// Target: 50-100ms

// 2. First-time authentication
console.time('Login');
await authService.login(username, password);
console.timeEnd('Login');
// Target: <2000ms (p95)

// 3. Token refresh
console.time('Refresh');
await authService.refreshTokens(refreshToken);
console.timeEnd('Refresh');
// Target: <500ms (p95)

// 4. WebSocket connection
console.time('WebSocket');
await wsClient.connect(token);
console.timeEnd('WebSocket');
// Target: <1000ms (p95)
```

**Document results** and verify all meet targets

---

### Phase 6 Checkpoint

**Success Criteria**:
- [ ] Test coverage >90% for auth components
- [ ] All P0 tasks completed
- [ ] E2E authentication flow tested
- [ ] All error scenarios handled
- [ ] Performance targets met
- [ ] Zero failing tests

**If all criteria met** → Proceed to Phase 7

---

## Phase 7: Observability (2-3 hours)

**Goal**: Add monitoring and logging  
**Tasks**: 9, 18  
**Risk**: Low

### 7.1 Improve Lambda Logging [1 hour] - Task 9

**File**: `session-management/lambda/authorizer/handler.py`

**Update exception handlers** with structured logging (see design.md Component 5 for complete example):

```python
except jwt.ExpiredSignatureError:
    logger.error(
        'Authorization failed: Token expired',
        extra={
            'error_type': 'TokenExpired',
            'method_arn': event.get('methodArn'),
            'has_token': bool(token),
            'request_id': context.request_id if context else None,
        }
    )
    raise Exception('Unauthorized')
```

**Apply to all exception handlers**

**Commit**:
```bash
git commit -am "Add structured logging to Lambda authorizer (Req 9.1-9.4)"
```

---

### 7.2 Configure CloudWatch [1-2 hours] - Task 18

**Actions**:
1. Define new metrics in Lambda (use CloudWatch SDK)
2. Create CloudWatch dashboard
3. Configure alerts per design.md

**Validation**: Check CloudWatch console shows new metrics and alerts

---

## Phase 8: Documentation (1 hour)

**Goal**: Update all documentation  
**Task**: 17  
**Risk**: None

### Documentation Updates

```bash
# Update README files
# Remove OAuth2 references
# Document direct auth flow only
# Update architecture diagrams

# Files to update:
# - frontend-client-apps/README.md
# - session-management/README.md
# - CODE_REVIEW_AUTH_CHANGES.md
# - AUTHENTICATION_CLEANUP_GUIDE.md
# - CLEANUP_ACTION_PLAN.md

git commit -am "Update documentation to reflect direct auth only (Req 1.4, 6.5)"
```

---

## Implementation Checkpoints

### After Each Phase

1. **Run full test suite**: `npm test`
2. **Check coverage**: `npm test -- --coverage`
3. **Manual smoke test**: Login → Session creation
4. **Git commit**: Descriptive message with requirement refs
5. **Update tasks.md**: Check off completed tasks

### Daily Standup Questions

1. Which phase am I in?
2. Which tasks completed yesterday?
3. Which tasks for today?
4. Any blockers?
5. Is test coverage increasing?

### Warning Signs

🚨 **Stop and review if**:
- Tests start failing
- Coverage decreases
- Can't run application
- Authentication flow broken
- Build errors occur

---

## Testing Protocol

### For Every Code Change

```bash
# 1. Make the change
# 2. Run affected tests
npm test <component>.test.ts

# 3. Check coverage increased
npm test -- --coverage <file-being-tested>

# 4. Run full suite
npm test

# 5. Manual test if UI changed
npm run dev
```

### Coverage Targets

- TokenStorage.ts: **100%** (security-critical)
- AuthGuard.tsx: **100%** (security-critical)
- AuthError.ts: **>80%**
- SessionCreationOrchestrator.ts: **>90%**
- Overall auth components: **>90%**

### If Coverage Falls Short

1. Run coverage report: `npm test -- --coverage`
2. Check `coverage/lcov-report/index.html`
3. Identify untested lines
4. Add tests for missing scenarios
5. Re-run until target met

---

## Troubleshooting Common Issues

### Issue: PBKDF2 Too Slow

**Symptom**: Key derivation takes >200ms

**Solution**: 
- Reduce iterations to 50,000 (still secure)
- Or cache derived key in memory
- Document performance in design.md

### Issue: Tests Failing After PBKDF2

**Symptom**: Existing tests break

**Likely Cause**: Mock crypto API not updated

**Solution**: Update test mocks for PBKDF2

### Issue: AuthGuard Infinite Refresh Loop

**Symptom**: Continuous refresh calls

**Likely Cause**: Concurrent protection not working

**Solution**: Check refreshPromiseRef.current logic

### Issue: WebSocket Connection Fails

**Symptom**: Connection rejected after changes

**Likely Cause**: Token format issue

**Solution**: 
- Check token is ID token (not access)
- Verify Lambda authorizer env vars
- Check CloudWatch logs for specific error

---

## Success Validation

### Before Marking Tasks Complete

For each task, verify:
- [ ] Code changes committed
- [ ] Tests written and passing
- [ ] Coverage targets met
- [ ] Manual testing completed (if applicable)
- [ ] No regressions
- [ ] Documented if needed

### Before Phase Complete

- [ ] All phase tasks checked off in tasks.md
- [ ] Phase checkpoint validation passed
- [ ] Git commit with phase summary
- [ ] Ready to start next phase

### Before Production Deployment

- [ ] All P0 tasks completed
- [ ] Test coverage >90%
- [ ] Performance targets met
- [ ] E2E testing passed
- [ ] Documentation updated
- [ ] Monitoring configured
- [ ] Rollback plan ready

---

## Quick Command Reference

```bash
# Navigate to project
cd /Volumes/workplace/low-latency-translate

# Frontend work
cd frontend-client-apps

# Run all tests
npm test

# Run with coverage
npm test -- --coverage

# Run specific test
npm test TokenStorage.test.ts

# Watch mode
npm test -- --watch

# Check for magic numbers
grep -r "5 \* 60 \* 1000\|300000" shared/ --include="*.ts"

# Check for dynamic imports
grep -r "await import\|require(" shared/ --include="*.ts" --include="*.tsx"

# Verify test coverage
cat coverage/lcov-report/index.html

# Backend work
cd session-management

# Run Lambda tests
python -m pytest tests/unit/test_authorizer.py -v

# Check coverage
python -m pytest --cov=lambda/authorizer tests/unit/
```

---

## Recommended Daily Schedule

### Day 1 (2 hours): Phase 1
- Morning: Tasks 1-2 (remove, constants, env docs)
- Afternoon: Tasks 5-8 (bug fixes, imports, enum)
- **Deliverable**: Clean codebase with constants

### Day 2 (3 hours): Phase 2
- Morning: Task 3 (PBKDF2 implementation)
- Afternoon: Task 4 (concurrent refresh)
- **Deliverable**: Security improvements complete

### Day 3 (5 hours): Phase 3
- All day: Task 10 (TokenStorage tests)
- **Deliverable**: TokenStorage 100% tested

### Day 4 (4 hours): Phase 4
- All day: Task 11 (AuthGuard tests)
- **Deliverable**: AuthGuard 100% tested

### Day 5 (3 hours): Phase 5-6
- Morning: Tasks 12-13 (AuthError tests)
- Afternoon: Tasks 14-16 (validation)
- **Deliverable**: All tests complete, validated

### Day 6 (3 hours): Phase 7-8
- Morning: Tasks 9, 18 (logging, monitoring)
- Afternoon: Task 17 (documentation)
- **Deliverable**: Production ready

---

## Progress Tracking

### Checklist Format

After completing each task, update tasks.md:
```markdown
- [x] 1. Remove orphaned OAuth2 code ✓
```

### Coverage Tracking

After each test phase, document:
```markdown
## Coverage Progress

| Component | Phase 3 | Phase 4 | Phase 5 | Target |
|-----------|---------|---------|---------|--------|
| TokenStorage | 100% | - | - | 100% ✓ |
| AuthGuard | - | 100% | - | 100% ✓ |
| AuthError | - | - | 85% | 80% ✓ |
| Overall | 33% | 67% | 90% | 90% ✓ |
```

---

## Key Success Indicators

### Phase 1 Success
✅ AuthService.ts deleted  
✅ Constants file created  
✅ All bugs fixed  
✅ Tests still passing

### Phase 2 Success
✅ PBKDF2 implemented  
✅ Concurrent refresh protected  
✅ Tests still passing

### Phase 3 Success
✅ TokenStorage 100% tested  
✅ Encryption validated

### Phase 4 Success
✅ AuthGuard 100% tested  
✅ Route protection validated

### Phase 5 Success
✅ All error handling tested  
✅ Bug fixes validated

### Phase 6 Success
✅ Coverage >90%  
✅ E2E tests pass  
✅ Performance targets met

### Phase 7-8 Success
✅ Monitoring configured  
✅ Documentation updated  
✅ Production ready

---

## Final Pre-Production Checklist

### Code Quality ✅
- [ ] Zero orphaned files
- [ ] Zero magic numbers
- [ ] All constants used
- [ ] Static imports only
- [ ] Clean git history

### Testing ✅
- [ ] TokenStorage: 100% coverage
- [ ] AuthGuard: 100% coverage
- [ ] AuthError: >80% coverage
- [ ] Overall: >90% coverage
- [ ] All tests passing
- [ ] E2E tests pass

### Security ✅
- [ ] PBKDF2 with 100k iterations
- [ ] Concurrent refresh protection
- [ ] Token expiry validation
- [ ] No sensitive data in logs
- [ ] WebSocket state validated

### Performance ✅
- [ ] Login <2s (p95)
- [ ] Refresh <500ms (p95)
- [ ] WebSocket <1s (p95)
- [ ] PBKDF2 <100ms

### Operations ✅
- [ ] CloudWatch metrics configured
- [ ] Alerts configured
- [ ] Structured logging in place
- [ ] Documentation updated
- [ ] Rollback plan ready

**When all checked** → ✅ Ready for production deployment

---

## Emergency Procedures

### If Tests Start Failing

1. **Don't proceed** to next task
2. **Identify** which change broke tests
3. **Fix** the issue or revert the change
4. **Re-run** tests until passing
5. **Continue** with original plan

### If Coverage Drops Below Target

1. **Stop** adding new changes
2. **Identify** uncovered lines in coverage report
3. **Add** missing test cases
4. **Re-run** coverage check
5. **Proceed** only when target met

### If Authentication Breaks

1. **Stop** immediately
2. **Revert** to last working commit
3. **Review** what changed
4. **Fix** incrementally
5. **Test** after each fix

### If Performance Degrades

1. **Measure** specific operation
2. **Compare** to target
3. **Profile** if needed
4. **Optimize** or adjust target
5. **Re-measure** to confirm

---

## Communication

### After Each Phase

Report:
1. Phase number and name
2. Tasks completed
3. Test coverage achieved
4. Any issues encountered
5. Ready for next phase (yes/no)

### If Blocked

Report:
1. Which task is blocked
2. What the blocker is
3. What you've tried
4. What help is needed

---

## Kiro-Specific Guidance

### File References

Always use relative paths from current working directory:
```
/Volumes/workplace/low-latency-translate/frontend-client-apps/...
```

### Test Execution

Run tests from frontend-client-apps directory:
```bash
cd /Volumes/workplace/low-latency-translate/frontend-client-apps
npm test
```

### When Using Design Templates

1. Open design.md
2. Search for relevant section (e.g., "TokenStorage.test.ts")
3. Copy the complete template
4. Create new file
5. Paste and adapt as needed

### Error Handling

If any step fails:
1. Read the error message carefully
2. Check the file path is correct
3. Verify you're in the right directory
4. Review the design.md section
5. Ask for clarification if needed

---

## Expected Timeline

**Optimistic** (everything goes smoothly): 16 hours over 5 days  
**Realistic** (minor issues encountered): 18-20 hours over 6 days  
**Pessimistic** (significant issues): 23-25 hours over 7-8 days

**Target**: Complete in 5-6 days with focused work

---

## Final Notes

### What Makes This Implementation Successful

1. **Follow the phases** - Don't skip ahead
2. **Test after every change** - Catch issues early
3. **Use the templates** - Don't reinvent solutions
4. **Validate at checkpoints** - Ensure quality
5. **Commit frequently** - Easy rollback if needed

### Remember

- ✅ You have complete specifications (requirements, design, tasks)
- ✅ You have code examples for everything
- ✅ You have test templates ready
- ✅ You have validation criteria
- ✅ You have troubleshooting guides

**You're fully equipped for successful implementation!** 🚀

---

## Quick Start

```bash
# Start here:
cd /Volumes/workplace/low-latency-translate

# Phase 1, Task 1:
git rm frontend-client-apps/shared/services/AuthService.ts
cd frontend-client-apps && npm test
git commit -m "Remove orphaned OAuth2 AuthService (Req 1)"

# Then follow STEERING.md Phase 1.2 onwards...
```

**Good luck! 🎉**
