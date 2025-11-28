#!/bin/bash
# ================================================================================
# Debug Listener Credentials and Permissions
# ================================================================================
# 
# This script simulates what the listener browser does and tests each step
#
# ================================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

IDENTITY_POOL_ID="us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4"
CHANNEL_ARN="arn:aws:kinesisvideo:us-east-1:193020606184:channel/session-peaceful-temple-109/1764083660586"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Debugging Listener Credentials${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Step 1: Get Identity ID (simulating browser)
echo -e "${YELLOW}Step 1: Getting Identity ID from Cognito...${NC}"
IDENTITY_ID=$(aws cognito-identity get-id \
  --identity-pool-id "$IDENTITY_POOL_ID" \
  --query 'IdentityId' \
  --output text)

if [ -z "$IDENTITY_ID" ]; then
    echo -e "${RED}❌ Failed to get identity ID${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Identity ID: $IDENTITY_ID${NC}"
echo ""

# Step 2: Get credentials for identity
echo -e "${YELLOW}Step 2: Getting credentials for identity...${NC}"
CREDS=$(aws cognito-identity get-credentials-for-identity \
  --identity-id "$IDENTITY_ID" \
  --output json)

ACCESS_KEY=$(echo "$CREDS" | jq -r '.Credentials.AccessKeyId')
SECRET_KEY=$(echo "$CREDS" | jq -r '.Credentials.SecretKey')
SESSION_TOKEN=$(echo "$CREDS" | jq -r '.Credentials.SessionToken')
EXPIRATION=$(echo "$CREDS" | jq -r '.Credentials.Expiration')

if [ -z "$ACCESS_KEY" ]; then
    echo -e "${RED}❌ Failed to get credentials${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Credentials obtained${NC}"
echo "Access Key: ${ACCESS_KEY:0:20}..."
echo "Expiration: $EXPIRATION"
echo ""

# Step 3: Check which role was assumed
echo -e "${YELLOW}Step 3: Checking assumed role...${NC}"
CALLER_IDENTITY=$(AWS_ACCESS_KEY_ID="$ACCESS_KEY" \
  AWS_SECRET_ACCESS_KEY="$SECRET_KEY" \
  AWS_SESSION_TOKEN="$SESSION_TOKEN" \
  aws sts get-caller-identity --output json)

echo "$CALLER_IDENTITY" | jq '.'
ASSUMED_ROLE=$(echo "$CALLER_IDENTITY" | jq -r '.Arn')
echo ""

if [[ "$ASSUMED_ROLE" == *"KVSGuestRole"* ]]; then
    echo -e "${GREEN}✅ Correctly assumed Guest Role${NC}"
else
    echo -e "${RED}❌ Wrong role assumed: $ASSUMED_ROLE${NC}"
fi
echo ""

# Step 4: Test KVS GetSignalingChannelEndpoint with these credentials
echo -e "${YELLOW}Step 4: Testing KVS GetSignalingChannelEndpoint...${NC}"
echo "Testing on channel: $CHANNEL_ARN"
echo ""

# Disable exit on error for this test
set +e
KVS_RESULT=$(AWS_ACCESS_KEY_ID="$ACCESS_KEY" \
  AWS_SECRET_ACCESS_KEY="$SECRET_KEY" \
  AWS_SESSION_TOKEN="$SESSION_TOKEN" \
  aws kinesisvideo get-signaling-channel-endpoint \
  --channel-arn "$CHANNEL_ARN" \
  --single-master-channel-endpoint-configuration Protocols=WSS,HTTPS,Role=VIEWER \
  --output json 2>&1)
KVS_EXIT_CODE=$?
set -e

echo "Exit code: $KVS_EXIT_CODE"
echo ""

if [ $KVS_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ SUCCESS! KVS call worked${NC}"
    echo "$KVS_RESULT" | jq '.ResourceEndpointList'
elif echo "$KVS_RESULT" | grep -q "AccessDeniedException"; then
    echo -e "${RED}❌ AccessDeniedException - Permission denied${NC}"
    echo "$KVS_RESULT"
    echo ""
    echo -e "${RED}The IAM permission is not working. Investigating...${NC}"
    echo ""
    
    # Check the exact policy
    echo -e "${YELLOW}Current policy on guest role:${NC}"
    aws iam get-role-policy \
      --role-name KVSWebRTC-dev-KVSGuestRoleB2D31EDC-WLWmKOrefMQt \
      --policy-name KVSGuestRoleDefaultPolicyE9CC46BC \
      --output json | jq '.PolicyDocument'
    
    echo ""
    echo -e "${YELLOW}Checking if resource pattern matches:${NC}"
    echo "Policy resource: arn:aws:kinesisvideo:us-east-1:193020606184:channel/session-*/*"
    echo "Actual channel:  $CHANNEL_ARN"
    
    # Test if pattern matching works
    if [[ "$CHANNEL_ARN" == arn:aws:kinesisvideo:us-east-1:193020606184:channel/session-*/* ]]; then
        echo -e "${GREEN}Pattern SHOULD match${NC}"
    else
        echo -e "${RED}Pattern DOES NOT match${NC}"
    fi
    
else
    echo -e "${YELLOW}⚠️  Unexpected response (exit code: $KVS_EXIT_CODE):${NC}"
    echo "$KVS_RESULT"
fi

echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Analysis${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Check if IAM policies need time to propagate
echo "If AccessDeniedException occurred:"
echo "1. IAM policies can take 5-10 minutes to fully propagate"
echo "2. Try waiting 10 minutes and run this script again"
echo "3. Check for any AWS Organizations SCPs that might block KVS"
echo "4. Verify the channel exists: aws kinesisvideo describe-signaling-channel --channel-arn \"$CHANNEL_ARN\""
echo ""
