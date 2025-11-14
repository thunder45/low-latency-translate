import type { AudioState, SessionState } from '../types/controls';
import { WebSocketClient } from '../websocket/WebSocketClient';

/**
 * Manages control state synchronization between speaker and listeners
 * Handles state updates and notifications via WebSocket
 */
export class ControlStateManager {
  private wsClient: WebSocketClient;
  private sessionStates: Map<string, SessionState> = new Map();
  private stateChangeCallbacks: Map<string, Function[]> = new Map();
  
  constructor(wsClient: WebSocketClient) {
    this.wsClient = wsClient;
    this.setupMessageHandlers();
  }
  
  /**
   * Update speaker state
   */
  async updateSpeakerState(
    sessionId: string,
    userId: string,
    state: Partial<AudioState>
  ): Promise<void> {
    // Send state update via WebSocket
    this.wsClient.send({
      action: 'updateSpeakerState',
      sessionId,
      userId,
      state,
      timestamp: Date.now(),
    });
    
    // Update local cache
    this.updateLocalState(sessionId, 'speaker', state);
  }
  
  /**
   * Update listener state
   */
  async updateListenerState(
    sessionId: string,
    userId: string,
    state: Partial<AudioState>
  ): Promise<void> {
    // Send state update via WebSocket
    this.wsClient.send({
      action: 'updateListenerState',
      sessionId,
      userId,
      state,
      timestamp: Date.now(),
    });
    
    // Update local cache
    this.updateLocalState(sessionId, userId, state);
  }
  
  /**
   * Get session state
   */
  async getSessionState(sessionId: string): Promise<SessionState> {
    return this.sessionStates.get(sessionId) || {
      sessionId,
      speakerState: { isPaused: false, isMuted: false, volume: 75, timestamp: Date.now() },
      listenerStates: new Map(),
      activeListenerCount: 0,
    };
  }
  
  /**
   * Subscribe to speaker state changes
   */
  subscribeToSpeakerState(
    sessionId: string,
    callback: (state: AudioState) => void
  ): () => void {
    const key = `speaker_${sessionId}`;
    const callbacks = this.stateChangeCallbacks.get(key) || [];
    callbacks.push(callback);
    this.stateChangeCallbacks.set(key, callbacks);
    
    // Return unsubscribe function
    return () => {
      const cbs = this.stateChangeCallbacks.get(key) || [];
      const index = cbs.indexOf(callback);
      if (index > -1) {
        cbs.splice(index, 1);
      }
    };
  }
  
  /**
   * Subscribe to listener state changes
   */
  subscribeToListenerState(
    sessionId: string,
    userId: string,
    callback: (state: AudioState) => void
  ): () => void {
    const key = `listener_${sessionId}_${userId}`;
    const callbacks = this.stateChangeCallbacks.get(key) || [];
    callbacks.push(callback);
    this.stateChangeCallbacks.set(key, callbacks);
    
    // Return unsubscribe function
    return () => {
      const cbs = this.stateChangeCallbacks.get(key) || [];
      const index = cbs.indexOf(callback);
      if (index > -1) {
        cbs.splice(index, 1);
      }
    };
  }
  
  /**
   * Setup WebSocket message handlers
   */
  private setupMessageHandlers(): void {
    this.wsClient.on('speakerStateChange', (data: any) => {
      this.handleSpeakerStateChange(data);
    });
    
    this.wsClient.on('listenerStateChange', (data: any) => {
      this.handleListenerStateChange(data);
    });
  }
  
  /**
   * Handle speaker state change message
   */
  private handleSpeakerStateChange(data: any): void {
    const { sessionId, state } = data;
    this.updateLocalState(sessionId, 'speaker', state);
    this.notifySubscribers(`speaker_${sessionId}`, state);
  }
  
  /**
   * Handle listener state change message
   */
  private handleListenerStateChange(data: any): void {
    const { sessionId, userId, state } = data;
    this.updateLocalState(sessionId, userId, state);
    this.notifySubscribers(`listener_${sessionId}_${userId}`, state);
  }
  
  /**
   * Update local state cache
   */
  private updateLocalState(
    sessionId: string,
    userId: string,
    state: Partial<AudioState>
  ): void {
    let sessionState = this.sessionStates.get(sessionId);
    
    if (!sessionState) {
      sessionState = {
        sessionId,
        speakerState: { isPaused: false, isMuted: false, volume: 75, timestamp: Date.now() },
        listenerStates: new Map(),
        activeListenerCount: 0,
      };
      this.sessionStates.set(sessionId, sessionState);
    }
    
    if (userId === 'speaker') {
      sessionState.speakerState = {
        ...sessionState.speakerState,
        ...state,
        timestamp: Date.now(),
      };
    } else {
      const listenerState = sessionState.listenerStates.get(userId) || {
        isPaused: false,
        isMuted: false,
        volume: 75,
        timestamp: Date.now(),
      };
      sessionState.listenerStates.set(userId, {
        ...listenerState,
        ...state,
        timestamp: Date.now(),
      });
    }
  }
  
  /**
   * Notify subscribers of state change
   */
  private notifySubscribers(key: string, state: AudioState): void {
    const callbacks = this.stateChangeCallbacks.get(key) || [];
    callbacks.forEach(cb => {
      try {
        cb(state);
      } catch (error) {
        console.error('Error in state change callback:', error);
      }
    });
  }
  
  /**
   * Cleanup resources
   */
  destroy(): void {
    this.sessionStates.clear();
    this.stateChangeCallbacks.clear();
  }
}
