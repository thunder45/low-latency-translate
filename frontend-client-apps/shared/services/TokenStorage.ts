/**
 * TokenStorage Service
 * 
 * Securely stores and retrieves encrypted Cognito tokens in localStorage.
 * Uses AES-256-GCM encryption with PBKDF2 key derivation for token protection.
 */

import { STORAGE_KEYS, type AuthTokens } from '../utils/storage';
import { AUTH_CONSTANTS } from '../constants/auth';

/**
 * Storage error codes
 */
export const STORAGE_ERROR_CODES = {
  ENCRYPTION_FAILED: 'ENCRYPTION_FAILED',
  DECRYPTION_FAILED: 'DECRYPTION_FAILED',
  INVALID_DATA: 'INVALID_DATA',
  STORAGE_UNAVAILABLE: 'STORAGE_UNAVAILABLE',
  MISSING_KEY: 'MISSING_KEY',
} as const;

/**
 * Storage error class
 */
export class StorageError extends Error {
  constructor(
    public code: string,
    message: string
  ) {
    super(message);
    this.name = 'StorageError';
  }
}

/**
 * Encrypted data structure
 */
interface EncryptedData {
  encrypted: string; // Base64 encoded encrypted data
  iv: string; // Base64 encoded initialization vector
}

/**
 * TokenStorage class for secure token management
 */
export class TokenStorage {
  private static instance: TokenStorage;
  private encryptionKey: CryptoKey | null = null;
  private readonly STORAGE_KEY = STORAGE_KEYS.AUTH_TOKENS;

  private constructor() {}

  /**
   * Get singleton instance
   */
  static getInstance(): TokenStorage {
    if (!TokenStorage.instance) {
      TokenStorage.instance = new TokenStorage();
    }
    return TokenStorage.instance;
  }

  /**
   * Derive encryption key from passphrase using PBKDF2
   * 
   * Uses PBKDF2 with 100,000 iterations and SHA-256 to derive a secure
   * encryption key from the provided passphrase. This adds computational
   * cost to brute-force attacks.
   * 
   * @param passphrase - User-provided encryption key string
   * @param salt - Salt for key derivation
   * @returns CryptoKey for AES-GCM encryption/decryption
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
    
    // Derive encryption key using PBKDF2
    // Cast salt to BufferSource to satisfy TypeScript
    return crypto.subtle.deriveKey(
      {
        name: 'PBKDF2',
        salt: salt as BufferSource,
        iterations: AUTH_CONSTANTS.PBKDF2_ITERATIONS,
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
   * 
   * Derives a secure encryption key from the provided passphrase using PBKDF2.
   * The key must be at least 32 characters long.
   * 
   * @param keyString - Encryption key passphrase (min 32 characters)
   */
  async initialize(keyString: string): Promise<void> {
    if (!keyString || keyString.length < AUTH_CONSTANTS.ENCRYPTION_KEY_MIN_LENGTH) {
      throw new StorageError(
        STORAGE_ERROR_CODES.MISSING_KEY,
        `Encryption key must be at least ${AUTH_CONSTANTS.ENCRYPTION_KEY_MIN_LENGTH} characters`
      );
    }

    try {
      // Use fixed application salt for key derivation
      const salt = new TextEncoder().encode(AUTH_CONSTANTS.APPLICATION_SALT);
      this.encryptionKey = await this.deriveKey(keyString, salt);
    } catch (error) {
      throw new StorageError(
        STORAGE_ERROR_CODES.ENCRYPTION_FAILED,
        `Failed to initialize encryption: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  }

  /**
   * Check if localStorage is available
   */
  private isStorageAvailable(): boolean {
    try {
      const test = '__storage_test__';
      localStorage.setItem(test, test);
      localStorage.removeItem(test);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Encrypt data
   * 
   * Encrypts data using AES-256-GCM with a unique IV for each encryption.
   * The IV is generated randomly and must be stored alongside the encrypted data.
   * 
   * @param data - Plaintext data to encrypt
   * @returns Encrypted data with IV
   */
  private async encrypt(data: string): Promise<EncryptedData> {
    if (!this.encryptionKey) {
      throw new StorageError(
        STORAGE_ERROR_CODES.MISSING_KEY,
        'Encryption key not initialized'
      );
    }

    try {
      // Generate unique random IV for this encryption
      const iv = crypto.getRandomValues(new Uint8Array(AUTH_CONSTANTS.ENCRYPTION_IV_LENGTH));
      
      // Encrypt data
      const encoder = new TextEncoder();
      const encodedData = encoder.encode(data);
      
      const encryptedBuffer = await crypto.subtle.encrypt(
        { name: 'AES-GCM', iv },
        this.encryptionKey,
        encodedData
      );

      // Convert to base64
      const encryptedArray = new Uint8Array(encryptedBuffer);
      const encrypted = btoa(String.fromCharCode(...encryptedArray));
      const ivBase64 = btoa(String.fromCharCode(...iv));

      return { encrypted, iv: ivBase64 };
    } catch (error) {
      throw new StorageError(
        STORAGE_ERROR_CODES.ENCRYPTION_FAILED,
        `Encryption failed: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  }

  /**
   * Decrypt data
   */
  private async decrypt(encryptedData: EncryptedData): Promise<string> {
    if (!this.encryptionKey) {
      throw new StorageError(
        STORAGE_ERROR_CODES.MISSING_KEY,
        'Encryption key not initialized'
      );
    }

    try {
      // Convert from base64
      const encrypted = Uint8Array.from(atob(encryptedData.encrypted), c => c.charCodeAt(0));
      const iv = Uint8Array.from(atob(encryptedData.iv), c => c.charCodeAt(0));

      // Decrypt data
      const decryptedBuffer = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv },
        this.encryptionKey,
        encrypted
      );

      // Convert to string
      const decoder = new TextDecoder();
      return decoder.decode(decryptedBuffer);
    } catch (error) {
      throw new StorageError(
        STORAGE_ERROR_CODES.DECRYPTION_FAILED,
        `Decryption failed: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  }

  /**
   * Store encrypted tokens
   */
  async storeTokens(tokens: AuthTokens): Promise<void> {
    if (!this.isStorageAvailable()) {
      throw new StorageError(
        STORAGE_ERROR_CODES.STORAGE_UNAVAILABLE,
        'localStorage is not available'
      );
    }

    try {
      // Validate tokens
      if (!tokens.idToken || !tokens.accessToken || !tokens.refreshToken) {
        throw new StorageError(
          STORAGE_ERROR_CODES.INVALID_DATA,
          'Invalid tokens: missing required fields'
        );
      }

      if (!tokens.expiresAt || tokens.expiresAt <= Date.now()) {
        throw new StorageError(
          STORAGE_ERROR_CODES.INVALID_DATA,
          'Invalid tokens: expiresAt must be in the future'
        );
      }

      // Encrypt tokens
      const tokensJson = JSON.stringify(tokens);
      const encryptedData = await this.encrypt(tokensJson);

      // Store encrypted data
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(encryptedData));
    } catch (error) {
      if (error instanceof StorageError) {
        throw error;
      }
      throw new StorageError(
        STORAGE_ERROR_CODES.ENCRYPTION_FAILED,
        `Failed to store tokens: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  }

  /**
   * Retrieve and decrypt tokens
   */
  async getTokens(): Promise<AuthTokens | null> {
    if (!this.isStorageAvailable()) {
      throw new StorageError(
        STORAGE_ERROR_CODES.STORAGE_UNAVAILABLE,
        'localStorage is not available'
      );
    }

    try {
      // Get encrypted data
      const storedData = localStorage.getItem(this.STORAGE_KEY);
      if (!storedData) {
        return null;
      }

      // Parse encrypted data
      const encryptedData = JSON.parse(storedData) as EncryptedData;
      if (!encryptedData.encrypted || !encryptedData.iv) {
        // Clear invalid data and return null
        console.warn('[TokenStorage] Invalid encrypted data format, clearing storage');
        await this.clearTokens();
        return null;
      }

      // Decrypt tokens
      const tokensJson = await this.decrypt(encryptedData);
      const tokens = JSON.parse(tokensJson) as AuthTokens;

      // Validate decrypted tokens
      if (!tokens.idToken || !tokens.accessToken || !tokens.refreshToken || !tokens.expiresAt) {
        // Clear invalid tokens and return null
        console.warn('[TokenStorage] Invalid token structure after decryption, clearing storage');
        await this.clearTokens();
        return null;
      }

      return tokens;
    } catch (error) {
      // If decryption fails (including StorageError.DECRYPTION_FAILED),
      // clear corrupted/stale data and return null instead of throwing
      if (error instanceof StorageError && error.code === STORAGE_ERROR_CODES.DECRYPTION_FAILED) {
        console.warn('[TokenStorage] Decryption failed (likely stale data), clearing storage');
        await this.clearTokens();
        return null;
      }
      
      // Re-throw other storage errors (STORAGE_UNAVAILABLE, MISSING_KEY)
      if (error instanceof StorageError) {
        throw error;
      }
      
      // For unexpected errors, clear data and return null
      console.error('[TokenStorage] Unexpected error retrieving tokens:', error);
      await this.clearTokens();
      return null;
    }
  }

  /**
   * Clear all tokens
   */
  async clearTokens(): Promise<void> {
    if (!this.isStorageAvailable()) {
      throw new StorageError(
        STORAGE_ERROR_CODES.STORAGE_UNAVAILABLE,
        'localStorage is not available'
      );
    }

    try {
      localStorage.removeItem(this.STORAGE_KEY);
    } catch (error) {
      throw new StorageError(
        STORAGE_ERROR_CODES.STORAGE_UNAVAILABLE,
        `Failed to clear tokens: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  }

  /**
   * Check if tokens exist
   */
  hasTokens(): boolean {
    if (!this.isStorageAvailable()) {
      return false;
    }

    try {
      const storedData = localStorage.getItem(this.STORAGE_KEY);
      return storedData !== null;
    } catch {
      return false;
    }
  }

  /**
   * Validate token expiration
   */
  async isTokenExpired(): Promise<boolean> {
    try {
      const tokens = await this.getTokens();
      if (!tokens) {
        return true;
      }

      // Check if token expires within 5 minutes (300000ms)
      const expiresIn = tokens.expiresAt - Date.now();
      return expiresIn <= 300000; // 5 minutes buffer
    } catch {
      return true;
    }
  }
}

/**
 * Export singleton instance
 */
export const tokenStorage = TokenStorage.getInstance();
