# Deployment Guide

This guide covers the complete deployment process for the Session Management & WebSocket Infrastructure component, including DynamoDB tables, Lambda functions, and API Gateway WebSocket API.

## Prerequisites

1. **AWS Account**: You need an AWS account with appropriate permissions
2. **AWS CLI**: Install and configure AWS CLI with credentials
   ```bash
   aws configure
   # Enter your AWS Access Key ID, Secret Access Key, and default region
   ```
3. **Python 3.11+**: Required for Lambda functions and CDK
   ```bash
   python --version  # Should be 3.11 or higher
   ```
4. **Node.js 18+**: Required for AWS CDK CLI
   ```bash
   node --version  # Should be 18 or higher
   ```
5. **AWS CDK CLI**: Install globally with npm
   ```bash
   npm install -g aws-cdk
   cdk --version  # Verify installation
   ```

## Required IAM Permissions

Your AWS user/role needs the following permissions:
- **DynamoDB**: CreateTable, UpdateTable, DescribeTable, DeleteTable, TagResource
- **Lambda**: CreateFunction, UpdateFunctionCode, UpdateFunctionConfiguration, DeleteFunction
- **IAM**: CreateRole, AttachRolePolicy, PutRolePolicy, DeleteRole
- **API Gateway**: CreateApi, CreateRoute, CreateIntegration, CreateAuthorizer, CreateDeployment, CreateStage
- **CloudWatch Logs**: CreateLogGroup, PutRetentionPolicy
- **CloudWatch**: PutMetricAlarm, DeleteAlarms
- **SNS**: CreateTopic, Subscribe
- **CloudFormation**: CreateStack, UpdateStack, DeleteStack, DescribeStacks

## Initial Setup

### 1. Install Dependencies

```bash
cd session-management

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Install CDK dependencies
cd infrastructure
pip install -r requirements.txt
cd ..
```

### 2. Configure Environment

Copy the example configuration and update with your values:

```bash
cp infrastructure/config/dev.json.example infrastructure/config/dev.json
```

Edit `infrastructure/config/dev.json` and update the following required fields:

**Required Configuration:**
- `account`: Your AWS account ID (find with `aws sts get-caller-identity --query Account --output text`)
- `region`: AWS region (default: us-east-1)
- `cognitoUserPoolId`: Your Cognito User Pool ID (create one if needed)
- `cognitoClientId`: Your Cognito App Client ID
- `alarmEmail`: Email address for CloudWatch alarm notifications

**Optional Configuration (with defaults):**
- `sessionMaxDurationHours`: 2 (API Gateway WebSocket hard limit)
- `connectionRefreshMinutes`: 100 (trigger refresh at 1h 40min)
- `connectionWarningMinutes`: 105 (warn at 1h 45min)
- `maxListenersPerSession`: 500
- `dataRetentionHours`: 12
- `maxActiveSessions`: 100

**Example dev.json:**
```json
{
  "account": "123456789012",
  "region": "us-east-1",
  "cognitoUserPoolId": "us-east-1_ABC123XYZ",
  "cognitoClientId": "1a2b3c4d5e6f7g8h9i0j",
  "sessionMaxDurationHours": 2,
  "connectionRefreshMinutes": 100,
  "connectionWarningMinutes": 105,
  "maxListenersPerSession": 500,
  "dataRetentionHours": 12,
  "maxActiveSessions": 100,
  "alarmEmail": "your-email@example.com"
}
```

**Note on Cognito Setup:**
If you don't have a Cognito User Pool yet, create one:
```bash
aws cognito-idp create-user-pool \
  --pool-name translation-speakers \
  --policies 'PasswordPolicy={MinimumLength=8,RequireUppercase=true,RequireLowercase=true,RequireNumbers=true}' \
  --auto-verified-attributes email \
  --region us-east-1

# Create app client
aws cognito-idp create-user-pool-client \
  --user-pool-id <USER_POOL_ID> \
  --client-name translation-web-client \
  --no-generate-secret \
  --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH \
  --region us-east-1
```

### 3. Bootstrap CDK (First Time Only)

```bash
cd infrastructure
cdk bootstrap aws://ACCOUNT-ID/REGION
```

Replace `ACCOUNT-ID` and `REGION` with your values.

## Deployment

### Pre-Deployment Checklist

Before deploying, ensure:
- [ ] AWS CLI is configured with correct credentials
- [ ] Configuration file is updated with your AWS account details
- [ ] Cognito User Pool and App Client are created
- [ ] CDK is bootstrapped in your account/region
- [ ] All tests are passing: `make test`

### Deploy to Development

**Option 1: Using Makefile (Recommended)**
```bash
make deploy-dev
```

**Option 2: Manual CDK Deployment**
```bash
cd infrastructure
cdk deploy --context env=dev --require-approval never
```

**What Gets Deployed:**

1. **DynamoDB Tables (Task 13.1)**
   - `Sessions-dev` table with TTL enabled on `expiresAt`
   - `Connections-dev` table with TTL enabled on `ttl` and GSI `sessionId-targetLanguage-index`
   - `RateLimits-dev` table with TTL enabled on `expiresAt`
   - All tables use on-demand billing mode

2. **Lambda Functions (Task 13.2)**
   - `session-authorizer-dev` (128MB, 10s timeout)
   - `session-connection-handler-dev` (256MB, 30s timeout)
   - `session-heartbeat-handler-dev` (128MB, 10s timeout)
   - `session-disconnect-handler-dev` (256MB, 30s timeout)
   - `session-refresh-handler-dev` (256MB, 30s timeout)
   - All functions include environment variables from config

3. **API Gateway WebSocket API (Task 13.3)**
   - WebSocket API with custom domain support
   - Routes: $connect, $disconnect, heartbeat, refreshConnection
   - Lambda Authorizer for speaker authentication
   - Production stage with throttling configured

4. **Monitoring & Alarms**
   - CloudWatch Log Groups with 12-hour retention
   - CloudWatch Alarms for latency, errors, and capacity
   - SNS topic for alarm notifications

**Deployment Time:** Approximately 5-10 minutes

### Deploy to Staging

First, create staging configuration:
```bash
cp infrastructure/config/dev.json infrastructure/config/staging.json
# Edit staging.json with staging-specific values
```

Then deploy:
```bash
make deploy-staging
```

### Deploy to Production

**⚠️ Production Deployment Requires Extra Care**

1. Create production configuration:
```bash
cp infrastructure/config/dev.json infrastructure/config/prod.json
# Edit prod.json with production values
```

2. Review changes before deploying:
```bash
cd infrastructure
cdk diff --context env=prod
```

3. Deploy with approval:
```bash
make deploy-prod
# Or manually:
cd infrastructure
cdk deploy --context env=prod
```

**Production Recommendations:**
- Set `dataRetentionHours` to 24 or higher
- Configure `alarmEmail` to a team distribution list
- Consider increasing `maxListenersPerSession` if needed
- Enable DynamoDB Point-in-Time Recovery (PITR) manually after deployment

## Verify Deployment

### 1. Check CDK Outputs

After successful deployment, CDK will display outputs:
```
Outputs:
SessionManagement-dev.SessionsTableName = Sessions-dev
SessionManagement-dev.ConnectionsTableName = Connections-dev
SessionManagement-dev.RateLimitsTableName = RateLimits-dev
SessionManagement-dev.WebSocketAPIEndpoint = wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod
SessionManagement-dev.AlarmTopicArn = arn:aws:sns:us-east-1:123456789012:session-management-alarms-dev
```

Save the WebSocket API endpoint - you'll need it for client applications.

### 2. Verify DynamoDB Tables (Task 13.1)

**Check table creation:**
```bash
# List tables
aws dynamodb list-tables --region us-east-1

# Describe Sessions table
aws dynamodb describe-table --table-name Sessions-dev --region us-east-1

# Verify TTL is enabled
aws dynamodb describe-time-to-live --table-name Sessions-dev --region us-east-1

# Verify GSI on Connections table
aws dynamodb describe-table --table-name Connections-dev --region us-east-1 \
  --query 'Table.GlobalSecondaryIndexes[0].IndexName'
```

**Expected Results:**
- Sessions table exists with `expiresAt` TTL attribute
- Connections table exists with `ttl` TTL attribute and `sessionId-targetLanguage-index` GSI
- RateLimits table exists with `expiresAt` TTL attribute
- All tables use `PAY_PER_REQUEST` billing mode

### 3. Verify Lambda Functions (Task 13.2)

**Check function deployment:**
```bash
# List functions
aws lambda list-functions --region us-east-1 | grep session

# Get function details
aws lambda get-function --function-name session-connection-handler-dev --region us-east-1

# Check environment variables
aws lambda get-function-configuration \
  --function-name session-connection-handler-dev \
  --region us-east-1 \
  --query 'Environment.Variables'
```

**Expected Results:**
- All 5 Lambda functions are deployed
- Functions have correct memory and timeout settings
- Environment variables include table names and configuration parameters
- Functions have IAM roles with DynamoDB and CloudWatch permissions

### 4. Verify API Gateway (Task 13.3)

**Check WebSocket API:**
```bash
# List APIs
aws apigatewayv2 get-apis --region us-east-1

# Get API details
API_ID=$(aws apigatewayv2 get-apis --region us-east-1 \
  --query 'Items[?Name==`session-websocket-api-dev`].ApiId' --output text)

# List routes
aws apigatewayv2 get-routes --api-id $API_ID --region us-east-1

# Check authorizer
aws apigatewayv2 get-authorizers --api-id $API_ID --region us-east-1
```

**Expected Results:**
- WebSocket API exists with protocol type `WEBSOCKET`
- Routes: `$connect`, `$disconnect`, `heartbeat`, `refreshConnection`
- Lambda Authorizer is configured for `$connect` and `refreshConnection` routes
- Stage `prod` is deployed

### 5. Test WebSocket Connectivity

**Basic connection test using wscat:**
```bash
# Install wscat if not already installed
npm install -g wscat

# Test connection (will fail without valid JWT, but confirms API is reachable)
wscat -c "wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod?action=createSession&sourceLanguage=en&qualityTier=standard&token=YOUR_JWT_TOKEN"
```

**Expected Result:**
- Connection attempt reaches API Gateway
- Without valid JWT: Receives 401 Unauthorized
- With valid JWT: Receives `sessionCreated` message

### 6. Verify Monitoring Setup

**Check CloudWatch resources:**
```bash
# List log groups
aws logs describe-log-groups --region us-east-1 | grep session

# List alarms
aws cloudwatch describe-alarms --region us-east-1 | grep session

# Check SNS topic
aws sns list-topics --region us-east-1 | grep session-management-alarms
```

**Expected Results:**
- Log groups created for each Lambda function
- CloudWatch alarms created for latency, errors, and capacity
- SNS topic created for alarm notifications
- Email subscription pending confirmation (check your email)

### 7. Smoke Test

Run a simple smoke test to verify end-to-end functionality:

```bash
# Create a test user in Cognito
aws cognito-idp admin-create-user \
  --user-pool-id us-east-1_ABC123XYZ \
  --username testuser \
  --temporary-password TempPass123! \
  --user-attributes Name=email,Value=test@example.com \
  --region us-east-1

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id us-east-1_ABC123XYZ \
  --username testuser \
  --password TestPass123! \
  --permanent \
  --region us-east-1

# Authenticate and get JWT token
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id 1a2b3c4d5e6f7g8h9i0j \
  --auth-parameters USERNAME=testuser,PASSWORD=TestPass123! \
  --region us-east-1 \
  --query 'AuthenticationResult.IdToken' \
  --output text
```

Use the JWT token to test WebSocket connection as shown in step 5.

### Verification Checklist

- [ ] All DynamoDB tables created with correct configuration
- [ ] TTL enabled on appropriate attributes
- [ ] GSI created on Connections table
- [ ] All Lambda functions deployed with correct settings
- [ ] Environment variables configured properly
- [ ] WebSocket API created with all routes
- [ ] Lambda Authorizer configured
- [ ] CloudWatch Log Groups created
- [ ] CloudWatch Alarms configured
- [ ] SNS topic created and email subscription confirmed
- [ ] WebSocket endpoint is accessible
- [ ] Basic connectivity test passes

## Rollback

To rollback a deployment:

```bash
cd infrastructure
cdk destroy --context env=dev
```

## Updating Configuration

1. Update the configuration file: `infrastructure/config/dev.json`
2. Redeploy: `make deploy-dev`

CDK will automatically detect changes and update only affected resources.

## Monitoring

After deployment, monitor your application:

1. **CloudWatch Logs**: View Lambda function logs
2. **CloudWatch Metrics**: Monitor custom metrics
3. **DynamoDB Console**: Check table metrics and items

## Post-Deployment Configuration

### 1. Enable DynamoDB Point-in-Time Recovery (Production Only)

For production environments, enable PITR for disaster recovery:

```bash
# Enable PITR for Sessions table
aws dynamodb update-continuous-backups \
  --table-name Sessions-prod \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true \
  --region us-east-1

# Enable PITR for Connections table
aws dynamodb update-continuous-backups \
  --table-name Connections-prod \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true \
  --region us-east-1

# Enable PITR for RateLimits table
aws dynamodb update-continuous-backups \
  --table-name RateLimits-prod \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true \
  --region us-east-1
```

### 2. Configure Custom Domain (Optional)

To use a custom domain for your WebSocket API:

```bash
# Create custom domain
aws apigatewayv2 create-domain-name \
  --domain-name ws.yourdomain.com \
  --domain-name-configurations CertificateArn=arn:aws:acm:us-east-1:123456789012:certificate/abc-123 \
  --region us-east-1

# Create API mapping
aws apigatewayv2 create-api-mapping \
  --domain-name ws.yourdomain.com \
  --api-id $API_ID \
  --stage prod \
  --region us-east-1

# Update DNS with the domain name's target domain
```

### 3. Confirm SNS Email Subscription

Check your email for SNS subscription confirmation and click the confirmation link. This enables CloudWatch alarm notifications.

### 4. Create CloudWatch Dashboard

Create a dashboard for monitoring:

```bash
# Create dashboard JSON file
cat > dashboard.json << 'EOF'
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["SessionManagement", "SessionCreationLatency", {"stat": "p95"}],
          [".", "ListenerJoinLatency", {"stat": "p95"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "Latency Metrics"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["SessionManagement", "ActiveSessions"],
          [".", "TotalListeners"]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "Active Resources"
      }
    }
  ]
}
EOF

# Create dashboard
aws cloudwatch put-dashboard \
  --dashboard-name SessionManagement-dev \
  --dashboard-body file://dashboard.json \
  --region us-east-1
```

## Load Testing

Before going to production, run load tests to verify performance:

### Prerequisites

Install load testing tools:
```bash
pip install locust websocket-client
```

### Run Load Tests

Create a load test script `load_test.py`:

```python
from locust import User, task, between
import websocket
import json
import time

class WebSocketUser(User):
    wait_time = between(1, 5)
    
    def on_start(self):
        """Connect to WebSocket on start."""
        ws_url = "wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod"
        self.ws = websocket.create_connection(
            f"{ws_url}?action=joinSession&sessionId=test-session-123&targetLanguage=es"
        )
    
    @task
    def send_heartbeat(self):
        """Send heartbeat message."""
        self.ws.send(json.dumps({"action": "heartbeat"}))
        response = self.ws.recv()
        assert json.loads(response)["type"] == "heartbeatAck"
    
    def on_stop(self):
        """Close connection on stop."""
        self.ws.close()
```

Run load test:
```bash
# Test with 100 concurrent users
locust -f load_test.py --host wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod --users 100 --spawn-rate 10
```

**Performance Targets:**
- Session creation: <2s p95 latency
- Listener join: <1s p95 latency
- Heartbeat response: <100ms p95 latency
- Support 100 concurrent sessions
- Support 500 listeners per session

## Troubleshooting

### CDK Bootstrap Issues

If you encounter bootstrap errors:
```bash
# Force re-bootstrap
cdk bootstrap --force aws://ACCOUNT-ID/REGION

# Or with specific toolkit stack name
cdk bootstrap --toolkit-stack-name CDKToolkit-custom aws://ACCOUNT-ID/REGION
```

### Permission Errors

Ensure your AWS credentials have permissions for:
- DynamoDB (create/update tables)
- Lambda (create/update functions)
- IAM (create roles and policies)
- CloudWatch Logs (create log groups)
- API Gateway (create WebSocket APIs)
- CloudFormation (create/update stacks)

**Check your permissions:**
```bash
# Verify identity
aws sts get-caller-identity

# Test DynamoDB permissions
aws dynamodb list-tables --region us-east-1

# Test Lambda permissions
aws lambda list-functions --region us-east-1
```

### Deployment Failures

**Check CloudFormation events:**
```bash
# Get stack events
aws cloudformation describe-stack-events \
  --stack-name SessionManagement-dev \
  --region us-east-1 \
  --max-items 20
```

**Common issues:**

1. **Insufficient permissions**: Add required IAM permissions to your user/role
2. **Resource limits**: Check AWS service quotas in your account
3. **Invalid configuration**: Verify config/dev.json has correct values
4. **Cognito not found**: Ensure User Pool and App Client exist

### Lambda Function Errors

**View function logs:**
```bash
# Get recent logs
aws logs tail /aws/lambda/session-connection-handler-dev --follow --region us-east-1

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/session-connection-handler-dev \
  --filter-pattern "ERROR" \
  --region us-east-1
```

### WebSocket Connection Issues

**Test with verbose output:**
```bash
# Install wscat with debug
wscat -c "wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod?action=createSession&sourceLanguage=en&qualityTier=standard&token=JWT_TOKEN" --debug
```

**Common issues:**

1. **401 Unauthorized**: Invalid or expired JWT token
2. **403 Forbidden**: Lambda Authorizer denied access
3. **500 Internal Error**: Check Lambda function logs
4. **Connection timeout**: Check API Gateway configuration

### DynamoDB Issues

**Check table status:**
```bash
# Verify table is active
aws dynamodb describe-table \
  --table-name Sessions-dev \
  --region us-east-1 \
  --query 'Table.TableStatus'

# Check TTL status
aws dynamodb describe-time-to-live \
  --table-name Sessions-dev \
  --region us-east-1
```

### Monitoring Issues

**Verify metrics are being published:**
```bash
# List metrics
aws cloudwatch list-metrics \
  --namespace SessionManagement \
  --region us-east-1

# Get metric statistics
aws cloudwatch get-metric-statistics \
  --namespace SessionManagement \
  --metric-name SessionCreationLatency \
  --start-time 2025-11-11T00:00:00Z \
  --end-time 2025-11-11T23:59:59Z \
  --period 3600 \
  --statistics Average \
  --region us-east-1
```

## Clean Up

To remove all resources:

```bash
cd infrastructure
cdk destroy --context env=dev
```

**Warning**: This will delete all DynamoDB tables and their data.
