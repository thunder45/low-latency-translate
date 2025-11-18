/**
 * Unit tests for CognitoAuthService
 */

import { describe, it, expect, vi, beforeEach, Mock } from 'vitest';
import { CognitoAuthService, AuthError } from '../services/CognitoAuthService';
import { CognitoIdentityProviderClient, InitiateAuthCommand } from '@aws-sdk/client-cognito-identity-provider';

// Mock AWS SDK
vi.mock('@aws-sdk/client-cognito-identity-provider', () => ({
  CognitoIdentityProviderClient: vi.fn(),
  InitiateAuthCommand: vi.fn(),
  AuthFlowType: {
    USER_PASSWORD_AUTH: 'USER_PASSWORD_AUTH',
    REFRESH_TOKEN_AUTH: 'REFRESH_TOKEN_AUTH',
  },
}));

describe('CognitoAuthService', () => {
  let authService: CognitoAuthService;
  let mockSend: Mock;

  const mockConfig = {
    userPoolId: 'us-east-1_test123',
    clientId: 'test-client-id',
    region: 'us-east-1',
  };

  beforeEach(() => {
    // Reset mocks
    vi.clearAllMocks();

    // Create mock send function
    mockSend = vi.fn();

    // Mock CognitoIdentityProviderClient
    (CognitoIdentityProviderClient as unknown as Mock).mockImplementation(() => ({
      send: mockSend,
    }));

    // Create service instance
    authService = new CognitoAuthService(mockConfig);
  });

  describe('login', () => {
    it('should successfully authenticate with valid credentials', async () => {
      // Arrange
      const mockResponse = {
        AuthenticationResult: {
          AccessToken: 'mock-access-token',
          IdToken: 'mock-id-token',
          RefreshToken: 'mock-refresh-token',
          ExpiresIn: 3600,
        },
      };
      mockSend.mockResolvedValue(mockResponse);

      // Act
      const result = await authService.login('testuser', 'testpassword');

      // Assert
      expect(result).toEqual({
        accessToken: 'mock-access-token',
        idToken: 'mock-id-token',
        refreshToken: 'mock-refresh-token',
        expiresIn: 3600,
      });
      expect(mockSend).toHaveBeenCalledTimes(1);
    });

    it('should throw AuthError for invalid credentials (NotAuthorizedException)', async () => {
      // Arrange
      const mockError = {
        name: 'NotAuthorizedException',
        message: 'Incorrect username or password',
      };
      mockSend.mockRejectedValue(mockError);

      // Act & Assert
      await expect(authService.login('testuser', 'wrongpassword')).rejects.toThrow(AuthError);
      
      try {
        await authService.login('testuser', 'wrongpassword');
      } catch (error) {
        expect(error).toBeInstanceOf(AuthError);
        expect((error as AuthError).userMessage).toBe('Invalid username or password');
        expect((error as AuthError).code).toBe('INVALID_CREDENTIALS');
      }
    });

    it('should throw AuthError for user not found (UserNotFoundException)', async () => {
      // Arrange
      const mockError = {
        name: 'UserNotFoundException',
        message: 'User does not exist',
      };
      mockSend.mockRejectedValue(mockError);

      // Act & Assert
      try {
        await authService.login('nonexistent', 'password');
      } catch (error) {
        expect(error).toBeInstanceOf(AuthError);
        expect((error as AuthError).userMessage).toBe('Invalid username or password');
        expect((error as AuthError).code).toBe('INVALID_CREDENTIALS');
      }
    });

    it('should throw AuthError for NEW_PASSWORD_REQUIRED challenge', async () => {
      // Arrange
      const mockResponse = {
        ChallengeName: 'NEW_PASSWORD_REQUIRED',
        Session: 'mock-session',
      };
      mockSend.mockResolvedValue(mockResponse);

      // Act & Assert
      try {
        await authService.login('testuser', 'temppassword');
      } catch (error) {
        expect(error).toBeInstanceOf(AuthError);
        expect((error as AuthError).userMessage).toBe('Password change required. Please contact administrator.');
        expect((error as AuthError).code).toBe('NEW_PASSWORD_REQUIRED');
      }
    });

    it('should throw AuthError for network errors', async () => {
      // Arrange
      const mockError = {
        name: 'NetworkError',
        message: 'Network request failed',
      };
      mockSend.mockRejectedValue(mockError);

      // Act & Assert
      try {
        await authService.login('testuser', 'password');
      } catch (error) {
        expect(error).toBeInstanceOf(AuthError);
        expect((error as AuthError).userMessage).toBe('Network error. Please check your connection.');
        expect((error as AuthError).code).toBe('NETWORK_ERROR');
      }
    });

    it('should throw AuthError for user not confirmed', async () => {
      // Arrange
      const mockError = {
        name: 'UserNotConfirmedException',
        message: 'User is not confirmed',
      };
      mockSend.mockRejectedValue(mockError);

      // Act & Assert
      try {
        await authService.login('testuser', 'password');
      } catch (error) {
        expect(error).toBeInstanceOf(AuthError);
        expect((error as AuthError).userMessage).toBe('Account not confirmed. Please check your email.');
        expect((error as AuthError).code).toBe('USER_NOT_CONFIRMED');
      }
    });

    it('should throw AuthError for configuration errors', async () => {
      // Arrange
      const mockError = {
        name: 'InvalidParameterException',
        message: 'Invalid client id',
      };
      mockSend.mockRejectedValue(mockError);

      // Act & Assert
      try {
        await authService.login('testuser', 'password');
      } catch (error) {
        expect(error).toBeInstanceOf(AuthError);
        expect((error as AuthError).userMessage).toBe('Authentication not configured correctly');
        expect((error as AuthError).code).toBe('CONFIG_ERROR');
      }
    });

    it('should throw AuthError for missing authentication result', async () => {
      // Arrange
      const mockResponse = {
        // No AuthenticationResult
      };
      mockSend.mockResolvedValue(mockResponse);

      // Act & Assert
      try {
        await authService.login('testuser', 'password');
      } catch (error) {
        expect(error).toBeInstanceOf(AuthError);
        expect((error as AuthError).code).toBe('NO_AUTH_RESULT');
      }
    });

    it('should throw AuthError for missing tokens in result', async () => {
      // Arrange
      const mockResponse = {
        AuthenticationResult: {
          AccessToken: 'mock-access-token',
          // Missing IdToken, RefreshToken, ExpiresIn
        },
      };
      mockSend.mockResolvedValue(mockResponse);

      // Act & Assert
      try {
        await authService.login('testuser', 'password');
      } catch (error) {
        expect(error).toBeInstanceOf(AuthError);
        expect((error as AuthError).code).toBe('MISSING_TOKENS');
      }
    });
  });

  describe('refreshTokens', () => {
    it('should successfully refresh tokens', async () => {
      // Arrange
      const mockResponse = {
        AuthenticationResult: {
          AccessToken: 'new-access-token',
          IdToken: 'new-id-token',
          ExpiresIn: 3600,
        },
      };
      mockSend.mockResolvedValue(mockResponse);

      // Act
      const result = await authService.refreshTokens('mock-refresh-token');

      // Assert
      expect(result).toEqual({
        accessToken: 'new-access-token',
        idToken: 'new-id-token',
        refreshToken: 'mock-refresh-token', // Same refresh token
        expiresIn: 3600,
      });
      expect(mockSend).toHaveBeenCalledTimes(1);
    });

    it('should throw AuthError for expired refresh token', async () => {
      // Arrange
      const mockError = {
        name: 'NotAuthorizedException',
        message: 'Refresh Token has expired',
      };
      mockSend.mockRejectedValue(mockError);

      // Act & Assert
      try {
        await authService.refreshTokens('expired-token');
      } catch (error) {
        expect(error).toBeInstanceOf(AuthError);
        expect((error as AuthError).userMessage).toBe('Session expired. Please log in again.');
        expect((error as AuthError).code).toBe('SESSION_EXPIRED');
      }
    });

    it('should throw AuthError for network errors during refresh', async () => {
      // Arrange
      const mockError = {
        name: 'NetworkError',
        message: 'Network request failed',
      };
      mockSend.mockRejectedValue(mockError);

      // Act & Assert
      try {
        await authService.refreshTokens('mock-refresh-token');
      } catch (error) {
        expect(error).toBeInstanceOf(AuthError);
        expect((error as AuthError).userMessage).toBe('Network error. Please check your connection.');
        expect((error as AuthError).code).toBe('NETWORK_ERROR');
      }
    });

    it('should throw AuthError for missing authentication result', async () => {
      // Arrange
      const mockResponse = {
        // No AuthenticationResult
      };
      mockSend.mockResolvedValue(mockResponse);

      // Act & Assert
      try {
        await authService.refreshTokens('mock-refresh-token');
      } catch (error) {
        expect(error).toBeInstanceOf(AuthError);
        expect((error as AuthError).code).toBe('NO_AUTH_RESULT');
      }
    });

    it('should throw AuthError for missing tokens in refresh result', async () => {
      // Arrange
      const mockResponse = {
        AuthenticationResult: {
          AccessToken: 'new-access-token',
          // Missing IdToken, ExpiresIn
        },
      };
      mockSend.mockResolvedValue(mockResponse);

      // Act & Assert
      try {
        await authService.refreshTokens('mock-refresh-token');
      } catch (error) {
        expect(error).toBeInstanceOf(AuthError);
        expect((error as AuthError).code).toBe('MISSING_TOKENS');
      }
    });
  });

  describe('logout', () => {
    it('should resolve successfully', async () => {
      // Act & Assert
      await expect(authService.logout()).resolves.toBeUndefined();
    });
  });
});
