import { describe, it, expect, beforeEach, vi } from 'vitest';
import { SecureStorage, STORAGE_KEYS } from '../storage';

// Mock localStorage
const mockStorage: Record<string, string> = {};
const localStorageMock = {
  getItem: vi.fn((key: string) => mockStorage[key] || null),
  setItem: vi.fn((key: string, value: string) => {
    mockStorage[key] = value;
  }),
  removeItem: vi.fn((key: string) => {
    delete mockStorage[key];
  }),
  clear: vi.fn(() => {
    Object.keys(mockStorage).forEach(key => delete mockStorage[key]);
  }),
  length: 0,
  key: vi.fn(),
};

Object.defineProperty(global, 'localStorage', {
  value: localStorageMock,
  writable: true,
});

describe('SecureStorage', () => {
  let storage: SecureStorage;

  beforeEach(() => {
    // Clear mock storage
    Object.keys(mockStorage).forEach(key => delete mockStorage[key]);
    
    // Clear all mocks
    vi.clearAllMocks();
    
    storage = new SecureStorage('test-encryption-key');
  });

  describe('set and get', () => {
    it('should store and retrieve string values', async () => {
      await storage.set(STORAGE_KEYS.SPEAKER_PREFERENCES, 'test-value');
      const value = await storage.get(STORAGE_KEYS.SPEAKER_PREFERENCES);
      
      expect(value).toBe('test-value');
      expect(localStorage.setItem).toHaveBeenCalled();
      expect(localStorage.getItem).toHaveBeenCalled();
    });

    it('should store and retrieve object values', async () => {
      const testObject = { inputVolume: 0.8, keyboardShortcuts: true };
      await storage.set(STORAGE_KEYS.SPEAKER_PREFERENCES, JSON.stringify(testObject));
      const value = await storage.get(STORAGE_KEYS.SPEAKER_PREFERENCES);
      
      expect(JSON.parse(value!)).toEqual(testObject);
    });

    it('should return null for non-existent keys', async () => {
      const value = await storage.get('non-existent-key');
      expect(value).toBeNull();
    });

    it('should handle encryption errors gracefully', async () => {
      // Mock setItem to throw error
      localStorageMock.setItem.mockImplementationOnce(() => {
        throw new Error('Storage quota exceeded');
      });
      
      // Should not throw, but log error
      await storage.set(STORAGE_KEYS.SPEAKER_PREFERENCES, 'test');
      
      // Verify error was handled
      expect(localStorage.setItem).toHaveBeenCalled();
    });

    it('should handle decryption errors gracefully', async () => {
      // Set a value first
      await storage.set(STORAGE_KEYS.SPEAKER_PREFERENCES, 'test');
      
      // Mock getItem to return invalid JSON
      localStorageMock.getItem.mockReturnValueOnce('invalid-json{');
      
      const value = await storage.get(STORAGE_KEYS.SPEAKER_PREFERENCES);
      expect(value).toBeNull();
    });
  });

  describe('remove', () => {
    it('should remove stored values', async () => {
      await storage.set(STORAGE_KEYS.SPEAKER_PREFERENCES, 'test-value');
      await storage.remove(STORAGE_KEYS.SPEAKER_PREFERENCES);
      
      const value = await storage.get(STORAGE_KEYS.SPEAKER_PREFERENCES);
      expect(value).toBeNull();
      expect(localStorage.removeItem).toHaveBeenCalledWith(STORAGE_KEYS.SPEAKER_PREFERENCES);
    });
  });

  describe('clear', () => {
    it('should clear all stored values', async () => {
      await storage.set(STORAGE_KEYS.SPEAKER_PREFERENCES, 'value1');
      await storage.set(STORAGE_KEYS.LISTENER_PREFERENCES, 'value2');
      await storage.clear();
      
      expect(await storage.get(STORAGE_KEYS.SPEAKER_PREFERENCES)).toBeNull();
      expect(await storage.get(STORAGE_KEYS.LISTENER_PREFERENCES)).toBeNull();
      expect(localStorage.clear).toHaveBeenCalled();
    });
  });

  describe('STORAGE_KEYS', () => {
    it('should have all required keys', () => {
      expect(STORAGE_KEYS.AUTH_TOKEN).toBeDefined();
      expect(STORAGE_KEYS.REFRESH_TOKEN).toBeDefined();
      expect(STORAGE_KEYS.SPEAKER_PREFERENCES).toBeDefined();
      expect(STORAGE_KEYS.LISTENER_PREFERENCES).toBeDefined();
    });
  });
});
