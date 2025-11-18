/**
 * Cognito Authentication Service
 * Handles direct username/password authentication using AWS Cognito USER_PASSWORD_AUTH flow
 */

import {
  CognitoIdentityProviderClient,
  InitiateAuthCommand,
  InitiateAuthCommandInput,
  InitiateAuthCommandOutput,
  AuthFlowType,
} from '@aws-sdk/client-cognito-identity-provider';
import { AuthTokens } from '../utils/storage';

/**
 * Cognito configuration
 */
export interface CognitoConfig {
  userPoolId: string;
  clientId: string;
  region: string;
}

/**
 * Custom authentication error
 */
export class AuthError extends Error {
  constructor(
    message: string,
    public userMessage: string,
    public code?: string
  ) {
    super(message);
    this.name = 'AuthError';
  }
}

/**
 * Cognito Authentication Service
 * Provides methods for login, token refresh, and logout
 */
export class CognitoAuthService {
  private client: CognitoIdentityProviderClient;
  private config: CognitoConfig;

  constructor(config: CognitoConfig) {
    this.config = config;
    this.client = new CognitoIdentityProviderClient({
      region: config.region,
    });
  }

  /**
   * Authenticate user with username and password
   * 
   * @param username - User's username
   * @param password - User's password
   * @returns Authentication tokens
   * @throws AuthError if authentication fails
   */
  async login(username: string, password: string): Promise<AuthTokens> {
    try {
      const params: InitiateAuthCommandInput = {
        AuthFlow: AuthFlowType.USER_PASSWORD_AUTH,
        ClientId: this.config.clientId,
        AuthParameters: {
          USERNAME: username,
          PASSWORD: password,
        },
      };

      const command = new InitiateAuthCommand(params);
      const response: InitiateAuthCommandOutput = await this.client.send(command);

      // Handle NEW_PASSWORD_REQUIRED challenge
      if (response.ChallengeName === 'NEW_PASSWORD_REQUIRED') {
        throw new AuthError(
          'Password change required',
          'Password change required. Please contact administrator.',
          'NEW_PASSWORD_REQUIRED'
        );
      }

      // Extract tokens from response
      if (!response.AuthenticationResult) {
        throw new AuthError(
          'No authentication result returned',
          'Authentication failed. Please try again.',
          'NO_AUTH_RESULT'
        );
      }

      const { AccessToken, IdToken, RefreshToken, ExpiresIn } = response.AuthenticationResult;

      if (!AccessToken || !IdToken || !RefreshToken || !ExpiresIn) {
        throw new AuthError(
          'Missing tokens in authentication result',
          'Authentication failed. Please try again.',
          'MISSING_TOKENS'
        );
      }

      // Convert expiresIn (duration) to expiresAt (absolute timestamp)
      return {
        accessToken: AccessToken,
        idToken: IdToken,
        refreshToken: RefreshToken,
        expiresAt: Date.now() + (ExpiresIn * 1000),
      };
    } catch (error: any) {
      // Handle specific Cognito errors
      if (error instanceof AuthError) {
        throw error;
      }

      const errorCode = error.name || error.code;
      const errorMessage = error.message || 'Unknown error';

      switch (errorCode) {
        case 'NotAuthorizedException':
          throw new AuthError(
            `Authentication failed: ${errorMessage}`,
            'Invalid username or password',
            'INVALID_CREDENTIALS'
          );

        case 'UserNotFoundException':
          // Return same message as NotAuthorizedException for security
          throw new AuthError(
            `User not found: ${errorMessage}`,
            'Invalid username or password',
            'INVALID_CREDENTIALS'
          );

        case 'UserNotConfirmedException':
          throw new AuthError(
            `User not confirmed: ${errorMessage}`,
            'Account not confirmed. Please check your email.',
            'USER_NOT_CONFIRMED'
          );

        case 'NetworkError':
        case 'NetworkingError':
          throw new AuthError(
            `Network error: ${errorMessage}`,
            'Network error. Please check your connection.',
            'NETWORK_ERROR'
          );

        case 'InvalidParameterException':
          throw new AuthError(
            `Invalid parameter: ${errorMessage}`,
            'Authentication not configured correctly',
            'CONFIG_ERROR'
          );

        default:
          console.error('Unexpected authentication error:', error);
          throw new AuthError(
            `Authentication error: ${errorMessage}`,
            'An unexpected error occurred. Please try again.',
            'UNKNOWN_ERROR'
          );
      }
    }
  }

  /**
   * Refresh authentication tokens using refresh token
   * 
   * @param refreshToken - Refresh token from previous authentication
   * @returns New authentication tokens (without new refresh token)
   * @throws AuthError if refresh fails
   */
  async refreshTokens(refreshToken: string): Promise<AuthTokens> {
    try {
      const params: InitiateAuthCommandInput = {
        AuthFlow: AuthFlowType.REFRESH_TOKEN_AUTH,
        ClientId: this.config.clientId,
        AuthParameters: {
          REFRESH_TOKEN: refreshToken,
        },
      };

      const command = new InitiateAuthCommand(params);
      const response: InitiateAuthCommandOutput = await this.client.send(command);

      if (!response.AuthenticationResult) {
        throw new AuthError(
          'No authentication result returned from refresh',
          'Session refresh failed. Please log in again.',
          'NO_AUTH_RESULT'
        );
      }

      const { AccessToken, IdToken, ExpiresIn } = response.AuthenticationResult;

      if (!AccessToken || !IdToken || !ExpiresIn) {
        throw new AuthError(
          'Missing tokens in refresh result',
          'Session refresh failed. Please log in again.',
          'MISSING_TOKENS'
        );
      }

      // Refresh token is not returned in refresh response, use the existing one
      // Convert expiresIn (duration) to expiresAt (absolute timestamp)
      return {
        accessToken: AccessToken,
        idToken: IdToken,
        refreshToken: refreshToken, // Keep the same refresh token
        expiresAt: Date.now() + (ExpiresIn * 1000),
      };
    } catch (error: any) {
      if (error instanceof AuthError) {
        throw error;
      }

      const errorCode = error.name || error.code;
      const errorMessage = error.message || 'Unknown error';

      switch (errorCode) {
        case 'NotAuthorizedException':
          throw new AuthError(
            `Token refresh failed: ${errorMessage}`,
            'Session expired. Please log in again.',
            'SESSION_EXPIRED'
          );

        case 'NetworkError':
        case 'NetworkingError':
          throw new AuthError(
            `Network error during refresh: ${errorMessage}`,
            'Network error. Please check your connection.',
            'NETWORK_ERROR'
          );

        default:
          console.error('Unexpected token refresh error:', error);
          throw new AuthError(
            `Token refresh error: ${errorMessage}`,
            'Session refresh failed. Please log in again.',
            'REFRESH_ERROR'
          );
      }
    }
  }

  /**
   * Logout user
   * Note: This only clears local state. For global sign-out, use GlobalSignOutCommand
   */
  async logout(): Promise<void> {
    // Clear any local state if needed
    // For now, this is a no-op as token clearing is handled by TokenStorage
    return Promise.resolve();
  }
}
