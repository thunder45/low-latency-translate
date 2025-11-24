# Phase 2 Implementation Status

## ✅ Completed (Phase 2 Foundation)

### 1. Dependencies Installed
```bash
✅ amazon-kinesis-video-streams-webrtc
✅ @aws-sdk/client-kinesis-video
✅ @aws-sdk/client-kinesis-video-signaling
✅ @aws-sdk/client-cognito-identity
```

### 2. Core Services Created

#### KVSWebRTCService.ts (300 lines) ✅
- Master (speaker) connection with microphone access
- Viewer (listener) connection for audio playback
- WebRTC signaling (SDP offer/answer, ICE candidates)
- Automatic STUN/TURN server configuration from KVS
- Connection state management
- Mute/unmute controls
- Complete error handling

#### KVSCredentialsProvider.ts (140 lines) ✅
- Cognito Identity Pool integration
- JWT → AWS temporary credentials exchange
- Credential caching with auto-refresh
- Singleton pattern for convenience

---

## 🔄 Next: Update Speaker/Listener Services

### SpeakerService.ts Changes Needed

**REMOVE** (WebSocket audio - ~100 lines):
- `audioCapture: AudioCapture` and all AudioCapture methods
- `wsClient` audio transmission logic
- `sendAudio` WebSocket handling
- Manual chunk encoding/sending

**ADD** (WebRTC - ~50 lines):
```typescript
import { KVSWebRTCService } from '../../../shared/services/KVSWebRTCService';
import { getKVSCredentialsProvider } from '../../../shared/services/KVSCredentialsProvider';

private kvsService: KVSWebRTCService | null = null;

async startBroadcast(): Promise<void> {
  // Get AWS credentials for KVS
  const credentials = await this.getAWSCredentials();
  
  // Create KVS service
  this.kvsService = new KVSWebRTCService({
    channelARN: session.kvsChannelArn,
    channelEndpoint: session.kvsSignalingEndpoints.WSS,
    region: config.region,
    credentials: credentials,
    role: 'MASTER',
  });
  
  // Connect as Master (audio automatically streams)
  await this.kvsService.connectAsMaster();
  
  // Audio now flows via WebRTC - no manual handling!
  console.log('[Speaker] Broadcasting via WebRTC');
}
```

**KEEP** (All control methods):
- `pause()` / `resume()` - Still use WebSocket for control
- `mute()` / `unmute()` - Call `kvsService.mute()`
- `setVolume()` - Preference storage remains
- `endSession()` - Cleanup KVS connection
- Status polling (WebSocket for metadata)

**Net Result**: ~50 lines removed, cleaner code

### ListenerService.ts Changes Needed

**REMOVE** (WebSocket audio reception - ~80 lines):
- WebSocket audio message handling
- Base64 decoding
- AudioContext buffer management

**ADD** (WebRTC - ~40 lines):
```typescript
async startListening(): Promise<void> {
  // Get AWS credentials
  const credentials = await this.getAWSCredentials();
  
  // Create KVS service
  this.kvsService = new KVSWebRTCService({
    channelARN: session.kvsChannelArn,
    channelEndpoint: session.kvsSignalingEndpoints.WSS,
    region: config.region,
    credentials: credentials,
    role: 'VIEWER',
  });
  
  // Handle incoming audio track
  this.kvsService.onTrackReceived = (stream) => {
    this.audioElement.srcObject = stream;
    this.audioElement.play();
  };
  
  // Connect as Viewer
  await this.kvsService.connectAsViewer();
}
```

---

## 📝 Implementation Steps (Remaining)

### Step 1: Update SessionHttpService Types
Add KVS fields to SessionMetadata interface:
```typescript
interface SessionMetadata {
  sessionId: string;
  sourceLanguage: string;
  qualityTier: string;
  kvsChannelArn: string;        // NEW
  kvsChannelName: string;        // NEW
  kvsSignalingEndpoints: {       // NEW
    WSS: string;
    HTTPS: string;
  };
}
```

### Step 2: Rewrite SpeakerService
- Replace AudioCapture with KVSWebRTCService
- Remove WebSocket audio transmission
- Keep pause/mute/volume controls
- Update initialization flow

### Step 3: Rewrite ListenerService
- Replace WebSocket audio reception with WebRTC
- Handle `ontrack` event
- Connect audio element to stream
- Keep control message handling

### Step 4: Update SpeakerApp.tsx
- Pass KVS channel info from session creation
- Initialize KVS credentials provider
- Pass credentials to SpeakerService

### Step 5: Update ListenerApp.tsx
- Get KVS channel info from session join
- Initialize KVS credentials provider
- Pass credentials to ListenerService

---

## 🎯 Expected Outcome

### Before (WebSocket):
```
Speaker:
  Microphone → AudioCapture → Base64 → WebSocket (TCP) →
  API Gateway → Lambda → SQS → audio_processor

Problems:
- 1-3 seconds latency
- Connection closes constantly
- Base64 overhead
- Per-message costs
```

### After (WebRTC):
```
Speaker:
  Microphone → WebRTC (UDP) → KVS Signaling Channel →
  KVS Stream → Lambda → audio_processor

Benefits:
- <500ms latency (3-6x faster)
- Persistent connection
- Native binary
- Bandwidth-based cost
```

---

## ⏱️ Time Estimate

**Remaining Phase 2 Work**: 2-3 hours
- Update SpeakerService: 45 minutes
- Update ListenerService: 30 minutes
- Update types and configs: 30 minutes
- Testing: 1 hour
- Commit and document: 15 minutes

---

## 🧪 Testing Checklist

After implementation:
- [ ] Speaker can connect as Master
- [ ] Microphone access granted
- [ ] ICE connection established (check logs)
- [ ] Listener can connect as Viewer
- [ ] Listener receives audio track
- [ ] Audio plays correctly
- [ ] Mute/unmute works
- [ ] Volume control works
- [ ] Connection persists (no disconnections)
- [ ] Latency < 500ms

---

## 📚 References

- KVS WebRTC Docs: https://docs.aws.amazon.com/kinesisvideostreams-webrtc-dg/
- WebRTC API: https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API
- Migration Guide: `WEBRTC_MIGRATION_GUIDE.md`

---

**Status**: Phase 2 foundation complete, ready for service updates.
