# Real-Time Multilingual Audio Broadcasting System with Emotion Preservation
## Software Requirements Specification v2.0

***

## Document Information

**Project Name**: Real-Time Emotion-Aware Speech Translation Platform  
**Document Version**: 2.0  
**Date**: November 9, 2025  
**Status**: Ready for Development  
**Prepared For**: Software Development Team  

**Document Conventions**:
- Requirements are labeled with unique identifiers (FR-X.X for Functional, NFR-X.X for Non-Functional)
- **Bold text** indicates critical requirements
- *Italic text* indicates optional or future enhancements
- Code blocks use monospace font with syntax highlighting

***

## Executive Summary

This document specifies a cloud-based system for real-time audio streaming with live translation and emotion preservation capabilities. The system enables one authenticated speaker to broadcast audio to multiple anonymous listeners, with each listener receiving the audio translated into their preferred language while preserving the speaker's emotional expression, volume dynamics, and speaking rate.

### Key Differentiators
- **Emotion-aware translation**: Preserves whether speaker is angry/calm, loud/soft, fast/slow
- **Cost-optimized**: Only processes when listeners are active; translates once per language
- **Low latency**: 3-7 seconds end-to-end for standard mode
- **Human-readable session IDs**: Easy sharing (e.g., "golden-eagle-427")
- **Two-tier quality**: Fast mode (SSML-based) and Premium mode (emotion transfer)

***

## Table of Contents

1. [Introduction](#1-introduction)
2. [Overall Description](#2-overall-description)
3. [System Architecture](#3-system-architecture)
4. [Functional Requirements](#4-functional-requirements)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [Data Models](#6-data-models)
7. [API Specifications](#7-api-specifications)
8. [Processing Pipeline](#8-processing-pipeline)
9. [Emotion Detection & Transfer](#9-emotion-detection--transfer)
10. [Security & Authentication](#10-security--authentication)
11. [Cost Optimization](#11-cost-optimization)
12. [Testing Requirements](#12-testing-requirements)
13. [Deployment & Infrastructure](#13-deployment--infrastructure)
14. [Appendices](#14-appendices)

***

## 1. Introduction

### 1.1 Purpose

This Software Requirements Specification (SRS) defines the requirements for the Real-Time Emotion-Aware Speech Translation Platform. The document is intended for:
- Software developers implementing the system
- Quality assurance engineers testing the system
- DevOps engineers deploying the infrastructure
- Project managers tracking development progress
- Stakeholders evaluating technical feasibility

### 1.2 Scope

The system provides real-time audio broadcasting with translation and emotion preservation across multiple languages. The scope includes:

**In Scope**:
- Real-time audio capture and streaming (PCM format)
- Speech-to-text transcription (AWS Transcribe)
- Multi-language text translation (AWS Translate)
- Emotion and dynamics detection (volume, rate, emotion state)
- Emotion-aware text-to-speech synthesis (two-tier: SSML/Emotion Transfer)
- Session management with human-readable IDs
- Speaker authentication and listener anonymity
- Cost optimization through conditional processing
- WebSocket-based bidirectional communication

**Out of Scope** (v1.0):
- Video streaming
- Multi-speaker sessions (one speaker per session only)
- Recording and playback functionality
- Mobile native applications (web-based only)
- Real-time transcript display to users
- Custom language model training

### 1.3 Definitions and Acronyms

| Term | Definition |
|------|------------|
| **Speaker** | Authenticated user who creates a session and broadcasts audio |
| **Listener** | Anonymous user who joins a session to receive translated audio |
| **Session** | A broadcasting instance with one speaker and multiple listeners |
| **Emotion Transfer** | ML-based technique to preserve emotional expression across languages |
| **Dynamics** | Volume, speaking rate, and emotional characteristics of speech |
| **SSML** | Speech Synthesis Markup Language for controlling TTS output |
| **PCM** | Pulse-Code Modulation, uncompressed audio format |
| **SFU** | Selective Forwarding Unit (not used in this architecture) |
| **TTS** | Text-to-Speech synthesis |
| **ASR** | Automatic Speech Recognition (transcription) |

| Acronym | Full Form |
|---------|-----------|
| AWS | Amazon Web Services |
| API | Application Programming Interface |
| WSS | WebSocket Secure |
| JWT | JSON Web Token |
| IAM | Identity and Access Management |
| GSI | Global Secondary Index (DynamoDB) |
| RMS | Root Mean Square (energy calculation) |
| MFCC | Mel-Frequency Cepstral Coefficients |
| WPM | Words Per Minute |

### 1.4 References

- AWS Transcribe Streaming Documentation
- AWS API Gateway WebSocket API Guide
- AWS Translate Best Practices
- AWS Polly Developer Guide
- Speech Emotion Recognition Research (2025)
- Cross-lingual Prosody Transfer Papers
- librosa Audio Analysis Library Documentation
- PyTorch Torchaudio Documentation

***

## 2. Overall Description

### 2.1 Product Perspective

The system is a new, standalone cloud-based application that integrates multiple AWS services to provide emotion-aware speech translation. It operates entirely on AWS infrastructure with no on-premises components.

**System Context Diagram**:

```
┌─────────────────────────────────────────────────────────────────┐
│                         External Users                          │
├──────────────────┬──────────────────────────────────────────────┤
│   Speaker        │              Listeners                       │
│ (Authenticated)  │            (Anonymous)                       │
└────────┬─────────┴──────────────────┬───────────────────────────┘
         │                            │
         │ WSS + JWT                  │ WSS
         │ PCM Audio                  │ Receive Audio
         ▼                            ▼
┌────────────────────────────────────────────────────────────────┐
│              API Gateway WebSocket API (AWS)                   │
└────────────────────────┬───────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────┐
│                    Lambda Functions (AWS)                      │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  1. Connection Handler  2. Audio Processor               │ │
│  │  3. Emotion Detector    4. Broadcast Handler             │ │
│  └──────────────────────────────────────────────────────────┘ │
└──┬────────┬────────┬────────┬────────┬────────┬──────────────┬┘
   │        │        │        │        │        │              │
   │        │        │        │        │        │              │
   ▼        ▼        ▼        ▼        ▼        ▼              ▼
┌─────┐ ┌─────┐ ┌────────┐ ┌───────┐ ┌─────┐ ┌────────┐ ┌─────────┐
│Cogni│ │Dyna │ │Transcri│ │Transl │ │Polly│ │Emotion │ │CloudWat-│
│to   │ │moDB │ │be      │ │ate    │ │(Stan│ │Transfer│ │ch Logs  │
│User │ │     │ │Stream  │ │       │ │dard)│ │Model   │ │         │
│Pool │ │     │ │        │ │       │ │     │ │(SageMk)│ │         │
└─────┘ └─────┘ └────────┘ └───────┘ └─────┘ └────────┘ └─────────┘
```

### 2.2 Product Functions

**High-level Functions**:

1. **Session Management**: Create sessions with human-readable IDs, manage connections
2. **Audio Ingestion**: Capture PCM audio from speaker via WebSocket
3. **Emotion Analysis**: Real-time detection of volume, rate, and emotional state
4. **Transcription**: Convert audio to text with sentence-level final results
5. **Translation**: Convert text to multiple target languages (once per language)
6. **Emotion-Aware Synthesis**: Generate speech with preserved emotional characteristics
7. **Broadcasting**: Distribute translated audio to listeners by language preference
8. **Authentication**: Secure speaker authentication; anonymous listener access
9. **Cost Control**: Conditional processing based on active listener count

### 2.3 User Classes and Characteristics

#### Speaker (Primary User)
- **Technical Skill**: Moderate (can use web applications)
- **Authentication**: Required (AWS Cognito)
- **Frequency of Use**: Several times per week
- **Primary Goals**: Broadcast content to multilingual audience with emotional expression
- **Critical Success Factors**: Low latency, preserved emotion, reliable service

#### Listener (Secondary User)
- **Technical Skill**: Basic (can click a link and join)
- **Authentication**: None required
- **Frequency of Use**: Varies (event-based)
- **Primary Goals**: Receive clear, natural-sounding translated audio
- **Critical Success Factors**: Audio quality, natural emotion, minimal delay

#### System Administrator (Tertiary User)
- **Technical Skill**: Expert (DevOps/Cloud engineer)
- **Authentication**: AWS Console/IAM
- **Frequency of Use**: Daily monitoring
- **Primary Goals**: Monitor costs, performance, system health
- **Critical Success Factors**: Clear metrics, alerting, cost visibility

### 2.4 Operating Environment

**Client-Side Requirements**:
- Modern web browser (Chrome 90+, Firefox 88+, Safari 14+, Edge 90+)
- WebSocket support (WSS protocol)
- Web Audio API support for microphone access
- Minimum 1 Mbps upload (speaker) / 256 Kbps download (listener)
- JavaScript enabled

**Server-Side Environment**:
- AWS Cloud infrastructure (us-east-1 primary region)
- Serverless architecture (Lambda, API Gateway)
- Managed services (DynamoDB, Cognito, Transcribe, Translate, Polly)
- Optional: SageMaker endpoint for premium emotion transfer mode

**Network Requirements**:
- HTTPS/WSS connectivity
- Low latency network (<200ms RTT preferred)
- No corporate firewall blocking WebSocket connections

### 2.5 Design and Implementation Constraints

**Technology Constraints**:
- Must use AWS services for core functionality
- Audio format limited to PCM (16-bit, 16kHz or 44.1kHz)
- AWS Transcribe only supports final results (no partial result processing for production)
- AWS Polly SSML has limited emotion support (emphasis and prosody rate/volume only)
- WebSocket connections limited by API Gateway (10 minutes idle timeout, 2 hours max)

**Business Constraints**:
- Development budget: Serverless-first to minimize fixed costs
- Must support minimum 100 concurrent listeners per session
- Cost per listener-hour target: <$0.10
- No third-party SaaS dependencies outside AWS

**Regulatory Constraints**:
- GDPR compliance: No persistent storage of audio or transcripts
- Data residency: Process in EU regions if required by speaker
- Authentication: Industry-standard OAuth 2.0 / JWT tokens

**Language Constraints**:
- Must support AWS Translate language pairs (75+ languages)
- Must have AWS Polly neural voice support for target languages
- Emotion transfer model must support minimum 10 languages initially

### 2.6 Assumptions and Dependencies

**Assumptions**:
- Speakers have stable internet connection (minimum 1 Mbps upload)
- Audio input is relatively clean (not extremely noisy environments)
- Sessions typically last 15-60 minutes
- Average 20-50 listeners per session
- Most sessions use 2-5 target languages
- Speaker speaks at normal conversational pace (100-180 WPM)

**Dependencies**:
- AWS service availability and API stability
- Third-party emotion recognition model (or need to train/fine-tune)
- Browser support for Web Audio API
- Public npm packages (librosa.js or equivalent for client-side preprocessing)

***

## 3. System Architecture

### 3.1 High-Level Architecture

**Architecture Type**: Serverless event-driven microservices

**Core Components**:

```
┌────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                          │
│  ┌─────────────────┐              ┌─────────────────────────────┐ │
│  │ Speaker Web App │              │  Listener Web App           │ │
│  │ - Microphone    │              │  - Audio Playback           │ │
│  │ - WebSocket     │              │  - Session Joining          │ │
│  │ - Cognito Auth  │              │  - Language Selection       │ │
│  └────────┬────────┘              └──────────┬──────────────────┘ │
└───────────┼────────────────────────────────────┼───────────────────┘
            │                                    │
            └────────────────┬───────────────────┘
                             │ WSS Protocol
┌────────────────────────────┼───────────────────────────────────────┐
│                  API GATEWAY LAYER                                 │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │         API Gateway WebSocket API                            │ │
│  │  Routes: $connect, $disconnect, sendAudio                    │ │
│  └────────────────────────┬─────────────────────────────────────┘ │
└───────────────────────────┼───────────────────────────────────────┘
                            │
┌───────────────────────────┼───────────────────────────────────────┐
│               AUTHENTICATION & AUTHORIZATION                       │
│  ┌────────────────────────┴─────────────────────────────────────┐ │
│  │  Lambda Authorizer  →  Cognito User Pool                     │ │
│  │  (Validates JWT for speaker connections only)                │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────┼───────────────────────────────────────┐
│                    APPLICATION LAYER                               │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                   Lambda Functions                           │ │
│  │                                                              │ │
│  │  ┌─────────────────┐  ┌──────────────────┐                 │ │
│  │  │ Connection      │  │ Audio Processor  │                 │ │
│  │  │ Handler         │  │ - Emotion Detect │                 │ │
│  │  │ - Create Session│  │ - Transcribe     │                 │ │
│  │  │ - Join Session  │  │ - Translate      │                 │ │
│  │  │ - Store State   │  │ - Synthesize     │                 │ │
│  │  └─────────────────┘  └──────────────────┘                 │ │
│  │                                                              │ │
│  │  ┌─────────────────┐  ┌──────────────────┐                 │ │
│  │  │ Broadcast       │  │ Disconnect       │                 │ │
│  │  │ Handler         │  │ Handler          │                 │ │
│  │  │ - Fan-out Audio │  │ - Cleanup        │                 │ │
│  │  │ - Per Language  │  │ - Update Counts  │                 │ │
│  │  └─────────────────┘  └──────────────────┘                 │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────┬────────────┬───────────┬────────────┬───────────────┘
             │            │           │            │
┌────────────┼────────────┼───────────┼────────────┼───────────────┐
│                      DATA & SERVICES LAYER                        │
│            │            │           │            │                │
│  ┌─────────▼──────┐ ┌──▼────────┐ │  ┌────────▼─────────┐       │
│  │   DynamoDB     │ │  Cognito  │ │  │  AWS Transcribe  │       │
│  │                │ │  User Pool│ │  │  (Streaming API) │       │
│  │ - Sessions     │ └───────────┘ │  └──────────────────┘       │
│  │ - Connections  │               │                              │
│  └────────────────┘               │                              │
│                          ┌────────▼──────────┐                   │
│                          │  AWS Translate    │                   │
│                          └────────┬──────────┘                   │
│                                   │                              │
│  ┌────────────────────────────────┼──────────────────────────┐  │
│  │         TEXT-TO-SPEECH SYNTHESIS                          │  │
│  │                                 │                          │  │
│  │  ┌──────────────────┐  ┌───────▼────────────────────┐    │  │
│  │  │  Standard Mode   │  │    Premium Mode            │    │  │
│  │  │                  │  │                            │    │  │
│  │  │  AWS Polly       │  │  Emotion Transfer Model    │    │  │
│  │  │  + SSML          │  │  (SageMaker Endpoint)      │    │  │
│  │  │  Enhancement     │  │  - Neural TTS              │    │  │
│  │  │                  │  │  - Emotion Preservation    │    │  │
│  │  │  Latency: <4s    │  │  Latency: 5-8s             │    │  │
│  │  └──────────────────┘  └────────────────────────────┘    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Monitoring & Logging                        │  │
│  │  - CloudWatch Logs     - CloudWatch Metrics              │  │
│  │  - CloudWatch Alarms   - Cost Explorer                   │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Descriptions

#### 3.2.1 API Gateway WebSocket API
- **Purpose**: Manages persistent bidirectional connections with clients
- **Routes**: $connect, $disconnect, sendAudio
- **Responsibilities**: 
  - Accept WebSocket connections
  - Route messages to Lambda functions
  - Invoke Lambda authorizer for speaker authentication
  - Provide connection management API for broadcasting

#### 3.2.2 Lambda Authorizer
- **Purpose**: Authenticate speaker connections
- **Input**: JWT token from query string
- **Output**: IAM policy (allow/deny)
- **Validation**: Token signature, expiration, issuer

#### 3.2.3 Connection Handler Lambda
- **Purpose**: Handle $connect and manage session lifecycle
- **Responsibilities**:
  - Create new sessions (speakers) with human-readable IDs
  - Join existing sessions (listeners)
  - Store connection metadata in DynamoDB
  - Update listener counts
  - Validate session existence

#### 3.2.4 Audio Processor Lambda
- **Purpose**: Core audio processing pipeline
- **Responsibilities**:
  - Receive PCM audio chunks from speaker
  - Extract emotion and dynamics features
  - Stream audio to AWS Transcribe
  - Filter for final results (IsPartial: false)
  - Coordinate translation and synthesis
  - Trigger broadcast

#### 3.2.5 Broadcast Handler Lambda
- **Purpose**: Fan-out translated audio to listeners
- **Responsibilities**:
  - Query listeners by language from DynamoDB
  - Use API Gateway Management API to send audio
  - Handle connection errors (GoneException)
  - Clean up stale connections

#### 3.2.6 Disconnect Handler Lambda
- **Purpose**: Clean up on connection close
- **Responsibilities**:
  - Remove connection from DynamoDB
  - Decrement listener count
  - End session if speaker disconnects
  - Clean up orphaned resources

#### 3.2.7 Emotion Detection Module
- **Purpose**: Analyze audio for emotional and dynamic characteristics
- **Technology**: librosa + pre-trained LSTM model
- **Features Extracted**:
  - Emotion classification (angry, calm, happy, sad, neutral, etc.)
  - Volume level (whisper, quiet, normal, loud, very loud)
  - Speaking rate (WPM)
  - Energy contour

#### 3.2.8 Synthesis Router
- **Purpose**: Choose between Standard and Premium TTS modes
- **Standard Mode**: AWS Polly + dynamically generated SSML
- **Premium Mode**: Emotion Transfer Model on SageMaker endpoint
- **Selection Criteria**: Session quality tier or per-request flag

### 3.3 Data Flow Diagram

**Complete Processing Flow**:

```
1. Speaker connects with JWT token
   ↓
2. Lambda Authorizer validates token
   ↓
3. Connection Handler creates session
   ↓ (session ID: "golden-eagle-427")
4. Speaker shares session ID with audience
   ↓
5. Listeners connect with session ID + target language
   ↓
6. Connection Handler joins them to session
   ↓
7. Speaker starts sending PCM audio chunks
   ↓
8. Audio Processor Lambda receives audio
   ↓
9. Emotion Detector analyzes audio
   ↓ (detects: angry, loud, fast)
10. Check listenerCount > 0? 
    ↓ YES → continue
    ↓ NO → skip processing (save cost)
11. Stream audio to AWS Transcribe
    ↓
12. Receive transcript events
    ↓
13. Filter: IsPartial == false?
    ↓ YES → continue
    ↓ NO → ignore, wait for next
14. Get unique target languages from DynamoDB
    ↓ (e.g., ["es", "fr", "de"])
15. For each target language:
    ├─ a. Translate text (AWS Translate)
    ├─ b. Generate emotion-aware SSML or call SageMaker
    ├─ c. Synthesize audio (Polly or Emotion Transfer)
    ├─ d. Query listeners for this language
    └─ e. Broadcast audio to all listeners
    ↓
16. Listeners receive and play translated audio
    ↓
17. Loop back to step 7 for next audio chunk
    ↓
18. Speaker disconnects
    ↓
19. Disconnect Handler ends session
    ↓
20. All listeners disconnected automatically
```

### 3.4 Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | HTML5 + JavaScript | Web-based speaker/listener applications |
| **Audio API** | Web Audio API | Microphone capture and audio playback |
| **Communication** | WebSocket (WSS) | Real-time bidirectional messaging |
| **API Gateway** | AWS API Gateway (WebSocket) | Connection management and routing |
| **Compute** | AWS Lambda (Python 3.11) | Serverless processing |
| **Authentication** | Amazon Cognito User Pools | Speaker authentication |
| **Database** | Amazon DynamoDB | Session and connection state |
| **Transcription** | Amazon Transcribe Streaming | Speech-to-text |
| **Translation** | Amazon Translate | Multi-language translation |
| **TTS (Standard)** | Amazon Polly Neural | SSML-enhanced synthesis |
| **TTS (Premium)** | SageMaker Endpoint | Emotion transfer model |
| **Audio Processing** | librosa (Python) | Feature extraction |
| **ML Framework** | PyTorch / TensorFlow | Emotion recognition model |
| **Monitoring** | CloudWatch Logs/Metrics | Observability |
| **IaC** | AWS CDK or CloudFormation | Infrastructure as code |

***

## 4. Functional Requirements

### 4.1 Session Management

**FR-1.1**: The system SHALL allow authenticated speakers to create new broadcasting sessions.

**FR-1.2**: The system SHALL generate unique human-readable session identifiers in the format `{adjective}-{noun}-{number}` (e.g., "swift-eagle-427").

**FR-1.3**: Session identifiers SHALL be:
- 100+ adjectives (positive, simple words)
- 100+ nouns (common, concrete objects)
- 2-4 digit random numbers
- Case-insensitive for user convenience
- Checked for uniqueness against active sessions

**FR-1.4**: The system SHALL allow anonymous listeners to join existing sessions using only the session ID.

**FR-1.5**: Listeners SHALL specify their target language when joining (ISO 639-1 code).

**FR-1.6**: The system SHALL validate session existence before allowing listener connections.

**FR-1.7**: Sessions SHALL automatically terminate when the speaker disconnects.

**FR-1.8**: The system SHALL track the count of active listeners per session in real-time.

**FR-1.9**: Sessions SHALL persist for maximum 3 hours or until speaker disconnects (whichever comes first).

**FR-1.10**: The system SHALL reject session ID creation if it contains words from a profanity blacklist.

### 4.2 Audio Streaming

**FR-2.1**: The system SHALL accept PCM audio format (16-bit, 16kHz or 44.1kHz) from speakers via WebSocket.

**FR-2.2**: The system SHALL support audio chunk sizes of 1-5 seconds for optimal latency/quality balance.

**FR-2.3**: The system SHALL stream audio continuously until the speaker disconnects or stops transmission.

**FR-2.4**: The system SHALL broadcast synthesized audio to listeners in PCM or MP3 format.

**FR-2.5**: The system SHALL handle network jitter and packet loss gracefully without crashing.

### 4.3 Speech Transcription

**FR-3.1**: The system SHALL transcribe speaker audio to text using AWS Transcribe Streaming API.

**FR-3.2**: The system SHALL process only final transcription results (IsPartial: false), not partial results.

**FR-3.3**: The system SHALL segment transcriptions on sentence boundaries (natural pauses).

**FR-3.4**: The system SHALL support source languages available in AWS Transcribe (50+ languages).

**FR-3.5**: The system SHALL include punctuation in transcribed text for natural synthesis.

### 4.4 Translation

**FR-4.1**: The system SHALL translate transcribed text using AWS Translate.

**FR-4.2**: The system SHALL translate text only for target languages with active listeners.

**FR-4.3**: The system SHALL translate each sentence exactly once per unique target language (not per listener).

**FR-4.4**: The system SHALL support all AWS Translate language pairs (75+ languages).

**FR-4.5**: The system SHALL preserve original meaning and context during translation.

### 4.5 Emotion and Dynamics Detection

**FR-5.1**: The system SHALL analyze speaker audio in real-time to detect:
- **Emotional state**: angry, calm, happy, sad, neutral, fearful, surprised, disgusted
- **Volume level**: whisper, quiet, normal, loud, very loud
- **Speaking rate**: words per minute (WPM)

**FR-5.2**: The system SHALL extract audio features including:
- RMS energy (frame-by-frame volume)
- MFCCs (Mel-frequency cepstral coefficients)
- Spectral features (centroid, rolloff)
- Prosodic features (pitch, rhythm patterns)

**FR-5.3**: The system SHALL classify emotions using a pre-trained machine learning model with minimum 80% accuracy.

**FR-5.4**: The system SHALL quantify emotion intensity (confidence score 0.0-1.0).

**FR-5.5**: The system SHALL classify speaking rate into categories: very slow (<100 WPM), slow (100-130), normal (130-170), fast (170-200), very fast (>200).

**FR-5.6**: The system SHALL perform emotion detection within 100ms per audio chunk to maintain real-time performance.

### 4.6 Emotion-Aware Speech Synthesis

**FR-6.1**: The system SHALL provide two synthesis modes:
- **Standard Mode**: AWS Polly with dynamically generated SSML
- **Premium Mode**: Emotion Transfer Model for higher fidelity

**FR-6.2**: The system SHALL preserve speaking dynamics in synthesized output:
- **Volume**: Map detected volume level to synthesis amplitude
- **Rate**: Map detected speaking rate to synthesis speed
- **Emotion**: Map detected emotion to expressive synthesis controls

**FR-6.3**: In Standard Mode, the system SHALL:
- Generate SSML tags based on detected emotion and dynamics
- Apply `<prosody rate="...">` for speaking rate control
- Apply `<prosody volume="...">` for volume control (where supported)
- Apply `<emphasis level="strong">` for high-emotion segments
- Insert `<break time="...ms"/>` at natural phrase boundaries

**FR-6.4**: In Premium Mode, the system SHALL:
- Use emotion transfer model to preserve actual emotional tone
- Pass reference audio to model for style extraction
- Synthesize with target language while maintaining source emotion
- Support minimum 10 languages with emotion transfer

**FR-6.5**: The system SHALL allow session creators to select quality tier (Standard or Premium) at session creation.

**FR-6.6**: The system SHALL gracefully fall back to Standard Mode if Premium Mode fails or times out.

### 4.7 Audio Broadcasting

**FR-7.1**: The system SHALL broadcast synthesized audio to all listeners subscribed to each target language.

**FR-7.2**: The system SHALL query listeners by language efficiently using DynamoDB GSI.

**FR-7.3**: The system SHALL send audio to listeners using API Gateway Management API (PostToConnection).

**FR-7.4**: The system SHALL handle connection failures gracefully:
- Catch GoneException for disconnected clients
- Remove stale connections from database
- Continue broadcasting to remaining listeners

**FR-7.5**: The system SHALL broadcast to all listeners in parallel (not sequentially).

**FR-7.6**: The system SHALL not buffer more than 10 seconds of audio to maintain low latency.

### 4.8 Authentication and Authorization

**FR-8.1**: Speakers MUST authenticate using AWS Cognito before creating sessions.

**FR-8.2**: The system SHALL validate JWT tokens on WebSocket $connect for speaker routes.

**FR-8.3**: Listeners SHALL NOT require authentication to join sessions.

**FR-8.4**: Only authenticated speakers SHALL be permitted to send audio data.

**FR-8.5**: The system SHALL return appropriate error codes for authentication failures:
- 401 Unauthorized: Invalid or expired token
- 403 Forbidden: Valid token but insufficient permissions

**FR-8.6**: JWT tokens SHALL have maximum validity of 24 hours.

### 4.9 Cost Optimization

**FR-9.1**: The system SHALL NOT invoke AWS Transcribe when listenerCount == 0 (no active listeners).

**FR-9.2**: The system SHALL invoke AWS Translate exactly once per unique target language per sentence.

**FR-9.3**: The system SHALL invoke TTS (Polly or emotion model) exactly once per unique target language per sentence.

**FR-9.4**: The system SHALL track AWS service usage per authenticated speaker for billing/quota purposes.

**FR-9.5**: The system SHALL implement atomic counter updates for listener count to prevent race conditions.

**FR-9.6**: The system SHALL clean up sessions and connections within 5 minutes of disconnection to prevent resource leaks.

***

## 5. Non-Functional Requirements

### 5.1 Performance Requirements

**NFR-1.1**: End-to-end latency from speaker audio to listener playback SHALL be:
- **Standard Mode**: 3-5 seconds (target), 7 seconds (maximum)
- **Premium Mode**: 5-8 seconds (target), 10 seconds (maximum)

**NFR-1.2**: Emotion detection SHALL complete within 100ms per audio chunk.

**NFR-1.3**: The system SHALL process transcription results within 500ms of receiving final result from Transcribe.

**NFR-1.4**: Translation SHALL complete within 300ms per sentence per language.

**NFR-1.5**: Standard Mode synthesis (Polly + SSML) SHALL complete within 500ms per sentence.

**NFR-1.6**: Premium Mode synthesis SHALL complete within 1.5 seconds per sentence.

**NFR-1.7**: Broadcasting to 100 listeners SHALL complete within 2 seconds.

**NFR-1.8**: WebSocket message delivery SHALL have 99th percentile latency <100ms.

**NFR-1.9**: Database queries SHALL complete within 50ms (p99).

**NFR-1.10**: The system SHALL handle audio chunks arriving every 1-5 seconds without queuing delays.

### 5.2 Scalability Requirements

**NFR-2.1**: The system SHALL support unlimited concurrent listeners per session (AWS API Gateway limit: 100K+ connections).

**NFR-2.2**: The system SHALL support minimum 100 concurrent sessions.

**NFR-2.3**: Lambda functions SHALL auto-scale to handle concurrent invocations without throttling.

**NFR-2.4**: DynamoDB tables SHALL use on-demand capacity mode or auto-scaling for variable load.

**NFR-2.5**: The system SHALL handle traffic spikes of 10x normal load without degradation.

**NFR-2.6**: SageMaker endpoint (Premium Mode) SHALL support minimum 10 concurrent requests per second.

### 5.3 Reliability and Availability

**NFR-3.1**: The system SHALL achieve 99.5% uptime (monthly).

**NFR-3.2**: The system SHALL handle individual service failures gracefully:
- Transcribe failure: Notify speaker, maintain session
- Translate failure: Skip affected language, continue others
- TTS failure: Fall back to Standard Mode or notify listeners
- Database failure: Retry with exponential backoff

**NFR-3.3**: WebSocket connections SHALL automatically reconnect on network interruptions.

**NFR-3.4**: The system SHALL clean up orphaned resources automatically.

**NFR-3.5**: Lambda functions SHALL have timeout of 30 seconds with retry logic.

**NFR-3.6**: The system SHALL handle connection drops without losing in-flight audio (buffer 5 seconds).

### 5.4 Security Requirements

**NFR-4.1**: All data in transit SHALL use TLS 1.2 or higher (WSS protocol).

**NFR-4.2**: JWT tokens SHALL be validated for signature, expiration, and issuer.

**NFR-4.3**: Audio data SHALL NOT be persisted to disk (ephemeral processing only).

**NFR-4.4**: Transcripts SHALL NOT be stored beyond processing (transient only).

**NFR-4.5**: Connection IDs SHALL be treated as sensitive data (not exposed in logs).

**NFR-4.6**: Lambda execution roles SHALL follow principle of least privilege.

**NFR-4.7**: API Gateway SHALL enforce rate limiting: 1000 messages per minute per connection.

**NFR-4.8**: The system SHALL prevent injection attacks by sanitizing all text inputs.

**NFR-4.9**: SSML generation SHALL escape reserved XML characters (&, <, >, ", ').

**NFR-4.10**: The system SHALL implement CORS policies for web client access.

### 5.5 Usability Requirements

**NFR-5.1**: Session IDs SHALL be easily memorable and shareable (human-readable format).

**NFR-5.2**: Speaker SHALL receive session ID within 2 seconds of connection.

**NFR-5.3**: Listeners SHALL be able to join by entering only session ID (no additional credentials).

**NFR-5.4**: Error messages SHALL be clear and actionable for end users.

**NFR-5.5**: The system SHALL provide real-time feedback on connection status.

**NFR-5.6**: Audio quality SHALL be comparable to phone call quality (minimum 16kHz sampling).

### 5.6 Maintainability Requirements

**NFR-6.1**: Code SHALL follow PEP 8 style guide for Python.

**NFR-6.2**: All functions SHALL have docstrings with parameter and return type descriptions.

**NFR-6.3**: Infrastructure SHALL be defined as code (AWS CDK or CloudFormation).

**NFR-6.4**: The system SHALL have comprehensive logging at INFO level for normal operations.

**NFR-6.5**: All errors SHALL be logged with full context (stack trace, request ID, session ID).

**NFR-6.6**: Configuration SHALL be externalized (environment variables or Parameter Store).

**NFR-6.7**: The system SHALL support zero-downtime deployments.

### 5.7 Cost Requirements

**NFR-7.1**: Cost per listener-hour SHALL be <$0.10 in Standard Mode.

**NFR-7.2**: Cost per listener-hour SHALL be <$0.25 in Premium Mode.

**NFR-7.3**: Idle sessions (no listeners) SHALL incur zero AWS service costs (Transcribe, Translate, TTS).

**NFR-7.4**: The system SHALL provide cost visibility per speaker/session.

**NFR-7.5**: CloudWatch Logs retention SHALL be 7 days to control storage costs.

***

## 6. Data Models

### 6.1 DynamoDB Tables

#### 6.1.1 Sessions Table

**Table Name**: `Sessions`

**Primary Key**: `sessionId` (String, Partition Key)

**Attributes**:

| Attribute | Type | Description | Required |
|-----------|------|-------------|----------|
| sessionId | String | Human-readable ID (e.g., "golden-eagle-427") | Yes |
| speakerConnectionId | String | WebSocket connection ID of speaker | Yes |
| sourceLanguage | String | ISO 639-1 code (e.g., "en") | Yes |
| createdAt | Number | Unix timestamp (milliseconds) | Yes |
| isActive | Boolean | Session active status | Yes |
| listenerCount | Number | Count of active listeners | Yes |
| qualityTier | String | "standard" or "premium" | Yes |
| expiresAt | Number | TTL for auto-cleanup (Unix timestamp) | Yes |

**Indexes**: None (sessionId is primary key)

**TTL**: Enabled on `expiresAt` attribute (auto-delete after 3 hours)

**Capacity**: On-demand mode

**Example Item**:
```json
{
  "sessionId": "golden-eagle-427",
  "speakerConnectionId": "L0SM9cOFvHcCIhw=",
  "sourceLanguage": "en",
  "createdAt": 1699500000000,
  "isActive": true,
  "listenerCount": 15,
  "qualityTier": "standard",
  "expiresAt": 1699510800000
}
```

#### 6.1.2 Connections Table

**Table Name**: `Connections`

**Primary Key**: `connectionId` (String, Partition Key)

**Global Secondary Index**: `sessionId-targetLanguage-index`
- Partition Key: `sessionId` (String)
- Sort Key: `targetLanguage` (String)
- Projection: ALL

**Attributes**:

| Attribute | Type | Description | Required |
|-----------|------|-------------|----------|
| connectionId | String | WebSocket connection ID | Yes |
| sessionId | String | References Sessions table | Yes |
| targetLanguage | String | ISO 639-1 code (e.g., "es") | Conditional* |
| role | String | "speaker" or "listener" | Yes |
| connectedAt | Number | Unix timestamp (milliseconds) | Yes |
| ttl | Number | TTL for auto-cleanup | Yes |

*Required for listeners, not applicable for speakers

**Capacity**: On-demand mode

**Example Items**:
```json
// Speaker connection
{
  "connectionId": "L0SM9cOFvHcCIhw=",
  "sessionId": "golden-eagle-427",
  "role": "speaker",
  "connectedAt": 1699500000000,
  "ttl": 1699510800
}

// Listener connection
{
  "connectionId": "K3Rx8bNEuGdDJkx=",
  "sessionId": "golden-eagle-427",
  "targetLanguage": "es",
  "role": "listener",
  "connectedAt": 1699500120000,
  "ttl": 1699510800
}
```

### 6.2 Session ID Generation Algorithm

**Word Lists**:
- Adjectives: 100+ words (e.g., swift, golden, bright, calm, noble, proud, wise...)
- Nouns: 100+ words (e.g., eagle, mountain, river, forest, ocean, star, tiger...)
- Numbers: Random 2-4 digits (10-9999)

**Blacklist**: Maintain profanity blacklist for both adjectives and nouns

**Uniqueness**: Check against active sessions in DynamoDB before confirming

**Format**: `{adjective}-{noun}-{number}`

**Case Handling**: Store lowercase in database, accept any case from users

**Total Combinations**: 100 × 100 × 9990 ≈ 100 million unique IDs

### 6.3 Data Flow for Queries

#### Query 1: Get Active Target Languages for Session

```python
response = dynamodb.query(
    TableName='Connections',
    IndexName='sessionId-targetLanguage-index',
    KeyConditionExpression='sessionId = :sid',
    FilterExpression='#role = :role',
    ExpressionAttributeNames={'#role': 'role'},
    ExpressionAttributeValues={
        ':sid': 'golden-eagle-427',
        ':role': 'listener'
    }
)

languages = set(item['targetLanguage'] for item in response['Items'])
# Result: ['es', 'fr', 'de']
```

#### Query 2: Get Listeners for Specific Language

```python
response = dynamodb.query(
    TableName='Connections',
    IndexName='sessionId-targetLanguage-index',
    KeyConditionExpression='sessionId = :sid AND targetLanguage = :lang',
    ExpressionAttributeValues={
        ':sid': 'golden-eagle-427',
        ':lang': 'es'
    }
)

connection_ids = [item['connectionId'] for item in response['Items']]
# Result: ['K3Rx8bNEuGdDJkx=', 'M7Ty2fQGwIdELnz=', ...]
```

#### Update 1: Increment Listener Count

```python
dynamodb.update_item(
    TableName='Sessions',
    Key={'sessionId': 'golden-eagle-427'},
    UpdateExpression='ADD listenerCount :inc',
    ExpressionAttributeValues={':inc': 1}
)
```

#### Update 2: Decrement Listener Count (Atomic)

```python
dynamodb.update_item(
    TableName='Sessions',
    Key={'sessionId': 'golden-eagle-427'},
    UpdateExpression='ADD listenerCount :dec',
    ExpressionAttributeValues={':dec': -1}
)
```

***

## 7. API Specifications

### 7.1 WebSocket Connection Endpoints

**Base URL**: `wss://{api-id}.execute-api.{region}.amazonaws.com/{stage}`

Example: `wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod`

#### 7.1.1 $connect Route (Speaker)

**Purpose**: Authenticate speaker and create new session

**Query Parameters**:
```
?token=<JWT_TOKEN>
&action=createSession
&sourceLanguage=<ISO_639_1_CODE>
&qualityTier=<standard|premium>
```

**Authorization**: Lambda Authorizer validates JWT token

**Request Example**:
```
wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod?token=eyJhbGc...&action=createSession&sourceLanguage=en&qualityTier=standard
```

**Response** (WebSocket message after connection):
```json
{
  "type": "sessionCreated",
  "sessionId": "golden-eagle-427",
  "sourceLanguage": "en",
  "qualityTier": "standard",
  "connectionId": "L0SM9cOFvHcCIhw="
}
```

**Error Responses**:
```json
// Unauthorized (401)
{
  "message": "Unauthorized",
  "statusCode": 401
}

// Invalid Parameters (400)
{
  "type": "error",
  "message": "Invalid source language code",
  "code": "INVALID_LANGUAGE"
}
```

#### 7.1.2 $connect Route (Listener)

**Purpose**: Join existing session as anonymous listener

**Query Parameters**:
```
?sessionId=<SESSION_ID>
&targetLanguage=<ISO_639_1_CODE>
&action=joinSession
```

**Authorization**: None (anonymous)

**Request Example**:
```
wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod?sessionId=golden-eagle-427&targetLanguage=es&action=joinSession
```

**Response** (WebSocket message after connection):
```json
{
  "type": "sessionJoined",
  "sessionId": "golden-eagle-427",
  "targetLanguage": "es",
  "connectionId": "K3Rx8bNEuGdDJkx=",
  "sourceLanguage": "en"
}
```

**Error Responses**:
```json
// Session Not Found (404)
{
  "type": "error",
  "message": "Session not found or inactive",
  "code": "SESSION_NOT_FOUND"
}

// Invalid Language (400)
{
  "type": "error",
  "message": "Target language not supported",
  "code": "UNSUPPORTED_LANGUAGE"
}
```

#### 7.1.3 sendAudio Route (Custom Route)

**Purpose**: Receive audio chunks from speaker

**Authorization**: Connection must be authenticated speaker role

**Message Format** (JSON):
```json
{
  "action": "sendAudio",
  "audioData": "base64-encoded-pcm-audio-bytes",
  "timestamp": 1699500123456,
  "chunkId": "chunk-001"
}
```

**Audio Data Encoding**:
- Format: PCM (16-bit signed integers, little-endian)
- Sample Rate: 16000 Hz or 44100 Hz
- Channels: Mono (1 channel)
- Chunk Duration: 1-5 seconds recommended
- Base64 Encoding: Standard base64 encoding of raw PCM bytes

**Response**: None (fire-and-forget)

**Error Handling**:
```json
// Not Authorized to Send Audio (403)
{
  "type": "error",
  "message": "Only speakers can send audio",
  "code": "FORBIDDEN"
}

// Audio Format Invalid (400)
{
  "type": "error",
  "message": "Invalid audio format or encoding",
  "code": "INVALID_AUDIO"
}
```

#### 7.1.4 receiveAudio Message (Server → Listener)

**Purpose**: Deliver translated synthesized audio to listeners

**Message Format** (JSON):
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

**Audio Format**:
- PCM or MP3 (specified in "format" field)
- Sample rate matches source or standard rate
- Mono audio

**Client Handling**: Decode base64, feed to Web Audio API for playback

#### 7.1.5 $disconnect Route

**Trigger**: Automatic when WebSocket connection closes

**Processing**:
- Remove connection from Connections table
- If speaker: End session, disconnect all listeners
- If listener: Decrement listenerCount
- Cleanup resources

**No explicit request/response**: Triggered by connection close event

### 7.2 API Gateway Management API (Server-Side)

**Used By**: Lambda functions to send messages to connected clients

**Endpoint**: `https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/@connections/{connectionId}`

**Example Usage** (Python boto3):
```python
import boto3

api_gateway = boto3.client(
    'apigatewaymanagementapi',
    endpoint_url=f'https://{api_id}.execute-api.{region}.amazonaws.com/{stage}'
)

# Send audio to listener
api_gateway.post_to_connection(
    ConnectionId='K3Rx8bNEuGdDJkx=',
    Data=json.dumps({
        'type': 'audio',
        'audioData': base64_audio,
        'format': 'pcm',
        'sampleRate': 16000
    })
)
```

**Error Handling**:
```python
from botocore.exceptions import ClientError

try:
    api_gateway.post_to_connection(ConnectionId=conn_id, Data=data)
except ClientError as e:
    if e.response['Error']['Code'] == 'GoneException':
        # Connection no longer exists - remove from database
        remove_stale_connection(conn_id)
```

***

## 8. Processing Pipeline

### 8.1 Complete Audio Processing Flow

**Pipeline Diagram**:

```
┌──────────────────────────────────────────────────────────────────┐
│                    AUDIO PROCESSING PIPELINE                     │
└──────────────────────────────────────────────────────────────────┘

┌─────────────┐
│ Speaker     │
│ sends PCM   │
│ audio chunk │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│ STEP 1: Receive Audio Chunk                                     │
│ - Decode base64                                                  │
│ - Validate format (PCM, 16-bit, mono)                          │
│ - Extract audio waveform                                        │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│ STEP 2: Check Listener Count                                    │
│ Query: session.listenerCount from DynamoDB                      │
│ IF listenerCount == 0:                                          │
│    RETURN (skip processing - COST OPTIMIZATION)                 │
└──────┬───────────────────────────────────────────────────────────┘
       │ listenerCount > 0
       ▼
┌──────────────────────────────────────────────────────────────────┐
│ STEP 3: Emotion & Dynamics Detection (PARALLEL)                 │
│ Extract features:                                               │
│ - MFCCs, spectral features, RMS energy                         │
│ - Detect emotion: ML model → "angry" (0.87 confidence)        │
│ - Calculate volume: RMS → "loud" (-8 dB)                      │
│ - Estimate rate: Onset detection → 185 WPM ("fast")           │
│ Output: {emotion, intensity, volume, rate, energy_contour}     │
│ Duration: ~100ms                                                │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│ STEP 4: Transcription (AWS Transcribe Streaming)                │
│ - Send audio chunk to Transcribe stream                        │
│ - Receive transcript events                                     │
│ - Filter: IF IsPartial == true: IGNORE                         │
│ - Process only: IsPartial == false (final result)              │
│ Output: "Hello everyone, this is very important news."         │
│ Duration: 1-3 seconds (depends on pause/sentence boundary)      │
└──────┬───────────────────────────────────────────────────────────┘
       │ Final result received
       ▼
┌──────────────────────────────────────────────────────────────────┐
│ STEP 5: Get Active Target Languages                             │
│ Query DynamoDB:                                                 │
│   SELECT DISTINCT targetLanguage                                │
│   FROM Connections                                              │
│   WHERE sessionId = "golden-eagle-427"                         │
│   AND role = "listener"                                         │
│ Output: ["es", "fr", "de"]                                      │
│ Duration: ~20ms                                                 │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│ STEP 6: Translation Loop (ONCE PER LANGUAGE)                    │
│ FOR EACH target_lang IN ["es", "fr", "de"]:                    │
│                                                                  │
│   ┌────────────────────────────────────────────────────────┐   │
│   │ 6a. Translate Text (AWS Translate)                    │   │
│   │ Input: "Hello everyone, this is very important news." │   │
│   │ Source: "en", Target: "es"                            │   │
│   │ Output: "Hola a todos, estas son noticias muy..."    │   │
│   │ Duration: ~200ms                                       │   │
│   └────────┬───────────────────────────────────────────────┘   │
│            │                                                     │
│            ▼                                                     │
│   ┌────────────────────────────────────────────────────────┐   │
│   │ 6b. Choose Synthesis Mode                             │   │
│   │ IF session.qualityTier == "premium":                  │   │
│   │    → PREMIUM MODE (Emotion Transfer)                  │   │
│   │ ELSE:                                                  │   │
│   │    → STANDARD MODE (Polly + SSML)                    │   │
│   └────────┬───────────────────────────────────────────────┘   │
│            │                                                     │
│            ├──────────────┬──────────────────────────────────┐  │
│            │              │                                  │  │
│            ▼              ▼                                  │  │
│   ┌────────────────┐ ┌─────────────────────────────────┐   │  │
│   │ STANDARD MODE  │ │ PREMIUM MODE                     │   │  │
│   │                │ │                                  │   │  │
│   │ Generate SSML  │ │ Call SageMaker Emotion Transfer │   │  │
│   │ from dynamics: │ │ - Send translated text          │   │  │
│   │                │ │ - Send reference audio chunk    │   │  │
│   │ <speak>        │ │ - Send emotion: "angry"         │   │  │
│   │ <prosody       │ │ - Send rate: 185 WPM            │   │  │
│   │  rate="fast"   │ │ - Send volume: "loud"           │   │  │
│   │  volume="loud">│ │ Returns: Synthesized audio with │   │  │
│   │ <emphasis>     │ │          emotion preserved      │   │  │
│   │  Hola a todos  │ │ Duration: ~1500ms               │   │  │
│   │ </emphasis>    │ │                                  │   │  │
│   │ </prosody>     │ │                                  │   │  │
│   │ </speak>       │ │                                  │   │  │
│   │                │ │                                  │   │  │
│   │ Call Polly:    │ │                                  │   │  │
│   │ synthesize(    │ │                                  │   │  │
│   │   ssml,        │ │                                  │   │  │
│   │   voice="es"   │ │                                  │   │  │
│   │ )              │ │                                  │   │  │
│   │ Duration: ~400 │ │                                  │   │  │
│   └────────┬───────┘ └──────────┬──────────────────────┘   │  │
│            │                    │                          │  │
│            └────────┬───────────┘                          │  │
│                     │                                      │  │
│                     ▼                                      │  │
│   ┌────────────────────────────────────────────────────────┐  │
│   │ 6c. Get Listeners for This Language                   │  │
│   │ Query DynamoDB:                                        │  │
│   │   SELECT connectionId                                  │  │
│   │   FROM Connections (GSI)                              │  │
│   │   WHERE sessionId = "golden-eagle-427"                │  │
│   │   AND targetLanguage = "es"                           │  │
│   │ Output: ["K3Rx...", "M7Ty...", "P9Zx..."]            │  │
│   │ Duration: ~30ms                                        │  │
│   └────────┬───────────────────────────────────────────────┘  │
│            │                                                   │
│            ▼                                                   │
│   ┌────────────────────────────────────────────────────────┐  │
│   │ 6d. Broadcast Audio (PARALLEL)                        │  │
│   │ FOR EACH connection_id IN ["K3Rx...", "M7Ty..."]:    │  │
│   │   TRY:                                                 │  │
│   │     api_gateway.post_to_connection(                   │  │
│   │       ConnectionId=connection_id,                     │  │
│   │       Data=audio_stream                               │  │
│   │     )                                                  │  │
│   │   EXCEPT GoneException:                               │  │
│   │     remove_stale_connection(connection_id)            │  │
│   │ Duration: ~2000ms for 100 listeners                   │  │
│   └────────────────────────────────────────────────────────┘  │
│                                                                │
│ END FOR (next language)                                        │
└────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│ STEP 7: Wait for Next Audio Chunk                               │
│ Loop back to STEP 1                                             │
└──────────────────────────────────────────────────────────────────┘
```

### 8.2 Latency Breakdown

**Standard Mode (Target: 3-5 seconds)**:

| Stage | Duration | Notes |
|-------|----------|-------|
| Audio chunk capture | 1-3s | Depends on sentence length |
| Emotion detection | 100ms | Parallel with transcription |
| Transcription | 500-1500ms | Wait for final result |
| Get active languages | 20ms | DynamoDB query |
| Translate (per lang) | 200ms | Parallelizable across languages |
| Generate SSML | 50ms | String manipulation |
| Polly synthesis | 400ms | Per language |
| Query listeners | 30ms | Per language |
| Broadcast | 500-2000ms | Depends on listener count |
| **Total** | **3.8-7.3s** | End-to-end |

**Premium Mode (Target: 5-8 seconds)**:

| Stage | Duration | Difference from Standard |
|-------|----------|--------------------------|
| ... (same up to synthesis) | ... | ... |
| Emotion Transfer (SageMaker) | 1500ms | +1100ms vs Polly |
| **Total** | **5.0-8.5s** | +1.2s vs Standard |

### 8.3 Error Handling in Pipeline

**Error Scenarios**:

1. **Transcribe fails**: Log error, notify speaker, skip this chunk, continue with next
2. **Translate fails for one language**: Skip that language, continue with others
3. **TTS fails (Polly or model)**: Fall back to Standard Mode if in Premium; notify listeners if both fail
4. **Listener connection gone**: Catch GoneException, remove from DB, continue broadcasting to others
5. **DynamoDB throttling**: Retry with exponential backoff (max 3 retries)
6. **Lambda timeout (30s)**: This indicates a serious problem; alert operations team

***

## 9. Emotion Detection & Transfer

### 9.1 Emotion Detection Module

#### 9.1.1 Feature Extraction

**Implementation** (Python with librosa):

```python
import librosa
import numpy as np

class EmotionFeatureExtractor:
    """
    Extracts audio features for emotion recognition.
    """
    
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
    
    def extract_features(self, audio_waveform):
        """
        Extract comprehensive features from audio chunk.
        
        Args:
            audio_waveform: numpy array of audio samples
            
        Returns:
            dict with feature arrays
        """
        # 1. MFCCs (Mel-frequency cepstral coefficients)
        mfcc = librosa.feature.mfcc(
            y=audio_waveform, 
            sr=self.sample_rate, 
            n_mfcc=40
        )
        
        # 2. Spectral features
        spectral_centroid = librosa.feature.spectral_centroid(
            y=audio_waveform, 
            sr=self.sample_rate
        )
        spectral_rolloff = librosa.feature.spectral_rolloff(
            y=audio_waveform, 
            sr=self.sample_rate
        )
        spectral_bandwidth = librosa.feature.spectral_bandwidth(
            y=audio_waveform, 
            sr=self.sample_rate
        )
        
        # 3. Zero crossing rate
        zcr = librosa.feature.zero_crossing_rate(audio_waveform)
        
        # 4. RMS energy (volume)
        rms_energy = librosa.feature.rms(
            y=audio_waveform,
            frame_length=2048,
            hop_length=512
        )
        
        # 5. Chroma features (pitch class)
        chroma = librosa.feature.chroma_stft(
            y=audio_waveform, 
            sr=self.sample_rate
        )
        
        # 6. Tempo and beat
        tempo, beats = librosa.beat.beat_track(
            y=audio_waveform, 
            sr=self.sample_rate
        )
        
        # Aggregate statistics (mean, std, max, min)
        features = {
            'mfcc_mean': np.mean(mfcc, axis=1),
            'mfcc_std': np.std(mfcc, axis=1),
            'spectral_centroid_mean': np.mean(spectral_centroid),
            'spectral_rolloff_mean': np.mean(spectral_rolloff),
            'spectral_bandwidth_mean': np.mean(spectral_bandwidth),
            'zcr_mean': np.mean(zcr),
            'rms_energy': rms_energy[0],  # Frame-by-frame
            'chroma_mean': np.mean(chroma, axis=1),
            'tempo': tempo
        }
        
        return features
```

#### 9.1.2 Emotion Classification

**Model Architecture**: LSTM-based emotion classifier

**Training Data**: RAVDESS + TESS + CREMA-D datasets (combined ~15,000 samples)

**Emotion Classes**: 
1. Neutral
2. Calm
3. Happy
4. Sad
5. Angry
6. Fearful
7. Disgust
8. Surprised

**Implementation**:

```python
import tensorflow as tf
from tensorflow import keras

class EmotionClassifier:
    """
    Classifies emotion from extracted audio features.
    """
    
    def __init__(self, model_path='emotion_lstm_model.h5'):
        self.model = keras.models.load_model(model_path)
        self.emotions = [
            'neutral', 'calm', 'happy', 'sad', 
            'angry', 'fearful', 'disgust', 'surprised'
        ]
    
    def predict_emotion(self, features):
        """
        Predict emotion from features.
        
        Args:
            features: Feature vector from FeatureExtractor
            
        Returns:
            tuple: (emotion_label, confidence_score)
        """
        # Prepare features for model (reshape for LSTM)
        feature_vector = self._prepare_features(features)
        
        # Predict
        prediction = self.model.predict(feature_vector, verbose=0)
        
        # Get top prediction
        emotion_idx = np.argmax(prediction[0])
        confidence = float(prediction[0][emotion_idx])
        emotion = self.emotions[emotion_idx]
        
        return emotion, confidence
    
    def _prepare_features(self, features):
        """
        Flatten and reshape features for model input.
        """
        # Concatenate all features
        feature_list = []
        feature_list.extend(features['mfcc_mean'])
        feature_list.extend(features['mfcc_std'])
        feature_list.append(features['spectral_centroid_mean'])
        feature_list.append(features['spectral_rolloff_mean'])
        feature_list.append(features['spectral_bandwidth_mean'])
        feature_list.append(features['zcr_mean'])
        feature_list.extend(features['chroma_mean'])
        feature_list.append(features['tempo'])
        
        # Reshape for LSTM: (batch_size, timesteps, features)
        feature_array = np.array(feature_list).reshape(1, -1, 1)
        
        return feature_array
```

#### 9.1.3 Dynamics Extraction

```python
class DynamicsAnalyzer:
    """
    Analyzes volume and speaking rate dynamics.
    """
    
    def analyze_dynamics(self, audio_waveform, sample_rate, features):
        """
        Extract volume and rate dynamics.
        
        Args:
            audio_waveform: Audio samples
            sample_rate: Sample rate (Hz)
            features: Pre-extracted features from FeatureExtractor
            
        Returns:
            dict with dynamics information
        """
        # 1. Volume analysis
        rms_energy = features['rms_energy']
        avg_energy = np.mean(rms_energy)
        
        # Convert to dB
        db_level = librosa.amplitude_to_db(np.array([avg_energy]))[0]
        
        # Classify volume
        volume_level = self._classify_volume(db_level)
        
        # 2. Speaking rate analysis
        # Use onset detection as proxy for syllables
        onset_frames = librosa.onset.onset_detect(
            y=audio_waveform,
            sr=sample_rate,
            units='frames'
        )
        
        duration = len(audio_waveform) / sample_rate
        syllables_per_sec = len(onset_frames) / duration
        
        # Approximate WPM (English: ~1.5 syllables per word)
        words_per_minute = (syllables_per_sec / 1.5) * 60
        
        rate_category = self._classify_rate(words_per_minute)
        
        return {
            'volume_level': volume_level,
            'volume_db': db_level,
            'speaking_rate': rate_category,
            'rate_wpm': int(words_per_minute),
            'energy_contour': rms_energy
        }
    
    def _classify_volume(self, db_level):
        """Classify volume into categories."""
        if db_level < -40:
            return 'whisper'
        elif db_level < -25:
            return 'quiet'
        elif db_level < -10:
            return 'normal'
        elif db_level < 0:
            return 'loud'
        else:
            return 'very_loud'
    
    def _classify_rate(self, wpm):
        """Classify speaking rate."""
        if wpm < 100:
            return 'very_slow'
        elif wpm < 130:
            return 'slow'
        elif wpm < 170:
            return 'normal'
        elif wpm < 200:
            return 'fast'
        else:
            return 'very_fast'
```

#### 9.1.4 Complete Emotion Detection Pipeline

```python
class EmotionDetectionPipeline:
    """
    Complete pipeline for emotion and dynamics detection.
    """
    
    def __init__(self):
        self.feature_extractor = EmotionFeatureExtractor()
        self.emotion_classifier = EmotionClassifier()
        self.dynamics_analyzer = DynamicsAnalyzer()
    
    def analyze_audio(self, audio_base64, sample_rate=16000):
        """
        Analyze audio chunk for emotion and dynamics.
        
        Args:
            audio_base64: Base64-encoded PCM audio
            sample_rate: Audio sample rate
            
        Returns:
            dict with complete analysis
        """
        # Decode audio
        audio_bytes = base64.b64decode(audio_base64)
        audio_waveform = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_waveform = audio_waveform.astype(np.float32) / 32768.0  # Normalize
        
        # Extract features
        features = self.feature_extractor.extract_features(audio_waveform)
        
        # Classify emotion
        emotion, confidence = self.emotion_classifier.predict_emotion(features)
        
        # Analyze dynamics
        dynamics = self.dynamics_analyzer.analyze_dynamics(
            audio_waveform,
            sample_rate,
            features
        )
        
        # Combine results
        return {
            'emotion': emotion,
            'emotion_intensity': confidence,
            'volume_level': dynamics['volume_level'],
            'volume_db': dynamics['volume_db'],
            'speaking_rate': dynamics['speaking_rate'],
            'rate_wpm': dynamics['rate_wpm'],
            'energy_contour': dynamics['energy_contour'].tolist()
        }
```

### 9.2 Standard Mode: SSML Generation

**Purpose**: Map detected dynamics to AWS Polly SSML for enhanced synthesis

```python
class SSMLGenerator:
    """
    Generates SSML from detected emotion and dynamics.
    """
    
    def generate_ssml(self, text, dynamics_analysis):
        """
        Generate emotion-aware SSML.
        
        Args:
            text: Translated text to synthesize
            dynamics_analysis: Output from EmotionDetectionPipeline
            
        Returns:
            str: SSML-formatted text
        """
        # Escape XML reserved characters
        text = self._escape_xml(text)
        
        # Start SSML document
        ssml = '<speak>'
        
        # Apply speaking rate
        rate = self._map_rate_to_ssml(dynamics_analysis['rate_wpm'])
        ssml += f'<prosody rate="{rate}">'
        
        # Apply volume (limited support in neural voices)
        volume = self._map_volume_to_ssml(dynamics_analysis['volume_level'])
        if volume != 'medium':
            ssml += f'<prosody volume="{volume}">'
        
        # Apply emphasis based on emotion
        emotion = dynamics_analysis['emotion']
        intensity = dynamics_analysis['emotion_intensity']
        
        if emotion in ['angry', 'excited', 'surprised'] and intensity > 0.7:
            # High-intensity emotions: strong emphasis
            ssml += '<emphasis level="strong">'
            ssml += text
            ssml += '</emphasis>'
        elif emotion in ['happy'] and intensity > 0.6:
            # Moderate emphasis
            ssml += '<emphasis level="moderate">'
            ssml += text
            ssml += '</emphasis>'
        elif emotion in ['sad', 'fearful']:
            # Softer delivery, no emphasis
            # Add pauses for contemplative feel
            sentences = text.split('.')
            for sent in sentences:
                if sent.strip():
                    ssml += f'<s>{sent.strip()}.</s>'
                    ssml += '<break time="500ms"/>'
        else:
            # Neutral or calm: normal delivery
            ssml += text
        
        # Close prosody tags
        if volume != 'medium':
            ssml += '</prosody>'
        ssml += '</prosody>'
        
        # Close speak tag
        ssml += '</speak>'
        
        return ssml
    
    def _escape_xml(self, text):
        """Escape XML reserved characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))
    
    def _map_rate_to_ssml(self, wpm):
        """Map WPM to SSML rate values."""
        if wpm < 100:
            return 'x-slow'
        elif wpm < 130:
            return 'slow'
        elif wpm < 170:
            return 'medium'
        elif wpm < 200:
            return 'fast'
        else:
            return 'x-fast'
    
    def _map_volume_to_ssml(self, volume_level):
        """Map volume level to SSML volume."""
        volume_map = {
            'whisper': 'x-soft',
            'quiet': 'soft',
            'normal': 'medium',
            'loud': 'loud',
            'very_loud': 'x-loud'
        }
        return volume_map.get(volume_level, 'medium')
```

**Usage Example**:

```python
# Input
text = "This is extremely important news everyone!"
dynamics = {
    'emotion': 'angry',
    'emotion_intensity': 0.87,
    'volume_level': 'loud',
    'rate_wpm': 185
}

# Generated SSML
ssml = ssml_generator.generate_ssml(text, dynamics)

# Output:
# <speak>
#   <prosody rate="fast">
#     <prosody volume="loud">
#       <emphasis level="strong">
#         This is extremely important news everyone!
#       </emphasis>
#     </prosody>
#   </prosody>
# </speak>
```

### 9.3 Premium Mode: Emotion Transfer Model

**Architecture**: For Premium Mode, use a dedicated emotion transfer TTS model hosted on AWS SageMaker.

**Recommended Model**: YourTTS or custom fine-tuned multilingual emotion TTS

**SageMaker Endpoint Configuration

Sources
[1] Guidelines-and-Requirements-for-Transcription-Translation.pdf https://najit.org/wp-content/uploads/2016/09/Guidelines-and-Requirements-for-Transcription-Translation.pdf
[2] Requirements Specification Template (Word version) https://www.pnnl.gov/main/publications/external/technical_reports/PNNL-19974.pdf
[3] Your Sample Software Requirements Document Template https://getnerdify.com/blog/sample-software-requirements-document/
[4] Software Requirements Specification (SRS) https://www.enabel.be/app/uploads/2025/06/Annex-A-Detailed-Software-Requirements-Specification-SRS.pdf
[5] Best Software Requirements Document Template https://bit.ai/templates/software-requirements-document-template
[6] Software Requirements Specification: Language ... https://www.scribd.com/document/797542768/SRS
[7] How to Write a Software Requirements Document (SRD) https://www.requiment.com/how-to-write-a-software-requirements-document-srd/
[8] Software Requirements Specification Template.docx https://people.eecs.ku.edu/~saiedian/812/Project/Wiegers-Resources/Chapter%2010/Software%20Requirements%20Specification%20Template.docx
[9] IEEE Software Requirements Specification Template https://smart-cities-marketplace.ec.europa.eu/sites/default/files/EIP_RequirementsSpecificationGLA_%20V2-5.pdf
[10] IEEE Software Requirements Specification Template https://www.utdallas.edu/~chung/RE/Presentations06F/Team_1.doc
