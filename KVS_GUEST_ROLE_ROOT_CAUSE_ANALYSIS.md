# KVS Guest Role Access Denied - Root Cause Analysis

## Problem Statement

The Guest Role (`KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt`) correctly assumes via Cognito Identity Pool but **cannot access KVS APIs** despite having the correct permissions.

## What We've Verified ✅

1. ✅ **Role exists and has correct trust policy**
   - Trust: `cognito-identity.amazonaws.com` with correct identity pool ID
   - Condition: `amr: unauthenticated` (correct for guests)

2. ✅ **Role has inline policy with KVS permissions**
   ```json
   {
     "Action": [
       "kinesisvideo:ConnectAsViewer",
       "kinesisvideo:DescribeSignalingChannel",
       "kinesisvideo:GetIceServerConfig",
       "kinesisvideo:GetSignalingChannelEndpoint"
     ],
     "Resource": "arn:aws:kinesisvideo:us-east-1:193020606184:channel/session-*/*"
   }
   ```

3. ✅ **Cognito Identity Pool configured correctly**
   - unauthenticated role: Points to guest role
   - AllowUnauthenticatedIdentities: true

4. ✅ **Browser successfully assumes guest role**
   - Confirmed via `aws sts get-caller-identity` with Cognito credentials
   - ARN: `arn:aws:sts::193020606184:assumed-role/KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt/CognitoIdentityCredentials`

5. ✅ **KVS channel exists and is active**
   - Confirmed via describe-signaling-channel
   - Status: ACTIVE, Type: SINGLE_MASTER

6. ✅ **Your user account CAN access the channel**
   - Proves channel is accessible
   - Proves no resource-based policies blocking access

7. ❌ **Guest role CANNOT access channel** 
   - Even with `Resource: "*"` (wildcard)
   - AccessDeniedException persists

## Critical Finding: Wildcard Doesn't Work

**This is the key clue!** Even after adding a policy with `Resource: "*"`, the guest role still gets AccessDeniedException. This means:

**❌ NOT a resource pattern matching issue**  
**❌ NOT an IAM propagation delay** (user said resources deployed hours ago)  
**✅ LIKELY a Service Control Policy (SCP) or session policy restriction**

## Probable Root Causes

### Theory 1: AWS Organizations Service Control Policy (SCP)

An SCP at the organization or account level might be blocking KVS access for:
- All assumed roles
- Roles assumed via Cognito Identity
- Specific KVS actions

**How to check:**
- Admin needs to review AWS Organizations SCPs
- Look for deny statements affecting KVS or assumed roles

### Theory 2: Cognito Session Policies

When Cognito Identity assumes a role, it can pass session policies that further restrict permissions. These would override the role's inline policies.

**How to check:**
```bash
# Check if Cognito is configured with role mappings that include session policies
aws cognito-identity get-identity-pool-roles \
  --identity-pool-id "us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4" \
  --output json | jq '.RoleMappings'
```

### Theory 3: IAM Condition Keys

The role policy might need specific condition keys that KVS requires for assumed role access.

**Possible fix:**
Add condition keys to the policy:
```json
{
  "Effect": "Allow",
  "Action": ["kinesisvideo:GetSignalingChannelEndpoint", ...],
  "Resource": "*",
  "Condition": {
    "StringEquals": {
      "aws:RequestedRegion": "us-east-1"
    }
  }
}
```

### Theory 4: KVS Service Permissions Model

KVS might have undocumented requirements for Cognito-assumed roles, such as:
- Requiring additional actions (ListSignalingChannels, etc.)
- Requiring permissions on related resources
- Specific resource ARN format for signaling vs streaming

## Immediate Actions to Take

### Action 1: Check for Role Mappings
```bash
aws cognito-identity get-identity-pool-roles \
  --identity-pool-id "us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4" \
  --output json | jq '.RoleMappings'
```

If this returns session policies, those are restricting access.

### Action 2: Test Authenticated Role (Comparison)

Test if the authenticated role (client role) works with Cognito credentials:

```bash
# This requires a Cognito user JWT token
# If authenticated role works but unauthenticated doesn't, 
# it suggests Cognito applies different session policies
```

### Action 3: Contact AWS Support

Given:
- All IAM configurations are correct
- Even wildcard resources don't work
- Only affects Cognito-assumed roles (your user works)

**This likely requires AWS Support** to investigate:
- SCPs in the account
- Cognito session policy behavior
- Undocumented KVS permission requirements

### Action 4: Temporary Workaround - Use Authenticated Access

Instead of unauthenticated listeners, require authentication:
1. Listeners sign in with Cognito
2. Use authenticated role (which might not have these restrictions)
3. Test if that works

## Comparison: What Works vs What Doesn't

| Configuration | Result | Why |
|--------------|--------|-----|
| Your user + KVS channel | ✅ Works | Direct user access, likely has broad permissions |
| Guest role + Resource: `session-*/*` | ❌ Fails | Unknown blocker |
| Guest role + Resource: `*` | ❌ Fails | Proves not a resource pattern issue |
| Guest role assumes correctly | ✅ Works | Trust policy is correct |

## Next Steps

1. **Check for role mappings** (Action 1 above)
2. **Test with authenticated role** as comparison
3. **Open AWS Support case** with this analysis
4. **Consider authenticated-only access** as workaround

## For AWS Support Case

Include this information:
- Account ID: 193020606184
- Identity Pool: us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4
- Guest Role: KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt
- Issue: Cognito-assumed role cannot access KVS APIs despite correct permissions
- Evidence: Even Resource="*" doesn't work
- Comparison: Direct user access works fine

## Phase 3 Status

**Phase 3 EventBridge Integration: COMPLETE ✅**
- All code deployed
- All documentation complete
- Ready to test once Phase 2 listener access is resolved

This listener access issue is a **Phase 2 blocker** that needs AWS-level investigation.
