import React, { useState } from 'react';
import { LanguageStats } from '../../../shared/store/speakerStore';

interface SessionDisplayProps {
  sessionId: string;
  listenerCount: number;
  languageDistribution: LanguageStats[];
}

/**
 * Session display component showing session ID and listener statistics
 * 
 * Requirements: 2.2, 5.2, 5.3, 5.4, 5.5
 */
export const SessionDisplay: React.FC<SessionDisplayProps> = ({
  sessionId,
  listenerCount,
  languageDistribution,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopySessionId = async () => {
    try {
      await navigator.clipboard.writeText(sessionId);
      setCopied(true);
      
      // Reset copied state after 2 seconds
      setTimeout(() => {
        setCopied(false);
      }, 2000);
    } catch (err) {
      console.error('Failed to copy session ID:', err);
    }
  };

  return (
    <div className="session-display-container">
      <div className="session-id-section">
        <h2>Session ID</h2>
        <div
          className="session-id"
          onClick={handleCopySessionId}
          role="button"
          tabIndex={0}
          onKeyPress={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              handleCopySessionId();
            }
          }}
          aria-label={`Session ID: ${sessionId}. Click to copy`}
        >
          <span className="session-id-text">{sessionId}</span>
          <span className="copy-icon" aria-hidden="true">
            📋
          </span>
        </div>
        {copied && (
          <div className="copied-indicator" role="status" aria-live="polite">
            ✓ Copied to clipboard!
          </div>
        )}
        <p className="help-text">Share this ID with your listeners</p>
      </div>

      <div className="listener-stats-section">
        <div className="listener-count-card">
          <div className="count-value">{listenerCount}</div>
          <div className="count-label">Active Listeners</div>
        </div>

        {languageDistribution.length > 0 && (
          <div className="language-distribution">
            <h3>Languages</h3>
            <ul className="language-list">
              {languageDistribution.map((lang) => (
                <li key={lang.languageCode} className="language-item">
                  <span className="language-code">{lang.languageCode.toUpperCase()}</span>
                  <span className="language-count">{lang.count}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <style>{`
        .session-display-container {
          display: flex;
          flex-direction: column;
          gap: 2rem;
          padding: 1.5rem;
          background-color: #f9f9f9;
          border-radius: 8px;
        }

        .session-id-section {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .session-id-section h2 {
          font-size: 1.25rem;
          font-weight: 600;
          color: #333;
          margin: 0;
        }

        .session-id {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 1rem 1.5rem;
          background-color: white;
          border: 2px solid #4CAF50;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .session-id:hover {
          background-color: #f0f8f0;
          transform: translateY(-2px);
          box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }

        .session-id:focus {
          outline: none;
          box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.3);
        }

        .session-id-text {
          font-size: 24pt;
          font-weight: 700;
          color: #2e7d32;
          letter-spacing: 0.5px;
        }

        .copy-icon {
          font-size: 1.5rem;
          opacity: 0.6;
        }

        .copied-indicator {
          padding: 0.5rem 1rem;
          background-color: #4CAF50;
          color: white;
          border-radius: 4px;
          text-align: center;
          font-weight: 600;
          animation: fadeIn 0.3s;
        }

        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(-10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .help-text {
          font-size: 0.875rem;
          color: #666;
          margin: 0;
        }

        .listener-stats-section {
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
        }

        .listener-count-card {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 1.5rem;
          background-color: white;
          border-radius: 8px;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        .count-value {
          font-size: 48pt;
          font-weight: 700;
          color: #4CAF50;
          line-height: 1;
        }

        .count-label {
          font-size: 18pt;
          color: #666;
          margin-top: 0.5rem;
        }

        .language-distribution {
          background-color: white;
          border-radius: 8px;
          padding: 1.5rem;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        .language-distribution h3 {
          font-size: 1.125rem;
          font-weight: 600;
          color: #333;
          margin: 0 0 1rem 0;
        }

        .language-list {
          list-style: none;
          padding: 0;
          margin: 0;
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .language-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0.75rem 1rem;
          background-color: #f5f5f5;
          border-radius: 4px;
        }

        .language-code {
          font-weight: 600;
          color: #333;
          font-size: 1rem;
        }

        .language-count {
          font-weight: 700;
          color: #4CAF50;
          font-size: 1.125rem;
        }

        @media (max-width: 768px) {
          .session-id-text {
            font-size: 18pt;
          }

          .count-value {
            font-size: 36pt;
          }

          .count-label {
            font-size: 14pt;
          }
        }
      `}</style>
    </div>
  );
};
