# Deployment Guide

## Prerequisites

1. **AWS Account**: You need an AWS account with appropriate permissions
2. **AWS CLI**: Install and configure AWS CLI with credentials
3. **Python 3.11+**: Required for Lambda functions and CDK
4. **Node.js**: Required for AWS CDK CLI
5. **AWS CDK CLI**: Install globally with `npm install -g aws-cdk`

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

Edit `infrastructure/config/dev.json` and update:
- `account`: Your AWS account ID
- `region`: AWS region (default: us-east-1)
- `cognitoUserPoolId`: Your Cognito User Pool ID
- `cognitoClientId`: Your Cognito App Client ID

### 3. Bootstrap CDK (First Time Only)

```bash
cd infrastructure
cdk bootstrap aws://ACCOUNT-ID/REGION
```

Replace `ACCOUNT-ID` and `REGION` with your values.

## Deployment

### Deploy to Development

```bash
make deploy-dev
```

Or manually:

```bash
cd infrastructure
cdk deploy --context env=dev
```

### Deploy to Staging

```bash
make deploy-staging
```

### Deploy to Production

```bash
make deploy-prod
```

## Verify Deployment

After deployment, CDK will output:
- DynamoDB table names
- Lambda function ARNs
- WebSocket API endpoint (when implemented)

You can verify the deployment in the AWS Console:
1. **DynamoDB**: Check that tables are created
2. **Lambda**: Verify functions are deployed
3. **CloudWatch Logs**: Check log groups are created

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

## Troubleshooting

### CDK Bootstrap Issues

If you encounter bootstrap errors:
```bash
cdk bootstrap --force
```

### Permission Errors

Ensure your AWS credentials have permissions for:
- DynamoDB (create/update tables)
- Lambda (create/update functions)
- IAM (create roles and policies)
- CloudWatch Logs (create log groups)
- API Gateway (create WebSocket APIs)

### Deployment Failures

Check CloudFormation events in AWS Console for detailed error messages.

## Clean Up

To remove all resources:

```bash
cd infrastructure
cdk destroy --context env=dev
```

**Warning**: This will delete all DynamoDB tables and their data.
