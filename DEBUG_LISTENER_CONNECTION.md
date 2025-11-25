# Debug Listener WebSocket Connection - AWS Console Method

**Issue**: Listener WebSocket fails with code 1006  
**Code Fixed**: Empty token issue resolved  
**Backend**: Deployed with authorization removed

## Check CloudWatch Logs via AWS Console

Since CLI isn't accessible, use the console:

### 1. Open CloudWatch Logs Console
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups

### 2. Find Connection Handler Log Group
Look for: `/aws/lambda/session-connection-handler-dev`

### 3. View Recent Logs
1. Click on the log group
2. Look at the most recent log streams
3. Search for logs containing "righteous-light-766" (your session ID)
4. Look for ERROR or WARNING messages

### 4. What to Look For

**If Lambda is invoked**:
- You'll see "Connection handler invoked" log
- Check if it reaches "Connection accepted" or errors before

**If Lambda NOT invoked**:
- API Gateway is blocking before Lambda
- Check API Gateway execution logs

## Alternative: Test with wscat

Install and test raw WebSocket:

```bash
npm install -g wscat

# Test listener connection (no token)
wscat -c "wss://mji0q10vm1.execute-api.us-east-1.amazonaws.com/prod?sessionId=righteous-light-766&targetLanguage=de"
```

If this connects, frontend issue. If fails, backend issue.

## Most Likely Causes

### A. API Gateway Cache (Most Likely)
CDK deployed but API Gateway still using old configuration.

**Fix**: Force new deployment
```bash
cd session-management/infrastructure
cdk deploy SessionManagement-dev --force
```

### B. Lambda Not Updated
CDK didn't redeploy Lambda because code didn't change.

**Check**: Look at Lambda last modified time in console

### C. Missing KVS Management Role
Lambda needs permissions to manage KVS channels but might not have been granted.

**Check**: Lambda IAM role has KVS permissions

## Quick Test in AWS Console

###  Test Connection Via API Gateway Console

1. Go to: API Gateway Console → Your WebSocket API
2. Click "Dashboard" → "Test"
3. Try connecting with: `?sessionId=righteous-light-766&targetLanguage=de`
4. See immediate error response

## Summary

Can you check CloudWatch logs in the AWS Console for `/aws/lambda/session-connection-handler-dev` to see what error the Lambda is returning?

Or try the `wscat` test to see if it's a browser-specific issue?
