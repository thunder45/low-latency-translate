#!/bin/bash
#
# Verify HTTP API Deployment
#
# This script verifies that the HTTP API is deployed and functioning correctly.
# It tests all endpoints and validates JWT authentication.
#

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
API_ENDPOINT="${HTTP_API_ENDPOINT:-https://a4zdtiok36.execute-api.us-east-1.amazonaws.com}"
USER_POOL_ID="${COGNITO_USER_POOL_ID:-us-east-1_WoaXmyQLQ}"
CLIENT_ID="${COGNITO_CLIENT_ID:-38t8057tbi0o6873qt441kuo3n}"
REGION="${AWS_REGION:-us-east-1}"

echo "========================================="
echo "HTTP API Verification Script"
echo "========================================="
echo ""
echo "API Endpoint: $API_ENDPOINT"
echo "User Pool ID: $USER_POOL_ID"
echo "Region: $REGION"
echo ""

# Function to print test result
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ $2${NC}"
    else
        echo -e "${RED}✗ $2${NC}"
        exit 1
    fi
}

# Test 1: Health Check
echo "Test 1: Health Check (Public Endpoint)"
HEALTH_RESPONSE=$(curl -s "$API_ENDPOINT/health")
echo "$HEALTH_RESPONSE" | grep -q "healthy"
print_result $? "Health check endpoint accessible"
echo ""

# Test 2: Create Session Without Token (Should Fail)
echo "Test 2: Create Session Without Token (Should Return 401)"
CREATE_NO_AUTH=$(curl -s -w "%{http_code}" -o /dev/null -X POST "$API_ENDPOINT/sessions" \
    -H "Content-Type: application/json" \
    -d '{"sourceLanguage": "en", "qualityTier": "standard"}')
[ "$CREATE_NO_AUTH" = "401" ]
print_result $? "JWT authorizer blocking unauthenticated requests"
echo ""

# Test 3: Get Non-Existent Session (Should Return 404)
echo "Test 3: Get Non-Existent Session (Should Return 404)"
GET_404=$(curl -s -w "%{http_code}" -o /dev/null "$API_ENDPOINT/sessions/nonexistent-session-999")
[ "$GET_404" = "404" ]
print_result $? "GET endpoint returns 404 for non-existent sessions"
echo ""

# Test 4: Authenticate and Get Token
echo "Test 4: Authenticate Test User"
echo -e "${YELLOW}Note: This requires a test user to exist in Cognito${NC}"
echo "Creating test user if not exists..."

# Try to create test user (will fail if exists, which is fine)
aws cognito-idp admin-create-user \
    --user-pool-id "$USER_POOL_ID" \
    --username "test-speaker@example.com" \
    --temporary-password "TempPass123!" \
    --message-action SUPPRESS \
    --region "$REGION" 2>/dev/null || true

# Set permanent password
aws cognito-idp admin-set-user-password \
    --user-pool-id "$USER_POOL_ID" \
    --username "test-speaker@example.com" \
    --password "TestPassword123!" \
    --permanent \
    --region "$REGION" 2>/dev/null || true

# Get JWT token
TOKEN=$(aws cognito-idp admin-initiate-auth \
    --user-pool-id "$USER_POOL_ID" \
    --client-id "$CLIENT_ID" \
    --auth-flow ADMIN_NO_SRP_AUTH \
    --auth-parameters USERNAME=test-speaker@example.com,PASSWORD=TestPassword123! \
    --region "$REGION" \
    --query 'AuthenticationResult.IdToken' \
    --output text 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo -e "${RED}✗ Failed to get JWT token${NC}"
    exit 1
fi
print_result 0 "JWT token obtained successfully"
echo ""

# Test 5: Create Session With Token
echo "Test 5: Create Session With Valid Token"
CREATE_RESPONSE=$(curl -s -X POST "$API_ENDPOINT/sessions" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"sourceLanguage": "en", "qualityTier": "standard"}')

SESSION_ID=$(echo "$CREATE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['sessionId'])" 2>/dev/null)

if [ -z "$SESSION_ID" ]; then
    echo -e "${RED}✗ Failed to create session${NC}"
    echo "Response: $CREATE_RESPONSE"
    exit 1
fi
print_result 0 "Session created successfully: $SESSION_ID"
echo ""

# Test 6: Get Session (Public)
echo "Test 6: Get Session (Public Endpoint)"
GET_RESPONSE=$(curl -s "$API_ENDPOINT/sessions/$SESSION_ID")
echo "$GET_RESPONSE" | grep -q "$SESSION_ID"
print_result $? "Session retrieved successfully"
echo ""

# Test 7: Update Session
echo "Test 7: Update Session Status"
UPDATE_RESPONSE=$(curl -s -X PATCH "$API_ENDPOINT/sessions/$SESSION_ID" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"status": "paused"}')
echo "$UPDATE_RESPONSE" | grep -q "paused"
print_result $? "Session updated successfully"
echo ""

# Test 8: Delete Session
echo "Test 8: Delete Session"
DELETE_STATUS=$(curl -s -w "%{http_code}" -o /dev/null -X DELETE "$API_ENDPOINT/sessions/$SESSION_ID" \
    -H "Authorization: Bearer $TOKEN")
[ "$DELETE_STATUS" = "204" ]
print_result $? "Session deleted successfully (204 No Content)"
echo ""

# Test 9: Verify Session Ended
echo "Test 9: Verify Session Marked as Ended"
ENDED_RESPONSE=$(curl -s "$API_ENDPOINT/sessions/$SESSION_ID")
echo "$ENDED_RESPONSE" | grep -q "ended"
print_result $? "Session status is 'ended'"
echo ""

echo "========================================="
echo -e "${GREEN}All Tests Passed!${NC}"
echo "========================================="
echo ""
echo "HTTP API is deployed and functioning correctly."
echo ""
echo "Endpoints:"
echo "  - POST   /sessions          (Authenticated)"
echo "  - GET    /sessions/{id}     (Public)"
echo "  - PATCH  /sessions/{id}     (Authenticated)"
echo "  - DELETE /sessions/{id}     (Authenticated)"
echo "  - GET    /health            (Public)"
echo ""
