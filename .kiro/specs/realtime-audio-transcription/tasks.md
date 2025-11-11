# Implementation Plan

- [x] 1. Create core data models and configuration
- [x] 1.1 Implement PartialResult and FinalResult dataclasses with validation
  - Create dataclasses with all required fields (result_id, text, stability_score, timestamp, session_id, source_language)
  - Add validation methods for field constraints
  - _Requirements: 2.2, 2.3_

- [x] 1.2 Implement PartialResultConfig dataclass with validation
  - Create configuration dataclass with all tunable parameters
  - Implement validate() method to check parameter ranges (stability 0.70-0.95, timeout 2-10s)
  - _Requirements: 6.1, 6.2, 6.5_

- [x] 1.3 Implement BufferedResult and CacheEntry dataclasses
  - Create BufferedResult with forwarded tracking flag
  - Create CacheEntry with TTL and expiration check
  - _Requirements: 2.4, 5.3_

- [x] 2. Implement text normalization and deduplication cache
- [x] 2.1 Create text normalization function
  - Implement lowercase conversion and punctuation removal
  - Add whitespace normalization (strip and collapse multiple spaces)
  - Create SHA-256 hash generation for normalized text
  - _Requirements: 5.6, 8.5_

- [x] 2.2 Implement DeduplicationCache class
  - Create in-memory cache with TTL support
  - Implement contains(), add(), and cleanup_expired() methods
  - Add opportunistic cleanup for expired entries (check every 30 seconds, similar to orphan cleanup pattern)
  - Implement emergency cleanup if cache exceeds 10,000 entries
  - _Requirements: 5.2, 5.3, 5.6_

- [x] 2.3 Write unit tests for text normalization and deduplication
  - Test normalization with various punctuation and case combinations
  - Test cache hit/miss scenarios
  - Test TTL expiration
  - Test hash consistency
  - _Requirements: 5.6, 8.5_


- [ ] 3. Implement result buffer with capacity management
- [ ] 3.1 Create ResultBuffer class with add/remove operations
  - Implement dictionary-based storage with result_id as key
  - Add methods for add(), remove_by_id(), get_all()
  - _Requirements: 2.4, 3.5_

- [ ] 3.2 Implement capacity management and overflow handling
  - Calculate total words in buffer (estimate 30 words/second)
  - Implement flush_oldest() to remove oldest stable results when capacity exceeded
  - Add capacity check on each add operation
  - _Requirements: 3.5_

- [ ] 3.3 Implement orphan detection and cleanup
  - Create get_orphaned_results() method to find results older than timeout (15 seconds)
  - Track timestamp for each buffered result
  - _Requirements: 7.5_

- [ ] 3.4 Implement timestamp-based result ordering
  - Add sort_by_timestamp() method to ResultBuffer
  - Implement out-of-order detection and logging
  - Ensure results processed in chronological order
  - _Requirements: 7.2, 7.3_

- [ ]* 3.5 Write unit tests for result buffer
  - Test add/remove operations
  - Test capacity overflow handling
  - Test orphan detection with various timeouts
  - Test timestamp-based ordering
  - Test concurrent access scenarios
  - _Requirements: 3.5, 7.2, 7.3, 7.5_

- [ ] 4. Implement rate limiter
- [ ] 4.1 Create RateLimiter class with sliding window
  - Implement 200ms sliding window buffer
  - Track window start timestamp
  - Add should_process() method to check rate limit
  - _Requirements: 9.1, 9.2_

- [ ] 4.2 Implement best result selection in window
  - Create get_best_result_in_window() to select highest stability result
  - Handle tie-breaking with most recent timestamp
  - Handle missing stability scores (treat as 0)
  - _Requirements: 9.4_

- [ ] 4.3 Add CloudWatch metrics for dropped results
  - Emit metric when results are dropped due to rate limiting
  - Track count of dropped results per session
  - _Requirements: 9.3_

- [ ]* 4.4 Write unit tests for rate limiter
  - Test rate limit enforcement (5 per second)
  - Test best result selection with varying stability scores
  - Test window reset behavior
  - Test handling of missing stability scores
  - _Requirements: 9.1, 9.2, 9.4_

- [ ] 5. Implement sentence boundary detector
- [ ] 5.1 Create SentenceBoundaryDetector class
  - Initialize with configurable pause threshold (2 seconds) and buffer timeout (5 seconds)
  - Track last result timestamp
  - _Requirements: 5.4, 5.5_

- [ ] 5.2 Implement sentence completion detection logic
  - Check for sentence-ending punctuation (. ? !)
  - Detect pause threshold (2+ seconds since last result)
  - Detect buffer timeout (5 seconds since first buffered result)
  - Handle final results (always complete)
  - _Requirements: 3.1, 5.4, 5.5_

- [ ]* 5.3 Write unit tests for sentence boundary detector
  - Test punctuation detection (. ? !)
  - Test pause threshold detection
  - Test buffer timeout detection
  - Test final result handling
  - _Requirements: 5.4, 5.5_

- [ ] 6. Implement translation forwarder
- [ ] 6.1 Create TranslationForwarder class
  - Initialize with deduplication cache and translation pipeline reference
  - _Requirements: 5.2_

- [ ] 6.2 Implement forward() method with deduplication
  - Normalize text before checking cache
  - Check deduplication cache to prevent duplicate synthesis
  - Forward to translation pipeline if not duplicate
  - Update cache after forwarding
  - _Requirements: 5.2, 5.3, 8.4_

- [ ] 7. Implement partial result handler
- [ ] 7.1 Create PartialResultHandler class
  - Initialize with rate limiter, result buffer, and configuration
  - _Requirements: 2.1, 2.2_

- [ ] 7.2 Implement process() method with stability filtering
  - Check rate limiter before processing
  - Extract and validate stability score
  - Compare stability against configured threshold (default 0.85)
  - Handle missing stability scores with 3-second timeout fallback
  - _Requirements: 1.1, 1.5, 7.6_

- [ ] 7.3 Implement buffering and forwarding logic
  - Add partial result to buffer
  - Check sentence boundary detector
  - Forward to translation if complete sentence detected
  - Track forwarded status in buffer
  - _Requirements: 3.1, 3.2, 3.3, 5.4_

- [ ] 8. Implement final result handler
- [ ] 8.1 Create FinalResultHandler class
  - Initialize with result buffer and deduplication cache
  - _Requirements: 2.2, 2.4_

- [ ] 8.2 Implement process() method with partial cleanup
  - Remove corresponding partial results from buffer (match by result_id or timestamp range)
  - Check deduplication cache to avoid re-processing
  - Forward to translation pipeline if not duplicate
  - Update deduplication cache
  - _Requirements: 1.2, 2.4, 5.2_

- [ ] 8.3 Implement discrepancy logging using Levenshtein distance
  - Import python-Levenshtein library or implement edit distance algorithm
  - Calculate edit distance between forwarded partial and final text
  - Convert to percentage difference: (distance / max_length) * 100
  - Log warning if difference exceeds 20%
  - Track discrepancies for quality analysis
  - _Requirements: 4.5, 8.1, 8.5_

- [ ]* 8.4 Write unit tests for final result handler
  - Test partial result removal from buffer
  - Test deduplication cache checking
  - Test discrepancy calculation and logging
  - Test handling of missing corresponding partials
  - _Requirements: 2.4, 5.2, 8.1_

- [ ] 9. Implement transcription event handler
- [ ] 9.1 Create TranscriptionEventHandler class
  - Initialize with partial and final result handlers
  - _Requirements: 2.2_

- [ ] 9.2 Implement event parsing and metadata extraction
  - Parse AWS Transcribe event structure
  - Extract IsPartial flag, stability score, text, result_id, timestamp
  - Handle missing or malformed fields gracefully
  - Add defensive null checks for items array
  - _Requirements: 2.2, 2.3, 7.1, 7.6_

- [ ] 9.3 Implement routing logic for partial vs final results
  - Route to PartialResultHandler if IsPartial is true
  - Route to FinalResultHandler if IsPartial is false
  - _Requirements: 2.2_

- [ ]* 9.4 Write unit tests for transcription event handler
  - Test event parsing with valid and malformed events
  - Test metadata extraction with missing fields
  - Test routing logic for partial vs final results
  - Test null safety for items array
  - _Requirements: 2.2, 2.3, 7.1_

- [ ] 10. Implement main partial result processor
- [ ] 10.1 Create PartialResultProcessor class
  - Initialize all sub-components (handlers, buffer, cache, limiter, detector, forwarder)
  - Load configuration from environment or parameters
  - _Requirements: 6.3_

- [ ] 10.2 Implement opportunistic orphan cleanup
  - Track last_cleanup timestamp
  - Check on each event if 5+ seconds elapsed since last cleanup
  - Call buffer.get_orphaned_results() and flush to translation
  - Update last_cleanup timestamp
  - _Requirements: 7.5_

- [ ] 10.3 Implement async event processing methods
  - Create process_partial() async method
  - Create process_final() async method
  - Handle exceptions and log errors
  - _Requirements: 2.1, 2.2_

- [ ]* 10.4 Write integration tests for partial result processor
  - Test 1: End-to-end partial to translation (verify <200ms latency)
  - Test 2: Rate limiting with 20 partials in 1 second (verify 15 dropped, 5 processed)
  - Test 3: Orphan cleanup after 15-second timeout
  - Test 4: Fallback when stability scores unavailable (verify 3-second timeout used)
  - Test 5: Out-of-order result handling with timestamp sorting
  - Test 6: Deduplication prevents double synthesis
  - _Requirements: 1.1, 7.2, 7.3, 7.5, 7.6, 9.1_

- [ ] 11. Integrate with AWS Transcribe Streaming API
- [ ] 11.1 Create async stream handler for Transcribe events
  - Extend TranscriptResultStreamHandler
  - Implement handle_transcript_event() async method
  - Extract stability scores with null safety
  - Call PartialResultProcessor methods
  - _Requirements: 2.1, 2.2, 7.6_

- [ ] 11.2 Configure Transcribe client with partial results enabled
  - Set enable_partial_results_stabilization=True
  - Set partial_results_stability='high'
  - Configure language code and media parameters
  - _Requirements: 2.1_

- [ ] 12. Integrate with Lambda function
- [ ] 12.1 Update Audio Processor Lambda handler
  - Add async/sync bridge using asyncio.get_event_loop().run_until_complete()
  - Create async process_audio_async() function
  - Initialize PartialResultProcessor singleton on cold start
  - _Requirements: 6.3_

- [ ] 12.2 Implement configuration loading from environment variables
  - Load all configuration parameters from Lambda environment
  - Validate configuration on initialization
  - Handle invalid configuration with descriptive errors
  - _Requirements: 6.1, 6.2, 6.5_

- [ ] 12.3 Add error handling and fallback to final-only mode
  - Catch Transcribe failures and disable partial processing
  - Log fallback trigger events
  - Emit CloudWatch metric for fallback
  - _Requirements: 7.4_

- [ ] 12.4 Implement Transcribe service health monitoring
  - Track last_result_time during active audio sessions
  - Detect when no results received for 10+ seconds
  - Automatically disable partial processing on failure
  - Re-enable partial processing when results resume
  - Emit CloudWatch metric for fallback triggers
  - _Requirements: 7.4_

- [ ] 13. Implement CloudWatch metrics and logging
- [ ] 13.1 Add structured logging for all events
  - Log partial results at DEBUG level with stability and text preview
  - Log final results at INFO level
  - Log rate limiting, orphan cleanup, and discrepancies at WARNING level
  - Log errors with full context
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 13.2 Implement CloudWatch custom metrics
  - Emit PartialResultProcessingLatency (p50, p95, p99)
  - Emit PartialResultsDropped count
  - Emit PartialToFinalRatio
  - Emit DuplicatesDetected count
  - Emit OrphanedResultsFlushed count
  - _Requirements: 4.3, 4.4, 9.3_

- [ ] 14. Update DynamoDB session schema
- [ ] 14.1 Add partial result configuration fields to Sessions table
  - Add partialResultsEnabled boolean field
  - Add minStabilityThreshold float field
  - Add maxBufferTimeout float field
  - No migration needed (DynamoDB is schemaless)
  - _Requirements: 6.3_

- [ ] 14.2 Update session creation API to accept configuration parameters
  - Parse partialResults, minStability query parameters
  - Validate configuration using PartialResultConfig.validate()
  - Store configuration in DynamoDB session item
  - Return error for invalid configuration
  - _Requirements: 6.1, 6.2, 6.5_

- [ ] 15. Update infrastructure configuration
- [ ] 15.1 Update Lambda function configuration
  - Increase memory to 512 MB (monitor and increase to 768 MB if needed)
  - Increase timeout to 60 seconds
  - Add environment variables for all configuration parameters
  - _Requirements: 6.1, 6.2_

- [ ] 15.2 Add CloudWatch alarms for monitoring
  - Create alarm for end-to-end latency p95 > 5 seconds
  - Create alarm for partial results dropped > 100/minute
  - Create alarm for orphaned results > 10/session
  - Create alarm for Transcribe fallback triggered
  - _Requirements: 4.3_

- [ ] 16. Create deployment and rollout plan
- [ ] 16.1 Implement feature flag for gradual rollout
  - Use AWS AppConfig or Parameter Store for dynamic configuration
  - Support enabling/disabling partial results without redeployment
  - Implement canary deployment (10% → 50% → 100%)
  - _Requirements: 6.3, 6.4_

- [ ] 16.2 Document rollback procedures
  - Create runbook for disabling partial results via environment variable
  - Document fallback behavior to final-only mode
  - Test rollback procedure
  - _Requirements: 6.4_

- [ ]* 17. Performance and quality validation
- [ ]* 17.1 Run latency benchmark tests
  - Measure end-to-end latency with partial results enabled
  - Compare against final-only mode baseline
  - Verify target of 2-4 seconds achieved
  - _Requirements: 1.3_

- [ ]* 17.2 Run accuracy comparison tests
  - Process test audio samples with partial and final-only modes
  - Calculate translation similarity using BLEU score or Levenshtein distance
  - Verify ≥90% accuracy maintained
  - _Requirements: 1.4_

- [ ]* 17.3 Run throughput and memory tests
  - Test with 10 concurrent sessions for 60 minutes
  - Monitor buffer size, cache size, memory usage
  - Verify no memory leaks or buffer overflows
  - _Requirements: 3.5_
