#!/bin/bash
# Test WebSocket authorization with wscat

WS_URL="wss://2y19uvhyq5.execute-api.us-east-1.amazonaws.com/prod"

echo "======================================"
echo "WebSocket Authorization Test"
echo "======================================"
echo ""

# Test 1: Connection without token (listener)
echo "Test 1: Connecting WITHOUT token (should be authorized as listener)..."
echo "URL: ${WS_URL}?sessionId=test-session-123"
echo ""
echo "Connecting... (will auto-close after a few seconds)"
echo ""

# Use perl to timeout since timeout isn't available on macOS
(wscat -c "${WS_URL}?sessionId=test-session-123" &) 
PID=$!
sleep 3
kill $PID 2>/dev/null || true

echo ""
echo "Test 1 complete. Check authorizer logs above."
echo ""
echo "======================================"
echo ""

# Test 2: Connection with fake token (should be denied or fail validation)
echo "Test 2: Connecting WITH fake token (should fail validation)..."
echo "URL: ${WS_URL}?token=fake-jwt-token&sessionId=test-session-456"
echo ""
echo "Connecting... (will auto-close after a few seconds)"
echo ""

(wscat -c "${WS_URL}?token=fake-jwt-token&sessionId=test-session-456" &)
PID=$!
sleep 3
kill $PID 2>/dev/null || true

echo ""
echo "Test 2 complete. Check authorizer logs above."
echo ""
echo "======================================"
echo ""
echo "Next step: Check the tail-lambda-logs.sh output for session-authorizer-dev"
echo "The authorizer should show invocation logs for both tests."
echo ""
