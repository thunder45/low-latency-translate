# Frontend Client Applications - Context Document

This document provides essential context from existing backend specifications to inform the Frontend Client Applications specification. Use this as a reference when creating requirements, design, and tasks for the Speaker and Listener web applications.

---

## System Overview

**Project**: Real-Time Emotion-Aware Speech Translation Platform  
**Architecture**: Serverless (AWS Lambda, API Gateway WebSocket, DynamoDB)  
**Target Latency**: 2-4 seconds end-to-end  
**Max Session Duration**: 2 hours (with automatic connection refresh)  
**Max Listeners**: 500 per session (configurable to 1000)

### User Roles

**Speaker** (Authenticated):
- Creates sessions with human-readable IDs
- Broadcasts audio via WebSocket
- Receives quality warnings
- Sees listener status

**Listener** (Anonymous):
- Joins sessions with session ID only
- Receives translated audio
- Controls playback (pause, mute, volume)
- Can switch languages mid-session

---

## WebSocket API Contracts

### Base URL

```
wss://{api-id}.execute-api.{region}.amazonaws.com/{stage}
Example: wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod
```

### Speaker Connection

**Route**: `$connect`  
**Query Parameters**:
```
?token=<JWT_TOKEN>                     # Required: Cognito JWT
&action=createSession                  # Required
&sourceLanguage=<ISO_639_1>            # Required: e.g., "en"
&qualityTier=<standard|premium>        # Optional: default "standard"
```

**Success Response**:
```json
{
  "type": "sessionCreated",
  "sessionId": "golden-eagle-427",
  "sourceLanguage": "en",
  "qualityTier": "standard",
  "connectionId": "L0SM9cOFvHcCIhw=",
  "expiresAt": 1699510800000,
  "timestamp": 1699500000000
}
```

**Error Responses**: 401 (Unauthorized), 400 (Invalid params), 429 (Rate limit), 500 (Server error)

### Listener Connection

**Route**: `$connect`  
**Query Parameters**:
```
?sessionId=<SESSION_ID>                # Required: e.g., "golden-eagle-427"
&targetLanguage=<ISO_639_1>            # Required: e.g., "es"
&action=joinSession                    # Required
```

**Success Response**:
```json
{
  "type": "sessionJoined",
  "sessionId": "golden-eagle-427",
  "targetLanguage": "es",
  "sourceLanguage": "en",
  "connectionId": "K3Rx8bNEuGdDJkx=",
  "listenerCount": 16,
  "qualityTier": "standard",
  "timestamp": 1699500120000
}
```

**Error Responses**: 404 (Session not found), 400 (Invalid language), 429 (Rate limit), 503 (Session full)

### Connection Refresh (For Sessions >100 Minutes)

**Route**: Custom route `refreshConnection`  
**Query Parameters**:
```
?token=<JWT_TOKEN>                     # Speaker only
&action=refreshConnection
&sessionId=<SESSION_ID>
&role=<speaker|listener>
&targetLanguage=<ISO_639_1>            # Listener only
```

**Trigger**: System sends `connectionRefreshRequired` message at 100 minutes

**Response**:
```json
{
  "type": "connectionRefreshComplete",
  "sessionId": "golden-eagle-427",
  "role": "speaker",
  "timestamp": 1699500000000
}
```

### Heartbeat

**Client → Server** (every 30 seconds):
```json
{
  "action": "heartbeat",
  "timestamp": 1699500180000
}
```

**Server → Client**:
```json
{
  "type": "heartbeatAck",
  "timestamp": 1699500180123,
  "serverTime": 1699500180125
}
```

### Send Audio (Speaker Only)

**Client → Server**:
```json
{
  "action": "sendAudio",
  "audioData": "base64-encoded-pcm-audio-bytes",
  "timestamp": 1699500123456,
  "chunkId": "chunk-001"
}
```

**Audio Format**:
- Format: PCM (16-bit signed integers, little-endian)
- Sample Rate: 16000 Hz recommended
- Channels: Mono (1 channel)
- Chunk Duration: 1-3 seconds recommended
- Base64 Encoding: Standard base64 encoding

### Receive Audio (Listener)

**Server → Client**:
```json
{
  "type": "audio",
  "audioData": "base64-encoded-audio-bytes",
  "format": "pcm",
  "sampleRate": 16000,
  "channels": 1,
  "timestamp": 1699500125000,
  "sequenceNumber": 42
}
```

### Audio Quality Warnings (Speaker Only)

**Server → Client**:
```json
{
  "type": "audio_quality_warning",
  "issue": "snr_low|clipping|echo|silence",
  "message": "Audio quality is low (SNR: 15.2 dB). Try moving closer...",
  "details": {
    "snr": 15.2,
    "threshold": 20.0
  },
  "timestamp": 1699564800.123
}
```

### Session Status Query (Speaker Only)

**Client → Server**:
```json
{
  "action": "getSessionStatus",
  "sessionId": "golden-eagle-427"
}
```

**Server → Client**:
```json
{
  "type": "sessionStatus",
  "sessionId": "golden-eagle-427",
  "isActive": true,
  "listenerCount": 16,
  "languageDistribution": {
    "es": 7,
    "fr": 5,
    "de": 4
  },
  "sessionDuration": 300000,
  "createdAt": 1699500000000,
  "expiresAt": 1699510800000,
  "timestamp": 1699500300000
}
```

### End Session (Speaker Only)

**Client → Server**:
```json
{
  "action": "endSession",
  "sessionId": "golden-eagle-427",
  "reason": "Speaker ended session"
}
```

**Server → All Clients**:
```json
{
  "type": "sessionEnded",
  "sessionId": "golden-eagle-427",
  "reason": "Speaker ended session",
  "timestamp": 1699500400000
}
```

---

## Audio Capture (Speaker Client)

### Web Audio API Integration

**Required Steps**:
1. Request microphone permissions
2. Create AudioContext
3. Get MediaStream from getUserMedia
4. Create MediaStreamSource
5. Create ScriptProcessorNode or AudioWorklet
6. Process audio in chunks (1-3 seconds)
7. Convert to PCM 16-bit
8. Base64 encode
9. Send via WebSocket

**Code Pattern**:
```javascript
// Request microphone
const stream = await navigator.mediaDevices.getUserMedia({
  audio: {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
    sampleRate: 16000,
    channelCount: 1
  }
});

// Create audio context
const audioContext = new AudioContext({ sampleRate: 16000 });
const source = audioContext.createMediaStreamSource(stream);

// Process audio chunks
const processor = audioContext.createScriptProcessor(16384, 1, 1);
processor.onaudioprocess = (e) => {
  const audioData = e.inputBuffer.getChannelData(0);
  const pcm16 = convertFloat32ToPCM16(audioData);
  const base64Audio = btoa(String.fromCharCode(...pcm16));
  
  webSocket.send(JSON.dumps({
    action: 'sendAudio',
    audioData: base64Audio,
    timestamp: Date.now()
  }));
};
```

**Performance**:
- Chunk size: 1-3 seconds (balance latency vs efficiency)
- Max message size: 1MB (API Gateway limit)
- Processing overhead: <10ms per chunk

---

## Audio Playback (Listener Client)

### Web Audio API Integration

**Required Steps**:
1. Create AudioContext
2. Create audio buffer queue
3. Receive base64-encoded audio
4. Decode base64 to audio samples
5. Create AudioBufferSourceNode
6. Connect to AudioContext destination
7. Schedule playback

**Code Pattern**:
```javascript
const audioContext = new AudioContext();
const audioQueue = [];

// Receive audio from WebSocket
webSocket.onmessage = async (event) => {
  const message = JSON.parse(event.data);
  
  if (message.type === 'audio') {
    // Decode base64
    const audioBytes = atob(message.audioData);
    const audioData = new Int16Array(audioBytes.length);
    for (let i = 0; i < audioBytes.length; i++) {
      audioData[i] = audioBytes.charCodeAt(i);
    }
    
    // Convert to AudioBuffer
    const audioBuffer = audioContext.createBuffer(
      message.channels,
      audioData.length,
      message.sampleRate
    );
    
    // Copy data to buffer
    const channelData = audioBuffer.getChannelData(0);
    for (let i = 0; i < audioData.length; i++) {
      channelData[i] = audioData[i] / 32768.0; // Normalize to -1.0 to 1.0
    }
    
    // Queue for playback
    audioQueue.push(audioBuffer);
    schedulePlayback();
  }
};

function schedulePlayback() {
  if (audioQueue.length > 0 && !isPlaying) {
    const buffer = audioQueue.shift();
    const source = audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(audioContext.destination);
    source.start();
    isPlaying = true;
    source.onended = () => {
      isPlaying = false;
      schedulePlayback();
    };
  }
}
```

---

## Authentication Flow (Speaker Only)

### AWS Cognito Integration

**Steps**:
1. User enters email/password
2. Frontend calls Cognito InitiateAuth
3. Receive JWT tokens (idToken, accessToken, refreshToken)
4. Use idToken for WebSocket authentication
5. Refresh token before expiration (24 hours)

**Libraries**:
- amazon-cognito-identity-js
- aws-amplify (optional, higher-level)

**Code Pattern**:
```javascript
import { CognitoUserPool, CognitoUser, AuthenticationDetails } from 'amazon-cognito-identity-js';

const userPool = new CognitoUserPool({
  UserPoolId: 'us-east-1_ABC123',
  ClientId: 'abc123def456'
});

// Authenticate
const authDetails = new AuthenticationDetails({
  Username: email,
  Password: password
});

const cognitoUser = new CognitoUser({
  Username: email,
  Pool: userPool
});

cognitoUser.authenticateUser(authDetails, {
  onSuccess: (result) => {
    const idToken = result.getIdToken().getJwtToken();
    // Use idToken for WebSocket connection
  },
  onFailure: (err) => {
    console.error(err);
  }
});
```

---

## Performance Requirements

### Latency Targets

| Operation | Target | Maximum |
|-----------|--------|---------|
| Session creation | 2 seconds | 3 seconds |
| Listener join | 1 second | 2 seconds |
| Audio end-to-end | 2-4 seconds | 5 seconds |
| Control response (pause/mute) | 100ms | 200ms |
| Language switch | 500ms | 1 second |
| Connection refresh | 5 seconds | 10 seconds |

### UI Responsiveness

- Button clicks: <50ms feedback
- Volume slider: <100ms update
- Status updates: <2 seconds
- Error messages: Immediate display

---

## Browser Compatibility

### Minimum Versions

- Chrome: 90+
- Firefox: 88+
- Safari: 14+
- Edge: 90+

### Required APIs

- WebSocket support (WSS protocol)
- Web Audio API (getUserMedia, AudioContext)
- Local Storage API
- Base64 encoding/decoding
- ES2020+ JavaScript features
- async/await support

### Bandwidth Requirements

- Speaker upload: 1 Mbps minimum
- Listener download: 256 Kbps minimum

---

## UI Components Needed

### Speaker Application

**Required Components**:
1. **LoginForm**: Email/password authentication with Cognito
2. **SessionCreator**: Language selection, quality tier, session creation
3. **BroadcastControls**: Pause, mute, volume controls (from controls spec)
4. **SessionDisplay**: Session ID display (large, copyable)
5. **ListenerMonitor**: Active listener count, language distribution, pause/mute states
6. **AudioVisualizer**: Real-time waveform or level meter
7. **QualityIndicator**: SNR, clipping, echo warnings
8. **ConnectionStatus**: Connected/disconnected, refresh warnings, heartbeat status
9. **ErrorDisplay**: User-friendly error messages with remediation

**Layout Recommendations**:
- Large session ID at top (easy to read aloud)
- Controls in prominent position
- Listener stats on side panel
- Audio quality indicators
- Connection status always visible

### Listener Application

**Required Components**:
1. **SessionJoiner**: Session ID input, language selection
2. **PlaybackControls**: Pause, mute, volume controls (from controls spec)
3. **LanguageSelector**: Dropdown with available languages
4. **SpeakerStatus**: Speaker pause/mute state
5. **AudioPlayer**: Handles audio playback with buffering
6. **BufferIndicator**: Shows buffered audio during pause (0-30 seconds)
7. **ConnectionStatus**: Connected/disconnected status
8. **ErrorDisplay**: User-friendly error messages

**Layout Recommendations**:
- Session info at top
- Large play/pause button
- Volume and language controls
- Speaker status
- Connection quality indicator

---

## State Management Requirements

### Speaker State

```typescript
interface SpeakerState {
  // Session
  sessionId: string | null;
  connectionId: string | null;
  isConnected: boolean;
  
  // Audio
  isPaused: boolean;
  isMuted: boolean;
  inputVolume: number;  // 0-100
  isTransmitting: boolean;
  
  // Quality
  snr: number;
  hasClipping: boolean;
  hasEcho: boolean;
  isSilent: boolean;
  
  // Listeners
  listenerCount: number;
  languageDistribution: Record<string, number>;
  listenerStates: ListenerState[];
  
  // Connection
  connectionDuration: number;  // milliseconds
  needsRefresh: boolean;
  refreshing: boolean;
}
```

### Listener State

```typescript
interface ListenerState {
  // Session
  sessionId: string | null;
  connectionId: string | null;
  isConnected: boolean;
  sourceLanguage: string | null;
  
  // Audio
  isPaused: boolean;
  isMuted: boolean;
  playbackVolume: number;  // 0-100
  targetLanguage: string;
  
  // Buffer
  bufferedDuration: number;  // 0-30 seconds
  isBuffering: boolean;
  bufferOverflow: boolean;
  
  // Speaker
  speakerPaused: boolean;
  speakerMuted: boolean;
  
  // Connection
  connectionDuration: number;
  needsRefresh: boolean;
  refreshing: boolean;
}
```

---

## Error Handling

### Error Types to Handle

**Connection Errors**:
- 401: Show "Authentication failed. Please log in again."
- 404: Show "Session not found. Please check the session ID."
- 429: Show "Too many attempts. Please wait {retryAfter} seconds."
- 503: Show "Session is full. Try again later."

**Audio Errors**:
- Microphone permission denied: Show permission instructions
- Audio format not supported: Show browser compatibility message
- Network interruption: Show "Reconnecting..." with retry status
- Heartbeat timeout: Attempt automatic reconnection

**Quality Warnings** (Non-blocking):
- SNR low: "Background noise detected. Move to quieter location."
- Clipping: "Audio distortion. Reduce microphone volume."
- Echo: "Echo detected. Enable echo cancellation or use headphones."
- Silence: "No audio detected. Check if microphone is muted."

**Recovery Actions**:
- Auto-retry with exponential backoff (1s, 2s, 4s, 8s, max 30s)
- Show retry countdown to user
- Provide manual "Retry Now" button
- Offer "Start New Session" option on fatal errors

---

## Performance Optimization

### Audio Processing

**Speaker**:
- Use AudioWorklet instead of ScriptProcessorNode (better performance)
- Process audio in 1-2 second chunks (balance latency vs message size)
- Implement audio compression before base64 encoding (if bandwidth limited)
- Monitor microphone input levels for clipping prevention

**Listener**:
- Implement audio queue with 2-3 buffer prefetch
- Use smooth playback transitions between chunks
- Implement jitter buffer for network variations
- Monitor playback underruns

### Network Optimization

- Use binary WebSocket frames instead of text (smaller)
- Batch heartbeat with other messages when possible
- Implement message priority (audio > heartbeat > status)
- Use connection pooling for API calls

### UI Optimization

- Debounce volume slider updates (50ms)
- Throttle listener status updates (1 per second)
- Use React.memo or Vue/Angular equivalents
- Lazy load non-critical components
- Virtual scrolling for large listener lists (>100)

---

## Local Storage & Preferences

### Storage Keys

**Speaker**:
```
speaker_auth_token: JWT token (encrypted)
speaker_refresh_token: Refresh token (encrypted)
speaker_input_volume: number (0-100)
speaker_keyboard_shortcuts: JSON object
```

**Listener**:
```
listener_playback_volume: number (0-100)
listener_language_preference: string (ISO 639-1)
listener_keyboard_shortcuts: JSON object
```

### Security

- Store tokens in secure storage (encrypted localStorage or sessionStorage)
- Never log tokens or sensitive data
- Clear tokens on logout
- Implement token refresh before expiration

---

## Monitoring & Analytics

### Client-Side Metrics to Track

**Performance**:
- Time to connection establishment
- Audio latency (send to first audio received)
- Control response time
- Language switch duration
- Buffer utilization

**Quality**:
- Connection drop rate
- Audio underrun/overrun events
- Error frequency by type
- Browser compatibility issues

**Usage**:
- Session duration
- Average listener count
- Language distribution
- Feature usage (pause, mute, volume, language switch)

### Implementation

Use CloudWatch RUM (Real User Monitoring) or similar:
```javascript
import { AwsRum } from 'aws-rum-web';

const awsRum = new AwsRum(
  'APPLICATION_ID',
  '1.0.0',
  'REGION',
  {
    sessionSampleRate: 1.0,
    guestRoleArn: 'ARN',
    identityPoolId: 'ID',
    endpoint: 'ENDPOINT',
    telemetries: ['performance', 'errors', 'http']
  }
);
```

---

## Accessibility Requirements

### WCAG 2.1 Level AA Compliance

**Required**:
- Keyboard navigation for all controls
- Screen reader support (ARIA labels)
- Focus indicators
- Color contrast ratios (4.5:1 for text, 3:1 for UI components)
- Closed captions (future enhancement)

**Keyboard Shortcuts** (Default, Customizable):
- Mute toggle: `Ctrl+M` or `Cmd+M`
- Pause toggle: `Ctrl+P` or `Cmd+P`
- Volume up: `Ctrl+Up` or `Cmd+Up`
- Volume down: `Ctrl+Down` or `Cmd+Down`

---

## Testing Requirements

### Unit Tests

- Component rendering tests (Jest + React Testing Library)
- Audio processing utilities
- WebSocket client wrapper
- State management logic
- Error handling utilities

### Integration Tests

- Complete speaker flow (auth → create → broadcast → end)
- Complete listener flow (join → listen → controls → leave)
- Connection refresh flow
- Error scenarios

### End-to-End Tests

- Multi-browser testing (Playwright or Cypress)
- Mobile responsiveness
- Network condition simulation (slow 3G, packet loss)
- Concurrent user testing (multiple tabs)

### Performance Tests

- Lighthouse scores (Performance, Accessibility, Best Practices, SEO)
- Core Web Vitals (LCP, FID, CLS)
- Bundle size <500KB (excluding audio processing)
- Time to Interactive <3 seconds

---

## Deployment Considerations

### Build Configuration

**Development**:
- Hot reload for rapid iteration
- Source maps enabled
- Unminified code
- Mock WebSocket server for offline development

**Production**:
- Minified and obfuscated code
- Tree shaking for unused code
- Code splitting for faster loads
- CDN distribution (CloudFront)
- Gzip/Brotli compression

### Hosting Options

1. **AWS S3 + CloudFront** (Recommended)
   - Static site hosting
   - Global CDN distribution
   - HTTPS by default
   - Low cost

2. **AWS Amplify Hosting**
   - CI/CD integration
   - Preview deployments
   - Custom domains
   - Higher cost

3. **Self-hosted**
   - More control
   - Can use Nginx/Apache
   - Manual deployment

---

## Security Requirements

### Content Security Policy

```http
Content-Security-Policy: 
  default-src 'self'; 
  connect-src 'self' wss://*.execute-api.*.amazonaws.com https://cognito-idp.*.amazonaws.com; 
  script-src 'self' 'unsafe-inline'; 
  style-src 'self' 'unsafe-inline';
```

### Additional Security

- Enable CORS with specific origins
- Implement rate limiting on client side
- Validate all user inputs
- Sanitize displayed text (prevent XSS)
- Use HTTPS only (no mixed content)

---

## Key Constraints & Limitations

### From Backend Specs

1. **Session Duration**: 2 hours max (connection refresh required)
2. **Max Listeners**: 500 per session (configurable)
3. **Audio Chunk Size**: 1-3 seconds recommended
4. **Message Size**: <1MB (API Gateway limit)
5. **Supported Languages**: 75+ (AWS Translate + Polly intersection)
6. **Idle Timeout**: 10 minutes (heartbeat required)
7. **Rate Limits**:
   - Session creation: 50 per hour per user
   - Listener joins: 10 per minute per IP
   - Heartbeat: 2 per minute

### Client-Side Constraints

1. **Audio Buffer**: 30 seconds max for pause
2. **Preference Storage**: ~100KB max (localStorage limit consideration)
3. **Connection Refresh**: Must complete within 5-minute window
4. **Browser Compatibility**: Modern browsers only (2020+)

---

## Integration Points

### With Backend Services

**Session Management**: 
- Creates/joins sessions
- Maintains heartbeat
- Handles connection refresh
- Manages disconnection

**Transcription Pipeline** (transparent to frontend):
- Audio sent → transcription happens server-side
- No client-side interaction needed

**Translation Pipeline** (transparent to frontend):
- Happens server-side based on listener languages
- Client just receives translated audio

**Audio Quality** (feedback loop):
- Server analyzes audio quality
- Sends warnings to speaker
- Speaker UI displays warnings

**Emotion/SSML** (transparent to frontend):
- Server extracts dynamics from audio
- Applies SSML to synthesis
- Client receives emotionally-enhanced audio

### With Other Frontend Components

**Controls Component** (from controls spec):
- Provides reusable control UI components
- Manages audio state (pause, mute, volume)
- Handles preference persistence
- Implements keyboard shortcuts

**Main Applications**:
- Imports and uses controls component
- Adds session-specific UI (creation, joining, status)
- Adds audio processing (capture for speaker, playback for listener)
- Adds connection management

---

## Recommended Tech Stack

### Core Framework

**Option A: React** (Recommended)
- Pros: Large ecosystem, good for real-time UIs, easy testing
- Cons: Larger bundle size
- Libraries: React 18+, TypeScript, Vite

**Option B: Vue**
- Pros: Smaller bundle, easier learning curve
- Cons: Smaller ecosystem
- Libraries: Vue 3, TypeScript, Vite

**Option C: Vanilla + Web Components**
- Pros: Smallest bundle, no framework lock-in
- Cons: More boilerplate, harder state management

### Supporting Libraries

- **State Management**: Redux, Zustand, or Context API
- **WebSocket Client**: Native WebSocket API (no library needed)
- **Audio Processing**: Web Audio API (native)
- **UI Components**: Material-UI, Ant Design, or custom
- **Build Tool**: Vite (fast) or Webpack
- **Testing**: Jest, React Testing Library, Playwright/Cypress

---

## Success Criteria

### MVP (Minimum Viable Product)

**Speaker can**:
- ✅ Create session
- ✅ See session ID
- ✅ Transmit audio
- ✅ See listener count
- ✅ Pause/mute audio
- ✅ End session

**Listener can**:
- ✅ Join session
- ✅ Hear translated audio
- ✅ Pause/mute audio
- ✅ Adjust volume
- ✅ Switch language

**System provides**:
- ✅ <4 second latency
- ✅ Connection reliability (auto-reconnect)
- ✅ Clear error messages

### Full Feature Set

Add to MVP:
- ✅ Audio quality warnings
- ✅ Keyboard shortcuts
- ✅ Preference persistence
- ✅ Listener state visibility
- ✅ Mobile responsiveness
- ✅ Accessibility compliance

---

## Next Steps for Frontend Spec Creation

1. **Create requirements.md** using EARS format (like other specs)
   - User stories for speaker and listener workflows
   - UI requirements (components, layouts, interactions)
   - Performance requirements (load time, responsiveness)
   - Accessibility requirements
   - Browser compatibility requirements

2. **Create design.md** with:
   - Component architecture (React/Vue/etc.)
   - State management design
   - WebSocket integration patterns
   - Audio processing pipelines
   - Error handling strategies
   - Code examples for key functionality

3. **Create tasks.md** with:
   - Setup tasks (project scaffolding, dependencies)
   - Component implementation tasks
   - Integration tasks
   - Testing tasks
   - Deployment tasks

**Estimated Total**: 15-20 requirements, similar structure to other specs

---

## Reference Documents

**Use These Specs for Reference**:
1. session-management-websocket/requirements.md - WebSocket API contracts
2. session-management-websocket/design.md - Connection handling patterns
3. speaker-listener-controls/requirements.md - UI control requirements
4. speaker-listener-controls/design.md - Frontend component interfaces
5. audio-quality-validation/requirements.md - Quality warning requirements

**Follow These Patterns**:
- EARS format for requirements (WHEN/THE/SHALL)
- 5 acceptance criteria per requirement
- TypeScript interfaces in design
- Production-ready code examples
- Comprehensive testing strategy
- Monitoring and error handling

---

## Estimated Effort

**Frontend Specification Creation**: 4-6 hours  
**Frontend Implementation**: 4-6 weeks with 2 frontend developers

**This context document should accelerate spec creation!** 🚀
