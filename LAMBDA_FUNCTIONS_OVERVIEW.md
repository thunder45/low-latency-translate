# Lambda Functions Overview

Complete list of all Lambda functions in the low-latency translation system.

---

## Session Management Service (8 Lambdas)

### 1. **Authorizer** (`session-management/lambda/authorizer/`)
**Purpose**: Secure JWT validation for WebSocket connections
- Validates Cognito ID tokens using PyJWT
- Verifies signature, expiration, audience, and issuer
- Extracts user information (userId, email)
- Returns IAM policy (Allow/Deny) for API Gateway
- Supports token in query string or Authorization header

**Trigger**: API Gateway WebSocket Authorizer
**Runtime**: Python 3.9+

---

### 2. **Connection Handler** (`session-management/lambda/connection_handler/`)
**Purpose**: Handles WebSocket connections and MESSAGE events
- **$connect Route**: Validates sessionId and session status
- **MESSAGE Routes**: 
  - `createSession` - Creates new speaker session (legacy WebSocket mode)
  - `joinSession` - Listener joins existing session
  - Control messages: pause/resume/mute/unmute/setVolume/heartbeat
- Role-based authorization (speaker vs listener)
- Broadcasts state changes to all listeners

**Triggers**: 
- API Gateway $connect events
- API Gateway MESSAGE events (custom routes)
**Runtime**: Python 3.9+

---

### 3. **Disconnect Handler** (`session-management/lambda/disconnect_handler/`)
**Purpose**: Cleanup when WebSocket connections close
- Removes connection from DynamoDB
- Decrements listener count for session
- Ends session if speaker disconnects
- Notifies remaining listeners of session end
- Handles graceful and ungraceful disconnections

**Trigger**: API Gateway $disconnect events
**Runtime**: Python 3.9+

---

### 4. **Heartbeat Handler** (`session-management/lambda/heartbeat_handler/`)
**Purpose**: Keeps WebSocket connections alive
- Receives heartbeat messages from clients
- Sends heartbeatAck responses
- Updates lastActivityTime in DynamoDB
- Prevents idle timeout disconnections

**Trigger**: API Gateway MESSAGE event (heartbeat action)
**Runtime**: Python 3.9+

---

### 5. **HTTP Session Handler** (`session-management/lambda/http_session_handler/`)
**Purpose**: HTTP API for session management (hybrid architecture)
- **POST /sessions** - Create session via HTTP (returns sessionId)
- **DELETE /sessions/{sessionId}** - End session via HTTP
- **GET /sessions/{sessionId}** - Get session details
- Disconnects all WebSocket connections for session
- Primary entry point for session creation in hybrid mode

**Trigger**: API Gateway REST API events
**Runtime**: Python 3.9+

---

### 6. **Refresh Handler** (`session-management/lambda/refresh_handler/`)
**Purpose**: Audio data routing and real-time processing
- Receives audio chunks from speaker via WebSocket
- Routes to audio processor (transcription)
- Routes to emotion processor (sentiment analysis)
- Validates JWT at application level (WebSocket custom routes)
- Updates lastActivityTime to prevent timeouts

**Trigger**: API Gateway MESSAGE event (sendAudio action)
**Runtime**: Python 3.9+

---

### 7. **Session Status Handler** (`session-management/lambda/session_status_handler/`)
**Purpose**: Session status queries and periodic updates
- **WebSocket MODE**: Responds to getSessionStatus messages
- **EventBridge MODE**: Periodic status updates every 30 seconds
- Returns listener count and language distribution
- Sends status to speaker connection
- Supports both real-time queries and scheduled polling

**Triggers**:
- API Gateway MESSAGE event (getSessionStatus action)
- EventBridge scheduled event (every 30 seconds)
**Runtime**: Python 3.9+

---

### 8. **Timeout Handler** (`session-management/lambda/timeout_handler/`)
**Purpose**: Detects and closes idle WebSocket connections
- Scans connections for inactivity (default: 2 hours)
- Sends connectionTimeout message to client
- Closes connection via API Gateway Management API
- Triggers $disconnect handler for cleanup
- Runs every 5 minutes via EventBridge

**Trigger**: EventBridge scheduled event (every 5 minutes)
**Runtime**: Python 3.9+

---

## Audio Transcription Service (2 Lambdas)

### 9. **Audio Processor** (`audio-transcription/lambda/audio_processor/`)
**Purpose**: Real-time audio transcription using AWS Transcribe Streaming
- Receives audio chunks from refresh_handler via SQS
- Streams audio to AWS Transcribe (16kHz, PCM)
- Processes partial and final transcripts
- Calculates audio quality metrics (SNR, clipping, echo)
- Publishes transcripts to EventBridge for translation
- Sends quality warnings back to speaker via WebSocket

**Trigger**: SQS queue (audio chunks)
**Runtime**: Python 3.9+
**Key Features**:
- Streaming transcription with partial results
- Audio quality validation
- Multi-language support
- Emotion detection integration

---

### 10. **Emotion Processor** (`audio-transcription/lambda/emotion_processor/`)
**Purpose**: Real-time emotion and sentiment analysis
- Receives audio chunks from refresh_handler via SQS
- Analyzes prosodic features (pitch, energy, tempo)
- Detects emotions (happy, sad, angry, neutral, surprised)
- Provides sentiment scores and confidence levels
- Publishes emotion events to EventBridge
- Integrates with translation pipeline

**Trigger**: SQS queue (audio chunks)
**Runtime**: Python 3.9+
**Key Features**:
- Prosodic analysis
- Emotion classification
- Real-time sentiment detection
- Cross-lingual emotion support

---

## Translation Pipeline Service (1 Lambda)

### 11. **Translation Processor** (`translation-pipeline/lambda/translation_processor/`)
**Purpose**: Real-time translation of transcribed text
- Receives transcript events from EventBridge
- Translates text using AWS Translate
- Supports multiple target languages simultaneously
- Sends translations to listeners via WebSocket
- Handles partial and final transcripts
- Language-specific optimizations

**Trigger**: EventBridge event (transcript events)
**Runtime**: Python 3.9+
**Key Features**:
- Multi-language translation
- Partial result translation
- Language pair validation
- Translation quality metrics

---

## Lambda Flow Diagram

```
Speaker Audio Input
       ↓
[WebSocket] → connection_handler → refresh_handler
                                          ↓
                                    ┌─────┴─────┐
                                    ↓           ↓
                            audio_processor  emotion_processor
                                    ↓           ↓
                                    └─────┬─────┘
                                          ↓
                                    EventBridge
                                          ↓
                              translation_processor
                                          ↓
                              [WebSocket to Listeners]
```

## Lambda Categories

### Session Management (8)
- **Security**: authorizer
- **Lifecycle**: connection_handler, disconnect_handler, http_session_handler
- **Maintenance**: heartbeat_handler, timeout_handler
- **Data Flow**: refresh_handler (audio routing)
- **Status**: session_status_handler

### Audio Processing (2)
- **Transcription**: audio_processor (AWS Transcribe)
- **Sentiment**: emotion_processor (Emotion detection)

### Translation (1)
- **Translation**: translation_processor (AWS Translate)

---

## Total: 11 Lambda Functions

| Service | Lambda Count | Primary Purpose |
|---------|--------------|-----------------|
| Session Management | 8 | WebSocket lifecycle, audio routing, session state |
| Audio Transcription | 2 | Speech-to-text, emotion detection |
| Translation Pipeline | 1 | Multi-language translation |

---

## Key Integration Points

### 1. **WebSocket → Audio Pipeline**
```
refresh_handler → SQS → audio_processor
                     ↘ SQS → emotion_processor
```

### 2. **Audio → Translation Pipeline**
```
audio_processor → EventBridge → translation_processor
```

### 3. **Translation → Listeners**
```
translation_processor → API Gateway Management API → Listeners
```

### 4. **Session State Synchronization**
```
All handlers → DynamoDB (sessions, connections tables)
```

---

## Deployment Structure

### Session Management Stack
```
session-management/infrastructure/stacks/session_management_stack.py
- All 8 session management Lambdas
- WebSocket API Gateway
- HTTP API Gateway
- DynamoDB tables
- EventBridge rules
```

### Audio Transcription Stack
```
audio-transcription/infrastructure/stacks/audio_transcription_stack.py
- audio_processor Lambda
- emotion_processor Lambda
- SQS queues
- EventBridge rules
```

### Translation Pipeline Stack
```
translation-pipeline/infrastructure/stacks/translation_stack.py
- translation_processor Lambda
- EventBridge rules
```

---

## Lambda Configuration

### Common Settings
- **Runtime**: Python 3.9+
- **Architecture**: x86_64
- **Timeout**: 30 seconds (most), 60 seconds (audio/translation processors)
- **Memory**: 256 MB (handlers), 512-1024 MB (processors)
- **Layers**: shared-layer (common utilities)

### Environment Variables
Each Lambda has specific environment variables:
- DynamoDB table names
- API Gateway endpoints
- SQS queue URLs
- EventBridge bus ARNs
- AWS service configuration

---

## Monitoring & Observability

### CloudWatch Logs
Each Lambda has dedicated log group:
```
/aws/lambda/{function-name}
```

### Metrics (CloudWatch + Custom)
- Invocation count
- Duration
- Errors
- Throttles
- Custom business metrics

### X-Ray Tracing
Enabled for all Lambdas for distributed tracing

---

## Related Documentation

- Session Management: `session-management/OVERVIEW.md`
- Audio Transcription: `audio-transcription/OVERVIEW.md`
- Translation Pipeline: `translation-pipeline/docs/`
- Deployment: `session-management/DEPLOYMENT.md`
