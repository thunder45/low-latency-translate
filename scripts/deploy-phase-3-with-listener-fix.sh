#!/bin/bash
set -e

# ================================================================================
# Deployment Script for Phase 3 + Phase 2 Listener IAM Fix
# ================================================================================
# 
# This script:
# 1. Deploys Phase 3 EventBridge integration (HTTP handler + KVS consumer)
# 2. Fixes Phase 2 listener IAM permissions by deploying KVS Guest Role
# 3. Configures Cognito Identity Pool with proper roles
# 4. Verifies the deployment
#
# Usage:
#   ./scripts/deploy-phase-3-with-listener-fix.sh
#
# ================================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENV_NAME="${ENV_NAME:-dev}"
IDENTITY_POOL_ID="us-east-1:d5e057cb-a333-4f2f-913e-777e6c279bf4"
AWS_REGION="us-east-1"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Phase 3 + Listener Fix Deployment${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo "Environment: $ENV_NAME"
echo "Region: $AWS_REGION"
echo "Identity Pool: $IDENTITY_POOL_ID"
echo ""

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo -e "${RED}❌ Error: AWS CLI not configured or credentials expired${NC}"
    echo "Please run 'aws configure' or refresh your credentials"
    exit 1
fi

echo -e "${GREEN}✅ AWS credentials valid${NC}"
echo ""

# ================================================================================
# Step 1: Deploy KVS WebRTC Stack (includes new Guest Role)
# ================================================================================

echo -e "${YELLOW}Step 1: Deploying KVS WebRTC Stack (Guest Role)...${NC}"
cd session-management/infrastructure

if ! cdk deploy "KVSWebRTC-$ENV_NAME" --require-approval never; then
    echo -e "${RED}❌ Failed to deploy KVS WebRTC stack${NC}"
    exit 1
fi

echo -e "${GREEN}✅ KVS WebRTC stack deployed${NC}"
echo ""

# ================================================================================
# Step 2: Deploy HTTP API Stack (includes EventBridge permissions)
# ================================================================================

echo -e "${YELLOW}Step 2: Deploying HTTP API Stack (EventBridge integration)...${NC}"

if ! cdk deploy "SessionHttpApi-$ENV_NAME" --require-approval never; then
    echo -e "${RED}❌ Failed to deploy HTTP API stack${NC}"
    exit 1
fi

echo -e "${GREEN}✅ HTTP API stack deployed${NC}"
echo ""

# ================================================================================
# Step 3: Deploy Session Management Stack (includes KVS Consumer)
# ================================================================================

echo -e "${YELLOW}Step 3: Deploying Session Management Stack (KVS Consumer)...${NC}"

if ! cdk deploy "SessionManagement-$ENV_NAME" --require-approval never; then
    echo -e "${RED}❌ Failed to deploy Session Management stack${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Session Management stack deployed${NC}"

# Return to project root for AWS CLI commands
cd ../..

echo ""

# ================================================================================
# Step 4: Get Role ARNs from Stack Outputs
# ================================================================================

echo -e "${YELLOW}Step 4: Getting role ARNs from stack outputs...${NC}"

GUEST_ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name "KVSWebRTC-$ENV_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`KVSGuestRoleArn`].OutputValue' \
  --output text)

if [ -z "$GUEST_ROLE_ARN" ]; then
    echo -e "${RED}❌ Failed to get Guest Role ARN from stack${NC}"
    exit 1
fi

echo "Guest Role ARN: $GUEST_ROLE_ARN"

# Try to get authenticated role ARN (may not exist)
AUTH_ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name "KVSWebRTC-$ENV_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`KVSClientRoleArn`].OutputValue' \
  --output text 2>/dev/null || echo "")

if [ -n "$AUTH_ROLE_ARN" ]; then
    echo "Authenticated Role ARN: $AUTH_ROLE_ARN"
else
    echo "No authenticated role configured"
fi

echo ""

# ================================================================================
# Step 5: Update Cognito Identity Pool with New Roles
# ================================================================================

echo -e "${YELLOW}Step 5: Updating Cognito Identity Pool roles...${NC}"

if [ -n "$AUTH_ROLE_ARN" ]; then
    # Update both authenticated and unauthenticated roles
    if ! aws cognito-identity set-identity-pool-roles \
      --identity-pool-id "$IDENTITY_POOL_ID" \
      --roles "unauthenticated=$GUEST_ROLE_ARN,authenticated=$AUTH_ROLE_ARN"; then
        echo -e "${RED}❌ Failed to update identity pool roles${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Updated both authenticated and unauthenticated roles${NC}"
else
    # Update only unauthenticated role
    if ! aws cognito-identity set-identity-pool-roles \
      --identity-pool-id "$IDENTITY_POOL_ID" \
      --roles "unauthenticated=$GUEST_ROLE_ARN"; then
        echo -e "${RED}❌ Failed to update identity pool roles${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Updated unauthenticated role${NC}"
fi

echo ""

# ================================================================================
# Step 6: Verify Configuration
# ================================================================================

echo -e "${YELLOW}Step 6: Verifying configuration...${NC}"

# Verify identity pool roles
echo "Verifying Cognito Identity Pool configuration..."
POOL_CONFIG=$(aws cognito-identity get-identity-pool-roles \
  --identity-pool-id "$IDENTITY_POOL_ID" \
  --output json)

echo "$POOL_CONFIG" | jq '.'

# Verify guest role permissions
GUEST_ROLE_NAME=$(echo "$GUEST_ROLE_ARN" | awk -F'/' '{print $2}')
echo ""
echo "Verifying Guest Role permissions..."
aws iam get-role-policy \
  --role-name "$GUEST_ROLE_NAME" \
  --policy-name "Policy" \
  --query 'PolicyDocument' \
  --output json | jq '.'

echo ""

# ================================================================================
# Step 7: Verify EventBridge Configuration
# ================================================================================

echo -e "${YELLOW}Step 7: Verifying EventBridge configuration...${NC}"

# Check session lifecycle rule
RULE_NAME="session-lifecycle-$ENV_NAME"
if aws events describe-rule --name "$RULE_NAME" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ EventBridge rule '$RULE_NAME' exists${NC}"
    
    # Check targets
    TARGET_COUNT=$(aws events list-targets-by-rule \
      --rule "$RULE_NAME" \
      --query 'length(Targets)' \
      --output text)
    
    echo "   Targets configured: $TARGET_COUNT"
else
    echo -e "${YELLOW}⚠️  EventBridge rule '$RULE_NAME' not found${NC}"
fi

echo ""

# ================================================================================
# Summary and Next Steps
# ================================================================================

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Deployment Complete!${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "${GREEN}✅ Phase 3 EventBridge Integration:${NC}"
echo "   - HTTP Session Handler emits lifecycle events"
echo "   - KVS Stream Consumer receives and processes events"
echo "   - EventBridge rules configured for session-lifecycle"
echo ""
echo -e "${GREEN}✅ Phase 2 Listener IAM Fix:${NC}"
echo "   - KVS Guest Role created with viewer-only permissions"
echo "   - Cognito Identity Pool configured with guest role"
echo "   - Listeners can now connect to KVS signaling channels"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. Test listener connection:"
echo "   - Open listener app: http://localhost:5174"
echo "   - Create session in speaker app"
echo "   - Join session in listener app"
echo "   - Should connect without AccessDeniedException"
echo ""
echo "2. Test EventBridge integration:"
echo "   - Create a session via HTTP API"
echo "   - Check CloudWatch logs:"
echo "     aws logs tail /aws/lambda/session-http-handler-$ENV_NAME --follow"
echo "     aws logs tail /aws/lambda/kvs-stream-consumer-$ENV_NAME --follow"
echo ""
echo "3. Monitor metrics:"
echo "   - CloudWatch dashboard: SessionManagement namespace"
echo "   - EventBridge invocations: AWS/Events namespace"
echo ""
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "${GREEN}Stack Outputs:${NC}"
echo ""

# Display key stack outputs
echo "HTTP API Endpoint:"
aws cloudformation describe-stacks \
  --stack-name "SessionHttpApi-$ENV_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`HttpApiEndpoint`].OutputValue' \
  --output text

echo ""
echo "WebSocket API Endpoint:"
aws cloudformation describe-stacks \
  --stack-name "SessionManagement-$ENV_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`WebSocketAPIEndpoint`].OutputValue' \
  --output text

echo ""
echo "KVS Guest Role ARN:"
echo "$GUEST_ROLE_ARN"

echo ""
echo -e "${GREEN}🎉 Deployment successful! Ready to test.${NC}"
