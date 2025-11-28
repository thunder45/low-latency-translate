import { AudioWorkletService } from './AudioWorkletService';
import { useSpeakerStore, QualityWarning } from '../../../shared/store/speakerStore';
import { ErrorHandler } from '../../../shared/utils/ErrorHandler';
import { RetryHandler } from '../../../shared/utils/RetryHandler';
import { controlsMonitoring } from '../../../shared/utils/ControlsMonitoring';
import { WebSocketClient } from '../../../shared/websocket/WebSocketClient';

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
 * Speaker service orchestrates AudioWorklet PCM streaming and WebSocket control
 * 
 * Architecture:
 * - AudioWorklet: Low-latency raw PCM capture (~3ms latency)
 * - WebSocket: Audio streaming and control messages
 */
export class SpeakerService {
  private wsClient: WebSocketClient;
  private audioWorkletService: AudioWorkletService | null = null;
  private statusPollInterval: NodeJS.Timeout | null = null;
  private retryHandler: RetryHandler;

  constructor(_config: SpeakerServiceConfig, wsClient: WebSocketClient) {
    this.wsClient = wsClient;

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
   * Initialize session and prepare for broadcasting
   */
  async initialize(): Promise<void> {
    try {
      console.debug('[SpeakerService] Initializing WebSocket service...');
      
      // Load saved preferences
      await this.loadPreferences();
      
      useSpeakerStore.getState().setConnected(true);
      console.log('[SpeakerService] Initialization complete, ready to broadcast');
    } catch (error) {
      console.error('[SpeakerService] Initialization failed:', error);
      const appError = ErrorHandler.handle(error as Error, {
        component: 'SpeakerService',
        operation: 'initialize',
      });
      throw new Error(appError.userMessage);
    }
  }

  /**
   * Load saved preferences
   */
  private async loadPreferences(): Promise<void> {
    const startTime = Date.now();
    
    try {
      const { preferenceStore } = await import('../../../shared/services/PreferenceStore');
      
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
   * Start audio broadcasting via AudioWorklet
   */
  async startBroadcast(): Promise<void> {
    try {
      console.log('[SpeakerService] Starting audio streaming with AudioWorklet...');
      
      // Get session ID from store
      const sessionId = useSpeakerStore.getState().sessionId;
      if (!sessionId) {
        throw new Error('Session ID not set. Cannot start broadcast.');
      }
      
      console.log(`[SpeakerService] Session ID: ${sessionId}`);
      
      // Create AudioWorkletService
      this.audioWorkletService = new AudioWorkletService({
        sampleRate: 16000,  // AWS Transcribe optimal
        bufferSize: 4096,   // ~256ms at 16kHz
        onAudioData: (pcmData: ArrayBuffer, timestamp: number) => {
          // Send PCM data via WebSocket
          this.sendPCMChunk(pcmData, timestamp, sessionId);
        },
        onError: (error: Error) => {
          console.error('[SpeakerService] AudioWorklet error:', error);
          ErrorHandler.handle(error, {
            component: 'SpeakerService',
            operation: 'audioWorklet',
          });
        },
        onStateChange: (state) => {
          if (state === 'capturing') {
            useSpeakerStore.getState().setTransmitting(true);
          } else if (state === 'idle') {
            useSpeakerStore.getState().setTransmitting(false);
          }
        },
      });
      
      // Initialize AudioWorklet
      await this.audioWorkletService.initialize();
      
      // Start capturing
      await this.audioWorkletService.startCapture();
      
      // Start session status polling
      this.startStatusPolling();
      
      useSpeakerStore.getState().setConnected(true);
      useSpeakerStore.getState().setTransmitting(true);
      
      console.log('[SpeakerService] Audio streaming started with AudioWorklet');
      
    } catch (error) {
      console.error('[SpeakerService] Failed to start broadcast:', error);
      const appError = ErrorHandler.handle(error as Error, {
        component: 'SpeakerService',
        operation: 'startBroadcast',
      });
      throw new Error(appError.userMessage);
    }
  }
  
  /**
   * Send PCM chunk via WebSocket
   */
  private sendPCMChunk(pcmData: ArrayBuffer, timestamp: number, sessionId: string): void {
    try {
      // Convert ArrayBuffer to base64 for WebSocket transport
      const uint8Array = new Uint8Array(pcmData);
      const base64 = btoa(String.fromCharCode(...uint8Array));
      
      // Send via WebSocket
      this.wsClient.send({
        action: 'audioChunk',
        sessionId,
        audioData: base64,
        timestamp,
        format: 'pcm',  // Changed from 'webm-opus'
        sampleRate: 16000,
        channels: 1,
        encoding: 's16le',
      });
      
    } catch (error) {
      console.error('[SpeakerService] Failed to send PCM chunk:', error);
    }
  }

  /**
   * Pause broadcast
   */
  async pause(): Promise<void> {
    const startTime = Date.now();
    
    try {
      // Pause audio capture
      if (this.audioWorkletService) {
        this.audioWorkletService.pause();
      }
      
      useSpeakerStore.getState().setPaused(true);
      useSpeakerStore.getState().setTransmitting(false);
      
      // Send control message via WebSocket
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
      // Resume audio capture
      if (this.audioWorkletService) {
        this.audioWorkletService.resume();
      }
      
      useSpeakerStore.getState().setPaused(false);
      useSpeakerStore.getState().setTransmitting(true);
      
      // Send control message via WebSocket
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
   * Mute audio (stop streaming entirely)
   */
  async mute(): Promise<void> {
    const startTime = Date.now();
    
    try {
      // Pause audio capture
      if (this.audioWorkletService) {
        this.audioWorkletService.pause();
      }
      
      useSpeakerStore.getState().setMuted(true);
      useSpeakerStore.getState().setTransmitting(false);
      
      // Send control message via WebSocket
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
   * Unmute audio (resume streaming)
   */
  async unmute(): Promise<void> {
    const startTime = Date.now();
    
    try {
      // Resume audio capture
      if (this.audioWorkletService) {
        this.audioWorkletService.resume();
      }
      
      useSpeakerStore.getState().setMuted(false);
      useSpeakerStore.getState().setTransmitting(true);
      
      // Send control message via WebSocket
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
   * Note: WebRTC volume control is limited, stored for preference only
   */
  async setVolume(volume: number): Promise<void> {
    const clampedVolume = Math.max(0, Math.min(100, volume));
    
    // Update store
    useSpeakerStore.getState().setInputVolume(clampedVolume);
    
    // Save preference
    const startTime = Date.now();
    try {
      const { preferenceStore } = await import('../../../shared/services/PreferenceStore');
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
    console.log('[SpeakerService] Ending session...');
    try {
      // Send end session via WebSocket
      await this.retryHandler.execute(async () => {
        if (this.wsClient.isConnected()) {
          this.wsClient.send({
            action: 'endSession',
            sessionId: useSpeakerStore.getState().sessionId,
            reason: 'Speaker ended session',
          });
        }
      });

      // Cleanup audio capture
      if (this.audioWorkletService) {
        this.audioWorkletService.cleanup();
        this.audioWorkletService = null;
      }

      // Stop status polling
      this.stopStatusPolling();

      // Close WebSocket
      setTimeout(() => {
        this.wsClient.disconnect();
      }, 1000);

      // Clear session state
      useSpeakerStore.getState().reset();
    } catch (error) {
      const appError = ErrorHandler.handle(error as Error, {
        component: 'SpeakerService',
        operation: 'endSession',
      });
      throw new Error(appError.userMessage);
    }
  }

  /**
   * Get current audio input level
   */
  getInputLevel(): number {
    // TODO: Implement with AudioWorklet if needed
    return 0;
  }

  /**
   * Get average audio input level
   */
  getAverageInputLevel(): number {
    // TODO: Implement using Web Audio API if needed
    return 0;
  }

  /**
   * Cleanup resources
   */
  cleanup(): void {
    this.stopStatusPolling();
    
    if (this.audioWorkletService) {
      this.audioWorkletService.cleanup();
      this.audioWorkletService = null;
    }
    
    this.wsClient.disconnect();
  }

  /**
   * Setup WebSocket event handlers (for control messages only)
   */
  private setupEventHandlers(): void {
    // Handle quality warnings (from backend processing)
    this.wsClient.on('audioQualityWarning', (message: any) => {
      const warning: QualityWarning = {
        type: message.issue,
        message: this.getQualityWarningMessage(message.issue, message.value),
        timestamp: Date.now(),
        issue: message.issue,
      };
      
      useSpeakerStore.getState().addQualityWarning(warning);

      // Auto-clear warning after 2 seconds
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

    // Handle errors
    this.wsClient.onError((error) => {
      console.error('WebSocket error:', error);
      ErrorHandler.handle(error, {
        component: 'SpeakerService',
        operation: 'websocket',
      });
    });
  }

  /**
   * Start polling session status every 5 seconds (WebSocket for metadata)
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
