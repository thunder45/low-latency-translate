#!/bin/bash
# Create dedicated IAM role for listener authentication
# This role is specifically for listeners to access KVS as viewers

set -e

echo "================================================"
echo "Creating Listener IAM Role"
echo "================================================"
echo ""

# Configuration
ROLE_NAME="KVSWebRTC-dev-KVSListenerRole"
LISTENER_IDENTITY_POOL_ID="us-east-1:8e81542d-4b76-4b2e-966d-998939e67a23"
TRUST_POLICY_FILE="tmp/listener-role-trust-policy.json"
PERMISSIONS_POLICY_FILE="tmp/listener-role-permissions-policy.json"

# Step 1: Create IAM role with trust policy
echo "1. Creating IAM role: $ROLE_NAME"
aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document file://"$TRUST_POLICY_FILE" \
  --description "KVS viewer role for authenticated listeners" \
  --output json > /tmp/listener-role-output.json

ROLE_ARN=$(jq -r '.Role.Arn' /tmp/listener-role-output.json)
echo "✅ Role created: $ROLE_ARN"
echo ""

# Step 2: Create inline policy with KVS viewer permissions
echo "2. Attaching KVS viewer permissions policy..."
aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "KVSViewerPermissions" \
  --policy-document file://"$PERMISSIONS_POLICY_FILE"

echo "✅ Permissions attached"
echo ""

# Step 3: Associate role with listener Identity Pool
echo "3. Configuring Identity Pool to use new role..."
aws cognito-identity set-identity-pool-roles \
  --identity-pool-id "$LISTENER_IDENTITY_POOL_ID" \
  --roles "authenticated=$ROLE_ARN"

echo "✅ Identity Pool configured"
echo ""

# Step 4: Verify configuration
echo "4. Verifying configuration..."
aws cognito-identity get-identity-pool-roles \
  --identity-pool-id "$LISTENER_IDENTITY_POOL_ID" \
  --output json > /tmp/listener-pool-roles-verify.json

VERIFIED_ROLE=$(jq -r '.Roles.authenticated' /tmp/listener-pool-roles-verify.json)
echo "Verified authenticated role: $VERIFIED_ROLE"
echo ""

# Summary
echo "================================================"
echo "Listener IAM Role Setup Complete!"
echo "================================================"
echo ""
echo "Role ARN: $ROLE_ARN"
echo "Identity Pool: $LISTENER_IDENTITY_POOL_ID"
echo ""
echo "The listener app now has a dedicated IAM role for KVS access."
echo ""
echo "Next steps:"
echo "1. Wait 10-15 seconds for IAM propagation"
echo "2. Test listener app authentication at http://localhost:5174"
echo "3. Login with: advm@advm.lu"
echo "4. Join a speaker session"
echo "5. Verify audio playback works"
echo ""
