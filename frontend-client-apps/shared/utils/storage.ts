/**
 * Storage keys for secure storage
 */
export const STORAGE_KEYS = {
  // Authentication
  AUTH_TOKENS: 'auth_tokens',
  USER_ID: 'user_id',
  
  // Speaker preferences
  SPEAKER_INPUT_VOLUME: 'speaker_input_volume',
  SPEAKER_KEYBOARD_SHORTCUTS: 'speaker_keyboard_shortcuts',
  
  // Listener preferences
  LISTENER_PLAYBACK_VOLUME: 'listener_playback_volume',
  LISTENER_LANGUAGE_PREFERENCE: 'listener_language_preference',
  LISTENER_KEYBOARD_SHORTCUTS: 'listener_keyboard_shortcuts',
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
