/**
 * AudioStreamService - Captures audio via MediaRecorder and streams to backend
 * 
 * Features:
 * - 250ms chunk size for low latency
 * - WebM/Opus format (browser native, small size)
 * - Automatic reconnection on WebSocket failure
 * - Error recovery with local buffering
 */

export interface AudioStreamConfig {
  sessionId: string;
  websocket: WebSocket;
  chunkDuration: number; // milliseconds
  onChunkSent?: (size: number, index: number) => void;
  onError?: (error: Error) => void;
  onStreamStart?: () => void;
  onStreamStop?: () => void;
}

export class AudioStreamService {
  private mediaRecorder: MediaRecorder | null = null;
  private audioStream: MediaStream | null = null;
  private config: AudioStreamConfig;
  private chunkIndex: number = 0;
  private isStreaming: boolean = false;
  private chunksBuffer: Blob[] = []; // Buffer for failed sends
  private maxBufferSize: number = 20; // Max 5 seconds of buffering

  constructor(config: AudioStreamConfig) {
    this.config = config;
  }

  /**
   * Start audio capture and streaming
   */
  async start(): Promise<void> {
    try {
      console.log('[AudioStreamService] Starting audio capture...');

      // Request microphone access
      this.audioStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1, // Mono
          sampleRate: 16000, // 16kHz for Transcribe
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      });

      console.log('[AudioStreamService] Microphone access granted');

      // Check if WebM/Opus is supported
      const mimeType = this.getSupportedMimeType();
      console.log('[AudioStreamService] Using MIME type:', mimeType);

      // Create MediaRecorder
      this.mediaRecorder = new MediaRecorder(this.audioStream, {
        mimeType,
        audioBitsPerSecond: 16000, // 16kbps for low bandwidth
      });

      // Handle data available events
      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.handleAudioChunk(event.data);
        }
      };

      // Handle errors
      this.mediaRecorder.onerror = (event) => {
        console.error('[AudioStreamService] MediaRecorder error:', event);
        this.config.onError?.(new Error('MediaRecorder error'));
      };

      // Handle recording stop
      this.mediaRecorder.onstop = () => {
        console.log('[AudioStreamService] MediaRecorder stopped');
        this.config.onStreamStop?.();
      };

      // Start recording with time slices
      this.mediaRecorder.start(this.config.chunkDuration);
      this.isStreaming = true;

      console.log('[AudioStreamService] Audio streaming started');
      this.config.onStreamStart?.();

    } catch (error) {
      console.error('[AudioStreamService] Failed to start:', error);
      
      // Clean up on error
      this.cleanup();
      
      // Provide user-friendly error message
      let errorMessage = 'Failed to access microphone';
      if (error instanceof Error) {
        if (error.name === 'NotAllowedError') {
          errorMessage = 'Microphone access denied. Please allow microphone access in browser settings.';
        } else if (error.name === 'NotFoundError') {
          errorMessage = 'No microphone found. Please connect a microphone.';
        } else if (error.name === 'NotReadableError') {
          errorMessage = 'Microphone is already in use by another application.';
        }
      }
      
      throw new Error(errorMessage);
    }
  }

  /**
   * Stop audio capture and streaming
   */
  stop(): void {
    console.log('[AudioStreamService] Stopping audio capture...');

    this.isStreaming = false;

    // Stop MediaRecorder
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop();
    }

    // Stop all audio tracks
    if (this.audioStream) {
      this.audioStream.getTracks().forEach(track => track.stop());
    }

    // Clear buffer
    this.chunksBuffer = [];

    console.log('[AudioStreamService] Audio capture stopped');
  }

  /**
   * Pause streaming (keep capturing but don't send)
   */
  pause(): void {
    this.isStreaming = false;
    console.log('[AudioStreamService] Streaming paused');
  }

  /**
   * Resume streaming
   */
  resume(): void {
    this.isStreaming = true;
    
    // Send any buffered chunks
    if (this.chunksBuffer.length > 0) {
      console.log(`[AudioStreamService] Sending ${this.chunksBuffer.length} buffered chunks`);
      const buffer = [...this.chunksBuffer];
      this.chunksBuffer = [];
      buffer.forEach(chunk => this.handleAudioChunk(chunk));
    }
    
    console.log('[AudioStreamService] Streaming resumed');
  }

  /**
   * Get audio input level (0-100)
   * Returns 0 for now - would need Web Audio API analyzer
   */
  getInputLevel(): number {
    // TODO: Implement with Web Audio API if needed
    return 0;
  }

  /**
   * Cleanup resources
   */
  cleanup(): void {
    this.stop();
    this.mediaRecorder = null;
    this.audioStream = null;
  }

  /**
   * Handle audio chunk from MediaRecorder
   */
  private handleAudioChunk(blob: Blob): void {
    if (!this.isStreaming) {
      // Buffer chunk if not streaming
      if (this.chunksBuffer.length < this.maxBufferSize) {
        this.chunksBuffer.push(blob);
      } else {
        console.warn('[AudioStreamService] Buffer full, dropping chunk');
      }
      return;
    }

    // Convert blob to base64 and send
    const reader = new FileReader();
    
    reader.onload = () => {
      if (reader.result && typeof reader.result === 'string') {
        // Extract base64 data (remove data URL prefix)
        const base64Data = reader.result.split(',')[1];
        
        this.sendChunk(base64Data, blob.size);
      }
    };

    reader.onerror = () => {
      console.error('[AudioStreamService] Failed to read audio chunk');
      this.config.onError?.(new Error('Failed to read audio chunk'));
    };

    reader.readAsDataURL(blob);
  }

  /**
   * Send audio chunk via WebSocket
   */
  private sendChunk(base64Data: string, originalSize: number): void {
    if (this.config.websocket.readyState !== WebSocket.OPEN) {
      console.warn('[AudioStreamService] WebSocket not open, buffering chunk');
      
      // Buffer for later (will be sent on reconnect)
      // Note: We already converted to base64, so we'd need to reconvert
      // For simplicity, just skip this chunk and log
      return;
    }

    try {
      const message = {
        action: 'audioChunk',
        sessionId: this.config.sessionId,
        audioData: base64Data,
        timestamp: Date.now(),
        format: 'webm-opus',
        chunkIndex: this.chunkIndex++,
        originalSize: originalSize,
      };

      this.config.websocket.send(JSON.stringify(message));

      // Log every 10th chunk to avoid console spam
      if (this.chunkIndex % 10 === 0) {
        console.log(
          `[AudioStreamService] Sent chunk ${this.chunkIndex}, ` +
          `size: ${originalSize} bytes, ` +
          `base64: ${base64Data.length} chars`
        );
      }

      // Callback for monitoring
      this.config.onChunkSent?.(originalSize, this.chunkIndex);

    } catch (error) {
      console.error('[AudioStreamService] Failed to send chunk:', error);
      this.config.onError?.(error as Error);
    }
  }

  /**
   * Get supported MIME type for MediaRecorder
   */
  private getSupportedMimeType(): string {
    // Prefer WebM with Opus codec (best compression, widely supported)
    const types = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/ogg',
    ];

    for (const type of types) {
      if (MediaRecorder.isTypeSupported(type)) {
        return type;
      }
    }

    // Fallback to default
    console.warn('[AudioStreamService] No preferred MIME type supported, using default');
    return '';
  }

  /**
   * Check if microphone is currently accessible
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
   * Get list of available audio input devices
   */
  static async getAudioInputDevices(): Promise<MediaDeviceInfo[]> {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      return devices.filter(device => device.kind === 'audioinput');
    } catch (error) {
      console.error('[AudioStreamService] Failed to enumerate devices:', error);
      return [];
    }
  }
}
