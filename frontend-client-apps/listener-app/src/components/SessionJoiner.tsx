import React, { useState } from 'react';
import { Validator } from '../../../shared/utils/Validator';

interface SessionJoinerProps {
  onJoin: (sessionId: string, targetLanguage: string) => void;
  availableLanguages: string[];
  error?: string | null;
  isJoining?: boolean;
}

export const SessionJoiner: React.FC<SessionJoinerProps> = ({
  onJoin,
  availableLanguages,
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

  const handleSubmit = (e: React.FormEvent) => {
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
    onJoin(trimmedSessionId, targetLanguage);
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
      
      <style jsx>{`
        .session-joiner {
          max-width: 400px;
          margin: 2rem auto;
          padding: 2rem;
          background: #ffffff;
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }
        
        h2 {
          margin: 0 0 1.5rem 0;
          font-size: 24px;
          color: #333;
          text-align: center;
        }
        
        .form-group {
          margin-bottom: 1.5rem;
        }
        
        label {
          display: block;
          margin-bottom: 0.5rem;
          font-weight: 500;
          color: #555;
          font-size: 14px;
        }
        
        input,
        select {
          width: 100%;
          padding: 0.75rem;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-size: 16px;
          transition: border-color 0.2s;
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
          background-color: #f5f5f5;
          cursor: not-allowed;
        }
        
        .error-message {
          margin-top: 0.5rem;
          color: #f44336;
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
          background-color: #cccccc;
          cursor: not-allowed;
        }
        
        .join-button:focus {
          outline: none;
          box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.3);
        }
      `}</style>
    </div>
  );
};
