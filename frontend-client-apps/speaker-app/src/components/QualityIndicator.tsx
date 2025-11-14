import React, { useEffect, useRef } from 'react';
import { QualityWarning } from '../../../shared/store/speakerStore';

interface QualityIndicatorProps {
  warnings: QualityWarning[];
  onClearWarning: (timestamp: number) => void;
}

/**
 * Quality indicator component showing audio quality warnings
 * 
 * Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
 */
export const QualityIndicator: React.FC<QualityIndicatorProps> = ({
  warnings,
  onClearWarning,
}) => {
  const clearTimersRef = useRef<Map<number, NodeJS.Timeout>>(new Map());

  // Auto-clear warnings after 2 seconds when quality returns to normal
  useEffect(() => {
    // Set up timers for each warning
    warnings.forEach((warning) => {
      if (!clearTimersRef.current.has(warning.timestamp)) {
        const timer = setTimeout(() => {
          onClearWarning(warning.timestamp);
          clearTimersRef.current.delete(warning.timestamp);
        }, 2000);
        clearTimersRef.current.set(warning.timestamp, timer);
      }
    });

    // Cleanup function
    return () => {
      clearTimersRef.current.forEach((timer) => clearTimeout(timer));
      clearTimersRef.current.clear();
    };
  }, [warnings, onClearWarning]);

  const getWarningDetails = (type: QualityWarning['type']) => {
    switch (type) {
      case 'snr_low':
        return {
          icon: '🔊',
          title: 'Background Noise Detected',
          color: '#FFC107',
          bgColor: '#fff3cd',
        };
      case 'clipping':
        return {
          icon: '⚠️',
          title: 'Audio Distortion',
          color: '#f44336',
          bgColor: '#ffebee',
        };
      case 'echo':
        return {
          icon: '🔁',
          title: 'Echo Detected',
          color: '#FF9800',
          bgColor: '#fff3e0',
        };
      case 'silence':
        return {
          icon: '🔇',
          title: 'No Audio Detected',
          color: '#2196F3',
          bgColor: '#e3f2fd',
        };
      default:
        return {
          icon: '⚠️',
          title: 'Audio Issue',
          color: '#666',
          bgColor: '#f5f5f5',
        };
    }
  };

  if (warnings.length === 0) {
    return (
      <div className="quality-indicator-container">
        <div className="quality-status-good">
          <span className="status-icon">✓</span>
          <span className="status-text">Audio Quality: Good</span>
        </div>

        <style>{`
          .quality-indicator-container {
            padding: 1.5rem;
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
          }

          .quality-status-good {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 1rem;
            background-color: #e8f5e9;
            border-left: 4px solid #4CAF50;
            border-radius: 4px;
          }

          .status-icon {
            font-size: 1.5rem;
            color: #4CAF50;
          }

          .status-text {
            font-weight: 600;
            color: #2e7d32;
          }
        `}</style>
      </div>
    );
  }

  return (
    <div className="quality-indicator-container">
      <h3 className="quality-header">Audio Quality Warnings</h3>
      
      <div className="warnings-list">
        {warnings.map((warning) => {
          const details = getWarningDetails(warning.type);
          
          return (
            <div
              key={warning.timestamp}
              className="warning-card"
              style={{
                backgroundColor: details.bgColor,
                borderLeftColor: details.color,
              }}
              role="alert"
            >
              <div className="warning-header">
                <span className="warning-icon">{details.icon}</span>
                <span className="warning-title">{details.title}</span>
              </div>
              <p className="warning-message">{warning.message}</p>
              <div className="warning-timestamp">
                {new Date(warning.timestamp).toLocaleTimeString()}
              </div>
            </div>
          );
        })}
      </div>

      <style>{`
        .quality-indicator-container {
          padding: 1.5rem;
          background-color: white;
          border-radius: 8px;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        .quality-header {
          margin: 0 0 1rem 0;
          font-size: 1.125rem;
          font-weight: 600;
          color: #333;
        }

        .warnings-list {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }

        .warning-card {
          padding: 1rem;
          border-radius: 4px;
          border-left: 4px solid;
          animation: slideIn 0.3s ease-out;
        }

        @keyframes slideIn {
          from {
            opacity: 0;
            transform: translateX(-20px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }

        .warning-header {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          margin-bottom: 0.5rem;
        }

        .warning-icon {
          font-size: 1.5rem;
        }

        .warning-title {
          font-weight: 600;
          font-size: 1rem;
          color: #333;
        }

        .warning-message {
          margin: 0 0 0.5rem 0;
          color: #555;
          line-height: 1.5;
          padding-left: 2.25rem;
        }

        .warning-timestamp {
          font-size: 0.75rem;
          color: #666;
          padding-left: 2.25rem;
          font-style: italic;
        }

        .quality-status-good {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 1rem;
          background-color: #e8f5e9;
          border-left: 4px solid #4CAF50;
          border-radius: 4px;
        }

        .status-icon {
          font-size: 1.5rem;
          color: #4CAF50;
        }

        .status-text {
          font-weight: 600;
          color: #2e7d32;
        }
      `}</style>
    </div>
  );
};
