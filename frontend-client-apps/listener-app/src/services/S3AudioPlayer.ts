/**
 * S3AudioPlayer - Downloads and plays translated audio from S3
 * 
 * Features:
 * - Sequential playback queue
 * - Prefetching (download next while playing current)
 * - Buffer management (2-3 chunks ahead)
 * - Error recovery with retry
 * - Language-specific stream handling
 */

export interface AudioChunkMetadata {
  url: string;
  timestamp: number;
  duration: number;
  sequenceNumber: number;
  transcript?: string;
}

export interface S3AudioPlayerConfig {
  targetLanguage: string;
  onPlaybackStart?: () => void;
  onPlaybackEnd?: () => void;
  onBuffering?: (isBuffering: boolean) => void;
  onError?: (error: Error) => void;
  onProgress?: (current: number, total: number) => void;
}

export class S3AudioPlayer {
  private config: S3AudioPlayerConfig;
  private playQueue: AudioChunkMetadata[] = [];
  private currentAudio: HTMLAudioElement | null = null;
  private isPlaying: boolean = false;
  private isPaused: boolean = false;
  private prefetchCache: Map<number, Blob> = new Map();
  private maxCacheSize: number = 3; // Buffer 3 chunks ahead
  private volume: number = 1.0;

  constructor(config: S3AudioPlayerConfig) {
    this.config = config;
  }

  /**
   * Add audio chunk to playback queue
   */
  async addChunk(metadata: AudioChunkMetadata): Promise<void> {
    // Add to queue in sequence order
    this.playQueue.push(metadata);
    this.playQueue.sort((a, b) => a.sequenceNumber - b.sequenceNumber);

    console.log(
      `[S3AudioPlayer] Added chunk ${metadata.sequenceNumber}, ` +
      `queue size: ${this.playQueue.length}`
    );

    // Start prefetching if not already
    this.prefetchNextChunks();

    // Start playback if not playing
    if (!this.isPlaying && !this.isPaused) {
      await this.playNext();
    }
  }

  /**
   * Play next chunk in queue
   */
  private async playNext(): Promise<void> {
    if (this.playQueue.length === 0) {
      this.isPlaying = false;
      console.log('[S3AudioPlayer] Queue empty, stopping playback');
      this.config.onPlaybackEnd?.();
      return;
    }

    if (this.isPaused) {
      console.log('[S3AudioPlayer] Playback paused');
      return;
    }

    try {
      // Get next chunk
      const chunk = this.playQueue.shift()!;

      console.log(`[S3AudioPlayer] Playing chunk ${chunk.sequenceNumber}`);

      // Check if already in cache
      let audioBlob = this.prefetchCache.get(chunk.sequenceNumber);

      if (!audioBlob) {
        // Not cached, download now
        this.config.onBuffering?.(true);
        audioBlob = await this.downloadAudio(chunk.url);
        this.config.onBuffering?.(false);
      } else {
        // Remove from cache after use
        this.prefetchCache.delete(chunk.sequenceNumber);
      }

      if (!audioBlob) {
        console.error(`[S3AudioPlayer] Failed to get audio for chunk ${chunk.sequenceNumber}`);
        // Skip to next chunk
        await this.playNext();
        return;
      }

      // Create audio element
      const audio = new Audio();
      audio.volume = this.volume;
      
      // Create object URL from blob
      const objectUrl = URL.createObjectURL(audioBlob);
      audio.src = objectUrl;

      // Set up event handlers
      audio.onended = () => {
        URL.revokeObjectURL(objectUrl);
        this.currentAudio = null;
        
        // Play next chunk
        this.playNext();
      };

      audio.onerror = (error) => {
        console.error('[S3AudioPlayer] Playback error:', error);
        URL.revokeObjectURL(objectUrl);
        this.config.onError?.(new Error('Audio playback failed'));
        
        // Try next chunk
        this.playNext();
      };

      audio.onplay = () => {
        if (!this.isPlaying) {
          this.isPlaying = true;
          this.config.onPlaybackStart?.();
        }
      };

      // Store current audio element
      this.currentAudio = audio;

      // Start playback
      await audio.play();

      // Update progress
      this.config.onProgress?.(
        chunk.sequenceNumber,
        chunk.sequenceNumber + this.playQueue.length
      );

      // Prefetch next chunks while playing
      this.prefetchNextChunks();

    } catch (error) {
      console.error('[S3AudioPlayer] Error playing chunk:', error);
      this.config.onError?.(error as Error);
      
      // Try next chunk
      await this.playNext();
    }
  }

  /**
   * Download audio from S3 presigned URL
   */
  private async downloadAudio(url: string, retries: number = 3): Promise<Blob | undefined> {
    for (let attempt = 1; attempt <= retries; attempt++) {
      try {
        const response = await fetch(url);
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const blob = await response.blob();
        
        console.log(`[S3AudioPlayer] Downloaded ${blob.size} bytes from S3`);
        
        return blob;
        
      } catch (error) {
        console.error(
          `[S3AudioPlayer] Download attempt ${attempt}/${retries} failed:`,
          error
        );
        
        if (attempt < retries) {
          // Wait before retry (exponential backoff)
          await new Promise(resolve => setTimeout(resolve, 100 * Math.pow(2, attempt)));
        }
      }
    }
    
    return undefined;
  }

  /**
   * Prefetch next chunks to cache
   */
  private async prefetchNextChunks(): Promise<void> {
    // Prefetch up to maxCacheSize chunks ahead
    const chunksToPrefetch = this.playQueue.slice(0, this.maxCacheSize);

    for (const chunk of chunksToPrefetch) {
      // Skip if already in cache
      if (this.prefetchCache.has(chunk.sequenceNumber)) {
        continue;
      }

      // Skip if cache is full
      if (this.prefetchCache.size >= this.maxCacheSize) {
        break;
      }

      // Download asynchronously (don't await)
      this.downloadAudio(chunk.url).then(blob => {
        if (blob) {
          this.prefetchCache.set(chunk.sequenceNumber, blob);
          console.log(`[S3AudioPlayer] Prefetched chunk ${chunk.sequenceNumber}`);
        }
      }).catch(error => {
        console.warn(`[S3AudioPlayer] Prefetch failed for chunk ${chunk.sequenceNumber}:`, error);
      });
    }
  }

  /**
   * Pause playback
   */
  pause(): void {
    this.isPaused = true;
    
    if (this.currentAudio) {
      this.currentAudio.pause();
    }
    
    console.log('[S3AudioPlayer] Playback paused');
  }

  /**
   * Resume playback
   */
  async resume(): Promise<void> {
    this.isPaused = false;
    
    if (this.currentAudio) {
      await this.currentAudio.play();
    } else if (this.playQueue.length > 0) {
      await this.playNext();
    }
    
    console.log('[S3AudioPlayer] Playback resumed');
  }

  /**
   * Set playback volume (0-1)
   */
  setVolume(volume: number): void {
    this.volume = Math.max(0, Math.min(1, volume));
    
    if (this.currentAudio) {
      this.currentAudio.volume = this.volume;
    }
  }

  /**
   * Mute audio
   */
  mute(): void {
    if (this.currentAudio) {
      this.currentAudio.muted = true;
    }
  }

  /**
   * Unmute audio
   */
  unmute(): void {
    if (this.currentAudio) {
      this.currentAudio.muted = false;
    }
  }

  /**
   * Clear queue and stop playback
   */
  clear(): void {
    this.playQueue = [];
    this.prefetchCache.clear();
    
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio.src = '';
      this.currentAudio = null;
    }
    
    this.isPlaying = false;
    
    console.log('[S3AudioPlayer] Cleared queue and stopped playback');
  }

  /**
   * Get buffered duration (seconds)
   */
  getBufferedDuration(): number {
    return this.playQueue.reduce((sum, chunk) => sum + chunk.duration, 0);
  }

  /**
   * Get queue size
   */
  getQueueSize(): number {
    return this.playQueue.length;
  }

  /**
   * Cleanup resources
   */
  cleanup(): void {
    this.clear();
    this.config = {} as S3AudioPlayerConfig;
  }
}
