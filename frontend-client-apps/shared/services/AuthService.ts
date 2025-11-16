import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserSession,
  CognitoRefreshToken,
} from 'amazon-cognito-identity-js';
import { SecureStorage } from '../utils/SecureStorage';
import { STORAGE_KEYS, AuthTokens } from '../utils/storage';

/**
 * Authentication service configuration
 */
export interface AuthConfig {
  userPoolId: string;
  clientId: string;
}

/**
 * Sign in result
 */
export interface SignInResult {
  success: boolean;
  tokens?: AuthTokens;
  userId?: string;
  error?: string;
}

/**
 * Authentication service for speaker application
 * Handles AWS Cognito authentication and token management
 */
export class AuthService {
  private userPool: CognitoUserPool;
  private currentUser: CognitoUser | null = null;
  private storage: SecureStorage | null = null;

  /**
   * Initialize authentication service
   * @param config - Authentication configuration
   */
  constructor(config: AuthConfig) {
    this.userPool = new CognitoUserPool({
      UserPoolId: config.userPoolId,
      ClientId: config.clientId,
    });
  }

  /**
   * Sign in with email and password
   * @param email - User email
   * @param password - User password
   * @returns Sign in result with tokens
   */
  async signIn(email: string, password: string): Promise<SignInResult> {
    return new Promise((resolve) => {
      const authenticationDetails = new AuthenticationDetails({
        Username: email,
        Password: password,
      });

      const cognitoUser = new CognitoUser({
        Username: email,
        Pool: this.userPool,
      });

      cognitoUser.authenticateUser(authenticationDetails, {
        onSuccess: (session: CognitoUserSession) => {
          this.currentUser = cognitoUser;

          // Extract tokens
          const tokens: AuthTokens = {
            idToken: session.getIdToken().getJwtToken(),
            accessToken: session.getAccessToken().getJwtToken(),
            refreshToken: session.getRefreshToken().getToken(),
            expiresAt: session.getIdToken().getExpiration() * 1000, // Convert to milliseconds
          };

          // Get user ID from token payload
          const userId = session.getIdToken().payload.sub;

          // Initialize secure storage with user ID
          this.storage = new SecureStorage(userId);

          // Store tokens securely
          this.storage.set(STORAGE_KEYS.AUTH_TOKENS, tokens);
          this.storage.set(STORAGE_KEYS.USER_ID, userId);

          resolve({
            success: true,
            tokens,
            userId,
          });
        },

        onFailure: (error) => {
          resolve({
            success: false,
            error: error.message || 'Authentication failed',
          });
        },

        newPasswordRequired: () => {
          resolve({
            success: false,
            error: 'New password required. Please reset your password.',
          });
        },
      });
    });
  }

  /**
   * Refresh session using refresh token
   * @returns New tokens or null if refresh fails
   */
  async refreshSession(): Promise<AuthTokens | null> {
    return new Promise((resolve) => {
      if (!this.currentUser) {
        // Try to get current user from session
        this.currentUser = this.userPool.getCurrentUser();
      }

      if (!this.currentUser) {
        resolve(null);
        return;
      }

      // Capture currentUser in local constant for type safety in callbacks
      const currentUser = this.currentUser;

      currentUser.getSession((error: Error | null, session: CognitoUserSession | null) => {
        if (error || !session) {
          resolve(null);
          return;
        }

        // Check if session is still valid
        if (session.isValid()) {
          const tokens: AuthTokens = {
            idToken: session.getIdToken().getJwtToken(),
            accessToken: session.getAccessToken().getJwtToken(),
            refreshToken: session.getRefreshToken().getToken(),
            expiresAt: session.getIdToken().getExpiration() * 1000,
          };

          // Update stored tokens
          if (this.storage) {
            this.storage.set(STORAGE_KEYS.AUTH_TOKENS, tokens);
          }

          resolve(tokens);
        } else {
          // Session expired, try to refresh
          const refreshToken = new CognitoRefreshToken({
            RefreshToken: session.getRefreshToken().getToken(),
          });

          currentUser.refreshSession(refreshToken, (refreshError, newSession) => {
            if (refreshError || !newSession) {
              resolve(null);
              return;
            }

            const tokens: AuthTokens = {
              idToken: newSession.getIdToken().getJwtToken(),
              accessToken: newSession.getAccessToken().getJwtToken(),
              refreshToken: newSession.getRefreshToken().getToken(),
              expiresAt: newSession.getIdToken().getExpiration() * 1000,
            };

            // Update stored tokens
            if (this.storage) {
              this.storage.set(STORAGE_KEYS.AUTH_TOKENS, tokens);
            }

            resolve(tokens);
          });
        }
      });
    });
  }

  /**
   * Check if token needs refresh (within 5 minutes of expiration)
   * @param tokens - Current tokens
   * @returns True if refresh is needed
   */
  needsRefresh(tokens: AuthTokens): boolean {
    const now = Date.now();
    const fiveMinutes = 5 * 60 * 1000;
    return tokens.expiresAt - now < fiveMinutes;
  }

  /**
   * Get current session tokens
   * @returns Current tokens or null if not authenticated
   */
  async getCurrentTokens(): Promise<AuthTokens | null> {
    if (!this.storage) {
      // Try to restore from storage
      const userId = localStorage.getItem(STORAGE_KEYS.USER_ID);
      if (userId) {
        this.storage = new SecureStorage(userId);
      } else {
        return null;
      }
    }

    const tokens = this.storage.get<AuthTokens>(STORAGE_KEYS.AUTH_TOKENS);
    if (!tokens) {
      return null;
    }

    // Check if refresh is needed
    if (this.needsRefresh(tokens)) {
      return await this.refreshSession();
    }

    return tokens;
  }

  /**
   * Sign out current user
   */
  async signOut(): Promise<void> {
    if (this.currentUser) {
      this.currentUser.signOut();
      this.currentUser = null;
    }

    // Clear stored tokens
    if (this.storage) {
      this.storage.remove(STORAGE_KEYS.AUTH_TOKENS);
      this.storage.remove(STORAGE_KEYS.USER_ID);
      this.storage = null;
    }
  }

  /**
   * Check if user is authenticated
   * @returns True if user has valid session
   */
  async isAuthenticated(): Promise<boolean> {
    const tokens = await this.getCurrentTokens();
    return tokens !== null;
  }

  /**
   * Get current user ID
   * @returns User ID or null if not authenticated
   */
  getUserId(): string | null {
    if (!this.storage) {
      const userId = localStorage.getItem(STORAGE_KEYS.USER_ID);
      if (userId) {
        this.storage = new SecureStorage(userId);
        return userId;
      }
      return null;
    }

    return this.storage.get<string>(STORAGE_KEYS.USER_ID);
  }
}
