# Listener Authentication Setup Guide

## Overview

Moving from unauthenticated to authenticated listeners by creating a separate Cognito User Pool for listeners.

## Architecture

```
Speakers:
  → Cognito User Pool: us-east-1_WoaXmyQLQ (existing)
  → IAM Role: KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN
  → Permissions: Full master + viewer

Listeners:
  → Cognito User Pool: [NEW - to be created]
  → Identity Pool: [NEW - separate from speakers]
  → IAM Role: KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN (viewer-only usage)
  → Permissions: Viewer access to KVS channels
```

## Step 1: Create Listener Cognito User Pool

```bash
# Create user pool for listeners
aws cognito-idp create-user-pool \
  --pool-name "low-latency-translate-listeners-dev" \
  --policies '{
    "PasswordPolicy": {
      "MinimumLength": 8,
      "RequireUppercase": false,
      "RequireLowercase": false,
      "RequireNumbers": false,
      "RequireSymbols": false
    }
  }' \
  --auto-verified-attributes email \
  --username-attributes email \
  --account-recovery-setting '{
    "RecoveryMechanisms": [
      {"Name": "verified_email", "Priority": 1}
    ]
  }' \
  --output json > /tmp/listener-user-pool.json

# Extract user pool ID
LISTENER_USER_POOL_ID=$(jq -r '.UserPool.Id' /tmp/listener-user-pool.json)
echo "Listener User Pool ID: $LISTENER_USER_POOL_ID"
```

## Step 2: Create User Pool Client

```bash
# Create app client for listener app
aws cognito-idp create-user-pool-client \
  --user-pool-id "$LISTENER_USER_POOL_ID" \
  --client-name "listener-app-client" \
  --explicit-auth-flows "ALLOW_USER_SRP_AUTH" "ALLOW_REFRESH_TOKEN_AUTH" \
  --prevent-user-existence-errors ENABLED \
  --supported-identity-providers COGNITO \
  --output json > /tmp/listener-app-client.json

# Extract client ID
LISTENER_CLIENT_ID=$(jq -r '.UserPoolClient.ClientId' /tmp/listener-app-client.json)
echo "Listener Client ID: $LISTENER_CLIENT_ID"
```

## Step 3: Create Listener Identity Pool

```bash
# Create identity pool for listeners
aws cognito-identity create-identity-pool \
  --identity-pool-name "ListenersIdentityPool-dev" \
  --allow-unauthenticated-identities false \
  --cognito-identity-providers \
    ProviderName="cognito-idp.us-east-1.amazonaws.com/$LISTENER_USER_POOL_ID",ClientId="$LISTENER_CLIENT_ID",ServerSideTokenCheck=true \
  --output json > /tmp/listener-identity-pool.json

# Extract identity pool ID
LISTENER_IDENTITY_POOL_ID=$(jq -r '.IdentityPoolId' /tmp/listener-identity-pool.json)
echo "Listener Identity Pool ID: $LISTENER_IDENTITY_POOL_ID"
```

## Step 4: Attach IAM Role to Listener Identity Pool

Use the **existing authenticated KVS Client Role** (which has been verified to work):

```bash
# Configure identity pool to use existing KVS Client Role for authenticated users
aws cognito-identity set-identity-pool-roles \
  --identity-pool-id "$LISTENER_IDENTITY_POOL_ID" \
  --roles "authenticated=arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN"

# Verify configuration
aws cognito-identity get-identity-pool-roles \
  --identity-pool-id "$LISTENER_IDENTITY_POOL_ID"
```

## Step 5: Update Listener App Configuration

Update `frontend-client-apps/listener-app/.env`:

```env
# Cognito User Pool for listeners
VITE_COGNITO_USER_POOL_ID=<LISTENER_USER_POOL_ID from Step 1>
VITE_COGNITO_CLIENT_ID=<LISTENER_CLIENT_ID from Step 2>
VITE_COGNITO_REGION=us-east-1

# Cognito Identity Pool for KVS credentials
VITE_COGNITO_IDENTITY_POOL_ID=<LISTENER_IDENTITY_POOL_ID from Step 3>

# Keep existing config
VITE_WEBSOCKET_URL=wss://mji0q10vm1.execute-api.us-east-1.amazonaws.com/prod
VITE_HTTP_API_URL=https://sj1yqxts79.execute-api.us-east-1.amazonaws.com
VITE_SESSION_ID=
```

## Step 6: Update Configuration File

Update `session-management/infrastructure/config/dev.json`:

```json
{
  "account": "193020606184",
  "region": "us-east-1",
  "cognitoUserPoolId": "us-east-1_WoaXmyQLQ",
  "cognitoClientId": "38t8057tbi0o6873qt441kuo3n",
  "cognito_identity_pool_id": "us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4",
  "listenerCognitoUserPoolId": "<LISTENER_USER_POOL_ID>",
  "listenerCognitoClientId": "<LISTENER_CLIENT_ID>",
  "listenerIdentityPoolId": "<LISTENER_IDENTITY_POOL_ID>",
  "...": "... other config ..."
}
```

## Step 7: Create Test Listener User

```bash
# Create a test listener user
aws cognito-idp admin-create-user \
  --user-pool-id "$LISTENER_USER_POOL_ID" \
  --username "test-listener@example.com" \
  --user-attributes Name=email,Value="test-listener@example.com" \
  --temporary-password "TempPass123!" \
  --message-action SUPPRESS

echo "Test user created: test-listener@example.com / TempPass123!"
```

## Step 8: Test Listener Authentication

1. **Open listener app:** http://localhost:5174
2. **Sign in** with test-listener@example.com / TempPass123!
3. **Change password** when prompted
4. **Join session** - should now work with authenticated credentials!

## Complete Setup Script

Save as `scripts/setup-listener-authentication.sh`:

```bash
#!/bin/bash
set -e

echo "Creating Listener Authentication Infrastructure..."

# Step 1: Create User Pool
echo "1. Creating Listener User Pool..."
aws cognito-idp create-user-pool \
  --pool-name "low-latency-translate-listeners-dev" \
  --policies '{
    "PasswordPolicy": {
      "MinimumLength": 8,
      "RequireUppercase": false,
      "RequireLowercase": false,
      "RequireNumbers": false,
      "RequireSymbols": false
    }
  }' \
  --auto-verified-attributes email \
  --username-attributes email \
  --output json > /tmp/listener-user-pool.json

LISTENER_USER_POOL_ID=$(jq -r '.UserPool.Id' /tmp/listener-user-pool.json)
echo "✅ User Pool ID: $LISTENER_USER_POOL_ID"

# Step 2: Create App Client
echo "2. Creating App Client..."
aws cognito-idp create-user-pool-client \
  --user-pool-id "$LISTENER_USER_POOL_ID" \
  --client-name "listener-app-client" \
  --explicit-auth-flows "ALLOW_USER_SRP_AUTH" "ALLOW_REFRESH_TOKEN_AUTH" \
  --prevent-user-existence-errors ENABLED \
  --output json > /tmp/listener-app-client.json

LISTENER_CLIENT_ID=$(jq -r '.UserPoolClient.ClientId' /tmp/listener-app-client.json)
echo "✅ Client ID: $LISTENER_CLIENT_ID"

# Step 3: Create Identity Pool
echo "3. Creating Identity Pool..."
aws cognito-identity create-identity-pool \
  --identity-pool-name "ListenersIdentityPool-dev" \
  --allow-unauthenticated-identities false \
  --cognito-identity-providers \
    ProviderName="cognito-idp.us-east-1.amazonaws.com/$LISTENER_USER_POOL_ID",ClientId="$LISTENER_CLIENT_ID",ServerSideTokenCheck=true \
  --output json > /tmp/listener-identity-pool.json

LISTENER_IDENTITY_POOL_ID=$(jq -r '.IdentityPoolId' /tmp/listener-identity-pool.json)
echo "✅ Identity Pool ID: $LISTENER_IDENTITY_POOL_ID"

# Step 4: Attach KVS Client Role
echo "4. Configuring Identity Pool with KVS Client Role..."
aws cognito-identity set-identity-pool-roles \
  --identity-pool-id "$LISTENER_IDENTITY_POOL_ID" \
  --roles "authenticated=arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN"

echo "✅ Identity Pool configured"

# Step 5: Create test user
echo "5. Creating test listener user..."
aws cognito-idp admin-create-user \
  --user-pool-id "$LISTENER_USER_POOL_ID" \
  --username "test-listener@example.com" \
  --user-attributes Name=email,Value="test-listener@example.com" \
  --temporary-password "TempPass123!" \
  --message-action SUPPRESS

echo "✅ Test user created"

# Summary
echo ""
echo "================================================"
echo "Listener Authentication Setup Complete!"
echo "================================================"
echo ""
echo "Configuration values for listener app .env:"
echo ""
echo "VITE_COGNITO_USER_POOL_ID=$LISTENER_USER_POOL_ID"
echo "VITE_COGNITO_CLIENT_ID=$LISTENER_CLIENT_ID"
echo "VITE_COGNITO_IDENTITY_POOL_ID=$LISTENER_IDENTITY_POOL_ID"
echo "VITE_COGNITO_REGION=us-east-1"
echo ""
echo "Test credentials:"
echo "Email: test-listener@example.com"
echo "Temp Password: TempPass123!"
echo ""
echo "Next: Update frontend-client-apps/listener-app/.env with these values"
```

Make executable and run:
```bash
chmod +x scripts/setup-listener-authentication.sh
./scripts/setup-listener-authentication.sh
```

## Frontend Changes Needed

The listener app already has authentication UI from the speaker app pattern. You just need to:

1. **Update .env** with new Cognito IDs
2. **Ensure authentication flow enabled** in the app
3. **Test sign-in flow** before joining sessions

## Benefits of This Approach

✅ **Works immediately** - No waiting for IAM propagation  
✅ **Uses proven authenticated role** - Already works for speakers  
✅ **Separate user pools** - Clean separation of concerns  
✅ **Can track listeners** - Know who's listening to sessions  
✅ **Can implement listener quotas** - Control access programmatically  

## Rollback Plan

If you later solve the unauthenticated access issue:
1. Keep the authenticated listener pool for premium/tracked listeners
2. Re-enable unauthenticated for anonymous listeners
3. Have two listener modes: anonymous and authenticated

## Next Steps

1. Run the setup script above
2. Update listener app `.env` with new Cognito IDs
3. Test listener authentication and KVS access
4. Once working, document as the official listener auth approach
5. Continue with Phase 3 EventBridge testing
