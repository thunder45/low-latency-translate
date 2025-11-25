# Grant Cognito Identity Pool Configuration Permissions to gouveaf-dev

## Overview

This guide helps an AWS administrator grant the necessary permissions to the IAM user `gouveaf-dev` so they can configure Cognito Identity Pool roles.

## Prerequisites

- AWS Administrator access (ability to modify IAM policies)
- Access to AWS Console or AWS CLI

## Permissions Required

The policy grants:
1. **Cognito Identity Pool Role Management** - Configure identity pool roles
2. **IAM PassRole** - Attach IAM roles to Cognito Identity Pool
3. **IAM Read** - View role configurations

## Method 1: Attach Policy via AWS Console (Recommended)

### Step 1: Open IAM Console
1. Go to: https://console.aws.amazon.com/iam/
2. Click **"Users"** in the left sidebar
3. Search for and click user: **gouveaf-dev**

### Step 2: Attach Inline Policy
1. Click **"Permissions"** tab
2. Click **"Add permissions"** dropdown → **"Create inline policy"**
3. Click **"JSON"** tab
4. Copy and paste the policy from `iam-policies/cognito-identity-pool-config-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CognitoIdentityPoolRoleManagement",
      "Effect": "Allow",
      "Action": [
        "cognito-identity:SetIdentityPoolRoles",
        "cognito-identity:GetIdentityPoolRoles",
        "cognito-identity:DescribeIdentityPool",
        "cognito-identity:ListIdentityPools"
      ],
      "Resource": [
        "arn:aws:cognito-identity:us-east-1:193020606184:identitypool/us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4"
      ]
    },
    {
      "Sid": "IAMPassRoleForKVSRoles",
      "Effect": "Allow",
      "Action": [
        "iam:PassRole"
      ],
      "Resource": [
        "arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt",
        "arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN",
        "arn:aws:iam::193020606184:role/KVSWebRTC-*"
      ],
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": "cognito-identity.amazonaws.com"
        }
      }
    },
    {
      "Sid": "IAMReadRolePermissions",
      "Effect": "Allow",
      "Action": [
        "iam:GetRole",
        "iam:GetRolePolicy",
        "iam:ListRolePolicies",
        "iam:ListAttachedRolePolicies"
      ],
      "Resource": [
        "arn:aws:iam::193020606184:role/KVSWebRTC-*"
      ]
    }
  ]
}
```

5. Click **"Next"**
6. Name the policy: **CognitoIdentityPoolConfigAccess**
7. Click **"Create policy"**

### Step 3: Verify Policy Attached
1. Refresh the user's **Permissions** tab
2. Verify **CognitoIdentityPoolConfigAccess** appears in the inline policies list

## Method 2: Attach Policy via AWS CLI

An administrator can run these commands:

```bash
# Create the policy document (already exists in iam-policies/)
POLICY_FILE="iam-policies/cognito-identity-pool-config-policy.json"

# Attach inline policy to user
aws iam put-user-policy \
  --user-name gouveaf-dev \
  --policy-name CognitoIdentityPoolConfigAccess \
  --policy-document file://$POLICY_FILE

# Verify policy was attached
aws iam list-user-policies --user-name gouveaf-dev

# View policy document
aws iam get-user-policy \
  --user-name gouveaf-dev \
  --policy-name CognitoIdentityPoolConfigAccess
```

## After Permissions Are Granted

Once the policy is attached, the user can configure Cognito Identity Pool:

### Option A: Run the Fixed Deployment Script

```bash
# The script will now work end-to-end
./scripts/deploy-phase-3-with-listener-fix.sh
```

### Option B: Manual AWS CLI Configuration

```bash
# Configure Cognito Identity Pool with both roles
aws cognito-identity set-identity-pool-roles \
  --identity-pool-id "us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4" \
  --roles "unauthenticated=arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt,authenticated=arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN"

# Verify configuration
aws cognito-identity get-identity-pool-roles \
  --identity-pool-id "us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4"
```

## Security Considerations

This policy is **scoped and secure:**

✅ **Least Privilege:**
- Limited to specific identity pool (not all identity pools)
- Limited to specific KVS roles (not all IAM roles)
- PassRole condition ensures roles can only be passed to Cognito

✅ **Read-Only Where Possible:**
- IAM read permissions for troubleshooting
- No ability to create/delete roles

✅ **Production-Ready:**
- Includes wildcard for future KVS roles (KVSWebRTC-*)
- Proper resource scoping
- Condition-based PassRole protection

## Troubleshooting

### Error: "User is not authorized to perform iam:PassRole"

**Solution:** Verify the PassRole permission includes both specific role ARNs AND the wildcard pattern.

### Error: "Invalid identity pool ARN"

**Solution:** Check the identity pool ID is correct: `us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4`

### Policy Not Taking Effect

**Solution:**
1. Wait 5-10 seconds for IAM policy propagation
2. Have the user log out and log back in
3. Verify with: `aws iam get-user-policy --user-name gouveaf-dev --policy-name CognitoIdentityPoolConfigAccess`

## Alternative: Use AWS Console (No CLI Needed)

If the user still cannot run AWS CLI commands, they can configure via Console:

1. Go to: https://console.aws.amazon.com/cognito/v2/idp/identity-pools?region=us-east-1
2. Select identity pool: `us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4`
3. User access → Identity pool role settings
4. Set unauthenticated role to: `KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt`
5. Set authenticated role to: `KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN`
6. Save changes

## Summary for Administrator

**Action Required:**
Attach the inline policy `iam-policies/cognito-identity-pool-config-policy.json` to IAM user `gouveaf-dev`.

**Via Console:**
IAM → Users → gouveaf-dev → Permissions → Add permissions → Create inline policy → Paste JSON

**Via CLI:**
```bash
aws iam put-user-policy \
  --user-name gouveaf-dev \
  --policy-name CognitoIdentityPoolConfigAccess \
  --policy-document file://iam-policies/cognito-identity-pool-config-policy.json
```

**Estimated time:** 2 minutes

**Impact:** Allows user to complete Phase 2/3 deployment without admin intervention for future deployments.
