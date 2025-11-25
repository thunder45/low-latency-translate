/**
 * AuthGuard Component
 * 
 * Protects routes by checking authentication status.
 * Shows login form if not authenticated.
 * Implements automatic token refresh with concurrent protection.
 */

import React, { useEffect, useState, useRef } from 'react';
import { TokenStorage } from '../../../shared/services/TokenStorage';
import { CognitoAuthService } from '../../../shared/services/CognitoAuthService';
import { getConfig } from '../../../shared/utils/config';
import { LoginForm } from './LoginForm';
import { AUTH_CONSTANTS } from '../../../shared/constants/auth';

/**
 * AuthGuard props
 */
export interface AuthGuardProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

/**
 * AuthGuard component
 */
export function AuthGuard({ children, fallback }: AuthGuardProps): JSX.Element {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [isChecking, setIsChecking] = useState(true);
  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);
  const refreshPromiseRef = useRef<Promise<boolean> | null>(null);

  useEffect(() => {
    checkAuthentication();

    // Cleanup timer on unmount
    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
    };
  }, []);

  /**
   * Check if user is authenticated
   */
  const checkAuthentication = async () => {
    try {
      const config = getConfig();
      const tokenStorage = TokenStorage.getInstance();
      await tokenStorage.initialize(config.encryptionKey);
      const tokens = await tokenStorage.getTokens();

      if (!tokens) {
        setIsAuthenticated(false);
        setIsChecking(false);
        return;
      }

      // Check if tokens are expired
      const now = Date.now();
      if (tokens.expiresAt <= now) {
        // Try to refresh tokens
        const refreshed = await refreshTokens(tokens.refreshToken);
        setIsAuthenticated(refreshed);
        setIsChecking(false);
        return;
      }

      // Tokens are valid
      setIsAuthenticated(true);
      setIsChecking(false);

      // Schedule auto-refresh 5 minutes before expiry
      scheduleTokenRefresh(new Date(tokens.expiresAt), tokens.refreshToken);
    } catch (error) {
      console.error('Authentication check failed:', error);
      setIsAuthenticated(false);
      setIsChecking(false);
    }
  };

  /**
   * Refresh authentication tokens with concurrent protection
   * 
   * Prevents multiple simultaneous refresh operations by reusing
   * an existing refresh promise if one is already in progress.
   */
  const refreshTokens = async (refreshToken: string): Promise<boolean> => {
    // Return existing promise if refresh already in progress
    if (refreshPromiseRef.current) {
      console.log('[AuthGuard] Refresh already in progress, reusing promise');
      return refreshPromiseRef.current;
    }

    // Create new refresh promise
    refreshPromiseRef.current = performRefresh(refreshToken);

    try {
      return await refreshPromiseRef.current;
    } finally {
      refreshPromiseRef.current = null;
    }
  };

  /**
   * Perform actual token refresh
   */
  const performRefresh = async (refreshToken: string): Promise<boolean> => {
    try {
      const config = getConfig();

      if (!config.cognito) {
        console.error('[AuthGuard] Cognito not configured');
        return false;
      }

      const authService = new CognitoAuthService({
        userPoolId: config.cognito.userPoolId,
        clientId: config.cognito.clientId,
        region: config.awsRegion,
      });

      const tokens = await authService.refreshTokens(refreshToken);
      const tokenStorage = TokenStorage.getInstance();
      await tokenStorage.initialize(config.encryptionKey);

      await tokenStorage.storeTokens(tokens);

      // Schedule next refresh
      scheduleTokenRefresh(
        new Date(tokens.expiresAt),
        tokens.refreshToken
      );

      return true;
    } catch (error) {
      console.error('[AuthGuard] Token refresh failed:', error);
      
      // Clear stored tokens on refresh failure
      try {
        const config = getConfig();
        const tokenStorage = TokenStorage.getInstance();
        await tokenStorage.initialize(config.encryptionKey);
        await tokenStorage.clearTokens();
      } catch (clearError) {
        console.error('[AuthGuard] Failed to clear tokens:', clearError);
      }
      
      return false;
    }
  };

  /**
   * Schedule automatic token refresh
   * 
   * Refreshes tokens 5 minutes before expiry to ensure seamless
   * user experience without interruption.
   * 
   * @param expiresAt - Token expiration timestamp
   * @param refreshToken - Refresh token for obtaining new tokens
   */
  const scheduleTokenRefresh = (expiresAt: Date, refreshToken: string) => {
    // Clear existing timer
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
    }

    // Calculate time until refresh (5 minutes before expiry)
    const timeUntilRefresh = expiresAt.getTime() - Date.now() - AUTH_CONSTANTS.TOKEN_REFRESH_THRESHOLD_MS;

    // Only schedule if more than 1 minute away
    if (timeUntilRefresh > 60 * 1000) {
      refreshTimerRef.current = setTimeout(async () => {
        console.log('[AuthGuard] Auto-refreshing tokens...');
        const refreshed = await refreshTokens(refreshToken);
        if (!refreshed) {
          // Refresh failed, show login form
          console.error('[AuthGuard] Auto-refresh failed, redirecting to login');
          setIsAuthenticated(false);
        }
      }, timeUntilRefresh);
    }
  };

  /**
   * Handle successful login
   */
  const handleLoginSuccess = () => {
    setIsAuthenticated(true);
    checkAuthentication(); // Re-check to set up refresh timer
  };

  // Show loading state while checking
  if (isChecking) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        flexDirection: 'column',
        gap: '1rem',
      }}>
        <div style={{
          width: '40px',
          height: '40px',
          border: '4px solid #f3f3f3',
          borderTop: '4px solid #3498db',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite',
        }} />
        <p>Checking authentication...</p>
        <style>{`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  // Show login form if not authenticated
  if (!isAuthenticated) {
    if (fallback) {
      return <>{fallback}</>;
    }
    return <LoginForm onLoginSuccess={handleLoginSuccess} />;
  }

  // Render children if authenticated
  return <>{children}</>;
}
