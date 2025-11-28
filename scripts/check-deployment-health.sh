#!/bin/bash

# Deployment Health Check Script - Phase 4 (Kinesis Architecture)
# Verifies backend and frontend are ready for E2E testing

# Don't exit on error - we want to check everything
set +e

echo "🔍 Deployment Health Check - Phase 4 (Kinesis)"
echo "==============================================="
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
echo "4️⃣  Checking Phase 4 Backend Resources..."
echo "----------------------------------------"

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
    
    # Check Lambda functions (Phase 4 specific)
    REQUIRED_LAMBDAS=("session-connection-handler-dev" "session-disconnect-handler-dev" "audio-processor")
    
    for lambda in "${REQUIRED_LAMBDAS[@]}"; do
        if aws lambda get-function --function-name "$lambda" --region "$REGION" &> /dev/null; then
            print_status "PASS" "Lambda function exists: $lambda"
        else
            print_status "FAIL" "Lambda function not found: $lambda"
        fi
    done
    
    # Check Kinesis Data Stream (Phase 4 critical resource)
    STREAM_NAME="audio-ingestion-dev"
    if aws kinesis describe-stream --stream-name "$STREAM_NAME" --region "$REGION" &> /dev/null; then
        print_status "PASS" "Kinesis Data Stream exists: $STREAM_NAME"
        
        # Check stream status
        STREAM_STATUS=$(aws kinesis describe-stream --stream-name "$STREAM_NAME" --region "$REGION" --query 'StreamDescription.StreamStatus' --output text)
        if [ "$STREAM_STATUS" == "ACTIVE" ]; then
            print_status "PASS" "Stream is ACTIVE"
        else
            print_status "WARN" "Stream status: $STREAM_STATUS"
        fi
    else
        print_status "FAIL" "Kinesis Data Stream not found: $STREAM_NAME (Phase 4 required)"
    fi
    
    # Check S3 buckets
    REQUIRED_BUCKETS=("low-latency-audio-dev" "translation-audio-dev")
    
    for bucket in "${REQUIRED_BUCKETS[@]}"; do
        if aws s3 ls "s3://$bucket" --region "$REGION" &> /dev/null; then
            print_status "PASS" "S3 bucket exists: $bucket"
        else
            print_status "FAIL" "S3 bucket not found: $bucket"
        fi
    done
    
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
    echo "Phase 4 Architecture Verified:"
    echo "  AudioWorklet → PCM → Kinesis → audio_processor → S3 → Listener"
    echo ""
    echo "Next steps:"
    echo "1. cd frontend-client-apps/speaker-app && npm run dev"
    echo "2. cd frontend-client-apps/listener-app && npm run dev (separate terminal)"
    echo "3. Test end-to-end translation"
    echo "4. Monitor logs: ./scripts/tail-lambda-logs.sh audio-processor"
    exit 0
else
    echo -e "${RED}⚠️  Some checks failed. Please fix the issues above before proceeding.${NC}"
    echo ""
    echo "For troubleshooting, see:"
    echo "  - README.md (deployment instructions)"
    echo "  - CHECKPOINT_PHASE4_COMPLETE.md (deployment details)"
    exit 1
fi
