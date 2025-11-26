# Low-Latency Translation System - Traditional KVS Stream Architecture

**Real-time audio translation platform with 3-4 second end-to-end latency**

## Current Status: Phase 0 Complete ✅

**Architecture:** Traditional KVS Stream (MediaRecorder → Backend → Translation → S3)  
**Progress:** Blueprints ready, implementation starting  
**Next:** Phase 1 - Speaker MediaRecorder implementation

---

## Quick Start

### Documentation
- **📋 Master Reference:** [ARCHITECTURE_DECISIONS.md](./ARCHITECTURE_DECISIONS.md) - Start here
- **📈 Progress Tracking:** [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md)
- **🔨 Implementation Guides:**
  - [Phase 1: Speaker MediaRecorder](./PHASE1_SPEAKER_MEDIARECORDER_GUIDE.md)
  - [Phase 2: Backend KVS Writer](./PHASE2_BACKEND_KVS_WRITER_GUIDE.md)
  - [Phase 3: Listener S3 Playback](./PHASE3_LISTENER_S3_PLAYBACK_GUIDE.md)

### Verification
```bash
# Verify infrastructure
./scripts/verify-audio-pipeline.sh

# Monitor Lambda logs
./scripts/tail-lambda-logs.sh kvs-stream-writer-dev
```

---

## Architecture Overview

### Complete Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    SPEAKER BROWSER                           │
│                                                              │
│  1. getUserMedia() → Microphone                             │
│  2. MediaRecorder → Capture WebM (Opus, 16kHz, mono)        │
│  3. 250ms chunks → base64 encoding                          │
│  4. WebSocket → Send to backend                             │
│                                                              │
│  Latency: ~100ms buffering                                  │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ↓ WebSocket (wss://)
                     │ { action: 'audioChunk', audioData, ... }
                     │
┌────────────────────┴─────────────────────────────────────────┐
│              AWS Lambda: connection_handler                  │
│                                                              │
│  Routes WebSocket messages                                  │
│  Forwards audioChunk → kvs_stream_writer (async)            │
│                                                              │
│  Latency: ~50ms                                             │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ↓ Lambda invocation (async)
                     │
┌────────────────────┴─────────────────────────────────────────┐
│              AWS Lambda: kvs_stream_writer                   │
│                                                              │
│  1. Decode base64 → WebM binary                             │
│  2. ffmpeg: WebM → PCM (16kHz, 16-bit, mono)                │
│  3. PutMedia → Write to KVS Stream                          │
│  4. Create stream on-demand if needed                       │
│                                                              │
│  Latency: ~200ms (conversion + upload)                      │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ↓ KVS PutMedia API
                     │
┌────────────────────┴─────────────────────────────────────────┐
│              AWS Kinesis Video Streams                       │
│              (Traditional Stream, NOT WebRTC)                │
│                                                              │
│  • Stream name: session-{sessionId}                         │
│  • Stores PCM audio fragments                               │
│  • Retention: 1 hour (no long-term storage)                 │
│  • Emits EventBridge events on new fragments                │
│                                                              │
│  Latency: ~200ms ingestion                                  │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ↓ EventBridge: Fragment Complete
                     │
┌────────────────────┴─────────────────────────────────────────┐
│              AWS Lambda: kvs_stream_consumer                 │
│                                                              │
│  1. Triggered by EventBridge (new fragments)                │
│  2. GetMedia from KVS Stream                                │
│  3. Extract PCM audio chunks                                │
│  4. Invoke audio_processor (async)                          │
│                                                              │
│  Latency: ~100ms                                            │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ↓ Lambda invocation (async)
                     │
┌────────────────────┴─────────────────────────────────────────┐
│              AWS Lambda: audio_processor                     │
│                                                              │
│  1. AWS Transcribe Streaming → Speech-to-text               │
│     Latency: 1-2 seconds                                    │
│                                                              │
│  2. AWS Translate → Multiple languages (parallel)           │
│     Latency: ~500ms per language                            │
│                                                              │
│  3. Amazon Polly TTS → Generate speech (2s chunks)          │
│     Latency: ~1 second                                      │
│                                                              │
│  4. Store MP3 in S3 + Generate presigned URL                │
│     Latency: ~100ms                                         │
│                                                              │
│  5. Send WebSocket notification to listeners                │
│     Latency: ~50ms                                          │
│                                                              │
│  Total processing: 2-3 seconds                              │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ↓ WebSocket notification
                     │ { type: 'translatedAudio', url, duration }
                     │
┌────────────────────┴─────────────────────────────────────────┐
│                  LISTENER BROWSER                            │
│                                                              │
│  1. Receive WebSocket notification                          │
│  2. Download MP3 from S3 (presigned URL)                    │
│  3. Add to playback queue                                   │
│  4. Play audio (HTMLAudioElement)                           │
│  5. Prefetch next 2-3 chunks                                │
│                                                              │
│  Latency: ~100ms download                                   │
└──────────────────────────────────────────────────────────────┘

TOTAL END-TO-END LATENCY: 3-4 seconds ✅
```

### Key Design Decisions

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| **Audio Capture** | MediaRecorder API | Standard, lightweight, browser-native |
| **Upload Format** | WebM (Opus codec) | Small size, no browser conversion needed |
| **Chunk Size (Speaker)** | 250ms | Low latency, manageable size (~4-5 KB) |
| **Backend Conversion** | ffmpeg (WebM → PCM) | Centralized, keeps browser simple |
| **Storage** | KVS Stream (1hr retention) | Serverless, cost-effective ($0.01/hr) |
| **Event Trigger** | EventBridge (KVS events) | Automatic, scales with load |
| **Listener Delivery** | S3 presigned URLs | Simple, no WebSocket payload limits |
| **Chunk Size (Listener)** | 2 seconds | Balance download time vs smoothness |
| **Recording** | None (process & discard) | Save costs, no storage needed |

---

## Technology Stack

### Frontend
- **Framework:** React 18 + TypeScript
- **Build:** Vite
- **Audio:** MediaRecorder API, HTMLAudioElement
- **State:** Zustand stores
- **Communication:** WebSocket, HTTP API
- **Hosting:** S3 + CloudFront (static hosting)

### Backend
- **Compute:** AWS Lambda (Python 3.11)
- **API:** API Gateway (WebSocket + HTTP)
- **Storage:** 
  - DynamoDB (sessions, connections)
  - KVS Streams (audio fragments, 1hr retention)
  - S3 (translated audio, 24hr lifecycle)
- **Audio Processing:**
  - AWS Transcribe (speech-to-text)
  - AWS Translate (multi-language)
  - Amazon Polly (TTS with SSML)
  - ffmpeg (format conversion)
- **Events:** EventBridge (KVS Stream triggers)
- **Auth:** Cognito (User Pool + Identity Pool)

### Infrastructure as Code
- **AWS CDK** (Python)
- **Deployment:** CloudFormation stacks
- **CI/CD:** Makefiles for local deployment

---

## AWS Resources

### Lambda Functions:
1. **connection_handler** - WebSocket connection management
2. **disconnect_handler** - Cleanup on disconnect
3. **kvs_stream_writer** - WebM → PCM conversion → KVS Stream
4. **kvs_stream_consumer** - Extract audio from KVS Stream
5. **audio_processor** - Transcribe → Translate → TTS → S3

### Storage:
1. **DynamoDB Tables:**
   - `sessions` - Session metadata
   - `connections` - Active WebSocket connections
2. **KVS Streams:** Dynamic per session (session-{id})
3. **S3 Bucket:** translation-audio-{stage} (24hr lifecycle)

### Networking:
1. **API Gateway:** WebSocket API (bidirectional)
2. **API Gateway:** HTTP API (RESTful session management)

### Authentication:
1. **Cognito User Pool** - Speaker authentication
2. **Cognito Identity Pool** - Guest/listener access

---

## Cost Estimate

### Per Session-Hour:
- KVS Stream: $0.01
- Lambda invocations: $0.001
- S3 storage & transfer: $0.001
- Transcribe/Translate/TTS: $0.03-0.05 (depends on audio duration)
- **Total: ~$0.04-0.06 per session-hour**

### Scalability:
- 10 concurrent sessions: ~$0.50/hour
- 100 concurrent sessions: ~$5/hour
- No infrastructure costs (serverless)

---

## Key Features

### Speaker App:
- ✅ Real-time audio streaming (250ms chunks)
- ✅ Microphone controls (pause, mute, volume)
- ✅ Session management
- 🔄 Audio quality monitoring (future)
- 🔄 Emotion display (future)

### Listener App:
- ✅ Join sessions anonymously
- ✅ Language selection (10+ languages)
- ✅ Playback controls (pause, volume)
- 🔄 Transcript display (future)
- 🔄 Audio quality indicators (future)

### Backend:
- ✅ Real-time transcription (AWS Transcribe)
- ✅ Multi-language translation (AWS Translate)
- ✅ Natural TTS (Amazon Polly)
- 🔄 Translation caching (future)
- 🔄 Emotion preservation (future)

---

## Implementation Phases

| Phase | Status | Duration | Description |
|-------|--------|----------|-------------|
| Phase 0 | ✅ Complete | 2 hours | Cleanup & blueprints |
| Phase 1 | ⏳ Ready | 4-6 hours | Speaker MediaRecorder |
| Phase 2 | 📋 Planned | 6-8 hours | Backend KVS writer |
| Phase 3 | 📋 Planned | 6-8 hours | Listener S3 playback |
| Phase 4 | 📋 Planned | 4-6 hours | Testing & optimization |
| Phase 5 | 📋 Future | TBD | UI & monitoring |

**Timeline:** 3-4 days to working translation

---

## Getting Started

### Prerequisites:
- AWS CLI v2
- Node.js 18+
- Python 3.11+
- AWS Account with appropriate permissions

### Development Setup:
```bash
# Clone repository
git clone https://github.com/thunder45/low-latency-translate.git
cd low-latency-translate

# Review architecture decisions
cat ARCHITECTURE_DECISIONS.md

# Check implementation status
cat IMPLEMENTATION_STATUS.md

# Install frontend dependencies
cd frontend-client-apps
npm install

# Install backend dependencies
cd session-management
pip install -r requirements.txt -r requirements-dev.txt

cd audio-transcription
pip install -r requirements.txt -r requirements-dev.txt
```

### Deployment:
```bash
# Deploy backend (session management)
cd session-management
make deploy

# Deploy backend (audio processing)
cd audio-transcription
make deploy

# Build and deploy frontend
cd frontend-client-apps
npm run build
# Deploy to S3/CloudFront
```

### Testing:
```bash
# Verify infrastructure
SESSION_ID=your-session-id ./scripts/verify-audio-pipeline.sh

# Monitor logs
./scripts/tail-lambda-logs.sh kvs-stream-writer-dev
./scripts/tail-lambda-logs.sh audio-processor-dev

# Check KVS Stream fragments
aws kinesisvideo list-fragments \
  --stream-name session-your-id \
  --region us-east-1
```

---

## Project Structure

```
low-latency-translate/
├── ARCHITECTURE_DECISIONS.md          # Master reference (READ THIS FIRST)
├── IMPLEMENTATION_STATUS.md           # Current progress
├── PHASE1_SPEAKER_MEDIARECORDER_GUIDE.md  # Speaker implementation
├── PHASE2_BACKEND_KVS_WRITER_GUIDE.md     # Backend implementation
├── PHASE3_LISTENER_S3_PLAYBACK_GUIDE.md   # Listener implementation
│
├── frontend-client-apps/              # React/TypeScript apps
│   ├── speaker-app/                   # Speaker interface
│   ├── listener-app/                  # Listener interface
│   └── shared/                        # Shared components
│
├── session-management/                # WebSocket + KVS infrastructure
│   ├── lambda/
│   │   ├── connection_handler/        # WebSocket routing
│   │   ├── disconnect_handler/        # Cleanup
│   │   ├── kvs_stream_writer/         # WebM → KVS Stream (NEW)
│   │   └── kvs_stream_consumer/       # KVS → audio_processor
│   └── infrastructure/                # CDK stacks
│
├── audio-transcription/               # Translation pipeline
│   ├── lambda/
│   │   └── audio_processor/           # Transcribe → Translate → TTS → S3
│   └── infrastructure/                # CDK stacks
│
├── scripts/                           # Verification & deployment
│   ├── verify-audio-pipeline.sh       # Automated verification
│   └── tail-lambda-logs.sh            # Log monitoring
│
└── archive/                           # Historical documentation
    └── webrtc-architecture/           # Previous WebRTC approach
```

---

## Technical Specifications

### Audio Formats

| Stage | Format | Rate | Channels | Size (250ms) |
|-------|--------|------|----------|--------------|
| Browser Capture | WebM/Opus | 16kHz | Mono | ~4-5 KB |
| KVS Stream | PCM s16le | 16kHz | Mono | ~8 KB |
| Transcribe Input | PCM | 16kHz | Mono | ~8 KB |
| TTS Output | MP3 | 24kHz | Mono | ~32 KB (2s) |

### Latency Budget

| Component | Target | Measured |
|-----------|--------|----------|
| Browser capture | 100ms | TBD |
| Upload to backend | 200ms | TBD |
| Format conversion | 50ms | TBD |
| KVS ingestion | 200ms | TBD |
| Transcribe | 1-2s | TBD |
| Translate | 500ms | TBD |
| TTS | 1s | TBD |
| S3 upload | 100ms | TBD |
| Listener download | 100ms | TBD |
| **TOTAL** | **3-4s** | TBD |

---

## Core Components

### 1. Speaker App (Frontend)
**Purpose:** Capture and stream audio to backend

**Key Files:**
- `AudioStreamService.ts` - MediaRecorder implementation
- `SpeakerService.ts` - Service orchestration
- `SpeakerApp.tsx` - Main UI component

**Features:**
- Microphone access with permission handling
- 250ms chunk capture and streaming
- WebSocket communication
- Pause/mute/volume controls

### 2. kvs_stream_writer (Backend)
**Purpose:** Convert WebM to PCM and write to KVS Stream

**Key Files:**
- `handler.py` - Lambda entry point
- ffmpeg Lambda Layer - Format conversion

**Features:**
- Base64 decoding
- WebM → PCM conversion (ffmpeg)
- KVS Stream creation and management
- PutMedia API integration

### 3. kvs_stream_consumer (Backend)
**Purpose:** Extract audio from KVS and forward to processor

**Key Files:**
- `handler.py` - EventBridge handler

**Features:**
- Triggered by KVS Stream events
- GetMedia API integration
- PCM chunk extraction
- Forward to audio_processor

### 4. audio_processor (Backend)
**Purpose:** Transcribe, translate, and synthesize speech

**Key Files:**
- `handler.py` - Processing orchestration
- Transcribe/Translate/TTS integration

**Features:**
- Streaming transcription (partial results)
- Parallel translation (multiple languages)
- TTS with emotion SSML
- S3 storage with presigned URLs
- WebSocket notifications to listeners

### 5. Listener App (Frontend)
**Purpose:** Receive and play translated audio

**Key Files:**
- `S3AudioPlayer.ts` - S3 download and playback
- `ListenerService.ts` - Service orchestration
- `ListenerApp.tsx` - Main UI component

**Features:**
- S3 audio download with retry
- Sequential playback queue
- Prefetching (2-3 chunks ahead)
- Pause/mute/volume controls
- Language switching

---

## Development Workflow

### Current Phase: Phase 0 ✅
**Status:** Blueprints complete, ready for implementation

**Deliverables:**
- ✅ Master architecture document
- ✅ 3 detailed implementation guides
- ✅ Progress tracking system
- ✅ Verification scripts
- ✅ Obsolete docs archived

### Next Phase: Phase 1
**Goal:** Speaker MediaRecorder implementation

**Steps:**
1. Create `AudioStreamService.ts`
2. Replace WebRTC in `SpeakerService.ts`
3. Add WebSocket route for audio chunks
4. Test: Audio reaches backend

**Reference:** [PHASE1_SPEAKER_MEDIARECORDER_GUIDE.md](./PHASE1_SPEAKER_MEDIARECORDER_GUIDE.md)

---

## Testing

### Verification Script:
```bash
# Automated verification
SESSION_ID=your-session-id ./scripts/verify-audio-pipeline.sh
```

**Checks:**
1. ✓ KVS Stream exists
2. ✓ Fragments present (audio reaching KVS)
3. ✓ kvs_stream_writer healthy
4. ✓ EventBridge rule configured
5. ✓ kvs_stream_consumer triggered
6. ✓ audio_processor processing
7. ✓ S3 files created

### Manual Testing:
```bash
# Check KVS Stream
aws kinesisvideo describe-stream --stream-name session-{id}
aws kinesisvideo list-fragments --stream-name session-{id}

# Check S3 audio files
aws s3 ls s3://translation-audio-dev/sessions/{id}/translated/

# Monitor logs
./scripts/tail-lambda-logs.sh kvs-stream-writer-dev
```

---

## Monitoring

### CloudWatch Metrics:
- Audio chunks received (kvs_stream_writer)
- Conversion latency (kvs_stream_writer)
- Fragment count (KVS Stream)
- Processing latency (audio_processor)
- S3 upload success rate
- End-to-end latency

### CloudWatch Logs:
- `/aws/lambda/kvs-stream-writer-dev`
- `/aws/lambda/kvs-stream-consumer-dev`
- `/aws/lambda/audio-processor-dev`
- `/aws/lambda/connection-handler-dev`

### Alarms (Future):
- Latency > 5 seconds
- Error rate > 5%
- KVS Stream failures

---

## Security

### Authentication:
- **Speaker:** Cognito User Pool (authenticated users)
- **Listener:** Cognito Identity Pool (anonymous guests)

### Authorization:
- **Speaker:** Can create sessions, stream audio
- **Listener:** Can join sessions, receive translated audio

### Data Protection:
- WebSocket: TLS (wss://)
- S3: Presigned URLs (10-minute expiration)
- KVS Stream: Encrypted at rest
- No long-term storage: 1hr (KVS), 24hr (S3)

---

## Performance Targets

### Latency:
- **Target:** 3-4 seconds end-to-end
- **Components:** See latency budget above
- **Measurement:** Timestamps at each stage

### Scale:
- **Sessions:** 10 concurrent (MVP) → 100 (production)
- **Listeners:** 50 per session (MVP) → 500 (production)
- **Languages:** 10 supported
- **Uptime:** 99.9% target

### Quality:
- **Audio:** 16kHz, clear speech
- **Translation:** Accurate, contextual
- **TTS:** Natural, emotion-preserved

---

## Troubleshooting

### No Audio Reaching Backend:
```bash
# Check browser console for MediaRecorder errors
# Check WebSocket connection status
# Verify microphone permissions granted
```

### No Fragments in KVS Stream:
```bash
# Check kvs_stream_writer logs
./scripts/tail-lambda-logs.sh kvs-stream-writer-dev

# Verify ffmpeg conversion working
# Check IAM permissions for PutMedia
```

### Listeners Not Receiving Audio:
```bash
# Check S3 bucket exists
aws s3 ls | grep translation-audio

# Check audio_processor logs
./scripts/tail-lambda-logs.sh audio-processor-dev

# Verify WebSocket notifications sent
# Check S3 CORS configuration
```

---

## Documentation

### Master Reference:
- **ARCHITECTURE_DECISIONS.md** - Single source of truth, read this first

### Implementation Guides:
- **PHASE1_SPEAKER_MEDIARECORDER_GUIDE.md** - Speaker app implementation
- **PHASE2_BACKEND_KVS_WRITER_GUIDE.md** - Backend KVS integration
- **PHASE3_LISTENER_S3_PLAYBACK_GUIDE.md** - Listener app implementation

### Status & Progress:
- **IMPLEMENTATION_STATUS.md** - Current progress and next steps

### Historical:
- **archive/webrtc-architecture/** - Previous WebRTC approach (archived)

---

## Contributing

### Development Process:
1. Read `ARCHITECTURE_DECISIONS.md`
2. Check `IMPLEMENTATION_STATUS.md` for current phase
3. Follow corresponding `PHASEXX_GUIDE.md`
4. Update task_progress after each step
5. Create checkpoint document when phase complete
6. Commit with descriptive messages

### Code Standards:
- TypeScript strict mode
- Python type hints
- Comprehensive error handling
- Structured logging
- Unit tests for new code

---

## Support

### Issues:
Check phase-specific troubleshooting sections in implementation guides

### Questions:
Review `ARCHITECTURE_DECISIONS.md` for design rationale

### Context Recovery:
1. Read `ARCHITECTURE_DECISIONS.md`
2. Check `IMPLEMENTATION_STATUS.md`
3. Find latest `CHECKPOINT_PHASEXX_COMPLETE.md`
4. Continue from next unchecked task

---

## License

[Add your license here]

---

## Architecture History

**Nov 26, 2025:** Switched from WebRTC peer-to-peer to Traditional KVS Stream architecture for simpler implementation and backend processing integration.

**Previous approach:** WebRTC Signaling Channels (peer-to-peer audio, no backend processing)  
**Current approach:** Traditional KVS Stream (backend processing, translation enabled)  
**Rationale:** Translation requires backend processing; original audio not needed

Archived WebRTC documentation available in `archive/webrtc-architecture/` for reference.
