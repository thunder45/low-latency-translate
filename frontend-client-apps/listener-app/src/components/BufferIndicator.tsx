import React from 'react';

interface BufferIndicatorProps {
  bufferedDuration: number; // 0-30 seconds
  isBuffering: boolean;
  bufferOverflow: boolean;
}

export const BufferIndicator: React.FC<BufferIndicatorProps> = ({
  bufferedDuration,
  isBuffering,
  bufferOverflow
}) => {
  const maxBuffer = 30; // Maximum buffer duration in seconds
  const bufferPercentage = Math.min((bufferedDuration / maxBuffer) * 100, 100);
  
  // Determine buffer status color
  const getBufferColor = (): string => {
    if (bufferOverflow) return '#f44336'; // Red for overflow
    if (isBuffering) return '#ff9800'; // Orange for buffering
    if (bufferedDuration < 2) return '#ff9800'; // Orange for low buffer
    if (bufferedDuration > 25) return '#ff9800'; // Orange for near-full
    return '#4CAF50'; // Green for healthy buffer
  };

  // Format duration for display
  const formatDuration = (seconds: number): string => {
    return `${seconds.toFixed(1)}s`;
  };

  return (
    <div className="buffer-indicator">
      <div className="buffer-header">
        <span className="buffer-label">Audio Buffer</span>
        <span className="buffer-duration" aria-live="polite">
          {formatDuration(bufferedDuration)} / {maxBuffer}s
        </span>
      </div>
      
      <div className="buffer-bar-container">
        <div 
          className="buffer-bar"
          style={{
            width: `${bufferPercentage}%`,
            backgroundColor: getBufferColor()
          }}
          role="progressbar"
          aria-valuenow={bufferedDuration}
          aria-valuemin={0}
          aria-valuemax={maxBuffer}
          aria-label="Audio buffer level"
        />
      </div>
      
      {isBuffering && (
        <div className="buffer-status buffering" role="status" aria-live="polite">
          <span className="status-icon">⏳</span>
          <span className="status-text">Buffering...</span>
        </div>
      )}
      
      {bufferOverflow && (
        <div className="buffer-status overflow" role="alert">
          <span className="status-icon">⚠️</span>
          <span className="status-text">
            Buffer full - audio being skipped
          </span>
        </div>
      )}
      
      {!isBuffering && !bufferOverflow && bufferedDuration < 2 && (
        <div className="buffer-status low" role="status" aria-live="polite">
          <span className="status-icon">⚡</span>
          <span className="status-text">Low buffer</span>
        </div>
      )}

      <style jsx>{`
        .buffer-indicator {
          padding: 1rem;
          background: #ffffff;
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .buffer-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 0.75rem;
        }

        .buffer-label {
          font-size: 14px;
          font-weight: 500;
          color: #555;
        }

        .buffer-duration {
          font-size: 14px;
          font-weight: 600;
          color: #333;
          font-family: monospace;
        }

        .buffer-bar-container {
          width: 100%;
          height: 8px;
          background-color: #e0e0e0;
          border-radius: 4px;
          overflow: hidden;
          position: relative;
        }

        .buffer-bar {
          height: 100%;
          transition: width 0.3s ease, background-color 0.3s ease;
          border-radius: 4px;
        }

        .buffer-status {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          margin-top: 0.75rem;
          padding: 0.5rem;
          border-radius: 4px;
          font-size: 14px;
          font-weight: 500;
        }

        .buffer-status.buffering {
          background-color: #fff3e0;
          color: #e65100;
          border-left: 3px solid #ff9800;
        }

        .buffer-status.overflow {
          background-color: #ffebee;
          color: #c62828;
          border-left: 3px solid #f44336;
        }

        .buffer-status.low {
          background-color: #fff3e0;
          color: #e65100;
          border-left: 3px solid #ff9800;
        }

        .status-icon {
          font-size: 16px;
          line-height: 1;
        }

        .status-text {
          flex: 1;
        }

        /* Animation for buffering state */
        @keyframes pulse {
          0%, 100% {
            opacity: 1;
          }
          50% {
            opacity: 0.6;
          }
        }

        .buffer-status.buffering .status-icon {
          animation: pulse 1.5s ease-in-out infinite;
        }

        /* High contrast mode support */
        @media (prefers-contrast: high) {
          .buffer-bar-container {
            border: 2px solid #333;
          }
          
          .buffer-status {
            border-width: 2px;
            border-style: solid;
          }
          
          .buffer-status.buffering {
            border-color: #ff9800;
          }
          
          .buffer-status.overflow {
            border-color: #f44336;
          }
          
          .buffer-status.low {
            border-color: #ff9800;
          }
        }

        /* Reduced motion support */
        @media (prefers-reduced-motion: reduce) {
          .buffer-bar {
            transition: none;
          }
          
          .buffer-status.buffering .status-icon {
            animation: none;
          }
        }

        /* Responsive design for smaller screens */
        @media (max-width: 480px) {
          .buffer-indicator {
            padding: 0.75rem;
          }
          
          .buffer-header {
            font-size: 13px;
          }
          
          .buffer-duration {
            font-size: 13px;
          }
          
          .buffer-status {
            font-size: 13px;
            padding: 0.4rem;
          }
        }
      `}</style>
    </div>
  );
};
