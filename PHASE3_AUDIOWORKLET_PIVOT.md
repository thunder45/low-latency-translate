# Phase 3 Pivot: WebM → AudioWorklet + Raw PCM

## Problem with Current Approach

**MediaRecorder Issue:**
- Only first chunk has EBML header
- Subsequent chunks are just media clusters (no header)
- Cannot be processed individually by FFmpeg
- Requires complex header stitching or full stream reconstruction

**Current Architecture Complexity:**
```
Browser (MediaRecorder) → WebM chunks → S3 → Consumer aggregates → 
Concatenate → FFmpeg → PCM → Transcribe
```

**Problems:**
1. Heavy backend processing (FFmpeg in Lambda)
2. High latency (wait for aggregation + conversion)
3. Complex error handling (header stitching)
4. Higher compute costs

---

## Proposed Solution: AudioWorklet + Raw PCM

### New Architecture
```
Browser (AudioWorklet) → Raw PCM → WebSocket → Lambda → 
Direct to Transcribe (no conversion needed)
```

**Benefits:**
- ✅ **Zero container overhead** - No WebM parsing
- ✅ **Lowest latency** - Send audio immediately (every 3ms)
- ✅ **Cheaper compute** - No FFmpeg needed
- ✅ **Simpler code** - Direct PCM handling
- ✅ **Real-time ready** - Perfect for streaming

---

## Implementation Plan

### Part 1: Frontend - AudioWorklet Processor (NEW)

**File:** `frontend-client-apps/speaker-app/src/services/AudioWorkletProcessor.ts`

```typescript
/**
 * AudioWorklet processor for direct PCM capture
 * Runs in audio worklet thread for lowest latency
 */

// audio-worklet-processor.js (separate file for worklet)
class PCMAudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bufferSize = 4096; // ~85ms at 48kHz
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
  }
  
  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    
    const channel = input[0]; // Mono
    
    for (let i = 0; i < channel.length; i++) {
      this.buffer[this.bufferIndex++] = channel[i];
      
      if (this.bufferIndex >= this.bufferSize) {
        // Convert Float32 to Int16 PCM
        const pcmData = new Int16Array(this.bufferSize);
        for (let j = 0; j < this.bufferSize; j++) {
          // Clamp to [-1, 1] and convert to 16-bit
          const s = Math.max(-1, Math.min(1, this.buffer[j]));
          pcmData[j] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        
        // Send to main thread
        this.port.postMessage({
          type: 'audio',
          data: pcmData.buffer
        }, [pcmData.buffer]);
        
        // Reset buffer
        this.bufferIndex = 0;
      }
    }
    
    return true;
  }
}

registerProcessor('pcm-audio-processor', PCMAudioProcessor);
```

**File:** `frontend-client-apps/speaker-app/src/services/AudioWorkletService.ts`

```typescript
/**
 * AudioWorklet service for low-latency PCM capture
 * Replaces MediaRecorder-based AudioStreamService
 */

export class AudioWorkletService {
  private audioContext: AudioContext | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private mediaStream: MediaStream | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private isCapturing: boolean = false;
  private onAudioDataCallback: ((pcmData: ArrayBuffer) => void) | null = null;
  
  /**
   * Initialize AudioWorklet
   */
  async initialize(onAudioData: (pcmData: ArrayBuffer) => void): Promise<void> {
    this.onAudioDataCallback = onAudioData;
    
    // Create audio context (16kHz for Transcribe)
    this.audioContext = new AudioContext({ sampleRate: 16000 });
    
    // Load worklet module
    await this.audioContext.audioWorklet.addModule('/audio-worklet-processor.js');
    
    console.log('[AudioWorklet] Initialized, sample rate:', this.audioContext.sampleRate);
  }
  
  /**
   * Start capturing audio
   */
  async startCapture(): Promise<void> {
    if (!this.audioContext) {
      throw new Error('AudioWorklet not initialized');
    }
    
    // Get microphone access
    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: 16000,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      }
    });
    
    // Create source from microphone
    this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream);
    
    // Create worklet node
    this.workletNode = new AudioWorkletNode(
      this.audioContext,
      'pcm-audio-processor'
    );
    
    // Listen for PCM data from worklet
    this.workletNode.port.onmessage = (event) => {
      if (event.data.type === 'audio' && this.onAudioDataCallback) {
        this.onAudioDataCallback(event.data.data);
      }
    };
    
    // Connect: microphone → worklet → destination (for monitoring)
    this.sourceNode.connect(this.workletNode);
    this.workletNode.connect(this.audioContext.destination);
    
    this.isCapturing = true;
    console.log('[AudioWorklet] Started capturing');
  }
  
  /**
   * Stop capturing
   */
  stopCapture(): void {
    if (this.sourceNode) {
      this.sourceNode.disconnect();
    }
    
    if (this.workletNode) {
      this.workletNode.disconnect();
      this.workletNode.port.close();
    }
    
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(track => track.stop());
    }
    
    this.isCapturing = false;
    console.log('[AudioWorklet] Stopped capturing');
  }
  
  /**
   * Cleanup
   */
  cleanup(): void {
    this.stopCapture();
    
    if (this.audioContext) {
      this.audioContext.close();
    }
  }
}
```

### Part 2: Backend - Direct PCM Handling

**Update:** `session-management/lambda/kvs_stream_writer/handler.py`

```python
# Instead of writing WebM to S3, forward PCM directly to audio_processor
# OR write PCM to S3 if batching is still needed

async def handle_audio_chunk(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle raw PCM audio chunk from AudioWorklet."""
    
    # Extract PCM data (now base64-encoded Int16 array)
    pcm_base64 = event['audioData']
    pcm_bytes = base64.b64decode(pcm_base64)
    
    session_id = event['sessionId']
    timestamp = event['timestamp']
    
    # Option 1: Forward directly to audio_processor (lowest latency)
    # No S3 storage needed for real-time streaming
    
    # Option 2: Store in S3 for batching (if aggregation still needed)
    s3_key = f"sessions/{session_id}/pcm/{timestamp}.pcm"
    s3_client.put_object(
        Bucket=AUDIO_BUCKET_NAME,
        Key=s3_key,
        Body=pcm_bytes,
        ContentType='audio/pcm'
    )
    
    return {'statusCode': 200}
```

### Part 3: Simplify or Remove s3_audio_consumer

**Option A: Remove entirely**
- If using direct forwarding, no consumer needed
- PCM goes straight from WebSocket → audio_processor

**Option B: Simplify for PCM**
```python
# No FFmpeg needed!
# Just aggregate PCM chunks and forward

def process_session_chunks(session_id: str, bucket: str) -> None:
    # List PCM chunks
    chunks = list_pcm_chunks(bucket, f"sessions/{session_id}/pcm/")
    
    # Concatenate PCM (simple binary append)
    pcm_data = b''.join([download_chunk(c) for c in chunks])
    
    # Forward to audio_processor
    invoke_audio_processor(
        session_id=session_id,
        pcm_data=pcm_data,
        sample_rate=16000,
        # ...
    )
```

### Part 4: Update audio_processor

**Simplification:**
- Remove `transcribe_pcm_audio()` with S3 temp storage
- Use Transcribe Streaming API directly
- PCM is already in correct format

```python
# Direct streaming to Transcribe
async def transcribe_pcm_stream(
    pcm_bytes: bytes,
    language_code: str,
    sample_rate: int
) -> str:
    """Stream PCM directly to Transcribe."""
    
    transcribe = TranscribeStreamingClient(region='us-east-1')
    
    stream = await transcribe.start_stream_transcription(
        language_code=language_code,
        media_sample_rate_hz=sample_rate,
        media_encoding='pcm'
    )
    
    # Send audio
    await stream.input_stream.send_audio_event(audio_chunk=pcm_bytes)
    await stream.input_stream.end_stream()
    
    # Get result
    async for event in stream.output_stream:
        if event.transcript_event:
            return event.transcript_event.transcript.results[0].alternatives[0].transcript
    
    return ""
```

---

## Migration Path

### Phase 1: Implement AudioWorklet (1-2 hours)
1. Create audio-worklet-processor.js
2. Create AudioWorkletService.ts
3. Test PCM capture in browser console
4. Verify Int16 format and sample rate

### Phase 2: Update Backend for PCM (1 hour)
1. Update kvs_stream_writer to accept PCM
2. Decide: direct forward or S3 batching?
3. Update s3_audio_consumer for PCM (no FFmpeg)
4. Update audio_processor to use Transcribe Streaming

### Phase 3: Deploy and Test (1 hour)
1. Deploy changes
2. Test PCM flow end-to-end
3. Measure latency (should be <5s)
4. Remove FFmpeg layer (no longer needed)

### Phase 4: Cleanup (30 min)
1. Archive old WebM code
2. Update documentation
3. Remove FFmpeg-related code

---

## Comparison: Current vs Proposed

| Aspect | Current (WebM) | Proposed (PCM) |
|--------|----------------|----------------|
| **Browser** | MediaRecorder (WebM/Opus) | AudioWorklet (Raw PCM) |
| **Chunk size** | ~550 bytes (250ms) | ~8KB (85ms @ 48kHz) or ~2.7KB (85ms @ 16kHz) |
| **Backend storage** | WebM chunks in S3 | PCM chunks in S3 (optional) |
| **Conversion** | FFmpeg WebM→PCM (2s) | None needed (0s) |
| **Transcribe** | StartTranscriptionJob (polling) | Streaming API (real-time) |
| **Total latency** | ~10-15s | ~3-5s |
| **Compute cost** | High (FFmpeg) | Low (no conversion) |
| **Code complexity** | High | Low |

---

## Decision Point

**Immediate Fix (keep WebM):**
- Pro: Minimal code changes
- Pro: Works with existing infrastructure
- Con: Still complex (header stitching)
- Con: Still high latency

**Pivot to AudioWorklet:**
- Pro: Correct architecture for low-latency
- Pro: Simpler backend code
- Pro: Lower costs
- Pro: Better latency
- Con: Requires frontend rewrite (~2 hours)
- Con: Larger payload size (PCM is uncompressed)

---

## Recommendation

**Pivot to AudioWorklet** because:
1. You named the project "low-latency-translate"
2. Current approach will never achieve <5s latency
3. WebM header stitching is complex and error-prone
4. AudioWorklet is the industry standard for real-time audio
5. Eliminates entire layer of complexity (FFmpeg)

**Bandwidth consideration:**
- PCM @ 16kHz mono: ~32KB/s
- WebM/Opus @ 16kbps: ~2KB/s
- **Trade-off:** 16x bandwidth for 3x lower latency

If bandwidth is critical, use AudioWorklet but add browser-side Opus encoding (using opus-recorder WASM library) - still simpler than WebM container handling.

---

## Next Steps

Do you want me to:
1. **Option A:** Implement AudioWorklet + raw PCM (recommended, 3-4 hours)
2. **Option B:** Fix current WebM approach with header stitching (2 hours, but still complex)
3. **Option C:** Hybrid - AudioWorklet + Opus encoder (best of both, 4-5 hours)

Let me know which direction you prefer!
