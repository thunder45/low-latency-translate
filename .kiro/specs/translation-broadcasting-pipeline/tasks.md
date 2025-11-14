# Implementation Plan

**Note**: Tasks 2-7 can be implemented in parallel as they are independent components.

- [x] 1. Set up DynamoDB tables and indexes
  - Create Sessions table with listenerCount atomic counter
  - Create Connections table with sessionId-targetLanguage GSI
  - Create CachedTranslations table with TTL enabled
  - Configure on-demand billing mode for all tables
  - _Requirements: 2.1, 2.2, 9.1_

- [x] 2. Implement Translation Cache Manager
  - [x] 2.1 Create cache key generation logic
    - Implement text normalization (trim, lowercase)
    - Implement SHA-256 hashing with 16-character truncation
    - Generate composite key format: {source}:{target}:{hash16}
    - _Requirements: 9.2, 9.6, 9.7_

  - [x] 2.2 Implement cache lookup and storage
    - Write get_cached_translation() method with DynamoDB query
    - Write cache_translation() method with TTL setting (3600 seconds)
    - Handle cache misses gracefully
    - _Requirements: 9.3, 9.4_

  - [x] 2.3 Implement LRU eviction logic
    - Track accessCount and lastAccessedAt on cache reads
    - Implement eviction when cache exceeds 10,000 entries
    - Evict entries with lowest accessCount (oldest lastAccessedAt on tie)
    - _Requirements: 9.5_

  - [x] 2.4 Add cache metrics emission
    - Emit CloudWatch metric for cache hit rate
    - Emit CloudWatch metric for cache size
    - Emit CloudWatch metric for cache evictions
    - _Requirements: 9.8_

- [x] 3. Implement Parallel Translation Service
  - [x] 3.1 Create translation orchestration logic
    - Implement translate_to_languages() with asyncio.gather()
    - Integrate cache manager for cache-first lookups
    - Handle cache misses with AWS Translate API calls
    - Store successful translations in cache
    - _Requirements: 1.2, 1.3, 8.1_

  - [x] 3.2 Implement error handling for translations
    - Catch and log AWS Translate ClientError exceptions
    - Skip failed languages and continue with others
    - Return partial results for successful languages
    - Include session context in error logs
    - _Requirements: 7.1, 7.5_

  - [x] 3.3 Add translation timeout handling
    - Set 2-second timeout per translation call
    - Handle timeout exceptions gracefully
    - Log timeout events with language and session context
    - _Requirements: 8.1_

- [x] 4. Implement SSML Generator
  - [x] 4.1 Create XML escaping utility
    - Escape reserved characters: &, <, >, ", '
    - Apply escaping before SSML generation
    - _Requirements: 3.5_

  - [x] 4.2 Implement dynamics-to-SSML mapping
    - Map speaking rate (WPM) to SSML prosody rate values
    - Map volume level to SSML prosody volume values
    - Map emotion and intensity to emphasis levels
    - _Requirements: 3.2, 3.3, 3.4_

  - [x] 4.3 Create SSML template generation
    - Generate complete SSML document with speak tags
    - Apply nested prosody tags for rate and volume
    - Apply emphasis tags based on emotion type and intensity
    - Handle special cases (sad/fearful emotions with pauses)
    - _Requirements: 3.1_

- [x] 5. Implement Parallel Synthesis Service
  - [x] 5.1 Create synthesis orchestration logic
    - Implement synthesize_to_languages() with asyncio.gather()
    - Call AWS Polly for each language in parallel
    - Use neural voices with language-specific voice selection
    - Return PCM audio (16-bit, 16kHz, mono)
    - _Requirements: 4.1, 4.2, 4.5, 8.2_

  - [x] 5.2 Implement error handling for synthesis
    - Catch and log AWS Polly ClientError exceptions
    - Skip failed languages and continue with others
    - Return partial results for successful languages
    - _Requirements: 4.4, 7.2_

  - [x] 5.3 Add synthesis timeout and performance monitoring
    - Set timeout for synthesis operations
    - Log synthesis duration per language
    - Verify 500ms target for synthesis completion
    - _Requirements: 4.3_

- [x] 6. Implement Broadcast Handler
  - [x] 6.1 Create listener query logic
    - Query Connections table using sessionId-targetLanguage GSI
    - Extract connectionId list for target language
    - Handle empty results gracefully
    - _Requirements: 5.1, 2.3, 2.4_

  - [x] 6.2 Implement parallel broadcasting with concurrency control
    - Use asyncio.Semaphore to limit concurrent broadcasts to 100
    - Send audio to all listeners in parallel using asyncio.gather()
    - Use API Gateway Management API PostToConnection
    - _Requirements: 5.2, 5.5, 5.7_

  - [x] 6.3 Implement retry logic for broadcast failures
    - Catch GoneException and remove stale connections
    - Catch throttling and 500 errors for retry
    - Retry up to 2 times with 100ms exponential backoff
    - Log retry attempts and final failures
    - _Requirements: 5.3, 5.6_

  - [x] 6.4 Add broadcast metrics and monitoring
    - Track successful vs failed broadcasts
    - Calculate broadcast success rate
    - Measure broadcast latency
    - Emit CloudWatch metrics
    - _Requirements: 5.4_

- [x] 7. Implement Audio Buffer Manager
  - [x] 7.1 Create buffer management logic
    - Initialize per-listener buffers with deque
    - Implement add_audio() with overflow detection
    - Check buffer duration against 10-second limit
    - Drop oldest packets when buffer exceeds capacity
    - _Requirements: 10.1, 10.2_

  - [x] 7.2 Add buffer monitoring
    - Emit CloudWatch metric for buffer overflow events
    - Log buffer overflow with sessionId and listener count
    - Track buffer utilization percentage
    - _Requirements: 10.3, 10.4, 10.5_

- [x] 8. Implement Translation Pipeline Orchestrator
  - **Depends on**: Tasks 2-7 must be completed first
  - [x] 8.1 Create listener count check
    - Query Sessions table for listenerCount
    - Return early if listenerCount == 0 (cost optimization)
    - Log skip events for monitoring
    - _Requirements: 6.5_

  - [x] 8.2 Implement target language discovery
    - Query Connections table using GSI
    - Filter by sessionId and role="listener"
    - Extract unique set of target languages
    - _Requirements: 2.3, 2.4, 2.5_

  - [x] 8.3 Orchestrate parallel translation
    - Call ParallelTranslationService with target languages
    - Wait for all translations to complete
    - Handle partial failures (some languages succeed)
    - _Requirements: 1.2, 8.1, 8.3_

  - [x] 8.4 Generate SSML for all translations
    - Call SSMLGenerator for each translated text
    - Apply emotion dynamics to all languages
    - _Requirements: 3.1_

  - [x] 8.5 Orchestrate parallel synthesis
    - Call ParallelSynthesisService with SSML texts
    - Wait for all synthesis operations to complete
    - Handle partial failures
    - _Requirements: 8.2, 8.4_

  - [x] 8.6 Orchestrate broadcasting per language
    - For each language with synthesized audio
    - Call BroadcastHandler to fan out to listeners
    - Track overall success metrics
    - _Requirements: 8.4_

  - [x] 8.7 Implement DynamoDB retry logic
    - Add exponential backoff for throttled queries
    - Retry up to 3 times with 1-10 second delays
    - Log retry attempts and final failures
    - _Requirements: 7.3, 7.4_

- [x] 9. Implement atomic listener count updates
  - [x] 9.1 Create increment operation
    - Use DynamoDB UpdateItem with ADD operation
    - Increment listenerCount by 1 atomically
    - Handle update failures with retry
    - _Requirements: 6.1_

  - [x] 9.2 Create decrement operation
    - Use DynamoDB UpdateItem with ADD operation
    - Decrement listenerCount by -1 atomically
    - Ensure count never goes negative
    - _Requirements: 6.2, 6.4_

  - [x] 9.3 Integrate with connection lifecycle
    - Call increment when listener joins session
    - Call decrement when listener disconnects
    - Use atomic operations to prevent race conditions
    - _Requirements: 6.3_

- [x] 10. Create Lambda function and deployment configuration
  - [x] 10.1 Set up Lambda function structure
    - Create main handler function
    - Configure runtime (Python 3.11)
    - Set memory to 1024 MB
    - Set timeout to 30 seconds
    - _Requirements: All_

  - [x] 10.2 Configure environment variables
    - Add SESSIONS_TABLE_NAME
    - Add CONNECTIONS_TABLE_NAME
    - Add CACHED_TRANSLATIONS_TABLE_NAME
    - Add MAX_CONCURRENT_BROADCASTS (100)
    - Add CACHE_TTL_SECONDS (3600)
    - Add MAX_CACHE_ENTRIES (10000)
    - _Requirements: All_

  - [x] 10.3 Set up IAM permissions
    - Grant DynamoDB permissions (GetItem, PutItem, Query, UpdateItem, DeleteItem)
    - Grant AWS Translate permissions (TranslateText)
    - Grant AWS Polly permissions (SynthesizeSpeech)
    - Grant API Gateway permissions (ManageConnections)
    - _Requirements: All_

  - [x] 10.4 Create deployment package
    - Package Lambda code with dependencies
    - Include boto3, asyncio, hashlib libraries
    - Create deployment ZIP or container image
    - _Requirements: All_

- [x] 11. Set up monitoring and alerting
  - Create CloudWatch dashboard for pipeline metrics
  - Set up alarm for cache hit rate < 30%
  - Set up alarm for broadcast success rate < 95%
  - Set up alarm for buffer overflow rate > 5%
  - Set up alarm for failed languages > 10%
  - _Requirements: 9.8, 10.3, 10.4_

- [x] 12. Create integration tests
  - Write end-to-end translation pipeline test
  - Write cache performance test (hit vs miss)
  - Write GSI query performance test
  - Write concurrent translation test
  - Write broadcast scalability test
  - Write cache eviction test
  - _Requirements: All_
