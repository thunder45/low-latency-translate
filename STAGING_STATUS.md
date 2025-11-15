# Staging Environment Status

**Last Updated**: 2025-11-15  
**Region**: us-east-1  
**Environment**: staging

## ✅ Deployment Status: HEALTHY

All critical components are deployed and operational.

## Infrastructure Status

### CloudFormation Stacks
- ✅ **audio-transcription-staging**: CREATE_COMPLETE
- ✅ **SessionManagement-staging**: CREATE_COMPLETE

### Lambda Functions (8 total)
- ✅ audio-processor
- ✅ session-authorizer-staging
- ✅ session-connection-handler-staging
- ✅ session-disconnect-handler-staging
- ✅ session-heartbeat-handler-staging
- ✅ session-refresh-handler-staging
- ✅ session-status-handler-staging
- ✅ SessionManagement-staging-LogRetention (internal)

### DynamoDB Tables (6 total)
- ✅ Sessions-staging (ACTIVE)
- ✅ Connections-staging (ACTIVE)
- ✅ RateLimits-staging (ACTIVE)
- ✅ Sessions-dev (ACTIVE) - pre-existing
- ✅ Connections-dev (ACTIVE) - pre-existing
- ✅ RateLimits-dev (ACTIVE) - pre-existing

### WebSocket API
- ✅ **Endpoint**: `wss://vphqnkfxtf.execute-api.us-east-1.amazonaws.com/prod`
- ✅ **Status**: Active and reachable

### CloudWatch Alarms (7 total)
All alarms are in OK state:
- ✅ active-sessions-limit-staging: OK
- ✅ connection-errors-staging: OK
- ✅ connection-handler-errors-staging: OK
- ✅ disconnect-handler-errors-staging: OK
- ✅ heartbeat-handler-errors-staging: OK
- ✅ refresh-handler-errors-staging: OK
- ✅ session-creation-latency-staging: OK

## How to Test

### Quick Health Check
```bash
./quick-test.sh
```

### Detailed Testing
See `TESTING_GUIDE.md` for comprehensive testing instructions including:
- WebSocket connection testing
- Lambda function testing
- DynamoDB operations
- CloudWatch monitoring
- Integration testing

### Monitor Logs
```bash
# Audio processor logs
aws logs tail /aws/lambda/audio-processor --region us-east-1 --follow

# Connection handler logs
aws logs tail /aws/lambda/session-connection-handler-staging --region us-east-1 --follow

# All Lambda logs
aws logs tail --follow --region us-east-1 \
  --log-group-name /aws/lambda/audio-processor \
  --log-group-name /aws/lambda/session-connection-handler-staging
```

### Check Metrics
```bash
# View CloudWatch dashboard
open "https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:"

# Get Lambda metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=audio-processor \
  --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region us-east-1
```

## Next Steps

### 1. Authentication Setup
The WebSocket API requires authentication. To test end-to-end:

1. **Set up Cognito User Pool** (currently using placeholder):
   ```bash
   # Update staging.json with real Cognito details
   # Current placeholder: "cognitoUserPoolId": "us-east-1_STAGING"
   ```

2. **Create test users**:
   ```bash
   aws cognito-idp admin-create-user \
     --user-pool-id <YOUR_POOL_ID> \
     --username testuser \
     --temporary-password TempPass123! \
     --region us-east-1
   ```

3. **Generate JWT tokens** for testing

### 2. WebSocket Testing

Install wscat:
```bash
npm install -g wscat
```

Test connection (will fail without auth, but confirms endpoint):
```bash
wscat -c wss://vphqnkfxtf.execute-api.us-east-1.amazonaws.com/prod
```

### 3. Integration Testing

Run the integration test suite:
```bash
cd audio-transcription
pytest tests/integration/test_websocket_audio_e2e.py -v
```

### 4. Load Testing

Once basic functionality is verified:
- Test with multiple concurrent connections
- Verify auto-scaling behavior
- Monitor CloudWatch metrics under load

### 5. Frontend Integration

Deploy and test the frontend applications:
- Speaker application
- Listener application
- Admin dashboard

## Monitoring

### CloudWatch Dashboards
- **AudioQualityDashboard**: Audio processing metrics
- Custom dashboards for session management

### Key Metrics to Watch
- Lambda invocations and errors
- DynamoDB read/write capacity
- WebSocket connection count
- API Gateway 4xx/5xx errors
- Transcription latency
- Translation cache hit rate

### Alarms
All alarms are configured to send notifications to:
- SNS Topic: `arn:aws:sns:us-east-1:193020606184:session-management-alarms-staging`

Subscribe to receive alerts:
```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:193020606184:session-management-alarms-staging \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --region us-east-1
```

## Troubleshooting

### Common Issues

**WebSocket Connection Fails**
- Check if Cognito is configured
- Verify JWT token is valid
- Check CloudWatch logs for authorizer errors

**Lambda Errors**
- Check CloudWatch logs: `aws logs tail /aws/lambda/audio-processor --region us-east-1 --follow`
- Verify IAM permissions
- Check DynamoDB table access

**No Data in DynamoDB**
- Verify Lambda functions are being invoked
- Check Lambda execution role permissions
- Review CloudWatch logs for errors

### Support Resources
- Deployment documentation: `audio-transcription/docs/TASK_9_DEPLOYMENT_SUMMARY.md`
- Testing guide: `TESTING_GUIDE.md`
- Architecture docs: `session-management/docs/WEBSOCKET_AUDIO_INTEGRATION.md`

## Cost Monitoring

Current staging environment costs (estimated):
- Lambda: ~$0.20/day (minimal usage)
- DynamoDB: ~$0.50/day (on-demand)
- API Gateway: ~$0.10/day
- CloudWatch: ~$0.20/day
- **Total**: ~$1.00/day (~$30/month)

Monitor costs:
```bash
aws ce get-cost-and-usage \
  --time-period Start=2025-11-01,End=2025-11-15 \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=SERVICE \
  --region us-east-1
```

## Cleanup

To tear down the staging environment:
```bash
# Delete Session Management stack
aws cloudformation delete-stack \
  --stack-name SessionManagement-staging \
  --region us-east-1

# Delete Audio Transcription stack
aws cloudformation delete-stack \
  --stack-name audio-transcription-staging \
  --region us-east-1

# Verify deletion
aws cloudformation describe-stacks \
  --region us-east-1 \
  --query 'Stacks[?contains(StackName, `staging`)].{Name:StackName, Status:StackStatus}'
```

## Summary

✅ **All systems operational**  
✅ **Ready for testing**  
⚠️ **Cognito setup required for full end-to-end testing**

The staging environment is successfully deployed and all infrastructure components are healthy. You can now proceed with integration testing, load testing, and frontend development.
