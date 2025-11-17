/**
 * Storage keys for secure storage
 */
export const STORAGE_KEYS = {
  // Authentication
  AUTH_TOKEN: 'auth_token',
  REFRESH_TOKEN: 'refresh_token',
  AUTH_TOKENS: 'auth_tokens',
  USER_ID: 'user_id',
  
  // Speaker preferences
  SPEAKER_INPUT_VOLUME: 'speaker_input_volume',
  SPEAKER_KEYBOARD_SHORTCUTS: 'speaker_keyboard_shortcuts',
  SPEAKER_PREFERENCES: 'speaker_preferences',
  
  // Listener preferences
  LISTENER_PLAYBACK_VOLUME: 'listener_playback_volume',
  LISTENER_LANGUAGE_PREFERENCE: 'listener_language_preference',
  LISTENER_KEYBOARD_SHORTCUTS: 'listener_keyboard_shortcuts',
  LISTENER_PREFERENCES: 'listener_preferences',
} as const;

/**
 * Authentication tokens from Cognito
 */
export interface AuthTokens {
  idToken: string;
  accessToken: string;
  refreshToken: string;
  expiresAt: number; // Unix timestamp
}

/**
 * Speaker application preferences
 */
export interface SpeakerPreferences {
  inputVolume: number; // 0-100
  keyboardShortcutsEnabled: boolean;
}

/**
 * Listener application preferences
 */
export interface ListenerPreferences {
  playbackVolume: number; // 0-100
  languagePreference: string | null; // ISO 639-1 code
  keyboardShortcutsEnabled: boolean;
}

/**
 * Default speaker preferences
 */
export const DEFAULT_SPEAKER_PREFERENCES: SpeakerPreferences = {
  inputVolume: 75,
  keyboardShortcutsEnabled: true,
};

/**
 * Default listener preferences
 */
export const DEFAULT_LISTENER_PREFERENCES: ListenerPreferences = {
  playbackVolume: 75,
  languagePreference: null,
  keyboardShortcutsEnabled: true,
};


/**
 * Simple secure storage wrapper for localStorage
 */
export class SecureStorage {
  /**
   * Get item from storage
   */
  async get<T>(key: string): Promise<T | null> {
    try {
      const item = localStorage.getItem(key);
      if (!item) return null;
      return JSON.parse(item) as T;
    } catch (error) {
      console.error(`Failed to get item from storage: ${key}`, error);
      return null;
    }
  }

  /**
   * Set item in storage
   */
  async set(key: string, value: any): Promise<void> {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      console.error(`Failed to set item in storage: ${key}`, error);
    }
  }

  /**
   * Remove item from storage
   */
  async remove(key: string): Promise<void> {
    try {
      localStorage.removeItem(key);
    } catch (error) {
      console.error(`Failed to remove item from storage: ${key}`, error);
    }
  }

  /**
   * Clear all items from storage
   */
  async clear(): Promise<void> {
    try {
      localStorage.clear();
    } catch (error) {
      console.error('Failed to clear storage', error);
    }
  }
}
