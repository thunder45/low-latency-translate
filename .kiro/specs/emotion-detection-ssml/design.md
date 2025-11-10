# Design Document: Audio Dynamics Detection & SSML Generation

## Overview

The Audio Dynamics Detection & SSML Generation system extracts paralinguistic features (volume, speaking rate, energy) from speaker audio using librosa, then generates SSML-enhanced markup to preserve the speaker's vocal dynamics in translated speech via Amazon Polly. This design focuses on Standard mode operation using lightweight audio analysis libraries without custom ML models or SageMaker deployments.

### Key Design Principles

- **Preserve Speaker Dynamics**: Capture HOW the speaker spoke, not just WHAT they said
- **Parallel Processing**: Run audio analysis concurrently with transcription to minimize latency
- **Simplicity**: Use librosa for audio feature extraction rather than complex ML models
- **Reliability**: Implement comprehensive error handling with graceful degradation to plain text
- **Performance**: Meet real-time processing requirements with <100ms audio analysis
- **Integration**: Align with existing Python/boto3 infrastructure patterns
- **Observability**: Emit metrics and structured logs for monitoring and debugging

## Architecture

### High-Level Architecture

```
                    ┌──────────────────┐
                    │  Speaker Audio   │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │   Volume    │  │   Speaking  │  │   Energy    │
    │  Detector   │  │    Rate     │  │  Analyzer   │
    │  (RMS)      │  │  Detector   │  │  (Optional) │
    │             │  │  (Onset)    │  │             │
    └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
           │                │                │
           └────────────────┼────────────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │ Audio Dynamics   │
                  │  (volume, rate)  │
                  └────────┬─────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         │                 │                 │
    [PARALLEL]        [PARALLEL]             │
         │                 │                 │
         ▼                 ▼                 │
┌─────────────┐   ┌─────────────┐           │
│ Transcribe  │   │ Translation │           │
│  (1-3s)     │   │  (200ms)    │           │
└──────┬──────┘   └──────┬──────┘           │
       │                 │                  │
       └────────┬────────┘                  │
                │                           │
                ▼                           │
         ┌─────────────┐                    │
         │ Translated  │                    │
         │    Text     │                    │
         └──────┬──────┘                    │
                │                           │
                └───────────┬───────────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │  SSML Generator  │
                  │ (merges dynamics │
                  │   with text)     │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │   Amazon Polly   │
                  │   (SSML-enhanced │
                  │    synthesis)    │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │  Audio Stream    │
                  │  (MP3 with       │
                  │   preserved      │
                  │   dynamics)      │
                  └──────────────────┘
```

### Component Interaction Flow

1. **Input**: Speaker audio received from upstream service
2. **Parallel Processing Begins**:
   - **Path A**: Audio Dynamics Detection (100ms)
     - Volume extraction via RMS energy
     - Speaking rate via onset detection
   - **Path B**: Transcription (1-3s) → Translation (200ms)
3. **Synchronization**: Wait for both paths to complete
4. **SSML Generation**: Merge audio dynamics with translated text (50ms)
5. **Speech Synthesis**: Polly synthesizes SSML-enhanced audio (800ms)
6. **Output**: MP3 audio stream preserving speaker's vocal dynamics

### Timing Analysis

```
Time (ms)    Audio Path              Text Path
─────────────────────────────────────────────────
0            Audio received          Audio received
             │                       │
100          Dynamics extracted      │
             (volume, rate)          │
             │                       │
             │                       Transcription...
             │                       │
1000-3000    │                       Transcription done
             │                       │
             │                       Translation (200ms)
             │                       │
1200-3200    │                       Translation done
             │                       │
             └───────┬───────────────┘
                     │
                     SSML Generation (50ms)
                     │
                     Polly Synthesis (800ms)
                     │
2050-4050    Audio output ready
```

**Total Latency**: 2-4 seconds (dominated by transcription, not dynamics detection)

## Components and Interfaces

### 1. Volume Detector

**Responsibility**: Extract volume levels from audio using RMS energy analysis

**Interface**:
```python
class VolumeDetector:
    def detect_volume(self, audio_data: np.ndarray, sample_rate: int) -> VolumeResult:
        """
        Detect volume level from audio using RMS energy.
        
        Args:
            audio_data: Audio samples as numpy array
            sample_rate: Audio sample rate in Hz
            
        Returns:
            VolumeResult with level classification and dB value
            
        Raises:
            VolumeDetectionError: When analysis fails
        """
        pass
```

**Key Behaviors**:
- Computes RMS energy across audio frames using librosa
- Converts RMS to decibels (dB)
- Classifies volume based on dB thresholds:
  - Loud: > -10 dB
  - Medium: -10 to -20 dB
  - Soft: -20 to -30 dB
  - Whisper: < -30 dB
- Returns medium volume on failure
- Target latency: <50ms
- Emits CloudWatch metrics for latency and errors

**Librosa Integration**:
```python
import librosa
import numpy as np

# Load audio
y, sr = librosa.load(audio_file, sr=None)

# Compute RMS energy
rms = librosa.feature.rms(y=y)[0]

# Convert to dB
db = librosa.amplitude_to_db(rms, ref=np.max)

# Average across frames
avg_db = np.mean(db)
```

### 2. Speaking Rate Detector

**Responsibility**: Extract speaking rate from audio using onset detection

**Interface**:
```python
class SpeakingRateDetector:
    def detect_rate(self, audio_data: np.ndarray, sample_rate: int) -> RateResult:
        """
        Detect speaking rate from audio using onset detection.
        
        Args:
            audio_data: Audio samples as numpy array
            sample_rate: Audio sample rate in Hz
            
        Returns:
            RateResult with rate classification and WPM value
            
        Raises:
            RateDetectionError: When analysis fails
        """
        pass
```

**Key Behaviors**:
- Performs onset detection to identify speech events using librosa
- Calculates words per minute (WPM) from onset count and duration
- Classifies rate based on WPM thresholds:
  - Very Slow: < 100 WPM
  - Slow: 100-130 WPM
  - Medium: 130-160 WPM
  - Fast: 160-190 WPM
  - Very Fast: > 190 WPM
- Returns medium rate on failure
- Target latency: <50ms
- Emits CloudWatch metrics for latency and errors

**Librosa Integration**:
```python
import librosa

# Detect onsets (speech events)
onset_frames = librosa.onset.onset_detect(
    y=y, 
    sr=sr,
    units='frames',
    hop_length=512,
    backtrack=False
)

# Calculate WPM
duration_minutes = len(y) / sr / 60
onset_count = len(onset_frames)
wpm = onset_count / duration_minutes if duration_minutes > 0 else 0
```

### 3. SSML Generator

**Responsibility**: Map audio dynamics to SSML prosody tags

**Interface**:
```python
class SSMLGenerator:
    def generate_ssml(self, text: str, dynamics: AudioDynamics) -> str:
        """
        Generate SSML markup with prosody tags based on audio dynamics.
        
        Args:
            text: Translated text content
            dynamics: Audio dynamics (volume, rate)
            
        Returns:
            Valid SSML markup string
        """
        pass
```

**Prosody Mapping Rules**:

**Volume Mapping**:
| Audio Volume | SSML Volume Attribute |
|--------------|----------------------|
| Loud | x-loud |
| Medium | medium |
| Soft | soft |
| Whisper | x-soft |

**Rate Mapping**:
| Speaking Rate | SSML Rate Attribute |
|---------------|---------------------|
| Very Slow | x-slow |
| Slow | slow |
| Medium | medium |
| Fast | fast |
| Very Fast | x-fast |

**SSML Template**:
```xml
<speak>
    <prosody rate="{rate}" volume="{volume}">
        {text}
    </prosody>
</speak>
```

**Key Behaviors**:
- Validates SSML against Polly specification v1.1
- Escapes special XML characters in text
- Applies both volume and rate prosody attributes
- Target latency: <50ms
- Falls back to plain text on validation errors
- Emits CloudWatch metrics for generation time

### 4. Polly Client

**Responsibility**: Synthesize SSML-enhanced speech using Amazon Polly

**Interface**:
```python
class PollyClient:
    def synthesize_speech(self, ssml_text: str, voice_id: str = 'Joanna') -> AudioStream:
        """
        Synthesize speech from SSML markup.
        
        Args:
            ssml_text: SSML markup string
            voice_id: Polly neural voice ID
            
        Returns:
            AudioStream with MP3 audio data
            
        Raises:
            SynthesisError: When synthesis fails after fallback
        """
        pass
```

**Key Behaviors**:
- Uses neural voices supporting SSML prosody (Joanna, Matthew, etc.)
- Configures MP3 output at 24000 Hz sample rate
- Implements fallback to plain text on SSML rejection
- Target latency: <800ms for segments up to 3000 characters
- Streams audio response for memory efficiency
- Implements exponential backoff for throttling (max 3 retries)

**AWS Integration**:
```python
# Polly API call
response = polly_client.synthesize_speech(
    Text=ssml_text,
    TextType='ssml',
    OutputFormat='mp3',
    VoiceId=voice_id,
    Engine='neural',
    SampleRate='24000'
)
```

### 5. Audio Dynamics Orchestrator

**Responsibility**: Coordinate audio dynamics detection, SSML generation, and speech synthesis

**Interface**:
```python
class AudioDynamicsOrchestrator:
    def process_audio_and_text(
        self, 
        audio_data: np.ndarray, 
        sample_rate: int,
        translated_text: str,
        options: ProcessingOptions = None
    ) -> ProcessingResult:
        """
        Process audio and text through dynamics detection and SSML generation pipeline.
        
        Args:
            audio_data: Speaker audio samples
            sample_rate: Audio sample rate in Hz
            translated_text: Translated text from transcription
            options: Optional processing configuration
            
        Returns:
            ProcessingResult with audio stream and metadata
        """
        pass
```

**Processing Flow**:
1. Validate audio data and text inputs
2. Invoke VolumeDetector in parallel with RateDetector
3. Combine volume and rate into AudioDynamics object
4. Pass dynamics and text to SSMLGenerator
5. Invoke PollyClient with SSML
6. Return audio stream with metadata
7. Log correlation ID throughout pipeline
8. Emit end-to-end latency metrics

**Parallel Execution**:
```python
import concurrent.futures

# Execute volume and rate detection in parallel
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    volume_future = executor.submit(volume_detector.detect_volume, audio_data, sample_rate)
    rate_future = executor.submit(rate_detector.detect_rate, audio_data, sample_rate)
    
    volume_result = volume_future.result()
    rate_result = rate_future.result()
```

## Data Models

### VolumeResult

```python
@dataclass
class VolumeResult:
    level: str  # 'loud', 'medium', 'soft', 'whisper'
    db_value: float  # Decibel value
    timestamp: datetime
```

### RateResult

```python
@dataclass
class RateResult:
    classification: str  # 'very_slow', 'slow', 'medium', 'fast', 'very_fast'
    wpm: float  # Words per minute
    onset_count: int  # Number of detected onsets
    timestamp: datetime
```

### AudioDynamics

```python
@dataclass
class AudioDynamics:
    volume: VolumeResult
    rate: RateResult
    correlation_id: str
    
    def to_ssml_attributes(self) -> Dict[str, str]:
        """Convert dynamics to SSML prosody attributes."""
        return {
            'volume': self._map_volume_to_ssml(),
            'rate': self._map_rate_to_ssml()
        }
```

### ProcessingOptions

```python
@dataclass
class ProcessingOptions:
    voice_id: str = 'Joanna'
    enable_ssml: bool = True
    sample_rate: str = '24000'
    output_format: str = 'mp3'
    enable_volume_detection: bool = True
    enable_rate_detection: bool = True
```

### ProcessingResult

```python
@dataclass
class ProcessingResult:
    audio_stream: bytes
    dynamics: AudioDynamics
    ssml_text: str
    processing_time_ms: int
    correlation_id: str
    fallback_used: bool  # True if plain text fallback was used
    
    # Timing breakdown
    volume_detection_ms: int
    rate_detection_ms: int
    ssml_generation_ms: int
    polly_synthesis_ms: int
```

### Error Types

```python
class VolumeDetectionError(Exception):
    """Raised when volume detection fails."""
    pass

class RateDetectionError(Exception):
    """Raised when rate detection fails."""
    pass

class SSMLValidationError(Exception):
    """Raised when SSML generation produces invalid markup."""
    pass

class SynthesisError(Exception):
    """Raised when speech synthesis fails after fallback."""
    pass
```

## Error Handling

### Error Handling Strategy

```
┌─────────────────┐
│  Volume Error   │
└────────┬────────┘
         │
         ├─ Librosa failure → Return medium volume
         ├─ Invalid audio → Log and return medium volume
         └─ Processing timeout → Return medium volume
         
┌─────────────────┐
│   Rate Error    │
└────────┬────────┘
         │
         ├─ Librosa failure → Return medium rate
         ├─ No onsets detected → Return medium rate
         └─ Processing timeout → Return medium rate
         
┌─────────────────┐
│   SSML Error    │
└────────┬────────┘
         │
         ├─ Invalid markup → Fall back to plain text
         └─ Generation failure → Log and use plain text
         
┌─────────────────┐
│  Polly Error    │
└────────┬────────┘
         │
         ├─ SSML rejected → Retry with plain text
         ├─ Throttling → Exponential backoff (3 retries)
         └─ Service unavailable → Raise SynthesisError
```

### Retry Logic

**Exponential Backoff Configuration**:
```python
RETRY_CONFIG = {
    'max_attempts': 3,
    'base_delay': 0.1,  # 100ms
    'max_delay': 2.0,   # 2s
    'exponential_base': 2,
    'jitter': True
}
```

**Retry Conditions**:
- Polly: `ThrottlingException`, `ServiceFailureException`

**No Retry Conditions**:
- Librosa processing errors (use defaults instead)
- Invalid audio input errors
- Authentication/authorization errors
- SSML validation errors (use fallback instead)

### Fallback Mechanisms

1. **Volume Detection Failure**: Return medium volume (default)
2. **Rate Detection Failure**: Return medium rate (default)
3. **SSML Validation Failure**: Use plain text without SSML tags
4. **Polly SSML Rejection**: Retry with plain text (TextType='text')

### Graceful Degradation

The system degrades gracefully through multiple levels:

**Level 1 - Full Functionality**:
- Audio dynamics detected successfully
- SSML generated with volume and rate prosody
- Polly synthesizes with SSML

**Level 2 - Partial Dynamics**:
- One detector fails (volume OR rate)
- SSML generated with available prosody attribute
- Polly synthesizes with partial SSML

**Level 3 - Default Dynamics**:
- Both detectors fail
- SSML generated with medium volume and rate
- Polly synthesizes with neutral SSML

**Level 4 - Plain Text Fallback**:
- SSML validation or Polly rejection
- Plain text synthesis without prosody
- Audio still generated, just without dynamics

## Testing Strategy

### Unit Tests

**VolumeDetector Tests**:
- Test RMS energy calculation with known audio samples
- Test dB conversion accuracy
- Test volume classification for each threshold range
- Test fallback to medium volume on librosa errors
- Test handling of silent audio (very low RMS)
- Test handling of clipped audio (very high RMS)

**SpeakingRateDetector Tests**:
- Test onset detection with known speech patterns
- Test WPM calculation accuracy
- Test rate classification for each threshold range
- Test fallback to medium rate on librosa errors
- Test handling of continuous speech (many onsets)
- Test handling of sparse speech (few onsets)

**SSMLGenerator Tests**:
- Test prosody mapping for each volume level
- Test prosody mapping for each rate classification
- Test SSML XML structure and validity
- Test special character escaping in text
- Test fallback to plain text on validation errors
- Test handling of empty or None dynamics

**PollyClient Tests**:
- Test successful synthesis with SSML
- Test fallback to plain text on SSML rejection
- Test audio stream handling
- Test retry logic with mocked throttling errors
- Test voice configuration
- Test MP3 format and sample rate

### Integration Tests

**End-to-End Pipeline Tests**:
- Test complete flow from audio input to synthesized audio output
- Test correlation ID propagation through pipeline
- Test latency requirements (100ms dynamics + 50ms SSML + 800ms synthesis)
- Test concurrent processing (10 audio segments)
- Test error propagation and fallback chains
- Test parallel execution of volume and rate detection

**Audio Processing Tests**:
- Test with real speech audio samples (various speakers)
- Test with different audio formats (WAV, MP3, etc.)
- Test with different sample rates (16kHz, 24kHz, 48kHz)
- Test with various audio durations (1s, 3s, 5s)
- Test with noisy audio
- Test with multi-speaker audio

**AWS Service Integration Tests**:
- Test actual Polly API calls with SSML markup
- Test IAM role authentication
- Test VPC endpoint connectivity (if configured)
- Test CloudWatch metrics emission

### Performance Tests

**Latency Benchmarks**:
- Volume detection: <50ms for 3-second audio
- Rate detection: <50ms for 3-second audio
- Parallel detection: <100ms total (both detectors)
- SSML generation: <50ms
- Polly synthesis: <800ms for 3000 character text
- End-to-end: <1s total (excluding transcription)

**Concurrency Tests**:
- 10 concurrent audio processing requests without degradation
- 50 concurrent requests with acceptable degradation (<20%)
- Measure throughput (audio segments/second)

**Load Tests**:
- Sustained load over 5 minutes
- Burst traffic patterns
- Monitor librosa CPU usage
- Monitor memory usage for audio buffers
- Monitor AWS Polly throttling

### Error Scenario Tests

- Librosa import/initialization failures
- Invalid audio data (corrupted, wrong format)
- Audio processing timeouts
- Invalid SSML markup handling
- Polly SSML rejection and fallback
- Polly throttling and recovery
- Network timeout scenarios
- Concurrent error handling (multiple failures)

## Deployment Considerations

### AWS Infrastructure

**IAM Permissions Required**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "polly:SynthesizeSpeech"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*"
    }
  ]
}
```

**Python Dependencies**:
```
librosa>=0.10.0
numpy>=1.24.0
boto3>=1.28.0
soundfile>=0.12.0  # Required by librosa for audio I/O
```

**VPC Configuration** (if required):
- VPC endpoints for Comprehend, Polly, CloudWatch
- Security group allowing outbound HTTPS (443)
- Private subnet deployment with NAT gateway (if internet access needed)

**Lambda Configuration** (if deployed as Lambda):
- Runtime: Python 3.11 or later
- Memory: 1024 MB (required for librosa and numpy audio processing)
- Timeout: 15 seconds (accommodates audio processing + synthesis + retries)
- Ephemeral storage: 1024 MB (for temporary audio files)
- Environment variables: `VOICE_ID`, `LOG_LEVEL`, `ENABLE_SSML`
- Lambda Layer: Consider using a layer for librosa/numpy to reduce deployment package size

### Monitoring and Observability

**CloudWatch Metrics**:
```python
METRICS = {
    'VolumeDetectionLatency': 'Milliseconds',
    'RateDetectionLatency': 'Milliseconds',
    'AudioDynamicsLatency': 'Milliseconds',  # Combined volume + rate
    'SSMLGenerationLatency': 'Milliseconds',
    'PollySynthesisLatency': 'Milliseconds',
    'EndToEndLatency': 'Milliseconds',
    'VolumeDetectionErrors': 'Count',
    'RateDetectionErrors': 'Count',
    'SSMLValidationErrors': 'Count',
    'PollySynthesisErrors': 'Count',
    'FallbacksUsed': 'Count',
    'ConcurrentRequests': 'Count',
    'AudioDuration': 'Seconds',  # Input audio duration
    'DetectedVolume': 'None',  # Custom metric with volume level as dimension
    'DetectedRate': 'None'  # Custom metric with rate classification as dimension
}
```

**Structured Logging Format**:
```json
{
  "timestamp": "2025-11-10T12:34:56.789Z",
  "level": "INFO",
  "correlation_id": "uuid-1234",
  "component": "VolumeDetector",
  "message": "Volume detection completed",
  "volume_level": "loud",
  "db_value": -8.5,
  "latency_ms": 45,
  "audio_duration_s": 2.5
}
```

**Alarms**:
- Error rate > 5% over 5 minutes
- P99 latency > 1.5 seconds (audio processing + synthesis)
- Fallback usage > 10% of requests
- Polly throttling detected
- Librosa processing failures > 2% of requests

### Configuration Management

**Environment Variables**:
- `AWS_REGION`: AWS region for service calls
- `VOICE_ID`: Default Polly voice (default: 'Joanna')
- `LOG_LEVEL`: Logging verbosity (default: 'INFO')
- `ENABLE_SSML`: Feature flag for SSML generation (default: 'true')
- `ENABLE_VOLUME_DETECTION`: Feature flag for volume detection (default: 'true')
- `ENABLE_RATE_DETECTION`: Feature flag for rate detection (default: 'true')
- `MAX_RETRIES`: Maximum retry attempts for Polly (default: '3')
- `AUDIO_SAMPLE_RATE`: Expected audio sample rate in Hz (default: '16000')

**Feature Flags**:
- `enable_ssml`: Toggle SSML generation (fallback to plain text)
- `enable_volume_detection`: Toggle volume detection (use medium if disabled)
- `enable_rate_detection`: Toggle rate detection (use medium if disabled)
- `enable_metrics`: Toggle CloudWatch metrics emission

## Security Considerations

### Data Protection

- **In Transit**: All AWS API calls use HTTPS/TLS 1.2+
- **At Rest**: Audio streams not persisted by this component
- **PII Handling**: Text may contain PII; ensure upstream redaction if required
- **Encryption**: Use KMS for any cached data (if caching implemented)

### Access Control

- IAM roles with least privilege permissions
- No embedded credentials in code
- Service-to-service authentication via IAM roles
- VPC isolation for sensitive deployments

### Compliance

- GDPR: Text data processed transiently, not stored
- HIPAA: Not HIPAA-eligible without additional controls
- SOC 2: Audit logging via CloudWatch Logs

## Performance Optimization

### Caching Strategy

**Audio Dynamics Caching** (optional enhancement):
- Cache dynamics results for identical audio hashes (TTL: 5 minutes)
- Use in-memory cache (e.g., functools.lru_cache)
- Reduces librosa processing for repeated audio segments
- Hash audio data using MD5 or similar for cache key

**SSML Template Caching**:
- Pre-compile SSML templates at initialization
- Reduces string formatting overhead

**Librosa Model Caching**:
- Librosa loads models on first use
- Keep Lambda warm to avoid cold start model loading
- Consider provisioned concurrency for consistent performance

### Batch Processing

**Not Applicable**: Real-time processing requirement precludes batching

### Connection Pooling

- Reuse boto3 clients across invocations (Lambda warm starts)
- Configure connection pool size for concurrent requests
- Reuse librosa resources across invocations to avoid reinitialization

### Audio Processing Optimization

**Librosa Performance**:
- Use `sr=None` when loading audio to avoid resampling if not needed
- Use `mono=True` to convert stereo to mono (reduces processing)
- Use `hop_length` parameter to control frame resolution vs speed tradeoff
- Consider using `librosa.load(..., duration=3.0)` to limit processing to first 3 seconds

**Parallel Processing**:
- Run volume and rate detection in parallel using ThreadPoolExecutor
- Target: Both complete within 100ms combined (not 100ms each)

## Future Enhancements

### Potential Improvements

1. **Energy Contour Analysis**: Extract frame-by-frame energy patterns for more nuanced prosody
2. **Pitch Detection**: Add pitch extraction for `<prosody pitch>` attribute (limited in neural voices)
3. **Emphasis Detection**: Add `<emphasis>` tags for high-energy words or phrases
4. **Break Insertion**: Add `<break>` tags for natural pauses detected in audio
5. **Voice Selection**: Dynamic voice selection based on speaker characteristics
6. **Multi-Speaker Support**: Detect and preserve dynamics for multiple speakers
7. **Emotion Classification**: Add discrete emotion detection (happy, sad, angry) using audio features
8. **A/B Testing**: Compare SSML with dynamics vs plain text user satisfaction
9. **Adaptive Thresholds**: Learn optimal volume/rate thresholds per speaker or language
10. **Text Sentiment Enhancement**: Optionally combine audio dynamics with text sentiment for emphasis

### Premium Mode Considerations (Out of Scope)

- Custom emotion classification models via SageMaker (8 emotion classes)
- LSTM-based emotion detection from MFCC features
- Fine-tuned prosody parameters based on user feedback
- Real-time emotion tracking across conversation context
- Speaker identification and personalized dynamics profiles
