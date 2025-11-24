import { WebSocketClient } from '../websocket/WebSocketClient';
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
  sessionMetadata?: SessionMetadata; // Full session metadata including KVS fields
  wsClient?: WebSocketClient;
  error?: string;
  errorCode?: string;
}



const DEFAULT_TIMEOUT = 5000; // 5 seconds
const DEFAULT_RETRY_ATTEMPTS = 3;

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

  constructor(config: SessionCreationConfig) {
    this.config = {
      ...config,
      timeout: config.timeout || DEFAULT_TIMEOUT,
      retryAttempts: config.retryAttempts || DEFAULT_RETRY_ATTEMPTS,
    };
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
        sessionMetadata: sessionMetadata, // Return full metadata including KVS fields
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
   * Abort the session creation process
   */
  abort(): void {
    this.cleanup();
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
   * Clean up resources
   */
  private cleanup(): void {
    if (this.wsClient) {
      this.wsClient.disconnect();
      this.wsClient = null;
    }
  }
}
