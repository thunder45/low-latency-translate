# Testing Guide for Staging Deployment

## Quick Reference

**WebSocket Endpoint**: `wss://vphqnkfxtf.execute-api.us-east-1.amazonaws.com/prod`  
**Region**: `us-east-1`  
**Environment**: `staging`

## Prerequisites

Install required tools:
```bash
# Install wscat for WebSocket testing
npm install -g wscat

# Install AWS CLI (if not already installed)
# brew install awscli  # macOS
# pip install awscli   # Python

# Install jq for JSON parsing
brew install jq  # macOS
```

## 1. Quick Health Checks

### Check Stack Status
```bash
# Audio Transcription Stack
aws cloudformation describe-stacks \
  --stack-name audio-transcription-staging \
  --region us-east-1 \
  --query 'Stacks[0].StackStatus'

# Session Management Stack
aws cloudformation describe-stacks \
  --stack-name SessionManagement-staging \
  --region us-east-1 \
  --query 'Stacks[0].StackStatus'
```

### List Lambda Functions
```bash
aws lambda list-functions \
  --region us-east-1 \
  --query 'Functions[?contains(FunctionName, `staging`) || contains(FunctionName, `audio-processor`)].{Name:FunctionName, Runtime:Runtime, Memory:MemorySize}' \
  --output table
```

### Check DynamoDB Tables
```bash
aws dynamodb list-tables \
  --region us-east-1 \
  --query 'TableNames[?contains(@, `staging`) || contains(@, `Sessions`) || contains(@, `Connections`)]'
```

## 2. WebSocket Connection Testing

### Test 1: Basic Connection (No Auth)
This will fail with 401, but confirms the endpoint is reachable:
```bash
wscat -c wss://vphqnkfxtf.execute-api.us-east-1.amazonaws.com/prod
# Expected: Connection error or 401 Unauthorized (this is correct - auth is required)
```

### Test 2: Connection with Mock Token
First, you need a Cognito token. For testing, you can:

**Option A: Create a test user in Cognito** (if you have a user pool):
```bash
# Get your Cognito User Pool ID from config
cat session-management/infrastructure/config/staging.json | jq -r '.cognitoUserPoolId'

# Create a test user (you'll need to set up Cognito first)
aws cognito-idp admin-create-user \
  --user-pool-id us-east-1_STAGING \
  --username testuser \
  --temporary-password TempPass123! \
  --region us-east-1
```

**Option B: Test without auth** by temporarily disabling the authorizer:
```bash
# Invoke Lambda directly to test functionality
aws lambda invoke \
  --function-name audio-processor \
  --region us-east-1 \
  --payload '{"body": "test"}' \
  response.json

cat response.json
```

## 3. Lambda Function Testing

### Test Audio Processor Lambda
```bash
# Create test event
cat > test-audio-event.json << 'EOF'
{
  "requestContext": {
    "connectionId": "test-connection-123",
    "routeKey": "sendAudio"
  },
  "body": "{\"action\":\"sendAudio\",\"audioData\":\"dGVzdCBhdWRpbyBkYXRh\",\"format\":\"pcm\",\"sampleRate\":16000}"
}
EOF

# Invoke the function
aws lambda invoke \
  --function-name audio-processor \
  --region us-east-1 \
  --payload file://test-audio-event.json \
  audio-response.json

# Check response
cat audio-response.json | jq '.'
```

### Test Connection Handler
```bash
# Create connection test event
cat > test-connect-event.json << 'EOF'
{
  "requestContext": {
    "connectionId": "test-conn-456",
    "eventType": "CONNECT",
    "routeKey": "$connect"
  },
  "queryStringParameters": {
    "role": "speaker"
  }
}
EOF

# Invoke connection handler
aws lambda invoke \
  --function-name ConnectionHandler \
  --region us-east-1 \
  --payload file://test-connect-event.json \
  connect-response.json

cat connect-response.json | jq '.'
```

### Test Session Status Handler
```bash
# Create session status test event
cat > test-status-event.json << 'EOF'
{
  "requestContext": {
    "connectionId": "test-conn-789",
    "routeKey": "getSessionStatus"
  },
  "body": "{\"action\":\"getSessionStatus\",\"sessionId\":\"test-session-123\"}"
}
EOF

# Invoke session status handler
aws lambda invoke \
  --function-name SessionStatusHandler \
  --region us-east-1 \
  --payload file://test-status-event.json \
  status-response.json

cat status-response.json | jq '.'
```

## 4. DynamoDB Testing

### Check Sessions Table
```bash
# Scan sessions table (limit 10)
aws dynamodb scan \
  --table-name Sessions-staging \
  --region us-east-1 \
  --max-items 10

# Get specific session (if you know the ID)
aws dynamodb get-item \
  --table-name Sessions-staging \
  --region us-east-1 \
  --key '{"sessionId": {"S": "test-session-123"}}'
```

### Check Connections Table
```bash
# Scan connections table
aws dynamodb scan \
  --table-name Connections-staging \
  --region us-east-1 \
  --max-items 10
```

### Create Test Session Data
```bash
# Put a test session
aws dynamodb put-item \
  --table-name Sessions-staging \
  --region us-east-1 \
  --item '{
    "sessionId": {"S": "test-session-999"},
    "speakerConnectionId": {"S": "test-speaker-conn"},
    "sourceLanguage": {"S": "en"},
    "status": {"S": "active"},
    "listenerCount": {"N": "0"},
    "createdAt": {"N": "'$(date +%s)'"},
    "ttl": {"N": "'$(($(date +%s) + 43200))'"}
  }'

# Verify it was created
aws dynamodb get-item \
  --table-name Sessions-staging \
  --region us-east-1 \
  --key '{"sessionId": {"S": "test-session-999"}}'
```

## 5. CloudWatch Monitoring

### View Lambda Logs
```bash
# List log groups
aws logs describe-log-groups \
  --region us-east-1 \
  --query 'logGroups[?contains(logGroupName, `audio-processor`) || contains(logGroupName, `ConnectionHandler`)].logGroupName'

# Get recent logs for audio processor
aws logs tail /aws/lambda/audio-processor \
  --region us-east-1 \
  --follow \
  --format short

# Get recent logs for connection handler
aws logs tail /aws/lambda/ConnectionHandler \
  --region us-east-1 \
  --follow \
  --format short
```

### Check CloudWatch Metrics
```bash
# Get Lambda invocation count
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=audio-processor \
  --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region us-east-1

# Get Lambda errors
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=audio-processor \
  --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region us-east-1
```

### Check Alarms
```bash
# List all alarms
aws cloudwatch describe-alarms \
  --region us-east-1 \
  --query 'MetricAlarms[?contains(AlarmName, `staging`) || contains(AlarmName, `audio`) || contains(AlarmName, `Audio`)].{Name:AlarmName, State:StateValue}' \
  --output table

# Get specific alarm details
aws cloudwatch describe-alarms \
  --alarm-names "LambdaErrorAlarm" \
  --region us-east-1
```

## 6. Integration Testing Script

Create a simple test script:

```bash
#!/bin/bash
# save as test-staging.sh

echo "=== Staging Environment Health Check ==="
echo ""

echo "1. Checking CloudFormation Stacks..."
aws cloudformation describe-stacks \
  --stack-name audio-transcription-staging \
  --region us-east-1 \
  --query 'Stacks[0].StackStatus' \
  --output text

aws cloudformation describe-stacks \
  --stack-name SessionManagement-staging \
  --region us-east-1 \
  --query 'Stacks[0].StackStatus' \
  --output text

echo ""
echo "2. Checking Lambda Functions..."
aws lambda list-functions \
  --region us-east-1 \
  --query 'Functions[?contains(FunctionName, `staging`) || contains(FunctionName, `audio-processor`)].FunctionName' \
  --output text

echo ""
echo "3. Checking DynamoDB Tables..."
aws dynamodb list-tables \
  --region us-east-1 \
  --query 'TableNames[?contains(@, `staging`)]' \
  --output text

echo ""
echo "4. Checking CloudWatch Alarms..."
aws cloudwatch describe-alarms \
  --region us-east-1 \
  --query 'MetricAlarms[?contains(AlarmName, `staging`)].{Name:AlarmName, State:StateValue}' \
  --output table

echo ""
echo "5. Testing Lambda Invocation..."
aws lambda invoke \
  --function-name audio-processor \
  --region us-east-1 \
  --payload '{"test": true}' \
  /tmp/test-response.json > /dev/null 2>&1

if [ $? -eq 0 ]; then
  echo "✓ Lambda invocation successful"
  cat /tmp/test-response.json
else
  echo "✗ Lambda invocation failed"
fi

echo ""
echo "=== Health Check Complete ==="
```

Make it executable and run:
```bash
chmod +x test-staging.sh
./test-staging.sh
```

## 7. End-to-End Testing (Manual)

For full end-to-end testing, you'll need:

1. **Set up Cognito User Pool** (if not already done)
2. **Create test users** (speaker and listener)
3. **Build a simple test client** or use the frontend apps

### Simple Python Test Client

```python
# save as test_websocket.py
import asyncio
import websockets
import json

async def test_connection():
    uri = "wss://vphqnkfxtf.execute-api.us-east-1.amazonaws.com/prod"
    
    # Note: You'll need a valid JWT token for this to work
    # For now, this will test if the endpoint is reachable
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")
            
            # Send a test message
            message = {
                "action": "heartbeat",
                "timestamp": "2025-11-15T12:00:00Z"
            }
            await websocket.send(json.dumps(message))
            print(f"Sent: {message}")
            
            # Wait for response
            response = await websocket.recv()
            print(f"Received: {response}")
            
    except Exception as e:
        print(f"Connection failed: {e}")
        print("This is expected if authentication is required")

# Run the test
asyncio.run(test_connection())
```

Run it:
```bash
pip install websockets
python test_websocket.py
```

## 8. Monitoring Dashboard

View the CloudWatch Dashboard:
```bash
# Open in browser
echo "https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=AudioQualityDashboard"
```

Or use AWS CLI to get dashboard data:
```bash
aws cloudwatch get-dashboard \
  --dashboard-name AudioQualityDashboard \
  --region us-east-1
```

## 9. Troubleshooting Commands

### Check Lambda Errors
```bash
# Get error logs from last hour
aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor \
  --region us-east-1 \
  --start-time $(($(date +%s) - 3600))000 \
  --filter-pattern "ERROR" \
  --query 'events[*].message' \
  --output text
```

### Check API Gateway Logs
```bash
# Get API Gateway execution logs
aws logs tail /aws/apigateway/vphqnkfxtf/prod \
  --region us-east-1 \
  --follow \
  --format short
```

### Test IAM Permissions
```bash
# Check if Lambda can access DynamoDB
aws lambda get-policy \
  --function-name audio-processor \
  --region us-east-1

# Check Lambda execution role
aws lambda get-function-configuration \
  --function-name audio-processor \
  --region us-east-1 \
  --query 'Role'
```

## 10. Cleanup Test Data

After testing, clean up:
```bash
# Delete test session
aws dynamodb delete-item \
  --table-name Sessions-staging \
  --region us-east-1 \
  --key '{"sessionId": {"S": "test-session-999"}}'

# Remove test files
rm -f test-*.json audio-response.json connect-response.json status-response.json
```

## Next Steps

1. **Set up Cognito User Pool** for proper authentication testing
2. **Create integration test suite** using the patterns above
3. **Set up monitoring alerts** to your email/Slack
4. **Build frontend test application** for end-to-end testing
5. **Load testing** with multiple concurrent connections

## Common Issues

**Issue**: "Unable to connect to WebSocket"
- Check if API Gateway endpoint is correct
- Verify security groups and network access
- Check CloudWatch logs for connection errors

**Issue**: "401 Unauthorized"
- This is expected without a valid JWT token
- Set up Cognito and generate test tokens

**Issue**: "Lambda timeout"
- Check Lambda logs for errors
- Verify Lambda has correct IAM permissions
- Check if DynamoDB tables exist and are accessible

**Issue**: "No data in DynamoDB"
- Verify Lambda functions are being invoked
- Check Lambda logs for DynamoDB errors
- Verify IAM permissions for DynamoDB access
