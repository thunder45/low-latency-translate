/**
 * WebSocket configuration interface
 */
export interface WebSocketConfig {
  url: string;
  token?: string; // For speaker authentication
  reconnect: boolean;
  maxReconnectAttempts: number;
  reconnectDelay: number; // Initial delay in ms
  heartbeatInterval: number; // Default 30000ms
}

/**
 * WebSocket message interface
 */
export interface WebSocketMessage {
  type?: string;
  action?: string;
  [key: string]: any;
}

/**
 * Connection state interface
 */
export interface ConnectionState {
  status: 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'failed';
  connectionId: string | null;
  lastHeartbeat: number | null;
  reconnectAttempts: number;
}

/**
 * Message handler type
 */
export type MessageHandler = (message: WebSocketMessage) => void;

/**
 * Event handler types
 */
export type ConnectionEventHandler = () => void;
export type ErrorEventHandler = (error: Error) => void;
export type StateChangeHandler = (state: ConnectionState) => void;
