# Listener IAM Trust Policy Fix - ADMIN ACTION REQUIRED

## Root Cause Identified ✅

The listener authentication is working correctly, but the IAM role trust policy is blocking credential exchange.

### The Problem

**IAM Role:** `KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN`

**Current Trust Policy:** Only trusts speaker's Identity Pool
```json
{
  "cognito-identity.amazonaws.com:aud": "us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4"
}
```

**Error:** `InvalidIdentityPoolConfigurationException: Invalid identity pool configuration. Check assigned IAM roles for this pool.`

**Why it fails:**
- Listener uses different Identity Pool: `us-east-1:8e81542d-4b76-4b2e-966d-998939e67a23`
- IAM role doesn't trust this Identity Pool
- Cognito Identity can't assume the role to return credentials

## Solution: Update IAM Role Trust Policy

### Admin Command (Requires IAM Permissions)

```bash
aws iam update-assume-role-policy \
  --role-name KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN \
  --policy-document file://tmp/kvs-role-trust-policy-both-pools.json
```

### Trust Policy Content

**File:** `tmp/kvs-role-trust-policy-both-pools.json`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "cognito-identity.amazonaws.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "cognito-identity.amazonaws.com:aud": [
            "us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4",
            "us-east-1:8e81542d-4b76-4b2e-966d-998939e67a23"
          ]
        },
        "ForAnyValue:StringLike": {
          "cognito-identity.amazonaws.com:amr": "authenticated"
        }
      }
    }
  ]
}
```

### What Changed

**Before (Speaker Only):**
```json
"cognito-identity.amazonaws.com:aud": "us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4"
```

**After (Speaker + Listener):**
```json
"cognito-identity.amazonaws.com:aud": [
  "us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4",  // Speaker Identity Pool
  "us-east-1:8e81542d-4b76-4b2e-966d-998939e67a23"   // Listener Identity Pool
]
```

## Verification After Update

### 1. Verify Trust Policy Updated
```bash
aws iam get-role \
  --role-name KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN \
  --query 'Role.AssumeRolePolicyDocument' \
  --output json
```

Should show both Identity Pool IDs in the `aud` condition.

### 2. Test Listener Authentication

```bash
cd frontend-client-apps/listener-app
npm run dev
```

1. Open http://localhost:5174
2. Login with advm@advm.lu
3. Join a speaker session
4. **Expected:** Credentials obtained successfully, audio playback works

### 3. Check Console Logs

**Success indicators:**
```
[KVS Credentials] Fetching authenticated credentials from Cognito Identity Pool...
[KVS Credentials] Got Identity ID: us-east-1:2cf0ecb6-e81e-cafc-b32b-e11377490b34
[KVS Credentials] Credentials obtained, valid until: [timestamp]
```

**No errors like:**
- ❌ `InvalidIdentityPoolConfigurationException`
- ❌ `Access Denied`

## Why This Fix is Necessary

### Current State
```
Speaker Flow (Works):
  User Pool (us-east-1_WoaXmyQLQ)
    → Identity Pool (us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4)  ✅ Trusted
    → IAM Role (KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN)
    → KVS Access ✅

Listener Flow (Blocked):
  User Pool (us-east-1_Tn5BZTL7h)
    → Identity Pool (us-east-1:8e81542d-4b76-4b2e-966d-998939e67a23)  ❌ NOT Trusted
    → IAM Role (KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN)
    → KVS Access ❌ BLOCKED
```

### After Fix
```
Both Speaker and Listener:
  → Identity Pools (both trusted)  ✅
  → IAM Role (KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN)
  → KVS Access ✅
```

## Alternative Solutions

### Option 1: Use Speaker's Identity Pool (Not Recommended)
Change listener `.env` to use speaker's Identity Pool:
```env
VITE_COGNITO_IDENTITY_POOL_ID=us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4
```

**Cons:**
- Mixes speaker and listener identities
- Less clear separation of concerns
- Harder to track/audit usage

### Option 2: Update Trust Policy (Recommended) ✅
Add listener's Identity Pool to IAM role trust policy as shown above.

**Pros:**
- Clean separation of concerns
- Easy to track speaker vs listener usage
- Scalable for future additions

## Security Implications

✅ **No security risk** - Both Identity Pools require authentication
✅ **Same permissions** - IAM role permissions unchanged (KVS viewer)
✅ **Audit trail** - Can differentiate speaker vs listener in CloudTrail
✅ **Flexible** - Easy to add more Identity Pools or remove access

## IAM Permissions Required

The admin user needs these IAM permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iam:UpdateAssumeRolePolicy",
        "iam:GetRole"
      ],
      "Resource": "arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN"
    }
  ]
}
```

## Summary

**Authentication is working ✅** - Login successful, tokens stored
**Credential exchange is blocked ❌** - IAM role doesn't trust listener's Identity Pool
**Fix required:** Admin must update IAM role trust policy to include both Identity Pools

Once the trust policy is updated, the listener app will successfully obtain AWS credentials and connect to KVS channels.

**Action Required:** Admin user with IAM permissions must run the update command above.
