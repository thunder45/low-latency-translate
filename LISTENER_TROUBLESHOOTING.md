# Listener WebSocket Connection Troubleshooting

**Issue**: Listener WebSocket connection fails with code 1006  
**Status**: Need to investigate backend behavior

## Quick Diagnostic Steps

### 1. Check API Gateway Execution Logs

```bash
# Check API Gateway logs (if enabled)
aws logs tail /aws/apigateway/session-websocket-api-dev --since 10m
```

### 2. Check Lambda Invocations

```bash
# List all session-related Lambda functions
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `session`)].FunctionName' --output text

# Check recent invocations
aws lambda get-function --function-name session-connection-handler-dev

# Get recent logs
aws logs tail /aws/lambda/session-connection-handler-dev --since 10m --format short
```

### 3. Test WebSocket Connection Manually

Use `wscat` to test raw WebSocket connection:

```bash
# Install wscat if needed
npm install -g wscat

# Test connection WITHOUT token (listener)
wscat -c "wss://mji0q10vm1.execute-api.us-east-1.amazonaws.com/prod?sessionId=righteous-light-766&targetLanguage=de"
```

Expected: Connection should open if backend is working

### 4. Check if Lambda Was Updated

The CDK deployment may not have updated the Lambda if code didn't change:

```bash
cd session-management/infrastructure
cdk diff SessionManagement-dev
```

## Possible Issues

### A. API Gateway Route Not Updated
- Even though we deployed, route config may be cached
- Try: Delete and recreate the WebSocket API stage

### B. Lambda Code Mismatch
- Lambda code expects authorization context that's now missing
- Need to update connection_handler to handle missing authorizer data

### C. CORS or WebSocket Upgrade Issues
- Browser security blocking WebSocket upgrade
- Network/firewall blocking WebSocket connections

## Most Likely Issue: Lambda Expects Authorizer Context

Looking at connection_handler code:
```python
authorizer_context = event['requestContext'].get('authorizer', {})
user_id = authorizer_context.get('userId')
```

If we removed the authorizer, `authorizer_context` is now empty, which might cause the Lambda to fail when trying to determine role.

## Recommended Fix

Update `connection_handler/handler.py` CONNECT logic to handle missing authorizer gracefully:

```python
# Extract user context from authorizer (speaker only)
authorizer_context = event['requestContext'].get('authorizer', {})
user_id = authorizer_context.get('userId') if authorizer_context else None
```

This ensures the Lambda doesn't crash when authorizer is missing for listeners.

## Next Steps

Please toggle to Act mode so I can:
1. Check if Lambda code needs updating
2. Fix any authorizer context issues
3. Redeploy if needed
4. Test the connection
