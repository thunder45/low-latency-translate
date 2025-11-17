import React, { useState } from 'react';

/**
 * Session configuration
 */
export interface SessionConfig {
  sourceLanguage: string;
  qualityTier: 'standard' | 'premium';
}

interface SessionCreatorProps {
  onCreateSession: (config: SessionConfig) => Promise<void>;
  isCreating: boolean;
  error: string | null;
}

/**
 * Session creator component for speakers
 * 
 * Requirements: 2.1, 2.2, 2.4, 2.5
 */
export const SessionCreator: React.FC<SessionCreatorProps> = ({
  onCreateSession,
  isCreating,
  error,
}) => {
  const [sourceLanguage, setSourceLanguage] = useState('en');
  const [qualityTier, setQualityTier] = useState<'standard' | 'premium'>('standard');

  // Supported source languages (subset for MVP)
  const supportedLanguages = [
    { code: 'en', name: 'English' },
    { code: 'es', name: 'Spanish' },
    { code: 'fr', name: 'French' },
    { code: 'de', name: 'German' },
    { code: 'it', name: 'Italian' },
    { code: 'pt', name: 'Portuguese' },
    { code: 'ja', name: 'Japanese' },
    { code: 'ko', name: 'Korean' },
    { code: 'zh', name: 'Chinese' },
    { code: 'ar', name: 'Arabic' },
  ];

  const handleCreateSession = async () => {
    // Call parent's create session handler with configuration
    await onCreateSession({
      sourceLanguage,
      qualityTier,
    });
  };



  return (
    <div className="session-creator-container">
      <h1>Create Broadcast Session</h1>
      <p>Configure your session settings to start broadcasting</p>

      <div className="session-form">
        <div className="form-group">
          <label htmlFor="source-language">Source Language</label>
          <select
            id="source-language"
            value={sourceLanguage}
            onChange={(e) => setSourceLanguage(e.target.value)}
            disabled={isCreating}
            aria-label="Select source language"
          >
            {supportedLanguages.map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.name}
              </option>
            ))}
          </select>
          <p className="help-text">The language you will speak in</p>
        </div>

        <div className="form-group">
          <label htmlFor="quality-tier">Quality Tier</label>
          <select
            id="quality-tier"
            value={qualityTier}
            onChange={(e) => setQualityTier(e.target.value as 'standard' | 'premium')}
            disabled={isCreating}
            aria-label="Select quality tier"
          >
            <option value="standard">Standard (Audio Dynamics)</option>
            <option value="premium" disabled>Premium (Emotion Transfer - Coming Soon)</option>
          </select>
          <p className="help-text">
            Standard mode preserves volume and speaking rate
          </p>
        </div>

        {isCreating && (
          <div className="progress-message" role="status" aria-live="polite">
            <div className="spinner"></div>
            <span>Creating session...</span>
          </div>
        )}

        {error && (
          <div className="error-message" role="alert">
            <p>{error}</p>
            <button
              onClick={handleCreateSession}
              className="retry-button"
              aria-label="Retry session creation"
            >
              Retry
            </button>
          </div>
        )}

        <button
          onClick={handleCreateSession}
          disabled={isCreating}
          className="create-button"
          aria-label="Create session"
        >
          {isCreating ? 'Creating Session...' : 'Create Session'}
        </button>
      </div>

      <style>{`
        .session-creator-container {
          max-width: 500px;
          margin: 0 auto;
          padding: 2rem;
        }

        .session-creator-container h1 {
          font-size: 2rem;
          margin-bottom: 0.5rem;
          color: var(--text-primary, #1a1a1a);
        }

        .session-creator-container p {
          color: var(--text-secondary, #4a4a4a);
          margin-bottom: 2rem;
        }

        .session-form {
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
        }

        .form-group {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .form-group label {
          font-weight: 600;
          color: var(--text-primary, #1a1a1a);
          font-size: 1rem;
        }

        .form-group select {
          padding: 0.75rem;
          border: 1px solid var(--border-color, #ddd);
          border-radius: 4px;
          font-size: 1rem;
          background-color: var(--input-bg, #ffffff);
          color: var(--text-primary, #1a1a1a);
          cursor: pointer;
        }

        .form-group select option {
          background-color: var(--input-bg, #ffffff);
          color: var(--text-primary, #1a1a1a);
        }

        .form-group select:focus {
          outline: none;
          border-color: #4CAF50;
          box-shadow: 0 0 0 2px rgba(76, 175, 80, 0.2);
        }

        .form-group select:disabled {
          background-color: var(--input-disabled-bg, #f5f5f5);
          cursor: not-allowed;
          opacity: 0.6;
        }

        .help-text {
          font-size: 0.875rem;
          color: var(--text-secondary, #4a4a4a);
          margin: 0;
        }

        .progress-message {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.75rem;
          background-color: var(--info-bg, #e3f2fd);
          color: var(--info-text, #1976d2);
          border-radius: 4px;
          border-left: 4px solid var(--info-border, #1976d2);
        }

        .spinner {
          width: 20px;
          height: 20px;
          border: 3px solid var(--spinner-bg, #e0e0e0);
          border-top-color: var(--spinner-color, #1976d2);
          border-radius: 50%;
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .error-message {
          padding: 0.75rem;
          background-color: var(--error-bg, #ffebee);
          color: var(--error-text, #c62828);
          border-radius: 4px;
          border-left: 4px solid var(--error-border, #c62828);
        }

        .error-message p {
          margin: 0 0 0.5rem 0;
        }

        .retry-button {
          padding: 0.5rem 1rem;
          background-color: var(--error-text, #c62828);
          color: white;
          border: none;
          border-radius: 4px;
          font-size: 0.875rem;
          font-weight: 600;
          cursor: pointer;
          transition: background-color 0.2s;
        }

        .retry-button:hover {
          background-color: var(--error-hover, #b71c1c);
        }

        .retry-button:focus {
          outline: none;
          box-shadow: 0 0 0 3px rgba(198, 40, 40, 0.3);
        }

        .create-button {
          padding: 1rem 2rem;
          background-color: #4CAF50;
          color: white;
          border: none;
          border-radius: 4px;
          font-size: 1.125rem;
          font-weight: 600;
          cursor: pointer;
          transition: background-color 0.2s;
        }

        .create-button:hover:not(:disabled) {
          background-color: #45a049;
        }

        .create-button:disabled {
          background-color: var(--button-disabled-bg, #999);
          cursor: not-allowed;
          opacity: 0.6;
        }

        .create-button:focus {
          outline: none;
          box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.3);
        }

        /* Dark mode support */
        @media (prefers-color-scheme: dark) {
          .session-creator-container h1 {
            color: rgba(255, 255, 255, 0.95);
          }

          .session-creator-container p {
            color: rgba(255, 255, 255, 0.75);
          }

          .form-group label {
            color: rgba(255, 255, 255, 0.95);
          }

          .form-group select {
            background-color: #2a2a2a;
            color: rgba(255, 255, 255, 0.95);
            border-color: #444;
          }

          .form-group select option {
            background-color: #2a2a2a;
            color: rgba(255, 255, 255, 0.95);
          }

          .form-group select:disabled {
            background-color: #1a1a1a;
          }

          .help-text {
            color: rgba(255, 255, 255, 0.65);
          }

          .progress-message {
            background-color: rgba(25, 118, 210, 0.2);
            color: #64b5f6;
            border-left-color: #64b5f6;
          }

          .spinner {
            border-color: #444;
            border-top-color: #64b5f6;
          }

          .error-message {
            background-color: rgba(198, 40, 40, 0.2);
            color: #ff6b6b;
            border-left-color: #ff6b6b;
          }

          .retry-button {
            background-color: #ff6b6b;
          }

          .retry-button:hover {
            background-color: #ff5252;
          }

          .create-button:disabled {
            background-color: #555;
          }
        }
      `}</style>
    </div>
  );
};
