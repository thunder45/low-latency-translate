/**
 * AudioWorklet Processor for Raw PCM Capture
 * 
 * Runs in the audio worklet thread (separate from main thread)
 * Captures audio at lowest possible latency (~3ms per quantum)
 * Converts Float32 to Int16 PCM format for AWS Transcribe
 */

class PCMAudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    
    // Buffer configuration
    // At 16kHz, 4096 samples = ~256ms of audio
    this.bufferSize = 4096;
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
    
    // Statistics
    this.chunksSent = 0;
    this.totalSamples = 0;
    
    console.log('[PCMAudioProcessor] Initialized, buffer size:', this.bufferSize);
  }
  
  /**
   * Process audio quantum (128 samples typically)
   * Called automatically by audio rendering thread
   */
  process(inputs, outputs, parameters) {
    const input = inputs[0];
    
    // Check if we have input
    if (!input || !input[0] || input[0].length === 0) {
      return true; // Keep processor alive
    }
    
    const channel = input[0]; // Mono channel
    
    // Accumulate samples into buffer
    for (let i = 0; i < channel.length; i++) {
      this.buffer[this.bufferIndex++] = channel[i];
      this.totalSamples++;
      
      // When buffer is full, send to main thread
      if (this.bufferIndex >= this.bufferSize) {
        this.sendPCMChunk();
        this.bufferIndex = 0;
      }
    }
    
    return true; // Keep processor alive
  }
  
  /**
   * Convert Float32 buffer to Int16 PCM and send to main thread
   */
  sendPCMChunk() {
    // Convert Float32 [-1.0, 1.0] to Int16 [-32768, 32767]
    const pcmData = new Int16Array(this.bufferSize);
    
    for (let i = 0; i < this.bufferSize; i++) {
      // Clamp to valid range
      const sample = Math.max(-1, Math.min(1, this.buffer[i]));
      
      // Convert to 16-bit integer
      // Negative: multiply by 32768 (0x8000)
      // Positive: multiply by 32767 (0x7FFF)
      pcmData[i] = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
    }
    
    this.chunksSent++;
    
    // Send to main thread (transfer ownership for zero-copy)
    this.port.postMessage(
      {
        type: 'pcm-audio',
        data: pcmData.buffer,
        sampleCount: this.bufferSize,
        chunkIndex: this.chunksSent,
        timestamp: currentTime, // Audio context time
      },
      [pcmData.buffer] // Transfer ownership
    );
  }
}

// Register the processor
registerProcessor('pcm-audio-processor', PCMAudioProcessor);
