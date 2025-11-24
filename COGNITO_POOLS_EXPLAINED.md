# Cognito: User Pool vs Identity Pool

**Quick Answer:** You have User Pool configured ✅, but need Identity Pool ID (NEW for Phase 2).

---

## The Difference

### Cognito User Pool (Already Configured ✅)

**What it does:** **AUTHENTICATION** - Proves who you are

**Your existing config:**
```bash
VITE_COGNITO_USER_POOL_ID=us-east-1_WoaXmyQLQ  # User Pool
VITE_COGNITO_CLIENT_ID=38t8057tbi0o6873qt441kuo3n  # App Client in User Pool
```

**Usage:**
- User login (email/password)
- Issues JWT tokens
- Manages user accounts
- Used for speaker authentication

**Analogy:** Like a passport - proves who you are

---

### Cognito Identity Pool (NEW - Required for Phase 2 ❌)

**What it does:** **AUTHORIZATION** - Gives you AWS access

**Missing from your config:**
```bash
VITE_COGNITO_IDENTITY_POOL_ID=us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

**Usage:**
- Exchanges JWT → AWS temporary credentials
- Allows calling AWS services (like KVS)
- Provides IAM role permissions
- Used for accessing Kinesis Video Streams

**Analogy:** Like a security badge - grants access to buildings (AWS services)

---

## Why You Need Both

### Authentication Flow (Existing - Phase 0)
```
User → Cognito User Pool → JWT Token → Login to App
     (email/password)         ↓
                         Authenticate user
```

### Authorization Flow (NEW - Phase 2)
```
JWT Token → Cognito Identity Pool → AWS Temporary Credentials → Access KVS
           (exchange token)            ↓
                                   accessKeyId
                                   secretAccessKey
                                   sessionToken
```

---

## Current Status

### What You Have ✅
```bash
# User Pool - For Login
VITE_COGNITO_USER_POOL_ID=us-east-1_WoaXmyQLQ
VITE_COGNITO_CLIENT_ID=38t8057tbi0o6873qt441kuo3n
```

**This handles:**
- Speaker login ✅
- JWT token generation ✅
- Session authentication ✅

### What You Need ❌
```bash
# Identity Pool - For AWS Service Access
VITE_COGNITO_IDENTITY_POOL_ID=us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

**This handles:**
- Getting AWS credentials from JWT ❌
- Accessing KVS API (signaling, TURN servers) ❌
- Streaming audio to/from KVS ❌

---

## How to Get Identity Pool ID

### Option 1: Check if Already Created (Likely Yes)

Phase 1 should have created this. Check CDK outputs:

```bash
cd session-management/infrastructure
cdk outputs KVSWebRTCStack
```

**Look for:**
```
KVSWebRTCStack.CognitoIdentityPoolId = us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

If you see this, copy the ID and add to your .env files.

---

### Option 2: Check AWS Console

1. Go to AWS Console
2. Navigate to: **Cognito** → **Identity Pools** (not User Pools!)
3. Look for identity pool created by your CDK stack
4. Click on it
5. Copy the **Identity Pool ID** (format: `us-east-1:guid`)

---

### Option 3: Check via AWS CLI

```bash
aws cognito-identity list-identity-pools \
  --max-results 10 \
  --region us-east-1

# Look for IdentityPoolId in response
```

---

### Option 4: If Missing - Create via CDK

If Phase 1 CDK didn't create it, deploy KVS stack:

```bash
cd session-management/infrastructure
cdk deploy KVSWebRTCStack
```

This will create:
- Cognito Identity Pool
- IAM roles for authenticated/unauthenticated access
- Policies allowing KVS operations

---

## Complete .env Configuration

### After Finding Identity Pool ID

**frontend-client-apps/speaker-app/.env:**
```bash
# WebSocket & HTTP API
VITE_WEBSOCKET_URL=wss://xxx.execute-api.us-east-1.amazonaws.com/prod
VITE_HTTP_API_URL=https://xxx.execute-api.us-east-1.amazonaws.com
VITE_AWS_REGION=us-east-1
VITE_ENCRYPTION_KEY=your-32-character-encryption-key-here

# Cognito User Pool (Existing - Authentication)
VITE_COGNITO_USER_POOL_ID=us-east-1_WoaXmyQLQ
VITE_COGNITO_CLIENT_ID=38t8057tbi0o6873qt441kuo3n

# Cognito Identity Pool (NEW - AWS Service Access)
VITE_COGNITO_IDENTITY_POOL_ID=us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

**frontend-client-apps/listener-app/.env:**
```bash
# Same as speaker app
VITE_WEBSOCKET_URL=wss://xxx.execute-api.us-east-1.amazonaws.com/prod
VITE_HTTP_API_URL=https://xxx.execute-api.us-east-1.amazonaws.com
VITE_AWS_REGION=us-east-1
VITE_ENCRYPTION_KEY=your-32-character-encryption-key-here

# Cognito (same for both apps)
VITE_COGNITO_USER_POOL_ID=us-east-1_WoaXmyQLQ
VITE_COGNITO_CLIENT_ID=38t8057tbi0o6873qt441kuo3n
VITE_COGNITO_IDENTITY_POOL_ID=us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

---

## Technical Deep Dive

### User Pool (What You Have)

**Purpose:** User directory and authentication service

**Features:**
- User registration and login
- Password policies and MFA
- Email/phone verification
- Issues JWT tokens (ID token, access token, refresh token)

**Your Values:**
- Pool ID: `us-east-1_WoaXmyQLQ` (format: `region_alphanumeric`)
- Client ID: `38t8057tbi0o6873qt441kuo3n` (format: `alphanumeric`)

**Used in Phase 2:**
- Speaker login
- JWT token for API authentication
- Source of identity for Identity Pool

---

### Identity Pool (What You Need)

**Purpose:** AWS credentials provider for federated identities

**Features:**
- Exchanges authentication tokens for AWS credentials
- Supports multiple auth providers (Cognito, Google, Facebook, etc.)
- Returns temporary AWS credentials (accessKeyId, secretKey, sessionToken)
- Associates with IAM roles for permissions

**Format:** `us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` (region:guid)

**Used in Phase 2:**
- Converting JWT → AWS credentials
- Accessing KVS API (GetIceServerConfig, etc.)
- Calling KVS signaling operations
- Both speaker AND listener need this

---

## How They Work Together (Phase 2)

### Speaker Flow:
```
1. User enters email/password
2. User Pool authenticates → JWT token
3. JWT token used for HTTP/WebSocket API (existing)
4. JWT token → Identity Pool → AWS credentials (NEW)
5. AWS credentials → KVS API access
6. KVS API returns STUN/TURN servers
7. WebRTC connects using STUN/TURN
```

### Listener Flow:
```
1. No login required (anonymous)
2. Identity Pool generates anonymous credentials
3. Anonymous credentials → KVS API access
4. KVS API returns STUN/TURN servers
5. WebRTC connects as viewer
```

---

## Why Phase 2 Needs Identity Pool

### Before Phase 2 (WebSocket Only):
- User Pool JWT was enough
- All communication via API Gateway
- No direct AWS service access needed

### After Phase 2 (WebRTC + KVS):
- Need to call KVS APIs directly from browser
- Browser can't use JWT for AWS APIs
- Identity Pool converts JWT → AWS credentials
- AWS credentials allow KVS API calls

---

## Security Model

### User Pool Security:
- Protects user accounts
- Validates passwords
- Issues time-limited JWT tokens
- Tokens expire after 1 hour

### Identity Pool Security:
- Trusts User Pool JWTs
- Issues time-limited AWS credentials
- Credentials expire after 1 hour
- IAM roles limit what credentials can access
- Only allows KVS operations (not other AWS services)

**Both are secure** - different purposes, different security boundaries.

---

## Quick Commands

### Find Your Identity Pool ID:

**Method 1 - CDK Output:**
```bash
cd session-management/infrastructure
cdk outputs KVSWebRTCStack | grep IdentityPoolId
```

**Method 2 - AWS CLI:**
```bash
aws cognito-identity list-identity-pools --max-results 10 --region us-east-1 \
  | jq '.IdentityPools[] | {IdentityPoolId, IdentityPoolName}'
```

**Method 3 - AWS Console:**
- Go to: https://console.aws.amazon.com/cognito/
- Click "Identity Pools" (NOT "User Pools")
- Find your pool
- Copy the ID

---

## Summary

**Existing Config (User Pool):**
```bash
VITE_COGNITO_USER_POOL_ID=us-east-1_WoaXmyQLQ      # ✅ Have this
VITE_COGNITO_CLIENT_ID=38t8057tbi0o6873qt441kuo3n  # ✅ Have this
```
→ Used for: Login, authentication, JWT tokens

**New Config Needed (Identity Pool):**
```bash
VITE_COGNITO_IDENTITY_POOL_ID=us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx  # ❌ Need this
```
→ Used for: AWS credentials, KVS API access, WebRTC

**Action Required:**
1. Find your Identity Pool ID (likely created in Phase 1)
2. Add to both .env files
3. Rebuild and test

**Time to Fix:** 5 minutes (just add one line to two files)
