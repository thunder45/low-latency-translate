/**
 * Session HTTP Service
 * Handles HTTP-based session management operations (create, read, update, delete)
 * Separates session lifecycle from WebSocket audio streaming
 */

import { CognitoAuthService } from './CognitoAuthService';
import { AuthTokens } from '../utils/storage';

/**
 * Session configuration for creation
 */
export interface SessionConfig {
  sourceLanguage: string;
  qualityTier: 'standard' | 'premium';
}

/**
 * Session metadata returned from API
 */
export interface SessionMetadata {
  sessionId: string;
  speakerId: string;
  sourceLanguage: string;
  qualityTier: string;
  status: 'active' | 'paused' | 'ended';
  listenerCount: number;
  createdAt: number;
  updatedAt: number;
}

/**
 * Session update request
 */
export interface SessionUpdateRequest {
  status?: 'active' | 'paused' | 'ended';
  sourceLanguage?: string;
  qualityTier?: 'standard' | 'premium';
}

/**
 * Token storage interface
 */
export interface TokenStorage {
  getTokens(): Promise<AuthTokens | null>;
  storeTokens(tokens: AuthTokens): Promise<void>;
}

/**
 * HTTP error response from API
 */
interface HttpErrorResponse {
  type: 'error';
  code: string;
  message: string;
  details?: Record<string, unknown>;
  timestamp: number;
}

/**
 * Custom HTTP error class
 */
export class HttpError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public code: string,
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'HttpError';
  }
}

/**
 * Session HTTP Service configuration
 */
export interface SessionHttpServiceConfig {
  apiBaseUrl: string;
  authService?: CognitoAuthService;
  tokenStorage?: TokenStorage;
  timeout?: number;
  maxRetries?: number;
  retryDelay?: number;
}

/**
 * Retry configuration
 */
interface RetryConfig {
  maxRetries: number;
  initialDelay: number;
  maxDelay: number;
  backoffMultiplier: number;
}

const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  initialDelay: 1000, // 1 second
  maxDelay: 4000, // 4 seconds
  backoffMultiplier: 2,
};

/**
 * Session HTTP Service
 * Provides HTTP-based CRUD operations for session management
 */
export class SessionHttpService {
  private apiBaseUrl: string;
  private authService?: CognitoAuthService;
  private tokenStorage?: TokenStorage;
  private timeout: number;
  private retryConfig: RetryConfig;

  constructor(config: SessionHttpServiceConfig) {
    this.apiBaseUrl = config.apiBaseUrl.replace(/\/$/, ''); // Remove trailing slash
    this.authService = config.authService;
    this.tokenStorage = config.tokenStorage;
    this.timeout = config.timeout || 10000; // 10 second default timeout
    this.retryConfig = {
      ...DEFAULT_RETRY_CONFIG,
      maxRetries: config.maxRetries || DEFAULT_RETRY_CONFIG.maxRetries,
      initialDelay: config.retryDelay || DEFAULT_RETRY_CONFIG.initialDelay,
    };
  }

  /**
   * Get valid JWT token, refreshing if necessary
   * @returns Valid JWT token
   * @throws HttpError if token refresh fails
   */
  private async getValidToken(): Promise<string> {
    if (!this.authService || !this.tokenStorage) {
      throw new HttpError(
        'Authentication not configured',
        401,
        'AUTH_NOT_CONFIGURED'
      );
    }

    try {
      const tokens = await this.tokenStorage.getTokens();
      if (!tokens) {
        throw new HttpError(
          'No authentication tokens available',
          401,
          'NO_TOKENS'
        );
      }

      // Check if token is expired or close to expiry (within 5 minutes)
      const timeUntilExpiry = tokens.expiresAt - Date.now();

      if (timeUntilExpiry < 5 * 60 * 1000) {
        console.log('[SessionHttpService] Token close to expiry, refreshing...');
        const newTokens = await this.authService.refreshTokens(tokens.refreshToken);
        await this.tokenStorage.storeTokens(newTokens);
        return newTokens.idToken;
      }

      return tokens.idToken;
    } catch (error) {
      console.error('[SessionHttpService] Token refresh failed:', error);
      throw new HttpError(
        'Failed to refresh authentication token',
        401,
        'TOKEN_REFRESH_FAILED'
      );
    }
  }

  /**
   * Handle HTTP errors and convert to HttpError
   * @param response - Fetch response
   * @throws HttpError with appropriate status code and message
   */
  private async handleHttpError(response: Response): Promise<never> {
    let errorBody: HttpErrorResponse | null = null;

    try {
      errorBody = await response.json();
    } catch {
      // Response body is not JSON or empty
    }

    const statusCode = response.status;
    const errorCode = errorBody?.code || `HTTP_${statusCode}`;
    const errorMessage = errorBody?.message || this.getDefaultErrorMessage(statusCode);
    const details = errorBody?.details;

    throw new HttpError(errorMessage, statusCode, errorCode, details);
  }

  /**
   * Get default error message for HTTP status code
   * @param statusCode - HTTP status code
   * @returns User-friendly error message
   */
  private getDefaultErrorMessage(statusCode: number): string {
    switch (statusCode) {
      case 400:
        return 'Invalid request. Please check your input and try again.';
      case 401:
        return 'Authentication required. Please log in again.';
      case 403:
        return 'You do not have permission to perform this action.';
      case 404:
        return 'Session not found. It may have been deleted or expired.';
      case 409:
        return 'Session already exists or conflict detected.';
      case 429:
        return 'Too many requests. Please wait a moment and try again.';
      case 500:
        return 'Server error. Please try again later.';
      case 503:
        return 'Service temporarily unavailable. Please try again later.';
      default:
        return 'An unexpected error occurred. Please try again.';
    }
  }

  /**
   * Check if error is retryable (5xx errors or network errors)
   * @param error - Error to check
   * @returns True if error is retryable
   */
  private isRetryableError(error: HttpError): boolean {
    // Retry on 5xx server errors
    if (error.statusCode >= 500 && error.statusCode < 600) {
      return true;
    }

    // Retry on network errors
    if (error.statusCode === 0 && error.code === 'NETWORK_ERROR') {
      return true;
    }

    // Retry on timeout
    if (error.statusCode === 408 || error.code === 'REQUEST_TIMEOUT') {
      return true;
    }

    // Don't retry 4xx client errors
    return false;
  }

  /**
   * Calculate retry delay with exponential backoff
   * @param attempt - Current attempt number (1-based)
   * @returns Delay in milliseconds
   */
  private calculateRetryDelay(attempt: number): number {
    const delay = this.retryConfig.initialDelay * Math.pow(this.retryConfig.backoffMultiplier, attempt - 1);
    return Math.min(delay, this.retryConfig.maxDelay);
  }

  /**
   * Sleep for specified milliseconds
   * @param ms - Milliseconds to sleep
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Make HTTP request with timeout and error handling
   * @param url - Request URL
   * @param options - Fetch options
   * @returns Response object
   * @throws HttpError on failure
   */
  private async makeRequest(url: string, options: RequestInit): Promise<Response> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        await this.handleHttpError(response);
      }

      return response;
    } catch (error) {
      clearTimeout(timeoutId);

      if (error instanceof HttpError) {
        throw error;
      }

      if (error instanceof Error && error.name === 'AbortError') {
        throw new HttpError(
          'Request timed out. Please check your connection and try again.',
          408,
          'REQUEST_TIMEOUT'
        );
      }

      // Network error or other fetch error
      throw new HttpError(
        'Network error. Please check your connection and try again.',
        0,
        'NETWORK_ERROR'
      );
    }
  }

  /**
   * Make HTTP request with retry logic for 5xx errors
   * @param url - Request URL
   * @param options - Fetch options
   * @returns Response object
   * @throws HttpError on failure after all retries
   */
  private async makeRequestWithRetry(url: string, options: RequestInit): Promise<Response> {
    let lastError: HttpError | null = null;

    for (let attempt = 1; attempt <= this.retryConfig.maxRetries; attempt++) {
      try {
        return await this.makeRequest(url, options);
      } catch (error) {
        if (!(error instanceof HttpError)) {
          throw error;
        }

        lastError = error;

        // Don't retry on 4xx errors (client errors)
        if (!this.isRetryableError(error)) {
          throw error;
        }

        // Don't wait after last attempt
        if (attempt < this.retryConfig.maxRetries) {
          const delay = this.calculateRetryDelay(attempt);
          console.log(`[SessionHttpService] Retry attempt ${attempt}/${this.retryConfig.maxRetries} after ${delay}ms`);
          await this.sleep(delay);
        }
      }
    }

    // All retries exhausted
    throw lastError || new HttpError(
      'Request failed after multiple retries',
      0,
      'MAX_RETRIES_EXCEEDED'
    );
  }

  /**
   * Create a new session
   * @param config - Session configuration
   * @returns Session metadata
   * @throws HttpError on failure
   */
  async createSession(config: SessionConfig): Promise<SessionMetadata> {
    const token = await this.getValidToken();

    const response = await this.makeRequestWithRetry(`${this.apiBaseUrl}/sessions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(config),
    });

    const data = await response.json();
    return data as SessionMetadata;
  }

  /**
   * Get session by ID
   * @param sessionId - Session ID
   * @returns Session metadata
   * @throws HttpError on failure
   */
  async getSession(sessionId: string): Promise<SessionMetadata> {
    // No authentication required for GET (public endpoint for listeners)
    const response = await this.makeRequestWithRetry(`${this.apiBaseUrl}/sessions/${sessionId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    const data = await response.json();
    return data as SessionMetadata;
  }

  /**
   * Update session
   * @param sessionId - Session ID
   * @param updates - Session updates
   * @returns Updated session metadata
   * @throws HttpError on failure
   */
  async updateSession(sessionId: string, updates: SessionUpdateRequest): Promise<SessionMetadata> {
    const token = await this.getValidToken();

    const response = await this.makeRequestWithRetry(`${this.apiBaseUrl}/sessions/${sessionId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(updates),
    });

    const data = await response.json();
    return data as SessionMetadata;
  }

  /**
   * Delete session
   * @param sessionId - Session ID
   * @throws HttpError on failure
   */
  async deleteSession(sessionId: string): Promise<void> {
    const token = await this.getValidToken();

    await this.makeRequestWithRetry(`${this.apiBaseUrl}/sessions/${sessionId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    // 204 No Content - no response body
  }
}
