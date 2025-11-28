# Quick Reference Card

## 🚀 Staging Environment

**WebSocket**: `wss://vphqnkfxtf.execute-api.us-east-1.amazonaws.com/prod`  
**Region**: `us-east-1`  
**Status**: ✅ DEPLOYED

## 📋 Quick Commands

### Health Check
```bash
./quick-test.sh
```

### View Logs (Real-time)
```bash
# Audio processor
aws logs tail /aws/lambda/audio-processor --region us-east-1 --follow

# Connection handler
aws logs tail /aws/lambda/session-connection-handler-staging --region us-east-1 --follow
```

### Check DynamoDB
```bash
# List tables
aws dynamodb list-tables --region us-east-1

# Scan sessions
aws dynamodb scan --table-name Sessions-staging --region us-east-1 --max-items 5
```

### Check Alarms
```bash
aws cloudwatch describe-alarms --region us-east-1 \
  --query 'MetricAlarms[?contains(AlarmName, `staging`)].{Name:AlarmName, State:StateValue}' \
  --output table
```

### Test WebSocket
```bash
# Install wscat first: npm install -g wscat
wscat -c wss://vphqnkfxtf.execute-api.us-east-1.amazonaws.com/prod
```

## 📊 Monitoring URLs

**CloudWatch Console**:
```
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1
```

**Lambda Console**:
```
https://console.aws.amazon.com/lambda/home?region=us-east-1
```

**DynamoDB Console**:
```
https://console.aws.amazon.com/dynamodb/home?region=us-east-1
```

**API Gateway Console**:
```
https://console.aws.amazon.com/apigateway/home?region=us-east-1
```

## 🔧 Common Tasks

### Redeploy Stack
```bash
cd audio-transcription/infrastructure
export AWS_DEFAULT_REGION=us-east-1
cdk deploy -c environment=staging --require-approval never

cd ../../session-management/infrastructure
cdk deploy -c env=staging --require-approval never
```

### Update Lambda Code
```bash
# After code changes
cd audio-transcription/infrastructure
cdk deploy -c environment=staging --hotswap
```

### View Recent Errors
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor \
  --region us-east-1 \
  --start-time $(($(date +%s) - 3600))000 \
  --filter-pattern "ERROR"
```

### Get Stack Outputs
```bash
aws cloudformation describe-stacks \
  --stack-name SessionManagement-staging \
  --region us-east-1 \
  --query 'Stacks[0].Outputs'
```

## 📚 Documentation

- **Testing Guide**: `TESTING_GUIDE.md`
- **Staging Status**: `STAGING_STATUS.md`
- **Deployment Summary**: `audio-transcription/docs/TASK_9_DEPLOYMENT_SUMMARY.md`
- **Architecture**: `session-management/docs/WEBSOCKET_AUDIO_INTEGRATION.md`

## 🆘 Troubleshooting

**Problem**: WebSocket won't connect  
**Solution**: Check Cognito configuration, verify JWT token

**Problem**: Lambda errors  
**Solution**: Check logs with `aws logs tail /aws/lambda/audio-processor --region us-east-1 --follow`

**Problem**: No data in DynamoDB  
**Solution**: Verify Lambda IAM permissions, check execution logs

**Problem**: High costs  
**Solution**: Check CloudWatch metrics, verify no infinite loops

## 🎯 Next Steps

1. ✅ Infrastructure deployed
2. ⏭️ Set up Cognito User Pool
3. ⏭️ Create test users
4. ⏭️ Test WebSocket connections
5. ⏭️ Run integration tests
6. ⏭️ Deploy frontend apps
7. ⏭️ Load testing
8. ⏭️ Production deployment

## 💰 Cost Estimate

**Staging**: ~$1/day (~$30/month)
- Lambda: $0.20/day
- DynamoDB: $0.50/day
- API Gateway: $0.10/day
- CloudWatch: $0.20/day

## 🗑️ Cleanup

```bash
# Delete staging environment
aws cloudformation delete-stack --stack-name SessionManagement-staging --region us-east-1
aws cloudformation delete-stack --stack-name audio-transcription-staging --region us-east-1
```
