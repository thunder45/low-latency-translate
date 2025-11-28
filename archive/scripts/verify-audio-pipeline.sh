#!/bin/bash
# Comprehensive Audio Pipeline Verification Script
# Tests each component of the KVS -> Transcribe -> Translate -> TTS pipeline

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGION=${AWS_REGION:-us-east-1}
STAGE=${STAGE:-dev}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Audio Pipeline Verification${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to print section headers
print_section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# Function to print test results
print_result() {
    local status=$1
    local message=$2
    if [ "$status" = "PASS" ]; then
        echo -e "${GREEN}✓ PASS:${NC} $message"
    elif [ "$status" = "FAIL" ]; then
        echo -e "${RED}✗ FAIL:${NC} $message"
    elif [ "$status" = "WARN" ]; then
        echo -e "${YELLOW}⚠ WARN:${NC} $message"
    else
        echo -e "${BLUE}ℹ INFO:${NC} $message"
    fi
}

# Step 1: Verify KVS Stream Exists (Traditional Architecture)
print_section "Step 1: Verify KVS Stream (Traditional Architecture)"

if [ -z "$SESSION_ID" ]; then
    print_result "WARN" "SESSION_ID not provided. Skipping KVS verification."
    print_result "INFO" "Export SESSION_ID to test an active session"
    print_result "INFO" "Example: export SESSION_ID=joyful-hope-911"
else
    STREAM_NAME="session-${SESSION_ID}"
    
    print_result "INFO" "Checking KVS Stream: $STREAM_NAME"
    
    # Check for Traditional KVS Stream
    if aws kinesisvideo describe-stream \
        --stream-name "$STREAM_NAME" \
        --region "$REGION" > /dev/null 2>&1; then
        
        # Get stream details
        STREAM_INFO=$(aws kinesisvideo describe-stream \
            --stream-name "$STREAM_NAME" \
            --region "$REGION" \
            --output json)
        
        STREAM_ARN=$(echo "$STREAM_INFO" | jq -r '.StreamInfo.StreamARN')
        STREAM_STATUS=$(echo "$STREAM_INFO" | jq -r '.StreamInfo.Status')
        RETENTION=$(echo "$STREAM_INFO" | jq -r '.StreamInfo.DataRetentionInHours')
        
        print_result "PASS" "KVS Stream exists"
        print_result "INFO" "Stream ARN: $STREAM_ARN"
        print_result "INFO" "Stream Status: $STREAM_STATUS"
        print_result "INFO" "Data Retention: ${RETENTION} hours"
        
        # Check for recent fragments (CRITICAL TEST)
        print_result "INFO" "Checking for recent fragments..."
        
        FRAGMENTS=$(aws kinesisvideo list-fragments \
            --stream-name "$STREAM_NAME" \
            --region "$REGION" \
            --max-results 10 \
            --output json 2>/dev/null || echo '{"Fragments":[]}')
        
        FRAGMENT_COUNT=$(echo "$FRAGMENTS" | jq '.Fragments | length')
        
        if [ "$FRAGMENT_COUNT" -gt 0 ]; then
            print_result "PASS" "Found $FRAGMENT_COUNT recent fragments - Audio IS reaching KVS Stream!"
            print_result "INFO" "Fragment details:"
            
            # Show fragment details
            echo "$FRAGMENTS" | jq '.Fragments[] | {
                FragmentNumber: .FragmentNumber,
                ProducerTimestamp: .ProducerTimestamp,
                ServerTimestamp: .ServerTimestamp,
                FragmentLengthInMilliseconds: .FragmentLengthInMilliseconds,
                FragmentSizeInBytes: .FragmentSizeInBytes
            }'
        else
            print_result "FAIL" "No fragments found - Audio NOT reaching KVS Stream"
            print_result "INFO" "Possible causes:"
            print_result "INFO" "  1. Speaker not actively streaming"
            print_result "INFO" "  2. kvs_stream_writer not writing to stream"
            print_result "INFO" "  3. Stream just created (wait 30 seconds and retry)"
        fi
        
    else
        print_result "FAIL" "KVS Stream does not exist: $STREAM_NAME"
        print_result "INFO" "Stream should be created by kvs_stream_writer on first audio chunk"
        print_result "INFO" "Possible causes:"
        print_result "INFO" "  1. Speaker hasn't started streaming yet"
        print_result "INFO" "  2. kvs_stream_writer Lambda not deployed"
        print_result "INFO" "  3. kvs_stream_writer failing (check logs)"
    fi
fi

# Step 2: Check kvs_stream_writer Lambda
print_section "Step 2: Verify kvs_stream_writer Lambda"

WRITER_FUNCTION="kvs-stream-writer-${STAGE}"

print_result "INFO" "Checking Lambda function: $WRITER_FUNCTION"

if aws lambda get-function \
    --function-name "$WRITER_FUNCTION" \
    --region "$REGION" > /dev/null 2>&1; then
    
    print_result "PASS" "Lambda function exists"
    
    # Check recent invocations
    print_result "INFO" "Checking recent CloudWatch logs..."
    
    LOG_GROUP="/aws/lambda/${WRITER_FUNCTION}"
    
    if aws logs describe-log-groups \
        --log-group-name-prefix "$LOG_GROUP" \
        --region "$REGION" | grep -q "$LOG_GROUP"; then
        
        print_result "PASS" "CloudWatch log group exists"
        
        RECENT_LOGS=$(aws logs filter-log-events \
            --log-group-name "$LOG_GROUP" \
            --region "$REGION" \
            --start-time $(($(date +%s) * 1000 - 3600000)) \
            --max-items 10 \
            --output json 2>/dev/null || echo '{"events":[]}')
        
        LOG_COUNT=$(echo "$RECENT_LOGS" | jq '.events | length')
        
        if [ "$LOG_COUNT" -gt 0 ]; then
            print_result "PASS" "Found $LOG_COUNT recent log entries"
            print_result "INFO" "Recent logs:"
            echo "$RECENT_LOGS" | jq -r '.events[] | .message' | tail -5
        else
            print_result "WARN" "No recent log entries (last 1 hour)"
            print_result "INFO" "Lambda may not have been invoked yet"
        fi
    else
        print_result "WARN" "CloudWatch log group not found (Lambda never invoked)"
    fi
    
else
    print_result "FAIL" "Lambda function not found: $WRITER_FUNCTION"
    print_result "INFO" "This Lambda should be created in Phase 2"
fi

# Step 3: Verify EventBridge Rule
print_section "Step 3: Verify EventBridge Integration"

RULE_NAME="kvs-stream-consumer-trigger-${STAGE}"

print_result "INFO" "Checking EventBridge rule: $RULE_NAME"

if aws events describe-rule \
    --name "$RULE_NAME" \
    --region "$REGION" > /dev/null 2>&1; then
    
    RULE_INFO=$(aws events describe-rule \
        --name "$RULE_NAME" \
        --region "$REGION" \
        --output json)
    
    RULE_STATE=$(echo "$RULE_INFO" | jq -r '.State')
    EVENT_PATTERN=$(echo "$RULE_INFO" | jq -r '.EventPattern')
    
    print_result "PASS" "EventBridge rule exists"
    print_result "INFO" "Rule State: $RULE_STATE"
    print_result "INFO" "Event Pattern: $EVENT_PATTERN"
    
    # Check rule targets
    TARGETS=$(aws events list-targets-by-rule \
        --rule "$RULE_NAME" \
        --region "$REGION" \
        --output json)
    
    TARGET_COUNT=$(echo "$TARGETS" | jq '.Targets | length')
    
    if [ "$TARGET_COUNT" -gt 0 ]; then
        print_result "PASS" "Rule has $TARGET_COUNT target(s) configured"
        echo "$TARGETS" | jq '.Targets[] | {
            Id: .Id,
            Arn: .Arn
        }'
    else
        print_result "FAIL" "Rule has no targets configured"
    fi
else
    print_result "FAIL" "EventBridge rule not found: $RULE_NAME"
    print_result "INFO" "Rule should be created during infrastructure deployment"
fi

# Step 4: Check kvs_stream_consumer Lambda  
print_section "Step 4: Verify kvs_stream_consumer Lambda"

CONSUMER_FUNCTION="kvs-stream-consumer-${STAGE}"

print_result "INFO" "Checking Lambda function: $CONSUMER_FUNCTION"

if aws lambda get-function \
    --function-name "$CONSUMER_FUNCTION" \
    --region "$REGION" > /dev/null 2>&1; then
    
    print_result "PASS" "Lambda function exists"
    
    # Check recent invocations
    print_result "INFO" "Checking recent CloudWatch logs..."
    
    LOG_GROUP="/aws/lambda/${CONSUMER_FUNCTION}"
    
    # Check if log group exists
    if aws logs describe-log-groups \
        --log-group-name-prefix "$LOG_GROUP" \
        --region "$REGION" | grep -q "$LOG_GROUP"; then
        
        print_result "PASS" "CloudWatch log group exists"
        
        # Get recent log streams
        RECENT_LOGS=$(aws logs filter-log-events \
            --log-group-name "$LOG_GROUP" \
            --region "$REGION" \
            --start-time $(($(date +%s) * 1000 - 3600000)) \
            --max-items 20 \
            --output json 2>/dev/null || echo '{"events":[]}')
        
        LOG_COUNT=$(echo "$RECENT_LOGS" | jq '.events | length')
        
        if [ "$LOG_COUNT" -gt 0 ]; then
            print_result "PASS" "Found $LOG_COUNT recent log entries"
            print_result "INFO" "Recent log messages:"
            echo "$RECENT_LOGS" | jq -r '.events[] | .message' | tail -10
        else
            print_result "WARN" "No recent log entries found (last 1 hour)"
            print_result "INFO" "This may indicate the Lambda hasn't been invoked"
        fi
    else
        print_result "WARN" "CloudWatch log group not found (Lambda never invoked)"
    fi
    
else
    print_result "FAIL" "Lambda function not found: $CONSUMER_FUNCTION"
fi

# Step 5: Check SQS Queue (Optional - may not be used)
print_section "Step 5: Verify SQS Queue (Optional)"

QUEUE_NAME="audio-processing-queue-${STAGE}"

print_result "INFO" "Checking SQS queue: $QUEUE_NAME"

QUEUE_URL=$(aws sqs get-queue-url \
    --queue-name "$QUEUE_NAME" \
    --region "$REGION" \
    --output text \
    --query 'QueueUrl' 2>/dev/null || echo "")

if [ -n "$QUEUE_URL" ]; then
    print_result "PASS" "SQS queue exists: $QUEUE_URL"
    
    # Get queue attributes
    QUEUE_ATTRS=$(aws sqs get-queue-attributes \
        --queue-url "$QUEUE_URL" \
        --region "$REGION" \
        --attribute-names All \
        --output json)
    
    MSG_AVAILABLE=$(echo "$QUEUE_ATTRS" | jq -r '.Attributes.ApproximateNumberOfMessages')
    MSG_IN_FLIGHT=$(echo "$QUEUE_ATTRS" | jq -r '.Attributes.ApproximateNumberOfMessagesNotVisible')
    
    print_result "INFO" "Messages available: $MSG_AVAILABLE"
    print_result "INFO" "Messages in flight: $MSG_IN_FLIGHT"
    
    if [ "$MSG_AVAILABLE" -gt 0 ]; then
        print_result "PASS" "Queue has messages - audio chunks ARE being queued"
        
        # Peek at a message (without deleting)
        print_result "INFO" "Peeking at queue message..."
        
        MESSAGE=$(aws sqs receive-message \
            --queue-url "$QUEUE_URL" \
            --region "$REGION" \
            --max-number-of-messages 1 \
            --visibility-timeout 5 \
            --output json 2>/dev/null || echo '{"Messages":[]}')
        
        if [ "$(echo "$MESSAGE" | jq '.Messages | length')" -gt 0 ]; then
            print_result "INFO" "Sample message body (truncated):"
            echo "$MESSAGE" | jq -r '.Messages[0].Body' | head -c 200
            echo "..."
        fi
    else
        print_result "WARN" "Queue is empty - no audio chunks in queue"
        print_result "INFO" "This may indicate audio processing issues"
    fi
else
    print_result "WARN" "SQS queue not found: $QUEUE_NAME"
    print_result "INFO" "Current implementation may use direct Lambda invocation"
fi

# Step 6: Check audio_processor Lambda
print_section "Step 6: Verify audio_processor Lambda"

PROCESSOR_FUNCTION="audio-processor-${STAGE}"

print_result "INFO" "Checking Lambda function: $PROCESSOR_FUNCTION"

if aws lambda get-function \
    --function-name "$PROCESSOR_FUNCTION" \
    --region "$REGION" > /dev/null 2>&1; then
    
    print_result "PASS" "Lambda function exists"
    
    # Check recent invocations
    LOG_GROUP="/aws/lambda/${PROCESSOR_FUNCTION}"
    
    if aws logs describe-log-groups \
        --log-group-name-prefix "$LOG_GROUP" \
        --region "$REGION" | grep -q "$LOG_GROUP"; then
        
        RECENT_LOGS=$(aws logs filter-log-events \
            --log-group-name "$LOG_GROUP" \
            --region "$REGION" \
            --start-time $(($(date +%s) * 1000 - 3600000)) \
            --max-items 20 \
            --output json 2>/dev/null || echo '{"events":[]}')
        
        LOG_COUNT=$(echo "$RECENT_LOGS" | jq '.events | length')
        
        if [ "$LOG_COUNT" -gt 0 ]; then
            print_result "PASS" "Found $LOG_COUNT recent log entries"
            
            # Check for Transcribe mentions
            TRANSCRIBE_LOGS=$(echo "$RECENT_LOGS" | jq -r '.events[] | .message' | grep -i "transcribe" || echo "")
            
            if [ -n "$TRANSCRIBE_LOGS" ]; then
                print_result "PASS" "Found Transcribe processing logs"
                print_result "INFO" "Sample Transcribe logs:"
                echo "$TRANSCRIBE_LOGS" | head -5
            else
                print_result "WARN" "No Transcribe processing logs found"
            fi
        else
            print_result "WARN" "No recent log entries (last 1 hour)"
        fi
    fi
    
else
    print_result "FAIL" "Lambda function not found: $PROCESSOR_FUNCTION"
fi

# Step 7: Manual Test Commands
print_section "Step 7: Manual Test Commands"

print_result "INFO" "Test kvs_stream_writer Lambda:"
cat << 'EOF'
aws lambda invoke \
  --function-name kvs-stream-writer-dev \
  --payload '{"action": "health_check"}' \
  --region us-east-1 \
  response.json && cat response.json
EOF

echo ""
print_result "INFO" "Test stream creation:"
cat << 'EOF'
aws lambda invoke \
  --function-name kvs-stream-writer-dev \
  --payload '{"action": "createStream", "sessionId": "test-123"}' \
  --region us-east-1 \
  response.json && cat response.json
EOF

echo ""
print_result "INFO" "List fragments for your session:"
cat << 'EOF'
aws kinesisvideo list-fragments \
  --stream-name session-YOUR_SESSION_ID \
  --region us-east-1 \
  --max-results 10
EOF

# Step 8: Summary
print_section "Summary"

echo ""
print_result "INFO" "Verification complete!"
echo ""
echo "Architecture: Traditional KVS Stream (MediaRecorder → Backend → KVS)"
echo ""
echo "Next steps:"
echo "1. Create a test session via speaker app"
echo "2. Start speaking into microphone"
echo "3. Export SESSION_ID=<session-id> and re-run this script"
echo "4. Verify fragments exist: aws kinesisvideo list-fragments --stream-name session-<id>"
echo "5. Check CloudWatch logs for each Lambda function"
echo ""
print_result "INFO" "For detailed logs, run:"
echo "  ./scripts/tail-lambda-logs.sh kvs-stream-writer-dev"
echo "  ./scripts/tail-lambda-logs.sh kvs-stream-consumer-dev"
echo "  ./scripts/tail-lambda-logs.sh audio-processor-dev"
echo ""
print_result "INFO" "For implementation guides, see:"
echo "  - ARCHITECTURE_DECISIONS.md (master reference)"
echo "  - PHASE1_SPEAKER_MEDIARECORDER_GUIDE.md"
echo "  - PHASE2_BACKEND_KVS_WRITER_GUIDE.md"
echo "  - PHASE3_LISTENER_S3_PLAYBACK_GUIDE.md"
