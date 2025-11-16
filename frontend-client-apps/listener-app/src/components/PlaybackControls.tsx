import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AccessibleButton } from '../../../shared/components/AccessibleButton';

interface PlaybackControlsProps {
  isPaused: boolean;
  isMuted: boolean;
  volume: number;
  onPauseToggle: () => void;
  onMuteToggle: () => void;
  onVolumeChange: (volume: number) => void;
}

export const PlaybackControls: React.FC<PlaybackControlsProps> = ({
  isPaused,
  isMuted,
  volume,
  onPauseToggle,
  onMuteToggle,
  onVolumeChange
}) => {
  const [localVolume, setLocalVolume] = useState(volume);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastUpdateRef = useRef<number>(0);

  // Sync local volume with prop changes
  useEffect(() => {
    setLocalVolume(volume);
  }, [volume]);

  // Keyboard shortcuts: Ctrl+P for pause, Ctrl+M for mute
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Check for Ctrl (Windows/Linux) or Cmd (Mac)
      const isModifierPressed = e.ctrlKey || e.metaKey;
      
      if (!isModifierPressed) return;
      
      if (e.key === 'p' || e.key === 'P') {
        e.preventDefault();
        onPauseToggle();
      } else if (e.key === 'm' || e.key === 'M') {
        e.preventDefault();
        onMuteToggle();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onPauseToggle, onMuteToggle]);

  // Debounced volume change handler (50ms debounce)
  const handleVolumeChange = useCallback((newVolume: number) => {
    setLocalVolume(newVolume);
    
    // Clear existing timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    
    // Set new timer for debounced update
    debounceTimerRef.current = setTimeout(() => {
      const now = Date.now();
      // Ensure we update button states within 50ms of user interaction
      if (now - lastUpdateRef.current >= 50) {
        onVolumeChange(newVolume);
        lastUpdateRef.current = now;
      }
    }, 50);
  }, [onVolumeChange]);

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  return (
    <div className="playback-controls">
      <div className="control-buttons">
        <AccessibleButton
          onClick={onPauseToggle}
          label={isPaused ? 'Resume' : 'Pause'}
          ariaLabel={isPaused ? 'Resume playback' : 'Pause playback'}
          ariaPressed={isPaused}
          className={`control-button ${isPaused ? 'active' : ''}`}
        >
          {isPaused ? (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z"/>
            </svg>
          ) : (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
            </svg>
          )}
          <span className="button-label">{isPaused ? 'Resume' : 'Pause'}</span>
          <span className="keyboard-hint">Ctrl+P</span>
        </AccessibleButton>

        <AccessibleButton
          onClick={onMuteToggle}
          label={isMuted ? 'Unmute' : 'Mute'}
          ariaLabel={isMuted ? 'Unmute audio' : 'Mute audio'}
          ariaPressed={isMuted}
          className={`control-button ${isMuted ? 'active' : ''}`}
        >
          {isMuted ? (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
            </svg>
          ) : (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
            </svg>
          )}
          <span className="button-label">{isMuted ? 'Unmute' : 'Mute'}</span>
          <span className="keyboard-hint">Ctrl+M</span>
        </AccessibleButton>
      </div>

      <div className="volume-control">
        <label htmlFor="volume-slider" className="volume-label">
          Volume
        </label>
        <input
          id="volume-slider"
          type="range"
          min="0"
          max="100"
          value={localVolume}
          onChange={(e) => handleVolumeChange(Number(e.target.value))}
          aria-label="Volume control"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={localVolume}
          aria-valuetext={`${localVolume}%`}
          className="volume-slider"
        />
        <span className="volume-value" aria-live="polite">
          {localVolume}%
        </span>
      </div>

      <style>{`
        .playback-controls {
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
          padding: 1.5rem;
          background: #ffffff;
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .control-buttons {
          display: flex;
          gap: 1rem;
          justify-content: center;
        }

        .control-button {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.5rem;
          padding: 1rem;
          background: #f5f5f5;
          border: 2px solid transparent;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.05s ease;
          min-width: 100px;
        }

        .control-button:hover {
          background: #e8e8e8;
        }

        .control-button:focus {
          outline: none;
          border-color: #4CAF50;
          box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.2);
        }

        .control-button.active {
          background: #4CAF50;
          color: white;
        }

        .control-button.active:hover {
          background: #45a049;
        }

        .button-label {
          font-size: 14px;
          font-weight: 500;
        }

        .keyboard-hint {
          font-size: 11px;
          opacity: 0.7;
          font-family: monospace;
        }

        .volume-control {
          display: flex;
          align-items: center;
          gap: 1rem;
        }

        .volume-label {
          font-size: 14px;
          font-weight: 500;
          color: #555;
          min-width: 60px;
        }

        .volume-slider {
          flex: 1;
          height: 6px;
          border-radius: 3px;
          background: #ddd;
          outline: none;
          -webkit-appearance: none;
          appearance: none;
        }

        .volume-slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          width: 18px;
          height: 18px;
          border-radius: 50%;
          background: #4CAF50;
          cursor: pointer;
          transition: transform 0.1s;
        }

        .volume-slider::-webkit-slider-thumb:hover {
          transform: scale(1.2);
        }

        .volume-slider::-moz-range-thumb {
          width: 18px;
          height: 18px;
          border-radius: 50%;
          background: #4CAF50;
          cursor: pointer;
          border: none;
          transition: transform 0.1s;
        }

        .volume-slider::-moz-range-thumb:hover {
          transform: scale(1.2);
        }

        .volume-slider:focus {
          outline: none;
        }

        .volume-slider:focus::-webkit-slider-thumb {
          box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.3);
        }

        .volume-slider:focus::-moz-range-thumb {
          box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.3);
        }

        .volume-value {
          font-size: 14px;
          font-weight: 500;
          color: #555;
          min-width: 45px;
          text-align: right;
        }

        /* Ensure high contrast for accessibility */
        @media (prefers-contrast: high) {
          .control-button {
            border-width: 3px;
          }
          
          .control-button.active {
            border-color: #000;
          }
        }
      `}</style>
    </div>
  );
};
