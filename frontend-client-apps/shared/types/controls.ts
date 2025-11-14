/**
 * Core data models and types for Speaker & Listener Controls
 * 
 * This module defines the TypeScript interfaces for audio state management,
 * control state, session state, and buffer status used throughout the
 * speaker-listener controls system.
 */

/**
 * Audio state for both speakers and listeners
 */
export interface AudioState {
  isPaused: boolean;
  isMuted: boolean;
  volume: number; // 0-100
  timestamp: number;
}

/**
 * Control state for a user in a session
 */
export interface ControlState {
  sessionId: string;
  userId: string;
  role: 'speaker' | 'listener';
  audioState: AudioState;
  languagePreference?: string;
  lastUpdated: number;
}

/**
 * Session-wide control state
 */
export interface SessionState {
  sessionId: string;
  speakerState: AudioState;
  listenerStates: Map<string, AudioState>;
  activeListenerCount: number;
}

/**
 * Buffer status for pause functionality
 */
export interface BufferStatus {
  currentSize: number;
  maxSize: number;
  isOverflowing: boolean;
}

/**
 * Language information
 */
export interface Language {
  code: string;
  name: string;
  isAvailable: boolean;
}

/**
 * Speaker state for UI display
 */
export interface SpeakerState {
  isPaused: boolean;
  isMuted: boolean;
}

/**
 * Listener state for speaker's view
 */
export interface ListenerState {
  listenerId: string;
  displayName?: string;
  isPaused: boolean;
  isMuted: boolean;
}

/**
 * Listener control state with language preference
 */
export interface ListenerControlState {
  userId: string;
  audioState: AudioState;
  languagePreference: string;
  joinedAt: number;
  lastActiveAt: number;
}

/**
 * Audio buffer state for monitoring
 */
export interface AudioBufferState {
  sessionId: string;
  userId: string;
  bufferSize: number; // in bytes
  maxBufferSize: number; // 30 seconds worth
  bufferedDuration: number; // in milliseconds
  isOverflowing: boolean;
  oldestTimestamp: number;
  newestTimestamp: number;
}

/**
 * Keyboard shortcuts configuration
 */
export interface KeyboardShortcuts {
  mute: string;
  pause: string;
  volumeUp: string;
  volumeDown: string;
}

/**
 * User preferences for persistence
 */
export interface UserPreferences {
  userId: string;
  volume: number;
  languagePreference: string;
  keyboardShortcuts: KeyboardShortcuts;
  autoResumeOnJoin: boolean;
  createdAt: number;
  updatedAt: number;
}

/**
 * Control error types
 */
export enum ControlErrorType {
  STATE_SYNC_FAILED = 'STATE_SYNC_FAILED',
  AUDIO_CONTROL_FAILED = 'AUDIO_CONTROL_FAILED',
  LANGUAGE_SWITCH_FAILED = 'LANGUAGE_SWITCH_FAILED',
  PREFERENCE_SAVE_FAILED = 'PREFERENCE_SAVE_FAILED',
  BUFFER_OVERFLOW = 'BUFFER_OVERFLOW',
  INVALID_STATE_TRANSITION = 'INVALID_STATE_TRANSITION',
  SESSION_NOT_FOUND = 'SESSION_NOT_FOUND',
  UNAUTHORIZED = 'UNAUTHORIZED'
}

/**
 * Control error interface
 */
export interface ControlError {
  type: ControlErrorType;
  message: string;
  sessionId?: string;
  userId?: string;
  timestamp: number;
  recoverable: boolean;
}

/**
 * Language switch context for coordinated switching
 */
export interface SwitchContext {
  fromLanguage: string;
  toLanguage: string;
  newStreamUrl: string;
  syncTimestamp: number;
  estimatedLatency: number;
}

/**
 * Notification types for real-time updates
 */
export type NotificationType = 
  | 'speaker_state' 
  | 'listener_state' 
  | 'listener_joined' 
  | 'listener_left';

/**
 * Notification interface
 */
export interface Notification {
  type: NotificationType;
  sessionId: string;
  userId?: string;
  data: any;
  timestamp: number;
}
