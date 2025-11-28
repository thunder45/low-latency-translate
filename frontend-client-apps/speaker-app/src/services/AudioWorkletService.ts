/**
 * AudioWorklet Service for Low-Latency PCM Capture
 * 
 * Replaces MediaRecorder-based AudioStreamService
 * Captures raw PCM audio with ~3ms latency using AudioWorklet API
 * 
 * Benefits:
 * - Lowest possible latency (no buffering)
 * - Direct access to audio samples
 * - No container format overhead
 * - Ready for streaming to Transcribe
 */

export interface AudioWorkletConfig {
  sampleRate?: number;  // Target sample rate (default: 16000 for Transcribe)
  bufferSize?: number;  // Samples per chunk (default: 4096 = ~256ms @ 16kHz)
  onAudioData: (pcmData: ArrayBuffer, timestamp: number) => void;
  onError?: (error: Error) => void;
  onStateChange?: (state: 'idle' | 'capturing' | 'error') => void;
}

export class AudioWorkletService {
  private audioContext: AudioContext | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private mediaStream: MediaStream | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private config: AudioWorkletConfig;
  private state: 'idle' | 'capturing' | 'error' = 'idle';
  private chunkCount: number = 0;

  constructor(config: AudioWorkletConfig) {
    this.config = {
      sampleRate: 16000,  // AWS Transcribe optimal rate
      bufferSize: 4096,   // ~256ms chunks at 16kHz
      ...config,
    };
  }

  /**
   * Check if AudioWorklet is supported
   */
  static isSupported(): boolean {
    return typeof AudioWorkletNode !== 'undefined';
  }

  /**
   * Check microphone access
   */
  static async checkMicrophoneAccess(): Promise<boolean> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(track => track.stop());
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Get available audio input devices
   */
  static async getAudioInputDevices(): Promise<MediaDeviceInfo[]> {
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.filter(device => device.kind === 'audioinput');
  }

  /**
   * Initialize AudioWorklet
   */
  async initialize(): Promise<void> {
    try {
      console.log('[AudioWorklet] Initializing...');
      
      // Check support
      if (!AudioWorkletService.isSupported()) {
        throw new Error('AudioWorklet not supported in this browser');
      }

      // Create AudioContext with target sample rate
      this.audioContext = new AudioContext({
        sampleRate: this.config.sampleRate,
        latencyHint: 'interactive', // Lowest latency mode
      });

      // Load worklet processor module
      await this.audioContext.audioWorklet.addModule('/audio-worklet-processor.js');
      
      console.log(
        `[AudioWorklet] Initialized successfully`,
        `Sample rate: ${this.audioContext.sampleRate}Hz`,
        `Base latency: ${(this.audioContext.baseLatency * 1000).toFixed(2)}ms`
      );
      
      this.setState('idle');
      
    } catch (error) {
      console.error('[AudioWorklet] Initialization failed:', error);
      this.setState('error');
      this.config.onError?.(error as Error);
      throw error;
    }
  }

  /**
   * Start capturing audio
   */
  async startCapture(deviceId?: string): Promise<void> {
    try {
      if (!this.audioContext) {
        throw new Error('AudioWorklet not initialized. Call initialize() first.');
      }

      console.log('[AudioWorklet] Starting capture...');

      // Get microphone access
      const constraints: MediaStreamConstraints = {
        audio: {
          channelCount: 1,  // Mono
          sampleRate: this.config.sampleRate,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      };

      // Add device ID if specified
      if (deviceId) {
        (constraints.audio as MediaTrackConstraints).deviceId = { exact: deviceId };
      }

      this.mediaStream = await navigator.mediaDevices.getUserMedia(constraints);

      // Get actual settings
      const track = this.mediaStream.getAudioTracks()[0];
      const settings = track.getSettings();
      console.log('[AudioWorklet] Microphone settings:', settings);

      // Create source node from microphone
      this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream);

      // Create worklet node
      this.workletNode = new AudioWorkletNode(
        this.audioContext,
        'pcm-audio-processor',
        {
          numberOfInputs: 1,
          numberOfOutputs: 1,
          outputChannelCount: [1],
        }
      );

      // Listen for PCM data from worklet
      this.workletNode.port.onmessage = (event) => {
        if (event.data.type === 'pcm-audio') {
          this.handlePCMData(event.data);
        }
      };

      // Connect audio graph: microphone → worklet → destination
      this.sourceNode.connect(this.workletNode);
      // Note: Not connecting to destination to avoid feedback
      // this.workletNode.connect(this.audioContext.destination);

      this.setState('capturing');
      console.log('[AudioWorklet] Capture started');

    } catch (error) {
      console.error('[AudioWorklet] Failed to start capture:', error);
      this.setState('error');
      this.config.onError?.(error as Error);
      throw error;
    }
  }

  /**
   * Handle PCM data from worklet
   */
  private handlePCMData(data: any): void {
    try {
      this.chunkCount++;

      // Send to callback with current timestamp
      const timestamp = Date.now();
      this.config.onAudioData(data.data, timestamp);

      // Log every 10 chunks to avoid spam
      if (this.chunkCount % 10 === 0) {
        console.log(
          `[AudioWorklet] Sent ${this.chunkCount} chunks, ` +
          `latest: ${data.sampleCount} samples`
        );
      }

    } catch (error) {
      console.error('[AudioWorklet] Error handling PCM data:', error);
      this.config.onError?.(error as Error);
    }
  }

  /**
   * Stop capturing audio
   */
  stopCapture(): void {
    try {
      console.log('[AudioWorklet] Stopping capture...');

      // Disconnect audio graph
      if (this.sourceNode) {
        this.sourceNode.disconnect();
        this.sourceNode = null;
      }

      if (this.workletNode) {
        this.workletNode.disconnect();
        this.workletNode.port.close();
        this.workletNode = null;
      }

      // Stop microphone
      if (this.mediaStream) {
        this.mediaStream.getTracks().forEach(track => {
          track.stop();
          console.log(`[AudioWorklet] Stopped track: ${track.label}`);
        });
        this.mediaStream = null;
      }

      this.setState('idle');
      console.log(`[AudioWorklet] Capture stopped. Total chunks sent: ${this.chunkCount}`);

    } catch (error) {
      console.error('[AudioWorklet] Error stopping capture:', error);
      this.config.onError?.(error as Error);
    }
  }

  /**
   * Pause capture (mute input)
   */
  pause(): void {
    if (this.mediaStream) {
      this.mediaStream.getAudioTracks().forEach(track => {
        track.enabled = false;
      });
      console.log('[AudioWorklet] Paused (muted)');
    }
  }

  /**
   * Resume capture (unmute input)
   */
  resume(): void {
    if (this.mediaStream) {
      this.mediaStream.getAudioTracks().forEach(track => {
        track.enabled = true;
      });
      console.log('[AudioWorklet] Resumed (unmuted)');
    }
  }

  /**
   * Get current state
   */
  getState(): 'idle' | 'capturing' | 'error' {
    return this.state;
  }

  /**
   * Get statistics
   */
  getStats(): { chunksSent: number; sampleRate: number; bufferSize: number } {
    return {
      chunksSent: this.chunkCount,
      sampleRate: this.audioContext?.sampleRate || 0,
      bufferSize: this.config.bufferSize || 0,
    };
  }

  /**
   * Cleanup resources
   */
  cleanup(): void {
    try {
      console.log('[AudioWorklet] Cleaning up...');

      this.stopCapture();

      if (this.audioContext && this.audioContext.state !== 'closed') {
        this.audioContext.close();
        this.audioContext = null;
      }

      console.log('[AudioWorklet] Cleanup complete');

    } catch (error) {
      console.error('[AudioWorklet] Error during cleanup:', error);
    }
  }

  /**
   * Update internal state and notify callback
   */
  private setState(newState: 'idle' | 'capturing' | 'error'): void {
    if (this.state !== newState) {
      this.state = newState;
      this.config.onStateChange?.(newState);
    }
  }
}
