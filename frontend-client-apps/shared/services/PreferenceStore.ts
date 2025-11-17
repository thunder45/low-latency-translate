/**
 * Preference Store Service
 * 
 * Manages user preferences with local storage persistence.
 * Handles volume, language, and keyboard shortcut preferences.
 */

import type { KeyboardShortcuts } from '../types/controls';

/**
 * Default keyboard shortcuts
 */
const DEFAULT_SHORTCUTS: KeyboardShortcuts = {
  mute: 'KeyM',
  pause: 'KeyP',
  volumeUp: 'ArrowUp',
  volumeDown: 'ArrowDown'
};

/**
 * Default volume level
 */
const DEFAULT_VOLUME = 75;

/**
 * Storage keys
 */
const STORAGE_KEYS = {
  VOLUME: 'llt_volume',
  LANGUAGE: 'llt_language',
  SHORTCUTS: 'llt_shortcuts'
} as const;

/**
 * Preference Store for managing user preferences
 */
export class PreferenceStore {
  private static instance: PreferenceStore;

  /**
   * Get singleton instance
   */
  static getInstance(): PreferenceStore {
    if (!PreferenceStore.instance) {
      PreferenceStore.instance = new PreferenceStore();
    }
    return PreferenceStore.instance;
  }

  /**
   * Save volume preference
   * 
   * @param userId - User identifier
   * @param volume - Volume level (0-100)
   */
  async saveVolume(userId: string, volume: number): Promise<void> {
    try {
      const key = `${STORAGE_KEYS.VOLUME}_${userId}`;
      const clampedVolume = Math.max(0, Math.min(100, volume));
      localStorage.setItem(key, clampedVolume.toString());
    } catch (error) {
      console.error('Failed to save volume preference:', error);
      throw new Error('PREFERENCE_SAVE_FAILED');
    }
  }
  
  /**
   * Get saved volume preference
   * 
   * @param userId - User identifier
   * @returns Saved volume or null if not found
   */
  async getVolume(userId: string): Promise<number | null> {
    try {
      const key = `${STORAGE_KEYS.VOLUME}_${userId}`;
      const value = localStorage.getItem(key);
      
      if (value === null) {
        return null;
      }
      
      const volume = parseInt(value, 10);
      return isNaN(volume) ? null : Math.max(0, Math.min(100, volume));
    } catch (error) {
      console.error('Failed to get volume preference:', error);
      return null;
    }
  }
  
  /**
   * Save language preference
   * 
   * @param userId - User identifier
   * @param languageCode - ISO 639-1 language code
   */
  async saveLanguage(userId: string, languageCode: string): Promise<void> {
    try {
      const key = `${STORAGE_KEYS.LANGUAGE}_${userId}`;
      localStorage.setItem(key, languageCode);
    } catch (error) {
      console.error('Failed to save language preference:', error);
      throw new Error('PREFERENCE_SAVE_FAILED');
    }
  }
  
  /**
   * Get saved language preference
   * 
   * @param userId - User identifier
   * @returns Saved language code or null if not found
   */
  async getLanguage(userId: string): Promise<string | null> {
    try {
      const key = `${STORAGE_KEYS.LANGUAGE}_${userId}`;
      return localStorage.getItem(key);
    } catch (error) {
      console.error('Failed to get language preference:', error);
      return null;
    }
  }
  
  /**
   * Save keyboard shortcuts preference
   * 
   * @param userId - User identifier
   * @param shortcuts - Keyboard shortcut configuration
   */
  async saveKeyboardShortcuts(userId: string, shortcuts: KeyboardShortcuts): Promise<void> {
    try {
      const key = `${STORAGE_KEYS.SHORTCUTS}_${userId}`;
      localStorage.setItem(key, JSON.stringify(shortcuts));
    } catch (error) {
      console.error('Failed to save keyboard shortcuts:', error);
      throw new Error('PREFERENCE_SAVE_FAILED');
    }
  }
  
  /**
   * Get saved keyboard shortcuts preference
   * 
   * @param userId - User identifier
   * @returns Saved shortcuts or null if not found
   */
  async getKeyboardShortcuts(userId: string): Promise<KeyboardShortcuts | null> {
    try {
      const key = `${STORAGE_KEYS.SHORTCUTS}_${userId}`;
      const value = localStorage.getItem(key);
      
      if (value === null) {
        return null;
      }
      
      return JSON.parse(value) as KeyboardShortcuts;
    } catch (error) {
      console.error('Failed to get keyboard shortcuts:', error);
      return null;
    }
  }
  
  /**
   * Reset all preferences to defaults
   * 
   * @param userId - User identifier
   */
  async resetPreferences(userId: string): Promise<void> {
    try {
      const volumeKey = `${STORAGE_KEYS.VOLUME}_${userId}`;
      const languageKey = `${STORAGE_KEYS.LANGUAGE}_${userId}`;
      const shortcutsKey = `${STORAGE_KEYS.SHORTCUTS}_${userId}`;
      
      localStorage.removeItem(volumeKey);
      localStorage.removeItem(languageKey);
      localStorage.removeItem(shortcutsKey);
    } catch (error) {
      console.error('Failed to reset preferences:', error);
      throw new Error('PREFERENCE_SAVE_FAILED');
    }
  }
  
  /**
   * Get default volume
   */
  getDefaultVolume(): number {
    return DEFAULT_VOLUME;
  }
  
  /**
   * Get default keyboard shortcuts
   */
  getDefaultShortcuts(): KeyboardShortcuts {
    return { ...DEFAULT_SHORTCUTS };
  }
}

/**
 * Singleton instance
 */
export const preferenceStore = new PreferenceStore();
