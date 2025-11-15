# WebSocket Audio Integration Deployment Checklist

## Overview

This checklist ensures all components are properly configured and deployed for the WebSocket Audio Integration system. Follow this checklist for deployments to dev, staging, and production environments.

## Pre-Deployment Checklist

### Code Quality

- [ ] All tests passing locally
  ```bash
  cd session-management && pytest tests/
  cd audio-transcription && pytest tests/
  ```

- [ ] Code coverage >80%
  ```bash
  pytest --cov=session-management --cov-report=html
  pytest --cov=audio-transcription --cov-report=html
  ```

- [ ] No linting errors
  ```bash
  pylint session-management/
  pylint audio-transcription/
  ```

- [ ] Code formatted with Black
  ```bash
  black session-management/
  black audio-transcription/
  ```

- [ ] Type checking passed
  ```bash
  mypy session-management/
  mypy audio-transcription/
  ```

### Documentation

- [ ] README.md updated with latest changes
- [ ] CHANGELOG.md updated with version notes
- [ ] API documentation updated
- [ ] Integration points documented
- [ ] Troubleshooting guide updated

### Security

- [ ] No secrets in code
- [ ] Environment variables documented
- [ ] IAM permissions reviewed
- [ ] Security validation tests passed
- [ ] Dependency vulnerabilities checked
  ```bash
  pip-audit
  ```

## CDK Stacks to Deploy

### 1. Shared Lambda Layer

**Stack**: `SharedLayerStack`

**Location**: `shared-layer/`

**Components**:
- Structured logger
- Metrics emitter
- Validators
- Error codes
- Table names

**Deployment Command**:
```bash
cd shared-layer
./build.sh
cdk deploy SharedLayerStack --profile <aws-profile>
```

**Verification**:
```bash
# Verify layer exists
aws lambda list-layers --region us-east-1
```

- [ ] Shared layer built successfully
- [ ] Shared layer deployed
- [ ] Layer ARN recorded: `_______________________`

### 2. Session Management Stack

**Stack**: `SessionManagementStack`

**Location**: `session-management/infrastructure/`

**Components**:
- DynamoDB tables (Sessions, Connections, RateLimits)
- Lambda functions (Authorizer, ConnectionHandler, SessionStatusHandler, TimeoutHandler)
- API Gateway WebSocket API
- EventBridge rules
- CloudWatch alarms

**Deployment Command**:
```bash
cd session-management/infrastructure
cdk synth SessionManagementStack
cdk deploy SessionManagementStack --profile <aws-profile>
```

**Verification**:
```bash
# Verify DynamoDB tables
aws dynamodb list-tables --region us-east-1

# Verify Lambda functions
aws lambda list-functions --region us-east-1 | grep -E "Authorizer|ConnectionHandler|SessionStatus|Timeout"

# Verify API Gateway
aws apigatewayv2 get-apis --region us-east-1
```

- [ ] CDK synth successful
- [ ] DynamoDB tables created
- [ ] Lambda functions deployed
- [ ] API Gateway WebSocket API created
- [ ] EventBridge rules created
- [ ] CloudWatch alarms enabled
- [ ] WebSocket API URL recorded: `_______________________`

### 3. Audio Transcription Stack

**Stack**: `AudioTranscriptionStack`

**Location**: `audio-transcription/infrastructure/`

**Components**:
- Lambda function (AudioProcessor)
- IAM roles and policies
- CloudWatch log groups
- CloudWatch metrics

**Deployment Command**:
```bash
cd audio-transcription/infrastructure
cdk synth AudioTranscriptionStack
cdk deploy AudioTranscriptionStack --profile <aws-profile>
```

**Verification**:
```bash
# Verify Lambda function
aws lambda get-function --function-name AudioProcessor --region us-east-1

# Verify IAM role
aws iam get-role --role-name AudioProcessorLambdaRole
```

- [ ] CDK synth successful
- [ ] AudioProcessor Lambda deployed
- [ ] IAM roles created
- [ ] CloudWatch log groups created
- [ ] Lambda function ARN recorded: `_______________________`

### 4. Translation Pipeline Stack

**Stack**: `TranslationPipelineStack`

**Location**: `translation-pipeline/infrastructure/`

**Components**:
- Lambda function (TranslationProcessor)
- IAM roles and policies
- CloudWatch log groups

**Deployment Command**:
```bash
cd translation-pipeline/infrastructure
cdk synth TranslationPipelineStack
cdk deploy TranslationPipelineStack --profile <aws-profile>
```

**Verification**:
```bash
# Verify Lambda function
aws lambda get-function --function-name TranslationProcessor --region us-east-1
```

- [ ] CDK synth successful
- [ ] TranslationProcessor Lambda deployed
- [ ] IAM roles created
- [ ] Lambda function ARN recorded: `_______________________`

## Environment Variables to Configure

### Session Management Lambda Functions

#### Authorizer Lambda

- [ ] `COGNITO_USER_POOL_ID`: `_______________________`
- [ ] `COGNITO_CLIENT_ID`: `_______________________`
- [ ] `AWS_REGION`: `us-east-1`

#### Connection Handler Lambda

- [ ] `SESSIONS_TABLE_NAME`: `Sessions`
- [ ] `CONNECTIONS_TABLE_NAME`: `Connections`
- [ ] `RATE_LIMITS_TABLE_NAME`: `RateLimits`
- [ ] `AWS_REGION`: `us-east-1`

#### Session Status Handler Lambda

- [ ] `SESSIONS_TABLE_NAME`: `Sessions`
- [ ] `CONNECTIONS_TABLE_NAME`: `Connections`
- [ ] `AWS_REGION`: `us-east-1`

#### Timeout Handler Lambda

- [ ] `CONNECTIONS_TABLE_NAME`: `Connections`
- [ ] `IDLE_TIMEOUT_SECONDS`: `600`
- [ ] `AWS_REGION`: `us-east-1`

### Audio Transcription Lambda Functions

#### Audio Processor Lambda

- [ ] `TRANSLATION_PIPELINE_FUNCTION_NAME`: `TranslationProcessor`
- [ ] `ENABLE_EMOTION_DETECTION`: `true`
- [ ] `EMOTION_CACHE_TTL_SECONDS`: `60`
- [ ] `MAX_AUDIO_CHUNKS_PER_SECOND`: `10`
- [ ] `AUDIO_BUFFER_MAX_SECONDS`: `5`
- [ ] `AWS_REGION`: `us-east-1`

### Translation Pipeline Lambda Functions

#### Translation Processor Lambda

- [ ] `SESSIONS_TABLE_NAME`: `Sessions`
- [ ] `CONNECTIONS_TABLE_NAME`: `Connections`
- [ ] `TRANSLATION_CACHE_TABLE_NAME`: `TranslationCache`
- [ ] `AWS_REGION`: `us-east-1`

## IAM Permissions to Verify

### Audio Processor Lambda Role

- [ ] `transcribe:StartStreamTranscription` on `*`
- [ ] `lambda:InvokeFunction` on `TranslationProcessor`
- [ ] `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` on `*`
- [ ] `cloudwatch:PutMetricData` on `*`

**Verification**:
```bash
aws iam get-role-policy \
  --role-name AudioProcessorLambdaRole \
  --policy-name AudioProcessorPolicy
```

### Translation Processor Lambda Role

- [ ] `translate:TranslateText` on `*`
- [ ] `polly:SynthesizeSpeech` on `*`
- [ ] `dynamodb:GetItem`, `dynamodb:PutItem` on `TranslationCache` table
- [ ] `dynamodb:Query` on `Connections` table
- [ ] `execute-api:ManageConnections` on WebSocket API
- [ ] `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` on `*`

**Verification**:
```bash
aws iam get-role-policy \
  --role-name TranslationProcessorLambdaRole \
  --policy-name TranslationProcessorPolicy
```

### Connection Handler Lambda Role

- [ ] `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:DeleteItem` on all tables
- [ ] `dynamodb:Query` on GSI indexes
- [ ] `execute-api:ManageConnections` on WebSocket API
- [ ] `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` on `*`

**Verification**:
```bash
aws iam get-role-policy \
  --role-name ConnectionHandlerLambdaRole \
  --policy-name ConnectionHandlerPolicy
```

## CloudWatch Alarms to Enable

### Critical Alarms (Page On-Call)

- [ ] **AudioProcessorErrors**: Lambda errors >5% in 5 minutes
  ```bash
  aws cloudwatch put-metric-alarm \
    --alarm-name AudioProcessorErrors \
    --alarm-description "Audio Processor Lambda errors" \
    --metric-name Errors \
    --namespace AWS/Lambda \
    --statistic Sum \
    --period 300 \
    --threshold 5 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1
  ```

- [ ] **TranscribeStreamFailures**: Transcribe stream initialization failures >10 in 5 minutes

- [ ] **TranslationPipelineFailures**: Translation Pipeline invocation failures >10 in 5 minutes

- [ ] **WebSocketAPIErrors**: API Gateway 5xx errors >5% in 5 minutes

- [ ] **DynamoDBThrottling**: DynamoDB throttled requests >10 in 5 minutes

### Warning Alarms (Email)

- [ ] **HighLatency**: End-to-end latency p95 >5 seconds

- [ ] **LowCacheHitRate**: Translation cache hit rate <30%

- [ ] **HighMemoryUsage**: Lambda memory usage >90%

- [ ] **ConnectionTimeouts**: Connection timeouts >10 in 5 minutes

**Verification**:
```bash
# List all alarms
aws cloudwatch describe-alarms --region us-east-1
```

## Smoke Tests to Run Post-Deployment

### Test 1: Speaker Session Creation

**Objective**: Verify speaker can create session

**Steps**:
```bash
# Connect as speaker
wscat -c "wss://<api-id>.execute-api.us-east-1.amazonaws.com/prod" \
  -H "Authorization: Bearer <jwt-token>"

# Send createSession message
{"action": "createSession", "sourceLanguage": "en"}

# Expected response
{"type": "sessionCreated", "sessionId": "golden-eagle-427", ...}
```

- [ ] Speaker can connect
- [ ] Session created successfully
- [ ] Session ID returned
- [ ] Session stored in DynamoDB

### Test 2: Audio Chunk Sending

**Objective**: Verify audio chunks reach Transcribe

**Steps**:
```bash
# Send audio chunk
{"action": "sendAudio", "sessionId": "golden-eagle-427", "audioData": "<base64>"}

# Check CloudWatch Logs
aws logs tail /aws/lambda/AudioProcessor --follow
```

- [ ] Audio chunk accepted
- [ ] Audio forwarded to Transcribe
- [ ] No errors in logs
- [ ] Metrics emitted

### Test 3: Transcription Forwarding

**Objective**: Verify transcripts forwarded to Translation Pipeline

**Steps**:
```bash
# Monitor Translation Pipeline logs
aws logs tail /aws/lambda/TranslationProcessor --follow

# Send audio and wait for transcript
# Check logs for invocation
```

- [ ] Transcript received from Transcribe
- [ ] Transcript forwarded to Translation Pipeline
- [ ] Emotion data included
- [ ] No errors in logs

### Test 4: Listener Join

**Objective**: Verify listener can join session

**Steps**:
```bash
# Connect as listener (no auth)
wscat -c "wss://<api-id>.execute-api.us-east-1.amazonaws.com/prod"

# Send joinSession message
{"action": "joinSession", "sessionId": "golden-eagle-427", "targetLanguage": "es"}

# Expected response
{"type": "sessionJoined", "sessionId": "golden-eagle-427", ...}
```

- [ ] Listener can connect
- [ ] Listener joined session
- [ ] Listener count incremented
- [ ] Connection stored in DynamoDB

### Test 5: Control Messages

**Objective**: Verify control messages work

**Steps**:
```bash
# Send pause message
{"action": "controlBroadcast", "sessionId": "golden-eagle-427", "controlAction": "pause"}

# Expected response
{"type": "broadcastControlled", "controlAction": "pause"}
```

- [ ] Pause message accepted
- [ ] Resume message accepted
- [ ] Mute message accepted
- [ ] Unmute message accepted

### Test 6: Session Status Query

**Objective**: Verify session status endpoint

**Steps**:
```bash
# Query session status
{"action": "getSessionStatus", "sessionId": "golden-eagle-427"}

# Expected response
{"type": "sessionStatus", "sessionId": "golden-eagle-427", "listenerCount": 1, ...}
```

- [ ] Session status returned
- [ ] Listener count accurate
- [ ] Session state correct

### Test 7: End-to-End Flow

**Objective**: Verify complete audio-to-translation flow

**Steps**:
1. Speaker creates session
2. Listener joins session
3. Speaker sends audio
4. Listener receives translated audio
5. Measure latency

- [ ] Complete flow works
- [ ] Latency <5 seconds
- [ ] Audio quality acceptable
- [ ] No errors

## Post-Deployment Monitoring

### CloudWatch Dashboards

- [ ] Session Management Dashboard created
- [ ] Audio Transcription Dashboard created
- [ ] Translation Pipeline Dashboard created
- [ ] System Overview Dashboard created

**Dashboard URLs**:
- Session Management: `_______________________`
- Audio Transcription: `_______________________`
- Translation Pipeline: `_______________________`
- System Overview: `_______________________`

### Metrics to Monitor (First 24 Hours)

#### Latency Metrics

- [ ] AudioProcessingLatency (p50, p95, p99)
- [ ] TranscriptionForwardingLatency (p50, p95, p99)
- [ ] EndToEndLatency (p50, p95, p99)
- [ ] ControlMessageLatency (p50, p95, p99)

**Target**: All p95 values within targets

#### Error Metrics

- [ ] LambdaErrors (all functions)
- [ ] TranscribeStreamErrors
- [ ] TranslationPipelineErrors
- [ ] EmotionExtractionErrors
- [ ] AudioValidationErrors

**Target**: Error rate <1%

#### Throughput Metrics

- [ ] SessionsCreated
- [ ] ListenersJoined
- [ ] AudioChunksProcessed
- [ ] TranscriptsForwarded
- [ ] TranslationsGenerated

**Target**: Matches expected load

#### Resource Metrics

- [ ] LambdaMemoryUsed
- [ ] LambdaDuration
- [ ] LambdaConcurrentExecutions
- [ ] DynamoDBConsumedCapacity

**Target**: Within provisioned limits

### Log Monitoring

**CloudWatch Logs Insights Queries**:

```bash
# Find all errors in last hour
fields @timestamp, @message, level, session_id, error_code
| filter level = "ERROR"
| filter @timestamp > ago(1h)
| sort @timestamp desc
| limit 100

# Monitor latency
fields @timestamp, operation, duration_ms
| filter operation in ["audio_processing", "transcribe_forward", "translation_invoke"]
| stats avg(duration_ms) as avg_latency, p95(duration_ms) as p95_latency by operation

# Track session lifecycle
fields @timestamp, operation, session_id, message
| filter session_id = "<session-id>"
| sort @timestamp asc
```

- [ ] Error logs reviewed
- [ ] Latency logs reviewed
- [ ] Session lifecycle logs reviewed
- [ ] No critical issues found

## Rollback Plan

### Rollback Triggers

**Immediate Rollback** if:
- Error rate >5%
- Latency p95 >2x baseline
- System-wide outage
- Data loss detected
- Security incident

**Rollback Procedure**:

1. **Identify Previous Version**:
   ```bash
   # List CDK stack versions
   aws cloudformation describe-stack-events \
     --stack-name SessionManagementStack \
     --region us-east-1
   ```

2. **Rollback CDK Stacks**:
   ```bash
   # Rollback to previous version
   cdk deploy SessionManagementStack \
     --version-reporting false \
     --rollback
   ```

3. **Verify Rollback**:
   ```bash
   # Run smoke tests
   # Check metrics
   # Verify functionality
   ```

4. **Communicate**:
   - Notify team
   - Update status page
   - Document incident

- [ ] Rollback procedure documented
- [ ] Rollback tested in staging
- [ ] Team trained on rollback
- [ ] Rollback contacts identified

## Sign-Off

### Deployment Approval

**Environment**: _________________ (dev/staging/prod)

**Deployed By**: _________________

**Date**: _________________

**Version**: _________________

**Approvals**:
- [ ] Tech Lead: _________________
- [ ] DevOps: _________________
- [ ] Security: _________________ (prod only)

### Post-Deployment Verification

**24-Hour Monitoring**:
- [ ] No critical errors
- [ ] Latency within targets
- [ ] Throughput as expected
- [ ] No customer complaints

**Sign-Off**:
- [ ] Deployment successful
- [ ] All smoke tests passed
- [ ] Monitoring configured
- [ ] Team notified

**Deployment Status**: ⏳ Pending / ✅ Complete / ❌ Failed

**Notes**:
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

## Additional Resources

- [Integration Points Documentation](./INTEGRATION_POINTS.md)
- [Troubleshooting Guide](./TROUBLESHOOTING.md)
- [Performance Validation](./PERFORMANCE_VALIDATION.md)
- [Security Validation](./SECURITY_VALIDATION.md)
- [CDK Documentation](../infrastructure/README.md)
