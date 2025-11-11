# Deployment Checklist

Use this checklist to ensure all deployment steps are completed successfully.

## Pre-Deployment

### Environment Setup
- [ ] AWS CLI installed and configured
- [ ] Python 3.11+ installed
- [ ] Node.js 18+ installed
- [ ] AWS CDK CLI installed (`npm install -g aws-cdk`)
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`make install`)

### Configuration
- [ ] AWS account ID obtained
- [ ] Target region selected (default: us-east-1)
- [ ] Cognito User Pool created
- [ ] Cognito App Client created
- [ ] Configuration file created (`infrastructure/config/dev.json`)
- [ ] All required fields in config file filled
- [ ] Alarm email address configured

### Testing
- [ ] All unit tests passing (`make test`)
- [ ] Code linted successfully (`make lint`)
- [ ] Code formatted (`make format`)

### CDK Bootstrap
- [ ] CDK bootstrapped in target account/region
- [ ] Bootstrap verified (`cdk list --context env=dev`)

## Deployment

### Task 13.1: Deploy DynamoDB Tables
- [ ] Sessions table deployed
- [ ] Sessions table has TTL enabled on `expiresAt`
- [ ] Sessions table uses on-demand billing
- [ ] Connections table deployed
- [ ] Connections table has TTL enabled on `ttl`
- [ ] Connections table has GSI `sessionId-targetLanguage-index`
- [ ] Connections table uses on-demand billing
- [ ] RateLimits table deployed
- [ ] RateLimits table has TTL enabled on `expiresAt`
- [ ] RateLimits table uses on-demand billing

**Verification Commands:**
```bash
aws dynamodb list-tables --region us-east-1
aws dynamodb describe-table --table-name Sessions-dev --region us-east-1
aws dynamodb describe-time-to-live --table-name Sessions-dev --region us-east-1
aws dynamodb describe-table --table-name Connections-dev --region us-east-1 --query 'Table.GlobalSecondaryIndexes'
```

### Task 13.2: Deploy Lambda Functions
- [ ] Authorizer function deployed (128MB, 10s timeout)
- [ ] Connection Handler deployed (256MB, 30s timeout)
- [ ] Heartbeat Handler deployed (128MB, 10s timeout)
- [ ] Disconnect Handler deployed (256MB, 30s timeout)
- [ ] Refresh Handler deployed (256MB, 30s timeout)
- [ ] All functions have correct environment variables
- [ ] All functions have IAM roles with required permissions
- [ ] CloudWatch Log Groups created for all functions
- [ ] Log retention set to configured value (default: 12 hours)

**Verification Commands:**
```bash
aws lambda list-functions --region us-east-1 | grep session
aws lambda get-function --function-name session-connection-handler-dev --region us-east-1
aws lambda get-function-configuration --function-name session-connection-handler-dev --region us-east-1 --query 'Environment.Variables'
```

### Task 13.3: Deploy API Gateway
- [ ] WebSocket API created
- [ ] API has protocol type WEBSOCKET
- [ ] $connect route configured
- [ ] $disconnect route configured
- [ ] heartbeat route configured
- [ ] refreshConnection route configured
- [ ] Lambda Authorizer configured
- [ ] Authorizer attached to $connect route
- [ ] Authorizer attached to refreshConnection route
- [ ] Production stage deployed
- [ ] Stage has throttling configured
- [ ] API Gateway has permissions to invoke Lambda functions
- [ ] Lambda functions have permissions for API Gateway Management API

**Verification Commands:**
```bash
aws apigatewayv2 get-apis --region us-east-1
API_ID=$(aws apigatewayv2 get-apis --region us-east-1 --query 'Items[?Name==`session-websocket-api-dev`].ApiId' --output text)
aws apigatewayv2 get-routes --api-id $API_ID --region us-east-1
aws apigatewayv2 get-authorizers --api-id $API_ID --region us-east-1
```

### Monitoring & Alarms
- [ ] CloudWatch alarms created
- [ ] Session creation latency alarm configured
- [ ] Connection errors alarm configured
- [ ] Active sessions alarm configured
- [ ] Lambda error alarms configured for all functions
- [ ] SNS topic created
- [ ] Email subscription created
- [ ] Email subscription confirmed

**Verification Commands:**
```bash
aws cloudwatch describe-alarms --region us-east-1 | grep session
aws sns list-topics --region us-east-1 | grep session-management-alarms
aws sns list-subscriptions --region us-east-1
```

## Post-Deployment

### Verification
- [ ] CDK outputs captured and saved
- [ ] WebSocket API endpoint URL saved
- [ ] DynamoDB tables verified in AWS Console
- [ ] Lambda functions verified in AWS Console
- [ ] API Gateway verified in AWS Console
- [ ] CloudWatch Log Groups verified
- [ ] CloudWatch Alarms verified
- [ ] SNS email subscription confirmed

### Testing
- [ ] Basic WebSocket connectivity tested
- [ ] Test user created in Cognito
- [ ] JWT token obtained for test user
- [ ] Speaker session creation tested
- [ ] Listener join tested
- [ ] Heartbeat tested
- [ ] Disconnect tested
- [ ] Connection refresh tested (if applicable)

### Configuration (Production Only)
- [ ] DynamoDB Point-in-Time Recovery enabled
- [ ] Custom domain configured (if applicable)
- [ ] DNS records updated (if applicable)
- [ ] CloudWatch Dashboard created
- [ ] Log retention adjusted for production (24+ hours)

### Documentation
- [ ] WebSocket endpoint documented for client teams
- [ ] Cognito User Pool details shared
- [ ] Monitoring dashboard URL shared
- [ ] Alarm notification recipients confirmed
- [ ] Deployment notes documented

## Rollback Plan

If deployment fails or issues are discovered:

### Immediate Rollback
- [ ] Identify failing component
- [ ] Check CloudFormation events for errors
- [ ] Review Lambda function logs
- [ ] Determine if rollback is needed

### Execute Rollback
```bash
# Destroy the stack
cd infrastructure
cdk destroy --context env=dev

# Or rollback to previous version if updating
aws cloudformation cancel-update-stack --stack-name SessionManagement-dev --region us-east-1
```

### Post-Rollback
- [ ] Verify resources are cleaned up
- [ ] Document failure reason
- [ ] Fix issues in code/configuration
- [ ] Re-test locally
- [ ] Attempt deployment again

## Sign-Off

### Development Environment
- [ ] Deployment completed successfully
- [ ] All verification steps passed
- [ ] Testing completed
- [ ] Issues documented (if any)
- [ ] Deployed by: ________________
- [ ] Date: ________________

### Staging Environment
- [ ] Deployment completed successfully
- [ ] All verification steps passed
- [ ] Load testing completed
- [ ] Performance targets met
- [ ] Issues documented (if any)
- [ ] Deployed by: ________________
- [ ] Date: ________________

### Production Environment
- [ ] Deployment completed successfully
- [ ] All verification steps passed
- [ ] Production configuration applied
- [ ] PITR enabled
- [ ] Monitoring confirmed
- [ ] Stakeholders notified
- [ ] Issues documented (if any)
- [ ] Deployed by: ________________
- [ ] Approved by: ________________
- [ ] Date: ________________

## Notes

Use this section to document any issues, workarounds, or special considerations during deployment:

```
[Add deployment notes here]
```
