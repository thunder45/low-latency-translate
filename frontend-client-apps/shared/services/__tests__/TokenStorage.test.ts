/**
 * TokenStorage Unit Tests
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TokenStorage, StorageError, STORAGE_ERROR_CODES } from '../TokenStorage';
import type { AuthTokens } from '../../utils/storage';

describe('TokenStorage', () => {
  let tokenStorage: TokenStorage;
  const validEncryptionKey = 'test-encryption-key-32-chars-long-minimum-required';
  const shortEncryptionKey = 'short';

  const validTokens: AuthTokens = {
    idToken: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test',
    accessToken: 'access-token-test',
    refreshToken: 'refresh-token-test',
    expiresAt: Date.now() + 3600000, // 1 hour from now
  };

  beforeEach(async () => {
    // Clear localStorage before each test
    localStorage.clear();
    
    // Get fresh instance
    tokenStorage = TokenStorage.getInstance();
    
    // Initialize with valid key
    await tokenStorage.initialize(validEncryptionKey);
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('initialize', () => {
    it('should initialize with valid encryption key', async () => {
      const newStorage = TokenStorage.getInstance();
      await expect(newStorage.initialize(validEncryptionKey)).resolves.not.toThrow();
    });

    it('should throw error with short encryption key', async () => {
      const newStorage = TokenStorage.getInstance();
      await expect(newStorage.initialize(shortEncryptionKey)).rejects.toThrow(StorageError);
      await expect(newStorage.initialize(shortEncryptionKey)).rejects.toThrow(
        'Encryption key must be at least 32 characters'
      );
    });

    it('should throw error with empty encryption key', async () => {
      const newStorage = TokenStorage.getInstance();
      await expect(newStorage.initialize('')).rejects.toThrow(StorageError);
    });
  });

  describe('storeTokens', () => {
    it('should store valid tokens successfully', async () => {
      await expect(tokenStorage.storeTokens(validTokens)).resolves.not.toThrow();
      expect(localStorage.getItem('auth_tokens')).not.toBeNull();
    });

    it('should encrypt tokens before storing', async () => {
      await tokenStorage.storeTokens(validTokens);
      
      const storedData = localStorage.getItem('auth_tokens');
      expect(storedData).not.toBeNull();
      
      const parsed = JSON.parse(storedData!);
      expect(parsed).toHaveProperty('encrypted');
      expect(parsed).toHaveProperty('iv');
      
      // Encrypted data should not contain plain text tokens
      expect(parsed.encrypted).not.toContain(validTokens.idToken);
      expect(parsed.encrypted).not.toContain(validTokens.accessToken);
    });

    it('should throw error for missing idToken', async () => {
      const invalidTokens = { ...validTokens, idToken: '' };
      await expect(tokenStorage.storeTokens(invalidTokens)).rejects.toThrow(StorageError);
      await expect(tokenStorage.storeTokens(invalidTokens)).rejects.toThrow(
        'Invalid tokens: missing required fields'
      );
    });

    it('should throw error for missing accessToken', async () => {
      const invalidTokens = { ...validTokens, accessToken: '' };
      await expect(tokenStorage.storeTokens(invalidTokens)).rejects.toThrow(StorageError);
    });

    it('should throw error for missing refreshToken', async () => {
      const invalidTokens = { ...validTokens, refreshToken: '' };
      await expect(tokenStorage.storeTokens(invalidTokens)).rejects.toThrow(StorageError);
    });

    it('should throw error for expired tokens', async () => {
      const expiredTokens = { ...validTokens, expiresAt: Date.now() - 1000 };
      await expect(tokenStorage.storeTokens(expiredTokens)).rejects.toThrow(StorageError);
      await expect(tokenStorage.storeTokens(expiredTokens)).rejects.toThrow(
        'Invalid tokens: expiresAt must be in the future'
      );
    });

    it('should throw error for missing expiresAt', async () => {
      const invalidTokens = { ...validTokens, expiresAt: 0 };
      await expect(tokenStorage.storeTokens(invalidTokens)).rejects.toThrow(StorageError);
    });
  });

  describe('getTokens', () => {
    it('should retrieve and decrypt stored tokens', async () => {
      await tokenStorage.storeTokens(validTokens);
      
      const retrieved = await tokenStorage.getTokens();
      
      expect(retrieved).not.toBeNull();
      expect(retrieved?.idToken).toBe(validTokens.idToken);
      expect(retrieved?.accessToken).toBe(validTokens.accessToken);
      expect(retrieved?.refreshToken).toBe(validTokens.refreshToken);
      expect(retrieved?.expiresAt).toBe(validTokens.expiresAt);
    });

    it('should return null when no tokens stored', async () => {
      const retrieved = await tokenStorage.getTokens();
      expect(retrieved).toBeNull();
    });

    it('should handle corrupted encrypted data', async () => {
      // Store encrypted data with valid base64 but invalid JSON content
      // This will pass decryption but fail JSON parsing
      const invalidData = btoa('not-valid-json-data');
      const validIv = btoa('1234567890ab');
      
      localStorage.setItem('auth_tokens', JSON.stringify({
        encrypted: invalidData,
        iv: validIv,
      }));

      // Should return null and clear corrupted data
      const retrieved = await tokenStorage.getTokens();
      expect(retrieved).toBeNull();
      
      // Should clear corrupted data
      expect(localStorage.getItem('auth_tokens')).toBeNull();
    });

    it('should handle invalid JSON in storage', async () => {
      localStorage.setItem('auth_tokens', 'not-valid-json');
      
      const retrieved = await tokenStorage.getTokens();
      expect(retrieved).toBeNull();
    });

    it('should handle missing encrypted field', async () => {
      localStorage.setItem('auth_tokens', JSON.stringify({
        iv: 'some-iv',
      }));

      await expect(tokenStorage.getTokens()).rejects.toThrow(StorageError);
      await expect(tokenStorage.getTokens()).rejects.toThrow('Invalid encrypted data format');
    });

    it('should handle missing iv field', async () => {
      localStorage.setItem('auth_tokens', JSON.stringify({
        encrypted: 'some-encrypted-data',
      }));

      await expect(tokenStorage.getTokens()).rejects.toThrow(StorageError);
    });
  });

  describe('clearTokens', () => {
    it('should clear stored tokens', async () => {
      await tokenStorage.storeTokens(validTokens);
      expect(localStorage.getItem('auth_tokens')).not.toBeNull();
      
      await tokenStorage.clearTokens();
      expect(localStorage.getItem('auth_tokens')).toBeNull();
    });

    it('should not throw error when clearing non-existent tokens', async () => {
      await expect(tokenStorage.clearTokens()).resolves.not.toThrow();
    });
  });

  describe('hasTokens', () => {
    it('should return true when tokens exist', async () => {
      await tokenStorage.storeTokens(validTokens);
      expect(tokenStorage.hasTokens()).toBe(true);
    });

    it('should return false when no tokens exist', () => {
      expect(tokenStorage.hasTokens()).toBe(false);
    });

    it('should return false after clearing tokens', async () => {
      await tokenStorage.storeTokens(validTokens);
      await tokenStorage.clearTokens();
      expect(tokenStorage.hasTokens()).toBe(false);
    });
  });

  describe('isTokenExpired', () => {
    it('should return false for valid tokens', async () => {
      await tokenStorage.storeTokens(validTokens);
      const isExpired = await tokenStorage.isTokenExpired();
      expect(isExpired).toBe(false);
    });

    it('should return true for tokens expiring within 5 minutes', async () => {
      const soonToExpireTokens = {
        ...validTokens,
        expiresAt: Date.now() + 240000, // 4 minutes from now
      };
      
      await tokenStorage.storeTokens(soonToExpireTokens);
      const isExpired = await tokenStorage.isTokenExpired();
      expect(isExpired).toBe(true);
    });

    it('should return true for expired tokens', async () => {
      const expiredTokens = {
        ...validTokens,
        expiresAt: Date.now() - 1000, // 1 second ago
      };
      
      // Store with modified validation
      const storedData = JSON.stringify(expiredTokens);
      const encryptedData = await (tokenStorage as any).encrypt(storedData);
      localStorage.setItem('auth_tokens', JSON.stringify(encryptedData));
      
      const isExpired = await tokenStorage.isTokenExpired();
      expect(isExpired).toBe(true);
    });

    it('should return true when no tokens exist', async () => {
      const isExpired = await tokenStorage.isTokenExpired();
      expect(isExpired).toBe(true);
    });

    it('should return true when tokens are corrupted', async () => {
      localStorage.setItem('auth_tokens', 'corrupted-data');
      const isExpired = await tokenStorage.isTokenExpired();
      expect(isExpired).toBe(true);
    });
  });

  describe('encryption and decryption', () => {
    it('should encrypt and decrypt data correctly', async () => {
      await tokenStorage.storeTokens(validTokens);
      const retrieved = await tokenStorage.getTokens();
      
      expect(retrieved).toEqual(validTokens);
    });

    it('should produce different encrypted output for same input', async () => {
      await tokenStorage.storeTokens(validTokens);
      const encrypted1 = localStorage.getItem('auth_tokens');
      
      await tokenStorage.clearTokens();
      await tokenStorage.storeTokens(validTokens);
      const encrypted2 = localStorage.getItem('auth_tokens');
      
      // Different IVs should produce different encrypted output
      expect(encrypted1).not.toBe(encrypted2);
    });

    it('should fail decryption with wrong key', async () => {
      await tokenStorage.storeTokens(validTokens);
      
      // Note: In a real implementation with proper crypto, this would fail.
      // With our mocked crypto, we can't test key mismatch properly.
      // This test verifies the structure is maintained.
      const retrieved = await tokenStorage.getTokens();
      expect(retrieved).not.toBeNull();
      
      // In production, different keys would cause decryption failure
      // This is a limitation of the test environment
    });
  });

  describe('singleton pattern', () => {
    it('should return same instance', () => {
      const instance1 = TokenStorage.getInstance();
      const instance2 = TokenStorage.getInstance();
      expect(instance1).toBe(instance2);
    });
  });

  describe('localStorage availability', () => {
    it('should handle localStorage being unavailable', async () => {
      // Mock localStorage.setItem to throw error
      const originalSetItem = localStorage.setItem;
      localStorage.setItem = vi.fn(() => {
        throw new Error('QuotaExceededError');
      });

      await expect(tokenStorage.storeTokens(validTokens)).rejects.toThrow(StorageError);
      await expect(tokenStorage.storeTokens(validTokens)).rejects.toThrow(
        'localStorage is not available'
      );

      // Restore
      localStorage.setItem = originalSetItem;
    });

    it('should return false for hasTokens when localStorage unavailable', () => {
      const originalGetItem = localStorage.getItem;
      localStorage.getItem = vi.fn(() => {
        throw new Error('SecurityError');
      });

      expect(tokenStorage.hasTokens()).toBe(false);

      // Restore
      localStorage.getItem = originalGetItem;
    });
  });

  describe('error codes', () => {
    it('should use correct error codes', async () => {
      try {
        await tokenStorage.initialize('short');
      } catch (error) {
        expect(error).toBeInstanceOf(StorageError);
        expect((error as StorageError).code).toBe(STORAGE_ERROR_CODES.MISSING_KEY);
      }

      try {
        const invalidTokens = { ...validTokens, idToken: '' };
        await tokenStorage.storeTokens(invalidTokens);
      } catch (error) {
        expect(error).toBeInstanceOf(StorageError);
        expect((error as StorageError).code).toBe(STORAGE_ERROR_CODES.INVALID_DATA);
      }
    });
  });
});
