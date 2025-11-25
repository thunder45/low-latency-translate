# Manual Cognito Identity Pool Configuration

## Issue

The deployment script cannot automatically configure the Cognito Identity Pool roles because your IAM user lacks the `cognito-identity:SetIdentityPoolRoles` permission:

```
AccessDeniedException: User: arn:aws:iam::193020606184:user/gouveaf-dev 
is not authorized to perform: cognito-identity:SetIdentityPoolRoles
```

## ✅ What Was Successfully Deployed

**All infrastructure is deployed and ready:**
- ✅ KVS Guest Role created: `arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt`
- ✅ KVS Client Role created: `arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN`
- ✅ HTTP Session Handler updated with EventBridge events
- ✅ KVS Stream Consumer ready to process streams
- ✅ EventBridge rules configured

**Only missing:** Cognito Identity Pool role configuration (requires admin permission)

## Solution Options

### Option 1: AWS Console (Easiest)

1. **Open Cognito Console:**
   - Go to: https://console.aws.amazon.com/cognito/v2/idp/identity-pools
   - Region: **us-east-1**

2. **Select Identity Pool:**
   - Click on identity pool: `us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4`

3. **Navigate to User Access:**
   - Click **"User access"** in left sidebar
   - Click **"Identity pool role settings"** tab

4. **Configure Roles:**
   - **Unauthenticated role:** Select `KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt`
   - **Authenticated role:** Select `KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN`

5. **Save Changes:**
   - Click **"Save changes"**

### Option 2: AWS CLI (Requires Admin)

Ask someone with admin permissions to run this command:

```bash
aws cognito-identity set-identity-pool-roles \
  --identity-pool-id "us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4" \
  --roles "unauthenticated=arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt,authenticated=arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN"
```

### Option 3: Request IAM Permission (For Future)

Ask your admin to add this permission to your IAM user/role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cognito-identity:SetIdentityPoolRoles",
        "cognito-identity:GetIdentityPoolRoles",
        "iam:PassRole"
      ],
      "Resource": [
        "arn:aws:cognito-identity:us-east-1:193020606184:identitypool/us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4",
        "arn:aws:iam::193020606184:role/KVSWebRTC-dev-*"
      ]
    }
  ]
}
```

## Verification After Configuration

Once configured, verify with:

```bash
# Check current role configuration
aws cognito-identity get-identity-pool-roles \
  --identity-pool-id "us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4"

# Expected output:
# {
#   "IdentityPoolId": "us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4",
#   "Roles": {
#     "unauthenticated": "arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt",
#     "authenticated": "arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN"
#   }
# }
```

## Test After Configuration

### 1. Test Listener App (Phase 2 Fix)

```bash
# 1. Open listener app
open http://localhost:5174

# 2. Hard refresh browser (Cmd+Shift+R) to clear credentials cache

# 3. Create a session in speaker app

# 4. Join the session in listener app

# Expected: ✅ Connection succeeds, no AccessDeniedException
```

### 2. Test EventBridge Integration (Phase 3)

```bash
# Monitor both Lambda functions
aws logs tail /aws/lambda/session-http-handler-dev --follow &
aws logs tail /aws/lambda/kvs-stream-consumer-dev --follow &

# Create a session (use speaker app or HTTP API)
# Watch for these log messages:

# In session-http-handler-dev:
# - "EventBridge event emitted for session creation"
# - sessionId, channelArn, status=ACTIVE

# In kvs-stream-consumer-dev:
# - "Processing EventBridge event: session=..., status=ACTIVE"
# - "Starting stream processing for session..."
```

## Role ARNs (Quick Reference)

**Guest Role (Listeners):**
```
arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt
```

**Client Role (Speakers):**
```
arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN
```

**Identity Pool ID:**
```
us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4
```

## What the Roles Provide

### Guest Role (Unauthenticated - Listeners)
✅ `kinesisvideo:ConnectAsViewer`  
✅ `kinesisvideo:DescribeSignalingChannel`  
✅ `kinesisvideo:GetSignalingChannelEndpoint`  
✅ `kinesisvideo:GetIceServerConfig`  
❌ `kinesisvideo:ConnectAsMaster` (not allowed)

### Client Role (Authenticated - Speakers)
✅ `kinesisvideo:ConnectAsMaster`  
✅ `kinesisvideo:ConnectAsViewer`  
✅ `kinesisvideo:DescribeSignalingChannel`  
✅ `kinesisvideo:GetSignalingChannelEndpoint`  
✅ `kinesisvideo:GetIceServerConfig`  
✅ `kinesisvideo:SendAlexaOfferToMaster`

## Summary

**Deployment Status:**
- ✅ All AWS infrastructure deployed successfully
- ✅ Phase 3 EventBridge integration ready
- ✅ Phase 2 IAM roles created
- ⏳ **Manual step required:** Configure Cognito Identity Pool (see options above)

**Once configured:**
- Listeners will be able to connect to KVS channels
- Backend audio processing will automatically start on session creation
- Complete end-to-end flow will work

**Estimated time to configure:** 2-5 minutes via AWS Console
