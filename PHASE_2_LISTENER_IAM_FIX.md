# Phase 2 Listener IAM Permission Fix

## Problem

The listener app fails to connect to KVS with this error:
```
AccessDeniedException: User: arn:aws:sts::193020606184:assumed-role/KVSWebRTC-dev-GuestRole/CognitoIdentityCredentials 
is not authorized to perform: kinesisvideo:GetSignalingChannelEndpoint 
on resource: arn:aws:kinesisvideo:us-east-1:193020606184:channel/session-faithful-hope-135/1764076403172
```

## Root Cause

The Cognito Identity Pool is configured with a guest role (`KVSWebRTC-dev-GuestRole`) but that role doesn't have the necessary KVS permissions for listeners to connect to signaling channels.

## Solution

I've added a proper guest role to the KVS WebRTC CDK stack with viewer-only permissions. Now you need to:

1. **Deploy the updated KVS stack** to create the new guest role
2. **Update the Cognito Identity Pool** to use the new guest role

## Step 1: Deploy Updated Infrastructure

```bash
cd session-management/infrastructure

# Deploy KVS WebRTC stack to create new guest role
cdk deploy KVSWebRTC-dev

# This will output the new KVSGuestRoleArn
```

## Step 2: Get the New Guest Role ARN

After deployment, get the role ARN from the outputs:

```bash
# Get the KVS Guest Role ARN from stack outputs
aws cloudformation describe-stacks \
  --stack-name KVSWebRTC-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`KVSGuestRoleArn`].OutputValue' \
  --output text

# Example output:
# arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSGuestRole-XXXXX
```

## Step 3: Update Cognito Identity Pool

Update the Cognito Identity Pool to use the new guest role for unauthenticated access:

```bash
# Get your identity pool ID from config
IDENTITY_POOL_ID="us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4"

# Get the new guest role ARN (replace with actual ARN from Step 2)
GUEST_ROLE_ARN="arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSGuestRole-XXXXX"

# Update the identity pool roles
aws cognito-identity set-identity-pool-roles \
  --identity-pool-id "$IDENTITY_POOL_ID" \
  --roles "unauthenticated=$GUEST_ROLE_ARN"
```

**IMPORTANT**: If you also have an authenticated role configured, include it:

```bash
# Get authenticated role ARN (if you have one)
AUTHENTICATED_ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name KVSWebRTC-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`KVSClientRoleArn`].OutputValue' \
  --output text)

# Update both roles
aws cognito-identity set-identity-pool-roles \
  --identity-pool-id "$IDENTITY_POOL_ID" \
  --roles "unauthenticated=$GUEST_ROLE_ARN,authenticated=$AUTHENTICATED_ROLE_ARN"
```

## Step 4: Verify Configuration

```bash
# Verify the identity pool role configuration
aws cognito-identity get-identity-pool-roles \
  --identity-pool-id "$IDENTITY_POOL_ID"

# You should see:
# {
#   "IdentityPoolId": "us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4",
#   "Roles": {
#     "unauthenticated": "arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSGuestRole-XXXXX",
#     "authenticated": "arn:aws:iam::193020606184:role/..."
#   }
# }
```

## Step 5: Verify IAM Policy

Check that the guest role has the correct permissions:

```bash
# Get the guest role name (from ARN)
GUEST_ROLE_NAME="KVSWebRTC-dev-KVSGuestRole-XXXXX"

# List inline policies
aws iam list-role-policies --role-name "$GUEST_ROLE_NAME"

# Get the policy document
aws iam get-role-policy \
  --role-name "$GUEST_ROLE_NAME" \
  --policy-name "Policy"
```

**Expected permissions** in the guest role:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "KVSWebRTCViewerAccess",
      "Effect": "Allow",
      "Action": [
        "kinesisvideo:ConnectAsViewer",
        "kinesisvideo:DescribeSignalingChannel",
        "kinesisvideo:GetSignalingChannelEndpoint",
        "kinesisvideo:GetIceServerConfig"
      ],
      "Resource": "arn:aws:kinesisvideo:us-east-1:193020606184:channel/session-*/*"
    }
  ]
}
```

## Step 6: Test Listener Connection

After updating the Cognito Identity Pool:

1. **Refresh the listener app** (hard reload: Cmd+Shift+R)
2. **Join a session** - should now succeed
3. **Check browser console** - no more AccessDeniedException

## What Changed in CDK

### File: `session-management/infrastructure/stacks/kvs_webrtc_stack.py`

**Added Guest Role:**
```python
# Unauthenticated users role (listeners/guests)
self.kvs_guest_role = iam.Role(
    self,
    'KVSGuestRole',
    assumed_by=iam.FederatedPrincipal(
        'cognito-identity.amazonaws.com',
        conditions={
            'StringEquals': {
                'cognito-identity.amazonaws.com:aud': cognito_identity_pool_id
            },
            'ForAnyValue:StringLike': {
                'cognito-identity.amazonaws.com:amr': 'unauthenticated'
            },
        },
        assume_role_action='sts:AssumeRoleWithWebIdentity',
    ),
    description='Guest/listener role for KVS WebRTC access (unauthenticated)',
)

# Grant guest permissions for WebRTC signaling (viewer-only)
self.kvs_guest_role.add_to_policy(
    iam.PolicyStatement(
        sid='KVSWebRTCViewerAccess',
        actions=[
            'kinesisvideo:ConnectAsViewer',
            'kinesisvideo:DescribeSignalingChannel',
            'kinesisvideo:GetSignalingChannelEndpoint',
            'kinesisvideo:GetIceServerConfig',
        ],
        resources=[
            f'arn:aws:kinesisvideo:{self.region}:{self.account}:channel/session-*/*'
        ],
    )
)
```

**Key Differences from Client Role:**
- Guest role allows only **viewer** operations (no `ConnectAsMaster`)
- Same signaling and ICE server access needed for WebRTC
- Scoped to session-specific channels only

## Troubleshooting

### If listeners still can't connect after these steps:

1. **Verify role is attached:**
```bash
aws cognito-identity get-identity-pool-roles --identity-pool-id "$IDENTITY_POOL_ID"
```

2. **Test credentials manually:**
```bash
# Get identity from pool
IDENTITY_ID=$(aws cognito-identity get-id \
  --identity-pool-id "$IDENTITY_POOL_ID" \
  --query 'IdentityId' \
  --output text)

# Get credentials
aws cognito-identity get-credentials-for-identity \
  --identity-id "$IDENTITY_ID"
```

3. **Check CloudWatch logs for auth errors:**
```bash
aws logs tail /aws/lambda/session-connection-handler-dev --follow
```

4. **Verify the session exists:**
The error log also shows `SESSION_NOT_FOUND` - make sure you're testing with a valid, active session created by a speaker.

## Quick Test Script

Save this as `test-listener-permissions.sh`:

```bash
#!/bin/bash
set -e

# Configuration
IDENTITY_POOL_ID="us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4"
STACK_NAME="KVSWebRTC-dev"

echo "1. Deploying KVS WebRTC stack..."
cd session-management/infrastructure
cdk deploy "$STACK_NAME" --require-approval never

echo "2. Getting guest role ARN..."
GUEST_ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`KVSGuestRoleArn`].OutputValue' \
  --output text)

echo "Guest Role ARN: $GUEST_ROLE_ARN"

echo "3. Getting authenticated role ARN..."
AUTH_ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`KVSClientRoleArn`].OutputValue' \
  --output text)

echo "Authenticated Role ARN: $AUTH_ROLE_ARN"

echo "4. Updating Cognito Identity Pool roles..."
aws cognito-identity set-identity-pool-roles \
  --identity-pool-id "$IDENTITY_POOL_ID" \
  --roles "unauthenticated=$GUEST_ROLE_ARN,authenticated=$AUTH_ROLE_ARN"

echo "5. Verifying configuration..."
aws cognito-identity get-identity-pool-roles \
  --identity-pool-id "$IDENTITY_POOL_ID"

echo "✅ Configuration complete! Test the listener app now."
```

Make executable and run:
```bash
chmod +x test-listener-permissions.sh
./test-listener-permissions.sh
```

## Summary

**Phase 2 listener IAM issue fixed:**
- ✅ Created KVS Guest Role in CDK with viewer-only permissions
- ✅ Role allows `GetSignalingChannelEndpoint`, `GetIceServerConfig`, etc.
- ⏳ Need to deploy and configure Cognito Identity Pool (manual steps above)

**Once completed:**
- Listeners can connect to KVS channels as viewers
- No authentication required for listening
- Proper least-privilege access (viewer-only, no master capabilities)

This is separate from **Phase 3 EventBridge integration** which is complete and ready for backend audio processing.
