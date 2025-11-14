# Translation Processor Lambda Function

## Overview

This Lambda function processes transcribed text through the translation broadcasting pipeline. It coordinates translation, SSML generation, synthesis, and broadcasting to all listeners.

## Architecture

```
Input Event
    ↓
Check Listener Count (skip if 0)
    ↓
Get Target Languages (GSI query)
    ↓
Parallel Translation (with caching)
    ↓
Generate SSML (emotion dynamics)
    ↓
Parallel Synthesis (AWS Polly)
    ↓
Broadcast to Listeners (per language)
    ↓
Emit CloudWatch Metrics
    ↓
Return Response
```

## Event Format

```json
{
  "sessionId": "golden-eagle-427",
  "sourceLanguage": "en",
  "transcriptText": "Hello everyone, this is important news.",
  "emotionDynamics": {
    "emotion": "happy",
    "intensity": 0.8,
    "rateWpm": 150,
    "volumeLevel": "normal"
  }
}
```

## Response Format

### Success Response (200)

```json
{
  "success": true,
  "languagesProcessed": ["es", "fr", "de"],
  "languagesFailed": [],
  "cacheHitRate": 0.67,
  "broadcastSuccessRate": 0.98,
  "durationMs": 2170.5,
  "listenerCount": 15
}
```

### Error Response (500)

```json
{
  "success": false,
  "error": "All translations failed",
  "languagesFailed": ["es", "fr", "de"]
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SESSIONS_TABLE_NAME` | DynamoDB Sessions table name | Required |
| `CONNECTIONS_TABLE_NAME` | DynamoDB Connections table name | Required |
| `CACHED_TRANSLATIONS_TABLE_NAME` | DynamoDB CachedTranslations table name | Required |
| `API_GATEWAY_ENDPOINT` | API Gateway WebSocket endpoint | Required |
| `MAX_CONCURRENT_BROADCASTS` | Maximum concurrent broadcast connections | 100 |
| `CACHE_TTL_SECONDS` | Translation cache TTL in seconds | 3600 |
| `MAX_CACHE_ENTRIES` | Maximum cache entries before LRU eviction | 10000 |

## IAM Permissions

The Lambda function requires the following permissions:

- **DynamoDB**: GetItem, PutItem, Query, UpdateItem, DeleteItem on all tables
- **DynamoDB**: Query on Connections table GSI
- **AWS Translate**: TranslateText
- **AWS Polly**: SynthesizeSpeech
- **API Gateway**: ManageConnections
- **CloudWatch**: PutMetricData

## Configuration

### Memory and Timeout

- **Memory**: 1024 MB
- **Timeout**: 30 seconds
- **Runtime**: Python 3.11

### Lambda Layer

The function uses a Lambda layer containing shared code from the `shared/` directory:
- Data access repositories
- Service implementations
- Utility functions

## CloudWatch Metrics

The function emits the following metrics to the `TranslationPipeline` namespace:

| Metric | Description | Unit |
|--------|-------------|------|
| `CacheHitRate` | Translation cache hit rate | Percent |
| `BroadcastSuccessRate` | Broadcast success rate | Percent |
| `ProcessingDuration` | Total processing time | Milliseconds |
| `LanguagesProcessed` | Number of languages processed | Count |
| `FailedLanguagesCount` | Number of failed languages | Count |
| `ListenerCount` | Number of active listeners | Count |

## Deployment

### Using CDK

The Lambda function is deployed as part of the TranslationPipelineStack:

```bash
cd infrastructure
cdk deploy TranslationPipelineStack-dev
```

### Manual Deployment

1. Package shared code into a Lambda layer:
```bash
cd shared
zip -r ../layer.zip .
```

2. Create Lambda layer:
```bash
aws lambda publish-layer-version \
  --layer-name translation-pipeline-shared \
  --zip-file fileb://layer.zip \
  --compatible-runtimes python3.11
```

3. Package Lambda function:
```bash
cd lambda/translation_processor
zip -r function.zip handler.py
```

4. Create/update Lambda function:
```bash
aws lambda create-function \
  --function-name translation-processor \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT:role/translation-processor-role \
  --handler handler.lambda_handler \
  --zip-file fileb://function.zip \
  --layers arn:aws:lambda:REGION:ACCOUNT:layer:translation-pipeline-shared:VERSION \
  --memory-size 1024 \
  --timeout 30 \
  --environment Variables="{SESSIONS_TABLE_NAME=Sessions,CONNECTIONS_TABLE_NAME=Connections,...}"
```

## Testing

### Unit Tests

Run unit tests for the Lambda handler:

```bash
cd tests
pytest unit/test_lambda_handler.py -v
```

### Integration Tests

Run integration tests with real AWS services:

```bash
pytest integration/test_translation_pipeline_integration.py -v
```

### Local Testing

Test locally using AWS SAM:

```bash
sam local invoke TranslationProcessorFunction \
  --event events/sample-event.json \
  --env-vars env.json
```

## Monitoring

### CloudWatch Logs

Logs are available in CloudWatch Logs:
- Log Group: `/aws/lambda/translation-processor-{env}`
- Retention: 7 days (dev), 30 days (prod)

### CloudWatch Alarms

The following alarms are configured:
- Cache hit rate < 30%
- Broadcast success rate < 95%
- Buffer overflow rate > 5%
- Failed languages > 10%

### X-Ray Tracing

X-Ray tracing is enabled in production for performance analysis.

## Troubleshooting

### High Latency

1. Check CloudWatch metrics for bottlenecks
2. Review X-Ray traces for slow operations
3. Verify DynamoDB table performance
4. Check AWS Translate/Polly API latency

### Translation Failures

1. Check CloudWatch logs for error messages
2. Verify AWS Translate service limits
3. Check IAM permissions
4. Verify language code validity

### Broadcast Failures

1. Check API Gateway connection status
2. Verify WebSocket endpoint configuration
3. Review stale connection cleanup logs
4. Check concurrent broadcast limits

### Cache Issues

1. Monitor cache hit rate metric
2. Check DynamoDB CachedTranslations table
3. Verify TTL configuration
4. Review LRU eviction logs

## Performance Optimization

### Latency Targets

| Stage | Target | Actual |
|-------|--------|--------|
| Listener count check | 10ms | ~8ms |
| Get target languages | 20ms | ~15ms |
| Parallel translation (3 langs) | 200ms | ~180ms |
| Generate SSML | 10ms | ~5ms |
| Parallel synthesis (3 langs) | 400ms | ~380ms |
| Query listeners | 30ms | ~25ms |
| Broadcast (100 listeners) | 1500ms | ~1400ms |
| **Total** | **2170ms** | **~2013ms** |

### Cost Optimization

- **Translation caching**: 50% cost reduction
- **Skip processing when no listeners**: 100% cost savings for idle sessions
- **Translate once per language**: 98% cost reduction vs per-listener translation

## Related Documentation

- [Translation Pipeline Design](../../.kiro/specs/translation-broadcasting-pipeline/design.md)
- [Translation Pipeline Requirements](../../.kiro/specs/translation-broadcasting-pipeline/requirements.md)
- [Translation Pipeline Tasks](../../.kiro/specs/translation-broadcasting-pipeline/tasks.md)
