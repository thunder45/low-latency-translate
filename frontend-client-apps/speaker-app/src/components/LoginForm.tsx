import React, { useState } from 'react';
import { AuthService } from '../../../shared/services/AuthService';
import { ErrorHandler, ErrorType } from '../../../shared/utils/ErrorHandler';

interface LoginFormProps {
  authService: AuthService;
  onLoginSuccess: (tokens: { idToken: string; accessToken: string; refreshToken: string }) => void;
}

/**
 * Login form component for speaker authentication
 * 
 * Requirements: 1.1, 1.3, 1.5
 */
export const LoginForm: React.FC<LoginFormProps> = ({ authService, onLoginSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      // Validate inputs
      if (!email || !password) {
        setError('Please enter both email and password');
        setIsLoading(false);
        return;
      }

      // Authenticate with Cognito
      const tokens = await authService.signIn(email, password);
      
      // Success - redirect to session creation
      onLoginSuccess(tokens);
    } catch (err: any) {
      // Handle authentication errors with user-friendly messages
      const errorInfo = ErrorHandler.handle({
        type: ErrorType.AUTHENTICATION_ERROR,
        message: err.message || 'Authentication failed',
        originalError: err,
      });

      setError(errorInfo.userMessage);
      setIsLoading(false);
    }
  };

  return (
    <div className="login-form-container">
      <h1>Speaker Login</h1>
      <p>Sign in to create and manage broadcast sessions</p>

      <form onSubmit={handleSubmit} className="login-form">
        <div className="form-group">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="your.email@example.com"
            disabled={isLoading}
            required
            aria-label="Email address"
            autoComplete="email"
          />
        </div>

        <div className="form-group">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter your password"
            disabled={isLoading}
            required
            aria-label="Password"
            autoComplete="current-password"
          />
        </div>

        {error && (
          <div className="error-message" role="alert">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={isLoading}
          className="submit-button"
          aria-label="Sign in"
        >
          {isLoading ? 'Signing in...' : 'Sign In'}
        </button>
      </form>

      <style>{`
        .login-form-container {
          max-width: 400px;
          margin: 0 auto;
          padding: 2rem;
        }

        .login-form-container h1 {
          font-size: 2rem;
          margin-bottom: 0.5rem;
          color: #333;
        }

        .login-form-container p {
          color: #666;
          margin-bottom: 2rem;
        }

        .login-form {
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
        }

        .form-group input {
          padding: 0.75rem;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-size: 1rem;
        }

        .form-group input:focus {
          outline: none;
          border-color: #4CAF50;
          box-shadow: 0 0 0 2px rgba(76, 175, 80, 0.2);
        }

        .form-group input:disabled {
          background-color: #f5f5f5;
          cursor: not-allowed;
        }

        .error-message {
          padding: 0.75rem;
          background-color: #ffebee;
          color: #c62828;
          border-radius: 4px;
          border-left: 4px solid #c62828;
        }

        .submit-button {
          padding: 0.75rem 1.5rem;
          background-color: #4CAF50;
          color: white;
          border: none;
          border-radius: 4px;
          font-size: 1rem;
          font-weight: 600;
          cursor: pointer;
          transition: background-color 0.2s;
        }

        .submit-button:hover:not(:disabled) {
          background-color: #45a049;
        }

        .submit-button:disabled {
          background-color: #ccc;
          cursor: not-allowed;
        }

        .submit-button:focus {
          outline: none;
          box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.3);
        }
      `}</style>
    </div>
  );
};
