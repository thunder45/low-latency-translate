import React, { useState, useEffect } from 'react';

interface LanguageSelectorProps {
  currentLanguage: string;
  availableLanguages: string[];
  onLanguageChange: (language: string) => void;
  isSwitching?: boolean;
  error?: string | null;
}

// Language code to name mapping (subset of common languages)
const LANGUAGE_NAMES: Record<string, string> = {
  'en': 'English',
  'es': 'Spanish',
  'fr': 'French',
  'de': 'German',
  'it': 'Italian',
  'pt': 'Portuguese',
  'ru': 'Russian',
  'ja': 'Japanese',
  'ko': 'Korean',
  'zh': 'Chinese',
  'ar': 'Arabic',
  'hi': 'Hindi',
  'nl': 'Dutch',
  'pl': 'Polish',
  'tr': 'Turkish',
  'sv': 'Swedish',
  'no': 'Norwegian',
  'da': 'Danish',
  'fi': 'Finnish',
  'cs': 'Czech',
  'el': 'Greek',
  'he': 'Hebrew',
  'th': 'Thai',
  'vi': 'Vietnamese',
  'id': 'Indonesian',
  'ms': 'Malay',
  'uk': 'Ukrainian',
  'ro': 'Romanian',
  'hu': 'Hungarian',
  'bg': 'Bulgarian'
};

export const LanguageSelector: React.FC<LanguageSelectorProps> = ({
  currentLanguage,
  availableLanguages,
  onLanguageChange,
  isSwitching = false,
  error = null
}) => {
  const [selectedLanguage, setSelectedLanguage] = useState(currentLanguage);
  const [previousLanguage, setPreviousLanguage] = useState(currentLanguage);

  // Sync selected language with current language prop
  useEffect(() => {
    setSelectedLanguage(currentLanguage);
  }, [currentLanguage]);

  // Handle language switch failure - revert to previous language
  useEffect(() => {
    if (error && previousLanguage !== currentLanguage) {
      setSelectedLanguage(previousLanguage);
    }
  }, [error, previousLanguage, currentLanguage]);

  const handleLanguageChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newLanguage = e.target.value;
    
    // Store previous language for potential revert
    setPreviousLanguage(currentLanguage);
    
    // Update local state immediately for responsive UI
    setSelectedLanguage(newLanguage);
    
    // Trigger language switch
    onLanguageChange(newLanguage);
  };

  const getLanguageName = (code: string): string => {
    return LANGUAGE_NAMES[code] || code.toUpperCase();
  };

  return (
    <div className="language-selector">
      <label htmlFor="language-select" className="language-label">
        Translation Language
      </label>
      
      <div className="selector-wrapper">
        <select
          id="language-select"
          value={selectedLanguage}
          onChange={handleLanguageChange}
          disabled={isSwitching}
          aria-label="Select translation language"
          aria-busy={isSwitching}
          aria-describedby={error ? 'language-error' : undefined}
          className={`language-select ${isSwitching ? 'switching' : ''}`}
        >
          {availableLanguages.map(lang => (
            <option key={lang} value={lang}>
              {getLanguageName(lang)}
            </option>
          ))}
        </select>
        
        {isSwitching && (
          <div className="switching-indicator" role="status" aria-live="polite">
            <span className="spinner"></span>
            <span className="switching-text">
              Switching to {getLanguageName(selectedLanguage)}...
            </span>
          </div>
        )}
      </div>
      
      {error && (
        <div id="language-error" className="error-message" role="alert">
          {error}
        </div>
      )}

      <style jsx>{`
        .language-selector {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .language-label {
          font-size: 14px;
          font-weight: 500;
          color: #555;
        }

        .selector-wrapper {
          position: relative;
        }

        .language-select {
          width: 100%;
          padding: 0.75rem;
          padding-right: 2.5rem;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-size: 16px;
          background-color: white;
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23333' d='M6 9L1 4h10z'/%3E%3C/svg%3E");
          background-repeat: no-repeat;
          background-position: right 0.75rem center;
          background-size: 12px;
          cursor: pointer;
          transition: border-color 0.2s, background-color 0.2s;
          appearance: none;
          -webkit-appearance: none;
          -moz-appearance: none;
        }

        .language-select:hover:not(:disabled) {
          border-color: #4CAF50;
        }

        .language-select:focus {
          outline: none;
          border-color: #4CAF50;
          box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.1);
        }

        .language-select:disabled {
          background-color: #f5f5f5;
          cursor: not-allowed;
          opacity: 0.6;
        }

        .language-select.switching {
          border-color: #4CAF50;
        }

        .switching-indicator {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          margin-top: 0.5rem;
          padding: 0.5rem;
          background-color: #e8f5e9;
          border-radius: 4px;
          font-size: 14px;
          color: #2e7d32;
        }

        .spinner {
          display: inline-block;
          width: 16px;
          height: 16px;
          border: 2px solid #4CAF50;
          border-top-color: transparent;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }

        .switching-text {
          font-weight: 500;
        }

        .error-message {
          margin-top: 0.5rem;
          padding: 0.5rem;
          background-color: #ffebee;
          border-left: 3px solid #f44336;
          border-radius: 4px;
          color: #c62828;
          font-size: 14px;
        }

        /* High contrast mode support */
        @media (prefers-contrast: high) {
          .language-select {
            border-width: 2px;
          }
          
          .language-select:focus {
            border-width: 3px;
          }
        }

        /* Reduced motion support */
        @media (prefers-reduced-motion: reduce) {
          .spinner {
            animation: none;
            border-top-color: #4CAF50;
          }
          
          .language-select {
            transition: none;
          }
        }
      `}</style>
    </div>
  );
};
