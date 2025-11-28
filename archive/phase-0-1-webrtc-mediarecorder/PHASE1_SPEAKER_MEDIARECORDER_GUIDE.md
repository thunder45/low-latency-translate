# Phase 1: Speaker MediaRecorder Implementation Guide

## Overview
Replace WebRTC peer-to-peer with MediaRecorder → WebSocket → Backend streaming.

**Duration:** 4-6 hours  
**Prerequisites:** Phase 0 complete (cleanup done)  
**Goal:** Speaker captures audio and sends chunks to backend via WebSocket

---

## Architecture Changes

### Before (WebRTC):
```
Speaker → KVSWebRTCService → KVS Signaling Channel → Listener
         (peer-to-peer, no backend processing)
```

### After (Traditional Stream):
```
Speaker → AudioStreamService → WebSocket → Backend
         (MediaRecorder)      (250ms chunks)
```

---

## Step 1: Create AudioStreamService (NEW FILE)

**File:** `frontend-client-apps/speaker-app/src/services/AudioStreamService.ts`

```typescript
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
```

---

## Step 2: Update SpeakerService (MODIFY)

**File:** `frontend-client-apps/speaker-app/src/services/SpeakerService.ts`

### Changes Required:

1. **Remove imports:**
```typescript
// DELETE THESE:
import { KVSWebRTCService, AWSCredentials } from '../../../shared/services/KVSWebRTCService';
import { getKVSCredentialsProvider } from '../../../shared/services/KVSCredentialsProvider';
```

2. **Add new import:**
```typescript
// ADD THIS:
import { AudioStreamService } from './AudioStreamService';
```

3. **Update class properties:**
```typescript
// REPLACE:
private kvsService: KVSWebRTCService | null = null;

// WITH:
private audioStreamService: AudioStreamService | null = null;
```

4. **Remove from config interface:**
```typescript
// DELETE THESE from SpeakerServiceConfig:
kvsChannelArn: string;
kvsSignalingEndpoint: string;
region: string;
identityPoolId: string;
userPoolId: string;
```

5. **Replace startBroadcast() method:**
```typescript
/**
 * Start audio broadcasting via MediaRecorder
 */
async startBroadcast(): Promise<void> {
  try {
    console.log('[SpeakerService] Starting audio streaming...');
    
    // Create AudioStreamService
    this.audioStreamService = new AudioStreamService({
      sessionId: useSpeakerStore.getState().sessionId,
      websocket: this.wsClient.getWebSocket(), // Add getter to WebSocketClient
      chunkDuration: 250, // 250ms chunks
      onChunkSent: (size, index) => {
        // Update UI with streaming stats
        if (index % 40 === 0) { // Every 10 seconds
          console.log(`[SpeakerService] Streaming: ${index} chunks sent`);
        }
      },
      onError: (error) => {
        console.error('[SpeakerService] Audio streaming error:', error);
        ErrorHandler.handle(error, {
          component: 'SpeakerService',
          operation: 'audioStream',
        });
      },
      onStreamStart: () => {
        useSpeakerStore.getState().setTransmitting(true);
        console.log('[SpeakerService] Audio streaming started');
      },
      onStreamStop: () => {
        useSpeakerStore.getState().setTransmitting(false);
        console.log('[SpeakerService] Audio streaming stopped');
      },
    });
    
    // Start capturing and streaming
    await this.audioStreamService.start();
    
    // Start session status polling (WebSocket for metadata)
    this.startStatusPolling();
    
    useSpeakerStore.getState().setConnected(true);
    useSpeakerStore.getState().setTransmitting(true);
    
  } catch (error) {
    console.error('[SpeakerService] Failed to start broadcast:', error);
    const appError = ErrorHandler.handle(error as Error, {
      component: 'SpeakerService',
      operation: 'startBroadcast',
    });
    throw new Error(appError.userMessage);
  }
}
```

6. **Remove getAWSCredentials() method entirely**

7. **Update pause/resume/mute methods:**
```typescript
/**
 * Pause broadcast
 */
async pause(): Promise<void> {
  const startTime = Date.now();
  
  try {
    // Pause audio streaming (stop sending chunks)
    if (this.audioStreamService) {
      this.audioStreamService.pause();
    }
    
    useSpeakerStore.getState().setPaused(true);
    useSpeakerStore.getState().setTransmitting(false);
    
    // Send control message via WebSocket
    if (this.wsClient.isConnected()) {
      this.wsClient.send({
        action: 'pauseBroadcast',
        timestamp: Date.now(),
      });
    }
    
    this.logControlLatency('pause', startTime);
    controlsMonitoring.logControlAction('pause', true, {
      userType: 'speaker',
      sessionId: useSpeakerStore.getState().sessionId,
    });
  } catch (error) {
    console.error('Failed to pause broadcast:', error);
    controlsMonitoring.logControlAction('pause', false, {
      userType: 'speaker',
      error: (error as Error).message,
    });
    throw error;
  }
}

/**
 * Resume broadcast
 */
async resume(): Promise<void> {
  const startTime = Date.now();
  
  try {
    // Resume audio streaming
    if (this.audioStreamService) {
      this.audioStreamService.resume();
    }
    
    useSpeakerStore.getState().setPaused(false);
    useSpeakerStore.getState().setTransmitting(true);
    
    // Send control message via WebSocket
    if (this.wsClient.isConnected()) {
      this.wsClient.send({
        action: 'resumeBroadcast',
        timestamp: Date.now(),
      });
    }
    
    this.logControlLatency('resume', startTime);
    controlsMonitoring.logControlAction('resume', true, {
      userType: 'speaker',
      sessionId: useSpeakerStore.getState().sessionId,
    });
  } catch (error) {
    console.error('Failed to resume broadcast:', error);
    controlsMonitoring.logControlAction('resume', false, {
      userType: 'speaker',
      error: (error as Error).message,
    });
    throw error;
  }
}

/**
 * Mute audio (stop streaming entirely)
 */
async mute(): Promise<void> {
  const startTime = Date.now();
  
  try {
    // Pause audio streaming
    if (this.audioStreamService) {
      this.audioStreamService.pause();
    }
    
    useSpeakerStore.getState().setMuted(true);
    useSpeakerStore.getState().setTransmitting(false);
    
    // Send control message via WebSocket
    if (this.wsClient.isConnected()) {
      this.wsClient.send({
        action: 'muteBroadcast',
        timestamp: Date.now(),
      });
    }
    
    this.logControlLatency('mute', startTime);
    controlsMonitoring.logControlAction('mute', true, {
      userType: 'speaker',
      sessionId: useSpeakerStore.getState().sessionId,
    });
  } catch (error) {
    console.error('Failed to mute broadcast:', error);
    controlsMonitoring.logControlAction('mute', false, {
      userType: 'speaker',
      error: (error as Error).message,
    });
    throw error;
  }
}

/**
 * Unmute audio (resume streaming)
 */
async unmute(): Promise<void> {
  const startTime = Date.now();
  
  try {
    // Resume audio streaming
    if (this.audioStreamService) {
      this.audioStreamService.resume();
    }
    
    useSpeakerStore.getState().setMuted(false);
    useSpeakerStore.getState().setTransmitting(true);
    
    // Send control message via WebSocket
    if (this.wsClient.isConnected()) {
      this.wsClient.send({
        action: 'unmuteBroadcast',
        timestamp: Date.now(),
      });
    }
    
    this.logControlLatency('unmute', startTime);
    controlsMonitoring.logControlAction('unmute', true, {
      userType: 'speaker',
      sessionId: useSpeakerStore.getState().sessionId,
    });
  } catch (error) {
    console.error('Failed to unmute broadcast:', error);
    controlsMonitoring.logControlAction('unmute', false, {
      userType: 'speaker',
      error: (error as Error).message,
    });
    throw error;
  }
}
```

8. **Update getInputLevel() methods:**
```typescript
/**
 * Get current audio input level
 */
getInputLevel(): number {
  if (this.audioStreamService) {
    return this.audioStreamService.getInputLevel();
  }
  return 0;
}
```

9. **Update cleanup() method:**
```typescript
/**
 * Cleanup resources
 */
cleanup(): void {
  this.stopStatusPolling();
  
  if (this.audioStreamService) {
    this.audioStreamService.cleanup();
    this.audioStreamService = null;
  }
  
  this.wsClient.disconnect();
}
```

10. **Update endSession() method:**
```typescript
/**
 * End session
 */
async endSession(): Promise<void> {
  try {
    // Send end session via WebSocket
    await this.retryHandler.execute(async () => {
      if (this.wsClient.isConnected()) {
        this.wsClient.send({
          action: 'endSession',
          sessionId: useSpeakerStore.getState().sessionId,
          reason: 'Speaker ended session',
        });
      }
    });

    // Cleanup audio streaming
    if (this.audioStreamService) {
      this.audioStreamService.cleanup();
      this.audioStreamService = null;
    }

    // Stop status polling
    this.stopStatusPolling();

    // Close WebSocket
    setTimeout(() => {
      this.wsClient.disconnect();
    }, 1000);

    // Clear session state
    useSpeakerStore.getState().reset();
  } catch (error) {
    const appError = ErrorHandler.handle(error as Error, {
      component: 'SpeakerService',
      operation: 'endSession',
    });
    throw new Error(appError.userMessage);
  }
}
```

---

## Step 3: Update WebSocketClient (Add Getter)

**File:** `frontend-client-apps/shared/websocket/WebSocketClient.ts`

Add this method to WebSocketClient class:

```typescript
/**
 * Get the underlying WebSocket instance
 * Used by AudioStreamService to send audio chunks
 */
getWebSocket(): WebSocket {
  if (!this.ws) {
    throw new Error('WebSocket not connected');
  }
  return this.ws;
}
```

---

## Step 4: Add WebSocket Route for audioChunk

**File:** `session-management/lambda/connection_handler/handler.py`

Add this to the route handling in `lambda_handler()`:

```python
# In lambda_handler, after handling 'joinSession':

elif action == 'audioChunk':
    return handle_audio_chunk(event, connection_id, body, ip_address)
```

Add this function:

```python
def handle_audio_chunk(event, connection_id, body, ip_address):
    """
    Handle audio chunk from speaker - forward to kvs_stream_writer.
    
    Note: This is a temporary routing handler. In production, consider:
    - Direct Lambda invocation from WebSocket integration
    - SQS queue for buffering
    - Dedicated audio ingestion Lambda
    
    Args:
        event: Lambda event
        connection_id: WebSocket connection ID
        body: Message body with audio data
        ip_address: Client IP
        
    Returns:
        Success response
    """
    try:
        session_id = body.get('sessionId', '')
        audio_data_base64 = body.get('audioData', '')
        chunk_index = body.get('chunkIndex', 0)
        
        if not session_id or not audio_data_base64:
            logger.warning(
                message="Invalid audio chunk: missing sessionId or audioData",
                correlation_id=connection_id,
                operation='handle_audio_chunk'
            )
            return success_response(status_code=200, body={})
        
        # Verify connection is speaker role
        connection = connections_repo.get_connection(connection_id)
        if not connection or connection.get('role') != 'speaker':
            logger.warning(
                message="Audio chunk from non-speaker connection",
                correlation_id=connection_id,
                operation='handle_audio_chunk',
                role=connection.get('role') if connection else 'unknown'
            )
            return success_response(status_code=200, body={})
        
        # Forward to kvs_stream_writer Lambda
        kvs_writer_function = os.environ.get('KVS_STREAM_WRITER_FUNCTION', 'kvs-stream-writer-dev')
        
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(
            FunctionName=kvs_writer_function,
            InvocationType='Event',  # Async
            Payload=json.dumps({
                'action': 'writeToStream',
                'sessionId': session_id,
                'audioData': audio_data_base64,
                'timestamp': body.get('timestamp', int(time.time() * 1000)),
                'format': body.get('format', 'webm-opus'),
                'chunkIndex': chunk_index,
            })
        )
        
        # Log every 40th chunk to avoid log spam
        if chunk_index % 40 == 0:
            logger.info(
                message=f"Forwarded audio chunk {chunk_index} to kvs_stream_writer",
                correlation_id=f"{session_id}-{connection_id}",
                operation='handle_audio_chunk',
                sessionId=session_id,
                chunkIndex=chunk_index
            )
        
        return success_response(status_code=200, body={})
        
    except Exception as e:
        logger.error(
            message=f"Error handling audio chunk: {str(e)}",
            correlation_id=connection_id,
            operation='handle_audio_chunk',
            exc_info=True
        )
        # Return success to avoid WebSocket disconnect
        return success_response(status_code=200, body={})
```

---

## Step 5: Testing Phase 1

### Test 1: Microphone Access
```javascript
// In browser console
await AudioStreamService.checkMicrophoneAccess()
// Should return: true

await AudioStreamService.getAudioInputDevices()
// Should list available microphones
```

### Test 2: Audio Capture
```javascript
// In speaker app, after creating session
// Check browser console for:
// "[AudioStreamService] Microphone access granted"
// "[AudioStreamService] Audio streaming started"
// "[AudioStreamService] Sent chunk 10, size: 4523 bytes..."
```

### Test 3: Backend Receives Chunks
```bash
# Tail connection_handler logs
./scripts/tail-lambda-logs.sh connection-handler-dev

# Look for:
# "Forwarded audio chunk 0 to kvs_stream_writer"
# "Forwarded audio chunk 40 to kvs_stream_writer"
```

### Test 4: Verify Chunk Size
```javascript
// In browser console, speaker app
// Should see approximately:
// - Chunk every 250ms
// - Size: 4000-5000 bytes per chunk
// - Format: webm-opus
```

---

## Rollback Procedure

If Phase 1 fails:

1. **Restore WebRTC code:**
```bash
git checkout HEAD -- frontend-client-apps/speaker-app/src/services/SpeakerService.ts
```

2. **Remove AudioStreamService:**
```bash
rm frontend-client-apps/speaker-app/src/services/AudioStreamService.ts
```

3. **Revert connection_handler:**
```bash
git checkout HEAD -- session-management/lambda/connection_handler/handler.py
cd session-management && make deploy
```

---

## Common Issues & Solutions

### Issue 1: Microphone Access Denied

**Error:** "NotAllowedError: Permission denied"

**Solution:**
1. Check browser permissions (chrome://settings/content/microphone)
2. Ensure HTTPS connection (required for getUserMedia)
3. Try different browser (Chrome, Firefox, Safari)

### Issue 2: MediaRecorder Not Supported

**Error:** "MediaRecorder is not defined"

**Solution:**
- MediaRecorder is supported in all modern browsers
- Check browser version (Chrome 47+, Firefox 25+, Safari 14+)
- Fallback: Use Web Audio API recording (more complex)

### Issue 3: WebSocket Payload Too Large

**Error:** "WebSocket message size exceeds limit"

**Solution:**
- Reduce chunk duration: 250ms → 200ms
- Reduce bitrate: 16kbps → 12kbps
- Typical 250ms chunk at 16kbps: ~4-5 KB (well under 32KB limit)

### Issue 4: Audio Chunks Not Reaching Backend

**Diagnosis:**
```javascript
// Check WebSocket state
console.log('WebSocket ready state:', wsClient.isConnected());

// Check if chunks are being created
// Should see console logs every ~250ms
```

**Solution:**
- Verify WebSocket connection established
- Check connection_handler Lambda logs
- Verify audioChunk route exists in API Gateway

---

## Success Criteria

✅ **Phase 1 Complete When:**
1. MediaRecorder captures audio successfully
2. Chunks sent via WebSocket every 250ms
3. connection_handler Lambda receives chunks
4. No errors in browser console
5. No errors in Lambda logs

---

## Next Phase Preview

After Phase 1 completes, Phase 2 will:
- Create kvs_stream_writer Lambda
- Convert WebM → PCM using ffmpeg
- Write to KVS Stream
- Verify fragments exist in KVS

---

## Checkpoint: What to Verify

Before moving to Phase 2, confirm:
- [ ] Speaker app uses AudioStreamService (not KVSWebRTCService)
- [ ] Audio chunks appear in browser console
- [ ] WebSocket sends audioChunk messages
- [ ] Backend logs show "Forwarded audio chunk..."
- [ ] No microphone access errors
- [ ] No WebSocket errors

**Create:** `CHECKPOINT_PHASE1_COMPLETE.md` documenting results

---

## Estimated Timeline

- **AudioStreamService creation**: 2 hours
- **SpeakerService refactoring**: 1.5 hours
- **WebSocket route addition**: 0.5 hour
- **Testing and debugging**: 1-2 hours
- **Total**: 4-6 hours

---

## Files Modified Summary

### New Files:
- `frontend-client-apps/speaker-app/src/services/AudioStreamService.ts`

### Modified Files:
- `frontend-client-apps/speaker-app/src/services/SpeakerService.ts`
- `frontend-client-apps/shared/websocket/WebSocketClient.ts`
- `session-management/lambda/connection_handler/handler.py`

### Deployment Required:
```bash
# Frontend
cd frontend-client-apps/speaker-app
npm run build
# Deploy to hosting

# Backend
cd session-management
make deploy
```

---

## Reference: MediaRecorder API

**Browser Compatibility:**
- Chrome 47+ ✅
- Firefox 25+ ✅
- Safari 14+ ✅
- Edge 79+ ✅

**Key Methods:**
- `start(timeslice)` - Start recording with chunk interval
- `stop()` - Stop recording
- `pause()` - Pause recording
- `resume()` - Resume recording

**Events:**
- `ondataavailable` - Fired when chunk ready
- `onstop` - Fired when recording stops
- `onerror` - Fired on error

**Best Practices:**
- Always stop tracks when done: `stream.getTracks().forEach(t => t.stop())`
- Handle permissions errors gracefully
- Use small time slices for streaming (250-500ms)
- Test in multiple browsers
