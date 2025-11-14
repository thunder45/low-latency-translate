import { AudioPlaybackConfig, PlaybackState } from './types';

/**
 * Audio playback service for listener application
 * Handles audio decoding, buffering, and playback
 */
export class AudioPlayback {
  private audioContext: AudioContext | null = null;
  private audioQueue: AudioBuffer[] = [];
  private isPlaying: boolean = false;
  private isPaused: boolean = false;
  private isMuted: boolean = false;
  private volume: number = 0.8; // 0.0 to 1.0
  private gainNode: GainNode | null = null;
  private currentSource: AudioBufferSourceNode | null = null;
  private config: AudioPlaybackConfig;
  private onBufferingCallback: ((buffering: boolean) => void) | null = null;
  private onBufferOverflowCallback: (() => void) | null = null;

  constructor(config: AudioPlaybackConfig = { maxBufferDuration: 30 }) {
    this.config = config;
  }

  /**
   * Initialize audio playback
   */
  async initialize(): Promise<void> {
    this.audioContext = new AudioContext();
    this.gainNode = this.audioContext.createGain();
    this.gainNode.connect(this.audioContext.destination);
    this.gainNode.gain.value = this.volume;
  }

  /**
   * Play audio from base64-encoded PCM data
   */
  async playAudio(audioMessage: {
    audioData: string;
    sampleRate: number;
    channels: number;
  }): Promise<void> {
    if (!this.audioContext || !this.gainNode) {
      throw new Error('AudioPlayback not initialized');
    }

    try {
      // Decode base64 to audio samples
      const audioBytes = atob(audioMessage.audioData);
      const audioData = new Int16Array(audioBytes.length / 2);

      for (let i = 0; i < audioData.length; i++) {
        const byte1 = audioBytes.charCodeAt(i * 2);
        const byte2 = audioBytes.charCodeAt(i * 2 + 1);
        audioData[i] = (byte2 << 8) | byte1; // Little-endian
      }

      // Create AudioBuffer
      const audioBuffer = this.audioContext.createBuffer(
        audioMessage.channels,
        audioData.length,
        audioMessage.sampleRate
      );

      // Convert PCM to Float32 and copy to buffer
      const channelData = audioBuffer.getChannelData(0);
      for (let i = 0; i < audioData.length; i++) {
        channelData[i] = audioData[i] / 32768.0; // Normalize to -1.0 to 1.0
      }

      // Check buffer overflow
      const currentBufferDuration = this.getBufferDuration();
      if (currentBufferDuration >= this.config.maxBufferDuration) {
        // Discard oldest chunk
        this.audioQueue.shift();
        if (this.onBufferOverflowCallback) {
          this.onBufferOverflowCallback();
        }
      }

      // Queue for playback
      this.audioQueue.push(audioBuffer);

      if (!this.isPaused) {
        this.schedulePlayback();
      }
    } catch (error) {
      console.error('Failed to play audio:', error);
      throw error;
    }
  }

  /**
   * Pause playback (buffer audio)
   */
  pause(): void {
    this.isPaused = true;
    if (this.currentSource) {
      this.currentSource.stop();
      this.currentSource = null;
    }
    this.isPlaying = false;
  }

  /**
   * Resume playback
   */
  resume(): void {
    this.isPaused = false;
    this.schedulePlayback();
  }

  /**
   * Set muted state
   */
  setMuted(muted: boolean): void {
    this.isMuted = muted;
    if (this.gainNode) {
      this.gainNode.gain.value = muted ? 0 : this.volume;
    }
  }

  /**
   * Set volume (0.0 to 1.0)
   */
  setVolume(volume: number): void {
    this.volume = Math.max(0, Math.min(1, volume));
    if (this.gainNode && !this.isMuted) {
      this.gainNode.gain.value = this.volume;
    }
  }

  /**
   * Clear audio buffer
   */
  clearBuffer(): void {
    this.audioQueue = [];
  }

  /**
   * Get buffered audio duration in seconds
   */
  getBufferDuration(): number {
    return this.audioQueue.reduce((total, buffer) => total + buffer.duration, 0);
  }

  /**
   * Get number of chunks in queue
   */
  getQueueLength(): number {
    return this.audioQueue.length;
  }

  /**
   * Get current playback state
   */
  getState(): PlaybackState {
    return {
      isPlaying: this.isPlaying,
      isPaused: this.isPaused,
      isMuted: this.isMuted,
      volume: this.volume,
      bufferedDuration: this.getBufferDuration(),
      queueLength: this.getQueueLength(),
    };
  }

  /**
   * Register callback for buffering state changes
   */
  onBuffering(callback: (buffering: boolean) => void): void {
    this.onBufferingCallback = callback;
  }

  /**
   * Register callback for buffer overflow
   */
  onBufferOverflow(callback: () => void): void {
    this.onBufferOverflowCallback = callback;
  }

  /**
   * Destroy audio playback and clean up resources
   */
  destroy(): void {
    this.pause();
    this.clearBuffer();
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
    this.gainNode = null;
  }

  /**
   * Schedule next audio buffer for playback
   */
  private schedulePlayback(): void {
    if (this.isPaused || this.isPlaying || this.audioQueue.length === 0) {
      // Check if we're buffering
      if (this.audioQueue.length === 0 && this.onBufferingCallback) {
        this.onBufferingCallback(true);
      }
      return;
    }

    // Not buffering anymore
    if (this.onBufferingCallback) {
      this.onBufferingCallback(false);
    }

    const buffer = this.audioQueue.shift()!;
    this.currentSource = this.audioContext!.createBufferSource();
    this.currentSource.buffer = buffer;
    this.currentSource.connect(this.gainNode!);

    this.currentSource.onended = () => {
      this.isPlaying = false;
      this.currentSource = null;
      this.schedulePlayback();
    };

    this.currentSource.start();
    this.isPlaying = true;
  }
}
