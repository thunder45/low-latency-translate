# Creating a New Identity Pool for LowLatencyTranslate

**Date**: November 25, 2025  
**Purpose**: Create a dedicated Cognito Identity Pool to avoid breaking ServiceTranslateStack

## Why Create a New Identity Pool?

**Current Situation:**
- LowLatencyTranslate and ServiceTranslateStack share Identity Pool: `us-east-1:8a84f3fb-292e-4159-8e56-b6f238ff8d3a`
- Shared pool uses role: `ServiceTranslateStack-AuthenticatedRole`
- That role lacks KVS permissions
- Updating the shared role would break ServiceTranslateStack

**Solution:**
- Create a dedicated Identity Pool for LowLatencyTranslate
- New pool gets its own role with KVS permissions
- ServiceTranslateStack remains unchanged
- Clean separation between applications

## Prerequisites

- AWS CLI configured with proper credentials
- Access to create Cognito Identity Pools
- Existing Cognito User Pool: `us-east-1_WoaXmyQLQ`

## Step 1: Create New Identity Pool via AWS CLI

```bash
aws cognito-identity create-identity-pool \
  --identity-pool-name "LowLatencyTranslate-WebRTC-Dev" \
  --no-allow-unauthenticated-identities \
  --cognito-identity-providers \
    ProviderName=cognito-idp.us-east-1.amazonaws.com/us-east-1_WoaXmyQLQ,ClientId=38t8057tbi0o6873qt441kuo3n,ServerSideTokenCheck=true \
  --region us-east-1
```

**Note**: Remove `--profile your-profile` if you're using default AWS credentials.

**Expected Output:**
```json
{
  "IdentityPoolId": "us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "IdentityPoolName": "LowLatencyTranslate-WebRTC-Dev"
}
```

**IMPORTANT**: Copy the `IdentityPoolId` value - you'll need it in the next steps.

### Alternative: Create via AWS Console

1. Go to AWS Console → Cognito → Identity Pools
2. Click "Create identity pool"
3. Configure:
   - **Identity pool name**: `LowLatencyTranslate-WebRTC-Dev`
   - **User access**: Authenticated access
   - **Authentication flow**: Use default settings
   - **Identity providers**: 
     - Provider: Cognito User Pool
     - User Pool ID: `us-east-1_WoaXmyQLQ`
     - App client ID: `38t8057tbi0o6873qt441kuo3n`
4. Click "Next"
5. For IAM roles:
   - Select "Create a new IAM role"
   - Name: `LowLatencyTranslate-Authenticated-Role`
6. Create identity pool
7. **Copy the Identity Pool ID** from the pool details page

## Step 2: Update Backend Configuration

**File**: `session-management/infrastructure/config/dev.json`

Replace the old Identity Pool ID with the new one:

```json
{
  "account": "193020606184",
  "region": "us-east-1",
  "cognitoUserPoolId": "us-east-1_WoaXmyQLQ",
  "cognitoClientId": "38t8057tbi0o6873qt441kuo3n",
  "cognito_identity_pool_id": "us-east-1:NEW-IDENTITY-POOL-ID-HERE",  // UPDATE THIS
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

## Step 3: Deploy KVSWebRTC Stack

Now deploy the KVS stack to create the role with KVS permissions:

```bash
cd session-management/infrastructure
cdk deploy KVSWebRTC-dev --profile your-profile
```

**What this creates:**
- IAM Role: `KVSWebRTC-dev-KVSClientRole`
- Permissions:
  - `kinesisvideo:ConnectAsMaster`
  - `kinesisvideo:ConnectAsViewer`
  - `kinesisvideo:DescribeSignalingChannel`
  - `kinesisvideo:GetSignalingChannelEndpoint`
  - `kinesisvideo:GetIceServerConfig`
  - `kinesisvideo:SendAlexaOfferToMaster`

**Expected Output:**
```
✅  KVSWebRTC-dev

Outputs:
KVSWebRTC-dev.KVSClientRoleArn = arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSClientRole...
KVSWebRTC-dev.KVSManagementRoleArn = arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSManagementRole...
```

**IMPORTANT**: Copy the `KVSClientRoleArn` value.

## Step 4: Update Identity Pool to Use New Role

Now configure the new Identity Pool to use the KVS-enabled role:

### Option A: Via AWS CLI

```bash
aws cognito-identity set-identity-pool-roles \
  --identity-pool-id us-east-1:NEW-IDENTITY-POOL-ID-HERE \
  --roles authenticated=arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSClientRole... \
  --region us-east-1 \
  --profile your-profile
```

### Option B: Via AWS Console

1. Go to Cognito → Identity Pools
2. Select your new Identity Pool
3. Click "Edit identity pool"
4. Scroll to "Authenticated role"
5. Select "Choose role from IAM"
6. Find and select: `KVSWebRTC-dev-KVSClientRole`
7. Save changes

## Step 5: Update Frontend Configuration

**Files** (update both):
- `frontend-client-apps/speaker-app/.env`
- `frontend-client-apps/listener-app/.env`

Update the Identity Pool ID:

```bash
# Replace the old value
VITE_COGNITO_IDENTITY_POOL_ID=us-east-1:NEW-IDENTITY-POOL-ID-HERE
```

## Step 6: Test WebRTC Connections

```bash
# Terminal 1 - Speaker App
cd frontend-client-apps/speaker-app
npm run dev

# Terminal 2 - Listener App  
cd frontend-client-apps/listener-app
npm run dev
```

**Test Sequence:**
1. Login to speaker app
2. Create new session
3. Grant microphone permission
4. Check browser console for: `[KVS] ICE connection established successfully`
5. Join from listener app
6. Verify audio streaming

**Success Indicators:**
- No `AccessDeniedException` errors
- Console shows: "Connected as Master" (speaker) or "Connected as Viewer" (listener)
- ICE connection state: "connected"
- Audio streaming between apps

## Quick Commands Reference

```bash
# 1. Create Identity Pool
aws cognito-identity create-identity-pool \
  --identity-pool-name "LowLatencyTranslate-WebRTC-Dev" \
  --no-allow-unauthenticated-identities \
  --cognito-identity-providers \
    ProviderName=cognito-idp.us-east-1.amazonaws.com/us-east-1_WoaXmyQLQ,ClientId=38t8057tbi0o6873qt441kuo3n,ServerSideTokenCheck=true \
  --region us-east-1

# Save the output IdentityPoolId, then:

# 2. Update config/dev.json with new Identity Pool ID (not gitignored, manual edit)

# 3. Deploy KVS stack
cd session-management/infrastructure
cdk deploy KVSWebRTC-dev

# Save the KVSClientRoleArn output, then:

# 4. Link Identity Pool to KVS Role
aws cognito-identity set-identity-pool-roles \
  --identity-pool-id us-east-1:NEW-POOL-ID \
  --roles authenticated=arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSClientRole...

# 5. Update frontend .env files with new Identity Pool ID

# 6. Test!
cd frontend-client-apps/speaker-app && npm run dev
```

## Verification Checklist

- [ ] New Identity Pool created
- [ ] New Identity Pool ID copied
- [ ] Backend `config/dev.json` updated with new ID
- [ ] KVSWebRTC-dev stack deployed successfully
- [ ] KVSClientRole ARN obtained from outputs
- [ ] Identity Pool configured with KVSClientRole
- [ ] Frontend .env files updated with new Identity Pool ID
- [ ] Browser cache cleared
- [ ] Speaker app connects without AccessDeniedException
- [ ] Listener app receives audio stream

## What About ServiceTranslateStack?

**ServiceTranslateStack remains unchanged:**
- Still uses old Identity Pool: `us-east-1:8a84f3fb-292e-4159-8e56-b6f238ff8d3a`
- Still uses old role: `ServiceTranslateStack-AuthenticatedRole`
- No impact whatsoever

**LowLatencyTranslate gets new infrastructure:**
- New Identity Pool: `us-east-1:NEW-ID`
- New role: `KVSWebRTC-dev-KVSClientRole`
- KVS permissions included

## Troubleshooting

### If Identity Pool Creation Fails

**Error**: "User Pool not found"
- Verify User Pool ID: `us-east-1_WoaXmyQLQ` exists
- Check region is correct: `us-east-1`

**Error**: "Access denied"
- Verify your AWS credentials have `cognito-identity:CreateIdentityPool` permission

### If Role Assignment Fails

**Error**: "Role does not exist"
- Ensure KVSWebRTC-dev stack deployed successfully
- Verify role ARN is correct (copy from CDK outputs)

**Error**: "Invalid role trust policy"
- The CDK creates the role with correct trust policy
- If you created role manually, ensure it trusts `cognito-identity.amazonaws.com`

### If WebRTC Still Fails

**Check:**
1. Frontend .env has NEW Identity Pool ID (not old one)
2. Clear browser cache completely
3. Check browser console for credential fetch logs
4. Verify role has KVS permissions in IAM console

## Cost Considerations

**New Identity Pool Cost**: $0
- Identity Pools themselves are free
- You only pay for AWS service usage (KVS, etc.)

**New IAM Role Cost**: $0
- IAM roles are free
- No additional AWS cost

**Total Additional Cost**: $0

## Summary

**Recommended Action**: Create new dedicated Identity Pool

**Why**: 
- Safest approach
- No risk to ServiceTranslateStack  
- Best practice for multi-app architectures
- Zero additional cost

**Alternative**: Only if you absolutely must share pools, merge permissions (complex and risky)

---

**Ready to proceed?** Let me know when you've created the new Identity Pool and I can help with the rest of the configuration!
