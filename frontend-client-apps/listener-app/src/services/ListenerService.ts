import { WebSocketClient } from '../../../shared/websocket/WebSocketClient';
import { AudioPlayback } from '../../../shared/audio/AudioPlayback';
import { useListenerStore } from '../../../shared/store/listenerStore';
import { ErrorHandler, ErrorType } from '../../../shared/utils/ErrorHandler';

/**
 * Configuration for ListenerService
 */
export interface ListenerServiceConfig {
  wsUrl: string;
  sessionId: string;
  targetLanguage: string;
}

/**
 * Listener service orchestrates WebSocket and audio playback
 * Handles session joining, audio reception, and playback control
 */
export class ListenerService {
  private wsClient: WebSocketClient;
  private audioPlayback: AudioPlayback;
  private config: ListenerServiceConfig;

  constructor(config: ListenerServiceConfig) {
    this.config = config;

    // Initialize WebSocket client
    this.wsClient = new WebSocketClient({
      url: config.wsUrl,
      heartbeatInterval: 30000,
      reconnect: true,
      reconnectDelay: 1000,
      maxReconnectAttempts: 5,
    });

    // Initialize audio playback
    this.audioPlayback = new AudioPlayback({
      sampleRate: 16000,
      maxBufferDuration: 30,
    });

    this.setupEventHandlers();
  }

  /**
   * Initialize session and join
   */
  async initialize(): Promise<void> {
    try {
      // Connect WebSocket
      await this.wsClient.connect({
        sessionId: this.config.sessionId,
        targetLanguage: this.config.targetLanguage,
      });

      useListenerStore.getState().setConnected(true);

      // Send join session request
      this.wsClient.send({
        action: 'joinSession',
        sessionId: this.config.sessionId,
        targetLanguage: this.config.targetLanguage,
      });
    } catch (error) {
      const appError = ErrorHandler.handle(error as Error, ErrorType.WEBSOCKET_ERROR);
      throw new Error(appError.userMessage);
    }
  }

  /**
   * Pause playback
   */
  pause(): void {
    this.audioPlayback.pause();
    useListenerStore.getState().setPaused(true);
  }

  /**
   * Resume playback
   */
  resume(): void {
    this.audioPlayback.resume();
    useListenerStore.getState().setPaused(false);
  }

  /**
   * Mute audio
   */
  mute(): void {
    this.audioPlayback.setMuted(true);
    useListenerStore.getState().setMuted(true);
  }

  /**
   * Unmute audio
   */
  unmute(): void {
    this.audioPlayback.setMuted(false);
    useListenerStore.getState().setMuted(false);
  }

  /**
   * Set playback volume
   */
  setVolume(volume: number): void {
    this.audioPlayback.setVolume(volume / 100);
    useListenerStore.getState().setPlaybackVolume(volume);
  }

  /**
   * Switch target language
   */
  async switchLanguage(newLanguage: string): Promise<void> {
    const previousLanguage = useListenerStore.getState().targetLanguage;
    
    try {
      // Update UI to show switching state
      useListenerStore.getState().setTargetLanguage(newLanguage);

      // Clear audio buffer
      this.audioPlayback.clearBuffer();

      // Send switch language request
      if (this.wsClient.isConnected()) {
        this.wsClient.send({
          action: 'switchLanguage',
          targetLanguage: newLanguage,
        });
      }
    } catch (error) {
      // Revert to previous language on failure
      useListenerStore.getState().setTargetLanguage(previousLanguage);
      
      const appError = ErrorHandler.handle(error as Error, ErrorType.NETWORK_ERROR);
      throw new Error(appError.userMessage);
    }
  }

  /**
   * Leave session
   */
  leave(): void {
    // Stop audio playback
    this.audioPlayback.stop();

    // Close WebSocket
    this.wsClient.disconnect();

    // Clear session state
    useListenerStore.getState().reset();
  }

  /**
   * Get buffered audio duration
   */
  getBufferedDuration(): number {
    return this.audioPlayback.getBufferDuration();
  }

  /**
   * Cleanup resources
   */
  cleanup(): void {
    this.audioPlayback.stop();
    this.wsClient.disconnect();
  }

  /**
   * Setup WebSocket event handlers
   */
  private setupEventHandlers(): void {
    // Handle session joined
    this.wsClient.on('sessionJoined', (message: any) => {
      useListenerStore.getState().setSession(
        message.sessionId,
        message.sourceLanguage,
        message.targetLanguage
      );
    });

    // Handle audio messages
    this.wsClient.on('audio', (message: any) => {
      const state = useListenerStore.getState();
      
      // Decode and queue audio
      this.audioPlayback.queueAudio({
        data: message.audioData,
        timestamp: message.timestamp,
        chunkId: message.chunkId,
        duration: message.duration || 2,
      });

      // Update buffer status
      const bufferedDuration = this.audioPlayback.getBufferDuration();
      useListenerStore.getState().setBufferedDuration(bufferedDuration);

      // Check for buffer overflow
      if (bufferedDuration >= 30) {
        useListenerStore.getState().setBufferOverflow(true);
      } else {
        useListenerStore.getState().setBufferOverflow(false);
      }

      // Check for buffering state
      if (bufferedDuration === 0 && !this.audioPlayback.isPlaying()) {
        useListenerStore.getState().setBuffering(true);
      } else {
        useListenerStore.getState().setBuffering(false);
      }
    });

    // Handle speaker state changes
    this.wsClient.on('speakerPaused', () => {
      useListenerStore.getState().setSpeakerPaused(true);
    });

    this.wsClient.on('speakerResumed', () => {
      setTimeout(() => {
        useListenerStore.getState().setSpeakerPaused(false);
      }, 500);
    });

    this.wsClient.on('speakerMuted', () => {
      useListenerStore.getState().setSpeakerMuted(true);
    });

    this.wsClient.on('speakerUnmuted', () => {
      setTimeout(() => {
        useListenerStore.getState().setSpeakerMuted(false);
      }, 500);
    });

    // Handle session ended
    this.wsClient.on('sessionEnded', (message: any) => {
      // Stop playback
      this.audioPlayback.stop();
      
      // Update UI to show session ended
      useListenerStore.getState().setConnected(false);
      
      // UI will display "Session ended by speaker" message
    });

    // Handle connection state changes
    this.wsClient.onStateChange((state) => {
      useListenerStore.getState().setConnected(state.status === 'connected');
    });

    // Handle disconnection
    this.wsClient.onDisconnect(() => {
      useListenerStore.getState().setConnected(false);
    });

    // Handle errors
    this.wsClient.onError((error) => {
      console.error('WebSocket error:', error);
      const appError = ErrorHandler.handle(error, ErrorType.WEBSOCKET_ERROR);
      // Error will be displayed by UI components
    });
  }
}
