import { WebSocketClient } from '../../../shared/websocket/WebSocketClient';
import { AudioCapture } from '../../../shared/audio/AudioCapture';
import { useSpeakerStore, QualityWarning } from '../../../shared/store/speakerStore';
import { ErrorHandler, ErrorType } from '../../../shared/utils/ErrorHandler';
import { RetryHandler } from '../../../shared/utils/RetryHandler';
import { controlsMonitoring } from '../../../shared/utils/ControlsMonitoring';

/**
 * Configuration for SpeakerService
 */
export interface SpeakerServiceConfig {
  wsUrl: string;
  jwtToken: string;
  sourceLanguage: string;
  qualityTier: 'standard' | 'premium';
}

/**
 * Speaker service orchestrates WebSocket and audio capture
 * Handles session lifecycle, audio transmission, and quality monitoring
 */
export class SpeakerService {
  private wsClient: WebSocketClient;
  private audioCapture: AudioCapture;
  private config: SpeakerServiceConfig;
  private statusPollInterval: NodeJS.Timeout | null = null;
  private retryHandler: RetryHandler;
  private inputVolume: number = 75;

  constructor(config: SpeakerServiceConfig) {
    this.config = config;

    // Initialize WebSocket client
    this.wsClient = new WebSocketClient({
      url: config.wsUrl,
      token: config.jwtToken,
      heartbeatInterval: 30000,
      reconnect: true,
      reconnectDelay: 1000,
      maxReconnectAttempts: 5,
    });

    // Initialize audio capture
    this.audioCapture = new AudioCapture({
      sampleRate: 16000,
      channelCount: 1,
      chunkDuration: 2, // 2 seconds
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    });

    // Initialize retry handler
    this.retryHandler = new RetryHandler({
      maxAttempts: 3,
      initialDelay: 1000,
      maxDelay: 4000,
      backoffMultiplier: 2,
    });

    this.setupEventHandlers();
  }

  /**
   * Initialize session and start broadcasting
   */
  async initialize(): Promise<void> {
    try {
      // Load saved preferences
      await this.loadPreferences();
      
      // Connect WebSocket
      await this.wsClient.connect({
        sourceLanguage: this.config.sourceLanguage,
        qualityTier: this.config.qualityTier,
      });

      useSpeakerStore.getState().setConnected(true);

      // Send session creation request
      this.wsClient.send({
        action: 'createSession',
        sourceLanguage: this.config.sourceLanguage,
        qualityTier: this.config.qualityTier,
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
    const startTime = Date.now();
    
    try {
      const { PreferenceStore } = await import('../../../shared/services/PreferenceStore');
      const preferenceStore = PreferenceStore.getInstance();
      
      // Use a default user ID or get from auth
      const userId = 'speaker-user'; // TODO: Get from auth service
      
      // Load saved volume
      const savedVolume = await preferenceStore.getVolume(userId);
      if (savedVolume !== null) {
        await this.setVolume(savedVolume);
      }
      
      const duration = Date.now() - startTime;
      controlsMonitoring.logPreferenceOperation('load', 'volume', true, duration, {
        userType: 'speaker',
        userId,
      });
    } catch (error) {
      console.warn('Failed to load preferences:', error);
      const duration = Date.now() - startTime;
      controlsMonitoring.logPreferenceOperation('load', 'volume', false, duration, {
        userType: 'speaker',
        error: (error as Error).message,
      });
      // Continue with defaults
    }
  }

  /**
   * Start audio capture and transmission
   */
  async startBroadcast(): Promise<void> {
    try {
      await this.audioCapture.start();

      // Register audio chunk handler
      this.audioCapture.onChunk((chunk) => {
        const state = useSpeakerStore.getState();
        
        // Only send if not paused or muted
        if (!state.isPaused && !state.isMuted && this.wsClient.isConnected()) {
          this.wsClient.send({
            action: 'sendAudio',
            audioData: chunk.data,
            timestamp: chunk.timestamp,
            chunkId: chunk.chunkId,
            duration: chunk.duration,
          });
          
          useSpeakerStore.getState().setTransmitting(true);
        }
      });

      // Start session status polling
      this.startStatusPolling();
    } catch (error) {
      const appError = ErrorHandler.handle(error as Error, ErrorType.AUDIO_ERROR);
      throw new Error(appError.userMessage);
    }
  }

  /**
   * Pause broadcast
   */
  async pause(): Promise<void> {
    const startTime = Date.now();
    
    try {
      this.audioCapture.pause();
      useSpeakerStore.getState().setPaused(true);
      useSpeakerStore.getState().setTransmitting(false);
      
      if (this.wsClient.isConnected()) {
        this.wsClient.send({
          action: 'pauseBroadcast',
          timestamp: Date.now(),
        });
      }
      
      this.logControlLatency('pause', startTime);
      controlsMonitoring.logControlAction('pause', true, {
        userType: 'speaker',
        sessionId: useSpeakerStore.getState().sessionId,
      });
    } catch (error) {
      console.error('Failed to pause broadcast:', error);
      controlsMonitoring.logControlAction('pause', false, {
        userType: 'speaker',
        error: (error as Error).message,
      });
      throw error;
    }
  }

  /**
   * Resume broadcast
   */
  async resume(): Promise<void> {
    const startTime = Date.now();
    
    try {
      this.audioCapture.resume();
      useSpeakerStore.getState().setPaused(false);
      
      if (this.wsClient.isConnected()) {
        this.wsClient.send({
          action: 'resumeBroadcast',
          timestamp: Date.now(),
        });
      }
      
      this.logControlLatency('resume', startTime);
      controlsMonitoring.logControlAction('resume', true, {
        userType: 'speaker',
        sessionId: useSpeakerStore.getState().sessionId,
      });
    } catch (error) {
      console.error('Failed to resume broadcast:', error);
      controlsMonitoring.logControlAction('resume', false, {
        userType: 'speaker',
        error: (error as Error).message,
      });
      throw error;
    }
  }

  /**
   * Toggle pause/resume
   */
  async togglePause(): Promise<void> {
    const isPaused = useSpeakerStore.getState().isPaused;
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
      this.audioCapture.mute();
      useSpeakerStore.getState().setMuted(true);
      useSpeakerStore.getState().setTransmitting(false);
      
      if (this.wsClient.isConnected()) {
        this.wsClient.send({
          action: 'muteBroadcast',
          timestamp: Date.now(),
        });
      }
      
      this.logControlLatency('mute', startTime);
      controlsMonitoring.logControlAction('mute', true, {
        userType: 'speaker',
        sessionId: useSpeakerStore.getState().sessionId,
      });
    } catch (error) {
      console.error('Failed to mute broadcast:', error);
      controlsMonitoring.logControlAction('mute', false, {
        userType: 'speaker',
        error: (error as Error).message,
      });
      throw error;
    }
  }

  /**
   * Unmute audio
   */
  async unmute(): Promise<void> {
    const startTime = Date.now();
    
    try {
      this.audioCapture.unmute();
      useSpeakerStore.getState().setMuted(false);
      
      if (this.wsClient.isConnected()) {
        this.wsClient.send({
          action: 'unmuteBroadcast',
          timestamp: Date.now(),
        });
      }
      
      this.logControlLatency('unmute', startTime);
      controlsMonitoring.logControlAction('unmute', true, {
        userType: 'speaker',
        sessionId: useSpeakerStore.getState().sessionId,
      });
    } catch (error) {
      console.error('Failed to unmute broadcast:', error);
      controlsMonitoring.logControlAction('unmute', false, {
        userType: 'speaker',
        error: (error as Error).message,
      });
      throw error;
    }
  }

  /**
   * Toggle mute/unmute
   */
  async toggleMute(): Promise<void> {
    const isMuted = useSpeakerStore.getState().isMuted;
    if (isMuted) {
      await this.unmute();
    } else {
      await this.mute();
    }
  }

  /**
   * Set input volume (0-100)
   */
  async setVolume(volume: number): Promise<void> {
    const clampedVolume = Math.max(0, Math.min(100, volume));
    this.inputVolume = clampedVolume;
    
    // Update audio capture volume (normalize to 0-1)
    this.audioCapture.setVolume(clampedVolume / 100);
    
    // Update store
    useSpeakerStore.getState().setInputVolume(clampedVolume);
    
    // Save preference
    const startTime = Date.now();
    try {
      const { PreferenceStore } = await import('../../../shared/services/PreferenceStore');
      const preferenceStore = PreferenceStore.getInstance();
      const userId = 'speaker-user'; // TODO: Get from auth service
      await preferenceStore.saveVolume(userId, clampedVolume);
      
      const duration = Date.now() - startTime;
      controlsMonitoring.logPreferenceOperation('save', 'volume', true, duration, {
        userType: 'speaker',
        userId,
        volume: clampedVolume,
      });
    } catch (error) {
      console.warn('Failed to save volume preference:', error);
      const duration = Date.now() - startTime;
      controlsMonitoring.logPreferenceOperation('save', 'volume', false, duration, {
        userType: 'speaker',
        error: (error as Error).message,
      });
    }
  }

  /**
   * End session
   */
  async endSession(): Promise<void> {
    try {
      await this.retryHandler.execute(async () => {
        if (this.wsClient.isConnected()) {
          this.wsClient.send({
            action: 'endSession',
            sessionId: useSpeakerStore.getState().sessionId,
            reason: 'Speaker ended session',
          });
        }
      });

      // Stop audio capture
      this.audioCapture.stop();

      // Stop status polling
      this.stopStatusPolling();

      // Close WebSocket within 1 second
      setTimeout(() => {
        this.wsClient.disconnect();
      }, 1000);

      // Clear session state
      useSpeakerStore.getState().reset();
    } catch (error) {
      const appError = ErrorHandler.handle(error as Error, ErrorType.NETWORK_ERROR);
      throw new Error(appError.userMessage);
    }
  }

  /**
   * Get current audio input level
   */
  getInputLevel(): number {
    return this.audioCapture.getInputLevel();
  }

  /**
   * Get average audio input level
   */
  getAverageInputLevel(): number {
    return this.audioCapture.getAverageInputLevel();
  }

  /**
   * Cleanup resources
   */
  cleanup(): void {
    this.stopStatusPolling();
    this.audioCapture.stop();
    this.wsClient.disconnect();
  }

  /**
   * Setup WebSocket event handlers
   */
  private setupEventHandlers(): void {
    // Handle session created
    this.wsClient.on('sessionCreated', (message: any) => {
      useSpeakerStore.getState().setSession(
        message.sessionId,
        message.sourceLanguage,
        message.qualityTier
      );
    });

    // Handle quality warnings
    this.wsClient.on('audioQualityWarning', (message: any) => {
      const warning: QualityWarning = {
        type: message.issue,
        message: this.getQualityWarningMessage(message.issue, message.value),
        timestamp: Date.now(),
      };
      
      useSpeakerStore.getState().addQualityWarning(warning);

      // Auto-clear warning after 2 seconds if quality returns to normal
      setTimeout(() => {
        const warnings = useSpeakerStore.getState().qualityWarnings;
        const updatedWarnings = warnings.filter(w => w.timestamp !== warning.timestamp);
        if (updatedWarnings.length < warnings.length) {
          useSpeakerStore.getState().clearQualityWarnings();
        }
      }, 2000);
    });

    // Handle session status
    this.wsClient.on('sessionStatus', (message: any) => {
      useSpeakerStore.getState().updateListenerStats(
        message.listenerCount,
        message.languageDistribution
      );
    });

    // Handle connection state changes
    this.wsClient.onStateChange((state) => {
      useSpeakerStore.getState().setConnected(state.status === 'connected');
    });

    // Handle disconnection
    this.wsClient.onDisconnect(() => {
      useSpeakerStore.getState().setConnected(false);
      useSpeakerStore.getState().setTransmitting(false);
    });

    // Handle errors
    this.wsClient.onError((error) => {
      console.error('WebSocket error:', error);
      const appError = ErrorHandler.handle(error, ErrorType.WEBSOCKET_ERROR);
      // Error will be displayed by UI components
    });
  }

  /**
   * Start polling session status every 5 seconds
   */
  private startStatusPolling(): void {
    this.statusPollInterval = setInterval(() => {
      if (this.wsClient.isConnected()) {
        this.wsClient.send({
          action: 'getSessionStatus',
        });
      }
    }, 5000);
  }

  /**
   * Stop polling session status
   */
  private stopStatusPolling(): void {
    if (this.statusPollInterval) {
      clearInterval(this.statusPollInterval);
      this.statusPollInterval = null;
    }
  }

  /**
   * Get user-friendly quality warning message
   */
  private getQualityWarningMessage(issue: string, value?: number): string {
    switch (issue) {
      case 'snr_low':
        return `Background noise detected. Move to quieter location${value ? ` (SNR: ${value.toFixed(1)} dB)` : ''}`;
      case 'clipping':
        return 'Audio distortion detected. Reduce microphone volume';
      case 'echo':
        return 'Echo detected. Enable echo cancellation or use headphones';
      case 'silence':
        return 'No audio detected. Check if microphone is muted';
      default:
        return 'Audio quality issue detected';
    }
  }

  /**
   * Log control operation latency
   */
  private logControlLatency(operation: string, startTime: number): void {
    controlsMonitoring.logControlLatency(operation, startTime, {
      userType: 'speaker',
      sessionId: useSpeakerStore.getState().sessionId,
    });
  }
}
