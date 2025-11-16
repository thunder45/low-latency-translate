import React, { useState } from 'react';
import { Validator } from '../../../shared/utils/Validator';

interface SessionJoinerProps {
  onJoin?: (sessionId: string, targetLanguage: string) => void;
  onSessionJoined?: (sessionId: string, targetLanguage: string) => Promise<void>;
  onSendMessage?: (message: any) => void;
  availableLanguages?: string[];
  error?: string | null;
  isJoining?: boolean;
}

export const SessionJoiner: React.FC<SessionJoinerProps> = ({
  onJoin,
  onSessionJoined,
  availableLanguages = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ja', 'ko', 'zh', 'ar'],
  error,
  isJoining = false
}) => {
  const [sessionId, setSessionId] = useState('');
  const [targetLanguage, setTargetLanguage] = useState(availableLanguages[0] || 'es');
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSessionIdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSessionId(value);
    
    // Clear validation error when user types
    if (validationError) {
      setValidationError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const trimmedSessionId = sessionId.trim();
    
    // Validate session ID format before submission
    if (!trimmedSessionId) {
      setValidationError('Session ID is required');
      return;
    }
    
    if (!Validator.isValidSessionId(trimmedSessionId)) {
      setValidationError('Invalid session ID format. Expected format: word-word-number (e.g., golden-eagle-427)');
      return;
    }
    
    // Clear validation error and submit
    setValidationError(null);
    
    // Call the appropriate callback
    if (onSessionJoined) {
      await onSessionJoined(trimmedSessionId, targetLanguage);
    } else if (onJoin) {
      onJoin(trimmedSessionId, targetLanguage);
    }
  };

  return (
    <div className="session-joiner">
      <h2>Join Session</h2>
      
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="sessionId">Session ID</label>
          <input
            id="sessionId"
            type="text"
            value={sessionId}
            onChange={handleSessionIdChange}
            placeholder="e.g., golden-eagle-427"
            required
            aria-label="Session ID"
            aria-invalid={!!validationError || !!error}
            aria-describedby={validationError || error ? 'session-id-error' : undefined}
            disabled={isJoining}
            autoFocus
          />
          {(validationError || error) && (
            <div id="session-id-error" className="error-message" role="alert">
              {validationError || error}
            </div>
          )}
        </div>
        
        <div className="form-group">
          <label htmlFor="targetLanguage">Your Language</label>
          <select
            id="targetLanguage"
            value={targetLanguage}
            onChange={(e) => setTargetLanguage(e.target.value)}
            aria-label="Target language"
            disabled={isJoining}
          >
            {availableLanguages.map(lang => (
              <option key={lang} value={lang}>
                {lang.toUpperCase()}
              </option>
            ))}
          </select>
        </div>
        
        <button 
          type="submit" 
          className="join-button"
          disabled={isJoining || !sessionId.trim()}
          aria-busy={isJoining}
        >
          {isJoining ? 'Joining...' : 'Join Session'}
        </button>
      </form>
      
      <style>{`
        .session-joiner {
          max-width: 400px;
          margin: 2rem auto;
          padding: 2rem;
          background: var(--card-bg, #ffffff);
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }
        
        h2 {
          margin: 0 0 1.5rem 0;
          font-size: 24px;
          color: var(--text-primary, #1a1a1a);
          text-align: center;
        }
        
        .form-group {
          margin-bottom: 1.5rem;
        }
        
        label {
          display: block;
          margin-bottom: 0.5rem;
          font-weight: 500;
          color: var(--text-secondary, #4a4a4a);
          font-size: 14px;
        }
        
        input,
        select {
          width: 100%;
          padding: 0.75rem;
          border: 1px solid var(--border-color, #ddd);
          border-radius: 4px;
          font-size: 16px;
          background-color: var(--input-bg, #ffffff);
          color: var(--text-primary, #1a1a1a);
          transition: border-color 0.2s;
        }

        select option {
          background-color: var(--input-bg, #ffffff);
          color: var(--text-primary, #1a1a1a);
        }
        
        input:focus,
        select:focus {
          outline: none;
          border-color: #4CAF50;
          box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.1);
        }
        
        input[aria-invalid="true"] {
          border-color: #f44336;
        }
        
        input:disabled,
        select:disabled {
          background-color: var(--input-disabled-bg, #f5f5f5);
          cursor: not-allowed;
          opacity: 0.6;
        }
        
        .error-message {
          margin-top: 0.5rem;
          color: var(--error-text, #f44336);
          font-size: 14px;
        }
        
        .join-button {
          width: 100%;
          padding: 0.75rem;
          background-color: #4CAF50;
          color: white;
          border: none;
          border-radius: 4px;
          font-size: 16px;
          font-weight: 500;
          cursor: pointer;
          transition: background-color 0.2s;
        }
        
        .join-button:hover:not(:disabled) {
          background-color: #45a049;
        }
        
        .join-button:disabled {
          background-color: var(--button-disabled-bg, #999);
          cursor: not-allowed;
          opacity: 0.6;
        }
        
        .join-button:focus {
          outline: none;
          box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.3);
        }

        /* Dark mode support */
        @media (prefers-color-scheme: dark) {
          .session-joiner {
            background: #1e1e1e;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
          }

          h2 {
            color: rgba(255, 255, 255, 0.95);
          }

          label {
            color: rgba(255, 255, 255, 0.75);
          }

          input,
          select {
            background-color: #2a2a2a;
            color: rgba(255, 255, 255, 0.95);
            border-color: #444;
          }

          select option {
            background-color: #2a2a2a;
            color: rgba(255, 255, 255, 0.95);
          }

          input:disabled,
          select:disabled {
            background-color: #1a1a1a;
          }

          .error-message {
            color: #ff6b6b;
          }

          .join-button:disabled {
            background-color: #555;
          }
        }
      `}</style>
    </div>
  );
};
