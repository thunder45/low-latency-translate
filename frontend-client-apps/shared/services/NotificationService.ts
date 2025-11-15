import type { Notification, AudioState } from '../types/controls';
import { WebSocketClient } from '../websocket/WebSocketClient';

/**
 * Notification service for control-related events
 * Thin wrapper around WebSocket message routing
 */
export class NotificationService {
  private wsClient: WebSocketClient;
  private subscriptions: Map<string, Function[]> = new Map();
  
  constructor(wsClient: WebSocketClient) {
    this.wsClient = wsClient;
    this.setupHandlers();
  }
  
  /**
   * Notify speaker state change
   */
  async notifySpeakerStateChange(sessionId: string, state: AudioState): Promise<void> {
    this.wsClient.send({
      action: 'notifySpeakerState',
      sessionId,
      state,
      timestamp: Date.now(),
    });
  }
  
  /**
   * Notify listener state change
   */
  async notifyListenerStateChange(
    sessionId: string,
    userId: string,
    state: AudioState
  ): Promise<void> {
    this.wsClient.send({
      action: 'notifyListenerState',
      sessionId,
      userId,
      state,
      timestamp: Date.now(),
    });
  }
  
  /**
   * Subscribe to session notifications
   */
  subscribeToSession(
    sessionId: string,
    callback: (notification: Notification) => void
  ): () => void {
    const callbacks = this.subscriptions.get(sessionId) || [];
    callbacks.push(callback);
    this.subscriptions.set(sessionId, callbacks);
    
    return () => {
      const cbs = this.subscriptions.get(sessionId) || [];
      const index = cbs.indexOf(callback);
      if (index > -1) {
        cbs.splice(index, 1);
      }
    };
  }
  
  /**
   * Setup WebSocket handlers
   */
  private setupHandlers(): void {
    this.wsClient.on('notification', (data: any) => {
      const notification: Notification = {
        type: data.type,
        sessionId: data.sessionId,
        userId: data.userId,
        data: data.data,
        timestamp: Date.now(),
      };
      
      this.notifySubscribers(data.sessionId, notification);
    });
    
    // Handle specific notification types
    this.wsClient.on('broadcastPaused', (data: any) => {
      this.notifySubscribers(data.sessionId, {
        type: 'broadcastPaused',
        sessionId: data.sessionId,
        userId: 'speaker',
        data: {},
        timestamp: Date.now(),
      });
    });
    
    this.wsClient.on('broadcastResumed', (data: any) => {
      this.notifySubscribers(data.sessionId, {
        type: 'broadcastResumed',
        sessionId: data.sessionId,
        userId: 'speaker',
        data: {},
        timestamp: Date.now(),
      });
    });
    
    this.wsClient.on('broadcastMuted', (data: any) => {
      this.notifySubscribers(data.sessionId, {
        type: 'broadcastMuted',
        sessionId: data.sessionId,
        userId: 'speaker',
        data: {},
        timestamp: Date.now(),
      });
    });
    
    this.wsClient.on('broadcastUnmuted', (data: any) => {
      this.notifySubscribers(data.sessionId, {
        type: 'broadcastUnmuted',
        sessionId: data.sessionId,
        userId: 'speaker',
        data: {},
        timestamp: Date.now(),
      });
    });
  }
  
  /**
   * Notify subscribers
   */
  private notifySubscribers(sessionId: string, notification: Notification): void {
    const callbacks = this.subscriptions.get(sessionId) || [];
    callbacks.forEach(cb => {
      try {
        cb(notification);
      } catch (error) {
        console.error('Error in notification callback:', error);
      }
    });
  }
  
  /**
   * Cleanup resources
   */
  destroy(): void {
    this.subscriptions.clear();
  }
}
