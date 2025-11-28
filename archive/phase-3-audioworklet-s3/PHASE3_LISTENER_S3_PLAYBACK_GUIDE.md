# Phase 3: Listener S3 Playback Implementation Guide

## Overview
Implement S3-based translated audio delivery and playback for listener app.

**Duration:** 6-8 hours  
**Prerequisites:** Phase 2 complete (KVS Stream working)  
**Goal:** Listeners receive and play translated audio via S3

---

## Architecture Flow

```
audio_processor Lambda
    ↓ Transcribe → Translate → TTS
    ↓ Generate 2-second MP3 chunk
    ↓ Store in S3
    ↓ Generate presigned URL (10 min expiration)
    ↓ Send notification via WebSocket
Listener Browser
    ↓ Receive WebSocket message
    ↓ Download MP3 from S3
    ↓ Add to playback queue
    ↓ Play audio (HTMLAudioElement)
    ↓ Prefetch next chunk
```

---

## Step 1: Update audio_processor for S3 Storage

**File:** `audio-transcription/lambda/audio_processor/handler.py`

Add S3 storage after TTS generation:

```python
import boto3
from botocore.exceptions import ClientError

# Initialize S3 client
s3_client = boto3.client('s3')
apigw_management_client = None  # Initialized with endpoint

# Configuration
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', f'translation-audio-{STAGE}')
PRESIGNED_URL_EXPIRATION = int(os.environ.get('PRESIGNED_URL_EXPIRATION', '600'))  # 10 minutes
API_GATEWAY_ENDPOINT = os.environ.get('API_GATEWAY_ENDPOINT', '')

# Initialize API Gateway Management client
if API_GATEWAY_ENDPOINT:
    apigw_management_client = boto3.client(
        'apigatewaymanagementapi',
        endpoint_url=API_GATEWAY_ENDPOINT
    )


async def deliver_translated_audio(
    session_id: str,
    target_language: str,
    audio_bytes: bytes,
    transcript: str,
    timestamp: int,
    duration: float = 2.0
) -> bool:
    """
    Store TTS audio in S3 and notify listeners.
    
    Args:
        session_id: Session identifier
        target_language: Target language code (e.g., 'es', 'fr')
        audio_bytes: MP3 audio data from TTS
        transcript: Original transcribed text
        timestamp: Timestamp in milliseconds
        duration: Audio duration in seconds
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Generate S3 key
        s3_key = f"sessions/{session_id}/translated/{target_language}/{timestamp}.mp3"
        
        # Store in S3
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=audio_bytes,
            ContentType='audio/mpeg',
            Metadata={
                'sessionId': session_id,
                'targetLanguage': target_language,
                'transcript': transcript[:1000],  # Limit metadata size
                'timestamp': str(timestamp),
                'duration': str(duration),
            },
            # Tag for lifecycle policy
            Tagging=f'AutoDelete=1day&SessionId={session_id}'
        )
        
        logger.info(
            f"[AUDIO_DELIVERY] Stored TTS audio in S3",
            extra={
                'session_id': session_id,
                'target_language': target_language,
                's3_key': s3_key,
                'size_bytes': len(audio_bytes),
                'duration_seconds': duration
            }
        )
        
        # Generate presigned URL
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': S3_BUCKET_NAME,
                'Key': s3_key
            },
            ExpiresIn=PRESIGNED_URL_EXPIRATION
        )
        
        # Send notification to listeners (language-specific)
        success = await notify_listeners_for_language(
            session_id=session_id,
            target_language=target_language,
            message={
                'type': 'translatedAudio',
                'sessionId': session_id,
                'targetLanguage': target_language,
                'url': presigned_url,
                'timestamp': timestamp,
                'duration': duration,
                'transcript': transcript,
            }
        )
        
        if success:
            logger.info(
                f"[AUDIO_DELIVERY] Notified listeners for {target_language}",
                extra={
                    'session_id': session_id,
                    'target_language': target_language
                }
            )
        
        return success
        
    except ClientError as e:
        logger.error(
            f"[AUDIO_DELIVERY] S3 error: {str(e)}",
            extra={
                'session_id': session_id,
                'target_language': target_language,
                'error_code': e.response.get('Error', {}).get('Code', 'Unknown')
            },
            exc_info=True
        )
        return False
    except Exception as e:
        logger.error(
            f"[AUDIO_DELIVERY] Error delivering audio: {str(e)}",
            extra={
                'session_id': session_id,
                'target_language': target_language
            },
            exc_info=True
        )
        return False


async def notify_listeners_for_language(
    session_id: str,
    target_language: str,
    message: dict
) -> bool:
    """
    Send WebSocket notification to listeners of specific language.
    
    Args:
        session_id: Session identifier
        target_language: Target language code
        message: Notification message
        
    Returns:
        True if at least one listener notified successfully
    """
    try:
        # Get connections for this session and language
        # Query DynamoDB GSI: SessionLanguageIndex
        connections_table = dynamodb.Table(os.environ.get('CONNECTIONS_TABLE_NAME'))
        
        response = connections_table.query(
            IndexName='SessionLanguageIndex',
            KeyConditionExpression='sessionId = :sid AND targetLanguage = :lang',
            ExpressionAttributeValues={
                ':sid': session_id,
                ':lang': target_language
            }
        )
        
        connections = response.get('Items', [])
        
        if not connections:
            logger.warning(
                f"No listeners found for {target_language} in session {session_id}",
                extra={
                    'session_id': session_id,
                    'target_language': target_language
                }
            )
            return False
        
        # Send to each connection
        success_count = 0
        message_data = json.dumps(message).encode('utf-8')
        
        for connection in connections:
            connection_id = connection.get('connectionId')
            
            try:
                if apigw_management_client:
                    apigw_management_client.post_to_connection(
                        ConnectionId=connection_id,
                        Data=message_data
                    )
                    success_count += 1
                    
            except apigw_management_client.exceptions.GoneException:
                # Connection closed, will be cleaned up by disconnect_handler
                logger.info(f"Connection gone: {connection_id}")
            except Exception as send_error:
                logger.error(
                    f"Error sending to connection {connection_id}: {str(send_error)}"
                )
        
        logger.info(
            f"[AUDIO_DELIVERY] Notified {success_count}/{len(connections)} listeners",
            extra={
                'session_id': session_id,
                'target_language': target_language,
                'success_count': success_count,
                'total_count': len(connections)
            }
        )
        
        return success_count > 0
        
    except Exception as e:
        logger.error(
            f"Error notifying listeners: {str(e)}",
            extra={
                'session_id': session_id,
                'target_language': target_language
            },
            exc_info=True
        )
        return False
```

---

## Step 2: Create S3 Bucket via CDK

**File:** `audio-transcription/infrastructure/stacks/audio_stack.py`

Add S3 bucket for translated audio:

```python
from aws_cdk import (
    aws_s3 as s3,
    RemovalPolicy,
    Duration,
)

# ========================================
# S3 Bucket for Translated Audio
# ========================================

translated_audio_bucket = s3.Bucket(
    self,
    'TranslatedAudioBucket',
    bucket_name=f'translation-audio-{config["stage"]}',
    # Auto-delete objects after 24 hours
    lifecycle_rules=[
        s3.LifecycleRule(
            id='DeleteOldAudio',
            expiration=Duration.days(1),
            abort_incomplete_multipart_upload_after=Duration.days(1),
        )
    ],
    # CORS for listener access
    cors=[
        s3.CorsRule(
            allowed_methods=[s3.HttpMethods.GET],
            allowed_origins=['*'],  # TODO: Restrict to your domains
            allowed_headers=['*'],
            max_age=3600,
        )
    ],
    # Encryption
    encryption=s3.BucketEncryption.S3_MANAGED,
    # Public access blocked (presigned URLs only)
    block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
    # Remove bucket on stack deletion (dev only)
    removal_policy=RemovalPolicy.DESTROY if config['stage'] == 'dev' else RemovalPolicy.RETAIN,
    auto_delete_objects=config['stage'] == 'dev',
)

# Grant audio_processor write access
translated_audio_bucket.grant_put(audio_processor)
translated_audio_bucket.grant_read(audio_processor)  # For presigned URLs

# Add environment variable
audio_processor.add_environment(
    'S3_BUCKET_NAME',
    translated_audio_bucket.bucket_name
)
```

---

## Step 3: Create S3AudioPlayer Service (NEW)

**File:** `frontend-client-apps/listener-app/src/services/S3AudioPlayer.ts`

```typescript
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
  private currentSequence: number = 0;
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
      this.currentSequence = chunk.sequenceNumber;

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
  private async downloadAudio(url: string, retries: number = 3): Promise<Blob | null> {
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
    
    return null;
  }

  /**
   * Prefetch next chunks to cache
   */
  private async prefetchNextChunks(): Promise<void> {
    // Prefetch up to maxCacheSize chunks ahead
    const chunksToPrefe

= this.playQueue.slice(0, this.maxCacheSize);

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
    this.currentSequence = 0;
    
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
```

---

## Step 4: Update ListenerService (MODIFY)

**File:** `frontend-client-apps/listener-app/src/services/ListenerService.ts`

### Changes Required:

1. **Remove imports:**
```typescript
// DELETE:
import { KVSWebRTCService, AWSCredentials } from '../../../shared/services/KVSWebRTCService';
import { getKVSCredentialsProvider } from '../../../shared/services/KVSCredentialsProvider';
```

2. **Add new import:**
```typescript
// ADD:
import { S3AudioPlayer, AudioChunkMetadata } from './S3AudioPlayer';
```

3. **Update class properties:**
```typescript
// REPLACE:
private kvsService: KVSWebRTCService | null = null;
private audioElement: HTMLAudioElement | null = null;

// WITH:
private audioPlayer: S3AudioPlayer | null = null;
```

4. **Remove from config interface:**
```typescript
// DELETE from ListenerServiceConfig:
kvsChannelArn: string;
kvsSignalingEndpoint: string;
region: string;
identityPoolId: string;
userPoolId: string;
```

5. **Replace startListening() method:**
```typescript
/**
 * Start listening for translated audio
 */
async startListening(): Promise<void> {
  try {
    console.log('[ListenerService] Starting S3 audio player...');
    
    // Create S3 audio player
    this.audioPlayer = new S3AudioPlayer({
      targetLanguage: this.config.targetLanguage,
      onPlaybackStart: () => {
        console.log('[ListenerService] Playback started');
      },
      onPlaybackEnd: () => {
        console.log('[ListenerService] Playback ended');
      },
      onBuffering: (isBuffering) => {
        // Update UI buffering indicator
        console.log(`[ListenerService] Buffering: ${isBuffering}`);
      },
      onError: (error) => {
        console.error('[ListenerService] Playback error:', error);
        ErrorHandler.handle(error, {
          component: 'ListenerService',
          operation: 'audioPlayback',
        });
      },
      onProgress: (current, total) => {
        // Update UI progress if needed
      },
    });
    
    // Apply saved volume
    const savedVolume = useListenerStore.getState().playbackVolume;
    this.audioPlayer.setVolume(savedVolume / 100);
    
    console.log('[ListenerService] Audio player ready');
    
  } catch (error) {
    console.error('[ListenerService] Failed to start listening:', error);
    const appError = ErrorHandler.handle(error as Error, {
      component: 'ListenerService',
      operation: 'startListening',
    });
    throw new Error(appError.userMessage);
  }
}
```

6. **Remove waitForSpeakerReady() and getAWSCredentials() methods entirely**

7. **Update setupEventHandlers() to handle translatedAudio:**
```typescript
/**
 * Setup WebSocket event handlers
 */
private setupEventHandlers(): void {
  // ... existing handlers ...

  // Handle translated audio notification
  this.wsClient.on('translatedAudio', (message: any) => {
    if (message.targetLanguage === this.config.targetLanguage) {
      const metadata: AudioChunkMetadata = {
        url: message.url,
        timestamp: message.timestamp,
        duration: message.duration || 2.0,
        sequenceNumber: message.sequenceNumber || message.timestamp,
        transcript: message.transcript,
      };
      
      if (this.audioPlayer) {
        this.audioPlayer.addChunk(metadata);
      }
      
      console.log(
        `[ListenerService] Received translated audio chunk: ${metadata.sequenceNumber}`
      );
    }
  });

  // ... rest of handlers ...
}
```

8. **Update control methods:**
```typescript
/**
 * Pause playback
 */
async pause(): Promise<void> {
  const startTime = Date.now();
  
  try {
    if (this.audioPlayer) {
      this.audioPlayer.pause();
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
    if (this.audioPlayer) {
      await this.audioPlayer.resume();
    }
    useListenerStore.getState().setPaused(false);
    
    this.logControlLatency('resume', startTime);
  } catch (error) {
    console.error('Failed to resume playback:', error);
    throw error;
  }
}

/**
 * Mute audio
 */
async mute(): Promise<void> {
  const startTime = Date.now();
  
  try {
    if (this.audioPlayer) {
      this.audioPlayer.mute();
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
    if (this.audioPlayer) {
      this.audioPlayer.unmute();
    }
    useListenerStore.getState().setMuted(false);
    
    this.logControlLatency('unmute', startTime);
  } catch (error) {
    console.error('Failed to unmute playback:', error);
    throw error;
  }
}

/**
 * Set playback volume (0-100)
 */
async setVolume(volume: number): Promise<void> {
  const clampedVolume = Math.max(0, Math.min(100, volume));
  
  if (this.audioPlayer) {
    this.audioPlayer.setVolume(clampedVolume / 100);
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
 * Get buffered audio duration
 */
getBufferedDuration(): number {
  return this.audioPlayer?.getBufferedDuration() || 0;
}

/**
 * Leave session
 */
leave(): void {
  // Stop audio playback
  if (this.audioPlayer) {
    this.audioPlayer.cleanup();
    this.audioPlayer = null;
  }

  // Close WebSocket
  this.wsClient.disconnect();

  // Clear session state
  useListenerStore.getState().reset();
}

/**
 * Cleanup resources
 */
cleanup(): void {
  if (this.audioPlayer) {
    this.audioPlayer.cleanup();
    this.audioPlayer = null;
  }
  
  this.wsClient.disconnect();
}
```

---

## Step 5: Update DynamoDB GSI for Language Queries

The audio_processor needs to query listeners by language efficiently.

**File:** `session-management/infrastructure/stacks/session_management_stack.py`

Verify Connections table has SessionLanguageIndex:

```python
# In connections_table definition
connections_table = dynamodb.Table(
    self,
    'ConnectionsTable',
    # ... existing config ...
    global_secondary_indexes=[
        # ... existing indexes ...
        
        # Add SessionLanguageIndex for language-specific queries
        dynamodb.GlobalSecondaryIndex(
            index_name='SessionLanguageIndex',
            partition_key=dynamodb.Attribute(
                name='sessionId',
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name='targetLanguage',
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        ),
    ],
)
```

---

## Step 6: Testing Phase 3

### Test 1: Verify S3 Bucket Exists

```bash
aws s3 ls | grep translation-audio

# Should show: translation-audio-dev

# Check bucket configuration
aws s3api get-bucket-lifecycle-configuration \
  --bucket translation-audio-dev

# Should show 24-hour expiration rule
```

### Test 2: End-to-End Test

1. **Start speaker session**
2. **Speak into microphone** (e.g., "Hello world")
3. **Join as listener** (different browser/incognito)
4. **Wait 3-4 seconds**
5. **Should hear translated audio**

### Test 3: Check S3 for Audio Files

```bash
export SESSION_ID=your-session-id

# List translated audio for session
aws s3 ls s3://translation-audio-dev/sessions/${SESSION_ID}/translated/ --recursive

# Should show files like:
# sessions/session-id/translated/es/1732614570000.mp3
# sessions/session-id/translated/fr/1732614572000.mp3
```

### Test 4: Monitor Audio Processor Logs

```bash
./scripts/tail-lambda-logs.sh audio-processor-dev

# Look for:
# "[AUDIO_DELIVERY] Stored TTS audio in S3"
# "[AUDIO_DELIVERY] Notified X listeners for es"
# "Generated presigned URL for s3://..."
```

### Test 5: Check Listener Browser Console

```javascript
// Should see:
// "[S3AudioPlayer] Added chunk 1, queue size: 1"
// "[S3AudioPlayer] Playing chunk 1"
// "[S3AudioPlayer] Downloaded 32547 bytes from S3"
// "[S3AudioPlayer] Prefetched chunk 2"
```

### Test 6: Verify WebSocket Notifications

```bash
# In listener browser console, monitor WebSocket messages
# Should receive:
{
  "type": "translatedAudio",
  "targetLanguage": "es",
  "url": "https://s3.amazonaws.com/...",
  "duration": 2.0,
  "transcript": "Hola mundo"
}
```

---

## Common Issues & Solutions

### Issue 1: No Audio Received

**Symptoms:**
- Listener connected but no audio plays
- No S3 files in bucket
- No WebSocket notifications

**Diagnosis:**
```bash
# Check if audio_processor is being invoked
./scripts/tail-lambda-logs.sh audio-processor-dev

# Check if Transcribe is working
aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor-dev \
  --filter-pattern "Transcribe" \
  --since 10m
```

**Solution:**
- Verify kvs_stream_consumer is forwarding audio
- Check audio_processor has S3 bucket permissions
- Verify Transcribe/Translate/TTS are configured

### Issue 2: S3 Download Fails

**Error:** "Failed to fetch" or "403 Forbidden"

**Solution:**
- Verify presigned URL not expired (10 minutes)
- Check S3 CORS configuration allows GET from listener origin
- Verify bucket exists and has correct permissions

**
