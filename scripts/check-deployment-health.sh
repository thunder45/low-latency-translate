#!/bin/bash

# Deployment Health Check Script
# Verifies backend and frontend are ready for E2E testing

# Don't exit on error - we want to check everything
set +e

echo "🔍 Deployment Health Check"
echo "=========================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0
WARN=0

# Function to print status
print_status() {
    if [ "$1" == "PASS" ]; then
        echo -e "${GREEN}✅ PASS${NC}: $2"
        ((PASS++))
    elif [ "$1" == "FAIL" ]; then
        echo -e "${RED}❌ FAIL${NC}: $2"
        ((FAIL++))
    elif [ "$1" == "WARN" ]; then
        echo -e "${YELLOW}⚠️  WARN${NC}: $2"
        ((WARN++))
    else
        echo "ℹ️  INFO: $2"
    fi
}

echo "1️⃣  Checking Frontend Configuration..."
echo "-----------------------------------"

# Check if .env file exists
if [ -f "frontend-client-apps/speaker-app/.env" ]; then
    print_status "PASS" ".env file exists"
    
    # Check required variables
    if grep -q "VITE_COGNITO_USER_POOL_ID" frontend-client-apps/speaker-app/.env 2>/dev/null; then
        print_status "PASS" "VITE_COGNITO_USER_POOL_ID is set"
    else
        print_status "FAIL" "VITE_COGNITO_USER_POOL_ID is missing"
    fi
    
    if grep -q "VITE_COGNITO_CLIENT_ID" frontend-client-apps/speaker-app/.env 2>/dev/null; then
        print_status "PASS" "VITE_COGNITO_CLIENT_ID is set"
    else
        print_status "FAIL" "VITE_COGNITO_CLIENT_ID is missing"
    fi
    
    if grep -q "VITE_AWS_REGION" frontend-client-apps/speaker-app/.env 2>/dev/null; then
        print_status "PASS" "VITE_AWS_REGION is set"
    else
        print_status "FAIL" "VITE_AWS_REGION is missing"
    fi
    
    if grep -q "VITE_ENCRYPTION_KEY" frontend-client-apps/speaker-app/.env 2>/dev/null; then
        KEY_LENGTH=$(grep "VITE_ENCRYPTION_KEY" frontend-client-apps/speaker-app/.env 2>/dev/null | cut -d'=' -f2 | wc -c)
        if [ "$KEY_LENGTH" -ge 32 ]; then
            print_status "PASS" "VITE_ENCRYPTION_KEY is at least 32 characters"
        else
            print_status "FAIL" "VITE_ENCRYPTION_KEY is too short (need 32+ chars)"
        fi
    else
        print_status "FAIL" "VITE_ENCRYPTION_KEY is missing"
    fi
    
    if grep -q "VITE_WEBSOCKET_URL" frontend-client-apps/speaker-app/.env 2>/dev/null; then
        print_status "PASS" "VITE_WEBSOCKET_URL is set"
    else
        print_status "FAIL" "VITE_WEBSOCKET_URL is missing"
    fi
else
    print_status "FAIL" ".env file not found"
    echo "  Create it from .env.example: cp frontend-client-apps/speaker-app/.env.example frontend-client-apps/speaker-app/.env"
fi

echo ""
echo "2️⃣  Checking Frontend Dependencies..."
echo "-----------------------------------"

if [ -d "frontend-client-apps/speaker-app/node_modules" ]; then
    print_status "PASS" "node_modules exists"
else
    print_status "WARN" "node_modules not found - run 'npm install'"
fi

echo ""
echo "3️⃣  Checking AWS CLI Configuration..."
echo "-----------------------------------"

if command -v aws &> /dev/null; then
    print_status "PASS" "AWS CLI is installed"
    
    # Check if AWS credentials are configured
    if aws sts get-caller-identity &> /dev/null; then
        print_status "PASS" "AWS credentials are configured"
        ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
        echo "  Account ID: $ACCOUNT_ID"
    else
        print_status "FAIL" "AWS credentials not configured or invalid"
    fi
else
    print_status "WARN" "AWS CLI not installed - cannot check backend"
fi

echo ""
echo "4️⃣  Checking Backend Resources (if AWS CLI available)..."
echo "-------------------------------------------------------"

if command -v aws &> /dev/null && aws sts get-caller-identity &> /dev/null; then
    # Get region from .env or use default
    if [ -f "frontend-client-apps/speaker-app/.env" ]; then
        REGION=$(grep "VITE_AWS_REGION" frontend-client-apps/speaker-app/.env | cut -d'=' -f2 | tr -d ' ')
    else
        REGION="us-east-1"
    fi
    
    echo "  Using region: $REGION"
    
    # Check Cognito User Pool
    if [ -f "frontend-client-apps/speaker-app/.env" ]; then
        USER_POOL_ID=$(grep "VITE_COGNITO_USER_POOL_ID" frontend-client-apps/speaker-app/.env | cut -d'=' -f2 | tr -d ' ')
        if [ ! -z "$USER_POOL_ID" ]; then
            if aws cognito-idp describe-user-pool --user-pool-id "$USER_POOL_ID" --region "$REGION" &> /dev/null; then
                print_status "PASS" "Cognito User Pool exists ($USER_POOL_ID)"
            else
                print_status "FAIL" "Cognito User Pool not found ($USER_POOL_ID)"
            fi
        fi
    fi
    
    # Check API Gateway
    API_COUNT=$(aws apigatewayv2 get-apis --region "$REGION" --query 'Items[?ProtocolType==`WEBSOCKET`]' --output json 2>/dev/null | jq '. | length')
    if [ "$API_COUNT" -gt 0 ]; then
        print_status "PASS" "WebSocket API Gateway found ($API_COUNT API(s))"
    else
        print_status "WARN" "No WebSocket API Gateway found"
    fi
    
    # Check DynamoDB tables
    TABLE_COUNT=$(aws dynamodb list-tables --region "$REGION" --query 'TableNames' --output json 2>/dev/null | jq '. | length')
    if [ "$TABLE_COUNT" -gt 0 ]; then
        print_status "PASS" "DynamoDB tables found ($TABLE_COUNT table(s))"
    else
        print_status "WARN" "No DynamoDB tables found"
    fi
    
    # Check Lambda functions
    LAMBDA_COUNT=$(aws lambda list-functions --region "$REGION" --query 'Functions' --output json 2>/dev/null | jq '. | length')
    if [ "$LAMBDA_COUNT" -gt 0 ]; then
        print_status "PASS" "Lambda functions found ($LAMBDA_COUNT function(s))"
    else
        print_status "WARN" "No Lambda functions found"
    fi
else
    print_status "WARN" "Skipping backend checks (AWS CLI not available or not configured)"
fi

echo ""
echo "5️⃣  Checking Network Connectivity..."
echo "-----------------------------------"

# Check internet connectivity
if ping -c 1 google.com &> /dev/null; then
    print_status "PASS" "Internet connectivity OK"
else
    print_status "FAIL" "No internet connectivity"
fi

# Check AWS connectivity
if curl -s -I https://cognito-idp.us-east-1.amazonaws.com &> /dev/null; then
    print_status "PASS" "Can reach AWS Cognito"
else
    print_status "WARN" "Cannot reach AWS Cognito"
fi

echo ""
echo "6️⃣  Checking Build..."
echo "-------------------"

if [ -d "frontend-client-apps/speaker-app" ]; then
    cd frontend-client-apps/speaker-app
    
    if npm run build > /tmp/build-check.log 2>&1; then
        print_status "PASS" "Frontend builds successfully"
    else
        print_status "FAIL" "Frontend build failed (see /tmp/build-check.log for details)"
    fi
    
    cd ../..
else
    print_status "FAIL" "speaker-app directory not found"
fi

echo ""
echo "📊 Summary"
echo "=========="
echo -e "${GREEN}✅ Passed: $PASS${NC}"
echo -e "${YELLOW}⚠️  Warnings: $WARN${NC}"
echo -e "${RED}❌ Failed: $FAIL${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}🎉 All critical checks passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. cd frontend-client-apps/speaker-app"
    echo "2. npm run dev"
    echo "3. Open http://localhost:3000"
    echo "4. Follow E2E_AUTHENTICATION_TEST_GUIDE.md"
    exit 0
else
    echo -e "${RED}⚠️  Some checks failed. Please fix the issues above before proceeding.${NC}"
    echo ""
    echo "For detailed troubleshooting, see:"
    echo "  frontend-client-apps/docs/PRE_E2E_DEPLOYMENT_CHECKLIST.md"
    exit 1
fi
