# AWS Resource Cleanup Guide - Post-Phase 4

**Date:** November 28, 2025  
**Purpose:** Identify obsolete AWS resources that can be safely deleted after Phase 4 deployment  
**Status:** Phase 4 (Kinesis) deployed, Phase 0-3 resources obsolete

---

## ⚠️ IMPORTANT: Read Before Deleting

1. **Backup first:** Export configuration files and IAM policies before deletion
2. **Test Phase 4 first:** Ensure Phase 4 works before removing old resources
3. **Delete in order:** Follow the sequence below to avoid dependency issues
4. **Check references:** Some resources may be referenced in tests or monitoring

---

## Resources to DELETE (Obsolete)

### 1. CloudFormation Stack: `KVSWebRTC-dev` ✅ SAFE TO DELETE

**Why:** This entire stack was for WebRTC peer-to-peer architecture (abandoned Nov 28)

**What it contains:**
- IAM Role: `KVSWebRTC-dev-KVSManagementRole-*`
- IAM Role: `KVSWebRTC-dev-KVSClientRole-*`
- IAM Role: `KVSWebRTC-dev-KVSGuestRole-*`
- CloudWatch Log Group: `/aws/kinesisvideo/webrtc`

**How to delete:**
```bash
# Delete the entire stack (deletes all resources above)
aws cloudformation delete-stack --stack-name KVSWebRTC-dev --region us-east-1

# Wait for deletion
aws cloudformation wait stack-delete-complete --stack-name KVSWebRTC-dev --region us-east-1

# Verify deleted
aws cloudformation describe-stacks --stack-name KVSWebRTC-dev --region us-east-1
# Should return: Stack with id KVSWebRTC-dev does not exist
```

**Verification:** Phase 4 doesn't use KVS WebRTC at all

---

### 2. Lambda Functions (Already deleted from Phase 4 deployment)

These should already be gone if Phase 4 was deployed:

**Check if they still exist:**
```bash
# These should NOT exist anymore
aws lambda get-function --function-name kvs-stream-writer-dev --region us-east-1
aws lambda get-function --function-name s3-audio-consumer-dev --region us-east-1
aws lambda get-function --function-name kvs-stream-consumer-dev --region us-east-1
```

**If they still exist (CDK didn't remove them):**
```bash
# Manually delete
aws lambda delete-function --function-name kvs-stream-writer-dev --region us-east-1
aws lambda delete-function --function-name s3-audio-consumer-dev --region us-east-1
aws lambda delete-function --function-name kvs-stream-consumer-dev --region us-east-1
```

---

### 3. Lambda Layer: FFmpeg ⚠️ CHECK FIRST

**Status:** Should be deleted (not used in Phase 4)

**Check if referenced:**
```bash
# List all Lambda functions and their layers
aws lambda list-functions --region us-east-1 --query 'Functions[*].[FunctionName, Layers[*].Arn]' --output table | grep -i ffmpeg

# If no results, safe to delete
```

**How to delete (if not used):**
```bash
# Find layer versions
aws lambda list-layer-versions --layer-name ffmpeg-layer-dev --region us-east-1

# Delete each version
aws lambda delete-layer-version --layer-name ffmpeg-layer-dev --version-number <version> --region us-east-1
```

---

### 4. S3 Event Notifications ✅ SHOULD BE REMOVED

**What:** S3 bucket `low-latency-audio-dev` still has event notifications for `.pcm` and `.webm` files that trigger `s3-audio-consumer-dev`

**Check current state:**
```bash
aws s3api get-bucket-notification-configuration --bucket low-latency-audio-dev --region us-east-1
```

**Expected output (if not cleaned):**
```json
{
  "LambdaFunctionConfigurations": [
    {
      "LambdaFunctionArn": "arn:aws:lambda:us-east-1:xxx:function:s3-audio-consumer-dev",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": { "Key": { "FilterRules": [{"Name": "Suffix", "Value": ".pcm"}] }}
    }
  ]
}
```

**How to remove:**
```bash
# Remove ALL event notifications
aws s3api put-bucket-notification-configuration \
  --bucket low-latency-audio-dev \
  --region us-east-1 \
  --notification-configuration '{}'

# Verify removed
aws s3api get-bucket-notification-configuration --bucket low-latency-audio-dev --region us-east-1
# Should return: {} or no LambdaFunctionConfigurations
```

---

### 5. EventBridge Rules ⚠️ CHECK CAREFULLY

**Potentially obsolete:**
- Rules that trigger `kvs-stream-consumer-dev` (if they exist)
- Rules related to KVS Stream lifecycle (not Kinesis Data Streams)

**Check for obsolete rules:**
```bash
# List all EventBridge rules
aws events list-rules --region us-east-1 --query 'Rules[*].[Name, State]' --output table

# Look for rules containing: kvs-stream-consumer, kvs-lifecycle, etc.

# Check specific rule
aws events describe-rule --name kvs-stream-consumer-trigger-dev --region us-east-1

# Check rule targets
aws events list-targets-by-rule --rule kvs-stream-consumer-trigger-dev --region us-east-1
```

**How to delete (if obsolete):**
```bash
# Remove targets first
aws events remove-targets --rule kvs-stream-consumer-trigger-dev --ids <target-id> --region us-east-1

# Then delete rule
aws events delete-rule --name kvs-stream-consumer-trigger-dev --region us-east-1
```

---

## Resources to KEEP (Still Used)

### 1. Cognito User Pool ✅ KEEP
**Why:** Still used for speaker authentication (Phase 4)

**Resource:**
- User Pool ID: From `VITE_COGNITO_USER_POOL_ID`
- Used by: Speaker app login

---

### 2. Cognito Identity Pool ⚠️ PARTIALLY USED

**Current usage in Phase 4:**
- ✅ **CloudWatch RUM monitoring** (in `monitoring.ts`) - Keep for this
- ❌ **KVS WebRTC credentials** - No longer needed

**Recommendation:** KEEP the Identity Pool for CloudWatch RUM

**What to update:**
- Remove KVSClientRole and KVSGuestRole from Identity Pool's authenticated/unauthenticated role assignments
- Keep only roles needed for CloudWatch RUM

**How to update:**
```bash
# Get current identity pool configuration
aws cognito-identity get-identity-pool-roles \
  --identity-pool-id us-east-1:your-identity-pool-id \
  --region us-east-1

# Update to remove KVS roles (replace with RUM-only roles)
aws cognito-identity set-identity-pool-roles \
  --identity-pool-id us-east-1:your-identity-pool-id \
  --region us-east-1 \
  --roles authenticated=arn:aws:iam::xxx:role/RUM-Role,unauthenticated=arn:aws:iam::xxx:role/RUM-Guest-Role
```

---

### 3. DynamoDB Tables ✅ KEEP ALL
- `sessions-dev` - Used by Phase 4
- `connections-dev` - Used by Phase 4

---

### 4. S3 Buckets ✅ KEEP ALL
- `low-latency-audio-dev` - Used by Phase 4 (though Kinesis primary, may still have temp files)
- `translation-audio-dev` - Used by Phase 4 (stores translated MP3 files)

---

### 5. Lambda Functions ✅ KEEP
Phase 4 active functions:
- `session-connection-handler-dev`
- `session-disconnect-handler-dev`
- `audio-processor`

---

### 6. Kinesis Data Stream ✅ KEEP
- `audio-ingestion-dev` - Core of Phase 4 architecture

---

### 7. API Gateway ✅ KEEP
- WebSocket API - Still used
- HTTP API - Still used

---

## Cleanup Priority

### 🔴 Priority 1: Delete After Phase 4 Testing Passes

These are completely obsolete and should be deleted once you confirm Phase 4 works:

1. ✅ CloudFormation Stack: `KVSWebRTC-dev`
2. ✅ S3 Event Notifications (trigger s3-audio-consumer)
3. ✅ Lambda Functions: kvs-stream-writer, s3-audio-consumer, kvs-stream-consumer

### 🟡 Priority 2: Clean Up After 1 Week

Give yourself time to ensure nothing breaks:

1. ⚠️ Update Cognito Identity Pool roles (remove KVS roles, keep RUM roles)
2. ⚠️ Delete obsolete EventBridge rules

### 🟢 Priority 3: Optional Cleanup

Not urgent, can be done later:

1. CloudWatch Log Groups for deleted Lambdas (will expire automatically)
2. Old S3 objects in `low-latency-audio-dev` (lifecycle policy handles this)

---

## Verification Commands

### Before Deletion:
```bash
# Export current state
aws cloudformation describe-stacks --region us-east-1 > cfn-stacks-backup.json
aws iam list-roles --query 'Roles[?contains(RoleName, `KVS`)]' > kvs-roles-backup.json
aws lambda list-functions --region us-east-1 > lambda-functions-backup.json
```

### After Deletion:
```bash
# Test Phase 4 still works
./scripts/check-deployment-health.sh

# Test speaker app
cd frontend-client-apps/speaker-app && npm run dev

# Test listener app  
cd frontend-client-apps/listener-app && npm run dev

# Monitor logs
./scripts/tail-lambda-logs.sh audio-processor
```

---

## What NOT to Delete

### ❌ DO NOT DELETE:
- Cognito User Pool (speaker authentication)
- Cognito Identity Pool itself (used by CloudWatch RUM)
- DynamoDB tables (sessions, connections)
- S3 buckets (active storage)
- API Gateway (WebSocket + HTTP)
- Any Lambda function in the "KEEP" list above
- Kinesis Data Stream (core of Phase 4)

---

## CDK Infrastructure Cleanup

After manually deleting AWS resources, clean up CDK code:

### 1. Remove KVSWebRTCStack from app.py

**File:** `session-management/infrastructure/app.py`

```python
# DELETE these lines:
from stacks.kvs_webrtc_stack import KVSWebRTCStack

kvs_webrtc_stack = KVSWebRTCStack(...)

session_management_stack.add_dependency(kvs_webrtc_stack)
```

### 2. Delete KVSWebRTCStack file

```bash
rm session-management/infrastructure/stacks/kvs_webrtc_stack.py
```

### 3. Remove Identity Pool references

**File:** `frontend-client-apps/shared/utils/config.ts`

Consider removing:
```typescript
identityPoolId?: string; // For KVS WebRTC credentials (if not using RUM)
```

---

## Estimated Cleanup Time

- **Priority 1 (Safe deletions):** 15 minutes
- **Priority 2 (Identity Pool updates):** 30 minutes
- **Priority 3 (Optional cleanup):** 15 minutes
- **CDK code cleanup:** 15 minutes

**Total:** ~1.5 hours for complete cleanup

---

## Risk Assessment

### ✅ Low Risk (Safe to Delete Now)
- KVSWebRTC CloudFormation stack
- S3 event notifications
- Lambda functions: kvs-stream-writer, s3-audio-consumer, kvs-stream-consumer

### ⚠️ Medium Risk (Test First)
- Cognito Identity Pool role assignments
- EventBridge rules

### 🔴 High Risk (DO NOT DELETE)
- Cognito User Pool
- Cognito Identity Pool itself
- DynamoDB tables
- S3 buckets
- Current Lambda functions
- Kinesis Data Stream

---

## Rollback Plan

If something breaks after deletion:

### 1. CloudFormation Stack
```bash
# Redeploy KVSWebRTCStack (if needed)
cd session-management
cdk deploy KVSWebRTC-dev
```

### 2. Lambda Functions
```bash
# Restore from git history
git show e480936:session-management/lambda/kvs_stream_writer/handler.py > handler.py
# Then redeploy via CDK
```

### 3. Identity Pool Roles
- Manually reassign roles in Cognito Console
- Use exported JSON from backup

---

## Post-Cleanup Checklist

After deleting resources, verify:

- [ ] Phase 4 speaker app still works
- [ ] Phase 4 listener app still works
- [ ] CloudWatch RUM monitoring still functional (if using Identity Pool)
- [ ] No CloudFormation stack errors
- [ ] No Lambda permission errors in logs
- [ ] End-to-end translation still works

---

## Summary

**Safe to delete immediately:**
1. CloudFormation stack: KVSWebRTC-dev
2. S3 event notifications (low-latency-audio-dev bucket)
3. Lambda functions: kvs-stream-writer-dev, s3-audio-consumer-dev, kvs-stream-consumer-dev
4. FFmpeg Lambda layer

**Keep (still used):**
- Cognito User Pool
- Cognito Identity Pool (for CloudWatch RUM)
- DynamoDB tables
- S3 buckets
- Active Lambda functions
- Kinesis Data Stream
- API Gateways

**Update (after testing):**
- Cognito Identity Pool role assignments (remove KVS roles)
- CDK infrastructure code (remove KVSWebRTCStack)

**Estimated savings:** ~$5-10/month from deleted resources
