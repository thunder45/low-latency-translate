# Quick Start Guide

Get the Session Management infrastructure up and running in minutes.

## Prerequisites

- Python 3.11+
- AWS CLI configured with credentials
- Node.js and npm (for AWS CDK)
- AWS CDK CLI: `npm install -g aws-cdk`

## 5-Minute Setup

### 1. Install Dependencies

```bash
cd session-management

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
make install
```

### 2. Configure AWS

Update `infrastructure/config/dev.json` with your AWS details:

```json
{
  "account": "YOUR_AWS_ACCOUNT_ID",
  "region": "us-east-1",
  "cognitoUserPoolId": "YOUR_USER_POOL_ID",
  "cognitoClientId": "YOUR_CLIENT_ID"
}
```

### 3. Bootstrap CDK (First Time Only)

```bash
make bootstrap
```

### 4. Deploy

```bash
make deploy-dev
```

That's it! Your infrastructure is now deployed.

## What Gets Deployed?

- **3 DynamoDB Tables**: Sessions, Connections, RateLimits
- **5 Lambda Functions**: Authorizer, Connection Handler, Heartbeat Handler, Disconnect Handler, Refresh Handler
- **CloudWatch Log Groups**: For monitoring and debugging

## Verify Deployment

Check the CloudFormation outputs in your terminal or AWS Console:

```bash
aws cloudformation describe-stacks --stack-name SessionManagement-dev
```

## Next Steps

1. **Test the API**: Use the WebSocket endpoint (will be added in task 10)
2. **Monitor Logs**: Check CloudWatch Logs for Lambda execution
3. **View Metrics**: Monitor DynamoDB and Lambda metrics in CloudWatch

## Common Commands

```bash
# Run tests
make test

# Format code
make format

# Lint code
make lint

# Deploy to staging
make deploy-staging

# Synthesize CloudFormation template
make synth

# Clean build artifacts
make clean
```

## Troubleshooting

### "CDK not found"
Install CDK CLI: `npm install -g aws-cdk`

### "Permission denied"
Ensure your AWS credentials have necessary permissions for DynamoDB, Lambda, IAM, and CloudWatch.

### "Bootstrap required"
Run: `make bootstrap`

## Getting Help

- Check `DEPLOYMENT.md` for detailed deployment instructions
- Review `PROJECT_STRUCTURE.md` to understand the codebase
- See `README.md` for architecture overview

## Clean Up

To remove all deployed resources:

```bash
cd infrastructure
cdk destroy --context env=dev
```

**Warning**: This deletes all data in DynamoDB tables.
