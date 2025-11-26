# WebRTC Audio Verification Guide

## Critical Architectural Understanding

### KVS Signaling Channel vs KVS Stream

Your implementation uses **KVS WebRTC Signaling Channels**, NOT traditional KVS Streams:

```
❌ WRONG ASSUMPTION (Traditional KVS):
Speaker → PutMedia API → KVS Stream → GetMedia API → Consumer
                         ↓
                    Fragments stored
                    (can query with list-fragments)

✅ ACTUAL ARCHITECTURE (KVS WebRTC):
Speaker ↔ KVS Signaling Channel ↔ Listener
         (WebRTC peer-to-peer)
         NO persistent fragments
         NO list-fragments API
```

### Key Differences

| Feature | Traditional KVS Stream | KVS WebRTC (Your System) |
|---------|----------------------|--------------------------|
| Purpose | Store video/audio | Real-time communication |
| API | PutMedia/GetMedia | WebRTC signaling |
| Storage | Fragments in stream | No persistent storage |
| Verification | list-fragments | WebRTC stats API |
| Use Case | Recording/playback | Live streaming |

## Why This Matters

**The script failed because:**
- It tried to check for "KVS Stream" with `describe-stream`
- Your system uses "KVS Signaling Channel" with `describe-signaling-channel`
- Traditional `list-fragments` doesn't work with WebRTC architecture

**Your audio flow is actually:**
```
Speaker Microphone
    ↓
getUserMedia() in browser
    ↓
WebRTC PeerConnection
    ↓
KVS Signaling Channel (ICE/SDP negotiation)
    ↓
WebRTC Media Path (direct peer connection)
    ↓ [AUDIO FLOWS HERE - NOT STORED]
Listener receives audio stream
```

## How to Verify WebRTC Audio Flow

### Method 1: Browser WebRTC Stats (BEST for WebRTC)

**In Speaker App Browser Console:**

```javascript
// Check if audio is being sent
window.kvsWebRTC?.peerConnection?.getStats().then(stats => {
  stats.forEach(stat => {
    if (stat.type === 'outbound-rtp' && stat.mediaType === 'audio') {
      console.log('=== AUDIO TRANSMISSION ===');
      console.log('Packets sent:', stat.packetsSent);
      console.log('Bytes sent:', stat.bytesSent);
      console.log('Audio codec:', stat.mimeType);
      console.log('Sample rate:', stat.clockRate);
      
      if (stat.packetsSent > 0) {
        console.log('✅ AUDIO IS BEING TRANSMITTED');
      } else {
        console.log('❌ NO AUDIO PACKETS SENT');
      }
    }
  });
});

// Check microphone track
window.kvsWebRTC?.localStream?.getAudioTracks().forEach(track => {
  console.log('Audio track:', track.label);
  console.log('Enabled:', track.enabled);
  console.log('Muted:', track.muted);
  console.log('Ready state:', track.readyState);
});
```

**In Listener App Browser Console:**

```javascript
// Check if audio is being received
window.kvsWebRTC?.peerConnection?.getStats().then(stats => {
  stats.forEach(stat => {
    if (stat.type === 'inbound-rtp' && stat.mediaType === 'audio') {
      console.log('=== AUDIO RECEPTION ===');
      console.log('Packets received:', stat.packetsReceived);
      console.log('Bytes received:', stat.bytesReceived);
      console.log('Packets lost:', stat.packetsLost);
      console.log('Jitter:', stat.jitter);
      
      if (stat.packetsReceived > 0) {
        console.log('✅ AUDIO IS BEING RECEIVED');
      } else {
        console.log('❌ NO AUDIO PACKETS RECEIVED');
      }
    }
  });
});

// Check remote track
window.kvsWebRTC?.remoteStream?.getAudioTracks().forEach(track => {
  console.log('Remote audio track:', track.label);
  console.log('Enabled:', track.enabled);
  console.log('Muted:', track.muted);
  console.log('Ready state:', track.readyState);
});
```

### Method 2: KVS WebRTC Metrics (AWS Console)

1. Go to AWS Console → Kinesis Video Streams
2. Click on "Signaling channels" (not "Video streams")
3. Find your channel: `session-joyful-hope-911`
4. Click "Metrics" tab
5. Look for:
   - **MessagesSent**: Should be > 0 if signaling working
   - **MessagesReceived**: Should be > 0 if peers connected
   - **ConnectionDuration**: Shows active connections

### Method 3: CloudWatch Metrics

```bash
# Check KVS WebRTC signaling metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/KinesisVideoSignaling \
  --metric-name MessagesSent \
  --dimensions Name=ChannelName,Value=session-joyful-hope-911 \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region us-east-1
```

## Critical Realization: Architecture Gap

### Current Problem

Your system has a **critical architectural gap**:

```
Current (WebRTC Only):
Speaker ↔ KVS Signaling Channel ↔ Listener
         (peer-to-peer audio)
         ❌ NO processing in middle
         ❌ Backend never sees audio
```

**The audio flows directly peer-to-peer! Your backend pipeline is bypassed!**

### What You Need

To process audio through Transcribe/Translate/TTS, you need EITHER:

**Option A: Hybrid Architecture (Recommended)**
```
Speaker → KVS Signaling Channel → Multiple Listeners (direct audio)
    ↓
    Also sends audio to backend
    ↓
Backend: MediaStream Recording API → Upload to S3 → Process
    ↓
Transcribe → Translate → TTS → WebSocket to Listeners
```

**Option B: Server-Side Processing**
```
Speaker → KVS Signaling Channel → Media Server (EC2/ECS)
                                      ↓
                              Processes audio
                                      ↓
                              Transcribe/Translate/TTS
                                      ↓
                              Back to Listeners
```

**Option C: WebRTC Data Channel**
```
Speaker → Records audio locally
    ↓
Sends via WebRTC Data Channel → Backend
    ↓
Process → Send results back via Data Channel
```

## Immediate Action Required

### Test 1: Verify Peer-to-Peer Audio Works

1. **Open Speaker App** → Create session
2. **Open Listener App** → Join session
3. **Speak into speaker microphone**
4. **Check if listener hears original audio** (untranslated)

**If listener hears audio:**
- ✅ WebRTC peer-to-peer is working
- ❌ But backend processing isn't in the flow
- **Need to implement server-side capture**

**If listener doesn't hear audio:**
- ❌ WebRTC connection issue
- Check browser console for errors
- Verify ICE candidates exchanged

### Test 2: Check Backend Processing

Run this in speaker browser console while talking:

```javascript
// Record audio locally and send to backend
const recordAndProcess = async () => {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const mediaRecorder = new MediaRecorder(stream);
  const chunks = [];
  
  mediaRecorder.ondataavailable = (e) => {
    chunks.push(e.data);
    console.log('Audio chunk captured:', e.data.size, 'bytes');
  };
  
  mediaRecorder.onstop = async () => {
    const blob = new Blob(chunks, { type: 'audio/webm' });
    console.log('Total audio captured:', blob.size, 'bytes');
    
    // Convert to base64 and send to backend
    const reader = new FileReader();
    reader.onload = async () => {
      const base64Audio = reader.result.split(',')[1];
      
      // Send to audio processor (via API or WebSocket)
      console.log('Ready to send to backend:', base64Audio.substring(0, 50) + '...');
      // TODO: Actually send to backend
    };
    reader.readAsDataURL(blob);
  };
  
  // Record for 5 seconds
  mediaRecorder.start();
  setTimeout(() => mediaRecorder.stop(), 5000);
  
  console.log('Recording started...');
};

recordAndProcess();
```

## Required Architecture Changes

### Current vs Required

**What You Have:**
```typescript
// KVSWebRTCService.ts connects peers directly
this.peerConnection.addTrack(track, this.localStream);
// Audio flows peer-to-peer, backend never sees it
```

**What You Need:**
```typescript
// ALSO capture audio for backend processing
const audioContext = new AudioContext();
const source = audioContext.createMediaStreamSource(this.localStream);
const processor = audioContext.createScriptProcessor(4096, 1, 1);

processor.onaudioprocess = (e) => {
  const inputData = e.inputBuffer.getChannelData(0);
  // Convert to PCM and send to backend via WebSocket
  this.sendToBackend(inputData);
};

source.connect(processor);
processor.connect(audioContext.destination);
```

## Recommended Fix Strategy

### Phase 1: Verify WebRTC Works (This Week)
1. ✅ Confirm signaling channel exists (DONE)
2. Test peer-to-peer audio (listener hears speaker directly)
3. Verify WebRTC stats show packets flowing
4. Document current peer-to-peer latency

### Phase 2: Add Backend Processing (Next Week)
1. Implement MediaStream recording in speaker app
2. Send audio chunks via WebSocket to backend
3. Process through Transcribe/Translate/TTS
4. Send translated audio back to listeners

### Phase 3: Optimize (Week 3)
1. Dual-path: Direct audio + processed audio
2. Listeners choose: original (low latency) or translated (higher latency)
3. Implement audio mixing/switching
4. Optimize buffer sizes

## Testing Commands (Updated)

```bash
# Test with corrected script
export SESSION_ID=joyful-hope-911
./scripts/verify-audio-pipeline.sh

# Check signaling channel (not stream)
aws kinesisvideo describe-signaling-channel \
  --channel-name session-joyful-hope-911 \
  --region us-east-1

# Check WebRTC metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/KinesisVideoSignaling \
  --metric-name MessagesSent \
  --dimensions Name=ChannelName,Value=session-joyful-hope-911 \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum \
  --region us-east-1

# Tail logs
./scripts/tail-lambda-logs.sh kvs-stream-consumer-dev
```

## Success Criteria (Revised)

### Immediate (This Week)
- [ ] Signaling channel exists ✅ (VERIFIED)
- [ ] Peer-to-peer audio works (listener hears speaker)
- [ ] WebRTC stats show packets > 0
- [ ] Browser console shows no WebRTC errors

### Next Week
- [ ] Audio captured via MediaStream Recording API
- [ ] Audio sent to backend via WebSocket
- [ ] Backend processes through Transcribe/Translate
- [ ] Translated audio returned to listeners

### Week 3
- [ ] End-to-end latency < 5 seconds
- [ ] System works with 10+ listeners
- [ ] UI feedback implemented
- [ ] Basic monitoring in place

## Critical Questions Answered

**Q: Why can't I query fragments?**
A: WebRTC Signaling Channels don't store fragments. Media flows peer-to-peer.

**Q: Where does backend processing happen?**
A: Currently it doesn't! You need to add audio capture in the browser and send to backend separately.

**Q: Is kvs_stream_consumer even needed?**
A: Not for WebRTC signaling. You need a different approach: WebSocket audio streaming or MediaStream recording.

**Q: What's the fastest path to working translation?**
A: Add MediaStream Recording API in speaker app → Send chunks via WebSocket → Process → Return translated audio to listeners.

## Next Session Focus

1. Test peer-to-peer audio (does listener hear speaker?)
2. If yes: Implement MediaStream capture for backend processing
3. If no: Debug WebRTC connection issues first
4. Add WebSocket audio streaming from speaker to backend
5. Connect backend to existing Transcribe/Translate/TTS pipeline

---

**KEY INSIGHT:** Your WebRTC setup enables real-time peer-to-peer audio. To add translation, you need to **also** capture and process audio through your backend pipeline. The two paths can coexist:
- Path 1: Direct peer-to-peer (low latency, original audio)
- Path 2: Backend processing (higher latency, translated audio)
