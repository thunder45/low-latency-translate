# Real-Time Emotion-Aware Speech Translation Platform

Production-ready technical specifications for a cloud-based system enabling real-time audio broadcasting with live translation and emotion preservation.

## Project Overview

- **87 Requirements** across 7 major components
- **2-4 second end-to-end latency**
- **Supports 500 concurrent listeners per session**
- **Unlimited session duration** (automatic connection refresh)
- **Cost-optimized**: ~$0.04 per listener-hour

## Specifications

1. **Session Management & WebSocket** - Connection infrastructure
2. **Real-Time Transcription** - Partial results processing
3. **Translation & Broadcasting** - Multi-language with caching
4. **Audio Quality Validation** - SNR, clipping, echo detection
5. **Emotion Detection & SSML** - Preserve speaking dynamics
6. **Speaker & Listener Controls** - Pause, mute, volume, language switch
7. **Frontend Client Applications** - React/TypeScript web apps

## Implementation Timeline

**12 weeks** with 4 developers to production launch

See [implementation-roadmap.md](./implementation-roadmap.md) for detailed execution plan.

## Technology Stack

**Backend**: AWS Lambda, API Gateway WebSocket, DynamoDB, Transcribe, Translate, Polly  
**Frontend**: React 18, TypeScript, Vite, Web Audio API  
**Audio Processing**: librosa, numpy  
**Cost**: ~$170/month at scale  

## Getting Started

Review specifications in `.kiro/specs/` directory. Each component has:
- `requirements.md` - EARS-formatted requirements
- `design.md` - Architecture and implementation details
- `tasks.md` - Implementation task breakdown

## Architecture Overview

### System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CLIENT APPLICATIONS                                 │
├──────────────────────────────┬──────────────────────────────────────────────┤
│   SPEAKER APP (React/TS)     │      LISTENER APP (React/TS)                 │
│   ┌──────────────────────┐   │      ┌──────────────────────┐               │
│   │ • Microphone Input   │   │      │ • Audio Playback     │               │
│   │ • Session Controls   │   │      │ • Language Selection │               │
│   │ • Audio Validation   │   │      │ • Volume/Mute        │               │
│   │ • Emotion Display    │   │      │ • Pause/Resume       │               │
│   └──────────────────────┘   │      └──────────────────────┘               │
│            │                  │               │                              │
│            │ WebSocket (WSS)  │               │ WebSocket (WSS)              │
└────────────┼──────────────────┴───────────────┼──────────────────────────────┘
             │                                   │
             └───────────────┬───────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────────────────┐
│                    AWS API GATEWAY (WebSocket)                               │
│                    • Connection Management                                    │
│                    • Route: $connect, $disconnect, sendAudio, etc.           │
└────────────────────────────┬─────────────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌────────────────┐   ┌──────────────────┐
│   SESSION     │   │  TRANSCRIPTION │   │   TRANSLATION    │
│   MANAGER     │   │    SERVICE     │   │    PIPELINE      │
│   (Lambda)    │   │    (Lambda)    │   │    (Lambda)      │
├───────────────┤   ├────────────────┤   ├──────────────────┤
│• Create/Join  │   │• Partial       │   │• Multi-language  │
│• Validate JWT │   │  Results       │   │• Cache Lookup    │
│• Heartbeat    │   │• Stream Audio  │   │• Parallel Trans  │
│• Cleanup      │   │• Quality Check │   │• Broadcast       │
└───────┬───────┘   └────────┬───────┘   └────────┬─────────┘
        │                    │                     │
        │                    │                     │
        ▼                    ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                      DYNAMODB TABLES                         │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  Sessions    │ Connections  │ Translations │  Audio Quality │
│              │              │   (Cache)    │   Metrics      │
└──────────────┴──────────────┴──────────────┴────────────────┘
        │                    │                     │
        │                    │                     │
┌───────▼────────────────────▼─────────────────────▼───────────┐
│              SUPPORTING LAMBDA FUNCTIONS                      │
├───────────────┬──────────────────┬───────────────────────────┤
│ AUDIO QUALITY │  EMOTION         │  SPEAKER/LISTENER         │
│ VALIDATOR     │  DETECTOR        │  CONTROLS                 │
│ (Lambda)      │  (Lambda)        │  (Lambda)                 │
├───────────────┼──────────────────┼───────────────────────────┤
│• SNR Check    │• Pitch Analysis  │• Pause/Resume             │
│• Clipping     │• Energy Detect   │• Mute/Unmute              │
│• Echo Detect  │• SSML Generation │• Volume Control           │
│• Noise Level  │• Emotion Tags    │• Language Switch          │
└───────┬───────┴────────┬─────────┴───────────┬───────────────┘
        │                │                     │
        └────────────────┼─────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌─────────────┐  ┌────────────┐
│   AWS        │  │    AWS      │  │   AWS      │
│  TRANSCRIBE  │  │  TRANSLATE  │  │   POLLY    │
│              │  │             │  │            │
│• Streaming   │  │• 100+ Lang  │  │• Neural    │
│• Partial     │  │• Real-time  │  │• SSML      │
│  Results     │  │             │  │• Emotion   │
└──────────────┘  └─────────────┘  └────────────┘
```

**Data Flow (Speaker → Listener):**
1. Speaker sends audio chunks via WebSocket
2. Session Manager validates & routes
3. Audio Quality Validator checks SNR/clipping
4. Transcription Service → AWS Transcribe (partial results)
5. Emotion Detector analyzes audio features
6. Translation Pipeline: cache check → translate (parallel) → store
7. Generate SSML with emotion tags
8. AWS Polly synthesizes speech
9. Broadcast to all listeners via WebSocket

**Key Characteristics:**
- Event-Driven: Lambda functions triggered by WebSocket events
- Stateless: All state in DynamoDB, enables auto-scaling
- Parallel Processing: Translation to multiple languages simultaneously
- Caching: Translation cache reduces API calls by ~70%
- Streaming: Partial results for low latency
- Resilient: Auto-reconnect, heartbeat, graceful degradation

### Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        COMPONENT RELATIONSHIPS                               │
└─────────────────────────────────────────────────────────────────────────────┘

DEPENDENCY FLOW: 1 → 2 → 3 → 5 → 6
                     ↓   ↓
                     4   └─→ 7

┌──────────────────────────────────────────────────────────────────────────┐
│  1. SESSION MANAGEMENT & WEBSOCKET                                       │
│     • handler.py - Lambda entry point                                    │
│     • session_service.py - Core business logic                           │
│     • connection_manager.py - WebSocket connections                      │
│     • models.py - Session/Connection data models                         │
│     • validators.py - JWT & input validation                             │
│                                                                          │
│     PROVIDES: Session lifecycle, connection tracking                     │
│     STORES: DynamoDB (sessions, connections tables)                      │
└──────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│  2. REAL-TIME TRANSCRIPTION                                              │
│     • handler.py - Receives audio chunks                                 │
│     • transcriber.py - AWS Transcribe integration                        │
│     • audio_processor.py - Audio format conversion                       │
│     • partial_results.py - Streaming partial results                     │
│                                                                          │
│     RECEIVES: Raw audio from speaker                                     │
│     OUTPUTS: Partial & final transcripts                                 │
│     CALLS: AWS Transcribe Streaming API                                  │
└──────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│  3. TRANSLATION & BROADCASTING PIPELINE                                  │
│     • handler.py - Orchestrates translation flow                         │
│     • translator.py - AWS Translate integration                          │
│     • cache_manager.py - Translation cache (DynamoDB)                    │
│     • broadcaster.py - Send to all listeners                             │
│     • parallel_processor.py - Parallel translation                       │
│                                                                          │
│     RECEIVES: Transcribed text                                           │
│     OUTPUTS: Translated text in N languages                              │
│     CALLS: AWS Translate API, DynamoDB cache                             │
│     BROADCASTS: To all connected listeners                               │
└──────────────────────────────────────────────────────────────────────────┘
                    ↓                               ↓
┌─────────────────────────────┐   ┌────────────────────────────────────────┐
│  4. AUDIO QUALITY           │   │  5. EMOTION DETECTION & SSML           │
│     VALIDATION              │   │     • detector.py - Feature extraction │
│     • validator.py          │   │     • pitch_analyzer.py - Pitch track  │
│     • snr_checker.py        │   │     • energy_detector.py - Energy      │
│     • clipping_detector.py  │   │     • ssml_generator.py - SSML tags    │
│     • echo_detector.py      │   │                                        │
│                             │   │     ANALYZES: Pitch, energy, rate      │
│     VALIDATES: SNR, clip    │   │     OUTPUTS: Emotion tags + SSML       │
│     OUTPUTS: Quality metrics│   │     CALLS: AWS Polly for synthesis     │
└─────────────────────────────┘   └────────────────────────────────────────┘
                                                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│  6. FRONTEND CLIENT APPLICATIONS                                         │
│     SPEAKER APP              │  LISTENER APP                             │
│     • AudioInput.tsx         │  • AudioPlayer.tsx                        │
│     • SessionControl.tsx     │  • LanguageSelect.tsx                     │
│     • QualityMonitor.tsx     │  • VolumeControl.tsx                      │
│     • EmotionDisplay.tsx     │  • TranscriptView.tsx                     │
│     • useWebSocket hook      │  • useWebSocket hook                      │
│     • useAudioInput hook     │  • useAudioPlayer hook                    │
│                                                                          │
│     SENDS: Audio chunks, controls  │  RECEIVES: Translations             │
│     DISPLAYS: Quality, emotions    │  CONTROLS: Volume, pause            │
└──────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│  7. SPEAKER & LISTENER CONTROLS                                          │
│     SPEAKER CONTROLS         │  LISTENER CONTROLS                        │
│     • pause_manager.py       │  • audio_controller.py                    │
│     • Pause/resume session   │  • Mute/volume/language switch            │
│                              │  • Client-side controls                   │
│                                                                          │
│     MANAGES: User interaction states                                     │
│     UPDATES: DynamoDB connection preferences                             │
└──────────────────────────────────────────────────────────────────────────┘
```

**Component Dependencies:**

| Component | Depends On | Provides To |
|-----------|------------|-------------|
| Session Manager | DynamoDB, API Gateway | All components (session validation) |
| Transcription | Session Manager, AWS Transcribe, Audio Quality | Translation Pipeline, Emotion Detector |
| Translation Pipeline | Transcription, AWS Translate, DynamoDB Cache, Emotion Detector | Frontend Apps (via WebSocket) |
| Audio Quality Validator | None (standalone) | Transcription (quality metrics) |
| Emotion Detector | Transcription (audio chunks), AWS Polly | Translation Pipeline (SSML tags) |
| Speaker App | Session Manager, WebSocket API, Speaker Controls | Audio to backend, Control commands |
| Listener App | Session Manager, Translation, Listener Controls | User preferences, Control commands |
| Controls | Session Manager, DynamoDB | Frontend Apps (state updates) |

**Shared Data Stores (DynamoDB):**
- `sessions` - Session Manager (write), All (read)
- `connections` - Session Manager (write), All (read)
- `translation_cache` - Translation Pipeline (read/write)
- `audio_quality` - Audio Quality Validator (write)
- `emotion_data` - Emotion Detector (write)

**Communication Patterns:**
- **Synchronous**: Direct Lambda invocation between services
- **Asynchronous**: Event-driven via DynamoDB Streams
- **WebSocket**: Bidirectional real-time communication with clients

## Standards & Best Practices

This project demonstrates production-grade patterns:

**Architecture**
- Serverless-first with event-driven Lambda functions
- Stateless design with DynamoDB persistence
- Separation of concerns (handler vs. business logic)
- Auto-scaling without infrastructure management

**Code Quality**
- Python type hints throughout
- TypeScript with strict mode
- Pydantic models for data validation
- Structured exception hierarchy
- Comprehensive error handling

**Testing**
- >80% unit test coverage target
- Integration tests for component interactions
- Mocking external services (AWS, APIs)
- Test-driven development workflow

**Documentation**
- EARS requirements format ("The system SHALL...")
- Measurable acceptance criteria
- Complete API documentation with examples
- Task breakdown with traceability

**Performance**
- Streaming partial results for low latency
- Translation caching (reduces API calls ~70%)
- Parallel processing where possible
- 2-4 second end-to-end latency target

**Security**
- JWT token validation
- Role-based access control
- Encrypted WebSocket connections (WSS)
- Input validation and sanitization
- No PII in logs

**Cost Optimization**
- Translation caching reduces API calls
- Lambda cold start mitigation
- DynamoDB on-demand pricing
- ~$0.04 per listener-hour achieved

**Observability**
- Structured JSON logging with correlation IDs
- Request tracing across components
- Latency and success rate metrics
- Error tracking with context

## License


