import { create } from 'zustand';

/**
 * Listener application state
 */
export interface ListenerState {
  // Session state
  sessionId: string | null;
  targetLanguage: string | null;
  isConnected: boolean;
  
  // Playback state
  isPaused: boolean;
  isMuted: boolean;
  playbackVolume: number; // 0-100
  
  // Buffer state
  bufferedDuration: number; // seconds
  isBuffering: boolean;
  isBufferOverflow: boolean;
  
  // Speaker state
  isSpeakerPaused: boolean;
  isSpeakerMuted: boolean;
  
  // Actions
  setSession: (sessionId: string, targetLanguage: string) => void;
  setConnected: (connected: boolean) => void;
  setPaused: (paused: boolean) => void;
  setMuted: (muted: boolean) => void;
  setPlaybackVolume: (volume: number) => void;
  setTargetLanguage: (language: string) => void;
  setBufferedDuration: (duration: number) => void;
  setBuffering: (buffering: boolean) => void;
  setBufferOverflow: (overflow: boolean) => void;
  setSpeakerPaused: (paused: boolean) => void;
  setSpeakerMuted: (muted: boolean) => void;
  reset: () => void;
}

/**
 * Initial state for listener store
 */
const initialState = {
  sessionId: null,
  targetLanguage: null,
  isConnected: false,
  isPaused: false,
  isMuted: false,
  playbackVolume: 75,
  bufferedDuration: 0,
  isBuffering: false,
  isBufferOverflow: false,
  isSpeakerPaused: false,
  isSpeakerMuted: false,
};

/**
 * Zustand store for listener application state
 */
export const useListenerStore = create<ListenerState>((set) => ({
  ...initialState,
  
  setSession: (sessionId, targetLanguage) => 
    set({ sessionId, targetLanguage }),
  
  setConnected: (connected) => 
    set({ isConnected: connected }),
  
  setPaused: (paused) => 
    set({ isPaused: paused }),
  
  setMuted: (muted) => 
    set({ isMuted: muted }),
  
  setPlaybackVolume: (volume) => 
    set({ playbackVolume: Math.max(0, Math.min(100, volume)) }),
  
  setTargetLanguage: (language) => 
    set({ targetLanguage: language }),
  
  setBufferedDuration: (duration) => 
    set({ bufferedDuration: duration }),
  
  setBuffering: (buffering) => 
    set({ isBuffering: buffering }),
  
  setBufferOverflow: (overflow) => 
    set({ isBufferOverflow: overflow }),
  
  setSpeakerPaused: (paused) => 
    set({ isSpeakerPaused: paused }),
  
  setSpeakerMuted: (muted) => 
    set({ isSpeakerMuted: muted }),
  
  reset: () => 
    set(initialState),
}));
