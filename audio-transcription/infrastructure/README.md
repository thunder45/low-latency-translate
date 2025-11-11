# Audio Transcription Infrastructure

This directory contains AWS CDK infrastructure code for the Audio Transcription component with partial results processing support.

## Overview

The infrastructure includes:
- **Lambda Function**: Audio processor with 512 MB memory and 60-second timeout
- **IAM Roles**: Least privilege permissions for Transcribe, DynamoDB, and CloudWatch
- **CloudWatch Alarms**: Monitoring for latency, rate limiting, orphaned results, and service health
- **SNS Topic**: Alarm notifications

## Prerequisites

- AWS CDK CLI installed (`npm install -g aws-cdk`)
- Python 3.11+
- AWS credentials configured
- CDK bootstrapped in target account/region

## Configuration

### Environment Variables

The Lambda function is configured with the following environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PARTIAL_RESULTS_ENABLED` | `true` | Enable/disable partial results processing |
| `MIN_STABILITY_THRESHOLD` | `0.85` | Minimum stability score to forward partial results (0.70-0.95) |
| `MAX_BUFFER_TIMEOUT` | `5.0` | Maximum time to buffer results in seconds (2-10) |
| `PAUSE_THRESHOLD` | `2.0` | Pause duration to trigger sentence boundary in seconds |
| `ORPHAN_TIMEOUT` | `15.0` | Time before flushing orphaned results in seconds |
| `MAX_RATE_PER_SECOND` | `5` | Maximum partial results to process per second |
| `DEDUP_CACHE_TTL` | `10` | Deduplication cache TTL in seconds |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Environment-Specific Configuration

Configuration files are located in `config/`:
- `dev.json.example` - Development environment
- `staging.json.example` - Staging environment
- `prod.json.example` - Production environment

Copy the example file and customize:
```bash
cp config/dev.json.example config/dev.json
# Edit config/dev.json with your settings
```

## Deployment

### Install Dependencies

```bash
cd infrastructure
pip install -r requirements.txt
```

### Deploy to Development

```bash
cdk deploy --context environment=dev
```

### Deploy to Staging

```bash
cdk deploy --context environment=staging
```

### Deploy to Production

```bash
cdk deploy --context environment=prod
```

### Synthesize CloudFormation Template

```bash
cdk synth --context environment=dev
```

### View Differences

```bash
cdk diff --context environment=dev
```

## Lambda Function Configuration

### Memory and Timeout

- **Memory**: 512 MB (increased from 256 MB)
  - Base runtime: ~100 MB
  - boto3 SDK: ~50 MB
  - Emotion detection: ~100 MB
  - Emotion model: ~200 MB
  - Buffers and cache: ~2 MB
  - Total: ~452 MB
  - Recommendation: Start with 512 MB, monitor usage, increase to 768 MB if needed

- **Timeout**: 60 seconds (increased from 30 seconds)
  - Allows for opportunistic orphan cleanup every 5 seconds
  - Handles longer audio processing sessions

### IAM Permissions

The Lambda function has permissions for:
- **AWS Transcribe**: Start streaming transcription
- **CloudWatch**: Put custom metrics (namespace: `AudioTranscription/PartialResults`)
- **DynamoDB**: Read session configuration from Sessions table
- **CloudWatch Logs**: Write logs (via AWSLambdaBasicExecutionRole)

## CloudWatch Alarms

### Critical Alarms

1. **Latency High** (`audio-transcription-latency-high`)
   - Metric: `PartialResultProcessingLatency` p95
   - Threshold: > 5000 ms
   - Evaluation: 2 periods of 5 minutes
   - Action: SNS notification

2. **Transcribe Fallback** (`audio-transcription-transcribe-fallback`)
   - Metric: `TranscribeFallbackTriggered`
   - Threshold: >= 1
   - Evaluation: 1 period of 5 minutes
   - Action: SNS notification

3. **Lambda Errors** (`audio-transcription-lambda-errors`)
   - Metric: Lambda Errors
   - Threshold: > 5
   - Evaluation: 1 period of 5 minutes
   - Action: SNS notification

### Warning Alarms

4. **Rate Limit High** (`audio-transcription-rate-limit-high`)
   - Metric: `PartialResultsDropped`
   - Threshold: > 100 per minute
   - Evaluation: 2 periods of 1 minute
   - Action: SNS notification

5. **Orphaned Results High** (`audio-transcription-orphaned-results-high`)
   - Metric: `OrphanedResultsFlushed`
   - Threshold: > 10
   - Evaluation: 2 periods of 5 minutes
   - Action: SNS notification

6. **Lambda Throttles** (`audio-transcription-lambda-throttles`)
   - Metric: Lambda Throttles
   - Threshold: > 10
   - Evaluation: 1 period of 5 minutes
   - Action: SNS notification

## Monitoring

### Custom Metrics

The Lambda function emits the following custom metrics to CloudWatch:

| Metric | Unit | Description |
|--------|------|-------------|
| `PartialResultProcessingLatency` | Milliseconds | Time to process partial result |
| `PartialResultsDropped` | Count | Number of partial results dropped due to rate limiting |
| `PartialToFinalRatio` | None | Ratio of partial to final results processed |
| `DuplicatesDetected` | Count | Number of duplicate texts detected |
| `OrphanedResultsFlushed` | Count | Number of orphaned results flushed |
| `TranscribeFallbackTriggered` | Count | Number of times fallback to final-only mode triggered |

All metrics are in the `AudioTranscription/PartialResults` namespace.

### CloudWatch Dashboard

Create a dashboard to visualize metrics:

```bash
# TODO: Add dashboard creation command or link to console
```

## Rollback Procedures

### Disable Partial Results

To disable partial results processing without redeployment:

1. Update Lambda environment variable:
   ```bash
   aws lambda update-function-configuration \
     --function-name audio-processor \
     --environment Variables="{PARTIAL_RESULTS_ENABLED=false}"
   ```

2. System automatically falls back to final-result-only mode

### Full Rollback

To rollback to previous version:

```bash
# List versions
aws lambda list-versions-by-function --function-name audio-processor

# Update alias to previous version
aws lambda update-alias \
  --function-name audio-processor \
  --name live \
  --function-version <previous-version>
```

## Troubleshooting

### High Latency

If `PartialResultProcessingLatency` p95 > 5 seconds:
1. Check CloudWatch Logs for errors
2. Verify Transcribe service health
3. Check rate limiting metrics
4. Consider increasing Lambda memory to 768 MB

### High Rate Limiting

If `PartialResultsDropped` > 100/minute:
1. Review `MAX_RATE_PER_SECOND` setting (consider increasing to 7-10)
2. Check if continuous speech is causing excessive partials
3. Verify stability threshold is appropriate

### Orphaned Results

If `OrphanedResultsFlushed` > 10/session:
1. Check Transcribe service health
2. Review CloudWatch Logs for Transcribe errors
3. Verify network connectivity
4. Check if `ORPHAN_TIMEOUT` is too aggressive (consider increasing to 20-30s)

### Lambda Errors

If Lambda errors > 5:
1. Check CloudWatch Logs for stack traces
2. Verify IAM permissions
3. Check DynamoDB table availability
4. Verify Transcribe API availability

## Cost Estimation

### Lambda Costs

- **Memory**: 512 MB
- **Duration**: ~5 seconds per invocation (average)
- **Invocations**: ~1000 per day (100 sessions × 10 audio chunks)
- **Monthly Cost**: ~$2.00

### CloudWatch Costs

- **Custom Metrics**: 6 metrics × $0.30/metric = $1.80/month
- **Alarms**: 6 alarms × $0.10/alarm = $0.60/month
- **Logs**: ~$2.00/month (with INFO level logging)

**Total Additional Cost**: ~$6.40/month

## Security

### IAM Least Privilege

The Lambda execution role follows least privilege principles:
- Only necessary AWS service permissions
- CloudWatch metrics limited to specific namespace
- DynamoDB access limited to Sessions table

### Data Privacy

- No persistent storage of audio or transcripts
- All processing is ephemeral (in-memory only)
- Logs do not contain PII or sensitive data

### Encryption

- Data in transit: TLS 1.2+ (AWS Transcribe, DynamoDB)
- Data at rest: AWS-managed encryption (CloudWatch Logs)

## References

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [AWS Transcribe Documentation](https://docs.aws.amazon.com/transcribe/)
- [CloudWatch Alarms Documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html)
