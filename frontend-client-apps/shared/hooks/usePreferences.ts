import { useEffect } from 'react';
import { SecureStorage, STORAGE_KEYS, SpeakerPreferences, ListenerPreferences } from '../utils/storage';

const storage = new SecureStorage();

/**
 * Hook to load and persist speaker preferences
 */
export function useSpeakerPreferences(
  setInputVolume: (volume: number) => void,
  setKeyboardShortcutsEnabled: (enabled: boolean) => void
) {
  useEffect(() => {
    // Load preferences on mount
    const loadPreferences = async () => {
      try {
        const prefs = await storage.get<SpeakerPreferences>(STORAGE_KEYS.SPEAKER_PREFERENCES);
        
        if (prefs) {
          if (prefs.inputVolume !== undefined) {
            setInputVolume(prefs.inputVolume);
          }
          if (prefs.keyboardShortcutsEnabled !== undefined) {
            setKeyboardShortcutsEnabled(prefs.keyboardShortcutsEnabled);
          }
        }
      } catch (error) {
        console.error('Failed to load speaker preferences:', error);
      }
    };

    loadPreferences();
  }, [setInputVolume, setKeyboardShortcutsEnabled]);
}

/**
 * Hook to load and persist listener preferences
 */
export function useListenerPreferences(
  setPlaybackVolume: (volume: number) => void,
  setLanguagePreference: (language: string | null) => void,
  setKeyboardShortcutsEnabled: (enabled: boolean) => void
) {
  useEffect(() => {
    // Load preferences on mount
    const loadPreferences = async () => {
      try {
        const prefs = await storage.get<ListenerPreferences>(STORAGE_KEYS.LISTENER_PREFERENCES);
        
        if (prefs) {
          if (prefs.playbackVolume !== undefined) {
            setPlaybackVolume(prefs.playbackVolume);
          }
          if (prefs.languagePreference) {
            setLanguagePreference(prefs.languagePreference);
          }
          if (prefs.keyboardShortcutsEnabled !== undefined) {
            setKeyboardShortcutsEnabled(prefs.keyboardShortcutsEnabled);
          }
        }
      } catch (error) {
        console.error('Failed to load listener preferences:', error);
      }
    };

    loadPreferences();
  }, [setPlaybackVolume, setLanguagePreference, setKeyboardShortcutsEnabled]);
}

/**
 * Debounced save function to avoid excessive writes
 */
let saveTimeout: NodeJS.Timeout | null = null;

export function debouncedSave<T>(key: string, value: T, delay: number = 500): void {
  if (saveTimeout) {
    clearTimeout(saveTimeout);
  }

  saveTimeout = setTimeout(async () => {
    try {
      await storage.set(key, value);
    } catch (error) {
      console.error(`Failed to save preference ${key}:`, error);
    }
  }, delay);
}

/**
 * Save speaker preferences
 */
export async function saveSpeakerPreferences(prefs: Partial<SpeakerPreferences>): Promise<void> {
  try {
    const existing = await storage.get<SpeakerPreferences>(STORAGE_KEYS.SPEAKER_PREFERENCES) || {};
    const updated = { ...existing, ...prefs };
    await storage.set(STORAGE_KEYS.SPEAKER_PREFERENCES, updated);
  } catch (error) {
    console.error('Failed to save speaker preferences:', error);
  }
}

/**
 * Save listener preferences
 */
export async function saveListenerPreferences(prefs: Partial<ListenerPreferences>): Promise<void> {
  try {
    const existing = await storage.get<ListenerPreferences>(STORAGE_KEYS.LISTENER_PREFERENCES) || {};
    const updated = { ...existing, ...prefs };
    await storage.set(STORAGE_KEYS.LISTENER_PREFERENCES, updated);
  } catch (error) {
    console.error('Failed to save listener preferences:', error);
  }
}
