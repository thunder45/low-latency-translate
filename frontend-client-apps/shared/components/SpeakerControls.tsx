/**
 * Speaker Controls UI Component
 * 
 * Provides control interface for speakers including pause/resume,
 * mute/unmute, volume control, and listener status display.
 */

import React, { useState, useCallback, useEffect } from 'react';
import type { ListenerState } from '../types/controls';

/**
 * Props for SpeakerControls component
 */
export interface SpeakerControlsProps {
  sessionId: string;
  onPauseToggle: () => void;
  onMuteToggle: () => void;
  onVolumeChange: (volume: number) => void;
  isPaused: boolean;
  isMuted: boolean;
  volume: number;
  listenerCount: number;
  listenerStates?: ListenerState[];
}

/**
 * Speaker Controls Component
 */
export const SpeakerControls: React.FC<SpeakerControlsProps> = ({
  sessionId,
  onPauseToggle,
  onMuteToggle,
  onVolumeChange,
  isPaused,
  isMuted,
  volume,
  listenerCount,
  listenerStates = [],
}) => {
  const [localVolume, setLocalVolume] = useState(volume);
  const [volumeDebounceTimer, setVolumeDebounceTimer] = useState<NodeJS.Timeout | null>(null);

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
   * Cleanup debounce timer on unmount
   */
  useEffect(() => {
    return () => {
      if (volumeDebounceTimer) {
        clearTimeout(volumeDebounceTimer);
      }
    };
  }, [volumeDebounceTimer]);

  /**
   * Get count of paused listeners
   */
  const pausedListenerCount = listenerStates.filter(l => l.isPaused).length;

  /**
   * Get count of muted listeners
   */
  const mutedListenerCount = listenerStates.filter(l => l.isMuted).length;

  return (
    <div className="speaker-controls" role="region" aria-label="Speaker Controls">
      {/* Control Buttons */}
      <div className="control-buttons">
        {/* Pause/Resume Button */}
        <button
          onClick={onPauseToggle}
          className={`control-button ${isPaused ? 'active' : ''}`}
          aria-label={isPaused ? 'Resume broadcasting' : 'Pause broadcasting'}
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
          aria-label={isMuted ? 'Unmute microphone' : 'Mute microphone'}
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
        <label htmlFor="speaker-volume" className="volume-label">
          Input Volume: {localVolume}%
        </label>
        <input
          id="speaker-volume"
          type="range"
          min="0"
          max="100"
          value={localVolume}
          onChange={handleVolumeChange}
          className="volume-slider"
          aria-label="Microphone input volume"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={localVolume}
        />
      </div>

      {/* Listener Statistics */}
      <div className="listener-stats" role="status" aria-live="polite">
        <div className="stat-item">
          <span className="stat-label">Active Listeners:</span>
          <span className="stat-value">{listenerCount}</span>
        </div>

        {listenerStates.length > 0 && (
          <>
            {pausedListenerCount > 0 && (
              <div className="stat-item">
                <span className="stat-label">Paused:</span>
                <span className="stat-value">{pausedListenerCount}</span>
              </div>
            )}

            {mutedListenerCount > 0 && (
              <div className="stat-item">
                <span className="stat-label">Muted:</span>
                <span className="stat-value">{mutedListenerCount}</span>
              </div>
            )}
          </>
        )}
      </div>

      {/* Listener List (if detailed states available) */}
      {listenerStates.length > 0 && (
        <div className="listener-list">
          <h3 className="listener-list-title">Listener Status</h3>
          <ul className="listener-items">
            {listenerStates.map((listener) => (
              <li key={listener.listenerId} className="listener-item">
                <span className="listener-name">
                  {listener.displayName || `Listener ${listener.listenerId.slice(0, 8)}`}
                </span>
                <div className="listener-status">
                  {listener.isPaused && (
                    <span className="status-badge paused" title="Paused">
                      ⏸
                    </span>
                  )}
                  {listener.isMuted && (
                    <span className="status-badge muted" title="Muted">
                      🔇
                    </span>
                  )}
                  {!listener.isPaused && !listener.isMuted && (
                    <span className="status-badge active" title="Active">
                      ✓
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
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
};

export default SpeakerControls;
