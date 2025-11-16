import React, { useState, useEffect, useRef } from 'react';
import { AccessibleButton } from '../../../shared/components/AccessibleButton';

interface BroadcastControlsProps {
  isPaused: boolean;
  isMuted: boolean;
  inputVolume: number;
  onPauseToggle: () => void;
  onMuteToggle: () => void;
  onVolumeChange: (volume: number) => void;
  onEndSession: () => void;
}

/**
 * Broadcast controls component for speaker
 * 
 * Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.3, 7.4, 7.5, 17.1, 17.2
 */
export const BroadcastControls: React.FC<BroadcastControlsProps> = ({
  isPaused,
  isMuted,
  inputVolume,
  onPauseToggle,
  onMuteToggle,
  onVolumeChange,
  onEndSession,
}) => {
  const [showEndConfirmation, setShowEndConfirmation] = useState(false);
  const [volumeValue, setVolumeValue] = useState(inputVolume);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Update local volume when prop changes
  useEffect(() => {
    setVolumeValue(inputVolume);
  }, [inputVolume]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+P or Cmd+P for pause
      if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
        e.preventDefault();
        onPauseToggle();
      }
      // Ctrl+M or Cmd+M for mute
      else if ((e.ctrlKey || e.metaKey) && e.key === 'm') {
        e.preventDefault();
        onMuteToggle();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onPauseToggle, onMuteToggle]);

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newVolume = parseInt(e.target.value, 10);
    setVolumeValue(newVolume);

    // Debounce volume updates (50ms)
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      onVolumeChange(newVolume);
    }, 50);
  };

  const handleEndSessionClick = () => {
    setShowEndConfirmation(true);
  };

  const handleConfirmEndSession = () => {
    setShowEndConfirmation(false);
    onEndSession();
  };

  const handleCancelEndSession = () => {
    setShowEndConfirmation(false);
  };

  return (
    <div className="broadcast-controls-container">
      <div className="controls-row">
        <AccessibleButton
          onClick={onPauseToggle}
          label={isPaused ? 'Resume' : 'Pause'}
          ariaLabel={isPaused ? 'Resume broadcast' : 'Pause broadcast'}
          ariaPressed={isPaused}
          className={`control-button ${isPaused ? 'active' : ''}`}
        >
          <span className="button-icon">{isPaused ? '▶️' : '⏸️'}</span>
          <span className="button-label">{isPaused ? 'Resume' : 'Pause'}</span>
          <span className="keyboard-hint">Ctrl+P</span>
        </AccessibleButton>

        <AccessibleButton
          onClick={onMuteToggle}
          label={isMuted ? 'Unmute' : 'Mute'}
          ariaLabel={isMuted ? 'Unmute microphone' : 'Mute microphone'}
          ariaPressed={isMuted}
          className={`control-button ${isMuted ? 'active' : ''}`}
        >
          <span className="button-icon">{isMuted ? '🔇' : '🔊'}</span>
          <span className="button-label">{isMuted ? 'Unmuted' : 'Mute'}</span>
          <span className="keyboard-hint">Ctrl+M</span>
        </AccessibleButton>
      </div>

      <div className="volume-control">
        <label htmlFor="input-volume" className="volume-label">
          Input Volume
        </label>
        <div className="volume-slider-container">
          <span className="volume-icon">🔉</span>
          <input
            id="input-volume"
            type="range"
            min="0"
            max="100"
            value={volumeValue}
            onChange={handleVolumeChange}
            className="volume-slider"
            aria-label="Input volume"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={volumeValue}
          />
          <span className="volume-value">{volumeValue}%</span>
        </div>
      </div>

      <div className="status-indicators">
        {isPaused && (
          <div className="status-badge paused">
            ⏸️ Broadcast Paused
          </div>
        )}
        {isMuted && (
          <div className="status-badge muted">
            🔇 Microphone Muted
          </div>
        )}
      </div>

      <div className="end-session-section">
        <button
          onClick={handleEndSessionClick}
          className="end-session-button"
          aria-label="End broadcast session"
        >
          End Session
        </button>
      </div>

      {showEndConfirmation && (
        <div className="confirmation-dialog-overlay" role="dialog" aria-modal="true">
          <div className="confirmation-dialog">
            <h3>End Broadcast Session?</h3>
            <p>
              This will disconnect all listeners and end your broadcast.
              This action cannot be undone.
            </p>
            <div className="dialog-buttons">
              <button
                onClick={handleCancelEndSession}
                className="cancel-button"
                aria-label="Cancel"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmEndSession}
                className="confirm-button"
                aria-label="Confirm end session"
              >
                End Session
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .broadcast-controls-container {
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
          padding: 1.5rem;
          background-color: white;
          border-radius: 8px;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        .controls-row {
          display: flex;
          gap: 1rem;
          justify-content: center;
        }

        .control-button {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.5rem;
          padding: 1rem 2rem;
          background-color: #f5f5f5;
          border: 2px solid #ddd;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.05s;
          min-width: 120px;
        }

        .control-button:hover {
          background-color: #e8e8e8;
          border-color: #4CAF50;
        }

        .control-button:focus {
          outline: none;
          box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.3);
        }

        .control-button.active {
          background-color: #4CAF50;
          border-color: #4CAF50;
          color: white;
        }

        .control-button.active .keyboard-hint {
          color: rgba(255, 255, 255, 0.8);
        }

        .button-icon {
          font-size: 2rem;
        }

        .button-label {
          font-weight: 600;
          font-size: 1rem;
        }

        .keyboard-hint {
          font-size: 0.75rem;
          color: #666;
        }

        .volume-control {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .volume-label {
          font-weight: 600;
          color: #333;
        }

        .volume-slider-container {
          display: flex;
          align-items: center;
          gap: 1rem;
        }

        .volume-icon {
          font-size: 1.5rem;
        }

        .volume-slider {
          flex: 1;
          height: 8px;
          border-radius: 4px;
          background: #ddd;
          outline: none;
          -webkit-appearance: none;
        }

        .volume-slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background: #4CAF50;
          cursor: pointer;
        }

        .volume-slider::-moz-range-thumb {
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background: #4CAF50;
          cursor: pointer;
          border: none;
        }

        .volume-slider:focus {
          outline: none;
        }

        .volume-slider:focus::-webkit-slider-thumb {
          box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.3);
        }

        .volume-value {
          font-weight: 600;
          color: #333;
          min-width: 45px;
          text-align: right;
        }

        .status-indicators {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .status-badge {
          padding: 0.75rem 1rem;
          border-radius: 4px;
          font-weight: 600;
          text-align: center;
        }

        .status-badge.paused {
          background-color: #fff3cd;
          color: #856404;
          border: 1px solid #ffc107;
        }

        .status-badge.muted {
          background-color: #f8d7da;
          color: #721c24;
          border: 1px solid #f5c6cb;
        }

        .end-session-section {
          display: flex;
          justify-content: center;
          padding-top: 1rem;
          border-top: 1px solid #eee;
        }

        .end-session-button {
          padding: 0.75rem 2rem;
          background-color: #dc3545;
          color: white;
          border: none;
          border-radius: 4px;
          font-weight: 600;
          cursor: pointer;
          transition: background-color 0.2s;
        }

        .end-session-button:hover {
          background-color: #c82333;
        }

        .end-session-button:focus {
          outline: none;
          box-shadow: 0 0 0 3px rgba(220, 53, 69, 0.3);
        }

        .confirmation-dialog-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background-color: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }

        .confirmation-dialog {
          background-color: white;
          border-radius: 8px;
          padding: 2rem;
          max-width: 400px;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }

        .confirmation-dialog h3 {
          margin: 0 0 1rem 0;
          color: #333;
        }

        .confirmation-dialog p {
          margin: 0 0 1.5rem 0;
          color: #666;
          line-height: 1.5;
        }

        .dialog-buttons {
          display: flex;
          gap: 1rem;
          justify-content: flex-end;
        }

        .cancel-button,
        .confirm-button {
          padding: 0.75rem 1.5rem;
          border: none;
          border-radius: 4px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .cancel-button {
          background-color: #f5f5f5;
          color: #333;
        }

        .cancel-button:hover {
          background-color: #e8e8e8;
        }

        .confirm-button {
          background-color: #dc3545;
          color: white;
        }

        .confirm-button:hover {
          background-color: #c82333;
        }

        .cancel-button:focus,
        .confirm-button:focus {
          outline: none;
          box-shadow: 0 0 0 3px rgba(0, 0, 0, 0.2);
        }
      `}</style>
    </div>
  );
};
