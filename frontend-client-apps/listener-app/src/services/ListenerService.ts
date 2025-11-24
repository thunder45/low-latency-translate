import { WebSocketClient } from '../../../shared/websocket/WebSocketClient';
import { KVSWebRTCService, AWSCredentials } from '../../../shared/services/KVSWebRTCService';
import { getKVSCredentialsProvider } from '../../../shared/services/KVSCredentialsProvider';
import { useListenerStore } from '../../../shared/store/listenerStore';
import { ErrorHandler } from '../../../shared/utils/ErrorHandler';
import { preferenceStore } from '../../../shared/services/PreferenceStore';

/**
 * Configuration for ListenerService
 */
export interface ListenerServiceConfig {
  wsUrl: string;
  sessionId: string;
  targetLanguage: string;
  jwtToken: string;
  // KVS WebRTC configuration
  kvsChannelArn: string;
  kvsSignalingEndpoint: string;
  region: string;
  identityPoolId: string;
  userPoolId: string;
}

/**
 * Listener service orchestrates WebRTC audio reception and WebSocket control
 * 
 * Architecture:
 * - WebRTC (via KVS): Low-latency audio streaming (<500ms)
 * - WebSocket: Control messages and session metadata
 */
export class ListenerService {
  private wsClient: WebSocketClient;
  private kvsService: KVSWebRTCService | null = null;
  private audioElement: HTMLAudioElement | null = null;
  private config: ListenerServiceConfig;

  constructor(config: ListenerServiceConfig) {
    this.config = config;

    // Initialize WebSocket client (for control messages only)
    this.wsClient = new WebSocketClient({
      url: config.wsUrl,
      token: config.jwtToken,
      heartbeatInterval: 30000,
      reconnect: true,
      reconnectDelay: 1000,
      maxReconnectAttempts: 5,
    });

    this.setupEventHandlers();
  }

  /**
   * Initialize session and join
   */
  async initialize(): Promise<void> {
    try {
      console.log('[ListenerService] Initializing WebRTC+WebSocket hybrid service...');
      
      // Load saved preferences
      await this.loadPreferences();
      
      // Connect WebSocket (for control messages)
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

      console.log('[ListenerService] Initialization complete, ready to receive audio');
    } catch (error) {
      console.error('[ListenerService] Initialization failed:', error);
      const appError = ErrorHandler.handle(error as Error, {
        component: 'ListenerService',
        operation: 'initialize',
        sessionId: this.config.sessionId,
      });
      throw new Error(appError.userMessage);
    }
  }

  /**
   * Start receiving audio via WebRTC
   */
  async startListening(): Promise<void> {
    try {
      console.log('[ListenerService] Starting WebRTC audio reception...');
      
      // Get AWS credentials for KVS access
      const credentials = await this.getAWSCredentials();
      
      // Create KVS WebRTC service as viewer
      this.kvsService = new KVSWebRTCService({
        channelARN: this.config.kvsChannelArn,
        channelEndpoint: this.config.kvsSignalingEndpoint,
        region: this.config.region,
        credentials: credentials,
        role: 'VIEWER',
      });
      
      // Set up event handlers
      this.kvsService.onConnectionStateChange = (state) => {
        console.log('[ListenerService] WebRTC connection state:', state);
        useListenerStore.getState().setConnected(state === 'connected');
      };
      
      this.kvsService.onICEConnectionStateChange = (state) => {
        console.log('[ListenerService] ICE connection state:', state);
      };
      
      this.kvsService.onTrackReceived = (stream: MediaStream) => {
        console.log('[ListenerService] Received remote audio track');
        
        // Create audio element if not exists
        if (!this.audioElement) {
          this.audioElement = new Audio();
          this.audioElement.autoplay = true;
          
          // Apply saved volume
          const savedVolume = useListenerStore.getState().playbackVolume;
          this.audioElement.volume = savedVolume / 100;
        }
        
        // Attach remote stream to audio element
        this.audioElement.srcObject = stream;
        
        console.log('[ListenerService] Audio track connected to player');
      };
      
      this.kvsService.onError = (error) => {
        console.error('[ListenerService] WebRTC error:', error);
        ErrorHandler.handle(error, {
          component: 'ListenerService',
          operation: 'webrtc',
        });
      };
      
      // Connect as Viewer
      await this.kvsService.connectAsViewer();
      
      console.log('[ListenerService] WebRTC audio reception started');
    } catch (error) {
      console.error('[ListenerService] Failed to start listening:', error);
      const appError = ErrorHandler.handle(error as Error, {
        component: 'ListenerService',
        operation: 'startListening',
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
      console.error('[ListenerService] Failed to get AWS credentials:', error);
      throw new Error('Failed to obtain AWS credentials for audio streaming');
    }
  }

  /**
   * Load saved preferences
   */
  private async loadPreferences(): Promise<void> {
    try {
      // Use a default user ID or get from session
      const userId = `listener-${this.config.sessionId}`;
      
      // Load saved volume
      const savedVolume = await preferenceStore.getVolume(userId);
      if (savedVolume !== null) {
        await this.setVolume(savedVolume);
      }
      
      // Load saved language (if different from config)
      const savedLanguage = await preferenceStore.getLanguage(userId);
      // Ensure non-null/undefined string before using
      if (savedLanguage != null && typeof savedLanguage === 'string') {
        const trimmedLanguage = savedLanguage.trim();
        if (trimmedLanguage !== '' && trimmedLanguage !== this.config.targetLanguage) {
          // Update config but don't switch yet (will switch after connection)
          this.config.targetLanguage = trimmedLanguage;
        }
      }
    } catch (error) {
      console.warn('Failed to load preferences:', error);
      // Continue with defaults
    }
  }

  /**
   * Pause playback
   * Note: With WebRTC, we mute the audio element
   */
  async pause(): Promise<void> {
    const startTime = Date.now();
    
    try {
      if (this.audioElement) {
        this.audioElement.pause();
      }
      useListenerStore.getState().setPaused(true);
      
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
      if (this.audioElement) {
        await this.audioElement.play();
      }
      useListenerStore.getState().setPaused(false);
      
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
      if (this.audioElement) {
        this.audioElement.muted = true;
      }
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
      if (this.audioElement) {
        this.audioElement.muted = false;
      }
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
    
    if (this.audioElement) {
      this.audioElement.volume = clampedVolume / 100;
    }
    
    useListenerStore.getState().setPlaybackVolume(clampedVolume);
    
    // Save preference
    try {
      const userId = `listener-${this.config.sessionId}`;
      await preferenceStore.saveVolume(userId, clampedVolume);
    } catch (error) {
      console.warn('Failed to save volume preference:', error);
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

      // Send switch language request via WebSocket
      if (this.wsClient.isConnected()) {
        this.wsClient.send({
          action: 'changeLanguage',
          targetLanguage: newLanguage,
          timestamp: Date.now(),
        });
      }
      
      // Save preference
      try {
        const userId = `listener-${this.config.sessionId}`;
        await preferenceStore.saveLanguage(userId, newLanguage);
      } catch (error) {
        console.warn('Failed to save language preference:', error);
      }
      
      this.logControlLatency('switchLanguage', startTime);
    } catch (error) {
      // Revert to previous language on failure
      if (previousLanguage !== null) {
        useListenerStore.getState().setTargetLanguage(previousLanguage);
      }
      
      const appError = ErrorHandler.handle(error as Error, {
        component: 'ListenerService',
        operation: 'switchLanguage',
        previousLanguage: previousLanguage ?? 'unknown',
        newLanguage,
      });
      throw new Error(appError.userMessage);
    }
  }

  /**
   * Leave session
   */
  leave(): void {
    // Stop audio playback
    if (this.audioElement) {
      this.audioElement.pause();
      this.audioElement.srcObject = null;
      this.audioElement = null;
    }

    // Cleanup WebRTC
    if (this.kvsService) {
      this.kvsService.cleanup();
      this.kvsService = null;
    }

    // Close WebSocket
    this.wsClient.disconnect();

    // Clear session state
    useListenerStore.getState().reset();
  }

  /**
   * Get buffered audio duration
   * Note: With WebRTC direct streaming, buffering is minimal
   */
  getBufferedDuration(): number {
    return 0; // WebRTC streams directly with minimal buffering
  }

  /**
   * Cleanup resources
   */
  cleanup(): void {
    if (this.audioElement) {
      this.audioElement.pause();
      this.audioElement.srcObject = null;
      this.audioElement = null;
    }
    
    if (this.kvsService) {
      this.kvsService.cleanup();
      this.kvsService = null;
    }
    
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
   * Setup WebSocket event handlers (for control messages only)
   */
  private setupEventHandlers(): void {
    // Handle session joined
    this.wsClient.on('sessionJoined', (message: any) => {
      useListenerStore.getState().setSession(
        message.sessionId,
        message.targetLanguage
      );
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
    this.wsClient.on('sessionEnded', () => {
      // Stop playback
      if (this.audioElement) {
        this.audioElement.pause();
        this.audioElement.srcObject = null;
      }
      
      // Cleanup WebRTC
      if (this.kvsService) {
        this.kvsService.cleanup();
        this.kvsService = null;
      }
      
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
      ErrorHandler.handle(error, {
        component: 'ListenerService',
        operation: 'websocket',
        sessionId: this.config.sessionId,
      });
      // Error will be displayed by UI components
    });
  }
}
