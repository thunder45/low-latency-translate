#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Creating Listener Authentication Infrastructure${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Step 1: Create User Pool
echo -e "${YELLOW}1. Creating Listener User Pool...${NC}"
aws cognito-idp create-user-pool \
  --pool-name "low-latency-translate-listeners-dev" \
  --policies '{
    "PasswordPolicy": {
      "MinimumLength": 6,
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

LISTENER_USER_POOL_ID=$(jq -r '.UserPool.Id' /tmp/listener-user-pool.json)
echo -e "${GREEN}✅ User Pool ID: $LISTENER_USER_POOL_ID${NC}"
echo ""

# Step 2: Create App Client
echo -e "${YELLOW}2. Creating App Client...${NC}"
aws cognito-idp create-user-pool-client \
  --user-pool-id "$LISTENER_USER_POOL_ID" \
  --client-name "listener-app-client" \
  --explicit-auth-flows "ALLOW_USER_SRP_AUTH" "ALLOW_REFRESH_TOKEN_AUTH" \
  --prevent-user-existence-errors ENABLED \
  --supported-identity-providers COGNITO \
  --output json > /tmp/listener-app-client.json

LISTENER_CLIENT_ID=$(jq -r '.UserPoolClient.ClientId' /tmp/listener-app-client.json)
echo -e "${GREEN}✅ Client ID: $LISTENER_CLIENT_ID${NC}"
echo ""

# Step 3: Create Identity Pool
echo -e "${YELLOW}3. Creating Identity Pool...${NC}"
aws cognito-identity create-identity-pool \
  --identity-pool-name "ListenersIdentityPool-dev" \
  --no-allow-unauthenticated-identities \
  --cognito-identity-providers ProviderName="cognito-idp.us-east-1.amazonaws.com/$LISTENER_USER_POOL_ID",ClientId="$LISTENER_CLIENT_ID",ServerSideTokenCheck=false \
  --output json > /tmp/listener-identity-pool.json

LISTENER_IDENTITY_POOL_ID=$(jq -r '.IdentityPoolId' /tmp/listener-identity-pool.json)
echo -e "${GREEN}✅ Identity Pool ID: $LISTENER_IDENTITY_POOL_ID${NC}"
echo ""

# Step 4: Attach KVS Client Role
echo -e "${YELLOW}4. Configuring Identity Pool with KVS Client Role...${NC}"
aws cognito-identity set-identity-pool-roles \
  --identity-pool-id "$LISTENER_IDENTITY_POOL_ID" \
  --roles "authenticated=arn:aws:iam::193020606184:role/KVSWebRTC-dev-KVSClientRoleD58A328F-GNjSJXzIIbxN"

echo -e "${GREEN}✅ Identity Pool configured${NC}"
echo ""

# Step 5: Create test user
echo -e "${YELLOW}5. Creating test listener user...${NC}"
aws cognito-idp admin-create-user \
  --user-pool-id "$LISTENER_USER_POOL_ID" \
  --username "test@example.com" \
  --user-attributes Name=email,Value="test@example.com" \
  --temporary-password "Test123Abc!" \
  --message-action SUPPRESS

echo -e "${GREEN}✅ Test user created${NC}"
echo ""

# Summary
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Listener Authentication Setup Complete!${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "${GREEN}Configuration values for listener app .env:${NC}"
echo ""
echo "VITE_COGNITO_USER_POOL_ID=$LISTENER_USER_POOL_ID"
echo "VITE_COGNITO_CLIENT_ID=$LISTENER_CLIENT_ID"
echo "VITE_COGNITO_IDENTITY_POOL_ID=$LISTENER_IDENTITY_POOL_ID"
echo "VITE_COGNITO_REGION=us-east-1"
echo ""
echo -e "${GREEN}Test credentials:${NC}"
echo "Email: test@example.com"
echo "Temp Password: Test123Abc!"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Update frontend-client-apps/listener-app/.env with values above"
echo "2. Restart listener app: npm run dev"
echo "3. Open http://localhost:3001 and sign in"
echo "4. Join a session - should work with authenticated access!"
echo ""
