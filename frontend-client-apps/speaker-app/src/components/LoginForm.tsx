/**
 * Login Form Component
 * Provides username/password authentication UI
 */

import React, { useState, FormEvent, KeyboardEvent } from 'react';
import { CognitoAuthService } from '../../../shared/services/CognitoAuthService';
import { TokenStorage } from '../../../shared/services/TokenStorage';
import { getConfig } from '../../../shared/utils/config';
import './LoginForm.css';

interface LoginFormProps {
  onLoginSuccess: () => void;
}

interface LoginFormState {
  username: string;
  password: string;
  isLoading: boolean;
  error: string | null;
}

export function LoginForm({ onLoginSuccess }: LoginFormProps): JSX.Element {
  const [state, setState] = useState<LoginFormState>({
    username: '',
    password: '',
    isLoading: false,
    error: null,
  });

  /**
   * Handle form submission
   */
  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await performLogin();
  };

  /**
   * Handle Enter key press in input fields
   */
  const handleKeyPress = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      performLogin();
    }
  };

  /**
   * Perform login operation
   */
  const performLogin = async () => {
    // Clear previous error
    setState(prev => ({ ...prev, error: null, isLoading: true }));

    try {
      const config = getConfig();

      if (!config.cognito) {
        throw new Error('Authentication not configured');
      }

      // Create auth service
      const authService = new CognitoAuthService({
        userPoolId: config.cognito.userPoolId,
        clientId: config.cognito.clientId,
        region: config.awsRegion,
      });

      // Authenticate
      const tokens = await authService.login(state.username, state.password);

      // Store tokens
      const tokenStorage = TokenStorage.getInstance();
      await tokenStorage.initialize(config.encryptionKey);
      await tokenStorage.storeTokens(tokens);

      // Clear password from memory
      setState(prev => ({ ...prev, password: '', isLoading: false }));

      // Notify success
      onLoginSuccess();
    } catch (error: any) {
      console.error('Login error:', error);
      
      // Extract user-friendly error message
      let errorMessage = 'An unexpected error occurred. Please try again.';
      
      if (error.userMessage) {
        errorMessage = error.userMessage;
      } else if (error.message) {
        errorMessage = error.message;
      }

      setState(prev => ({
        ...prev,
        password: '', // Clear password on error
        isLoading: false,
        error: errorMessage,
      }));
    }
  };

  /**
   * Handle username input change
   */
  const handleUsernameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setState(prev => ({ ...prev, username: event.target.value }));
  };

  /**
   * Handle password input change
   */
  const handlePasswordChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setState(prev => ({ ...prev, password: event.target.value }));
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <h1 className="login-title">Speaker Login</h1>
        <p className="login-subtitle">Sign in to start broadcasting</p>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="username" className="form-label">
              Username
            </label>
            <input
              id="username"
              type="text"
              className="form-input"
              value={state.username}
              onChange={handleUsernameChange}
              onKeyPress={handleKeyPress}
              disabled={state.isLoading}
              required
              autoComplete="username"
              aria-label="Username"
              aria-required="true"
              placeholder="Enter your username"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password" className="form-label">
              Password
            </label>
            <input
              id="password"
              type="password"
              className="form-input"
              value={state.password}
              onChange={handlePasswordChange}
              onKeyPress={handleKeyPress}
              disabled={state.isLoading}
              required
              autoComplete="current-password"
              aria-label="Password"
              aria-required="true"
              placeholder="Enter your password"
            />
          </div>

          {state.error && (
            <div className="error-message" role="alert" aria-live="polite">
              {state.error}
            </div>
          )}

          <button
            type="submit"
            className="login-button"
            disabled={state.isLoading || !state.username || !state.password}
            aria-label={state.isLoading ? 'Logging in...' : 'Log in'}
          >
            {state.isLoading ? (
              <>
                <span className="spinner" aria-hidden="true"></span>
                Logging in...
              </>
            ) : (
              'Log In'
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
