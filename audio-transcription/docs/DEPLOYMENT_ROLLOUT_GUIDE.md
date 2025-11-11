# Deployment and Rollout Guide

## Overview

This guide describes the deployment and gradual rollout strategy for the partial results processing feature. The rollout uses a canary deployment approach with percentage-based feature flags to minimize risk and enable quick rollback if issues are detected.

## Rollout Strategy

### Phase 1: Canary Deployment (10% of sessions)
- **Duration**: 1 week
- **Rollout**: 10% of new sessions
- **Monitoring**: Intensive monitoring of latency, accuracy, and error rates
- **Success Criteria**: 
  - End-to-end latency p95 < 5 seconds
  - No increase in error rate
  - No critical alarms triggered
  - Positive user feedback

### Phase 2: Gradual Rollout (50% of sessions)
- **Duration**: 1 week
- **Rollout**: 50% of new sessions
- **Monitoring**: Continue monitoring key metrics
- **Success Criteria**:
  - Metrics remain stable compared to Phase 1
  - Cost per listener-hour < $0.10
  - Translation cache hit rate > 30%

### Phase 3: Full Rollout (100% of sessions)
- **Duration**: Ongoing
- **Rollout**: 100% of new sessions
- **Monitoring**: Standard production monitoring
- **Success Criteria**:
  - All metrics within acceptable ranges
  - No degradation in user experience

## Feature Flag Management

### Architecture

The feature flag system uses AWS Systems Manager Parameter Store for dynamic configuration without redeployment. The system implements:

1. **Global Enable/Disable**: Emergency kill switch for the entire feature
2. **Percentage-Based Rollout**: Gradual rollout using consistent hashing
3. **Configuration Parameters**: Dynamic tuning of stability thresholds and timeouts
4. **Caching**: 60-second cache TTL to reduce SSM API calls

### SSM Parameter Structure

```json
{
  "enabled": true,
  "rollout_percentage": 100,
  "min_stability_threshold": 0.85,
  "max_buffer_timeout": 5.0
}
```

**Fields**:
- `enabled` (boolean): Global enable/disable flag
- `rollout_percentage` (0-100): Percentage of sessions to enable partial results
- `min_stability_threshold` (0.70-0.95): Minimum stability score to forward partial results
- `max_buffer_timeout` (2.0-10.0): Maximum time to buffer results before forwarding

### Consistent Hashing

The system uses SHA-256 hashing of session IDs to ensure:
- Same session always gets same result during rollout
- Uniform distribution across 0-99 buckets
- No session flipping between enabled/disabled states

## Deployment Commands

### Prerequisites

```bash
# Install AWS CLI
pip install awscli boto3

# Configure AWS credentials
aws configure

# Verify access to SSM Parameter Store
aws ssm get-parameter --name /audio-transcription/partial-results/config
```

### Initial Deployment

```bash
# 1. Deploy infrastructure with feature flag parameter
cd audio-transcription/infrastructure
cdk deploy --context env=dev

# 2. Verify parameter created
aws ssm get-parameter --name /audio-transcription/partial-results/config

# 3. Start with 0% rollout (disabled)
python ../scripts/manage_rollout.py --percentage 0
```

### Phase 1: Canary Deployment (10%)

```bash
# Enable for 10% of sessions
python scripts/manage_rollout.py --percentage 10

# Verify status
python scripts/manage_rollout.py --status

# Monitor metrics for 1 week
# Check CloudWatch dashboard: audio-transcription-partial-results
```

### Phase 2: Gradual Rollout (50%)

```bash
# After successful Phase 1, increase to 50%
python scripts/manage_rollout.py --percentage 50

# Continue monitoring for 1 week
```

### Phase 3: Full Rollout (100%)

```bash
# After successful Phase 2, enable for all sessions
python scripts/manage_rollout.py --percentage 100

# Verify full rollout
python scripts/manage_rollout.py --status
```

### Emergency Rollback

```bash
# Option 1: Disable feature entirely (fastest)
python scripts/manage_rollout.py --disable

# Option 2: Roll back to previous percentage
python scripts/manage_rollout.py --percentage 50  # or 10, or 0

# Option 3: Environment variable override (requires Lambda update)
# Update Lambda environment variable: PARTIAL_RESULTS_ENABLED=false
aws lambda update-function-configuration \
  --function-name audio-processor \
  --environment Variables={PARTIAL_RESULTS_ENABLED=false}
```

## Monitoring During Rollout

### Key Metrics to Monitor

1. **End-to-End Latency**
   - Metric: `AudioTranscription/PartialResults/PartialResultProcessingLatency`
   - Target: p95 < 5 seconds
   - Alarm: p95 > 5 seconds for 2 consecutive periods

2. **Partial Results Dropped**
   - Metric: `AudioTranscription/PartialResults/PartialResultsDropped`
   - Target: < 100 per minute
   - Alarm: > 100 per minute for 2 consecutive periods

3. **Orphaned Results**
   - Metric: `AudioTranscription/PartialResults/OrphanedResultsFlushed`
   - Target: < 10 per session
   - Alarm: > 10 per session for 2 consecutive periods

4. **Transcribe Fallback**
   - Metric: `AudioTranscription/PartialResults/TranscribeFallbackTriggered`
   - Target: 0
   - Alarm: ≥ 1 occurrence

5. **Lambda Errors**
   - Metric: `AWS/Lambda/Errors`
   - Target: < 1% error rate
   - Alarm: > 5 errors in 5 minutes

### CloudWatch Dashboard

Access the dashboard at:
```
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=audio-transcription-partial-results
```

### CloudWatch Insights Queries

**Find errors in last hour**:
```
fields @timestamp, @message, level, error_code
| filter level = "ERROR"
| sort @timestamp desc
| limit 100
```

**Track partial result processing**:
```
fields @timestamp, event, action, stability_score, session_id
| filter event = "partial_result"
| stats count() by action
```

**Measure latency by session**:
```
fields @timestamp, session_id, processing_latency_ms
| stats avg(processing_latency_ms), max(processing_latency_ms), p99(processing_latency_ms) by session_id
```

## Rollback Procedures

### Scenario 1: High Latency Detected

**Symptoms**: End-to-end latency p95 > 5 seconds

**Actions**:
1. Check CloudWatch alarm: `audio-transcription-latency-high`
2. Verify metric in dashboard
3. Roll back to previous percentage or disable:
   ```bash
   python scripts/manage_rollout.py --percentage 50  # or --disable
   ```
4. Investigate root cause:
   - Check Lambda memory usage
   - Check buffer overflow events
   - Check Transcribe service health
5. Fix issue and re-deploy
6. Resume rollout after verification

### Scenario 2: High Error Rate

**Symptoms**: Lambda errors > 5 in 5 minutes

**Actions**:
1. Check CloudWatch alarm: `audio-transcription-lambda-errors`
2. View error logs in CloudWatch Logs
3. Disable feature immediately:
   ```bash
   python scripts/manage_rollout.py --disable
   ```
4. Investigate error cause:
   - Check Lambda logs for stack traces
   - Check Transcribe API errors
   - Check DynamoDB throttling
5. Fix issue and deploy hotfix
6. Test in dev environment
7. Resume rollout with 10% canary

### Scenario 3: Transcribe Service Issues

**Symptoms**: Transcribe fallback alarm triggered

**Actions**:
1. Check CloudWatch alarm: `audio-transcription-transcribe-fallback`
2. Verify Transcribe service health
3. System automatically falls back to final-only mode
4. Monitor for recovery
5. If persistent, disable feature:
   ```bash
   python scripts/manage_rollout.py --disable
   ```
6. Contact AWS Support if Transcribe issue persists

### Scenario 4: User Complaints

**Symptoms**: Users report poor translation quality or audio issues

**Actions**:
1. Gather specific session IDs from users
2. Check logs for those sessions:
   ```
   fields @timestamp, @message
   | filter session_id = "golden-eagle-427"
   | sort @timestamp asc
   ```
3. Compare partial vs final result accuracy
4. If widespread issue, roll back:
   ```bash
   python scripts/manage_rollout.py --percentage 10  # or --disable
   ```
5. Investigate discrepancy logs
6. Adjust stability threshold if needed:
   ```bash
   # Update SSM parameter manually
   aws ssm put-parameter \
     --name /audio-transcription/partial-results/config \
     --value '{"enabled":true,"rollout_percentage":10,"min_stability_threshold":0.90,"max_buffer_timeout":5.0}' \
     --overwrite
   ```

## Fallback Behavior

### Automatic Fallback

The system automatically falls back to final-result-only mode in these scenarios:

1. **SSM Parameter Unavailable**: Uses environment variable defaults
2. **Transcribe Stability Scores Missing**: Uses 3-second timeout fallback
3. **Transcribe Service Unhealthy**: Disables partial processing after 10 seconds without results
4. **Feature Flag Disabled**: Processes only final results

### Manual Fallback

Operators can manually trigger fallback:

1. **Via Feature Flag** (recommended):
   ```bash
   python scripts/manage_rollout.py --disable
   ```
   - Takes effect within 60 seconds (cache TTL)
   - No redeployment required
   - Reversible

2. **Via Environment Variable**:
   ```bash
   aws lambda update-function-configuration \
     --function-name audio-processor \
     --environment Variables={PARTIAL_RESULTS_ENABLED=false}
   ```
   - Takes effect immediately for new invocations
   - Requires Lambda update
   - Reversible

3. **Via Code Deployment**:
   - Update code to disable partial processing
   - Deploy new Lambda version
   - Slowest option, use only if other methods fail

## Testing Rollout

### Pre-Rollout Testing

Before starting Phase 1, verify:

```bash
# 1. Run all tests
cd audio-transcription
make test

# 2. Deploy to dev environment
make deploy-dev

# 3. Test with 0% rollout (disabled)
python scripts/manage_rollout.py --percentage 0 --parameter-name /audio-transcription/dev/partial-results/config

# 4. Create test session and verify final-only mode
# (Use dev environment session creation API)

# 5. Enable for 100% in dev
python scripts/manage_rollout.py --percentage 100 --parameter-name /audio-transcription/dev/partial-results/config

# 6. Create test session and verify partial results enabled
# (Check logs for "partial_result" events)

# 7. Test rollback
python scripts/manage_rollout.py --disable --parameter-name /audio-transcription/dev/partial-results/config
```

### Canary Testing

During Phase 1 (10% rollout):

```bash
# Create 10 test sessions
for i in {1..10}; do
  # Create session via API
  # Check logs to see if partial results enabled
  # Approximately 1 out of 10 should have partial results
done

# Verify consistent hashing (same session ID always gets same result)
# Create same session ID multiple times
# Should always be enabled or always disabled
```

## Configuration Tuning

### Adjusting Stability Threshold

If translation quality issues detected:

```bash
# Increase stability threshold (more conservative)
aws ssm put-parameter \
  --name /audio-transcription/partial-results/config \
  --value '{"enabled":true,"rollout_percentage":100,"min_stability_threshold":0.90,"max_buffer_timeout":5.0}' \
  --overwrite

# Verify change
python scripts/manage_rollout.py --status
```

### Adjusting Buffer Timeout

If latency too high:

```bash
# Decrease buffer timeout (faster forwarding)
aws ssm put-parameter \
  --name /audio-transcription/partial-results/config \
  --value '{"enabled":true,"rollout_percentage":100,"min_stability_threshold":0.85,"max_buffer_timeout":3.0}' \
  --overwrite
```

## Success Criteria

### Phase 1 Success Criteria

- [ ] End-to-end latency p95 < 5 seconds
- [ ] No increase in Lambda error rate
- [ ] No critical alarms triggered
- [ ] Partial results dropped < 100/minute
- [ ] Orphaned results < 10/session
- [ ] No Transcribe fallback events
- [ ] User feedback positive or neutral

### Phase 2 Success Criteria

- [ ] All Phase 1 criteria maintained
- [ ] Cost per listener-hour < $0.10
- [ ] Translation cache hit rate > 30%
- [ ] No degradation in translation quality
- [ ] System stable for 1 week

### Phase 3 Success Criteria

- [ ] All Phase 2 criteria maintained
- [ ] Full rollout stable for 2 weeks
- [ ] No rollback events
- [ ] User satisfaction maintained or improved

## Communication Plan

### Stakeholder Updates

**Before Rollout**:
- Notify team of rollout schedule
- Share monitoring dashboard links
- Establish on-call rotation

**During Rollout**:
- Daily status updates during Phase 1
- Weekly updates during Phase 2 and 3
- Immediate notification of any issues

**After Rollout**:
- Final report with metrics
- Lessons learned document
- Update runbooks

### User Communication

**Before Rollout**:
- No user communication needed (transparent change)

**During Rollout**:
- Monitor user feedback channels
- Respond to quality concerns promptly

**After Rollout**:
- Announce improved latency in release notes
- Update documentation with new latency targets

## Troubleshooting

### Issue: Feature flag not taking effect

**Symptoms**: Changes to SSM parameter not reflected in Lambda behavior

**Diagnosis**:
```bash
# Check parameter value
aws ssm get-parameter --name /audio-transcription/partial-results/config

# Check Lambda environment variables
aws lambda get-function-configuration --function-name audio-processor

# Check Lambda logs for feature flag loading
aws logs tail /aws/lambda/audio-processor --follow
```

**Solution**:
- Wait 60 seconds for cache to expire
- Or invalidate cache by restarting Lambda (invoke with test event)

### Issue: Inconsistent rollout percentage

**Symptoms**: More or fewer sessions enabled than expected percentage

**Diagnosis**:
```bash
# Check session distribution
# Query CloudWatch Logs for "rollout check" messages
aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor \
  --filter-pattern "rollout check" \
  --start-time $(date -u -d '1 hour ago' +%s)000
```

**Solution**:
- Verify consistent hashing implementation
- Check for session ID format changes
- Ensure parameter value is correct

### Issue: High memory usage

**Symptoms**: Lambda memory usage approaching limit

**Diagnosis**:
```bash
# Check Lambda memory metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name MemoryUtilization \
  --dimensions Name=FunctionName,Value=audio-processor \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Maximum
```

**Solution**:
- Increase Lambda memory to 768 MB
- Check for memory leaks in buffer or cache
- Verify orphan cleanup running correctly

## Appendix

### SSM Parameter Naming Convention

- **Dev**: `/audio-transcription/dev/partial-results/config`
- **Staging**: `/audio-transcription/staging/partial-results/config`
- **Production**: `/audio-transcription/partial-results/config`

### Rollout Timeline

| Week | Phase | Percentage | Actions |
|------|-------|------------|---------|
| 1 | Pre-rollout | 0% | Deploy infrastructure, test in dev |
| 2 | Phase 1 | 10% | Canary deployment, intensive monitoring |
| 3 | Phase 1 | 10% | Continue monitoring, gather feedback |
| 4 | Phase 2 | 50% | Gradual rollout, monitor metrics |
| 5 | Phase 2 | 50% | Continue monitoring, verify stability |
| 6 | Phase 3 | 100% | Full rollout |
| 7+ | Production | 100% | Standard monitoring |

### Contact Information

- **On-Call**: [On-call rotation link]
- **Slack Channel**: #llt-deployments
- **Incident Response**: [Runbook link]
- **AWS Support**: [Support case link]
