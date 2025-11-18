/**
 * AuthGuard Component Tests
 * 
 * Tests route protection, token refresh, and concurrent refresh prevention
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { AuthGuard } from '../AuthGuard';
import { TokenStorage } from '../../../../shared/services/TokenStorage';
import { CognitoAuthService } from '../../../../shared/services/CognitoAuthService';
import type { AuthTokens } from '../../../../shared/utils/storage';

// Mock dependencies
vi.mock('../../../../shared/services/TokenStorage');
vi.mock('../../../../shared/services/CognitoAuthService');
vi.mock('../LoginForm', () => ({
  LoginForm: ({ onLoginSuccess }: any) => (
    <form role="form" data-testid="login-form">
      <button type="button" onClick={onLoginSuccess}>Login</button>
    </form>
  ),
}));
vi.mock('../../../../shared/utils/config', () => ({
  getConfig: vi.fn(() => ({
    encryptionKey: 'test-encryption-key-32-chars-long-minimum-required',
    cognito: {
      userPoolId: 'us-east-1_TEST',
      clientId: 'test-client-id',
    },
    awsRegion: 'us-east-1',
  })),
}));

describe('AuthGuard', () => {
  let mockTokenStorage: any;
  let mockAuthService: any;

  const validTokens: AuthTokens = {
    idToken: 'valid-id-token',
    accessToken: 'valid-access-token',
    refreshToken: 'valid-refresh-token',
    expiresAt: Date.now() + 3600000, // 1 hour from now
  };

  const expiredTokens: AuthTokens = {
    ...validTokens,
    expiresAt: Date.now() - 1000, // 1 second ago
  };

  const soonToExpireTokens: AuthTokens = {
    ...validTokens,
    expiresAt: Date.now() + 240000, // 4 minutes from now (within 5 min threshold)
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();

    // Setup TokenStorage mock
    mockTokenStorage = {
      getInstance: vi.fn(),
      initialize: vi.fn().mockResolvedValue(undefined),
      getTokens: vi.fn(),
      storeTokens: vi.fn().mockResolvedValue(undefined),
      clearTokens: vi.fn().mockResolvedValue(undefined),
    };
    (TokenStorage.getInstance as any).mockReturnValue(mockTokenStorage);

    // Setup CognitoAuthService mock
    mockAuthService = {
      refreshTokens: vi.fn(),
    };
    (CognitoAuthService as any).mockImplementation(() => mockAuthService);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllTimers();
  });

  describe('authentication state', () => {
    it('should show loading state while checking authentication', () => {
      mockTokenStorage.getTokens.mockImplementation(() => new Promise(() => {})); // Never resolves

      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      expect(screen.getByText('Checking authentication...')).toBeInTheDocument();
    });

    it('should render children when authenticated with valid tokens', async () => {
      mockTokenStorage.getTokens.mockResolvedValue(validTokens);

      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      await waitFor(() => {
        expect(screen.getByText('Protected Content')).toBeInTheDocument();
      });
    });

    it('should show login form when not authenticated', async () => {
      mockTokenStorage.getTokens.mockResolvedValue(null);

      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      await waitFor(() => {
        expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
        expect(screen.getByTestId('login-form')).toBeInTheDocument();
      });
    });

    it('should show custom fallback when provided and not authenticated', async () => {
      mockTokenStorage.getTokens.mockResolvedValue(null);

      render(
        <AuthGuard fallback={<div>Custom Fallback</div>}>
          <div>Protected Content</div>
        </AuthGuard>
      );

      await waitFor(() => {
        expect(screen.getByText('Custom Fallback')).toBeInTheDocument();
        expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
      });
    });
  });

  describe('token refresh', () => {
    it('should attempt refresh when tokens are expired', async () => {
      mockTokenStorage.getTokens.mockResolvedValue(expiredTokens);
      mockAuthService.refreshTokens.mockResolvedValue({
        idToken: 'new-id-token',
        accessToken: 'new-access-token',
        refreshToken: 'new-refresh-token',
        expiresIn: 3600,
      });

      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      await waitFor(() => {
        expect(mockAuthService.refreshTokens).toHaveBeenCalledWith(expiredTokens.refreshToken);
      });

      await waitFor(() => {
        expect(mockTokenStorage.storeTokens).toHaveBeenCalled();
      });
    });

    it('should show login form when refresh fails', async () => {
      mockTokenStorage.getTokens.mockResolvedValue(expiredTokens);
      mockAuthService.refreshTokens.mockRejectedValue(new Error('Refresh failed'));

      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      await waitFor(() => {
        expect(mockAuthService.refreshTokens).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(mockTokenStorage.clearTokens).toHaveBeenCalled();
        expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
      });
    });

    it('should render children after successful refresh', async () => {
      mockTokenStorage.getTokens.mockResolvedValue(expiredTokens);
      mockAuthService.refreshTokens.mockResolvedValue({
        idToken: 'new-id-token',
        accessToken: 'new-access-token',
        refreshToken: 'new-refresh-token',
        expiresIn: 3600,
      });

      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      await waitFor(() => {
        expect(mockAuthService.refreshTokens).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(screen.getByText('Protected Content')).toBeInTheDocument();
      });
    });
  });

  describe('concurrent refresh protection', () => {
    it('should prevent multiple simultaneous refresh operations', async () => {
      mockTokenStorage.getTokens.mockResolvedValue(expiredTokens);
      
      let refreshResolve: any;
      const refreshPromise = new Promise((resolve) => {
        refreshResolve = resolve;
      });
      
      mockAuthService.refreshTokens.mockReturnValue(refreshPromise);

      // Render component which will trigger first refresh
      const { rerender } = render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      // Wait for first refresh to start
      await waitFor(() => {
        expect(mockAuthService.refreshTokens).toHaveBeenCalledTimes(1);
      });

      // Trigger another check (simulating concurrent refresh attempt)
      rerender(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      // Should still only have one refresh call
      expect(mockAuthService.refreshTokens).toHaveBeenCalledTimes(1);

      // Resolve the refresh
      refreshResolve({
        idToken: 'new-id-token',
        accessToken: 'new-access-token',
        refreshToken: 'new-refresh-token',
        expiresIn: 3600,
      });

      await waitFor(() => {
        expect(mockTokenStorage.storeTokens).toHaveBeenCalled();
      });
    });
  });

  describe('refresh scheduling', () => {
    it('should schedule refresh 5 minutes before expiry', async () => {
      const futureExpiry = Date.now() + 600000; // 10 minutes from now
      const tokensWithFutureExpiry = {
        ...validTokens,
        expiresAt: futureExpiry,
      };

      mockTokenStorage.getTokens.mockResolvedValue(tokensWithFutureExpiry);

      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      await waitFor(() => {
        expect(screen.getByText('Protected Content')).toBeInTheDocument();
      });

      // Verify timer was set (5 minutes before expiry = 5 minutes from now)
      const expectedDelay = 300000; // 5 minutes in ms
      
      // Fast-forward to just before the scheduled refresh
      vi.advanceTimersByTime(expectedDelay - 1000);
      expect(mockAuthService.refreshTokens).not.toHaveBeenCalled();

      // Fast-forward past the scheduled refresh
      mockAuthService.refreshTokens.mockResolvedValue({
        idToken: 'refreshed-id-token',
        accessToken: 'refreshed-access-token',
        refreshToken: 'refreshed-refresh-token',
        expiresIn: 3600,
      });

      vi.advanceTimersByTime(2000);

      await waitFor(() => {
        expect(mockAuthService.refreshTokens).toHaveBeenCalled();
      });
    });

    it('should not schedule refresh if token expires in less than 1 minute', async () => {
      const nearExpiry = Date.now() + 30000; // 30 seconds from now
      const tokensNearExpiry = {
        ...validTokens,
        expiresAt: nearExpiry,
      };

      mockTokenStorage.getTokens.mockResolvedValue(tokensNearExpiry);

      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      await waitFor(() => {
        expect(screen.getByText('Protected Content')).toBeInTheDocument();
      });

      // Fast-forward time
      vi.advanceTimersByTime(60000);

      // Should not have scheduled a refresh
      expect(mockAuthService.refreshTokens).not.toHaveBeenCalled();
    });
  });

  describe('timer cleanup', () => {
    it('should clear timer on component unmount', async () => {
      mockTokenStorage.getTokens.mockResolvedValue(validTokens);

      const { unmount } = render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      await waitFor(() => {
        expect(screen.getByText('Protected Content')).toBeInTheDocument();
      });

      // Unmount component
      unmount();

      // Fast-forward time
      mockAuthService.refreshTokens.mockResolvedValue({
        idToken: 'new-id-token',
        accessToken: 'new-access-token',
        refreshToken: 'new-refresh-token',
        expiresIn: 3600,
      });

      vi.advanceTimersByTime(600000); // 10 minutes

      // Timer should have been cleared, so no refresh should occur
      expect(mockAuthService.refreshTokens).not.toHaveBeenCalled();
    });
  });

  describe('error handling', () => {
    it('should handle TokenStorage initialization errors', async () => {
      mockTokenStorage.initialize.mockRejectedValue(new Error('Init failed'));

      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      await waitFor(() => {
        expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
      });
    });

    it('should handle TokenStorage getTokens errors', async () => {
      mockTokenStorage.getTokens.mockRejectedValue(new Error('Get tokens failed'));

      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      await waitFor(() => {
        expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
      });
    });

    it('should handle missing Cognito configuration', async () => {
      const { getConfig } = await import('../../../../shared/utils/config');
      (getConfig as any).mockReturnValue({
        encryptionKey: 'test-key-32-chars-long-minimum',
        cognito: null, // Missing Cognito config
        awsRegion: 'us-east-1',
      });

      mockTokenStorage.getTokens.mockResolvedValue(expiredTokens);

      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      await waitFor(() => {
        expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
      });
    });
  });

  describe('auto-refresh on scheduled timer', () => {
    it('should redirect to login if auto-refresh fails', async () => {
      const futureExpiry = Date.now() + 600000; // 10 minutes from now
      const tokensWithFutureExpiry = {
        ...validTokens,
        expiresAt: futureExpiry,
      };

      mockTokenStorage.getTokens.mockResolvedValue(tokensWithFutureExpiry);
      mockAuthService.refreshTokens.mockRejectedValue(new Error('Refresh failed'));

      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      );

      await waitFor(() => {
        expect(screen.getByText('Protected Content')).toBeInTheDocument();
      });

      // Fast-forward to scheduled refresh time (5 minutes before expiry)
      vi.advanceTimersByTime(300000);

      await waitFor(() => {
        expect(mockAuthService.refreshTokens).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
      });
    });
  });
});
