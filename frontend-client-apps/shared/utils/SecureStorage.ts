import CryptoJS from 'crypto-js';

/**
 * Secure storage utility with AES encryption for sensitive data
 */
export class SecureStorage {
  private encryptionKey: string;

  /**
   * Initialize secure storage with encryption key
   * @param encryptionKey - Key for AES encryption (should be unique per user/session)
   */
  constructor(encryptionKey: string) {
    this.encryptionKey = encryptionKey;
  }

  /**
   * Store encrypted value in localStorage
   * @param key - Storage key
   * @param value - Value to store (will be JSON stringified and encrypted)
   */
  set<T>(key: string, value: T): void {
    try {
      const jsonString = JSON.stringify(value);
      const encrypted = CryptoJS.AES.encrypt(jsonString, this.encryptionKey).toString();
      localStorage.setItem(key, encrypted);
    } catch (error) {
      console.error('Failed to store encrypted value:', error);
      throw new Error('Storage encryption failed');
    }
  }

  /**
   * Retrieve and decrypt value from localStorage
   * @param key - Storage key
   * @returns Decrypted value or null if not found or decryption fails
   */
  get<T>(key: string): T | null {
    try {
      const encrypted = localStorage.getItem(key);
      if (!encrypted) {
        return null;
      }

      const decrypted = CryptoJS.AES.decrypt(encrypted, this.encryptionKey);
      const jsonString = decrypted.toString(CryptoJS.enc.Utf8);
      
      if (!jsonString) {
        // Decryption failed (wrong key or corrupted data)
        console.warn('Failed to decrypt value for key:', key);
        return null;
      }

      return JSON.parse(jsonString) as T;
    } catch (error) {
      console.error('Failed to retrieve encrypted value:', error);
      return null;
    }
  }

  /**
   * Remove value from localStorage
   * @param key - Storage key
   */
  remove(key: string): void {
    localStorage.removeItem(key);
  }

  /**
   * Clear all values from localStorage
   */
  clear(): void {
    localStorage.clear();
  }

  /**
   * Check if key exists in localStorage
   * @param key - Storage key
   * @returns True if key exists
   */
  has(key: string): boolean {
    return localStorage.getItem(key) !== null;
  }
}

/**
 * Create a secure storage instance with a derived encryption key
 * @param userId - User identifier to derive encryption key
 * @returns SecureStorage instance
 */
export function createSecureStorage(userId: string): SecureStorage {
  // Derive encryption key from user ID and a static salt
  // In production, consider using a more robust key derivation function
  const salt = 'low-latency-translate-v1';
  const encryptionKey = CryptoJS.SHA256(userId + salt).toString();
  return new SecureStorage(encryptionKey);
}
