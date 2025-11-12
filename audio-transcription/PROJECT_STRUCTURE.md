# Audio Transcription - Project Structure

## Directory Tree

```
audio-transcription/
├── lambda/                          # Lambda function handlers
│   ├── __init__.py                 # Lambda package initialization
│   └── audio_processor/            # Audio processor Lambda
│       ├── __init__.py             # Audio processor package
│       ├── handler.py              # Lambda handler with async/sync bridge
│       └── requirements.txt        # Lambda-specific dependencies
│
├── audio_quality/                   # Audio quality validation package
│   ├── __init__.py                 # Package exports
│   ├── models/                     # Quality data models
│   │   ├── __init__.py             # Model exports
│   │   ├── quality_config.py       # QualityConfig dataclass
│   │   ├── quality_metrics.py      # QualityMetrics dataclass
│   │   ├── audio_format.py         # AudioFormat dataclass
│   │   ├── quality_event.py        # QualityEvent dataclass
│   │   ├── validation_result.py    # ValidationResult dataclass
│   │   └── results.py              # ClippingResult, EchoResult, SilenceResult
│   ├── validators/                 # Audio format validators
│   │   ├── format_validator.py     # AudioFormatValidator class
│   │   └── __init__.py
│   ├── analyzers/                  # Quality analyzers (SNR, clipping, echo, silence)
│   │   ├── __init__.py             # Analyzer exports
│   │   ├── snr_calculator.py       # SNRCalculator class (Task 3)
│   │   ├── clipping_detector.py    # ClippingDetector class (Task 4)
│   │   ├── echo_detector.py        # EchoDetector class (Task 5)
│   │   ├── silence_detector.py     # SilenceDetector class (Task 6)
│   │   └── quality_analyzer.py     # AudioQualityAnalyzer class (Task 7)
│   ├── processors/                 # Audio processors (high-pass, noise gate)
│   │   └── __init__.py
│   ├── notifiers/                  # Quality notifiers (metrics, events)
│   │   ├── __init__.py             # Notifier exports
│   │   └── metrics_emitter.py      # QualityMetricsEmitter class (Task 8)
│   ├── examples/                   # Example scripts
│   │   ├── demo_quality_analyzer.py # Demo of AudioQualityAnalyzer
│   │   └── demo_metrics_emitter.py # Demo of QualityMetricsEmitter
│   └── docs/                       # Audio quality documentation
│       ├── TASK_1_SUMMARY.md       # Task 1 implementation summary
│       ├── TASK_2_SUMMARY.md       # Task 2 implementation summary
│       ├── TASK_3_SUMMARY.md       # Task 3 implementation summary
│       ├── TASK_4_SUMMARY.md       # Task 4 implementation summary
│       ├── TASK_5_SUMMARY.md       # Task 5 implementation summary
│       ├── TASK_6_SUMMARY.md       # Task 6 implementation summary
│       ├── TASK_7_SUMMARY.md       # Task 7 implementation summary
│       └── TASK_8_SUMMARY.md       # Task 8 implementation summary
│
├── shared/                          # Shared code within component
│   ├── models/                      # Data models & types
│   │   ├── __init__.py             # Model exports
│   │   ├── cache.py                # CacheEntry dataclass
│   │   ├── configuration.py        # PartialResultConfig
│   │   └── transcription_results.py # PartialResult, FinalResult, BufferedResult
│   ├── services/                    # Business logic
│   │   ├── __init__.py             # Service exports
│   │   ├── deduplication_cache.py  # DeduplicationCache class
│   │   ├── feature_flag_service.py # FeatureFlagService class (Task 16)
│   │   ├── final_result_handler.py # FinalResultHandler class
│   │   ├── partial_result_handler.py # PartialResultHandler class
│   │   ├── partial_result_processor.py # PartialResultProcessor class
│   │   ├── rate_limiter.py         # RateLimiter class
│   │   ├── result_buffer.py        # ResultBuffer class
│   │   ├── sentence_boundary_detector.py # SentenceBoundaryDetector class
│   │   ├── transcribe_client.py    # TranscribeClientConfig, TranscribeClientManager
│   │   ├── transcribe_stream_handler.py # TranscribeStreamHandler class
│   │   ├── transcription_event_handler.py # TranscriptionEventHandler class
│   │   └── translation_forwarder.py # TranslationForwarder class
│   └── utils/                       # Utilities
│       ├── __init__.py             # Utility exports
│       ├── metrics.py              # MetricsEmitter class
│       └── text_normalization.py   # normalize_text(), hash_text()
│
├── tests/                           # All tests for component
│   ├── unit/                       # Unit tests
│   │   ├── __init__.py
│   │   ├── test_audio_format_validator.py # 20 tests for audio format validation
│   │   ├── test_data_models.py     # 30 tests for models
│   │   ├── test_deduplication_cache.py # 20 tests for cache
│   │   ├── test_final_result_handler.py # 15 tests for final handler
│   │   ├── test_partial_result_handler.py # 17 tests for partial handler
│   │   ├── test_metrics_emitter.py # 16 tests for QualityMetricsEmitter
│   │   ├── test_quality_analyzer.py # 18 tests for AudioQualityAnalyzer
│   │   ├── test_rate_limiter.py    # 15 tests for rate limiter
│   │   ├── test_result_buffer.py   # 23 tests for buffer
│   │   ├── test_sentence_boundary_detector.py # 29 tests for sentence detector
│   │   ├── test_text_normalization.py # 21 tests for normalization
│   │   ├── test_transcribe_client.py # 15 tests for Transcribe client config
│   │   ├── test_transcribe_stream_handler.py # 13 tests for stream handler
│   │   └── test_transcription_event_handler.py # 20 tests for event handler
│   ├── integration/                # Integration tests
│   │   └── test_partial_result_processor.py # 7 integration tests
│   ├── __init__.py
│   └── conftest.py                 # Shared pytest fixtures
│
├── infrastructure/                   # AWS CDK infrastructure
│   ├── stacks/                     # CDK stacks
│   │   ├── __init__.py             # Stack package initialization
│   │   └── audio_transcription_stack.py # Main CDK stack
│   ├── config/                     # Environment-specific configs
│   │   ├── dev.json.example        # Development configuration
│   │   ├── staging.json.example    # Staging configuration
│   │   └── prod.json.example       # Production configuration
│   ├── app.py                      # CDK app entry point
│   ├── cdk.json                    # CDK configuration
│   ├── requirements.txt            # CDK dependencies
│   └── README.md                   # Infrastructure documentation
│
├── scripts/                         # Deployment and utility scripts
│   ├── manage_rollout.py          # Rollout management script (Task 16)
│   └── test_rollback.py           # Rollback testing script (Task 16)
│
├── docs/                            # Component documentation
│   ├── DEPLOYMENT_ROLLOUT_GUIDE.md # Deployment and rollout guide (Task 16)
│   ├── ROLLBACK_RUNBOOK.md        # Rollback procedures runbook (Task 16)
│   ├── TASK_1_SUMMARY.md          # Task 1 implementation summary
│   ├── TASK_2_SUMMARY.md          # Task 2 implementation summary
│   ├── TASK_3_SUMMARY.md          # Task 3 implementation summary
│   ├── TASK_4_SUMMARY.md          # Task 4 implementation summary
│   ├── TASK_5_SUMMARY.md          # Task 5 implementation summary
│   ├── TASK_6_SUMMARY.md          # Task 6 implementation summary
│   ├── TASK_7_SUMMARY.md          # Task 7 implementation summary
│   ├── TASK_8_SUMMARY.md          # Task 8 implementation summary
│   ├── TASK_9_SUMMARY.md          # Task 9 implementation summary
│   ├── TASK_10_SUMMARY.md         # Task 10 implementation summary
│   ├── TASK_11_SUMMARY.md         # Task 11 implementation summary
│   ├── TASK_12_SUMMARY.md         # Task 12 implementation summary
│   ├── TASK_13_SUMMARY.md         # Task 13 implementation summary
│   ├── TASK_14_SUMMARY.md         # Task 14 implementation summary
│   ├── TASK_15_SUMMARY.md         # Task 15 implementation summary
│   └── TASK_16_SUMMARY.md         # Task 16 implementation summary
│
├── .gitignore                       # Git ignore patterns
├── .pytest_cache/                   # Pytest cache (gitignored)
├── htmlcov/                         # Coverage HTML report (gitignored)
├── Makefile                         # Common commands
├── pytest.ini                       # Pytest configuration
├── README.md                        # Technical documentation
├── OVERVIEW.md                      # High-level overview
├── PROJECT_STRUCTURE.md             # This file
├── QUICKSTART.md                    # Quick start tutorial
├── DEPLOYMENT.md                    # Deployment guide
├── requirements.txt                 # Production dependencies
├── requirements-dev.txt             # Development dependencies
├── setup.py                         # Package configuration
└── validate_structure.py            # Structure validation script
```

## File Counts

### Production Code
- **Lambda**: 3 files, ~200 statements
- **Models**: 4 files, ~125 statements
- **Audio Quality Models**: 5 files, ~360 statements
- **Services**: 12 files, ~660 statements (includes feature_flag_service.py)
- **Utils**: 3 files, ~49 statements
- **Infrastructure**: 2 files, ~400 statements (updated with SSM parameter)
- **Scripts**: 2 files, ~650 statements (rollout management and testing)
- **Total**: 31 files, ~2,444 statements

### Test Code
- **Unit Tests**: 10 files, 190 tests
- **Integration Tests**: 1 file, 7 tests
- **Fixtures**: 1 file
- **Total**: 12 files, ~3,000 lines

### Documentation
- **Root Documentation**: 6 files (README, OVERVIEW, PROJECT_STRUCTURE, QUICKSTART, DEPLOYMENT, DEPLOYMENT_CHECKLIST)
- **Transcription Task Summaries**: 16 files (TASK_1 through TASK_16)
- **Audio Quality Task Summaries**: 1 file (TASK_1)
- **Deployment Guides**: 2 files (DEPLOYMENT_ROLLOUT_GUIDE, ROLLBACK_RUNBOOK)
- **Total**: 25 files, ~15,500 lines

## File Descriptions

### Production Code

#### `audio_quality/models/`
Data models for audio quality validation and configuration.

- **`quality_config.py`** (95 statements)
  - `QualityConfig`: Configuration for quality thresholds (SNR, clipping, echo, silence)
  - Validation method with 15+ validation rules
  - Default values aligned with requirements

- **`quality_metrics.py`** (58 statements)
  - `QualityMetrics`: Aggregated quality measurements for analysis window
  - Includes SNR, clipping, echo, and silence metrics
  - Serialization support with `to_dict()` method

- **`audio_format.py`** (85 statements)
  - `AudioFormat`: Audio format specification and validation
  - Supports 8/16/24/48 kHz sample rates, 16-bit depth, mono
  - `is_valid()` and `get_validation_errors()` methods

- **`quality_event.py`** (70 statements)
  - `QualityEvent`: Quality degradation events for EventBridge
  - Event types: snr_low, clipping, echo, silence
  - `to_eventbridge_entry()` for EventBridge integration

- **`results.py`** (50 statements)
  - `ClippingResult`: Clipping detection results
  - `EchoResult`: Echo detection results
  - `SilenceResult`: Silence detection results

#### `shared/models/`
Data models for transcription results and configuration.

- **`transcription_results.py`** (80 statements)
  - `PartialResult`: Intermediate transcription with stability score
  - `FinalResult`: Completed transcription segment
  - `BufferedResult`: Partial result in buffer with metadata
  - `ResultMetadata`: Extracted event metadata

- **`configuration.py`** (25 statements)
  - `PartialResultConfig`: Configuration with validation
  - Validates stability threshold (0.70-0.95)
  - Validates buffer timeout (2-10 seconds)

- **`cache.py`** (16 statements)
  - `CacheEntry`: Deduplication cache entry with TTL
  - `is_expired()`: Check if entry has expired

#### `shared/services/`
Business logic services for processing.

- **`deduplication_cache.py`** (57 statements)
  - `DeduplicationCache`: Prevent duplicate synthesis
  - `contains()`: Check if text exists in cache
  - `add()`: Add text with TTL
  - `cleanup_expired()`: Remove expired entries
  - Opportunistic cleanup every 30 seconds
  - Emergency cleanup at 10,000 entries

- **`rate_limiter.py`** (50 statements)
  - `RateLimiter`: Limit processing to 5 results per second
  - `should_process()`: Buffer results in 200ms windows
  - `get_best_result_in_window()`: Select highest stability
  - `flush_window()`: Process best result from window
  - `get_statistics()`: Track processed/dropped counts

- **`result_buffer.py`** (65 statements)
  - `ResultBuffer`: Store partial results awaiting finalization
  - `add()`: Add partial result with capacity check
  - `remove_by_id()`: Remove specific result
  - `get_orphaned_results()`: Find results older than timeout
  - `sort_by_timestamp()`: Chronological ordering
  - Capacity: 300 words (30 words/sec × 10 sec)

- **`sentence_boundary_detector.py`** (38 statements)
  - `SentenceBoundaryDetector`: Detect complete sentences
  - `is_complete_sentence()`: Check if result is complete
  - `update_last_result_time()`: Track pause detection
  - Detection methods: punctuation (. ? !), pause (2s), buffer timeout (5s), final results
  - Configurable thresholds for pause and buffer timeout

- **`translation_forwarder.py`** (25 statements)
  - `TranslationForwarder`: Forward results to translation pipeline with deduplication
  - `TranslationPipeline`: Protocol defining translation pipeline interface
  - `forward()`: Forward text if not duplicate, update cache
  - `_should_skip_duplicate()`: Check deduplication cache
  - Prevents duplicate synthesis of identical text segments

- **`partial_result_handler.py`** (55 statements)
  - `PartialResultHandler`: Orchestrates partial result processing pipeline
  - `process()`: Main processing flow with stability filtering

- **`final_result_handler.py`** (62 statements)
  - `FinalResultHandler`: Processes final transcription results
  - `process()`: Removes partials, checks duplicates, forwards to translation
  - `_calculate_discrepancy()`: Levenshtein distance calculation for quality monitoring
  - `_should_forward_based_on_stability()`: Stability check with timeout fallback
  - `_is_complete_sentence()`: Sentence boundary detection integration
  - `_forward_to_translation()`: Forward to translation and mark as forwarded
  - Implements rate limiting, buffering, and deduplication

- **`transcription_event_handler.py`** (78 statements)
  - `TranscriptionEventHandler`: Receives and parses AWS Transcribe events
  - `handle_event()`: Main event processing with error handling
  - `_extract_result_metadata()`: Parse event structure with defensive null checks
  - `_extract_stability_score()`: Extract stability with comprehensive validation
  - `_handle_partial_result()`: Route partial results to PartialResultHandler
  - `_handle_final_result()`: Route final results to FinalResultHandler
  - Implements defensive parsing and graceful error handling

- **`partial_result_processor.py`** (60 statements)
  - `PartialResultProcessor`: Main coordinator for partial results processing
  - `__init__()`: Initialize all sub-components in dependency order
  - `_load_config_from_environment()`: Load configuration from environment variables
  - `process_partial()`: Async processing of partial results
  - `process_final()`: Async processing of final results
  - `_cleanup_orphans_if_needed()`: Opportunistic orphan cleanup every 5 seconds
  - Integrates all components into cohesive pipeline

- **`transcribe_stream_handler.py`** (78 statements)
  - `TranscribeStreamHandler`: Async handler for AWS Transcribe streaming events
  - `handle_transcript_event()`: Process transcription events asynchronously
  - `_process_result()`: Extract metadata and route to processor
  - `_extract_stability_score()`: Extract stability with null safety and validation
  - Defensive null checks for all event fields
  - Generates result_id if missing from event
  - Clamps stability scores to [0.0, 1.0] range

- **`transcribe_client.py`** (49 statements)
  - `TranscribeClientConfig`: Configuration with validation
  - `TranscribeClientManager`: Manages client lifecycle
  - `create_transcribe_client_for_session()`: Convenience function
  - Validates language code, sample rate, encoding, stability level
  - Supports 4 sample rates: 8000, 16000, 24000, 48000 Hz
  - Supports 3 encodings: pcm, ogg-opus, flac
  - Defaults to partial results enabled with 'high' stability

#### `shared/utils/`
Utility functions for text processing and metrics.

- **`metrics.py`** (35 statements)
  - `MetricsEmitter`: CloudWatch metrics integration
  - `emit_dropped_results()`: Track rate-limited results
  - `emit_processing_latency()`: Track processing time
  - `emit_partial_to_final_ratio()`: Track result ratios
  - `emit_duplicates_detected()`: Track duplicates
  - `emit_orphaned_results_flushed()`: Track orphans

- **`text_normalization.py`** (14 statements)
  - `normalize_text()`: Lowercase, remove punctuation, collapse spaces
  - `hash_text()`: SHA-256 hash of normalized text

### Test Code

#### `tests/unit/`
Comprehensive unit tests with 97% coverage.

- **`test_data_models.py`** (30 tests)
  - PartialResult validation (7 tests)
  - FinalResult validation (4 tests)
  - BufferedResult validation (2 tests)
  - ResultMetadata validation (2 tests)
  - PartialResultConfig validation (9 tests)
  - CacheEntry validation (5 tests)
  - Edge cases: empty strings, invalid ranges, None values

- **`test_text_normalization.py`** (21 tests)
  - Text normalization (12 tests)
  - Hash generation (9 tests)
  - Edge cases: empty, punctuation-only, unicode, long text

- **`test_transcribe_stream_handler.py`** (13 tests)
  - Partial result handling with/without stability (2 tests)
  - Final result handling (1 test)
  - Missing/malformed event fields (4 tests)
  - Stability score extraction edge cases (6 tests)
  - Edge cases: out of range, negative, invalid type

- **`test_transcribe_client.py`** (15 tests)
  - TranscribeClientConfig validation (9 tests)
  - TranscribeClientManager operations (4 tests)
  - Convenience function (2 tests)
  - Edge cases: invalid parameters, all valid combinations

- **`test_deduplication_cache.py`** (20 tests)
  - Cache operations (11 tests)
  - TTL expiration (3 tests)
  - Cleanup mechanisms (3 tests)
  - Edge cases: empty strings, long text, overflow

- **`test_rate_limiter.py`** (15 tests)
  - Rate limiter initialization and configuration
  - Window-based buffering and best result selection
  - Statistics tracking and reset
  - Edge cases: None stability, ties, empty buffer

- **`test_result_buffer.py`** (23 tests)
  - Buffer operations: add, remove, get, mark forwarded
  - Orphan detection and cleanup
  - Capacity management and flush logic
  - Edge cases: out-of-order timestamps, overflow

- **`test_sentence_boundary_detector.py`** (29 tests)
  - Punctuation detection (. ? !)
  - Pause threshold detection
  - Buffer timeout detection
  - Final result handling
  - Edge cases: whitespace, exact boundaries

- **`test_translation_forwarder.py`** (included in integration tests)
  - Forwarding with deduplication
  - Error handling
  - Cache integration

- **`test_partial_result_handler.py`** (17 tests)
  - Rate limiter initialization (2 tests)
  - Buffering and selection (5 tests)

- **`test_final_result_handler.py`** (15 tests)
  - Partial removal by ID and timestamp (3 tests)
  - Deduplication cache checking (2 tests)
  - Discrepancy calculation (4 tests)
  - Warning logs and edge cases (6 tests)
  - Window flushing (3 tests)
  - Statistics tracking (2 tests)
  - Edge cases: missing stability, ties, empty buffers

- **`test_transcription_event_handler.py`** (20 tests)
  - Event parsing with valid events (3 tests)
  - Routing logic for partial vs final (1 test)
  - Malformed event handling (10 tests)
  - Null safety for Items array (4 tests)
  - Metadata extraction and timestamps (2 tests)

#### `tests/integration/`
End-to-end integration tests.

- **`test_partial_result_processor.py`** (7 tests)
  - End-to-end partial to translation latency (<200ms)
  - Rate limiting with 20 partials in 1 second
  - Orphan cleanup after 15-second timeout
  - Fallback when stability scores unavailable
  - Out-of-order result handling with timestamp sorting
  - Deduplication prevents double synthesis
  - Complete workflow: partial followed by final

- **`test_result_buffer.py`** (23 tests)
  - Buffer operations (9 tests)
  - Capacity management (3 tests)
  - Orphan detection (2 tests)
  - Edge cases: out-of-order, session tracking

- **`test_sentence_boundary_detector.py`** (29 tests)
  - Initialization and validation (6 tests)
  - Punctuation detection (7 tests)
  - Pause detection (5 tests)
  - Buffer timeout detection (3 tests)
  - Final result handling (3 tests)
  - Combined conditions (5 tests)
  - Orphan detection (2 tests)
  - Timestamp ordering (2 tests)
  - Edge cases: out-of-order, overflow, nonexistent results

- **`conftest.py`**
  - Shared pytest fixtures
  - Valid partial/final/buffered results
  - Default and custom configurations

### Documentation

#### Root-Level Docs

- **`README.md`** (~400 lines)
  - Technical architecture
  - Development guide
  - Configuration reference
  - Troubleshooting

- **`OVERVIEW.md`** (~150 lines)
  - High-level summary
  - Current status
  - Quick commands
  - Documentation guide

- **`PROJECT_STRUCTURE.md`** (this file, ~250 lines)
  - Complete file tree
  - File descriptions
  - Statistics

- **`QUICKSTART.md`** (~200 lines)
  - 5-minute setup tutorial
  - First test run
  - Development workflow

- **`DEPLOYMENT.md`** (~300 lines)
  - Deployment procedures
  - Environment configuration
  - Rollback procedures

#### Task Summaries

- **`docs/TASK_1_SUMMARY.md`** (~200 lines)
  - Core data models implementation
  - 30 tests, 94% coverage

- **`docs/TASK_2_SUMMARY.md`** (~250 lines)
  - Text normalization and deduplication
  - 41 tests, 96% coverage

- **`docs/TASK_3_SUMMARY.md`** (~250 lines)
  - Result buffer with capacity management
  - 23 tests, 97% coverage

- **`docs/TASK_4_SUMMARY.md`** (~300 lines)
  - Rate limiter with sliding windows
  - 15 tests, 98% coverage

- **`docs/TASK_5_SUMMARY.md`** (~350 lines)
  - Sentence boundary detector with multiple detection methods
  - 29 tests, 97% coverage

- **`docs/TASK_6_SUMMARY.md`** (~300 lines)
  - Translation forwarder with deduplication
  - Integration tests

- **`docs/TASK_7_SUMMARY.md`** (~300 lines)
  - Partial result handler with stability filtering
  - 17 tests, 96% coverage

- **`docs/TASK_8_SUMMARY.md`** (~300 lines)
  - Final result handler with discrepancy tracking
  - 15 tests, 98% coverage

- **`docs/TASK_9_SUMMARY.md`** (~350 lines)
  - Transcription event handler with defensive parsing
  - 20 tests, 97% coverage

- **`docs/TASK_10_SUMMARY.md`** (~400 lines)
  - Main partial result processor coordinator
  - 7 integration tests, 90% coverage

## Dependencies

### Production (`requirements.txt`)
```
boto3>=1.28.0              # AWS SDK
botocore>=1.31.0           # AWS SDK core
librosa>=0.10.0            # Audio analysis
numpy>=1.24.0              # Numerical computing
soundfile>=0.12.0          # Audio I/O
PyJWT>=2.8.0               # JWT validation
cryptography>=41.0.0       # JWT signatures
requests>=2.31.0           # HTTP client
python-Levenshtein>=0.21.0 # Text similarity
```

### Development (`requirements-dev.txt`)
```
pytest>=7.4.0              # Testing framework
pytest-asyncio>=0.21.0     # Async testing
pytest-cov>=4.1.0          # Coverage reporting
moto>=4.2.0                # AWS mocking
pylint>=2.17.0             # Linting
flake8>=6.0.0              # Style checking
black>=23.0.0              # Code formatting
mypy>=1.4.0                # Type checking
```

## Statistics

### Code Metrics
- **Production Code**: ~975 lines
- **Test Code**: ~3,000 lines
- **Documentation**: ~3,200 lines
- **Test/Code Ratio**: 3.1:1
- **Coverage**: 90%

### File Counts
- **Python Files**: 24 (14 production, 10 test)
- **Documentation Files**: 16
- **Configuration Files**: 5
- **Total Files**: 45

### Test Metrics
- **Total Tests**: 197 (190 unit + 7 integration)
- **Test Execution Time**: ~12 seconds
- **Tests per File**: ~18 average
- **Coverage**: 90% (exceeds 80% requirement)

## Future Structure

As development progresses, these directories will be added:

```
audio-transcription/
├── lambda/                          # Lambda function handlers
│   ├── audio_processor/            # Main audio processor
│   │   ├── handler.py              # Lambda entry point
│   │   └── requirements.txt        # Function dependencies
│   └── layers/                     # Lambda layers (optional)
│
├── infrastructure/                  # Component-specific IaC
│   ├── stacks/
│   │   └── audio_transcription_stack.py
│   ├── app.py                      # CDK app entry
│   └── cdk.json                    # CDK config
│
└── tests/
    └── integration/                 # Integration tests
        └── test_end_to_end.py
```

## Navigation Tips

### Finding Code
- **Models**: `shared/models/` - All dataclasses
- **Business Logic**: `shared/services/` - Cache, buffer, handlers
- **Utilities**: `shared/utils/` - Text processing, helpers

### Finding Tests
- **Unit Tests**: `tests/unit/test_*.py` - Mirrors source structure
- **Fixtures**: `tests/conftest.py` - Reusable test data

### Finding Documentation
- **Getting Started**: `QUICKSTART.md`
- **Architecture**: `README.md`
- **Current Status**: `OVERVIEW.md`
- **File Organization**: `PROJECT_STRUCTURE.md` (this file)
- **Implementation Details**: `docs/TASK_*_SUMMARY.md`
