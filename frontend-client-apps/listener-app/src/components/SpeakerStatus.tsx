import React, { useState, useEffect, useRef } from 'react';

interface SpeakerStatusProps {
  speakerPaused: boolean;
  speakerMuted: boolean;
}

export const SpeakerStatus: React.FC<SpeakerStatusProps> = ({
  speakerPaused,
  speakerMuted
}) => {
  const [showPausedIndicator, setShowPausedIndicator] = useState(speakerPaused);
  const [showMutedIndicator, setShowMutedIndicator] = useState(speakerMuted);
  const pausedTimerRef = useRef<NodeJS.Timeout | null>(null);
  const mutedTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Handle speaker paused state changes with 500ms clear delay
  useEffect(() => {
    if (speakerPaused) {
      // Show indicator immediately when speaker pauses
      setShowPausedIndicator(true);
      
      // Clear any existing timer
      if (pausedTimerRef.current) {
        clearTimeout(pausedTimerRef.current);
        pausedTimerRef.current = null;
      }
    } else {
      // Clear indicator within 500ms when speaker resumes
      pausedTimerRef.current = setTimeout(() => {
        setShowPausedIndicator(false);
      }, 500);
    }

    return () => {
      if (pausedTimerRef.current) {
        clearTimeout(pausedTimerRef.current);
      }
    };
  }, [speakerPaused]);

  // Handle speaker muted state changes with 500ms clear delay
  useEffect(() => {
    if (speakerMuted) {
      // Show indicator immediately when speaker mutes
      setShowMutedIndicator(true);
      
      // Clear any existing timer
      if (mutedTimerRef.current) {
        clearTimeout(mutedTimerRef.current);
        mutedTimerRef.current = null;
      }
    } else {
      // Clear indicator within 500ms when speaker unmutes
      mutedTimerRef.current = setTimeout(() => {
        setShowMutedIndicator(false);
      }, 500);
    }

    return () => {
      if (mutedTimerRef.current) {
        clearTimeout(mutedTimerRef.current);
      }
    };
  }, [speakerMuted]);

  // Don't render anything if no indicators are active
  if (!showPausedIndicator && !showMutedIndicator) {
    return null;
  }

  return (
    <div className="speaker-status">
      {showPausedIndicator && (
        <div 
          className="status-indicator paused"
          role="status"
          aria-live="polite"
          aria-label="Speaker has paused broadcasting"
        >
          <span className="status-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
            </svg>
          </span>
          <span className="status-text">Speaker paused</span>
        </div>
      )}
      
      {showMutedIndicator && (
        <div 
          className="status-indicator muted"
          role="status"
          aria-live="polite"
          aria-label="Speaker has muted their microphone"
        >
          <span className="status-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
            </svg>
          </span>
          <span className="status-text">Speaker muted</span>
        </div>
      )}

      <style jsx>{`
        .speaker-status {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .status-indicator {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.75rem 1rem;
          border-radius: 8px;
          font-size: 14px;
          font-weight: 500;
          border-left: 4px solid;
          animation: slideIn 0.3s ease-out;
        }

        @keyframes slideIn {
          from {
            opacity: 0;
            transform: translateY(-10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .status-indicator.paused {
          background-color: #fff3e0;
          color: #e65100;
          border-left-color: #ff9800;
        }

        .status-indicator.muted {
          background-color: #fce4ec;
          color: #c2185b;
          border-left-color: #e91e63;
        }

        .status-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }

        .status-text {
          flex: 1;
          line-height: 1.4;
        }

        /* Pulsing animation for active states */
        @keyframes pulse {
          0%, 100% {
            opacity: 1;
          }
          50% {
            opacity: 0.7;
          }
        }

        .status-indicator.paused .status-icon,
        .status-indicator.muted .status-icon {
          animation: pulse 2s ease-in-out infinite;
        }

        /* High contrast mode support */
        @media (prefers-contrast: high) {
          .status-indicator {
            border-width: 3px;
            border-style: solid;
          }
          
          .status-indicator.paused {
            border-color: #ff9800;
            background-color: #fff;
          }
          
          .status-indicator.muted {
            border-color: #e91e63;
            background-color: #fff;
          }
        }

        /* Reduced motion support */
        @media (prefers-reduced-motion: reduce) {
          .status-indicator {
            animation: none;
          }
          
          .status-indicator.paused .status-icon,
          .status-indicator.muted .status-icon {
            animation: none;
          }
        }

        /* Responsive design for smaller screens */
        @media (max-width: 480px) {
          .status-indicator {
            padding: 0.6rem 0.8rem;
            font-size: 13px;
          }
          
          .status-icon svg {
            width: 18px;
            height: 18px;
          }
        }

        /* Dark mode support (if needed in future) */
        @media (prefers-color-scheme: dark) {
          .status-indicator.paused {
            background-color: rgba(255, 152, 0, 0.2);
            color: #ffb74d;
          }
          
          .status-indicator.muted {
            background-color: rgba(233, 30, 99, 0.2);
            color: #f48fb1;
          }
        }
      `}</style>
    </div>
  );
};
