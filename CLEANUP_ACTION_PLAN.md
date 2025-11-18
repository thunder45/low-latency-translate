# Authentication Cleanup & Testing Action Plan

**Date**: November 18, 2025  
**Goal**: Remove orphaned OAuth2 code and complete authentication implementation

## Current Situation

✅ **What You Have**: Clean direct username/password authentication using CognitoAuthService  
❌ **Problem**: Orphaned OAuth2 code (AuthService.ts) still in repo  
⚠️ **Risk**: Critical security code lacks test coverage

---

## Phase 1: Remove Orphaned OAuth2 Code (30 minutes)

### Files to Delete

```bash
# 1. Delete the orphaned OAuth2 service
git rm frontend-client-apps/shared/services/AuthService.ts
git commit -m "Remove orphaned OAuth2 AuthService (switched to direct auth)"
```

### Verification Steps

```bash
# Confirm no imports reference it
grep -r "from.*AuthService\|import.*AuthService" frontend-client-apps/ \
  --include="*.ts" --include="*.tsx" \
  --exclude-dir=node_modules | grep -v CognitoAuthService

# Should return empty (only CognitoAuthService should appear)
```

---

## Phase 2: Critical Test Coverage (8-10 hours)

### Priority 1: TokenStorage.ts Tests (4-5 hours)

**Why Critical**: Handles encryption of security tokens in browser

**Create**: `frontend-client-apps/shared/__tests__/TokenStorage.test.ts`

**Test Template**:
```typescript
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TokenStorage, StorageError, STORAGE_ERROR_CODES } from '../services/TokenStorage';

describe('TokenStorage', () => {
  let storage: TokenStorage;
  let mockLocalStorage: Record<string, string>;

  beforeEach(async () => {
    // Mock localStorage
    mockLocalStorage = {};
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key, value) => {
      mockLocalStorage[key] = value;
    });
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key) => {
      return mockLocalStorage[key] || null;
    });
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation((key) => {
      delete mockLocalStorage[key];
    });

    storage = TokenStorage.getInstance();
    await storage.initialize('test-encryption-key-minimum-32-chars');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('should initialize with valid encryption key', async () => {
      const newStorage = TokenStorage.getInstance();
      await expect(newStorage.initialize('valid-key-32-characters-long-x')).resolves.not.toThrow();
    });

    it('should reject key shorter than 32 characters', async () => {
      const newStorage = TokenStorage.getInstance();
      await expect(newStorage.initialize('short-key')).rejects.toThrow(StorageError);
    });
  });

  describe('storeTokens', () => {
    it('should encrypt and store tokens', async () => {
      const tokens = {
        idToken: 'test-id-token',
        accessToken: 'test-access-token',
        refreshToken: 'test-refresh-token',
        expiresAt: Date.now() + 3600000, // 1 hour
      };

      await storage.storeTokens(tokens);

      expect(mockLocalStorage['auth_tokens']).toBeDefined();
      const stored = JSON.parse(mockLocalStorage['auth_tokens']);
      expect(stored.encrypted).toBeDefined();
      expect(stored.iv).toBeDefined();
    });

    it('should reject tokens with missing fields', async () => {
      const tokens = {
        idToken: 'test-id-token',
        accessToken: 'test-access-token',
        // Missing refreshToken
        expiresAt: Date.now() + 3600000,
      } as any;

      await expect(storage.storeTokens(tokens)).rejects.toThrow(StorageError);
    });

    it('should reject expired tokens', async () => {
      const tokens = {
        idToken: 'test-id-token',
        accessToken: 'test-access-token',
        refreshToken: 'test-refresh-token',
        expiresAt: Date.now() - 1000, // Past
      };

      await expect(storage.storeTokens(tokens)).rejects.toThrow(StorageError);
    });
  });

  describe('getTokens', () => {
    it('should decrypt and return stored tokens', async () => {
      const tokens = {
        idToken: 'test-id-token',
        accessToken: 'test-access-token',
        refreshToken: 'test-refresh-token',
        expiresAt: Date.now() + 3600000,
      };

      await storage.storeTokens(tokens);
      const retrieved = await storage.getTokens();

      expect(retrieved).toEqual(tokens);
    });

    it('should return null when no tokens stored', async () => {
      const retrieved = await storage.getTokens();
      expect(retrieved).toBeNull();
    });

    it('should clear corrupted data and return null', async () => {
      mockLocalStorage['auth_tokens'] = 'corrupted-data';

      const retrieved = await storage.getTokens();

      expect(retrieved).toBeNull();
      expect(mockLocalStorage['auth_tokens']).toBeUndefined();
    });
  });

  describe('isTokenExpired', () => {
    it('should return false for valid tokens', async () => {
      const tokens = {
        idToken: 'test-id-token',
        accessToken: 'test-access-token',
        refreshToken: 'test-refresh-token',
        expiresAt: Date.now() + 600000, // 10 minutes
      };

      await storage.storeTokens(tokens);
      const isExpired = await storage.isTokenExpired();

      expect(isExpired).toBe(false);
    });

    it('should return true for tokens expiring within 5 minutes', async () => {
      const tokens = {
        idToken: 'test-id-token',
        accessToken: 'test-access-token',
        refreshToken: 'test-refresh-token',
        expiresAt: Date.now() + 240000, // 4 minutes
      };

      await storage.storeTokens(tokens);
      const isExpired = await storage.isTokenExpired();

      expect(isExpired).toBe(true);
    });

    it('should return true when no tokens exist', async () => {
      const isExpired = await storage.isTokenExpired();
      expect(isExpired).toBe(true);
    });
  });

  describe('clearTokens', () => {
    it('should remove all tokens', async () => {
      const tokens = {
        idToken: 'test-id-token',
        accessToken: 'test-access-token',
        refreshToken: 'test-refresh-token',
        expiresAt: Date.now() + 3600000,
      };

      await storage.storeTokens(tokens);
      await storage.clearTokens();

      expect(mockLocalStorage['auth_tokens']).toBeUndefined();
    });
  });

  describe('hasTokens', () => {
    it('should return true when tokens exist', async () => {
      const tokens = {
        idToken: 'test-id-token',
        accessToken: 'test-access-token',
        refreshToken: 'test-refresh-token',
        expiresAt: Date.now() + 3600000,
      };

      await storage.storeTokens(tokens);
      expect(storage.hasTokens()).toBe(true);
    });

    it('should return false when no tokens', () => {
      expect(storage.hasTokens()).toBe(false);
    });
  });
});
```

### Priority 2: AuthGuard.tsx Tests (3-4 hours)

**Why Critical**: Controls access to protected routes and manages auto-refresh

**Create**: `frontend-client-apps/speaker-app/src/components/__tests__/AuthGuard.test.tsx`

**Test Template**:
```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { AuthGuard } from '../AuthGuard';
import * as TokenStorageModule from '../../../../shared/services/TokenStorage';
import * as CognitoAuthServiceModule from '../../../../shared/services/CognitoAuthService';

vi.mock('../../../../shared/services/TokenStorage');
vi.mock('../../../../shared/services/CognitoAuthService');
vi.mock('../../../../shared/utils/config');

describe('AuthGuard', () => {
  let mockTokenStorage: any;
  let mockAuthService: any;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();

    mockTokenStorage = {
      initialize: vi.fn().mockResolvedValue(undefined),
      getTokens: vi.fn(),
      storeTokens: vi.fn(),
      clearTokens: vi.fn(),
    };

    mockAuthService = {
      refreshTokens: vi.fn(),
    };

    vi.spyOn(TokenStorageModule, 'TokenStorage').mockReturnValue({
      getInstance: () => mockTokenStorage,
    } as any);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('authentication check', () => {
    it('should show children when authenticated', async () => {
      mockTokenStorage.getTokens.mockResolvedValue({
        idToken: 'valid-token',
        accessToken: 'valid-access',
        refreshToken: 'valid-refresh',
        expiresAt: Date.now() + 600000, // 10 minutes
      });

      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      await waitFor(() => {
        expect(screen.getByText('Protected Content')).toBeInTheDocument();
      });
    });

    it('should show login form when not authenticated', async () => {
      mockTokenStorage.getTokens.mockResolvedValue(null);

      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      await waitFor(() => {
        expect(screen.getByText('Speaker Login')).toBeInTheDocument();
      });
    });

    it('should show loading state while checking', () => {
      mockTokenStorage.getTokens.mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve(null), 1000))
      );

      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      expect(screen.getByText('Checking authentication...')).toBeInTheDocument();
    });
  });

  describe('token refresh', () => {
    it('should refresh expired tokens', async () => {
      mockTokenStorage.getTokens.mockResolvedValue({
        idToken: 'expired-token',
        accessToken: 'expired-access',
        refreshToken: 'valid-refresh',
        expiresAt: Date.now() - 1000, // Expired
      });

      mockAuthService.refreshTokens.mockResolvedValue({
        idToken: 'new-token',
        accessToken: 'new-access',
        refreshToken: 'valid-refresh',
        expiresIn: 3600,
      });

      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      await waitFor(() => {
        expect(mockAuthService.refreshTokens).toHaveBeenCalled();
      });
    });

    it('should schedule refresh 5 minutes before expiry', async () => {
      const expiresAt = Date.now() + 600000; // 10 minutes
      mockTokenStorage.getTokens.mockResolvedValue({
        idToken: 'valid-token',
        accessToken: 'valid-access',
        refreshToken: 'valid-refresh',
        expiresAt,
      });

      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      await waitFor(() => {
        expect(screen.getByText('Protected Content')).toBeInTheDocument();
      });

      // Advance time to 5 minutes before expiry
      vi.advanceTimersByTime(300000); // 5 minutes

      await waitFor(() => {
        expect(mockAuthService.refreshTokens).toHaveBeenCalled();
      });
    });

    it('should handle refresh failure', async () => {
      mockTokenStorage.getTokens.mockResolvedValue({
        idToken: 'expired-token',
        accessToken: 'expired-access',
        refreshToken: 'valid-refresh',
        expiresAt: Date.now() - 1000,
      });

      mockAuthService.refreshTokens.mockRejectedValue(new Error('Refresh failed'));

      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      await waitFor(() => {
        expect(screen.getByText('Speaker Login')).toBeInTheDocument();
      });
    });
  });
});
```

### Priority 3: AuthError.ts Tests (2-3 hours)

**Why Important**: Ensures consistent error handling across app

**Create**: `frontend-client-apps/shared/__tests__/AuthError.test.ts`

**Test Template**:
```typescript
import { describe, it, expect } from 'vitest';
import {
  AuthError,
  AUTH_ERROR_CODES,
  isAuthError,
  toAuthError,
  handleAuthError,
  shouldReAuthenticate,
  isRetryableError,
} from '../utils/AuthError';

describe('AuthError', () => {
  describe('constructor', () => {
    it('should create error with code and message', () => {
      const error = new AuthError(
        AUTH_ERROR_CODES.NOT_AUTHENTICATED,
        'Custom message'
      );

      expect(error.code).toBe(AUTH_ERROR_CODES.NOT_AUTHENTICATED);
      expect(error.message).toBe('Custom message');
      expect(error.userMessage).toBe('Please log in to create a session');
    });

    it('should chain original error', () => {
      const original = new Error('Original error');
      const error = new AuthError(
        AUTH_ERROR_CODES.NETWORK_ERROR,
        'Network failed',
        original
      );

      expect(error.originalError).toBe(original);
    });

    it('should include context', () => {
      const context = { userId: '123', operation: 'login' };
      const error = new AuthError(
        AUTH_ERROR_CODES.TOKEN_EXPIRED,
        'Token expired',
        undefined,
        context
      );

      expect(error.context).toEqual(context);
    });
  });

  describe('isAuthError', () => {
    it('should return true for AuthError instances', () => {
      const error = new AuthError(AUTH_ERROR_CODES.NOT_AUTHENTICATED);
      expect(isAuthError(error)).toBe(true);
    });

    it('should return false for regular errors', () => {
      const error = new Error('Regular error');
      expect(isAuthError(error)).toBe(false);
    });
  });

  describe('toAuthError', () => {
    it('should return AuthError as-is', () => {
      const error = new AuthError(AUTH_ERROR_CODES.NOT_AUTHENTICATED);
      const result = toAuthError(error);
      expect(result).toBe(error);
    });

    it('should convert network errors', () => {
      const error = new Error('network timeout');
      const result = toAuthError(error);
      expect(result.code).toBe(AUTH_ERROR_CODES.NETWORK_ERROR);
    });

    it('should convert token errors', () => {
      const error = new Error('token expired');
      const result = toAuthError(error);
      expect(result.code).toBe(AUTH_ERROR_CODES.TOKEN_EXPIRED);
    });

    it('should use default code for unknown errors', () => {
      const error = new Error('unknown error');
      const result = toAuthError(error, AUTH_ERROR_CODES.COGNITO_ERROR);
      expect(result.code).toBe(AUTH_ERROR_CODES.COGNITO_ERROR);
    });
  });

  describe('shouldReAuthenticate', () => {
    it('should return true for auth-required errors', () => {
      const codes = [
        AUTH_ERROR_CODES.NOT_AUTHENTICATED,
        AUTH_ERROR_CODES.TOKEN_EXPIRED,
        AUTH_ERROR_CODES.REFRESH_FAILED,
        AUTH_ERROR_CODES.INVALID_TOKEN,
      ];

      codes.forEach(code => {
        const error = new AuthError(code);
        expect(shouldReAuthenticate(error)).toBe(true);
      });
    });

    it('should return false for retryable errors', () => {
      const error = new AuthError(AUTH_ERROR_CODES.NETWORK_ERROR);
      expect(shouldReAuthenticate(error)).toBe(false);
    });
  });

  describe('isRetryableError', () => {
    it('should return true for network errors', () => {
      const error = new AuthError(AUTH_ERROR_CODES.NETWORK_ERROR);
      expect(isRetryableError(error)).toBe(true);
    });

    it('should return false for auth errors', () => {
      const error = new AuthError(AUTH_ERROR_CODES.TOKEN_EXPIRED);
      expect(isRetryableError(error)).toBe(false);
    });
  });
});
```

---

## Phase 3: Code Quality Improvements (2-3 hours)

### 1. Create Constants File

**File**: `frontend-client-apps/shared/constants/auth.ts`

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
  
  /** JWKS cache TTL for Lambda authorizer (1 hour) */
  JWKS_CACHE_TTL_SECONDS: 3600,
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
```

### 2. Update Components to Use Constants

**Files to Update**:
- `WebSocketClient.ts` - Replace hardcoded close codes
- `TokenStorage.ts` - Replace magic numbers  
- `SessionCreationOrchestrator.ts` - Replace timeouts/thresholds
- `AuthGuard.tsx` - Replace refresh threshold

**Example**:
```typescript
// Before:
if (event.code === 1008) {

// After:
import { WebSocketCloseCode } from '../constants/auth';
if (event.code === WebSocketCloseCode.POLICY_VIOLATION) {
```

### 3. Fix Concurrent Refresh in AuthGuard

```typescript
// Add to AuthGuard.tsx
const refreshPromiseRef = useRef<Promise<boolean> | null>(null);

const refreshTokens = async (refreshToken: string): Promise<boolean> => {
  // Prevent concurrent refreshes
  if (refreshPromiseRef.current) {
    console.log('Refresh already in progress, reusing promise');
    return refreshPromiseRef.current;
  }

  refreshPromiseRef.current = performRefresh(refreshToken);
  
  try {
    return await refreshPromiseRef.current;
  } finally {
    refreshPromiseRef.current = null;
  }
};

// Extract actual refresh logic to separate function
const performRefresh = async (refreshToken: string): Promise<boolean> => {
  // ... existing refresh logic ...
};
```

### 4. Remove Dynamic Imports from LoginForm

```typescript
// Change in LoginForm.tsx performLogin():

// BEFORE (adds ~50-100ms latency):
const { CognitoAuthService } = await import('../../../shared/services/CognitoAuthService');
const { TokenStorage } = await import('../../../shared/services/TokenStorage');

// AFTER (module-level import):
import { CognitoAuthService } from '../../../shared/services/CognitoAuthService';
import { TokenStorage } from '../../../shared/services/TokenStorage';
```

### 5. Centralize TokenStorage Initialization

**File**: `frontend-client-apps/speaker-app/src/main.tsx`

```typescript
// Add before rendering app:
import { tokenStorage } from '../shared/services/TokenStorage';

async function initializeApp() {
  try {
    const config = getConfig();
    await tokenStorage.initialize(config.encryptionKey);
    console.log('TokenStorage initialized');
  } catch (error) {
    console.error('Failed to initialize TokenStorage:', error);
  }
}

// Call before rendering
initializeApp().then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
});
```

**Then remove initializations from**:
- LoginForm.tsx
- AuthGuard.tsx (keep one call if needed for safety)

---

## Phase 4: Security Improvements (2-3 hours)

### 1. Implement Key Derivation in TokenStorage

**Why**: Current implementation truncates keys and has no KDF

**Update**: `TokenStorage.ts`

```typescript
/**
 * Derive encryption key from password using PBKDF2
 */
private async deriveKey(password: string, salt: Uint8Array): Promise<CryptoKey> {
  // Import password as key material
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(password),
    'PBKDF2',
    false,
    ['deriveKey']
  );

  // Derive actual encryption key
  return crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt,
      iterations: 100000, // OWASP recommended minimum
      hash: 'SHA-256',
    },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  );
}

/**
 * Initialize with encryption key
 */
async initialize(keyString: string): Promise<void> {
  if (!keyString || keyString.length < 32) {
    throw new StorageError(
      STORAGE_ERROR_CODES.MISSING_KEY,
      'Encryption key must be at least 32 characters'
    );
  }

  try {
    // Use application-specific salt (can be public)
    const salt = new TextEncoder().encode('low-latency-translate-v1');
    this.encryptionKey = await this.deriveKey(keyString, salt);
  } catch (error) {
    throw new StorageError(
      STORAGE_ERROR_CODES.ENCRYPTION_FAILED,
      `Failed to initialize encryption: ${error instanceof Error ? error.message : 'Unknown error'}`
    );
  }
}
```

---

## Phase 5: Documentation (1 hour)

### Update Existing Docs

1. **Remove OAuth2 References**
   ```bash
   # Search and update
   grep -l "OAuth\|oauth\|Hosted UI" frontend-client-apps/docs/*.md
   ```

2. **Document Clean Architecture**
   - Update README with direct auth flow only
   - Remove any OAuth2 diagrams/references
   - Add clear architecture diagram

---

## Quick Reference: What to Keep vs Remove

### ✅ KEEP (Direct Authentication)

| File | Purpose | Status |
|------|---------|--------|
| CognitoAuthService.ts | Direct username/password auth | ✅ Active, tested |
| TokenStorage.ts | Encrypted token storage | ⚠️ Missing tests |
| AuthError.ts | Error handling utilities | ⚠️ Missing tests |
| LoginForm.tsx | Login UI | ✅ Tested |
| AuthGuard.tsx | Route protection | ⚠️ Missing tests |

### ❌ REMOVE (OAuth2)

| File | Reason | Safe to Delete? |
|------|--------|-----------------|
| AuthService.ts | OAuth2 implementation, unused | ✅ Yes - no references |

---

## Execution Plan

### Week 1 (Total: ~15 hours)

**Day 1 (2 hours)**:
- [ ] Delete AuthService.ts
- [ ] Create constants file
- [ ] Update imports to use constants
- [ ] Git commit: "Clean up auth implementation"

**Day 2-3 (6 hours)**:
- [ ] Write TokenStorage tests
- [ ] Fix encryption key derivation
- [ ] Test encryption/decryption thoroughly
- [ ] Git commit: "Add TokenStorage tests and improve encryption"

**Day 4 (4 hours)**:
- [ ] Write AuthGuard tests
- [ ] Add concurrent refresh protection
- [ ] Test refresh timer logic
- [ ] Git commit: "Add AuthGuard tests and fix concurrent refresh"

**Day 5 (3 hours)**:
- [ ] Write AuthError tests
- [ ] Centralize TokenStorage initialization
- [ ] Remove dynamic imports from LoginForm
- [ ] Update documentation
- [ ] Git commit: "Complete authentication test coverage"

---

## Success Metrics

After completing this plan:

- [ ] Zero OAuth2 code in repository
- [ ] 90%+ test coverage for all auth code
- [ ] All magic numbers replaced with constants
- [ ] Security-critical code fully tested
- [ ] Single clear authentication flow
- [ ] Production-ready implementation

**Current Coverage**: ~50%  
**Target Coverage**: ~90%  
**Effort Required**: ~15 hours

---

## Final Checklist Before Production

- [ ] AuthService.ts deleted
- [ ] TokenStorage.ts tests added (100% coverage)
- [ ] AuthGuard.tsx tests added (100% coverage)
- [ ] AuthError.ts tests added (100% coverage)
- [ ] Constants file created and used
- [ ] Encryption uses PBKDF2
- [ ] Concurrent refresh protection added
- [ ] TokenStorage centrally initialized
- [ ] Dynamic imports removed
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Integration tests run successfully

**Ready for Production**: When all boxes checked ✅
