import { describe, it, expect, beforeEach, vi } from 'vitest';
import { SecureStorage, STORAGE_KEYS } from '../storage';

describe('SecureStorage', () => {
  let storage: SecureStorage;
  const mockStorage: Record<string, string> = {};

  beforeEach(() => {
    // Clear mock storage
    Object.keys(mockStorage).forEach(key => delete mockStorage[key]);
    
    // Setup localStorage mock to use mockStorage
    vi.mocked(localStorage.getItem).mockImplementation((key: string) => mockStorage[key] || null);
    vi.mocked(localStorage.setItem).mockImplementation((key: string, value: string) => {
      mockStorage[key] = value;
    });
    vi.mocked(localStorage.removeItem).mockImplementation((key: string) => {
      delete mockStorage[key];
    });
    vi.mocked(localStorage.clear).mockImplementation(() => {
      Object.keys(mockStorage).forEach(key => delete mockStorage[key]);
    });
    
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
      vi.mocked(localStorage.setItem).mockImplementation(() => {
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
      vi.mocked(localStorage.getItem).mockReturnValue('invalid-json{');
      
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
