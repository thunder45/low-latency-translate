import {
  WebSocketConfig,
  WebSocketMessage,
  ConnectionState,
  MessageHandler,
  ConnectionEventHandler,
  ErrorEventHandler,
  StateChangeHandler,
} from './types';

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
          this.updateState({
            status: 'connected',
            reconnectAttempts: 0,
          });
          this.startHeartbeat();
          this.onConnectHandlers.forEach((handler) => handler());
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          const err = new Error('WebSocket connection error');
          this.onErrorHandlers.forEach((handler) => handler(err));
          reject(err);
        };

        this.ws.onclose = () => {
          this.handleDisconnect();
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
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
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
    return this.state.status === 'connected' && this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Build WebSocket URL with query parameters
   */
  private buildUrl(queryParams: Record<string, string>): string {
    const params = new URLSearchParams(queryParams);
    if (this.config.token) {
      params.set('token', this.config.token);
    }
    return `${this.config.url}?${params.toString()}`;
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
   * Handle disconnection
   */
  private handleDisconnect(): void {
    this.stopHeartbeat();
    this.updateState({ status: 'disconnected' });
    this.onDisconnectHandlers.forEach((handler) => handler());

    if (this.config.reconnect && this.state.reconnectAttempts < this.config.maxReconnectAttempts) {
      this.attemptReconnect();
    } else if (this.state.reconnectAttempts >= this.config.maxReconnectAttempts) {
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
