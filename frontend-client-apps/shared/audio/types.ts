/**
 * Audio capture configuration
 */
export interface AudioCaptureConfig {
  sampleRate: number; // 16000
  channelCount: number; // 1 (mono)
  chunkDuration: number; // 1-3 seconds
  echoCancellation: boolean;
  noiseSuppression: boolean;
  autoGainControl: boolean;
}

/**
 * Audio chunk data
 */
export interface AudioChunk {
  data: string; // Base64-encoded PCM
  timestamp: number;
  chunkId: string;
  duration: number;
}

/**
 * Audio playback configuration
 */
export interface AudioPlaybackConfig {
  maxBufferDuration: number; // Maximum buffer duration in seconds (default 30)
}

/**
 * Audio format information
 */
export interface AudioFormat {
  sampleRate: number;
  channels: number;
  format: 'pcm';
}

/**
 * Playback state
 */
export interface PlaybackState {
  isPlaying: boolean;
  isPaused: boolean;
  isMuted: boolean;
  volume: number; // 0.0 to 1.0
  bufferedDuration: number; // seconds
  queueLength: number;
}
