# IAM Policy for Emotion Dynamics Lambda Function

## Overview

This document defines the IAM permissions required for the Emotion Dynamics Lambda function to operate. The policy follows the principle of least privilege, granting only the minimum permissions necessary for the function to perform its duties.

## Required Permissions

### 1. Amazon Polly - Speech Synthesis

**Permission**: `polly:SynthesizeSpeech`

**Purpose**: Generate speech audio from SSML-enhanced text

**Resource**: `*` (Polly doesn't support resource-level permissions)

**Condition**: Restricted to neural engine only for quality

```json
{
  "Sid": "PollyTextToSpeechPermissions",
  "Effect": "Allow",
  "Action": [
    "polly:SynthesizeSpeech"
  ],
  "Resource": "*",
  "Condition": {
    "StringEquals": {
      "polly:Engine": "neural"
    }
  }
}
```

**Justification**:
- Required for core functionality (Requirement 4.2)
- Neural voices provide better quality and SSML support
- Condition restricts to neural engine to prevent accidental standard voice usage

### 2. CloudWatch Logs - Logging

**Permissions**:
- `logs:CreateLogGroup` - Create log group if it doesn't exist
- `logs:CreateLogStream` - Create log stream for each invocation
- `logs:PutLogEvents` - Write log entries

**Purpose**: Enable structured logging for debugging and monitoring

**Resource**: Specific to emotion-dynamics-processor log group

```json
{
  "Sid": "CloudWatchLogsPermissions",
  "Effect": "Allow",
  "Action": [
    "logs:CreateLogGroup",
    "logs:CreateLogStream",
    "logs:PutLogEvents"
  ],
  "Resource": [
    "arn:aws:logs:*:*:log-group:/aws/lambda/emotion-dynamics-processor",
    "arn:aws:logs:*:*:log-group:/aws/lambda/emotion-dynamics-processor:*"
  ]
}
```

**Justification**:
- Required for operational visibility (Requirement 8.5)
- Scoped to specific log group for security
- Standard Lambda logging pattern

### 3. CloudWatch Metrics - Observability

**Permission**: `cloudwatch:PutMetricData`

**Purpose**: Emit custom metrics for latency, errors, and fallbacks

**Resource**: `*` (CloudWatch Metrics doesn't support resource-level permissions)

**Condition**: Restricted to EmotionDynamics namespace

```json
{
  "Sid": "CloudWatchMetricsPermissions",
  "Effect": "Allow",
  "Action": [
    "cloudwatch:PutMetricData"
  ],
  "Resource": "*",
  "Condition": {
    "StringEquals": {
      "cloudwatch:namespace": "EmotionDynamics"
    }
  }
}
```

**Justification**:
- Required for performance monitoring (Requirement 5.5, 6.4, 7.5)
- Condition restricts to specific namespace to prevent metric pollution
- Enables latency tracking and error rate monitoring

## Complete IAM Policy Document

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PollyTextToSpeechPermissions",
      "Effect": "Allow",
      "Action": [
        "polly:SynthesizeSpeech"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "polly:Engine": "neural"
        }
      }
    },
    {
      "Sid": "CloudWatchLogsPermissions",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": [
        "arn:aws:logs:*:*:log-group:/aws/lambda/emotion-dynamics-processor",
        "arn:aws:logs:*:*:log-group:/aws/lambda/emotion-dynamics-processor:*"
      ]
    },
    {
      "Sid": "CloudWatchMetricsPermissions",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "cloudwatch:namespace": "EmotionDynamics"
        }
      }
    }
  ]
}
```

## IAM Role Trust Policy

The Lambda function requires a trust policy that allows the Lambda service to assume the role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

## Creating the IAM Role

### Using AWS CLI

```bash
# Create trust policy file
cat > trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create IAM role
aws iam create-role \
    --role-name EmotionDynamicsLambdaRole \
    --assume-role-policy-document file://trust-policy.json \
    --description "Execution role for Emotion Dynamics Lambda function"

# Attach custom policy
aws iam put-role-policy \
    --role-name EmotionDynamicsLambdaRole \
    --policy-name EmotionDynamicsPolicy \
    --policy-document file://iam-policy.json

# Get role ARN
aws iam get-role \
    --role-name EmotionDynamicsLambdaRole \
    --query 'Role.Arn' \
    --output text
```

### Using AWS CDK

```python
from aws_cdk import aws_iam as iam

# Create IAM role
lambda_role = iam.Role(
    self,
    'EmotionDynamicsLambdaRole',
    assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
    description='Execution role for Emotion Dynamics Lambda function',
    role_name='EmotionDynamicsLambdaRole'
)

# Add CloudWatch Logs permissions (managed policy)
lambda_role.add_managed_policy(
    iam.ManagedPolicy.from_aws_managed_policy_name(
        'service-role/AWSLambdaBasicExecutionRole'
    )
)

# Add Polly permissions
lambda_role.add_to_policy(
    iam.PolicyStatement(
        sid='PollyTextToSpeechPermissions',
        effect=iam.Effect.ALLOW,
        actions=['polly:SynthesizeSpeech'],
        resources=['*'],
        conditions={
            'StringEquals': {
                'polly:Engine': 'neural'
            }
        }
    )
)

# Add CloudWatch Metrics permissions
lambda_role.add_to_policy(
    iam.PolicyStatement(
        sid='CloudWatchMetricsPermissions',
        effect=iam.Effect.ALLOW,
        actions=['cloudwatch:PutMetricData'],
        resources=['*'],
        conditions={
            'StringEquals': {
                'cloudwatch:namespace': 'EmotionDynamics'
            }
        }
    )
)
```

## Permission Boundaries (Optional)

For additional security in multi-tenant environments, you can apply a permission boundary:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "polly:SynthesizeSpeech",
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*"
    }
  ]
}
```

Apply boundary:

```bash
aws iam put-role-permissions-boundary \
    --role-name EmotionDynamicsLambdaRole \
    --permissions-boundary arn:aws:iam::123456789012:policy/EmotionDynamicsPermissionBoundary
```

## Security Best Practices

### 1. Least Privilege

✅ **Do**:
- Grant only required permissions
- Use conditions to restrict actions
- Scope resources where possible

❌ **Don't**:
- Use `polly:*` or `logs:*` wildcards
- Grant permissions to all resources without conditions
- Use overly permissive managed policies

### 2. Resource Scoping

✅ **Do**:
- Scope CloudWatch Logs to specific log group
- Use namespace condition for CloudWatch Metrics
- Use engine condition for Polly

❌ **Don't**:
- Allow access to all log groups
- Allow metrics in any namespace
- Allow standard Polly voices

### 3. Regular Audits

**Audit checklist**:
- [ ] Review IAM policy quarterly
- [ ] Check for unused permissions
- [ ] Verify conditions are still appropriate
- [ ] Review CloudTrail logs for denied actions
- [ ] Update policy based on actual usage

### 4. Monitoring

**CloudTrail events to monitor**:
- `polly:SynthesizeSpeech` - Track Polly usage
- `logs:PutLogEvents` - Verify logging is working
- `cloudwatch:PutMetricData` - Verify metrics emission
- Denied actions - Identify missing permissions

## Cost Implications

### Polly Costs

**Pricing** (as of 2024):
- Neural voices: $16 per 1M characters
- Standard voices: $4 per 1M characters (not used)

**Estimated usage**:
- Average text length: 100 characters
- 1000 invocations: 100,000 characters
- Cost: $1.60 per 1000 invocations

### CloudWatch Costs

**Logs**:
- $0.50 per GB ingested
- $0.03 per GB stored
- Estimated: ~$0.01 per 1000 invocations

**Metrics**:
- $0.30 per custom metric per month
- 10 custom metrics: $3.00 per month
- PutMetricData: First 1M requests free

**Total CloudWatch**: ~$3.01 per month + $0.01 per 1000 invocations

## Troubleshooting

### Common Permission Issues

**Issue 1: AccessDeniedException from Polly**

```
botocore.exceptions.ClientError: An error occurred (AccessDeniedException) 
when calling the SynthesizeSpeech operation: User is not authorized to 
perform: polly:SynthesizeSpeech
```

**Solution**:
- Verify IAM role is attached to Lambda function
- Check policy includes `polly:SynthesizeSpeech`
- Verify role trust policy allows Lambda service

**Issue 2: Unable to write logs**

```
Unable to write to CloudWatch Logs. Please check the role permissions.
```

**Solution**:
- Verify `AWSLambdaBasicExecutionRole` is attached
- Check log group name matches policy resource
- Verify log group exists or role can create it

**Issue 3: Metrics not appearing in CloudWatch**

**Solution**:
- Verify `cloudwatch:PutMetricData` permission exists
- Check namespace condition matches code
- Verify metrics are being emitted (check logs)
- Wait up to 5 minutes for metrics to appear

### Validation Commands

```bash
# Check role exists
aws iam get-role --role-name EmotionDynamicsLambdaRole

# List attached policies
aws iam list-attached-role-policies --role-name EmotionDynamicsLambdaRole

# Get inline policies
aws iam list-role-policies --role-name EmotionDynamicsLambdaRole

# Get policy document
aws iam get-role-policy \
    --role-name EmotionDynamicsLambdaRole \
    --policy-name EmotionDynamicsPolicy

# Simulate policy
aws iam simulate-principal-policy \
    --policy-source-arn arn:aws:iam::123456789012:role/EmotionDynamicsLambdaRole \
    --action-names polly:SynthesizeSpeech \
    --resource-arns "*"
```

## Compliance Considerations

### GDPR

- No PII stored in IAM policies
- Audit logs retained per compliance requirements
- Access reviews conducted quarterly

### SOC 2

- Least privilege principle enforced
- Regular access reviews documented
- Changes to IAM policies logged in CloudTrail

### HIPAA

- Not HIPAA-eligible without additional controls
- No PHI processed by this function
- If PHI required, additional encryption and logging needed

## References

- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [Amazon Polly IAM Permissions](https://docs.aws.amazon.com/polly/latest/dg/security_iam_service-with-iam.html)
- [CloudWatch IAM Permissions](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/permissions-reference-cw.html)
- [Lambda Execution Role](https://docs.aws.amazon.com/lambda/latest/dg/lambda-intro-execution-role.html)
- [IAM Policy Conditions](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition.html)

## Appendix: Alternative Configurations

### Option 1: Managed Policy Only

Use AWS managed policies for simplicity:

```python
lambda_role.add_managed_policy(
    iam.ManagedPolicy.from_aws_managed_policy_name(
        'service-role/AWSLambdaBasicExecutionRole'
    )
)
lambda_role.add_managed_policy(
    iam.ManagedPolicy.from_aws_managed_policy_name(
        'AmazonPollyFullAccess'  # Too permissive, not recommended
    )
)
```

**Pros**: Simple, quick setup
**Cons**: Overly permissive, violates least privilege

### Option 2: Separate Policies

Create separate policies for each service:

```python
# Polly policy
polly_policy = iam.Policy(
    self,
    'PollyPolicy',
    statements=[
        iam.PolicyStatement(
            actions=['polly:SynthesizeSpeech'],
            resources=['*']
        )
    ]
)
lambda_role.attach_inline_policy(polly_policy)

# Metrics policy
metrics_policy = iam.Policy(
    self,
    'MetricsPolicy',
    statements=[
        iam.PolicyStatement(
            actions=['cloudwatch:PutMetricData'],
            resources=['*']
        )
    ]
)
lambda_role.attach_inline_policy(metrics_policy)
```

**Pros**: Modular, easier to manage
**Cons**: More policies to track

### Option 3: Service Control Policies (SCP)

For organization-wide restrictions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Deny",
      "Action": [
        "polly:SynthesizeSpeech"
      ],
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "polly:Engine": "neural"
        }
      }
    }
  ]
}
```

**Pros**: Enforces standards across organization
**Cons**: Requires AWS Organizations
