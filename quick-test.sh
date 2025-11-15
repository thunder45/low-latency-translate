#!/bin/bash
# Quick Staging Environment Test Script

set -e

REGION="us-east-1"
AUDIO_STACK="audio-transcription-staging"
SESSION_STACK="SessionManagement-staging"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Staging Environment Quick Health Check                 ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: CloudFormation Stacks
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Checking CloudFormation Stacks..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

AUDIO_STATUS=$(aws cloudformation describe-stacks \
  --stack-name $AUDIO_STACK \
  --region $REGION \
  --query 'Stacks[0].StackStatus' \
  --output text 2>/dev/null || echo "NOT_FOUND")

SESSION_STATUS=$(aws cloudformation describe-stacks \
  --stack-name $SESSION_STACK \
  --region $REGION \
  --query 'Stacks[0].StackStatus' \
  --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$AUDIO_STATUS" = "CREATE_COMPLETE" ] || [ "$AUDIO_STATUS" = "UPDATE_COMPLETE" ]; then
  echo -e "  ${GREEN}✓${NC} Audio Transcription Stack: $AUDIO_STATUS"
else
  echo -e "  ${RED}✗${NC} Audio Transcription Stack: $AUDIO_STATUS"
fi

if [ "$SESSION_STATUS" = "CREATE_COMPLETE" ] || [ "$SESSION_STATUS" = "UPDATE_COMPLETE" ]; then
  echo -e "  ${GREEN}✓${NC} Session Management Stack: $SESSION_STATUS"
else
  echo -e "  ${RED}✗${NC} Session Management Stack: $SESSION_STATUS"
fi

echo ""

# Test 2: Lambda Functions
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. Checking Lambda Functions..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

FUNCTIONS=$(aws lambda list-functions \
  --region $REGION \
  --query 'Functions[?contains(FunctionName, `staging`) || contains(FunctionName, `audio-processor`) || contains(FunctionName, `ConnectionHandler`) || contains(FunctionName, `SessionStatusHandler`)].FunctionName' \
  --output text)

if [ -n "$FUNCTIONS" ]; then
  echo "$FUNCTIONS" | tr '\t' '\n' | while read func; do
    echo -e "  ${GREEN}✓${NC} $func"
  done
else
  echo -e "  ${RED}✗${NC} No Lambda functions found"
fi

echo ""

# Test 3: DynamoDB Tables
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. Checking DynamoDB Tables..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TABLES=$(aws dynamodb list-tables \
  --region $REGION \
  --query 'TableNames[?contains(@, `staging`) || contains(@, `Sessions`) || contains(@, `Connections`) || contains(@, `RateLimits`)]' \
  --output text)

if [ -n "$TABLES" ]; then
  echo "$TABLES" | tr '\t' '\n' | while read table; do
    # Get table status
    STATUS=$(aws dynamodb describe-table \
      --table-name "$table" \
      --region $REGION \
      --query 'Table.TableStatus' \
      --output text 2>/dev/null || echo "ERROR")
    
    if [ "$STATUS" = "ACTIVE" ]; then
      echo -e "  ${GREEN}✓${NC} $table ($STATUS)"
    else
      echo -e "  ${YELLOW}⚠${NC} $table ($STATUS)"
    fi
  done
else
  echo -e "  ${RED}✗${NC} No DynamoDB tables found"
fi

echo ""

# Test 4: WebSocket API
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. Checking WebSocket API..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

WS_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name $SESSION_STACK \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`WebSocketAPIEndpoint`].OutputValue' \
  --output text 2>/dev/null || echo "")

if [ -n "$WS_ENDPOINT" ]; then
  echo -e "  ${GREEN}✓${NC} WebSocket Endpoint: $WS_ENDPOINT"
else
  echo -e "  ${RED}✗${NC} WebSocket endpoint not found"
fi

echo ""

# Test 5: CloudWatch Alarms
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. Checking CloudWatch Alarms..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ALARMS=$(aws cloudwatch describe-alarms \
  --region $REGION \
  --query 'MetricAlarms[?contains(AlarmName, `staging`) || contains(AlarmName, `Audio`) || contains(AlarmName, `Lambda`)].{Name:AlarmName, State:StateValue}' \
  --output text 2>/dev/null)

if [ -n "$ALARMS" ]; then
  echo "$ALARMS" | while read name state; do
    if [ "$state" = "OK" ]; then
      echo -e "  ${GREEN}✓${NC} $name: $state"
    elif [ "$state" = "INSUFFICIENT_DATA" ]; then
      echo -e "  ${YELLOW}⚠${NC} $name: $state (no data yet)"
    else
      echo -e "  ${RED}✗${NC} $name: $state"
    fi
  done
else
  echo -e "  ${YELLOW}⚠${NC} No alarms found (this might be normal for new deployment)"
fi

echo ""

# Test 6: Lambda Invocation Test
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6. Testing Lambda Invocation..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test audio-processor
echo '{"test": true}' > /tmp/test-payload.json
aws lambda invoke \
  --function-name audio-processor \
  --region $REGION \
  --payload file:///tmp/test-payload.json \
  /tmp/test-response.json > /dev/null 2>&1

if [ $? -eq 0 ]; then
  echo -e "  ${GREEN}✓${NC} audio-processor invocation successful"
  if [ -f /tmp/test-response.json ]; then
    RESPONSE=$(cat /tmp/test-response.json)
    echo "    Response: $RESPONSE"
  fi
else
  echo -e "  ${RED}✗${NC} audio-processor invocation failed"
fi

# Cleanup
rm -f /tmp/test-payload.json /tmp/test-response.json

echo ""

# Summary
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    Test Summary                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

if [ "$AUDIO_STATUS" = "CREATE_COMPLETE" ] && [ "$SESSION_STATUS" = "CREATE_COMPLETE" ] && [ -n "$WS_ENDPOINT" ]; then
  echo -e "${GREEN}✓ All critical components are deployed and healthy${NC}"
  echo ""
  echo "Next steps:"
  echo "  1. Review TESTING_GUIDE.md for detailed testing instructions"
  echo "  2. Set up Cognito User Pool for authentication testing"
  echo "  3. Test WebSocket connections with wscat or custom client"
  echo "  4. Monitor CloudWatch logs and metrics"
  echo ""
  echo "WebSocket Endpoint: $WS_ENDPOINT"
else
  echo -e "${YELLOW}⚠ Some components may need attention${NC}"
  echo ""
  echo "Check the output above for details"
fi

echo ""
echo "For detailed testing: see TESTING_GUIDE.md"
echo "For monitoring: aws logs tail /aws/lambda/audio-processor --region $REGION --follow"
