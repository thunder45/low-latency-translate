# Manual API Gateway Route Fix - AWS Console

**Issue**: API Gateway $connect route still has CUSTOM authorization (401 errors)  
**Cause**: CloudFormation drift - our CDK change didn't apply  
**Solution**: Manually update the route in AWS Console

## Fix the $connect Route

### Step 1: Open API Gateway Console

https://console.aws.amazon.com/apigateway/main/apis?region=us-east-1

### Step 2: Find Your WebSocket API

Look for: **session-websocket-api-dev**  
Type: **WebSocket**

### Step 3: Navigate to Routes

1. Click on the API name
2. Click **"Routes"** in the left sidebar
3. Find the **$connect** route

### Step 4: Edit $connect Route

1. Click on **$connect** route
2. Look for **"Authorization"** section
3. Current value: **CUSTOM** (with session-authorizer-dev)
4. Change to: **NONE**
5. **Save** changes

### Step 5: Deploy to Stage

CRITICAL: Changes don't take effect until you deploy!

1. Click **"Deployments"** in left sidebar  
2. Click **"Deploy API"**
3. Stage: **prod**
4. Description: "Remove authorization from $connect for listeners"
5. Click **"Deploy"**

### Step 6: Test with wscat

```bash
wscat -c "wss://mji0q10vm1.execute-api.us-east-1.amazonaws.com/prod?sessionId=righteous-light-766&targetLanguage=de"
```

**Expected**: Connection opens successfully (not 401)

### Step 7: Test Listener App

Refresh listener app and try joining session again.

## Grant CloudWatch Permissions to gouveaf-dev

To avoid needing root user for CloudWatch logs:

### Option A: Attach ReadOnlyAccess Policy

```bash
# As root or admin user
aws iam attach-user-policy \
  --user-name gouveaf-dev \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsReadOnlyAccess
```

### Option B: Create Custom Policy (More Restrictive)

```bash
# Create policy file
cat > cloudwatch-logs-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:FilterLogEvents",
        "logs:GetLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
EOF

# Create and attach policy
aws iam create-policy \
  --policy-name CloudWatchLogsRead \
  --policy-document file://cloudwatch-logs-policy.json

aws iam attach-user-policy \
  --user-name gouveaf-dev \
  --policy-arn arn:aws:iam::193020606184:policy/CloudWatchLogsRead
```

### Option C: Via AWS Console (Easiest)

1. Go to IAM Console → Users
2. Click on **gouveaf-dev**
3. Click **"Add permissions"**
4. Select **"Attach policies directly"**
5. Search for: **CloudWatchLogsReadOnlyAccess**
6. Check the box and click **"Add permissions"**

## Alternative: Destroy and Recreate API

If manual update doesn't work:

```bash
# This will recreate the WebSocket API with correct settings
cd session-management/infrastructure
cdk destroy SessionManagement-dev
cdk deploy SessionManagement-dev

# Note: This will change the WebSocket URL
# You'll need to update .env files with new endpoint
```

## Why This Happened

CloudFormation "drift" occurs when:
- Resources are manually modified in console
- CDK detects resources exist and skips update
- State in AWS doesn't match CDK template

The **--force** flag doesn't fix drift - only manual correction does.

## Summary

**Fastest Fix**: Manually update $connect route in AWS Console (5 minutes)  
**Nuclear Option**: Destroy and recreate stack (if manual doesn't work)  
**CloudWatch Access**: Attach CloudWatchLogsReadOnlyAccess policy to gouveaf-dev

After fixing the route, wscat should connect without 401, and listener app will work!
