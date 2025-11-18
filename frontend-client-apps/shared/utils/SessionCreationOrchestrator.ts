import { WebSocketClient } from '../websocket/WebSocketClient';
import { WebSocketMessage } from '../websocket/types';
import { CognitoAuthService } from '../services/CognitoAuthService';
import { SessionHttpService, SessionConfig, SessionMetadata, HttpError } from '../services/SessionHttpService';
import { AuthTokens } from './storage';

/**
 * Token storage interface
 */
export interface TokenStorage {
  getTokens(): Promise<AuthTokens | null>;
  storeTokens(tokens: AuthTokens): Promise<void>;
}

/**
 * Configuration for session creation
 */
export interface SessionCreationConfig {
  wsUrl: string;
  httpApiUrl: string; // HTTP API URL for session management
  jwtToken: string;
  refreshToken?: string;
  sourceLanguage: string;
  qualityTier: 'standard' | 'premium';
  timeout?: number;
  retryAttempts?: number;
  authService?: CognitoAuthService;
  tokenStorage?: TokenStorage;
}

/**
 * Result of session creation attempt
 */
export interface SessionCreationResult {
  success: boolean;
  sessionId?: string;
  wsClient?: WebSocketClient;
  error?: string;
  errorCode?: string;
}

/**
 * Session created message from server
 */
interface SessionCreatedMessage extends WebSocketMessage {
  type: 'sessionCreated';
  sessionId: string;
  sourceLanguage: string;
  qualityTier: string;
  timestamp: number;
}

/**
 * Error message from server
 */
interface ErrorMessage extends WebSocketMessage {
  type: 'error';
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

/**
 * Retry configuration
 */
interface RetryConfig {
  maxAttempts: number;
  initialDelay: number;
  maxDelay: number;
  backoffMultiplier: number;
}

const DEFAULT_TIMEOUT = 5000; // 5 seconds
const DEFAULT_RETRY_ATTEMPTS = 3;

const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxAttempts: 3,
  initialDelay: 1000, // 1 second
  maxDelay: 4000, // 4 seconds
  backoffMultiplier: 2,
};

/**
 * Error messages for different failure scenarios
 */
export const ERROR_MESSAGES = {
  CONNECTION_FAILED: 'Unable to connect to server. Please check your internet connection and try again.',
  CONNECTION_TIMEOUT: 'Connection timed out. Please try again.',
  CREATION_FAILED: 'Failed to create session. Please try again.',
  CREATION_TIMEOUT: 'Session creation timed out. Please try again.',
  INITIALIZATION_FAILED: 'Failed to initialize broadcast. Please check your microphone permissions.',
  UNKNOWN_ERROR: 'An unexpected error occurred. Please try again.',
  MAX_RETRIES_EXCEEDED: 'Failed to connect after multiple attempts. Please check your connection and try again.',
};

/**
 * Orchestrates the session creation flow:
 * 1. Create and connect WebSocket client
 * 2. Send session creation request
 * 3. Wait for response with timeout
 * 4. Handle errors and retries
 */
export class SessionCreationOrchestrator {
  private config: SessionCreationConfig;
  private wsClient: WebSocketClient | null = null;
  private retryConfig: RetryConfig;
  private aborted: boolean = false;

  constructor(config: SessionCreationConfig) {
    this.config = {
      ...config,
      timeout: config.timeout || DEFAULT_TIMEOUT,
      retryAttempts: config.retryAttempts || DEFAULT_RETRY_ATTEMPTS,
    };
    this.retryConfig = DEFAULT_RETRY_CONFIG;
  }

  /**
   * Check if token needs refresh and refresh if necessary
   */
  private async ensureValidToken(): Promise<string> {
    // If no auth service or token storage, use existing token
    if (!this.config.authService || !this.config.tokenStorage) {
      return this.config.jwtToken;
    }

    try {
      const tokens = await this.config.tokenStorage.getTokens();
      if (!tokens) {
        throw new Error('No tokens available');
      }

      // Check if token is expired or close to expiry (within 5 minutes)
      // Use stored expiresAt directly (absolute timestamp, not duration)
      const timeUntilExpiry = tokens.expiresAt - Date.now();

      if (timeUntilExpiry < 5 * 60 * 1000) {
        console.log('Token close to expiry, refreshing...');
        const newTokens = await this.config.authService.refreshTokens(tokens.refreshToken);
        await this.config.tokenStorage.storeTokens(newTokens);
        return newTokens.idToken;
      }

      return tokens.idToken;
    } catch (error) {
      console.error('Token refresh failed:', error);
      // Fall back to existing token
      return this.config.jwtToken;
    }
  }

  /**
   * Create session via HTTP API
   */
  private async createSessionViaHttp(): Promise<SessionCreationResult> {
    try {
      // Create HTTP service
      const httpService = new SessionHttpService({
        apiBaseUrl: this.config.httpApiUrl,
        authService: this.config.authService,
        tokenStorage: this.config.tokenStorage,
        timeout: this.config.timeout,
      });

      // Create session via HTTP
      const sessionConfig: SessionConfig = {
        sourceLanguage: this.config.sourceLanguage,
        qualityTier: this.config.qualityTier,
      };

      console.log('[SessionOrchestrator] Creating session via HTTP API...');
      const sessionMetadata: SessionMetadata = await httpService.createSession(sessionConfig);
      console.log('[SessionOrchestrator] Session created:', sessionMetadata.sessionId);

      // Connect WebSocket with sessionId
      const wsClient = await this.connectWebSocketWithSession(sessionMetadata.sessionId);

      return {
        success: true,
        sessionId: sessionMetadata.sessionId,
        wsClient: wsClient,
      };
    } catch (error) {
      console.error('[SessionOrchestrator] HTTP session creation failed:', error);

      if (error instanceof HttpError) {
        return {
          success: false,
          error: error.message,
          errorCode: error.code,
        };
      }

      return {
        success: false,
        error: error instanceof Error ? error.message : ERROR_MESSAGES.CREATION_FAILED,
        errorCode: 'HTTP_CREATION_FAILED',
      };
    }
  }

  /**
   * Connect WebSocket with existing sessionId (hybrid mode)
   */
  private async connectWebSocketWithSession(sessionId: string): Promise<WebSocketClient> {
    const wsClient = new WebSocketClient({
      url: this.config.wsUrl,
      token: this.config.jwtToken,
      heartbeatInterval: 30000,
      reconnect: false,
      maxReconnectAttempts: 0,
      reconnectDelay: 1000,
    });

    this.wsClient = wsClient;

    // Connect with sessionId query parameter
    const connectPromise = wsClient.connect({
      sessionId: sessionId,
    });
    const timeoutPromise = this.createTimeoutPromise(
      this.config.timeout!,
      ERROR_MESSAGES.CONNECTION_TIMEOUT
    );

    try {
      await Promise.race([connectPromise, timeoutPromise]);
      return wsClient;
    } catch (error) {
      wsClient.disconnect();
      throw error;
    }
  }

  /**
   * Create session with retry logic
   * Always uses HTTP-based session creation
   */
  async createSession(): Promise<SessionCreationResult> {
    console.log('[SessionOrchestrator] Creating session via HTTP API');
    return this.createSessionViaHttp();
  }

  /**
   * Create session via WebSocket (legacy method - deprecated)
   * Kept for reference but no longer used
   */
  private async createSessionViaWebSocket(): Promise<SessionCreationResult> {
    let lastError: string = ERROR_MESSAGES.UNKNOWN_ERROR;
    let lastErrorCode: string = 'UNKNOWN_ERROR';
    let authRetryDone = false;

    for (let attempt = 1; attempt <= this.retryConfig.maxAttempts; attempt++) {
      if (this.aborted) {
        return {
          success: false,
          error: 'Operation cancelled',
          errorCode: 'CANCELLED',
        };
      }

      try {
        // Ensure we have a valid token before connecting
        const token = await this.ensureValidToken();
        this.config.jwtToken = token;

        // Attempt to connect WebSocket
        const wsClient = await this.connectWebSocket();
        
        if (this.aborted) {
          wsClient.disconnect();
          return {
            success: false,
            error: 'Operation cancelled',
            errorCode: 'CANCELLED',
          };
        }

        // Set up auth error handler
        let authErrorReceived = false;
        wsClient.on('auth_error', () => {
          authErrorReceived = true;
        });

        // Send session creation request and wait for response
        const result = await this.sendCreationRequest(wsClient);
        
        if (result.success) {
          return result;
        }

        // If auth error and we haven't tried refreshing yet, try once more
        if (authErrorReceived && !authRetryDone && this.config.authService && this.config.tokenStorage) {
          authRetryDone = true;
          wsClient.disconnect();
          
          try {
            console.log('Auth error detected, attempting token refresh...');
            const tokens = await this.config.tokenStorage.getTokens();
            if (tokens) {
              const newTokens = await this.config.authService.refreshTokens(tokens.refreshToken);
              await this.config.tokenStorage.storeTokens(newTokens);
              this.config.jwtToken = newTokens.idToken;
              
              // Retry immediately with new token
              continue;
            }
          } catch (refreshError) {
            console.error('Token refresh failed:', refreshError);
            return {
              success: false,
              error: 'Authentication failed. Please log in again.',
              errorCode: 'AUTH_FAILED',
            };
          }
        }

        // If creation failed, clean up and prepare for retry
        lastError = result.error || ERROR_MESSAGES.CREATION_FAILED;
        lastErrorCode = result.errorCode || 'CREATION_FAILED';
        wsClient.disconnect();

        // Don't retry on certain errors
        if (result.errorCode === 'INVALID_PARAMETERS' || result.errorCode === 'UNAUTHORIZED') {
          return result;
        }

      } catch (error) {
        lastError = error instanceof Error ? error.message : ERROR_MESSAGES.CONNECTION_FAILED;
        lastErrorCode = 'CONNECTION_FAILED';
        
        // Clean up on error
        if (this.wsClient) {
          this.wsClient.disconnect();
          this.wsClient = null;
        }
      }

      // Wait before retry (except on last attempt)
      if (attempt < this.retryConfig.maxAttempts) {
        const delay = this.calculateRetryDelay(attempt);
        await this.sleep(delay);
      }
    }

    // All retries exhausted
    return {
      success: false,
      error: lastError || ERROR_MESSAGES.MAX_RETRIES_EXCEEDED,
      errorCode: lastErrorCode || 'MAX_RETRIES_EXCEEDED',
    };
  }

  /**
   * Abort the session creation process
   */
  abort(): void {
    this.aborted = true;
    this.cleanup();
  }

  /**
   * Connect WebSocket with timeout
   */
  private async connectWebSocket(): Promise<WebSocketClient> {
    const wsClient = new WebSocketClient({
      url: this.config.wsUrl,
      token: this.config.jwtToken,
      heartbeatInterval: 30000,
      reconnect: false, // We handle reconnection at orchestrator level
      maxReconnectAttempts: 0,
      reconnectDelay: 1000,
    });

    this.wsClient = wsClient;

    // Connect with timeout and required query parameters
    const connectPromise = wsClient.connect({
      action: 'createSession',
      sourceLanguage: this.config.sourceLanguage,
      qualityTier: this.config.qualityTier,
    });
    const timeoutPromise = this.createTimeoutPromise(
      this.config.timeout!,
      ERROR_MESSAGES.CONNECTION_TIMEOUT
    );

    try {
      await Promise.race([connectPromise, timeoutPromise]);
      return wsClient;
    } catch (error) {
      wsClient.disconnect();
      throw error;
    }
  }

  /**
   * Send session creation request and wait for response
   */
  private async sendCreationRequest(wsClient: WebSocketClient): Promise<SessionCreationResult> {
    return new Promise((resolve) => {
      let responseReceived = false;
      let timeoutId: NodeJS.Timeout;

      // Set up message handlers
      const handleSessionCreated = (message: WebSocketMessage) => {
        if (responseReceived) return;
        responseReceived = true;
        clearTimeout(timeoutId);

        const sessionCreated = message as SessionCreatedMessage;
        resolve({
          success: true,
          sessionId: sessionCreated.sessionId,
          wsClient: wsClient,
        });
      };

      const handleError = (message: WebSocketMessage) => {
        if (responseReceived) return;
        responseReceived = true;
        clearTimeout(timeoutId);

        const errorMsg = message as ErrorMessage;
        resolve({
          success: false,
          error: errorMsg.message || ERROR_MESSAGES.CREATION_FAILED,
          errorCode: errorMsg.code || 'CREATION_FAILED',
        });
      };

      // Register handlers
      wsClient.on('sessionCreated', handleSessionCreated);
      wsClient.on('error', handleError);

      // Set timeout
      timeoutId = setTimeout(() => {
        if (responseReceived) return;
        responseReceived = true;

        console.warn('[SessionOrchestrator] Session creation timed out after', this.config.timeout, 'ms');
        wsClient.off('sessionCreated');
        wsClient.off('error');

        resolve({
          success: false,
          error: ERROR_MESSAGES.CREATION_TIMEOUT,
          errorCode: 'CREATION_TIMEOUT',
        });
      }, this.config.timeout!);

      // Send creation request
      try {
        // Validate connection state before sending
        if (!wsClient.isConnected()) {
          console.error('[SessionOrchestrator] WebSocket not connected, cannot send message');
          throw new Error('WebSocket not connected');
        }
        
        console.log('[SessionOrchestrator] Sending createSession message:', {
          action: 'createSession',
          sourceLanguage: this.config.sourceLanguage,
          qualityTier: this.config.qualityTier,
        });
        
        wsClient.send({
          action: 'createSession',
          sourceLanguage: this.config.sourceLanguage,
          qualityTier: this.config.qualityTier,
        });
        
        console.log('[SessionOrchestrator] Message sent successfully');
      } catch (error) {
        console.error('[SessionOrchestrator] Error sending message:', error);
        if (responseReceived) return;
        responseReceived = true;
        clearTimeout(timeoutId);

        wsClient.off('sessionCreated');
        wsClient.off('error');

        resolve({
          success: false,
          error: error instanceof Error ? error.message : ERROR_MESSAGES.CREATION_FAILED,
          errorCode: 'SEND_FAILED',
        });
      }
    });
  }

  /**
   * Calculate retry delay with exponential backoff
   */
  private calculateRetryDelay(attempt: number): number {
    const delay = this.retryConfig.initialDelay * Math.pow(this.retryConfig.backoffMultiplier, attempt - 1);
    return Math.min(delay, this.retryConfig.maxDelay);
  }

  /**
   * Create a promise that rejects after timeout
   */
  private createTimeoutPromise(timeout: number, message: string): Promise<never> {
    return new Promise((_, reject) => {
      setTimeout(() => {
        reject(new Error(message));
      }, timeout);
    });
  }

  /**
   * Sleep for specified milliseconds
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Clean up resources
   */
  private cleanup(): void {
    if (this.wsClient) {
      this.wsClient.disconnect();
      this.wsClient = null;
    }
  }
}
