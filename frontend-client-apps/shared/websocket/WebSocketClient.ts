import {
  WebSocketConfig,
  WebSocketMessage,
  ConnectionState,
  MessageHandler,
  ConnectionEventHandler,
  ErrorEventHandler,
  StateChangeHandler,
} from './types';
import { WebSocketCloseCode } from '../constants/auth';

/**
 * WebSocket client with automatic reconnection and heartbeat management
 */
export class WebSocketClient {
  private ws: WebSocket | null = null;
  private config: WebSocketConfig;
  private state: ConnectionState;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private heartbeatTimeoutTimer: NodeJS.Timeout | null = null;
  private messageHandlers: Map<string, MessageHandler>;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private onConnectHandlers: ConnectionEventHandler[] = [];
  private onDisconnectHandlers: ConnectionEventHandler[] = [];
  private onErrorHandlers: ErrorEventHandler[] = [];
  private onStateChangeHandlers: StateChangeHandler[] = [];

  constructor(config: WebSocketConfig) {
    this.config = config;
    this.state = {
      status: 'disconnected',
      connectionId: null,
      lastHeartbeat: null,
      reconnectAttempts: 0,
    };
    this.messageHandlers = new Map();
  }

  /**
   * Connect to WebSocket server
   */
  async connect(queryParams: Record<string, string> = {}): Promise<void> {
    const url = this.buildUrl(queryParams);
    this.updateState({ status: 'connecting' });

    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
          console.log('[WebSocketClient] WebSocket connection opened, readyState:', this.ws?.readyState);
          this.updateState({
            status: 'connected',
            reconnectAttempts: 0,
          });
          this.startHeartbeat();
          this.onConnectHandlers.forEach((handler) => handler());
          console.log('[WebSocketClient] onopen handlers completed, resolving connect promise');
          resolve();
        };

        this.ws.onmessage = (event) => {
          console.log('[WebSocketClient] Raw message received:', event.data, 'at', Date.now());
          try {
            const message = JSON.parse(event.data);
            console.log('[WebSocketClient] Parsed message type:', message.type, 'full message:', message);
            this.handleMessage(message);
          } catch (error) {
            console.error('[WebSocketClient] Failed to parse WebSocket message:', error, 'raw data:', event.data);
          }
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.handleConnectionError(error);
          const err = new Error('WebSocket connection error');
          this.onErrorHandlers.forEach((handler) => handler(err));
          reject(err);
        };

        this.ws.onclose = (event) => {
          this.handleConnectionClose(event);
        };
      } catch (error) {
        const err = error instanceof Error ? error : new Error('Failed to create WebSocket');
        this.onErrorHandlers.forEach((handler) => handler(err));
        reject(err);
      }
    });
  }

  /**
   * Send message to server
   */
  send(message: WebSocketMessage): void {
    console.log('[WebSocketClient] send() called, readyState:', this.ws?.readyState, 'message:', message);
    
    if (this.ws?.readyState === WebSocket.OPEN) {
      const payload = JSON.stringify(message);
      console.log('[WebSocketClient] Sending payload:', payload);
      this.ws.send(payload);
      console.log('[WebSocketClient] Payload sent successfully');
    } else {
      console.error('[WebSocketClient] Cannot send - WebSocket not open. ReadyState:', this.ws?.readyState);
      throw new Error('WebSocket not connected');
    }
  }

  /**
   * Register message handler for specific message type
   */
  on(messageType: string, handler: MessageHandler): void {
    this.messageHandlers.set(messageType, handler);
  }

  /**
   * Remove message handler
   */
  off(messageType: string): void {
    this.messageHandlers.delete(messageType);
  }

  /**
   * Register connection event handler
   */
  onConnect(handler: ConnectionEventHandler): void {
    this.onConnectHandlers.push(handler);
  }

  /**
   * Register disconnection event handler
   */
  onDisconnect(handler: ConnectionEventHandler): void {
    this.onDisconnectHandlers.push(handler);
  }

  /**
   * Register error event handler
   */
  onError(handler: ErrorEventHandler): void {
    this.onErrorHandlers.push(handler);
  }

  /**
   * Register state change event handler
   */
  onStateChange(handler: StateChangeHandler): void {
    this.onStateChangeHandlers.push(handler);
  }

  /**
   * Disconnect from server
   */
  disconnect(): void {
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.updateState({ status: 'disconnected' });
  }

  /**
   * Get current connection state
   */
  getState(): ConnectionState {
    return { ...this.state };
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    const stateConnected = this.state.status === 'connected';
    const wsOpen = this.ws?.readyState === WebSocket.OPEN;
    const result = stateConnected && wsOpen;
    
    // Add detailed logging when there's a mismatch
    if (stateConnected !== wsOpen) {
      console.warn('[WebSocketClient] Connection state mismatch!', {
        stateStatus: this.state.status,
        wsReadyState: this.ws?.readyState,
        wsOpen,
        result
      });
    }
    
    return result;
  }

  /**
   * Build WebSocket URL with query parameters
   */
  private buildUrl(queryParams: Record<string, string>): string {
    const params = new URLSearchParams();
    
    // Add token if provided
    if (this.config.token) {
      params.set('token', this.config.token);
    }
    
    // Add other query params
    Object.entries(queryParams).forEach(([key, value]) => {
      params.set(key, value);
    });
    
    // Only add query string if there are params
    const queryString = params.toString();
    return queryString ? `${this.config.url}?${queryString}` : this.config.url;
  }

  /**
   * Handle incoming message
   */
  private handleMessage(message: WebSocketMessage): void {
    // Handle heartbeat acknowledgment
    if (message.type === 'heartbeatAck') {
      this.state.lastHeartbeat = Date.now();
      if (this.heartbeatTimeoutTimer) {
        clearTimeout(this.heartbeatTimeoutTimer);
        this.heartbeatTimeoutTimer = null;
      }
      return;
    }

    // Route to registered handler
    const messageType = message.type || message.action;
    if (messageType) {
      const handler = this.messageHandlers.get(messageType);
      if (handler) {
        handler(message);
      }
    }
  }

  /**
   * Start heartbeat mechanism
   */
  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      if (this.isConnected()) {
        this.send({
          action: 'heartbeat',
          timestamp: Date.now(),
        });

        // Set timeout for heartbeat acknowledgment
        this.heartbeatTimeoutTimer = setTimeout(() => {
          const timeSinceLastHeartbeat = Date.now() - (this.state.lastHeartbeat || 0);
          if (timeSinceLastHeartbeat > 5000) {
            console.warn('Heartbeat timeout, reconnecting...');
            this.handleDisconnect();
          }
        }, 5000);
      }
    }, this.config.heartbeatInterval);
  }

  /**
   * Stop heartbeat mechanism
   */
  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    if (this.heartbeatTimeoutTimer) {
      clearTimeout(this.heartbeatTimeoutTimer);
      this.heartbeatTimeoutTimer = null;
    }
  }

  /**
   * Handle connection error
   */
  private handleConnectionError(error: Event): void {
    // WebSocket errors don't provide detailed info, but we can infer from close code
    const handler = this.messageHandlers.get('connection_error');
    if (handler) {
      handler({
        type: 'connection_error',
        message: 'Failed to connect to server',
        error,
      });
    }
  }

  /**
   * Handle connection close with specific error codes
   */
  private handleConnectionClose(event: CloseEvent): void {
    console.log(`[WebSocketClient] WebSocket closed with code: ${event.code}, reason: "${event.reason}", wasClean: ${event.wasClean}`);
    
    // WebSocket close codes:
    // NORMAL_CLOSURE = Normal closure
    // ABNORMAL_CLOSURE = Abnormal closure (no close frame)
    // POLICY_VIOLATION = Policy violation (auth failure)
    // SERVER_ERROR = Server error
    
    if (event.code === WebSocketCloseCode.POLICY_VIOLATION) {
      // Authentication failure
      const handler = this.messageHandlers.get('auth_error');
      if (handler) {
        handler({
          type: 'auth_error',
          message: 'Authentication failed. Please log in again.',
          code: event.code,
          reason: event.reason,
        });
      }
    } else if (event.code === WebSocketCloseCode.ABNORMAL_CLOSURE) {
      // Connection failed (could be network or auth)
      const handler = this.messageHandlers.get('connection_failed');
      if (handler) {
        handler({
          type: 'connection_failed',
          message: 'Connection failed. Please check your network.',
          code: event.code,
        });
      }
    } else {
      // Other errors
      const handler = this.messageHandlers.get('disconnected');
      if (handler) {
        handler({
          type: 'disconnected',
          code: event.code,
          reason: event.reason,
        });
      }
    }

    // Call the standard disconnect handler
    this.handleDisconnect();

    // Attempt reconnection if not a normal closure and not an auth error
    if (event.code !== WebSocketCloseCode.NORMAL_CLOSURE && event.code !== WebSocketCloseCode.POLICY_VIOLATION && this.config.reconnect && this.state.reconnectAttempts < this.config.maxReconnectAttempts) {
      this.attemptReconnect();
    }
  }

  /**
   * Handle disconnection
   */
  private handleDisconnect(): void {
    console.log('[WebSocketClient] handleDisconnect() called');
    console.trace('[WebSocketClient] handleDisconnect stack trace');
    this.stopHeartbeat();
    this.updateState({ status: 'disconnected' });
    this.onDisconnectHandlers.forEach((handler) => handler());

    if (this.state.reconnectAttempts >= this.config.maxReconnectAttempts) {
      this.updateState({ status: 'failed' });
    }
  }

  /**
   * Attempt to reconnect with exponential backoff
   */
  private attemptReconnect(): void {
    this.updateState({
      status: 'reconnecting',
      reconnectAttempts: this.state.reconnectAttempts + 1,
    });

    const delay = Math.min(
      this.config.reconnectDelay * Math.pow(2, this.state.reconnectAttempts - 1),
      30000 // Max 30 seconds
    );

    console.log(`Reconnecting in ${delay}ms (attempt ${this.state.reconnectAttempts}/${this.config.maxReconnectAttempts})`);

    this.reconnectTimer = setTimeout(() => {
      // Reconnection will be handled by application layer
      // Emit state change to notify application
      this.onStateChangeHandlers.forEach((handler) => handler(this.state));
    }, delay);
  }

  /**
   * Update connection state and notify handlers
   */
  private updateState(updates: Partial<ConnectionState>): void {
    this.state = { ...this.state, ...updates };
    this.onStateChangeHandlers.forEach((handler) => handler(this.state));
  }
}
