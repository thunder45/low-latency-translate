# Real-Time Audio Transcription with Partial Results

Real-time audio transcription component with intelligent partial results processing for the Low Latency Translate platform.

## Overview

This component processes audio transcription results from AWS Transcribe Streaming API, implementing partial results processing to reduce end-to-end latency from 3-7 seconds to 2-4 seconds while maintaining ≥90% translation accuracy.

### Key Features

- **Partial Results Processing**: Forward high-stability partial results before final results arrive
- **Intelligent Buffering**: Buffer low-stability results until they stabilize or finalize
- **Rate Limiting**: Process maximum 5 partial results per second to control costs
- **Deduplication**: Prevent duplicate synthesis of identical text segments
- **Sentence Boundary Detection**: Identify complete sentences for natural speech synthesis
- **Orphan Cleanup**: Automatically flush partial results that never finalize
- **Configurable**: Per-session configuration of stability thresholds and timeouts

## Architecture

```
AWS Lambda Handler (sync/async bridge)
    ↓
AWS Transcribe Streaming API
    ↓
TranscribeStreamHandler (async event handler)
    ↓
Transcription Event Handler → Partial Result Processor
                                      ↓
                              Result Buffer
                                      ↓
                          Deduplication Cache
                                      ↓
                          Translation Pipeline
```

### Components

1. **Lambda Handler**: Bridges synchronous Lambda interface with async Transcribe processing
2. **TranscribeStreamHandler**: Async handler for AWS Transcribe streaming events with null safety
3. **TranscribeClientManager**: Manages Transcribe client lifecycle and configuration
4. **Transcription Event Handler**: Receives and parses AWS Transcribe events
5. **Partial Result Handler**: Processes partial results with stability filtering
6. **Final Result Handler**: Processes final results and cleans up partials
7. **Result Buffer**: Stores partial results awaiting finalization
8. **Deduplication Cache**: Prevents duplicate synthesis
9. **Sentence Boundary Detector**: Identifies complete sentences
10. **Rate Limiter**: Controls processing rate (5 per second)
11. **Translation Forwarder**: Forwards results to translation pipeline
12. **Health Monitor**: Tracks Transcribe service health and enables fallback mode

## Getting Started

### Prerequisites

- Python 3.11+
- AWS account with Transcribe, Translate, and Polly access
- boto3 configured with appropriate credentials

### Installation

```bash
# Install dependencies
make install

# Or manually
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/unit/test_data_models.py -v

# Run with coverage
pytest --cov=shared --cov=lambda --cov-report=html
```

### Code Quality

```bash
# Format code
make format

# Run linters
make lint
```

## Infrastructure

### AWS CDK Deployment

Infrastructure is defined using AWS CDK in the `infrastructure/` directory.

**Quick Deployment**:
```bash
cd infrastructure
pip install -r requirements.txt
cdk deploy --context environment=dev
```

**Components**:
- Lambda function (512 MB memory, 60s timeout)
- IAM roles with least privilege permissions
- CloudWatch alarms for monitoring
- SNS topic for alarm notifications

See [infrastructure/README.md](infrastructure/README.md) for detailed deployment instructions.

### Lambda Configuration

**Memory**: 512 MB (increase to 768 MB if memory pressure detected)
**Timeout**: 60 seconds (for orphan cleanup)

## Configuration

### Environment Variables

Lambda function configuration:

```bash
PARTIAL_RESULTS_ENABLED=true              # Enable/disable partial results
MIN_STABILITY_THRESHOLD=0.85              # Minimum stability to forward (0.70-0.95)
MAX_BUFFER_TIMEOUT=5.0                    # Maximum buffer timeout (2-10 seconds)
PAUSE_THRESHOLD=2.0                       # Pause detection threshold (seconds)
ORPHAN_TIMEOUT=15.0                       # Orphan cleanup timeout (seconds)
MAX_RATE_PER_SECOND=5                     # Maximum partial results per second
DEDUP_CACHE_TTL=10                        # Deduplication cache TTL (seconds)
DEDUP_CACHE_TTL=10                        # Deduplication cache TTL (seconds)
```

### Per-Session Configuration

Sessions can override default configuration via query parameters:

```
?partialResults=true&minStability=0.90&maxBufferTimeout=7.0
```

## Development

### Project Structure

```
audio-transcription/
├── shared/                    # Shared code
│   ├── models/               # Data models
│   ├── data_access/          # Repository pattern
│   ├── services/             # Business logic
│   └── utils/                # Utilities
├── lambda/                   # Lambda functions
│   ├── audio_processor/      # Main audio processor
│   └── layers/               # Lambda layers
├── infrastructure/           # CDK infrastructure
├── tests/                    # All tests
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   └── fixtures/            # Test fixtures
└── docs/                    # Documentation
    └── TASK_*_SUMMARY.md    # Task summaries
```

### Development Workflow

1. Create feature branch
2. Implement changes with tests
3. Run tests: `make test`
4. Format code: `make format`
5. Run linters: `make lint`
6. Submit PR

## Performance Targets

- **End-to-End Latency**: 2-4 seconds (target), <5 seconds (maximum)
- **Translation Accuracy**: ≥90% vs final-only mode
- **Processing Overhead**: <5% of real-time duration
- **Rate Limiting**: 5 partial results per second per session
- **Cache Hit Rate**: >30% for translation cache

## Monitoring

### CloudWatch Metrics

- `PartialResultProcessingLatency` - Processing time (p50, p95, p99)
- `PartialResultsDropped` - Count of rate-limited results
- `PartialToFinalRatio` - Ratio of partial to final results
- `DuplicatesDetected` - Count of duplicate text segments
- `OrphanedResultsFlushed` - Count of orphaned results

### CloudWatch Alarms

- End-to-end latency p95 > 5 seconds (Critical)
- Partial results dropped > 100/minute (Warning)
- Orphaned results > 10/session (Warning)
- Transcribe fallback triggered (Critical)

## Deployment

### Development Environment

```bash
make deploy-dev
```

### Staging Environment

```bash
make deploy-staging
```

### Production Environment

```bash
make deploy-prod
```

## Troubleshooting

### Common Issues

**Issue**: Partial results not being forwarded
- Check `MIN_STABILITY_THRESHOLD` configuration
- Verify stability scores are available for source language
- Check rate limiter metrics

**Issue**: High duplicate detection rate
- Verify deduplication cache TTL is appropriate
- Check text normalization logic
- Review CloudWatch logs for cache behavior

**Issue**: Orphaned results accumulating
- Check AWS Transcribe service health
- Verify final results are arriving
- Review orphan timeout configuration

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for development guidelines.

## License

Internal use only - Low Latency Translate Platform

## Implementation Progress

### Completed Tasks

- ✅ [Task 1: Core Data Models and Configuration](docs/TASK_1_SUMMARY.md) - 30 tests, 94% coverage
- ✅ [Task 2: Text Normalization and Deduplication Cache](docs/TASK_2_SUMMARY.md) - 41 tests, 96% coverage
- ✅ [Task 3: Result Buffer with Capacity Management](docs/TASK_3_SUMMARY.md) - 23 tests, 97% coverage
- ✅ [Task 4: Rate Limiter](docs/TASK_4_SUMMARY.md) - 15 tests, 98% coverage
- ✅ [Task 5: Sentence Boundary Detector](docs/TASK_5_SUMMARY.md) - 29 tests, 97% coverage
- ✅ [Task 6: Translation Forwarder](docs/TASK_6_SUMMARY.md) - 138 tests, 86% coverage
- ✅ [Task 7: Partial Result Handler](docs/TASK_7_SUMMARY.md) - 17 tests, 96% coverage
- ✅ [Task 8: Final Result Handler](docs/TASK_8_SUMMARY.md) - 15 tests, 98% coverage
- ✅ [Task 9: Transcription Event Handler](docs/TASK_9_SUMMARY.md) - 20 tests, 97% coverage
- ✅ [Task 10: Main Partial Result Processor](docs/TASK_10_SUMMARY.md) - 7 integration tests, 90% coverage
- ✅ [Task 11: AWS Transcribe Streaming Integration](docs/TASK_11_SUMMARY.md) - 28 tests (13 stream handler, 15 client), 91.51% coverage
- ✅ [Task 12: Health Monitoring and Fallback](docs/TASK_12_SUMMARY.md) - 15 tests, 96% coverage
- ✅ [Task 13: CloudWatch Metrics Integration](docs/TASK_13_SUMMARY.md) - 12 tests, 94% coverage
- ✅ [Task 14: DynamoDB Session Schema Updates](docs/TASK_14_SUMMARY.md) - Session configuration support
- ✅ [Task 15: Infrastructure Configuration Updates](docs/TASK_15_SUMMARY.md) - Lambda and CloudWatch alarms
- ✅ [Task 16: Deployment and Rollout Plan](docs/TASK_16_SUMMARY.md) - Feature flags and rollback procedures

### In Progress

- None

### Planned

- None - All implementation tasks complete!

## References

- [Requirements Document](.kiro/specs/realtime-audio-transcription/requirements.md)
- [Design Document](.kiro/specs/realtime-audio-transcription/design.md)
- [Implementation Tasks](.kiro/specs/realtime-audio-transcription/tasks.md)
- [AWS Transcribe Documentation](https://docs.aws.amazon.com/transcribe/)
