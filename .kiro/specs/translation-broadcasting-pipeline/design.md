# Design Document: Multi-Language Translation & Broadcasting Pipeline

## Overview

The Translation and Broadcasting Pipeline is a serverless system that efficiently translates transcribed text into multiple languages and broadcasts synthesized audio to listeners. The design optimizes for cost and latency through DynamoDB caching, parallel processing, and intelligent query patterns using Global Secondary Indexes.

### Key Design Principles

1. **Cost Optimization**: Translate once per language, cache results, skip processing when no listeners
2. **Low Latency**: Parallel translation/synthesis, efficient GSI queries, minimal buffering
3. **Fault Tolerance**: Graceful degradation per language, retry logic, stale connection cleanup
4. **Scalability**: Serverless architecture, concurrent processing, DynamoDB auto-scaling

## Architecture

### High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                   TRANSLATION & BROADCAST PIPELINE              │
└─────────────────────────────────────────────────────────────────┘

Input: Transcribed Text + Emotion Dynamics
       ↓
┌──────────────────────────────────────────────────────────────────┐
│  STEP 1: Check Listener Count                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Query Sessions Table                                      │ │
│  │  IF listenerCount == 0: SKIP (cost optimization)          │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
       ↓ listenerCount > 0
┌──────────────────────────────────────────────────────────────────┐
│  STEP 2: Get Unique Target Languages                            │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Query Connections Table (GSI)                            │ │
│  │  sessionId-targetLanguage-index                           │ │
│  │  Result: ["es", "fr", "de"]                               │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────────────────────────────┐
│  STEP 3: Parallel Translation (Once Per Language)               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  FOR EACH language IN ["es", "fr", "de"] (PARALLEL):     │ │
│  │                                                            │ │
│  │  3a. Check Translation Cache                              │ │
│  │      Key: "en:es:{hash}"                                  │ │
│  │      ├─ HIT: Use cached translation                       │ │
│  │      └─ MISS: Call AWS Translate → Cache result           │ │
│  │                                                            │ │
│  │  Result: {"es": "Hola...", "fr": "Bonjour...", ...}      │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────────────────────────────┐
│  STEP 4: Generate SSML (Per Language)                           │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  FOR EACH translated_text (PARALLEL):                     │ │
│  │                                                            │ │
│  │  Apply emotion dynamics:                                  │ │
│  │  - Emotion: "angry" → <emphasis level="strong">          │ │
│  │  - Rate: 185 WPM → <prosody rate="fast">                 │ │
│  │  - Volume: "loud" → <prosody volume="loud">              │ │
│  │                                                            │ │
│  │  Result: SSML-enhanced text per language                  │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────────────────────────────┐
│  STEP 5: Parallel Synthesis (Once Per Language)                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  FOR EACH ssml_text (PARALLEL):                           │ │
│  │                                                            │ │
│  │  Call AWS Polly:                                          │ │
│  │  - Voice: Neural voice for target language               │ │
│  │  - Input: SSML text                                       │ │
│  │  - Output: PCM audio (16-bit, 16kHz, mono)               │ │
│  │                                                            │ │
│  │  Result: Audio streams per language                       │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────────────────────────────┐
│  STEP 6: Broadcast to Listeners (Per Language)                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  FOR EACH language WITH audio:                            │ │
│  │                                                            │ │
│  │  6a. Query Listeners (GSI)                                │ │
│  │      sessionId = X AND targetLanguage = "es"              │ │
│  │      Result: [conn1, conn2, conn3, ...]                   │ │
│  │                                                            │ │
│  │  6b. Broadcast (PARALLEL, max 100 concurrent)             │ │
│  │      FOR EACH connectionId:                               │ │
│  │        TRY:                                                │ │
│  │          PostToConnection(connectionId, audio)            │ │
│  │        EXCEPT GoneException:                              │ │
│  │          Remove stale connection                          │ │
│  │        EXCEPT Throttling/500:                             │ │
│  │          Retry up to 2 times (100ms backoff)              │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
       ↓
Output: Audio delivered to all listeners by language
```

## Components and Interfaces

### 1. Translation Pipeline Orchestrator

**Responsibility**: Coordinates the entire translation and broadcasting flow

**Interface**:
```python
class TranslationPipelineOrchestrator:
    def process_transcript(
        self,
        session_id: str,
        source_language: str,
        transcript_text: str,
        emotion_dynamics: EmotionDynamics
    ) -> ProcessingResult:
        """
        Main entry point for processing transcribed text.
        
        Args:
            session_id: Session identifier
            source_language: ISO 639-1 source language code
            transcript_text: Transcribed text to translate
            emotion_dynamics: Detected emotion and speaking dynamics
            
        Returns:
            ProcessingResult with success status and metrics
        """
```

**Key Methods**:
- `check_listener_count()`: Query Sessions table for active listeners
- `get_target_languages()`: Query Connections GSI for unique languages
- `orchestrate_translation()`: Coordinate parallel translation
- `orchestrate_synthesis()`: Coordinate parallel synthesis
- `orchestrate_broadcast()`: Coordinate parallel broadcasting

### 2. Translation Cache Manager

**Responsibility**: Manage DynamoDB translation cache with LRU eviction

**Interface**:
```python
class TranslationCacheManager:
    def get_cached_translation(
        self,
        source_lang: str,
        target_lang: str,
        text: str
    ) -> Optional[str]:
        """
        Retrieve cached translation if available.
        
        Args:
            source_lang: Source language code
            target_lang: Target language code
            text: Normalized text to translate
            
        Returns:
            Cached translation or None if cache miss
        """
    
    def cache_translation(
        self,
        source_lang: str,
        target_lang: str,
        text: str,
        translation: str
    ) -> None:
        """
        Store translation in cache with TTL.
        
        Args:
            source_lang: Source language code
            target_lang: Target language code
            text: Normalized source text
            translation: Translated text
        """
    
    def _generate_cache_key(
        self,
        source_lang: str,
        target_lang: str,
        text: str
    ) -> str:
        """
        Generate cache key: {source}:{target}:{hash16}
        
        Returns:
            Cache key string
        """
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for consistent caching.
        
        Returns:
            Normalized text (trimmed, lowercase)
        """
```

**Cache Key Format**:
```
{sourceLanguage}:{targetLanguage}:{textHash}

Example: "en:es:3f7b2a1c9d8e5f4a"

Where:
- sourceLanguage: ISO 639-1 code (e.g., "en")
- targetLanguage: ISO 639-1 code (e.g., "es")
- textHash: First 16 chars of SHA-256 hash of normalized text
```

### 3. Parallel Translation Service

**Responsibility**: Execute concurrent translations with caching

**Interface**:
```python
class ParallelTranslationService:
    def translate_to_languages(
        self,
        source_lang: str,
        text: str,
        target_languages: List[str]
    ) -> Dict[str, str]:
        """
        Translate text to multiple languages in parallel.
        
        Args:
            source_lang: Source language code
            text: Text to translate
            target_languages: List of target language codes
            
        Returns:
            Dictionary mapping language code to translated text
        """
    
    async def _translate_single(
        self,
        source_lang: str,
        target_lang: str,
        text: str
    ) -> Tuple[str, str]:
        """
        Translate to single language with cache check.
        
        Returns:
            Tuple of (target_lang, translated_text)
        """
```

**Concurrency Strategy**:
- Use `asyncio.gather()` for parallel AWS Translate calls
- Maximum concurrent requests: Number of target languages (typically 2-5)
- Timeout per translation: 2 seconds
- Fallback: Skip language on timeout, continue with others

### 4. SSML Generator

**Responsibility**: Generate emotion-aware SSML from dynamics

**Interface**:
```python
class SSMLGenerator:
    def generate_ssml(
        self,
        text: str,
        emotion_dynamics: EmotionDynamics
    ) -> str:
        """
        Generate SSML with emotion and dynamics applied.
        
        Args:
            text: Translated text
            emotion_dynamics: Detected emotion and speaking characteristics
            
        Returns:
            SSML-formatted text
        """
    
    def _escape_xml(self, text: str) -> str:
        """Escape XML reserved characters."""
    
    def _map_rate_to_ssml(self, wpm: int) -> str:
        """Map WPM to SSML rate values."""
    
    def _map_volume_to_ssml(self, volume_level: str) -> str:
        """Map volume level to SSML volume."""
    
    def _apply_emotion_emphasis(
        self,
        text: str,
        emotion: str,
        intensity: float
    ) -> str:
        """Apply emphasis tags based on emotion."""
```

**SSML Template**:
```xml
<speak>
  <prosody rate="{rate}">
    <prosody volume="{volume}">
      {emotion_enhanced_text}
    </prosody>
  </prosody>
</speak>
```

### 5. Parallel Synthesis Service

**Responsibility**: Execute concurrent TTS synthesis

**Interface**:
```python
class ParallelSynthesisService:
    def synthesize_to_languages(
        self,
        ssml_by_language: Dict[str, str],
        target_languages: List[str]
    ) -> Dict[str, bytes]:
        """
        Synthesize SSML to audio for multiple languages in parallel.
        
        Args:
            ssml_by_language: SSML text per language
            target_languages: List of target language codes
            
        Returns:
            Dictionary mapping language code to PCM audio bytes
        """
    
    async def _synthesize_single(
        self,
        language: str,
        ssml: str
    ) -> Tuple[str, bytes]:
        """
        Synthesize single language with AWS Polly.
        
        Returns:
            Tuple of (language, audio_bytes)
        """
```

**Voice Selection Strategy**:
```python
NEURAL_VOICES = {
    "en": "Joanna",
    "es": "Lupe",
    "fr": "Lea",
    "de": "Vicki",
    "it": "Bianca",
    "pt": "Camila",
    "ja": "Takumi",
    "ko": "Seoyeon",
    "zh": "Zhiyu"
}
```

### 6. Broadcast Handler

**Responsibility**: Fan out audio to listeners with retry logic

**Interface**:
```python
class BroadcastHandler:
    def broadcast_to_language(
        self,
        session_id: str,
        target_language: str,
        audio_data: bytes
    ) -> BroadcastResult:
        """
        Broadcast audio to all listeners of a specific language.
        
        Args:
            session_id: Session identifier
            target_language: Target language code
            audio_data: PCM audio bytes
            
        Returns:
            BroadcastResult with success/failure counts
        """
    
    async def _send_to_connection(
        self,
        connection_id: str,
        audio_data: bytes,
        retry_count: int = 0
    ) -> bool:
        """
        Send audio to single connection with retry logic.
        
        Returns:
            True if successful, False otherwise
        """
    
    def _handle_gone_exception(
        self,
        connection_id: str,
        session_id: str
    ) -> None:
        """Remove stale connection from database."""
```

**Concurrency Control**:
```python
# Limit concurrent broadcasts to prevent API Gateway throttling
MAX_CONCURRENT_BROADCASTS = 100

# Use semaphore for concurrency control
semaphore = asyncio.Semaphore(MAX_CONCURRENT_BROADCASTS)

async with semaphore:
    await api_gateway.post_to_connection(...)
```

### 7. Audio Buffer Manager

**Responsibility**: Manage per-listener audio buffers with overflow handling

**Interface**:
```python
class AudioBufferManager:
    def __init__(self, max_buffer_seconds: int = 10):
        self.max_buffer_seconds = max_buffer_seconds
        self.buffers: Dict[str, deque] = {}
    
    def add_audio(
        self,
        connection_id: str,
        audio_chunk: bytes,
        timestamp: float
    ) -> bool:
        """
        Add audio to listener buffer.
        
        Returns:
            True if added, False if buffer full (overflow)
        """
    
    def get_buffered_audio(
        self,
        connection_id: str
    ) -> List[bytes]:
        """Get all buffered audio for connection."""
    
    def clear_buffer(self, connection_id: str) -> None:
        """Clear buffer for connection."""
    
    def _check_overflow(
        self,
        connection_id: str
    ) -> bool:
        """Check if buffer exceeds 10 seconds."""
```

## Data Models

### DynamoDB Tables

#### 1. Sessions Table

**Purpose**: Track active sessions and listener counts

```python
{
    "sessionId": "golden-eagle-427",  # Partition Key
    "speakerConnectionId": "L0SM9cOFvHcCIhw=",
    "sourceLanguage": "en",
    "listenerCount": 15,  # Atomic counter
    "isActive": True,
    "createdAt": 1699500000000,
    "expiresAt": 1699510800000  # TTL
}
```

**Indexes**: None (primary key only)

#### 2. Connections Table

**Purpose**: Store connection metadata with language-based queries

```python
{
    "connectionId": "K3Rx8bNEuGdDJkx=",  # Partition Key
    "sessionId": "golden-eagle-427",
    "targetLanguage": "es",
    "role": "listener",
    "connectedAt": 1699500120000,
    "ttl": 1699510800
}
```

**Global Secondary Index**: `sessionId-targetLanguage-index`
- Partition Key: `sessionId`
- Sort Key: `targetLanguage`
- Projection: ALL

**Query Patterns**:

1. Get unique target languages:
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

# Extract unique languages
languages = set(item['targetLanguage'] for item in response['Items'])
```

2. Get listeners for specific language:
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
```

#### 3. CachedTranslations Table

**Purpose**: Cache translation results for cost optimization

```python
{
    "cacheKey": "en:es:3f7b2a1c9d8e5f4a",  # Partition Key
    "sourceLanguage": "en",
    "targetLanguage": "es",
    "sourceText": "Hello everyone, this is important news.",
    "translatedText": "Hola a todos, estas son noticias importantes.",
    "createdAt": 1699500000000,
    "accessCount": 5,
    "lastAccessedAt": 1699500300000,
    "ttl": 1699503600  # 1 hour TTL
}
```

**Indexes**: None (primary key only)

**LRU Eviction Strategy**:
- Track `accessCount` and `lastAccessedAt`
- When cache reaches 10,000 entries, evict entries with lowest `accessCount`
- If tie, evict oldest `lastAccessedAt`

## Error Handling

### Error Scenarios and Responses

#### 1. Translation Failure

**Scenario**: AWS Translate API call fails for one language

**Response**:
```python
try:
    translation = await translate_client.translate_text(...)
except ClientError as e:
    logger.error(f"Translation failed for {target_lang}: {e}")
    # Skip this language, continue with others
    failed_languages.append(target_lang)
    continue
```

**Impact**: Listeners of failed language receive no audio for this segment

#### 2. Synthesis Failure

**Scenario**: AWS Polly synthesis fails

**Response**:
```python
try:
    audio = await polly_client.synthesize_speech(...)
except ClientError as e:
    logger.error(f"Synthesis failed for {language}: {e}")
    # Skip this language, continue with others
    failed_languages.append(language)
    continue
```

**Impact**: Same as translation failure

#### 3. DynamoDB Throttling

**Scenario**: Query or update operations throttled

**Response**:
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(ProvisionedThroughputExceededException)
)
async def query_with_retry(...):
    return await dynamodb.query(...)
```

**Impact**: Adds latency (1-10 seconds) but ensures eventual success

#### 4. Broadcast Connection Failure

**Scenario**: PostToConnection fails

**Response**:
```python
try:
    await api_gateway.post_to_connection(
        ConnectionId=connection_id,
        Data=audio_data
    )
except GoneException:
    # Connection no longer exists
    await remove_stale_connection(connection_id, session_id)
except (ThrottlingException, InternalServerError) as e:
    # Retryable errors
    if retry_count < 2:
        await asyncio.sleep(0.1 * (2 ** retry_count))
        return await self._send_to_connection(
            connection_id, audio_data, retry_count + 1
        )
    else:
        logger.error(f"Broadcast failed after retries: {e}")
        return False
```

**Impact**: Individual listener may miss audio segment

#### 5. Cache Miss with Translation Failure

**Scenario**: Cache miss and subsequent AWS Translate call fails

**Response**:
```python
cached = await cache_manager.get_cached_translation(...)
if cached:
    return cached

try:
    translation = await translate_client.translate_text(...)
    await cache_manager.cache_translation(...)
    return translation
except ClientError as e:
    logger.error(f"Translation failed: {e}")
    # Return None, skip this language
    return None
```

**Impact**: Language skipped for this segment

## Testing Strategy

### Unit Tests

**Translation Cache Manager**:
- Test cache key generation with various text inputs
- Test text normalization (whitespace, case)
- Test SHA-256 hash truncation to 16 characters
- Test cache hit/miss scenarios
- Test LRU eviction when limit reached

**SSML Generator**:
- Test XML escaping for reserved characters
- Test rate mapping (WPM to SSML values)
- Test volume mapping (levels to SSML values)
- Test emotion emphasis application
- Test complete SSML generation with all dynamics

**Parallel Translation Service**:
- Test concurrent translation execution
- Test cache integration (hit/miss)
- Test error handling for individual language failures
- Test timeout handling

**Broadcast Handler**:
- Test concurrent broadcasting with semaphore
- Test retry logic for throttling errors
- Test GoneException handling
- Test stale connection cleanup

### Integration Tests

**End-to-End Translation Flow**:
```python
async def test_translation_pipeline_e2e():
    # Setup
    session_id = "test-session-123"
    transcript = "Hello everyone"
    dynamics = EmotionDynamics(emotion="happy", rate_wpm=150, volume="normal")
    
    # Create test listeners
    await create_test_listeners(session_id, ["es", "fr", "de"])
    
    # Execute pipeline
    result = await orchestrator.process_transcript(
        session_id=session_id,
        source_language="en",
        transcript_text=transcript,
        emotion_dynamics=dynamics
    )
    
    # Verify
    assert result.success == True
    assert len(result.languages_processed) == 3
    assert result.cache_hit_rate >= 0.0
    assert result.broadcast_success_rate >= 0.95
```

**Cache Performance Test**:
```python
async def test_cache_hit_performance():
    # First call: cache miss
    start = time.time()
    result1 = await translate_with_cache("en", "es", "Hello")
    duration1 = time.time() - start
    
    # Second call: cache hit
    start = time.time()
    result2 = await translate_with_cache("en", "es", "Hello")
    duration2 = time.time() - start
    
    # Verify
    assert result1 == result2
    assert duration2 < duration1 * 0.5  # Cache hit should be 50%+ faster
```

**GSI Query Performance Test**:
```python
async def test_gsi_query_latency():
    # Create test data
    session_id = "test-session-456"
    await create_test_listeners(session_id, ["es"] * 100)
    
    # Query listeners
    start = time.time()
    listeners = await query_listeners_by_language(session_id, "es")
    duration = time.time() - start
    
    # Verify
    assert len(listeners) == 100
    assert duration < 0.05  # < 50ms requirement
```

### Load Tests

**Concurrent Translation Test**:
- Simulate 5 target languages
- Measure total translation time
- Verify parallel execution (should be ~same as 1 language)

**Broadcast Scalability Test**:
- Simulate 100 listeners per language
- Measure broadcast completion time
- Verify < 2 seconds requirement

**Cache Eviction Test**:
- Fill cache to 10,000 entries
- Add 1,000 more entries
- Verify LRU eviction occurs
- Verify cache size remains at 10,000

## Performance Optimization

### Latency Breakdown (Target)

| Stage | Duration | Optimization |
|-------|----------|--------------|
| Check listener count | 10ms | Single DynamoDB GetItem |
| Get target languages | 20ms | GSI query with projection |
| Parallel translation (3 langs) | 200ms | Concurrent API calls + cache |
| Generate SSML (3 langs) | 10ms | In-memory string operations |
| Parallel synthesis (3 langs) | 400ms | Concurrent Polly calls |
| Query listeners (per lang) | 30ms | GSI query |
| Broadcast (100 listeners) | 1500ms | Concurrent with semaphore |
| **Total** | **2170ms** | **~2.2 seconds** |

### Cost Optimization Strategies

**Translation Caching**:
```
Without cache:
- 100 segments × 3 languages = 300 AWS Translate calls
- Cost: 300 × $0.000015 = $0.0045

With 50% cache hit rate:
- 150 AWS Translate calls
- Cost: 150 × $0.000015 = $0.00225
- Savings: 50%
```

**Skip Processing When No Listeners**:
```
Idle session (0 listeners):
- Transcribe: $0 (skipped)
- Translate: $0 (skipped)
- Polly: $0 (skipped)
- Total: $0

Active session (10 listeners):
- Transcribe: $0.0004/min
- Translate: $0.000015 × 3 langs = $0.000045
- Polly: $0.000004 × 3 langs = $0.000012
- Total: ~$0.0005/min
```

**Translate Once Per Language**:
```
Without optimization:
- 50 Spanish listeners × 1 translation each = 50 calls
- Cost: 50 × $0.000015 = $0.00075

With optimization:
- 1 translation for all Spanish listeners = 1 call
- Cost: 1 × $0.000015 = $0.000015
- Savings: 98%
```

## Deployment Considerations

### Lambda Configuration

**Translation Pipeline Lambda**:
```yaml
Runtime: Python 3.11
Memory: 1024 MB
Timeout: 30 seconds
Environment Variables:
  - SESSIONS_TABLE_NAME
  - CONNECTIONS_TABLE_NAME
  - CACHED_TRANSLATIONS_TABLE_NAME
  - MAX_CONCURRENT_BROADCASTS: 100
  - CACHE_TTL_SECONDS: 3600
  - MAX_CACHE_ENTRIES: 10000
```

**IAM Permissions**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Query",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/Sessions",
        "arn:aws:dynamodb:*:*:table/Connections",
        "arn:aws:dynamodb:*:*:table/Connections/index/*",
        "arn:aws:dynamodb:*:*:table/CachedTranslations"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "translate:TranslateText"
      ],
      "Resource": "*"
    },
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
        "execute-api:ManageConnections"
      ],
      "Resource": "arn:aws:execute-api:*:*:*/@connections/*"
    }
  ]
}
```

### DynamoDB Configuration

**Connections Table**:
```yaml
BillingMode: PAY_PER_REQUEST
GlobalSecondaryIndexes:
  - IndexName: sessionId-targetLanguage-index
    KeySchema:
      - AttributeName: sessionId
        KeyType: HASH
      - AttributeName: targetLanguage
        KeyType: RANGE
    Projection:
      ProjectionType: ALL
```

**CachedTranslations Table**:
```yaml
BillingMode: PAY_PER_REQUEST
TimeToLiveSpecification:
  Enabled: true
  AttributeName: ttl
```

### Monitoring and Metrics

**CloudWatch Metrics**:
- `TranslationCacheHitRate`: Percentage of cache hits
- `TranslationCacheSize`: Current number of cached entries
- `TranslationCacheEvictions`: Number of LRU evictions
- `BroadcastSuccessRate`: Percentage of successful broadcasts
- `BroadcastLatency`: Time to broadcast to all listeners
- `AudioBufferOverflows`: Number of buffer overflow events
- `FailedLanguages`: Count of languages that failed processing

**CloudWatch Alarms**:
- Cache hit rate < 30% (investigate cache effectiveness)
- Broadcast success rate < 95% (investigate connection issues)
- Buffer overflow rate > 5% (investigate latency issues)
- Failed languages > 10% (investigate AWS service issues)
