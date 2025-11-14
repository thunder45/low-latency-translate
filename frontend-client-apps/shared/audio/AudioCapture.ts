import { AudioCaptureConfig, AudioChunk } from './types';

/**
 * Audio capture service for speaker application
 * Handles microphone access, audio processing, and PCM conversion
 */
export class AudioCapture {
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private processor: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private analyser: AnalyserNode | null = null;
  private config: AudioCaptureConfig;
  private chunkCounter: number = 0;
  private onChunkCallback: ((chunk: AudioChunk) => void) | null = null;
  private currentInputLevel: number = 0;
  private levelHistory: number[] = [];
  private readonly LEVEL_HISTORY_SIZE = 30; // 1 second at 30 FPS

  constructor(config: AudioCaptureConfig) {
    this.config = config;
  }

  /**
   * Start audio capture
   */
  async start(): Promise<void> {
    try {
      // Request microphone permission
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: this.config.echoCancellation,
          noiseSuppression: this.config.noiseSuppression,
          autoGainControl: this.config.autoGainControl,
          sampleRate: { ideal: this.config.sampleRate },
          channelCount: { ideal: this.config.channelCount },
        },
      });

      // Create audio context
      this.audioContext = new AudioContext({ sampleRate: this.config.sampleRate });
      this.source = this.audioContext.createMediaStreamSource(this.mediaStream);

      // Create analyser for input level monitoring
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 256;
      this.source.connect(this.analyser);

      // Calculate buffer size for chunk duration
      const bufferSize = Math.pow(2, Math.ceil(Math.log2(this.config.sampleRate * this.config.chunkDuration)));
      this.processor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);

      this.processor.onaudioprocess = (e) => {
        const audioData = e.inputBuffer.getChannelData(0);
        const chunk = this.processAudioChunk(audioData);

        // Update input level
        this.updateInputLevel(audioData);

        if (this.onChunkCallback) {
          this.onChunkCallback(chunk);
        }
      };

      this.source.connect(this.processor);
      this.processor.connect(this.audioContext.destination);
    } catch (error) {
      if (error instanceof Error) {
        if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
          throw new Error('Microphone access denied. Please enable microphone permissions in your browser settings.');
        } else if (error.name === 'NotFoundError') {
          throw new Error('No microphone found. Please connect a microphone and try again.');
        }
      }
      throw error;
    }
  }

  /**
   * Stop audio capture
   */
  stop(): void {
    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }
    if (this.analyser) {
      this.analyser.disconnect();
      this.analyser = null;
    }
    if (this.source) {
      this.source.disconnect();
      this.source = null;
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
    this.chunkCounter = 0;
    this.currentInputLevel = 0;
    this.levelHistory = [];
  }

  /**
   * Register callback for audio chunks
   */
  onChunk(callback: (chunk: AudioChunk) => void): void {
    this.onChunkCallback = callback;
  }

  /**
   * Get current input level (0-100)
   */
  getInputLevel(): number {
    return this.currentInputLevel;
  }

  /**
   * Get average input level over last second (0-100)
   */
  getAverageInputLevel(): number {
    if (this.levelHistory.length === 0) return 0;
    const sum = this.levelHistory.reduce((a, b) => a + b, 0);
    return sum / this.levelHistory.length;
  }

  /**
   * Check if audio capture is active
   */
  isActive(): boolean {
    return this.audioContext !== null && this.audioContext.state === 'running';
  }

  /**
   * Process audio chunk: convert Float32 to PCM 16-bit and encode as base64
   */
  private processAudioChunk(audioData: Float32Array): AudioChunk {
    // Convert Float32 to PCM 16-bit
    const pcm16 = new Int16Array(audioData.length);
    for (let i = 0; i < audioData.length; i++) {
      const s = Math.max(-1, Math.min(1, audioData[i]));
      pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }

    // Convert to base64
    const bytes = new Uint8Array(pcm16.buffer);
    const base64 = btoa(String.fromCharCode(...bytes));

    return {
      data: base64,
      timestamp: Date.now(),
      chunkId: `chunk-${++this.chunkCounter}`,
      duration: this.config.chunkDuration,
    };
  }

  /**
   * Update input level from audio data
   */
  private updateInputLevel(audioData: Float32Array): void {
    // Calculate RMS (Root Mean Square) level
    let sum = 0;
    for (let i = 0; i < audioData.length; i++) {
      sum += audioData[i] * audioData[i];
    }
    const rms = Math.sqrt(sum / audioData.length);

    // Convert to percentage (0-100)
    // RMS typically ranges from 0 to ~0.5 for normal speech
    const level = Math.min(100, Math.round(rms * 200));

    this.currentInputLevel = level;

    // Update history for average calculation
    this.levelHistory.push(level);
    if (this.levelHistory.length > this.LEVEL_HISTORY_SIZE) {
      this.levelHistory.shift();
    }
  }
}
