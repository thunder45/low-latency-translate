# Phase 3: Backend IAM Permissions Issue

**Date**: November 25, 2025  
**Status**: ⚠️ **Backend Configuration Required**

## Issue Summary

The frontend WebRTC code is working correctly, but the backend IAM permissions are not properly configured. The Cognito Identity Pool is using an old role that lacks KVS permissions.

## Error Details

```
User: arn:aws:sts::193020606184:assumed-role/ServiceTranslateStack-AuthenticatedRole86104F1A-9jxUz0pyoDyA/CognitoIdentityCredentials 
is not authorized to perform: kinesisvideo:GetSignalingChannelEndpoint 
on resource: arn:aws:kinesisvideo:us-east-1:193020606184:channel/session-peaceful-gospel-701/1764058120804
```

## Root Cause

1. **Old Identity Pool**: There's an existing Cognito Identity Pool from a previous stack (`ServiceTranslateStack`)
2. **Old Role**: That Identity Pool uses `ServiceTranslateStack-AuthenticatedRole` which doesn't have KVS permissions
3. **New Role Not Created**: The `KVSWebRTCStack` can create a new `KVSClientRole` with proper permissions, but only if `cognito_identity_pool_id` is provided
4. **Missing Config**: The backend config (`session-management/infrastructure/config/dev.json`) doesn't have `cognito_identity_pool_id`

## What's NOT Wrong

✅ **Phase 2 Frontend Code** - Working perfectly:
- EventEmitter polyfill correctly bundled
- WebRTC services instantiating properly
- Credentials being fetched from Cognito Identity Pool
- App loads and runs in browser

❌ **Backend IAM Setup** - Needs configuration:
- Identity Pool authenticated role lacks KVS permissions
- Backend CDK not deploying KVS client role
- Identity Pool not configured to use new role

## Solution Steps

### Step 1: Understand Identity Pool vs Identity ID

**IMPORTANT**: Don't confuse these two:

1. **Identity Pool ID** (what you need): `us-east-1:8a84f3fb-292e-4159-8e56-b6f238ff8d3a`
   - This is the ID of the Identity Pool itself
   - Used in backend config and frontend .env files
   - One per application

2. **Identity ID** (from error log): `us-east-1:2cf0ecb6-e8fa-c390-2042-7776e186b389`
   - This is a specific user's Identity within the pool
   - Assigned to individual authenticated users
   - Many per Identity Pool
   - NOT used in configuration

**You need**: The Identity Pool ID (`us-east-1:8a84f3fb-292e-4159-8e56-b6f238ff8d3a`)

Find it in AWS Console:
```bash
# AWS Console:
# 1. Go to Cognito → Identity Pools
# 2. Select your Identity Pool
# 3. Copy the Identity Pool ID from the top (format: us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
```

### Step 2: Update Backend Configuration

Add the Identity Pool ID to your backend config:

**File**: `session-management/infrastructure/config/dev.json`

```json
{
  "account": "193020606184",
  "region": "us-east-1",
  "cognitoUserPoolId": "us-east-1_WoaXmyQLQ",
  "cognitoClientId": "38t8057tbi0o6873qt441kuo3n",
  "cognito_identity_pool_id": "us-east-1:2cf0ecb6-e8fa-c390-2042-7776e186b389",  // ADD THIS LINE
  "sessionMaxDurationHours": 2,
  "connectionRefreshMinutes": 100,
  "connectionWarningMinutes": 105,
  "maxListenersPerSession": 500,
  "rateLimitSessionsPerHour": 50,
  "rateLimitListenerJoinsPerMin": 10,
  "rateLimitConnectionAttemptsPerMin": 20,
  "rateLimitHeartbeatsPerMin": 2,
  "dataRetentionHours": 12,
  "maxActiveSessions": 100,
  "alarmEmail": "your-email@example.com"
}
```

### Step 3: Deploy Backend to Create New Role

```bash
cd session-management/infrastructure
cdk deploy KVSWebRTC-dev --profile your-profile
```

This will create a new IAM role: `KVSWebRTC-dev-KVSClientRole` with proper permissions:
- `kinesisvideo:ConnectAsMaster`
- `kinesisvideo:ConnectAsViewer`
- `kinesisvideo:DescribeSignalingChannel`
- `kinesisvideo:GetSignalingChannelEndpoint`
- `kinesisvideo:GetIceServerConfig`

### Step 4: Update Identity Pool to Use New Role

After deployment, get the new role ARN from CDK outputs:

```bash
# Get the new role ARN
aws cloudformation describe-stacks \
  --stack-name KVSWebRTC-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`KVSClientRoleArn`].OutputValue' \
  --output text
```

Then update your Identity Pool:

**Option A: Via AWS Console**
1. Go to Cognito → Identity Pools
2. Select your Identity Pool
3. Edit authenticated role
4. Replace with new `KVSWebRTC-dev-KVSClientRole` ARN

**Option B: Via AWS CLI**
```bash
aws cognito-identity set-identity-pool-roles \
  --identity-pool-id us-east-1:2cf0ecb6-e8fa-c390-2042-7776e186b389 \
  --roles authenticated=arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSClientRole... \
  --profile your-profile
```

### Step 5: Test WebRTC Connection

After updating the Identity Pool:

1. Clear browser cache/cookies
2. Refresh the speaker app
3. Create a new session
4. Verify you see: "ICE connection established successfully"

## Technical Details

### What the KVSClientRole Does

The `KVSClientRole` in `kvs_webrtc_stack.py` is designed for frontend clients:

```python
self.kvs_client_role = iam.Role(
    self,
    'KVSClientRole',
    assumed_by=iam.FederatedPrincipal(
        'cognito-identity.amazonaws.com',
        conditions={
            'StringEquals': {
                'cognito-identity.amazonaws.com:aud': cognito_identity_pool_id
            },
            'ForAnyValue:StringLike': {
                'cognito-identity.amazonaws.com:amr': 'authenticated'
            },
        },
        assume_role_action='sts:AssumeRoleWithWebIdentity',
    ),
    description='Frontend client role for KVS WebRTC access',
)
```

### Why Phase 2 is Complete

Phase 2 was about **frontend WebRTC integration**:
- ✅ EventEmitter browser compatibility fixed
- ✅ WebRTC services implemented
- ✅ Credentials provider working
- ✅ Apps build and load successfully

This IAM issue is **backend infrastructure** (Phase 3 territory):
- ❌ Backend CDK not creating KVS client role
- ❌ Identity Pool using wrong role
- ❌ KVS permissions not granted

## Alternative: Create New Identity Pool

If updating the existing pool is problematic, you can create a new Identity Pool:

```bash
# Create new Identity Pool with User Pool provider
aws cognito-identity create-identity-pool \
  --identity-pool-name low-latency-translate-webrtc \
  --allow-unauthenticated-identities false \
  --cognito-identity-providers \
    ProviderName=cognito-idp.us-east-1.amazonaws.com/us-east-1_WoaXmyQLQ,ClientId=38t8057tbi0o6873qt441kuo3n \
  --profile your-profile
```

Then follow steps 2-4 above with the new Identity Pool ID.

## Verification Checklist

After completing the solution:

- [ ] Backend config has `cognito_identity_pool_id`
- [ ] `KVSWebRTC-dev` stack deployed successfully
- [ ] `KVSClientRole` exists in IAM
- [ ] Identity Pool configured with new role
- [ ] Frontend .env files have `VITE_COGNITO_IDENTITY_POOL_ID`
- [ ] Browser cache cleared
- [ ] Speaker app creates session without KVS errors
- [ ] Browser console shows "ICE connection established"

## Summary

**Phase 2 Status**: ✅ **COMPLETE** - EventEmitter issue resolved, frontend WebRTC code working

**Phase 3 Status**: ⚠️ **BLOCKED** - Backend IAM permissions need configuration

**Next Action**: Update backend config and redeploy to create proper IAM role

---

**Related Documentation**:
- `EVENTEMITTER_FIX_SOLUTION.md` - Phase 2 fix details
- `PHASE_2_STATUS_UPDATED.md` - Phase 2 completion status
- `COGNITO_POOLS_EXPLAINED.md` - User Pool vs Identity Pool
