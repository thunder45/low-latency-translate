import { describe, it, expect, beforeEach, vi } from 'vitest';
import { SecureStorage, STORAGE_KEYS } from '../storage';

describe('SecureStorage', () => {
  let storage: SecureStorage;

  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    storage = new SecureStorage('test-encryption-key');
  });

  describe('set and get', () => {
    it('should store and retrieve string values', () => {
      storage.set(STORAGE_KEYS.SPEAKER_PREFERENCES, 'test-value');
      const value = storage.get(STORAGE_KEYS.SPEAKER_PREFERENCES);
      
      expect(value).toBe('test-value');
      expect(localStorage.setItem).toHaveBeenCalled();
      expect(localStorage.getItem).toHaveBeenCalled();
    });

    it('should store and retrieve object values', () => {
      const testObject = { inputVolume: 0.8, keyboardShortcuts: true };
      storage.set(STORAGE_KEYS.SPEAKER_PREFERENCES, JSON.stringify(testObject));
      const value = storage.get(STORAGE_KEYS.SPEAKER_PREFERENCES);
      
      expect(JSON.parse(value!)).toEqual(testObject);
    });

    it('should return null for non-existent keys', () => {
      const value = storage.get('non-existent-key');
      expect(value).toBeNull();
    });

    it('should handle encryption errors gracefully', () => {
      // Mock crypto.subtle.encrypt to throw error
      vi.spyOn(crypto.subtle, 'encrypt').mockRejectedValue(new Error('Encryption failed'));
      
      expect(() => {
        storage.set(STORAGE_KEYS.SPEAKER_PREFERENCES, 'test');
      }).toThrow();
    });

    it('should handle decryption errors gracefully', () => {
      // Set a value first
      storage.set(STORAGE_KEYS.SPEAKER_PREFERENCES, 'test');
      
      // Mock crypto.subtle.decrypt to throw error
      vi.spyOn(crypto.subtle, 'decrypt').mockRejectedValue(new Error('Decryption failed'));
      
      const value = storage.get(STORAGE_KEYS.SPEAKER_PREFERENCES);
      expect(value).toBeNull();
    });
  });

  describe('remove', () => {
    it('should remove stored values', () => {
      storage.set(STORAGE_KEYS.SPEAKER_PREFERENCES, 'test-value');
      storage.remove(STORAGE_KEYS.SPEAKER_PREFERENCES);
      
      const value = storage.get(STORAGE_KEYS.SPEAKER_PREFERENCES);
      expect(value).toBeNull();
      expect(localStorage.removeItem).toHaveBeenCalledWith(STORAGE_KEYS.SPEAKER_PREFERENCES);
    });
  });

  describe('clear', () => {
    it('should clear all stored values', () => {
      storage.set(STORAGE_KEYS.SPEAKER_PREFERENCES, 'value1');
      storage.set(STORAGE_KEYS.LISTENER_PREFERENCES, 'value2');
      storage.clear();
      
      expect(storage.get(STORAGE_KEYS.SPEAKER_PREFERENCES)).toBeNull();
      expect(storage.get(STORAGE_KEYS.LISTENER_PREFERENCES)).toBeNull();
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
