import { KVSWebRTCService, AWSCredentials } from '../../../shared/services/KVSWebRTCService';
import { getKVSCredentialsProvider } from '../../../shared/services/KVSCredentialsProvider';
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
  kvsChannelArn: string;
  kvsSignalingEndpoint: string;
  region: string;
  identityPoolId: string;
  userPoolId: string;
}

/**
 * Speaker service orchestrates WebRTC audio streaming and WebSocket control
 * 
 * Architecture:
 * - WebRTC (via KVS): Low-latency audio streaming (<500ms)
 * - WebSocket: Control messages and session metadata
 */
export class SpeakerService {
  private wsClient: WebSocketClient;
  private kvsService: KVSWebRTCService | null = null;
  private statusPollInterval: NodeJS.Timeout | null = null;
  private retryHandler: RetryHandler;
  private config: SpeakerServiceConfig;

  constructor(config: SpeakerServiceConfig, wsClient: WebSocketClient) {
    this.config = config;
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
      console.log('[SpeakerService] Initializing WebRTC+WebSocket hybrid service...');
      
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
   * Start audio broadcasting via WebRTC
   * Audio automatically streams to KVS - no manual chunk handling!
   */
  async startBroadcast(): Promise<void> {
    try {
      console.log('[SpeakerService] Starting WebRTC broadcast...');
      
      // Get AWS credentials for KVS access
      const credentials = await this.getAWSCredentials();
      
      // Create KVS WebRTC service
      this.kvsService = new KVSWebRTCService({
        channelARN: this.config.kvsChannelArn,
        channelEndpoint: this.config.kvsSignalingEndpoint,
        region: this.config.region,
        credentials: credentials,
        role: 'MASTER',
      });
      
      // Set up event handlers
      this.kvsService.onConnectionStateChange = (state) => {
        console.log('[SpeakerService] WebRTC connection state:', state);
        useSpeakerStore.getState().setConnected(state === 'connected');
        useSpeakerStore.getState().setTransmitting(state === 'connected');
      };
      
      this.kvsService.onICEConnectionStateChange = (state) => {
        console.log('[SpeakerService] ICE connection state:', state);
      };
      
      this.kvsService.onError = (error) => {
        console.error('[SpeakerService] WebRTC error:', error);
        ErrorHandler.handle(error, {
          component: 'SpeakerService',
          operation: 'webrtc',
        });
      };
      
      // Connect as Master (microphone access + WebRTC connection)
      await this.kvsService.connectAsMaster();
      
      console.log('[SpeakerService] WebRTC broadcast started - audio streaming via UDP');
      
      // Start session status polling (WebSocket for metadata only)
      this.startStatusPolling();
      
      useSpeakerStore.getState().setTransmitting(true);
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
   * Get AWS credentials for KVS access
   */
  private async getAWSCredentials(): Promise<AWSCredentials> {
    try {
      const credentialsProvider = getKVSCredentialsProvider({
        region: this.config.region,
        identityPoolId: this.config.identityPoolId,
        userPoolId: this.config.userPoolId,
      });
      
      return await credentialsProvider.getCredentials(this.config.jwtToken);
    } catch (error) {
      console.error('[SpeakerService] Failed to get AWS credentials:', error);
      throw new Error('Failed to obtain AWS credentials for streaming');
    }
  }

  /**
   * Pause broadcast
   */
  async pause(): Promise<void> {
    const startTime = Date.now();
    
    try {
      // Mute WebRTC audio track (effectively pauses transmission)
      if (this.kvsService) {
        this.kvsService.mute();
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
      // Unmute WebRTC audio track (resumes transmission)
      if (this.kvsService) {
        this.kvsService.unmute();
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
   * Mute audio
   */
  async mute(): Promise<void> {
    const startTime = Date.now();
    
    try {
      // Mute WebRTC audio track
      if (this.kvsService) {
        this.kvsService.mute();
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
   * Unmute audio
   */
  async unmute(): Promise<void> {
    const startTime = Date.now();
    
    try {
      // Unmute WebRTC audio track
      if (this.kvsService) {
        this.kvsService.unmute();
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

      // Cleanup WebRTC
      if (this.kvsService) {
        this.kvsService.cleanup();
        this.kvsService = null;
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
   * Note: WebRTC doesn't provide easy access to input levels
   * Would need Web Audio API analyzer node
   */
  getInputLevel(): number {
    // TODO: Implement using Web Audio API if needed
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
    
    if (this.kvsService) {
      this.kvsService.cleanup();
      this.kvsService = null;
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
