# Rollback Runbook for Partial Results Feature

## Overview

This runbook provides step-by-step procedures for rolling back the partial results processing feature in case of issues. The system is designed with multiple fallback mechanisms to ensure quick recovery.

## Quick Reference

| Scenario | Severity | Action | Time to Effect |
|----------|----------|--------|----------------|
| High latency | Medium | Reduce rollout % | 60 seconds |
| High error rate | Critical | Disable feature | 60 seconds |
| Transcribe issues | Critical | Auto-fallback | Immediate |
| User complaints | Medium | Reduce rollout % | 60 seconds |
| Emergency | Critical | Environment variable | Immediate |

## Rollback Methods

### Method 1: Feature Flag (Recommended)

**Use When**: Standard rollback needed, non-emergency

**Advantages**:
- No redeployment required
- Takes effect within 60 seconds (cache TTL)
- Easily reversible
- Gradual rollback possible

**Procedure**:

```bash
# Option A: Disable completely
python scripts/manage_rollout.py --disable

# Option B: Roll back to previous percentage
python scripts/manage_rollout.py --percentage 50  # or 10, or 0

# Verify change
python scripts/manage_rollout.py --status
```

**Verification**:
```bash
# Check SSM parameter
aws ssm get-parameter --name /audio-transcription/partial-results/config

# Monitor logs for fallback
aws logs tail /aws/lambda/audio-processor --follow | grep "partial results"
```

### Method 2: Environment Variable

**Use When**: Feature flag not working, emergency situation

**Advantages**:
- Takes effect immediately for new Lambda invocations
- Bypasses SSM Parameter Store
- Works even if SSM unavailable

**Disadvantages**:
- Requires Lambda configuration update
- Affects all sessions immediately (no gradual rollback)

**Procedure**:

```bash
# Disable partial results via environment variable
aws lambda update-function-configuration \
  --function-name audio-processor \
  --environment Variables='{
    "PARTIAL_RESULTS_ENABLED":"false",
    "MIN_STABILITY_THRESHOLD":"0.85",
    "MAX_BUFFER_TIMEOUT":"5.0",
    "PAUSE_THRESHOLD":"2.0",
    "ORPHAN_TIMEOUT":"15.0",
    "MAX_RATE_PER_SECOND":"5",
    "DEDUP_CACHE_TTL":"10",
    "AWS_REGION":"us-east-1",
    "SESSIONS_TABLE_NAME":"Sessions",
    "LOG_LEVEL":"INFO",
    "STRUCTURED_LOGGING":"true",
    "FEATURE_FLAG_PARAMETER_NAME":"/audio-transcription/partial-results/config",
    "FEATURE_FLAG_CACHE_TTL":"60",
    "ROLLOUT_PERCENTAGE":"0"
  }'

# Verify change
aws lambda get-function-configuration \
  --function-name audio-processor \
  --query 'Environment.Variables.PARTIAL_RESULTS_ENABLED'
```

**Verification**:
```bash
# Invoke Lambda with test event
aws lambda invoke \
  --function-name audio-processor \
  --payload '{"test": true}' \
  response.json

# Check logs
aws logs tail /aws/lambda/audio-processor --follow
```

### Method 3: Code Deployment

**Use When**: Both feature flag and environment variable methods fail

**Advantages**:
- Complete control over behavior
- Can include bug fixes

**Disadvantages**:
- Slowest method (requires deployment)
- Requires code changes
- Higher risk

**Procedure**:

```bash
# 1. Update code to disable partial results
# Edit shared/services/partial_result_processor.py
# Set PARTIAL_RESULTS_ENABLED = False at module level

# 2. Run tests
cd audio-transcription
make test

# 3. Deploy
make deploy-prod

# 4. Verify deployment
aws lambda get-function --function-name audio-processor
```

## Fallback Behavior

### Automatic Fallback Scenarios

The system automatically falls back to final-result-only mode in these cases:

#### 1. Transcribe Service Unhealthy

**Trigger**: No results received for 10+ seconds during active audio

**Behavior**:
- System detects lack of results
- Automatically disables partial processing
- Emits CloudWatch metric: `TranscribeFallbackTriggered`
- Logs warning message
- Re-enables when results resume

**No Action Required**: System handles automatically

**Monitoring**:
```bash
# Check for fallback events
aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor \
  --filter-pattern "Transcribe service appears unhealthy" \
  --start-time $(date -u -d '1 hour ago' +%s)000
```

#### 2. Stability Scores Unavailable

**Trigger**: Transcribe doesn't provide stability scores for language

**Behavior**:
- System uses 3-second timeout fallback
- Buffers partial results for 3 seconds
- Forwards after timeout
- Logs warning once per session

**No Action Required**: System handles automatically

**Monitoring**:
```bash
# Check for missing stability scores
aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor \
  --filter-pattern "stability scores unavailable" \
  --start-time $(date -u -d '1 hour ago' +%s)000
```

#### 3. SSM Parameter Unavailable

**Trigger**: Cannot fetch feature flag from Parameter Store

**Behavior**:
- System uses environment variable defaults
- Logs warning
- Continues processing

**Action**: Investigate SSM issue, but system continues working

**Monitoring**:
```bash
# Check for SSM errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor \
  --filter-pattern "Error fetching parameter from SSM" \
  --start-time $(date -u -d '1 hour ago' +%s)000
```

## Rollback Scenarios

### Scenario 1: High End-to-End Latency

**Symptoms**:
- CloudWatch alarm: `audio-transcription-latency-high`
- End-to-end latency p95 > 5 seconds
- User complaints about delays

**Diagnosis**:
```bash
# Check latency metrics
aws cloudwatch get-metric-statistics \
  --namespace AudioTranscription/PartialResults \
  --metric-name PartialResultProcessingLatency \
  --dimensions Name=SessionId,Value=* \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum \
  --extended-statistics p95,p99

# Check Lambda duration
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=audio-processor \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum
```

**Rollback Steps**:

1. **Immediate Action** (if p95 > 7 seconds):
   ```bash
   # Disable feature completely
   python scripts/manage_rollout.py --disable
   ```

2. **Gradual Rollback** (if p95 between 5-7 seconds):
   ```bash
   # Reduce rollout percentage
   python scripts/manage_rollout.py --percentage 50  # or 10
   ```

3. **Verify Improvement**:
   ```bash
   # Wait 5 minutes, then check metrics again
   sleep 300
   
   # Check if latency improved
   aws cloudwatch get-metric-statistics \
     --namespace AudioTranscription/PartialResults \
     --metric-name PartialResultProcessingLatency \
     --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 60 \
     --statistics p95
   ```

4. **Root Cause Analysis**:
   - Check Lambda memory usage (may need increase to 768 MB)
   - Check buffer overflow events
   - Check orphan cleanup frequency
   - Check Transcribe API latency

### Scenario 2: High Error Rate

**Symptoms**:
- CloudWatch alarm: `audio-transcription-lambda-errors`
- Lambda errors > 5 in 5 minutes
- Error logs in CloudWatch

**Diagnosis**:
```bash
# Check error count
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=audio-processor \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum

# Check error logs
aws logs tail /aws/lambda/audio-processor --follow | grep ERROR

# Get specific error messages
aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor \
  --filter-pattern "ERROR" \
  --start-time $(date -u -d '1 hour ago' +%s)000 \
  --limit 50
```

**Rollback Steps**:

1. **Immediate Action**:
   ```bash
   # Disable feature immediately
   python scripts/manage_rollout.py --disable
   ```

2. **Verify Error Rate Drops**:
   ```bash
   # Wait 2 minutes, check error rate
   sleep 120
   
   aws cloudwatch get-metric-statistics \
     --namespace AWS/Lambda \
     --metric-name Errors \
     --dimensions Name=FunctionName,Value=audio-processor \
     --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 60 \
     --statistics Sum
   ```

3. **Investigate Root Cause**:
   - Analyze error stack traces
   - Check for code bugs
   - Check for AWS service issues (Transcribe, DynamoDB)
   - Check for configuration errors

4. **Fix and Re-deploy**:
   ```bash
   # After fixing issue
   cd audio-transcription
   make test
   make deploy-prod
   
   # Test in dev first
   make deploy-dev
   # Verify fix works
   
   # Re-enable with 10% canary
   python scripts/manage_rollout.py --percentage 10
   ```

### Scenario 3: Excessive Partial Results Dropped

**Symptoms**:
- CloudWatch alarm: `audio-transcription-rate-limit-high`
- Partial results dropped > 100/minute
- Rate limiting too aggressive

**Diagnosis**:
```bash
# Check dropped results metric
aws cloudwatch get-metric-statistics \
  --namespace AudioTranscription/PartialResults \
  --metric-name PartialResultsDropped \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum

# Check rate limiting logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor \
  --filter-pattern "Rate limit" \
  --start-time $(date -u -d '1 hour ago' +%s)000
```

**Rollback Steps**:

1. **Assess Impact**:
   - If latency still acceptable: No rollback needed, just tune
   - If latency degraded: Roll back

2. **Tune Configuration** (if no rollback needed):
   ```bash
   # Increase rate limit via environment variable
   aws lambda update-function-configuration \
     --function-name audio-processor \
     --environment Variables='{
       "MAX_RATE_PER_SECOND":"10",
       ...other variables...
     }'
   ```

3. **Rollback** (if latency degraded):
   ```bash
   # Reduce rollout percentage
   python scripts/manage_rollout.py --percentage 50
   ```

### Scenario 4: High Orphaned Results

**Symptoms**:
- CloudWatch alarm: `audio-transcription-orphaned-results-high`
- Orphaned results > 10 per session
- Transcribe not sending final results

**Diagnosis**:
```bash
# Check orphaned results metric
aws cloudwatch get-metric-statistics \
  --namespace AudioTranscription/PartialResults \
  --metric-name OrphanedResultsFlushed \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum

# Check orphan cleanup logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor \
  --filter-pattern "Flushing orphaned result" \
  --start-time $(date -u -d '1 hour ago' +%s)000
```

**Rollback Steps**:

1. **Check Transcribe Health**:
   ```bash
   # Check for Transcribe fallback events
   aws logs filter-log-events \
     --log-group-name /aws/lambda/audio-processor \
     --filter-pattern "Transcribe service appears unhealthy" \
     --start-time $(date -u -d '1 hour ago' +%s)000
   ```

2. **If Transcribe Issue**:
   - System should auto-fallback
   - Monitor for recovery
   - If persistent, disable feature:
     ```bash
     python scripts/manage_rollout.py --disable
     ```
   - Contact AWS Support

3. **If Not Transcribe Issue**:
   - May be normal behavior for certain speech patterns
   - Monitor user feedback
   - If complaints, reduce rollout:
     ```bash
     python scripts/manage_rollout.py --percentage 50
     ```

### Scenario 5: User Complaints About Quality

**Symptoms**:
- Users report poor translation quality
- Users report unnatural audio
- Specific session IDs provided

**Diagnosis**:
```bash
# Get logs for specific session
SESSION_ID="golden-eagle-427"

aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor \
  --filter-pattern "$SESSION_ID" \
  --start-time $(date -u -d '2 hours ago' +%s)000

# Check discrepancy logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor \
  --filter-pattern "discrepancy" \
  --start-time $(date -u -d '1 hour ago' +%s)000

# Check duplicate detection
aws cloudwatch get-metric-statistics \
  --namespace AudioTranscription/PartialResults \
  --metric-name DuplicatesDetected \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

**Rollback Steps**:

1. **If Isolated Issue**:
   - Investigate specific session
   - May be language-specific issue
   - No rollback needed

2. **If Widespread Issue**:
   ```bash
   # Reduce rollout to 10%
   python scripts/manage_rollout.py --percentage 10
   
   # Or increase stability threshold
   aws ssm put-parameter \
     --name /audio-transcription/partial-results/config \
     --value '{"enabled":true,"rollout_percentage":100,"min_stability_threshold":0.90,"max_buffer_timeout":5.0}' \
     --overwrite
   ```

3. **Monitor Improvement**:
   - Gather user feedback
   - Check discrepancy logs
   - If improved, maintain; if not, disable:
     ```bash
     python scripts/manage_rollout.py --disable
     ```

## Post-Rollback Actions

### 1. Verify Rollback Successful

```bash
# Check feature flag status
python scripts/manage_rollout.py --status

# Check Lambda configuration
aws lambda get-function-configuration \
  --function-name audio-processor \
  --query 'Environment.Variables'

# Monitor metrics for 15 minutes
# Verify latency returned to baseline
# Verify error rate returned to baseline
```

### 2. Notify Stakeholders

```bash
# Post to Slack
# Template:
# "🔄 Partial results feature rolled back
#  Reason: [High latency / High errors / User complaints]
#  Action: [Disabled / Reduced to X%]
#  Status: [Monitoring / Investigating]
#  ETA: [When will be re-enabled]"
```

### 3. Root Cause Analysis

- Gather all relevant logs and metrics
- Identify root cause
- Document findings
- Create action items for fixes

### 4. Create Incident Report

```markdown
# Incident Report: Partial Results Rollback

## Summary
- Date: YYYY-MM-DD
- Duration: X hours
- Impact: [Description]
- Root Cause: [Description]

## Timeline
- HH:MM - Issue detected
- HH:MM - Rollback initiated
- HH:MM - Rollback completed
- HH:MM - Verified successful

## Root Cause
[Detailed explanation]

## Resolution
[What was done to fix]

## Action Items
- [ ] Fix root cause
- [ ] Add monitoring for early detection
- [ ] Update runbook
- [ ] Test fix in dev
- [ ] Plan re-rollout
```

### 5. Plan Re-Rollout

After fixing issue:

1. **Test in Dev**:
   ```bash
   make deploy-dev
   # Test thoroughly
   ```

2. **Start with 10% Canary**:
   ```bash
   python scripts/manage_rollout.py --percentage 10
   ```

3. **Monitor Closely**:
   - Check metrics every hour for first day
   - Gather user feedback
   - Verify issue resolved

4. **Gradual Re-Rollout**:
   - If successful after 1 week: 50%
   - If successful after 2 weeks: 100%

## Emergency Contacts

- **On-Call Engineer**: [Pager link]
- **Team Lead**: [Contact info]
- **AWS Support**: [Support case link]
- **Slack Channel**: #llt-incidents

## Testing Rollback Procedures

### Pre-Production Testing

Test rollback procedures in dev environment:

```bash
# 1. Deploy to dev
make deploy-dev

# 2. Enable feature
python scripts/manage_rollout.py --percentage 100 \
  --parameter-name /audio-transcription/dev/partial-results/config

# 3. Verify enabled
python scripts/manage_rollout.py --status \
  --parameter-name /audio-transcription/dev/partial-results/config

# 4. Test rollback via feature flag
python scripts/manage_rollout.py --disable \
  --parameter-name /audio-transcription/dev/partial-results/config

# 5. Verify disabled
python scripts/manage_rollout.py --status \
  --parameter-name /audio-transcription/dev/partial-results/config

# 6. Test rollback via environment variable
aws lambda update-function-configuration \
  --function-name audio-processor-dev \
  --environment Variables='{
    "PARTIAL_RESULTS_ENABLED":"false",
    ...
  }'

# 7. Verify disabled
aws lambda get-function-configuration \
  --function-name audio-processor-dev \
  --query 'Environment.Variables.PARTIAL_RESULTS_ENABLED'
```

## Appendix

### Rollback Decision Matrix

| Metric | Threshold | Action |
|--------|-----------|--------|
| Latency p95 | > 7s | Disable immediately |
| Latency p95 | 5-7s | Reduce to 50% |
| Error rate | > 5% | Disable immediately |
| Error rate | 2-5% | Reduce to 50% |
| Dropped results | > 200/min | Reduce to 50% |
| Orphaned results | > 20/session | Investigate, consider disable |
| User complaints | > 5/hour | Reduce to 10% |

### Useful Commands

```bash
# Quick status check
python scripts/manage_rollout.py --status

# Quick disable
python scripts/manage_rollout.py --disable

# Check recent errors
aws logs tail /aws/lambda/audio-processor --follow | grep ERROR

# Check recent alarms
aws cloudwatch describe-alarms \
  --alarm-names audio-transcription-latency-high \
               audio-transcription-lambda-errors \
               audio-transcription-rate-limit-high \
               audio-transcription-orphaned-results-high \
               audio-transcription-transcribe-fallback

# Get alarm history
aws cloudwatch describe-alarm-history \
  --alarm-name audio-transcription-latency-high \
  --start-date $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --max-records 10
```
