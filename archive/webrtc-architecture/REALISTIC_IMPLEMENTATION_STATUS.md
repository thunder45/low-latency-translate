# Realistic Implementation Status & Testing Strategy

**Created**: November 26, 2025  
**Reality Check**: We're at ~30% completion, not 70%

---

## Honest Assessment

### ✅ What Actually Works (30%)

#### Phase 1: Infrastructure ✓
- KVS signaling channels created on session creation
- HTTP API returns KVS metadata
- IAM roles configured (after propagation)

#### Phase 2: Basic Connectivity ✓
- Speaker WebRTC connects as Master
- Listener WebRTC connects as Viewer (anonymous)
- ICE connection established (logged in console)

### ❌ What Doesn't Work / Not Implemented (70%)

#### 1. No User Feedback in UI
- ❌ Session ID not displayed to speaker
- ❌ Connection status not shown (users don't know if connected)
- ❌ No audio transmission indicators
- ❌ No listener count updates
- ❌ Errors silently ignored (users see nothing)
- ❌ No WebRTC connection state visualization

#### 2. Audio Pipeline Not Verified
- ❌ Don't know if audio reaches KVS stream
- ❌ kvs_stream_consumer may not be receiving data
- ❌ No verification SQS receives audio chunks
- ❌ audio_processor may not be processing KVS audio
- ❌ Full pipeline (Transcribe → Translate → TTS) untested
- ❌ Listeners don't receive translated audio yet

#### 3. Testing is Primitive
- ✅ Only tested: WebRTC connection logs in browser console
- ❌ No automated tests
- ❌ No integration tests
- ❌ No end-to-end pipeline verification
- ❌ No latency measurements
- ❌ No error scenario testing

#### 4. Missing Frontend Features
- ❌ AudioVisualizer not working (getInputLevel returns 0)
- ❌ Session display incomplete
- ❌ Error messages not shown to users
- ❌ Loading states not implemented
- ❌ Connection troubleshooting UI missing

---

## Comprehensive Testing Strategy

### Level 1: Component Testing (Unit Tests)

#### Frontend Components
```typescript
// Test KVSWebRTCService
- Mock SignalingClient, verify Master/Viewer connection
- Test mute/unmute functionality
- Test error handling
- Test cleanup

// Test KVSCredentialsProvider
- Mock Cognito Identity API
- Test credential caching
- Test refresh logic
- Test error scenarios

// Test SpeakerService
- Mock KVSWebRTCService
- Verify startBroadcast() calls connectAsMaster()
- Test control methods (pause/mute)
- Test cleanup
```

#### Backend Lambdas
```python
# Test kvs_stream_consumer
- Mock EventBridge event
- Mock KVS GetMedia API
- Verify SQS message sent
- Test error handling

# Test http_session_handler
- Mock KVS CreateSignalingChannel
- Verify session record created
- Verify EventBridge event emitted
- Test KVS channel deletion
```

### Level 2: Integration Testing

#### Test 1: Speaker WebRTC Connection
```bash
Test: Speaker establishes WebRTC connection to KVS

Steps:
1. Create session via HTTP API
2. Verify KVS channel exists
3. Connect as Master
4. Verify ICE connection state = "connected"
5. Verify audio track added to peer connection

Expected Logs:
[KVS] Signaling channel opened as Master
[KVS] ICE connection state: connected
[KVS] Added audio track to peer connection

Success Criteria:
- WebRTC connection state = "connected"
- Audio track has enabled=true
- No errors in console
```

#### Test 2: Audio Reaches KVS Stream
```bash
Test: Speaker audio flows to KVS stream

Steps:
1. Speaker connects and starts speaking
2. Query KVS stream for data
3. Verify stream has fragments

Commands:
aws kinesisvideo describe-stream \
  --stream-arn {derived from channel ARN}

aws kinesisvideo get-data-endpoint \
  --stream-arn {arn} \
  --api-name GET_MEDIA

# Check if stream has data
aws kinesis-video-media get-media \
  --stream-arn {arn} \
  --start-selector StartSelectorType=NOW \
  | head -c 1000 | xxd

Expected:
- Stream exists
- Media endpoint returns data
- Binary audio data visible

Success Criteria:
- get-media returns audio data (not empty)
- Data format is valid (can be parsed)
```

#### Test 3: KVS Consumer Triggered
```bash
Test: EventBridge triggers kvs_stream_consumer

Steps:
1. Create session (triggers EventBridge)
2. Monitor kvs_stream_consumer logs
3. Verify Lambda invoked

Commands:
aws logs tail /aws/lambda/kvs-stream-consumer-dev \
  --since 5m --follow

Expected Logs:
"Processing session creation event"
"KVS channel ARN: arn:aws:..."
"Connecting to KVS stream"

Success Criteria:
- Lambda invoked within 10 seconds
- No errors in logs
- Function completes successfully
```

#### Test 4: Audio Reaches SQS
```bash
Test: kvs_stream_consumer forwards audio to SQS

Steps:
1. Speaker streaming audio
2. Check SQS queue for messages
3. Verify message format

Commands:
aws sqs get-queue-attributes \
  --queue-url {audio-queue-url} \
  --attribute-names ApproximateNumberOfMessages

aws sqs receive-message \
  --queue-url {audio-queue-url} \
  --max-number-of-messages 1

Expected:
- Queue has messages
- Message contains audio data
- Message has sessionId

Success Criteria:
- ApproximateNumberOfMessages > 0
- Message body is valid JSON
- audioData field is base64 encoded
```

#### Test 5: Audio Processor Handles KVS Audio
```bash
Test: audio_processor receives and processes KVS audio

Steps:
1. Monitor audio_processor logs
2. Verify Transcribe invoked
3. Check for transcript events

Commands:
aws logs tail /aws/lambda/audio-processor-dev --follow

Expected Logs:
"Processing audio chunk from KVS"
"Starting Transcribe streaming session"
"Received transcript: ..."

Success Criteria:
- Audio processor invoked
- Transcribe returns transcripts
- No processing errors
```

#### Test 6: Full Pipeline (Transcribe → Translate → TTS)
```bash
Test: Complete transcription, translation, synthesis flow

Steps:
1. Speaker says: "Hello everyone"
2. Monitor all Lambda logs
3. Verify each stage processes

Expected Flow:
audio_processor:
  → "Transcript: Hello everyone"
  → Publishes to EventBridge

translation_processor:
  → "Received transcript event"
  → "Translating to: es, fr, de"
  → "Synthesizing audio for es"
  → "Broadcasting to es listeners"

Success Criteria:
- Transcript accurate
- Translation occurs for each language
- TTS audio generated
- No errors in pipeline
```

#### Test 7: Listener Receives Audio
```bash
Test: Listener hears translated audio

Steps:
1. Listener joins session
2. Speaker speaks
3. Verify audio plays in listener browser

Browser Console Checks:
kvsService.onTrackReceived() fired?
audioElement.srcObject set?
audioElement.playing = true?
Audio context state = "running"?

Success Criteria:
- Listener hears audio (manual verification)
- Audio is in correct language
- Latency < 1 second (manual timing)
```

### Level 3: End-to-End Testing

#### E2E Test 1: Single Listener
```
Scenario: 1 speaker, 1 listener, 1 language

Steps:
1. Speaker creates session
2. Speaker sees session ID on screen
3. Listener joins with session ID
4. Listener sees "Connected" status
5. Speaker speaks: "Testing one two three"
6. Listener hears Spanish translation: "Probando uno dos tres"
7. Measure latency (stopwatch)

Success Criteria:
- Session creation < 3 seconds
- WebRTC connection < 5 seconds
- Audio latency < 2 seconds
- Translation is accurate
- No errors visible to users
```

#### E2E Test 2: Multiple Listeners
```
Scenario: 1 speaker, 3 listeners, 3 languages

Steps:
1. Speaker creates session
2. Listener 1 joins (Spanish)
3. Listener 2 joins (French)
4. Listener 3 joins (German)
5. Speaker speaks continuously for 1 minute
6. All listeners hear their language

Success Criteria:
- All listeners connect successfully
- Each hears correct language
- Latency consistent across listeners
- No dropouts or connection failures
```

#### E2E Test 3: Control Functions
```
Scenario: Test pause/mute controls

Steps:
1. Speaker streaming audio
2. Speaker pauses broadcast
3. Verify listeners notified
4. Speaker resumes
5. Speaker mutes
6. Verify no audio transmitted
7. Speaker unmutes

Success Criteria:
- Controls work immediately
- Listeners receive state change notifications
- Audio stops/starts correctly
- UI reflects current state
```

---

## Missing Frontend Implementation

### Critical Missing Features

#### 1. Session Display Component
**Current State**: Exists but incomplete  
**Missing**:
```typescript
// Show session ID prominently
<div className="session-id-display">
  <h2>Session ID: {sessionId}</h2>
  <button onClick={copyToClipboard}>Copy</button>
  <button onClick={shareSession}>Share</button>
</div>

// Show WebRTC connection status
<div className="connection-status">
  <StatusIndicator state={webrtcState} />
  <span>
    {webrtcState === 'connected' ? 
      '🟢 Streaming' : 
      '🔴 Connecting...'}
  </span>
</div>

// Show listener count in real-time
<div className="listener-stats">
  <span>👥 {listenerCount} listeners</span>
  <div>Languages: {languages.join(', ')}</div>
</div>
```

#### 2. Error Display Component
**Current State**: Errors logged to console only  
**Missing**:
```typescript
// Error banner at top of screen
{error && (
  <div className="error-banner">
    <span>⚠️ {error.message}</span>
    <button onClick={dismissError}>✕</button>
  </div>
)}

// Detailed error for troubleshooting
{error?.code === 'WEBRTC_CONNECTION_FAILED' && (
  <div className="troubleshooting-tips">
    <h3>Connection Failed</h3>
    <ul>
      <li>Check your firewall settings</li>
      <li>Try using a VPN</li>
      <li>Contact support with error code: {error.code}</li>
    </ul>
  </div>
)}
```

#### 3. WebRTC Stats Display
**Current State**: No visibility into connection quality  
**Missing**:
```typescript
// Real-time WebRTC stats
<div className="webrtc-stats">
  <div>Connection: {iceConnectionState}</div>
  <div>Latency: {roundTripTime}ms</div>
  <div>Packet Loss: {packetsLost}/{packetsReceived}</div>
  <div>Jitter: {jitter}ms</div>
  <div>Bitrate: {bitrate} kbps</div>
</div>

// Implement getStats() polling:
useEffect(() => {
  const interval = setInterval(async () => {
    if (kvsService) {
      const stats = await kvsService.getConnectionStats();
      setWebRTCStats(stats);
    }
  }, 1000);
  return () => clearInterval(interval);
}, [kvsService]);
```

#### 4. Audio Visualizer Fix
**Current State**: Returns 0 (no audio level)  
**Missing**: Implement Web Audio API analyzer

```typescript
// In KVSWebRTCService, add:
private analyzerNode: AnalyserNode | null = null;
private audioContext: AudioContext | null = null;

async connectAsMaster(): Promise<void> {
  // ... existing code ...
  
  // Create audio context for visualization
  this.audioContext = new AudioContext();
  const source = this.audioContext.createMediaStreamSource(this.localStream!);
  this.analyzerNode = this.audioContext.createAnalyser();
  this.analyzerNode.fftSize = 256;
  source.connect(this.analyzerNode);
}

getInputLevel(): number {
  if (!this.analyzerNode) return 0;
  
  const dataArray = new Uint8Array(this.analyzerNode.frequencyBinCount);
  this.analyzerNode.getByteFrequencyData(dataArray);
  
  // Calculate average
  const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
  return average / 255; // Normalize to 0-1
}
```

#### 5. Loading States
**Current State**: No loading indicators  
**Missing**:
```typescript
// Show loading during connection
{isConnectingWebRTC && (
  <div className="loading-overlay">
    <Spinner />
    <p>Establishing WebRTC connection...</p>
    <p>This may take 3-5 seconds</p>
  </div>
)}

// Show loading during session creation
{isCreatingSession && (
  <div className="loading-overlay">
    <Spinner />
    <p>Creating session...</p>
  </div>
)}
```

---

## Comprehensive Testing Plan

### Phase A: Verify Audio Capture (Week 1)

#### Test A1: Microphone Access
```bash
Goal: Verify microphone audio is captured

Browser Test:
1. Grant microphone permission
2. Open chrome://webrtc-internals/
3. Look for "ssrc" entries under sender
4. Verify "bytesSent" increasing
5. Verify "packetsSent" increasing

Success: bytesSent increases by ~16KB/second (16kHz mono audio)
```

#### Test A2: WebRTC Stats
```typescript
// Implement in KVSWebRTCService
async getConnectionStats(): Promise<WebRTCStats> {
  const stats = await this.peerConnection!.getStats();
  
  let bytesSent = 0;
  let packetsLost = 0;
  
  stats.forEach(report => {
    if (report.type === 'outbound-rtp') {
      bytesSent = report.bytesSent;
      packetsLost = report.packetsLost;
    }
  });
  
  return { bytesSent, packetsLost };
}

// Poll and display
useEffect(() => {
  const interval = setInterval(async () => {
    const stats = await kvsService.getConnectionStats();
    console.log('📊 WebRTC Stats:', stats);
    setStats(stats);
  }, 2000);
  
  return () => clearInterval(interval);
}, [kvsService]);
```

### Phase B: Verify KVS Ingestion (Week 1)

#### Test B1: Check KVS Stream Exists
```bash
Goal: Verify KVS creates a stream for the channel

Commands:
# List streams
aws kinesisvideo list-streams

# Describe stream (if exists)
aws kinesisvideo describe-stream \
  --stream-name {channel-name}

Expected:
- Stream exists with matching name
- Status = ACTIVE
- StreamARN returned

Note: KVS may use channel for signaling only,
      ingestion requires WebRTC Ingestion API
```

#### Test B2: KVS Ingestion Configuration
```bash
Goal: Verify WebRTC ingestion is configured

Problem: KVS WebRTC has two modes:
1. Signaling only (what we have) - P2P, no recording
2. Ingestion (what we need) - Routes through AWS

Solution: Need to configure KVS WebRTC Ingestion

Commands:
# Check if ingestion configured
aws kinesisvideo describe-media-storage-configuration \
  --channel-arn {arn}

# Expected: Configuration exists
# Actual: May return error if not configured

Action Required:
→ Configure WebRTC ingestion in http_session_handler
→ Use UpdateMediaStorageConfiguration API
→ Link signaling channel to stream
```

#### Test B3: Verify kvs_stream_consumer Triggered
```bash
Goal: EventBridge triggers Lambda when session created

Test Steps:
1. Create session in speaker app
2. Monitor EventBridge:
   aws events test-event-pattern \
     --event-pattern file://pattern.json \
     --event file://test-event.json

3. Check Lambda invocation:
   aws lambda list-invocations \
     --function-name kvs-stream-consumer-dev

4. Check logs:
   aws logs tail /aws/lambda/kvs-stream-consumer-dev --since 5m

Expected:
- EventBridge rule matches
- Lambda invoked
- Logs show "Processing session creation"

Current Issue:
→ May not be configured correctly
→ Need to verify EventBridge rule exists
→ Need to verify Lambda has permissions
```

### Phase C: Backend Pipeline Verification (Week 2)

#### Test C1: SQS Receives Audio
```bash
Goal: Verify kvs_stream_consumer sends to SQS

Commands:
# Check queue depth
aws sqs get-queue-attributes \
  --queue-url {audio-queue-url} \
  --attribute-names ApproximateNumberOfMessages

# Receive a message (non-destructive peek)
aws sqs receive-message \
  --queue-url {audio-queue-url} \
  --max-number-of-messages 1 \
  --visibility-timeout 0

Expected Message Format:
{
  "sessionId": "blessed-covenant-420",
  "audioData": "base64-encoded-pcm...",
  "timestamp": 1732620000000,
  "source": "kvs_webrtc",
  "chunkId": "chunk-001"
}

Success Criteria:
- Queue has messages
- Format is correct
- AudioData is valid base64
```

#### Test C2: Audio Processor Handles KVS Audio
```bash
Goal: audio_processor can process audio from kvs_stream_consumer

Test:
1. Manually send test message to SQS:
   aws sqs send-message \
     --queue-url {audio-queue-url} \
     --message-body file://test-audio-message.json

2. Monitor audio_processor:
   aws logs tail /aws/lambda/audio-processor-dev --follow

3. Verify Transcribe invoked

Expected Logs:
"Processing audio chunk"
"Source: kvs_webrtc"
"Starting Transcribe streaming"
"Received transcript: ..."

Issues to Check:
→ Does audio_processor expect different format from KVS?
→ Are sample rate/encoding compatible?
→ Is there a format conversion step missing?
```

#### Test C3: Full Pipeline Test
```bash
Goal: Verify Speaker → Transcribe → Translate → TTS → Listener

Test Steps:
1. Speaker says clear phrase: "Hello this is a test"
2. Monitor all Lambda logs in parallel:
   aws logs tail /aws/lambda/kvs-stream-consumer-dev --follow &
   aws logs tail /aws/lambda/audio-processor-dev --follow &
   aws logs tail /aws/lambda/translation-processor-dev --follow &

3. Verify each stage processes:
   - kvs_stream_consumer: Receives audio
   - audio_processor: Transcribes "Hello this is a test"
   - translation_processor: Translates to target languages
   - TTS synthesis occurs
   - Broadcast to listeners (TODO: implement)

4. Measure latency at each stage

Success Criteria:
- Full pipeline completes
- Total time < 2 seconds
- No errors in any Lambda
- Listener receives audio (when implemented)
```

### Phase D: Frontend Implementation (Week 2-3)

#### Task D1: Session ID Display
```typescript
// In SpeakerApp.tsx
<SessionDisplay 
  sessionId={sessionId}
  onCopy={() => {
    navigator.clipboard.writeText(sessionId);
    showNotification('Session ID copied!');
  }}
  onShare={() => {
    const url = `${window.location.origin}/listener?session=${sessionId}`;
    navigator.clipboard.writeText(url);
    showNotification('Share link copied!');
  }}
/>

// Styled prominently:
.session-id-display {
  font-size: 2rem;
  font-weight: bold;
  text-align: center;
  margin: 2rem 0;
  padding: 1rem;
  background: rgba(255,255,255,0.1);
  border-radius: 8px;
}
```

#### Task D2: Connection Status Indicator
```typescript
// Create ConnectionStatusIndicator component
interface ConnectionStatus {
  webrtc: 'connected' | 'connecting' | 'failed' | 'disconnected';
  websocket: 'connected' | 'disconnected';
  transmitting: boolean;
}

<ConnectionStatusIndicator status={connectionStatus} />

// Shows:
// 🟢 Connected & Streaming
// 🟡 Connecting...
// 🔴 Connection Failed
// 🟠 Connected (Not Streaming)
```

#### Task D3: WebRTC Diagnostics Panel
```typescript
// Add diagnostics panel for troubleshooting
<WebRTCDiagnostics 
  iceConnectionState={kvsService.getICEConnectionState()}
  connectionState={kvsService.getConnectionState()}
  bytesSent={stats.bytesSent}
  packetsLost={stats.packetsLost}
  roundTripTime={stats.roundTripTime}
  candidateType={stats.candidateType} // 'host', 'srflx', 'relay'
/>

// Shows:
// ICE: connected (relay via TURN)
// Sent: 1.2 MB
// Lost: 3 packets (0.1%)
// RTT: 45ms
```

#### Task D4: Error Display Component
```typescript
// Global error boundary
<ErrorBoundary>
  {error && (
    <ErrorDisplay 
      error={error}
      onDismiss={() => setError(null)}
      onRetry={() => retryConnection()}
    />
  )}
</ErrorBoundary>

// Error types:
- WEBRTC_CONNECTION_FAILED
- MICROPHONE_PERMISSION_DENIED
- KVS_ACCESS_DENIED
- SESSION_NOT_FOUND
- NETWORK_ERROR
```

#### Task D5: Audio Visualizer Fix
```typescript
// Implement proper audio level detection
class KVSWebRTCService {
  private audioContext: AudioContext | null = null;
  private analyzerNode: AnalyserNode | null = null;
  private dataArray: Uint8Array | null = null;
  
  async connectAsMaster(): Promise<void> {
    // ... existing connection code ...
    
    // Set up audio analysis
    this.audioContext = new AudioContext();
    const source = this.audioContext.createMediaStreamSource(this.localStream!);
    this.analyzerNode = this.audioContext.createAnalyser();
    this.analyzerNode.fftSize = 256;
    this.dataArray = new Uint8Array(this.analyzerNode.frequencyBinCount);
    source.connect(this.analyzerNode);
  }
  
  getInputLevel(): number {
    if (!this.analyzerNode || !this.dataArray) return 0;
    
    this.analyzerNode.getByteFrequencyData(this.dataArray);
    const average = this.dataArray.reduce((a, b) => a + b) / this.dataArray.length;
    return average / 255; // Normalize 0-1
  }
}

// Update visualizer to actually show levels
<AudioVisualizer 
  isTransmitting={isTransmitting}
  inputLevel={speakerService?.getInputLevel() || 0}
  refreshRate={60} // 60 FPS for smooth animation
/>
```

---

## Implementation Roadmap (Realistic)

### Week 1: Complete Basic Testing
- [ ] Implement WebRTC stats collection
- [ ] Verify audio reaches KVS stream
- [ ] Test kvs_stream_consumer trigger
- [ ] Verify SQS receives audio chunks
- [ ] Test audio_processor handles KVS audio

### Week 2: Frontend UI Implementation
- [ ] Add session ID display with copy/share
- [ ] Implement connection status indicators
- [ ] Add WebRTC diagnostics panel
- [ ] Implement error display components
- [ ] Fix audio visualizer with Web Audio API
- [ ] Add loading states

### Week 3: Backend Pipeline Testing
- [ ] Test full Transcribe → Translate → TTS flow
- [ ] Verify listener audio delivery (need to implement)
- [ ] Measure end-to-end latency
- [ ] Test with multiple listeners
- [ ] Test error scenarios

### Week 4: Integration & E2E Testing
- [ ] E2E test: Single listener flow
- [ ] E2E test: Multiple listeners (3+ languages)
- [ ] E2E test: Control functions (pause/mute)
- [ ] Load test: 50+ concurrent listeners
- [ ] Stress test: Network interruptions

### Week 5: Polish & Documentation
- [ ] Fix all identified bugs
- [ ] Complete Phase 5 cleanup
- [ ] Update all documentation
- [ ] Create deployment runbook
- [ ] Prepare for production

**Realistic Timeline**: 5 weeks, not "almost done"

---

## Critical Gaps to Address

### 1. KVS WebRTC Ingestion Not Configured
**Problem**: KVS might only be doing signaling, not ingestion  
**Solution**: Configure UpdateMediaStorageConfiguration in http_session_handler

```python
# In create_session(), after creating channel:
kvs_client.update_media_storage_configuration(
    ChannelARN=channel_arn,
    MediaStorageConfiguration={
        'StreamARN': stream_arn,  # Need to create stream first
        'Status': 'ENABLED'
    }
)
```

### 2. Audio Format Compatibility
**Problem**: KVS audio format may not match audio_processor expectations  
**Check**: 
- KVS outputs: Opus codec typically
- audio_processor expects: PCM 16kHz 16-bit
- **Need format conversion in kvs_stream_consumer**

### 3. Listener Audio Delivery Not Implemented
**Problem**: Listeners connect via WebRTC but receive no audio  
**Solution**: Need to implement one of:
- Option A: Separate KVS channel per language
- Option B: Media server to mix/distribute
- Option C: Direct WebSocket for translated audio (hybrid)

### 4. No Automated Testing
**Problem**: Only manual browser testing  
**Solution**: Implement test suite:
- Jest for unit tests
- Playwright for E2E tests
- AWS SAM for Lambda testing locally

---

## Immediate Action Items

### Priority 1: Verify Audio Flow (Critical)
1. Check if audio reaches KVS stream (Test B2)
2. Verify kvs_stream_consumer receives data (Test B3)
3. Confirm SQS has messages (Test C1)
4. Test audio_processor handles format (Test C2)

### Priority 2: Implement UI Feedback (High)
1. Display session ID prominently
2. Show WebRTC connection status
3. Display error messages to users
4. Fix audio visualizer
5. Add loading indicators

### Priority 3: Complete Testing (High)
1. Automated unit tests for services
2. Integration tests for pipeline
3. E2E test for full flow
4. Performance benchmarking

### Priority 4: Documentation (Medium)
1. Update this status doc with findings
2. Create troubleshooting runbook
3. Document known issues
4. Write deployment guide

---

## Honest Timeline

**Current Completion**: ~30%

**Remaining Work**:
- Testing & Verification: 2-3 weeks
- Frontend UI Implementation: 2 weeks
- Backend Pipeline Completion: 1-2 weeks
- Integration & Polish: 1 week
- Production Prep: 1 week

**Total to Production**: **7-9 weeks** from now

**Accelerated Path** (with shortcuts):
- Skip comprehensive UI (basic only): -2 weeks
- Skip extensive testing (manual only): -2 weeks
- Skip polish (MVP): -1 week
- **Minimum Viable**: 2-4 weeks

---

## Recommendation

### For MVP (Fastest Path to Working Demo):

**Week 1: Verify Core Flow**
1. Confirm audio reaches KVS → SQS → audio_processor
2. Test Transcribe → Translate → TTS pipeline
3. Implement basic session ID display
4. Show connection status (green/red dot)

**Week 2: Make it Usable**
1. Display errors to users (not just console)
2. Show listener count
3. Implement audio visualizer properly
4. Test with 5-10 listeners

**Week 3: Polish & Deploy**
1. Fix identified bugs
2. Add loading states
3. Write basic docs
4. Deploy to production

**Result**: Working MVP in 3 weeks, not production-perfect but functional

Would you like me to start with Priority 1 (verify audio flow) or implement Priority 2 UI feedback first?
