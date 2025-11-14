import React, { useState } from 'react';
import { ErrorHandler, ErrorType } from '../../../shared/utils/ErrorHandler';

interface SessionCreatorProps {
  jwtToken: string;
  onSessionCreated: (sessionId: string, sourceLanguage: string, qualityTier: 'standard' | 'premium') => void;
  onSendMessage: (message: any) => void;
}

/**
 * Session creator component for speakers
 * 
 * Requirements: 2.1, 2.2, 2.4, 2.5
 */
export const SessionCreator: React.FC<SessionCreatorProps> = ({
  jwtToken,
  onSessionCreated,
  onSendMessage,
}) => {
  const [sourceLanguage, setSourceLanguage] = useState('en');
  const [qualityTier, setQualityTier] = useState<'standard' | 'premium'>('standard');
  const [error, setError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

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
    setError(null);
    setIsCreating(true);

    try {
      // Send session creation request via WebSocket
      const message = {
        action: 'createSession',
        token: jwtToken,
        sourceLanguage,
        qualityTier,
      };

      onSendMessage(message);

      // Note: The actual session creation response will be handled by the parent component
      // which listens to WebSocket messages. This component just sends the request.
    } catch (err: any) {
      const errorInfo = ErrorHandler.handle({
        type: ErrorType.NETWORK_ERROR,
        message: err.message || 'Failed to create session',
        originalError: err,
      });

      setError(errorInfo.userMessage);
      setIsCreating(false);
    }
  };

  // This method should be called by parent when session creation response is received
  const handleSessionCreationResponse = (response: any) => {
    if (response.type === 'sessionCreated') {
      onSessionCreated(response.sessionId, sourceLanguage, qualityTier);
    } else if (response.type === 'error') {
      // Handle specific error codes
      if (response.code === 401) {
        setError('Authentication failed. Please log in again');
      } else if (response.code === 429) {
        const retryAfter = response.retryAfter || 60;
        setError(`Too many sessions created. Please wait ${retryAfter} seconds`);
      } else {
        setError(response.message || 'Failed to create session');
      }
      setIsCreating(false);
    }
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

        {error && (
          <div className="error-message" role="alert">
            {error}
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
          color: #333;
        }

        .session-creator-container p {
          color: #666;
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
          color: #333;
          font-size: 1rem;
        }

        .form-group select {
          padding: 0.75rem;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-size: 1rem;
          background-color: white;
          cursor: pointer;
        }

        .form-group select:focus {
          outline: none;
          border-color: #4CAF50;
          box-shadow: 0 0 0 2px rgba(76, 175, 80, 0.2);
        }

        .form-group select:disabled {
          background-color: #f5f5f5;
          cursor: not-allowed;
        }

        .help-text {
          font-size: 0.875rem;
          color: #666;
          margin: 0;
        }

        .error-message {
          padding: 0.75rem;
          background-color: #ffebee;
          color: #c62828;
          border-radius: 4px;
          border-left: 4px solid #c62828;
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
          background-color: #ccc;
          cursor: not-allowed;
        }

        .create-button:focus {
          outline: none;
          box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.3);
        }
      `}</style>
    </div>
  );
};
