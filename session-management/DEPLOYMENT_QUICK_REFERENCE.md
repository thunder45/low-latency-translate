# Deployment Quick Reference

Quick command reference for deploying the Session Management infrastructure.

> **📌 Note**: This is a command cheat sheet for experienced users. If you're new to this project, start with [QUICKSTART.md](QUICKSTART.md) for a tutorial-style guide with explanations.

## Prerequisites Check

```bash
# Check AWS CLI
aws --version
aws sts get-caller-identity

# Check Python
python --version  # Should be 3.11+

# Check Node.js
node --version  # Should be 18+

# Check CDK
cdk --version
```

## Initial Setup (One-Time)

```bash
# Clone and navigate to project
cd session-management

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
make install

# Configure environment
cp infrastructure/config/dev.json.example infrastructure/config/dev.json
# Edit dev.json with your AWS account details

# Bootstrap CDK (first time only)
make bootstrap
# Or: cd infrastructure && cdk bootstrap
```

## Deploy

```bash
# Deploy to development
make deploy-dev

# Deploy to staging
make deploy-staging

# Deploy to production
make deploy-prod
```

## Verify Deployment

```bash
# Check DynamoDB tables
aws dynamodb list-tables --region us-east-1

# Check Lambda functions
aws lambda list-functions --region us-east-1 | grep session

# Check API Gateway
aws apigatewayv2 get-apis --region us-east-1

# Get WebSocket endpoint
aws cloudformation describe-stacks \
  --stack-name SessionManagement-dev \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`WebSocketAPIEndpoint`].OutputValue' \
  --output text
```

## Test Connection

```bash
# Install wscat
npm install -g wscat

# Get JWT token (replace with your Cognito details)
TOKEN=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id YOUR_CLIENT_ID \
  --auth-parameters USERNAME=testuser,PASSWORD=TestPass123! \
  --region us-east-1 \
  --query 'AuthenticationResult.IdToken' \
  --output text)

# Test WebSocket connection
wscat -c "wss://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod?action=createSession&sourceLanguage=en&qualityTier=standard&token=$TOKEN"
```

## Monitor

```bash
# View Lambda logs
aws logs tail /aws/lambda/session-connection-handler-dev --follow --region us-east-1

# Check CloudWatch metrics
aws cloudwatch list-metrics --namespace SessionManagement --region us-east-1

# View alarms
aws cloudwatch describe-alarms --region us-east-1 | grep session
```

## Update Deployment

```bash
# Make code changes
# ...

# Run tests
make test

# Deploy updates
make deploy-dev
```

## Rollback

```bash
# Destroy stack
cd infrastructure
cdk destroy --context env=dev

# Or cancel in-progress update
aws cloudformation cancel-update-stack \
  --stack-name SessionManagement-dev \
  --region us-east-1
```

## Troubleshooting

```bash
# Check CloudFormation events
aws cloudformation describe-stack-events \
  --stack-name SessionManagement-dev \
  --region us-east-1 \
  --max-items 20

# View Lambda function errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/session-connection-handler-dev \
  --filter-pattern "ERROR" \
  --region us-east-1

# Check DynamoDB table status
aws dynamodb describe-table \
  --table-name Sessions-dev \
  --region us-east-1 \
  --query 'Table.TableStatus'

# Verify TTL configuration
aws dynamodb describe-time-to-live \
  --table-name Sessions-dev \
  --region us-east-1
```

## Common Issues

### Issue: CDK Bootstrap Failed
```bash
# Solution: Force re-bootstrap
cdk bootstrap --force aws://ACCOUNT-ID/REGION
```

### Issue: Permission Denied
```bash
# Solution: Check IAM permissions
aws sts get-caller-identity
# Ensure you have permissions for DynamoDB, Lambda, IAM, API Gateway, CloudFormation
```

### Issue: Deployment Timeout
```bash
# Solution: Check CloudFormation events for details
aws cloudformation describe-stack-events \
  --stack-name SessionManagement-dev \
  --region us-east-1
```

### Issue: Lambda Function Error
```bash
# Solution: Check function logs
aws logs tail /aws/lambda/FUNCTION-NAME --follow --region us-east-1
```

## Environment Variables Reference

Key environment variables set in Lambda functions:

- `ENV`: Environment name (dev/staging/prod)
- `REGION`: AWS region
- `USER_POOL_ID`: Cognito User Pool ID
- `CLIENT_ID`: Cognito App Client ID
- `SESSIONS_TABLE`: Sessions DynamoDB table name
- `CONNECTIONS_TABLE`: Connections DynamoDB table name
- `RATE_LIMITS_TABLE`: RateLimits DynamoDB table name
- `SESSION_MAX_DURATION_HOURS`: Maximum session duration (default: 2)
- `CONNECTION_REFRESH_MINUTES`: Connection refresh threshold (default: 100)
- `CONNECTION_WARNING_MINUTES`: Connection warning threshold (default: 105)
- `MAX_LISTENERS_PER_SESSION`: Maximum listeners per session (default: 500)
- `API_GATEWAY_ENDPOINT`: WebSocket API endpoint URL

## CDK Commands

```bash
# Synthesize CloudFormation template
cd infrastructure
cdk synth --context env=dev

# Show differences
cdk diff --context env=dev

# Deploy with approval
cdk deploy --context env=dev

# Deploy without approval
cdk deploy --context env=dev --require-approval never

# List stacks
cdk list --context env=dev

# Destroy stack
cdk destroy --context env=dev
```

## Useful AWS CLI Commands

```bash
# Get account ID
aws sts get-caller-identity --query Account --output text

# List all resources in region
aws resourcegroupstaggingapi get-resources --region us-east-1

# Get CloudFormation stack outputs
aws cloudformation describe-stacks \
  --stack-name SessionManagement-dev \
  --region us-east-1 \
  --query 'Stacks[0].Outputs'

# Enable DynamoDB PITR (production)
aws dynamodb update-continuous-backups \
  --table-name Sessions-prod \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true \
  --region us-east-1
```

## Performance Targets

Monitor these metrics after deployment:

- **Session Creation Latency**: <2s (p95)
- **Listener Join Latency**: <1s (p95)
- **Heartbeat Response**: <100ms (p95)
- **Concurrent Sessions**: 100+
- **Listeners per Session**: 500
- **Connection Duration**: Unlimited (via refresh)

## Cost Monitoring

```bash
# Check DynamoDB consumed capacity
aws dynamodb describe-table \
  --table-name Sessions-dev \
  --region us-east-1 \
  --query 'Table.BillingModeSummary'

# Check Lambda invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=session-connection-handler-dev \
  --start-time 2025-11-11T00:00:00Z \
  --end-time 2025-11-11T23:59:59Z \
  --period 86400 \
  --statistics Sum \
  --region us-east-1
```

## Support

For issues or questions:
1. Check DEPLOYMENT.md for detailed instructions
2. Review TROUBLESHOOTING.md for common issues
3. Check CloudWatch Logs for error details
4. Review CloudFormation events for deployment issues
5. Contact the development team
