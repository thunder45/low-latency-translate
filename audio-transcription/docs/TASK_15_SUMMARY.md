# Task 15: Update Infrastructure Configuration

## Task Description

Created AWS CDK infrastructure configuration for the Audio Transcription component with partial results processing support, including Lambda function configuration, CloudWatch alarms, and environment-specific settings.

## Task Instructions

From the specification:

**15.1 Update Lambda function configuration**
- Increase memory to 512 MB (monitor and increase to 768 MB if needed)
- Increase timeout to 60 seconds
- Add environment variables for all configuration parameters
- _Requirements: 6.1, 6.2_

**15.2 Add CloudWatch alarms for monitoring**
- Create alarm for end-to-end latency p95 > 5 seconds
- Create alarm for partial results dropped > 100/minute
- Create alarm for orphaned results > 10/session
- Create alarm for Transcribe fallback triggered
- _Requirements: 4.3_

## Task Solution

### Infrastructure Created

Created complete AWS CDK infrastructure in `audio-transcription/infrastructure/`:

1. **CDK Stack** (`stacks/audio_transcription_stack.py`):
   - Lambda function with 512 MB memory and 60-second timeout
   - IAM role with least privilege permissions for Transcribe, DynamoDB, CloudWatch
   - 6 CloudWatch alarms for comprehensive monitoring
   - SNS topic for alarm notifications

2. **CDK App** (`app.py`):
   - Environment-specific deployment support (dev, staging, prod)
   - Configuration loading from JSON files
   - Proper tagging and naming conventions

3. **Configuration Files** (`config/`):
   - `dev.json.example` - Development environment settings
   - `staging.json.example` - Staging environment settings
   - `prod.json.example` - Production environment settings

4. **Documentation** (`README.md`):
   - Comprehensive deployment guide
   - Configuration reference
   - Monitoring and troubleshooting procedures
   - Cost estimation
   - Security considerations

### Lambda Function Configuration

**Memory**: 512 MB (increased from 256 MB)
- Breakdown:
  - Base runtime: ~100 MB
  - boto3 SDK: ~50 MB
  - Emotion detection: ~100 MB
  - Emotion model: ~200 MB
  - Buffers and cache: ~2 MB
  - Total: ~452 MB
- Recommendation: Start with 512 MB, monitor usage, increase to 768 MB if memory pressure detected

**Timeout**: 60 seconds (increased from 30 seconds)
- Allows for opportunistic orphan cleanup every 5 seconds
- Handles longer audio processing sessions

**Environment Variables**:
```
PARTIAL_RESULTS_ENABLED=true
MIN_STABILITY_THRESHOLD=0.85
MAX_BUFFER_TIMEOUT=5.0
PAUSE_THRESHOLD=2.0
ORPHAN_TIMEOUT=15.0
MAX_RATE_PER_SECOND=5
DEDUP_CACHE_TTL=10
AWS_REGION=<region>
SESSIONS_TABLE_NAME=Sessions
LOG_LEVEL=INFO
STRUCTURED_LOGGING=true
```

### IAM Permissions

Created least privilege IAM role with permissions for:
- **AWS Transcribe**: `StartStreamTranscription`, `StartStreamTranscriptionWebSocket`
- **CloudWatch Metrics**: `PutMetricData` (limited to `AudioTranscription/PartialResults` namespace)
- **DynamoDB**: `GetItem`, `Query` (limited to Sessions table)
- **CloudWatch Logs**: Basic execution role for logging

### CloudWatch Alarms

Created 6 alarms for comprehensive monitoring:

1. **Latency High** (CRITICAL)
   - Metric: `PartialResultProcessingLatency` p95
   - Threshold: > 5000 ms
   - Evaluation: 2 periods of 5 minutes

2. **Rate Limit High** (WARNING)
   - Metric: `PartialResultsDropped`
   - Threshold: > 100 per minute
   - Evaluation: 2 periods of 1 minute

3. **Orphaned Results High** (WARNING)
   - Metric: `OrphanedResultsFlushed`
   - Threshold: > 10
   - Evaluation: 2 periods of 5 minutes

4. **Transcribe Fallback** (CRITICAL)
   - Metric: `TranscribeFallbackTriggered`
   - Threshold: >= 1
   - Evaluation: 1 period of 5 minutes

5. **Lambda Errors** (CRITICAL)
   - Metric: Lambda Errors
   - Threshold: > 5
   - Evaluation: 1 period of 5 minutes

6. **Lambda Throttles** (WARNING)
   - Metric: Lambda Throttles
   - Threshold: > 10
   - Evaluation: 1 period of 5 minutes

All alarms send notifications to SNS topic for alerting.

### Deployment Commands

```bash
# Install dependencies
cd audio-transcription/infrastructure
pip install -r requirements.txt

# Deploy to development
cdk deploy --context environment=dev

# Deploy to staging
cdk deploy --context environment=staging

# Deploy to production
cdk deploy --context environment=prod

# View differences before deployment
cdk diff --context environment=dev

# Synthesize CloudFormation template
cdk synth --context environment=dev
```

### Rollback Procedures

**Disable Partial Results** (without redeployment):
```bash
aws lambda update-function-configuration \
  --function-name audio-processor \
  --environment Variables="{PARTIAL_RESULTS_ENABLED=false}"
```

**Full Rollback** (to previous version):
```bash
# List versions
aws lambda list-versions-by-function --function-name audio-processor

# Update alias to previous version
aws lambda update-alias \
  --function-name audio-processor \
  --name live \
  --function-version <previous-version>
```

### Cost Estimation

**Additional Monthly Costs**:
- Lambda execution: ~$2.00 (512 MB, 5s average duration, 1000 invocations/day)
- CloudWatch metrics: ~$1.80 (6 custom metrics)
- CloudWatch alarms: ~$0.60 (6 alarms)
- CloudWatch logs: ~$2.00 (INFO level logging)

**Total**: ~$6.40/month (negligible compared to overall system cost)

### Files Created

```
audio-transcription/infrastructure/
├── stacks/
│   ├── __init__.py
│   └── audio_transcription_stack.py
├── config/
│   ├── dev.json.example
│   ├── staging.json.example
│   └── prod.json.example
├── app.py
├── cdk.json
├── requirements.txt
└── README.md
```

### Key Design Decisions

1. **Memory Allocation**: Started with 512 MB based on component breakdown, with recommendation to increase to 768 MB if needed
2. **Timeout**: Set to 60 seconds to accommodate orphan cleanup and longer processing sessions
3. **Alarm Thresholds**: Based on design document requirements and operational experience
4. **Environment Variables**: All configuration parameters exposed for runtime tuning
5. **IAM Permissions**: Least privilege with specific resource constraints where possible
6. **SNS Topic**: Centralized alarm notifications for operational monitoring

### Integration Points

- **Lambda Function**: Reads configuration from environment variables
- **DynamoDB**: Sessions table for session-specific configuration
- **CloudWatch**: Custom metrics namespace `AudioTranscription/PartialResults`
- **SNS**: Alarm notifications for operational alerts

### Security Considerations

- IAM role follows least privilege principles
- CloudWatch metrics limited to specific namespace
- DynamoDB access limited to Sessions table
- No persistent storage of audio or transcripts
- All processing is ephemeral (in-memory only)

## Next Steps

1. Copy example configuration files and customize for your environment:
   ```bash
   cp config/dev.json.example config/dev.json
   # Edit config/dev.json with your settings
   ```

2. Deploy to development environment:
   ```bash
   cd audio-transcription/infrastructure
   pip install -r requirements.txt
   cdk deploy --context environment=dev
   ```

3. Monitor CloudWatch alarms and metrics after deployment

4. Adjust Lambda memory to 768 MB if memory pressure detected

5. Proceed to Task 16: Create deployment and rollout plan
