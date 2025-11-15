import { WebSocketClient } from '../../../shared/websocket/WebSocketClient';
import { AudioPlayback } from '../../../shared/audio/AudioPlayback';
import { CircularAudioBuffer } from '../../../shared/audio/CircularAudioBuffer';
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
  private audioBuffer: CircularAudioBuffer;
  private config: ListenerServiceConfig;
  private playbackVolume: number = 75;
  private onAudioChunk: ((chunk: Float32Array) => void) | null = null;

  constructor(config: ListenerServiceConfig) {
    this.config = config;
    
    // Initialize circular buffer (16kHz sample rate, 30 seconds)
    this.audioBuffer = new CircularAudioBuffer(16000, 30000);

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
      // Load saved preferences
      await this.loadPreferences();
      
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
   * Load saved preferences
   */
  private async loadPreferences(): Promise<void> {
    try {
      const { PreferenceStore } = await import('../../../shared/services/PreferenceStore');
      const preferenceStore = PreferenceStore.getInstance();
      
      // Use a default user ID or get from session
      const userId = `listener-${this.config.sessionId}`;
      
      // Load saved volume
      const savedVolume = await preferenceStore.getVolume(userId);
      if (savedVolume !== null) {
        await this.setVolume(savedVolume);
      }
      
      // Load saved language (if different from config)
      const savedLanguage = await preferenceStore.getLanguage(userId);
      if (savedLanguage !== null && savedLanguage !== this.config.targetLanguage) {
        // Update config but don't switch yet (will switch after connection)
        this.config.targetLanguage = savedLanguage;
      }
    } catch (error) {
      console.warn('Failed to load preferences:', error);
      // Continue with defaults
    }
  }

  /**
   * Pause playback
   */
  async pause(): Promise<void> {
    const startTime = Date.now();
    
    try {
      this.audioPlayback.pause();
      useListenerStore.getState().setPaused(true);
      
      // Start buffering incoming audio
      this.startBuffering();
      
      this.logControlLatency('pause', startTime);
    } catch (error) {
      console.error('Failed to pause playback:', error);
      throw error;
    }
  }

  /**
   * Resume playback
   */
  async resume(): Promise<void> {
    const startTime = Date.now();
    
    try {
      // Play buffered audio first
      await this.playBufferedAudio();
      
      this.audioPlayback.resume();
      useListenerStore.getState().setPaused(false);
      
      // Stop buffering
      this.stopBuffering();
      
      this.logControlLatency('resume', startTime);
    } catch (error) {
      console.error('Failed to resume playback:', error);
      throw error;
    }
  }

  /**
   * Toggle pause/resume
   */
  async togglePause(): Promise<void> {
    const isPaused = useListenerStore.getState().isPaused;
    if (isPaused) {
      await this.resume();
    } else {
      await this.pause();
    }
  }

  /**
   * Mute audio
   */
  async mute(): Promise<void> {
    const startTime = Date.now();
    
    try {
      this.audioPlayback.setMuted(true);
      useListenerStore.getState().setMuted(true);
      
      this.logControlLatency('mute', startTime);
    } catch (error) {
      console.error('Failed to mute playback:', error);
      throw error;
    }
  }

  /**
   * Unmute audio
   */
  async unmute(): Promise<void> {
    const startTime = Date.now();
    
    try {
      this.audioPlayback.setMuted(false);
      useListenerStore.getState().setMuted(false);
      
      this.logControlLatency('unmute', startTime);
    } catch (error) {
      console.error('Failed to unmute playback:', error);
      throw error;
    }
  }

  /**
   * Toggle mute/unmute
   */
  async toggleMute(): Promise<void> {
    const isMuted = useListenerStore.getState().isMuted;
    if (isMuted) {
      await this.unmute();
    } else {
      await this.mute();
    }
  }

  /**
   * Set playback volume (0-100)
   */
  async setVolume(volume: number): Promise<void> {
    const clampedVolume = Math.max(0, Math.min(100, volume));
    this.playbackVolume = clampedVolume;
    
    const isMuted = useListenerStore.getState().isMuted;
    if (!isMuted) {
      this.audioPlayback.setVolume(clampedVolume / 100);
    }
    
    useListenerStore.getState().setPlaybackVolume(clampedVolume);
    
    // Save preference
    try {
      const { PreferenceStore } = await import('../../../shared/services/PreferenceStore');
      const preferenceStore = PreferenceStore.getInstance();
      const userId = `listener-${this.config.sessionId}`;
      await preferenceStore.saveVolume(userId, clampedVolume);
    } catch (error) {
      console.warn('Failed to save volume preference:', error);
    }
  }

  /**
   * Start buffering incoming audio
   */
  private startBuffering(): void {
    this.onAudioChunk = (chunk: Float32Array) => {
      const isNearCapacity = this.audioBuffer.write(chunk);
      
      if (isNearCapacity) {
        console.warn('Audio buffer near capacity');
        useListenerStore.getState().setBufferOverflow(true);
      }
      
      // Update buffer status
      const bufferedDuration = this.audioBuffer.getBufferedDuration();
      useListenerStore.getState().setBufferedDuration(bufferedDuration);
    };
  }

  /**
   * Stop buffering
   */
  private stopBuffering(): void {
    this.onAudioChunk = null;
    this.audioBuffer.clear();
    useListenerStore.getState().setBufferedDuration(0);
    useListenerStore.getState().setBufferOverflow(false);
  }

  /**
   * Play buffered audio
   */
  private async playBufferedAudio(): Promise<void> {
    const bufferedDuration = this.audioBuffer.getBufferedDuration();
    
    if (bufferedDuration > 0) {
      const audioData = this.audioBuffer.read(bufferedDuration);
      await this.audioPlayback.playBuffer(audioData);
    }
  }

  /**
   * Switch target language
   */
  async switchLanguage(newLanguage: string): Promise<void> {
    const previousLanguage = useListenerStore.getState().targetLanguage;
    const startTime = Date.now();
    
    try {
      // Update UI to show switching state
      useListenerStore.getState().setTargetLanguage(newLanguage);

      // Clear audio buffer
      this.audioPlayback.clearBuffer();

      // Send switch language request
      if (this.wsClient.isConnected()) {
        this.wsClient.send({
          action: 'changeLanguage',
          targetLanguage: newLanguage,
          timestamp: Date.now(),
        });
      }
      
      // Save preference
      try {
        const { PreferenceStore } = await import('../../../shared/services/PreferenceStore');
        const preferenceStore = PreferenceStore.getInstance();
        const userId = `listener-${this.config.sessionId}`;
        await preferenceStore.saveLanguage(userId, newLanguage);
      } catch (error) {
        console.warn('Failed to save language preference:', error);
      }
      
      this.logControlLatency('switchLanguage', startTime);
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
   * Log control operation latency
   */
  private logControlLatency(operation: string, startTime: number): void {
    const latency = Date.now() - startTime;
    console.log(`Control latency [${operation}]: ${latency}ms`);
    
    // Warn if latency exceeds target
    const target = operation === 'pause' || operation === 'resume' ? 100 : 50;
    if (latency > target) {
      console.warn(`Control latency exceeded target: ${latency}ms for ${operation}`);
    }
    
    // Send to monitoring service if available
    if (typeof window !== 'undefined' && (window as any).monitoring) {
      (window as any).monitoring.logMetric({
        name: `control.${operation}.latency`,
        value: latency,
        unit: 'ms',
        timestamp: Date.now(),
      });
    }
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
    this.wsClient.on('broadcastPaused', () => {
      useListenerStore.getState().setSpeakerPaused(true);
    });

    this.wsClient.on('broadcastResumed', () => {
      setTimeout(() => {
        useListenerStore.getState().setSpeakerPaused(false);
      }, 500);
    });

    this.wsClient.on('broadcastMuted', () => {
      useListenerStore.getState().setSpeakerMuted(true);
    });

    this.wsClient.on('broadcastUnmuted', () => {
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
