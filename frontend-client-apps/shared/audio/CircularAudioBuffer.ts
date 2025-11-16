/**
 * Circular Audio Buffer for pause functionality
 * 
 * Implements a circular buffer that stores up to 30 seconds of audio data
 * for listener pause/resume functionality. Automatically discards oldest
 * data when buffer capacity is exceeded.
 */

import type { BufferStatus } from '../types/controls';

export class CircularAudioBuffer {
  private buffer: Float32Array;
  private writePos: number = 0;
  private readPos: number = 0;
  private sampleRate: number;
  private maxSamples: number;
  private availableSamples: number = 0;
  
  /**
   * Create a new circular audio buffer
   * 
   * @param sampleRate - Audio sample rate in Hz (e.g., 24000)
   * @param maxDurationMs - Maximum buffer duration in milliseconds (default: 30000)
   */
  constructor(sampleRate: number, maxDurationMs: number = 30000) {
    this.sampleRate = sampleRate;
    this.maxSamples = Math.floor((sampleRate * maxDurationMs) / 1000);
    this.buffer = new Float32Array(this.maxSamples);
  }
  
  /**
   * Write audio data to the buffer
   * 
   * If buffer capacity is exceeded, oldest data is automatically discarded.
   * 
   * @param audioData - Audio samples to write
   * @returns true if buffer is near capacity (>90%), false otherwise
   */
  write(audioData: Float32Array): boolean {
    const samplesToWrite = audioData.length;
    
    // Check if buffer will overflow
    if (this.availableSamples + samplesToWrite > this.maxSamples) {
      // Discard oldest data to make room
      const overflow = (this.availableSamples + samplesToWrite) - this.maxSamples;
      this.readPos = (this.readPos + overflow) % this.maxSamples;
      this.availableSamples = this.maxSamples - samplesToWrite;
    }
    
    // Write new data
    for (let i = 0; i < samplesToWrite; i++) {
      this.buffer[this.writePos] = audioData[i];
      this.writePos = (this.writePos + 1) % this.maxSamples;
    }
    
    this.availableSamples += samplesToWrite;
    
    // Return true if near capacity (>90%)
    return this.availableSamples >= this.maxSamples * 0.9;
  }
  
  /**
   * Read audio data from the buffer
   * 
   * @param durationMs - Duration of audio to read in milliseconds
   * @returns Audio samples read from buffer
   */
  read(durationMs: number): Float32Array {
    const samplesToRead = Math.min(
      Math.floor((this.sampleRate * durationMs) / 1000),
      this.availableSamples
    );
    
    const result = new Float32Array(samplesToRead);
    
    for (let i = 0; i < samplesToRead; i++) {
      result[i] = this.buffer[this.readPos];
      this.readPos = (this.readPos + 1) % this.maxSamples;
    }
    
    this.availableSamples -= samplesToRead;
    return result;
  }
  
  /**
   * Clear all buffered audio data
   */
  clear(): void {
    this.writePos = 0;
    this.readPos = 0;
    this.availableSamples = 0;
    this.buffer.fill(0);
  }
  
  /**
   * Get the duration of buffered audio in milliseconds
   * 
   * @returns Buffered duration in milliseconds
   */
  getBufferedDuration(): number {
    return Math.floor((this.availableSamples / this.sampleRate) * 1000);
  }
  
  /**
   * Get current buffer status
   * 
   * @returns Buffer status including size and overflow state
   */
  getBufferStatus(): BufferStatus {
    return {
      currentSize: this.availableSamples,
      maxSize: this.maxSamples,
      isOverflowing: this.availableSamples >= this.maxSamples * 0.9
    };
  }
}
