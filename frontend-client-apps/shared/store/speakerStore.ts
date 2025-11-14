import { create } from 'zustand';

/**
 * Quality warning types from audio quality validation
 */
export interface QualityWarning {
  type: 'snr_low' | 'clipping' | 'echo' | 'silence';
  message: string;
  timestamp: number;
}

/**
 * Listener statistics by language
 */
export interface LanguageStats {
  languageCode: string;
  count: number;
}

/**
 * Speaker application state
 */
export interface SpeakerState {
  // Session state
  sessionId: string | null;
  sourceLanguage: string | null;
  qualityTier: 'standard' | 'premium';
  isConnected: boolean;
  
  // Audio state
  isPaused: boolean;
  isMuted: boolean;
  inputVolume: number; // 0-100
  isTransmitting: boolean;
  
  // Quality warnings
  qualityWarnings: QualityWarning[];
  
  // Listener statistics
  listenerCount: number;
  languageDistribution: LanguageStats[];
  
  // Actions
  setSession: (sessionId: string, sourceLanguage: string, qualityTier: 'standard' | 'premium') => void;
  setConnected: (connected: boolean) => void;
  setPaused: (paused: boolean) => void;
  setMuted: (muted: boolean) => void;
  setInputVolume: (volume: number) => void;
  setTransmitting: (transmitting: boolean) => void;
  addQualityWarning: (warning: QualityWarning) => void;
  clearQualityWarnings: () => void;
  updateListenerStats: (count: number, distribution: LanguageStats[]) => void;
  reset: () => void;
}

/**
 * Initial state for speaker store
 */
const initialState = {
  sessionId: null,
  sourceLanguage: null,
  qualityTier: 'standard' as const,
  isConnected: false,
  isPaused: false,
  isMuted: false,
  inputVolume: 75,
  isTransmitting: false,
  qualityWarnings: [],
  listenerCount: 0,
  languageDistribution: [],
};

/**
 * Zustand store for speaker application state
 */
export const useSpeakerStore = create<SpeakerState>((set) => ({
  ...initialState,
  
  setSession: (sessionId, sourceLanguage, qualityTier) => 
    set({ sessionId, sourceLanguage, qualityTier }),
  
  setConnected: (connected) => 
    set({ isConnected: connected }),
  
  setPaused: (paused) => 
    set({ isPaused: paused }),
  
  setMuted: (muted) => 
    set({ isMuted: muted }),
  
  setInputVolume: (volume) => 
    set({ inputVolume: Math.max(0, Math.min(100, volume)) }),
  
  setTransmitting: (transmitting) => 
    set({ isTransmitting: transmitting }),
  
  addQualityWarning: (warning) => 
    set((state) => ({
      qualityWarnings: [...state.qualityWarnings, warning],
    })),
  
  clearQualityWarnings: () => 
    set({ qualityWarnings: [] }),
  
  updateListenerStats: (count, distribution) => 
    set({ listenerCount: count, languageDistribution: distribution }),
  
  reset: () => 
    set(initialState),
}));
