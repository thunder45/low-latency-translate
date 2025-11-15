/**
 * Listener Controls UI Component
 * 
 * Provides control interface for listeners including pause/resume,
 * mute/unmute, volume control, language selection, and speaker status display.
 */

import React, { useState, useCallback, useEffect } from 'react';
import type { Language, SpeakerState } from '../types/controls';

/**
 * Props for ListenerControls component
 */
export interface ListenerControlsProps {
  sessionId: string;
  onPauseToggle: () => void;
  onMuteToggle: () => void;
  onVolumeChange: (volume: number) => void;
  onLanguageChange: (languageCode: string) => void;
  isPaused: boolean;
  isMuted: boolean;
  volume: number;
  selectedLanguage: string;
  availableLanguages: Language[];
  speakerState: SpeakerState;
}

/**
 * Listener Controls Component
 * Memoized for performance optimization
 */
export const ListenerControls: React.FC<ListenerControlsProps> = React.memo(({
  sessionId,
  onPauseToggle,
  onMuteToggle,
  onVolumeChange,
  onLanguageChange,
  isPaused,
  isMuted,
  volume,
  selectedLanguage,
  availableLanguages,
  speakerState,
}) => {
  const [localVolume, setLocalVolume] = useState(volume);
  const [volumeDebounceTimer, setVolumeDebounceTimer] = useState<NodeJS.Timeout | null>(null);
  const [isLanguageSwitching, setIsLanguageSwitching] = useState(false);

  // Sync local volume with prop changes
  useEffect(() => {
    setLocalVolume(volume);
  }, [volume]);

  /**
   * Handle volume slider change with debouncing
   */
  const handleVolumeChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const newVolume = parseInt(event.target.value, 10);
    setLocalVolume(newVolume);

    // Clear existing timer
    if (volumeDebounceTimer) {
      clearTimeout(volumeDebounceTimer);
    }

    // Set new debounce timer (50ms)
    const timer = setTimeout(() => {
      onVolumeChange(newVolume);
    }, 50);

    setVolumeDebounceTimer(timer);
  }, [volumeDebounceTimer, onVolumeChange]);

  /**
   * Handle language selection change
   */
  const handleLanguageChange = useCallback(async (event: React.ChangeEvent<HTMLSelectElement>) => {
    const newLanguage = event.target.value;
    
    if (newLanguage === selectedLanguage) {
      return;
    }

    setIsLanguageSwitching(true);
    
    try {
      await onLanguageChange(newLanguage);
    } catch (error) {
      console.error('Language switch failed:', error);
      // Language selector will handle rollback
    } finally {
      setIsLanguageSwitching(false);
    }
  }, [selectedLanguage, onLanguageChange]);

  /**
   * Cleanup debounce timer on unmount
   */
  useEffect(() => {
    return () => {
      if (volumeDebounceTimer) {
        clearTimeout(volumeDebounceTimer);
      }
    };
  }, [volumeDebounceTimer]);

  return (
    <div className="listener-controls" role="region" aria-label="Listener Controls">
      {/* Speaker Status */}
      <div className="speaker-status" role="status" aria-live="polite">
        <h3 className="status-title">Speaker Status</h3>
        <div className="status-indicators">
          {speakerState.isPaused && (
            <span className="status-badge paused">
              <span className="icon">⏸</span>
              <span className="text">Paused</span>
            </span>
          )}
          {speakerState.isMuted && (
            <span className="status-badge muted">
              <span className="icon">🔇</span>
              <span className="text">Muted</span>
            </span>
          )}
          {!speakerState.isPaused && !speakerState.isMuted && (
            <span className="status-badge active">
              <span className="icon">✓</span>
              <span className="text">Broadcasting</span>
            </span>
          )}
        </div>
      </div>

      {/* Control Buttons */}
      <div className="control-buttons">
        {/* Pause/Resume Button */}
        <button
          onClick={onPauseToggle}
          className={`control-button ${isPaused ? 'active' : ''}`}
          aria-label={isPaused ? 'Resume playback' : 'Pause playback'}
          aria-pressed={isPaused}
        >
          {isPaused ? (
            <>
              <span className="icon">▶</span>
              <span className="label">Resume</span>
            </>
          ) : (
            <>
              <span className="icon">⏸</span>
              <span className="label">Pause</span>
            </>
          )}
        </button>

        {/* Mute/Unmute Button */}
        <button
          onClick={onMuteToggle}
          className={`control-button ${isMuted ? 'active' : ''}`}
          aria-label={isMuted ? 'Unmute audio' : 'Mute audio'}
          aria-pressed={isMuted}
        >
          {isMuted ? (
            <>
              <span className="icon">🔇</span>
              <span className="label">Unmute</span>
            </>
          ) : (
            <>
              <span className="icon">🔊</span>
              <span className="label">Mute</span>
            </>
          )}
        </button>
      </div>

      {/* Volume Control */}
      <div className="volume-control">
        <label htmlFor="listener-volume" className="volume-label">
          Playback Volume: {localVolume}%
        </label>
        <input
          id="listener-volume"
          type="range"
          min="0"
          max="100"
          value={localVolume}
          onChange={handleVolumeChange}
          className="volume-slider"
          aria-label="Playback volume"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={localVolume}
        />
      </div>

      {/* Language Selector */}
      <div className="language-selector">
        <label htmlFor="language-select" className="language-label">
          Translation Language:
        </label>
        <select
          id="language-select"
          value={selectedLanguage}
          onChange={handleLanguageChange}
          disabled={isLanguageSwitching}
          className="language-dropdown"
          aria-label="Select translation language"
        >
          {availableLanguages.map((language) => (
            <option
              key={language.code}
              value={language.code}
              disabled={!language.isAvailable}
            >
              {language.name}
              {!language.isAvailable && ' (Unavailable)'}
            </option>
          ))}
        </select>
        {isLanguageSwitching && (
          <span className="language-switching-indicator" role="status">
            Switching...
          </span>
        )}
      </div>

      {/* Buffer Status (shown when paused) */}
      {isPaused && (
        <div className="buffer-status" role="status" aria-live="polite">
          <span className="buffer-icon">⏸</span>
          <span className="buffer-text">
            Playback paused. Audio is being buffered (up to 30 seconds).
          </span>
        </div>
      )}

      {/* Keyboard Shortcuts Hint */}
      <div className="shortcuts-hint" role="note">
        <small>
          Keyboard shortcuts: <kbd>M</kbd> to mute, <kbd>P</kbd> to pause
        </small>
      </div>
    </div>
  );
});

export default ListenerControls;
