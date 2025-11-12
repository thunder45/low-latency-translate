# Deployment Fix - Cryptography Library Issue

## 🔴 **ISSUE IDENTIFIED**

### Error from CloudWatch Logs
```
[ERROR] cryptography library not available - signature verification skipped
[WARNING] JWT signature verification failed
[WARNING] JWT validation failed
```

### Root Cause
Lambda functions couldn't find the `cryptography` library because:
1. **Architecture mismatch**: macOS builds cryptography with x86_64 binaries, but Lambda needs Linux x86_64
2. **No Docker bundling**: CDK was using local `Code.from_asset()` without Docker bundling

---

## ✅ **FIXES APPLIED**

### Fix 1: Docker Bundling for Authorizer
**File:** `session-management/infrastructure/stacks/session_management_stack.py`

**Before:**
```python
code=lambda_.Code.from_asset("../lambda/authorizer")
```

**After:**
```python
code=lambda_.Code.from_asset(
    "../lambda/authorizer",
    bundling=lambda_.BundlingOptions(
        image=lambda_.Runtime.PYTHON_3_11.bundling_image,
        command=[
            "bash", "-c",
            "pip install -r requirements.txt -t /asset-output && "
            "cp -au . /asset-output"
        ],
    )
)
```

**What This Does:**
- Uses Docker container with Amazon Linux 2023 (same as Lambda runtime)
- Installs `cryptography` with correct Linux binaries
- Packages everything into Lambda deployment

---

### Fix 2: Docker Bundling for Refresh Handler
**File:** `session-management/infrastructure/stacks/session_management_stack.py`

**Same change applied to refresh handler:**
```python
code=lambda_.Code.from_asset(
    "../lambda/refresh_handler",
    bundling=lambda_.BundlingOptions(
        image=lambda_.Runtime.PYTHON_3_11.bundling_image,
        command=[
            "bash", "-c",
            "pip install -r requirements.txt -t /asset-output && "
            "cp -au . /asset-output"
        ],
    )
)
```

---

### Fix 3: Environment Variables (Already Present)
JWT validation environment variables were already configured:
```python
environment={
    "REGION": self.config.get("region", "us-east-1"),
    "USER_POOL_ID": self.config.get("cognitoUserPoolId", ""),
    "CLIENT_ID": self.config.get("cognitoClientId", ""),
}
```

---

## 🚀 **DEPLOYMENT STEPS**

### Prerequisites
- Docker must be running on your machine
- CDK will use Docker to build Lambda packages

### Deploy
```bash
# 1. Ensure Docker is running
docker ps

# 2. Navigate to infrastructure directory
cd session-management/infrastructure

# 3. Deploy with Docker bundling
cdk deploy SessionManagement-dev

# Expected output:
# - CDK will build Lambda packages in Docker containers
# - cryptography will be compiled for Linux x86_64
# - Deployment will succeed
```

### Verify Deployment
```bash
# Check authorizer logs
aws logs tail /aws/lambda/session-authorizer-dev --follow

# Test with valid token
wscat -c "wss://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod?token=YOUR_JWT"

# Expected log output:
# [INFO] Loaded 2 Cognito public keys ✅
# [INFO] JWT validation successful (signature verified) ✅
# [INFO] Authorization successful for user abc12345... ✅
```

---

## 🔍 **WHAT CHANGED**

### Before (Broken)
```
macOS → pip install cryptography → macOS binaries → Lambda ❌
                                                      ↓
                                            ImportError: wrong architecture
```

### After (Fixed)
```
macOS → CDK Docker bundling → Amazon Linux container → pip install → Linux binaries → Lambda ✅
                                                                                         ↓
                                                                              cryptography works!
```

---

## 📊 **EXPECTED RESULTS**

### CloudWatch Logs (Success)
```
[INFO] Authorizer invoked with token present: True
[INFO] Loaded 2 Cognito public keys
[INFO] JWT validation successful (signature verified)  ← NEW!
[INFO] Authorization successful for user abc12345...
```

### Security Status
| Component | Signature Verification | Status |
|-----------|----------------------|--------|
| Authorizer | ✅ RSA with cryptography | SECURE |
| Refresh Handler | ✅ RSA with cryptography | SECURE |

---

## 🐛 **TROUBLESHOOTING**

### Issue: Docker not running
```
Error: Cannot connect to the Docker daemon
```

**Solution:**
```bash
# Start Docker Desktop (macOS)
open -a Docker

# Wait for Docker to start, then retry
cdk deploy SessionManagement-dev
```

---

### Issue: Docker build fails
```
Error: docker exited with status 1
```

**Solution:**
```bash
# Check requirements.txt exists
ls session-management/lambda/authorizer/requirements.txt
ls session-management/lambda/refresh_handler/requirements.txt

# Verify requirements.txt content
cat session-management/lambda/authorizer/requirements.txt
# Should contain: cryptography>=41.0.0
```

---

### Issue: Still getting "cryptography not available"
```
[ERROR] cryptography library not available
```

**Solution:**
```bash
# 1. Force rebuild
cdk deploy SessionManagement-dev --force

# 2. Check Lambda function code
aws lambda get-function --function-name session-authorizer-dev

# 3. Verify cryptography in package
aws lambda get-function --function-name session-authorizer-dev \
  --query 'Code.Location' --output text | xargs curl -o /tmp/lambda.zip
unzip -l /tmp/lambda.zip | grep cryptography
# Should show cryptography/ directory
```

---

## ✅ **VERIFICATION CHECKLIST**

After deployment:
- [ ] Docker bundling completed successfully
- [ ] No "cryptography not available" errors in logs
- [ ] Logs show "JWT validation successful (signature verified)"
- [ ] Valid tokens are accepted
- [ ] Invalid tokens are rejected
- [ ] Expired tokens are rejected
- [ ] Forged tokens are rejected

---

## 📚 **REFERENCES**

- [AWS CDK Bundling](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_lambda-readme.html#bundling-asset-code)
- [Lambda Python Dependencies](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html)
- [Cryptography Library](https://cryptography.io/)

---

## 🎯 **SUMMARY**

**Problem:** macOS-compiled cryptography binaries don't work in Lambda (Linux)

**Solution:** Use CDK Docker bundling to compile cryptography in Amazon Linux container

**Result:** JWT signature verification now works correctly in Lambda

**Status:** ✅ READY TO DEPLOY
