# Translation Pipeline Monitoring Guide

## Overview

This document describes the monitoring and alerting setup for the translation broadcasting pipeline, including CloudWatch dashboards, alarms, metrics, and troubleshooting procedures.

## CloudWatch Dashboard

### Dashboard Name

`TranslationPipeline-{env}` (e.g., `TranslationPipeline-dev`, `TranslationPipeline-prod`)

### Dashboard Sections

#### 1. Cache Performance (Row 1)

**Cache Hit Rate**
- Metric: `TranslationPipeline/CacheHitRate`
- Statistic: Average
- Period: 5 minutes
- Target: >30%
- Description: Percentage of translations served from cache vs AWS Translate API

**Cache Size**
- Metric: `TranslationPipeline/CacheSize`
- Statistic: Average
- Period: 5 minutes
- Target: <10,000 entries
- Description: Current number of cached translation entries

**Cache Evictions**
- Metric: `TranslationPipeline/CacheEvictions`
- Statistic: Sum
- Period: 5 minutes
- Target: Minimal
- Description: Number of LRU cache evictions

#### 2. Translation & Synthesis (Row 2)

**Languages Processed**
- Metrics: 
  - `TranslationPipeline/LanguagesProcessed` (Processed)
  - `TranslationPipeline/FailedLanguagesCount` (Failed)
- Statistic: Sum
- Period: 5 minutes
- Target: Failed < 10% of processed
- Description: Number of languages successfully processed vs failed

**Processing Duration**
- Metric: `TranslationPipeline/ProcessingDuration`
- Statistics: Average, P99
- Period: 5 minutes
- Target: Avg <2500ms, P99 <5000ms
- Description: End-to-end processing time from transcript to broadcast

#### 3. Broadcast Performance (Row 3)

**Broadcast Success Rate**
- Metric: `TranslationPipeline/BroadcastSuccessRate`
- Statistic: Average
- Period: 5 minutes
- Target: >95%
- Description: Percentage of successful broadcasts to listeners

**Buffer Overflow Rate**
- Metric: `TranslationPipeline/BufferOverflowRate`
- Statistic: Average
- Period: 5 minutes
- Target: <5%
- Description: Percentage of buffer overflows (audio dropped)

#### 4. Listener Metrics (Row 4)

**Active Listeners**
- Metric: `TranslationPipeline/ListenerCount`
- Statistic: Average
- Period: 5 minutes
- Description: Number of active listeners across all sessions

#### 5. Lambda Performance (Row 5)

**Lambda Invocations**
- Metrics:
  - Invocations (count)
  - Errors (count)
- Statistic: Sum
- Period: 5 minutes
- Target: Error rate <1%
- Description: Lambda function invocations and errors

**Lambda Duration**
- Metric: Lambda Duration
- Statistics: Average, P99
- Period: 5 minutes
- Target: Avg <3000ms, P99 <10000ms
- Description: Lambda execution time

**Lambda Throttles**
- Metric: Lambda Throttles
- Statistic: Sum
- Period: 5 minutes
- Target: 0
- Description: Number of throttled Lambda invocations

#### 6. DynamoDB Performance (Row 6)

**DynamoDB Read Capacity**
- Metrics:
  - Sessions table
  - Connections table
  - CachedTranslations table
- Statistic: Sum
- Period: 5 minutes
- Description: Consumed read capacity units per table

**DynamoDB Write Capacity**
- Metrics:
  - Sessions table
  - Connections table
  - CachedTranslations table
- Statistic: Sum
- Period: 5 minutes
- Description: Consumed write capacity units per table

## CloudWatch Alarms

### 1. Cache Hit Rate Low

**Alarm Name**: `translation-cache-hit-rate-low-{env}`

**Condition**: Cache hit rate < 30% for 2 consecutive 5-minute periods

**Severity**: Warning

**Impact**: Increased AWS Translate costs and latency

**Troubleshooting**:
1. Check if cache is being populated correctly
2. Verify TTL is not too short (should be 3600 seconds)
3. Check if text normalization is working properly
4. Review cache eviction rate - may need to increase max entries
5. Analyze if users are speaking unique phrases (low hit rate expected)

**Resolution**:
- If cache is full and evicting frequently, increase `MAX_CACHE_ENTRIES`
- If TTL is expiring too quickly, increase `CACHE_TTL_SECONDS`
- If normalization is broken, fix text preprocessing logic

### 2. Broadcast Success Rate Low

**Alarm Name**: `broadcast-success-rate-low-{env}`

**Condition**: Broadcast success rate < 95% for 2 consecutive 5-minute periods

**Severity**: High

**Impact**: Listeners not receiving audio

**Troubleshooting**:
1. Check API Gateway connection status
2. Review stale connection cleanup logs
3. Check for API Gateway throttling
4. Verify WebSocket endpoint configuration
5. Check network connectivity issues

**Resolution**:
- If stale connections, ensure cleanup is working properly
- If throttling, reduce `MAX_CONCURRENT_BROADCASTS` or request limit increase
- If endpoint issues, verify API Gateway configuration
- If network issues, investigate infrastructure

### 3. Buffer Overflow Rate High

**Alarm Name**: `buffer-overflow-rate-high-{env}`

**Condition**: Buffer overflow rate > 5% for 2 consecutive 5-minute periods

**Severity**: Medium

**Impact**: Audio packets being dropped, degraded listener experience

**Troubleshooting**:
1. Check broadcast latency metrics
2. Review listener connection quality
3. Check if processing is taking too long
4. Verify concurrent broadcast limits
5. Check API Gateway performance

**Resolution**:
- If latency is high, optimize processing pipeline
- If connections are slow, may need to drop slow listeners
- If processing is slow, increase Lambda memory or optimize code
- If API Gateway is slow, investigate infrastructure

### 4. Failed Languages High

**Alarm Name**: `failed-languages-high-{env}`

**Condition**: Failed languages count > 10 for 2 consecutive 5-minute periods

**Severity**: High

**Impact**: Some languages not being translated/synthesized

**Troubleshooting**:
1. Check CloudWatch logs for error messages
2. Verify AWS Translate service status
3. Verify AWS Polly service status
4. Check IAM permissions
5. Verify language codes are valid
6. Check for service quotas/limits

**Resolution**:
- If service issues, wait for AWS to resolve or contact support
- If permissions issues, update IAM role
- If invalid language codes, fix language selection logic
- If quota issues, request limit increase

## Metrics Reference

### Custom Metrics (TranslationPipeline Namespace)

| Metric Name | Unit | Description |
|-------------|------|-------------|
| `CacheHitRate` | Percent | Translation cache hit rate |
| `CacheSize` | Count | Current cache entry count |
| `CacheEvictions` | Count | Number of LRU evictions |
| `BroadcastSuccessRate` | Percent | Broadcast success rate |
| `BufferOverflowRate` | Percent | Buffer overflow rate |
| `ProcessingDuration` | Milliseconds | End-to-end processing time |
| `LanguagesProcessed` | Count | Languages successfully processed |
| `FailedLanguagesCount` | Count | Languages that failed |
| `ListenerCount` | Count | Active listener count |

### Lambda Metrics (AWS/Lambda Namespace)

| Metric Name | Unit | Description |
|-------------|------|-------------|
| `Invocations` | Count | Function invocations |
| `Errors` | Count | Function errors |
| `Duration` | Milliseconds | Execution duration |
| `Throttles` | Count | Throttled invocations |
| `ConcurrentExecutions` | Count | Concurrent executions |

### DynamoDB Metrics (AWS/DynamoDB Namespace)

| Metric Name | Unit | Description |
|-------------|------|-------------|
| `ConsumedReadCapacityUnits` | Count | Read capacity consumed |
| `ConsumedWriteCapacityUnits` | Count | Write capacity consumed |
| `UserErrors` | Count | Client-side errors |
| `SystemErrors` | Count | Server-side errors |
| `ThrottledRequests` | Count | Throttled requests |

## Accessing Monitoring

### CloudWatch Console

1. Navigate to CloudWatch in AWS Console
2. Select "Dashboards" from left menu
3. Click on `TranslationPipeline-{env}`
4. View real-time metrics and graphs

### CloudWatch Alarms

1. Navigate to CloudWatch in AWS Console
2. Select "Alarms" from left menu
3. Filter by `translation-` prefix
4. View alarm status and history

### CloudWatch Logs

1. Navigate to CloudWatch in AWS Console
2. Select "Log groups" from left menu
3. Click on `/aws/lambda/translation-processor-{env}`
4. View function logs and errors

### CloudWatch Insights Queries

**Find Errors**:
```
fields @timestamp, @message, level, error_code
| filter level = "ERROR"
| sort @timestamp desc
| limit 100
```

**Track Session Processing**:
```
fields @timestamp, operation, session_id, message
| filter session_id = "golden-eagle-427"
| sort @timestamp asc
```

**Measure Latency**:
```
fields @timestamp, operation, duration_ms
| stats avg(duration_ms), max(duration_ms), p99(duration_ms) by operation
```

**Cache Performance**:
```
fields @timestamp, cache_hit, cache_miss
| stats sum(cache_hit) as hits, sum(cache_miss) as misses
| extend hit_rate = hits / (hits + misses) * 100
```

## Performance Targets

### Latency Targets

| Metric | Target | Maximum | Current |
|--------|--------|---------|---------|
| End-to-end processing | 2-4s | 5s | ~2.2s |
| Cache lookup | 10ms | 20ms | ~8ms |
| Translation (3 langs) | 200ms | 500ms | ~180ms |
| Synthesis (3 langs) | 400ms | 800ms | ~380ms |
| Broadcast (100 listeners) | 1500ms | 2000ms | ~1400ms |

### Success Rate Targets

| Metric | Target | Minimum |
|--------|--------|---------|
| Broadcast success rate | >98% | 95% |
| Translation success rate | >99% | 95% |
| Synthesis success rate | >99% | 95% |
| Cache hit rate | >50% | 30% |

### Cost Targets

| Metric | Target | Maximum |
|--------|--------|---------|
| Cost per listener-hour | <$0.05 | $0.10 |
| Cache hit rate | >50% | 30% |
| Lambda duration | <3s | 10s |

## Troubleshooting Procedures

### High Latency

**Symptoms**: Processing duration > 5 seconds

**Investigation**:
1. Check CloudWatch dashboard for bottlenecks
2. Review X-Ray traces (if enabled)
3. Check DynamoDB table performance
4. Check AWS Translate/Polly API latency
5. Check broadcast concurrency limits

**Resolution**:
- Optimize slow operations
- Increase Lambda memory if CPU-bound
- Increase concurrent broadcast limit if needed
- Check for AWS service issues

### Translation Failures

**Symptoms**: Failed languages count increasing

**Investigation**:
1. Check CloudWatch logs for error messages
2. Verify AWS Translate service status
3. Check IAM permissions
4. Verify language code validity
5. Check service quotas

**Resolution**:
- Fix IAM permissions if needed
- Validate language codes
- Request quota increase if needed
- Wait for AWS service recovery

### Broadcast Failures

**Symptoms**: Broadcast success rate < 95%

**Investigation**:
1. Check API Gateway connection status
2. Review stale connection cleanup
3. Check for throttling errors
4. Verify WebSocket endpoint
5. Check network connectivity

**Resolution**:
- Ensure stale connection cleanup working
- Reduce concurrent broadcasts if throttled
- Fix WebSocket endpoint configuration
- Investigate network issues

### Cache Issues

**Symptoms**: Cache hit rate < 30%

**Investigation**:
1. Check cache population logic
2. Verify TTL configuration
3. Check text normalization
4. Review eviction rate
5. Analyze phrase uniqueness

**Resolution**:
- Fix cache population if broken
- Increase TTL if too short
- Fix normalization if broken
- Increase max entries if evicting too much

## Alerting Configuration

### SNS Topic

**Topic Name**: `translation-pipeline-alarms-{env}`

**Subscriptions**:
- Email: Configured via `alarmEmail` in config
- Additional subscriptions can be added manually

### Email Notifications

Alarm emails include:
- Alarm name and description
- Current metric value
- Threshold value
- Timestamp
- Link to CloudWatch console

### Alarm Actions

All alarms trigger SNS notifications to the alarm topic. Additional actions can be configured:
- Lambda function invocation
- Auto Scaling actions
- Systems Manager actions

## Best Practices

1. **Monitor Regularly**: Check dashboard daily in production
2. **Set Up Alerts**: Configure email notifications for all alarms
3. **Review Logs**: Investigate errors and warnings promptly
4. **Track Trends**: Monitor metrics over time to identify patterns
5. **Optimize Costs**: Use cache hit rate to optimize translation costs
6. **Test Alarms**: Trigger test alarms to verify notification delivery
7. **Document Issues**: Keep runbook updated with common issues
8. **Capacity Planning**: Monitor DynamoDB capacity and Lambda concurrency

## Related Documentation

- [Lambda Function README](../lambda/translation_processor/README.md)
- [Translation Pipeline Design](../../.kiro/specs/translation-broadcasting-pipeline/design.md)
- [Translation Pipeline Requirements](../../.kiro/specs/translation-broadcasting-pipeline/requirements.md)
