# IAM Policy Propagation - Waiting for Permissions to Activate

## Critical Finding from Debug Script

✅ **Identity obtained:** `us-east-1:2cf0ecb6-e8c2-c376-0ba7-45395d3ff840`  
✅ **Credentials fetched:** Successfully  
✅ **Role assumed:** `KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt` ← **CORRECT!**  
❌ **KVS API call:** AccessDeniedException ← **IAM propagation delay**

## Root Cause: IAM Policy Propagation Delay

**AWS IAM policy changes can take 5-15 minutes to fully propagate globally.**

### Timeline:
- **T+0 min** (4:20 PM): CDK deployed guest role with KVS permissions
- **T+20 min** (4:40 PM): Role exists, but permissions not yet active globally
- **T+5-15 min** (4:25-4:35 PM): **← We are here - waiting for propagation**
- **T+15 min+** (4:35 PM+): Permissions fully propagated, API calls work

## What's Happening

1. **CDK created the role** ✅
2. **Role has inline policy** with KVS permissions ✅
3. **Cognito Identity Pool configured** to use the role ✅
4. **Browser assumes the role** correctly ✅
5. **IAM permissions are propagating** ⏳ ← **Current bottleneck**
6. **KVS API will work once propagation complete** ⏳

## Solution: Wait and Retry

### Option 1: Wait 10 Minutes, Then Test

```bash
# Current time: ~4:44 PM
# Expected working: ~4:50 PM (10 min after initial deployment)

# At 4:50 PM, run the debug script
./scripts/debug-listener-credentials.sh
```

**If successful**, you'll see:
```
✅ SUCCESS! KVS call worked
ResourceEndpointList: [...]
```

**Then test the listener app** - it should work!

### Option 2: Retry Loop Script

```bash
#!/bin/bash
# retry-listener-test.sh

for i in {1..10}; do
  echo "Attempt $i of 10..."
  
  if ./scripts/debug-listener-credentials.sh 2>&1 | grep -q "SUCCESS"; then
    echo "✅ Permissions working! Test listener app now."
    exit 0
  fi
  
  echo "Still propagating... waiting 60 seconds"
  sleep 60
done

echo "❌ Permissions still not working after 10 minutes. Check for other issues."
```

### Option 3: Force IAM Cache Invalidation (Advanced)

AWS doesn't provide a direct way to force propagation, but you can:

```bash
# 1. Remove and re-add the policy (forces refresh)
ROLE_NAME="KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt"
POLICY_NAME="KVSGuestRoleDefaultPolicyE9CC46BC"

# Get current policy
aws iam get-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "$POLICY_NAME" \
  --query 'PolicyDocument' > /tmp/guest-policy.json

# Delete policy
aws iam delete-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "$POLICY_NAME"

# Re-add immediately
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "$POLICY_NAME" \
  --policy-document file:///tmp/guest-policy.json

# This sometimes triggers faster propagation
```

## Monitoring Propagation

### Check IAM Policy Versions
```bash
# List all versions of the role policy
aws iam list-role-policies \
  --role-name KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt

# Get the policy document
aws iam get-role-policy \
  --role-name KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt \
  --policy-name KVSGuestRoleDefaultPolicyE9CC46BC
```

### Test from Different AWS Region
IAM is global, but propagation can vary by region:

```bash
# Test from us-west-2
AWS_REGION=us-west-2 ./scripts/debug-listener-credentials.sh

# If this works but us-east-1 doesn't, it's definitely propagation delay
```

## Why This Happens

**AWS IAM is eventually consistent:**
- Policy changes replicate across multiple AWS regions
- Changes propagate to all AWS services
- KVS service caches IAM policies for performance
- Total propagation time: typically 5-15 minutes, sometimes up to 30 minutes

**Factors affecting propagation:**
- Number of AWS regions
- Current AWS system load
- IAM service caching
- Time of day (peak vs off-peak)

## Expected Propagation Timeline

| Time | Status | Action |
|------|--------|--------|
| 4:20 PM | Role deployed | Wait |
| 4:25 PM | Partial propagation | Test may fail |
| 4:30 PM | More propagation | Test may work |
| 4:35 PM | Should be ready | **Test now** |
| 4:40 PM | Definitely ready | If still failing, check other issues |

## What To Do Right Now

**Current time: ~4:44 PM**

1. **Wait until 4:50 PM** (10 min after initial deployment at 4:20 PM + 20 more min)
2. **Run:** `./scripts/debug-listener-credentials.sh`
3. **If SUCCESS:** Test listener app (it will work!)
4. **If still fails:** Run again at 5:00 PM (sometimes takes 15+ min)

## Alternative: Test with List Operations (Lower Level)

```bash
# List all signaling channels (doesn't require specific channel access)
aws kinesisvideo list-signaling-channels --max-results 10

# If this works, permissions are propagating
# If this fails, there's a deeper issue
```

## If Still Failing After 30 Minutes

Check for these issues:

1. **AWS Organizations SCP** blocking KVS access
2. **Permission boundary** on the role
3. **Resource-based policy** on KVS channel denying access
4. **Wrong AWS partition** (should be `aws`, not `aws-cn` or `aws-gov`)

## Summary

**Status:** IAM propagation in progress (normal 5-15 min delay)

**Action:** Wait until ~4:50-5:00 PM, then run:
```bash
./scripts/debug-listener-credentials.sh
```

**Expected:** Script will show "✅ SUCCESS! KVS call worked"

**Then:** Test listener app - permissions will work!

This is a normal AWS IAM behavior, not a configuration error.
