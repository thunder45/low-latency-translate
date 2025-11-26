#!/bin/bash
# Tail Lambda CloudWatch logs in real-time
# Usage: ./tail-lambda-logs.sh <function-name>

FUNCTION_NAME=$1
REGION=${AWS_REGION:-us-east-1}

if [ -z "$FUNCTION_NAME" ]; then
    echo "Usage: $0 <function-name>"
    echo "Example: $0 kvs-stream-consumer-dev"
    exit 1
fi

LOG_GROUP="/aws/lambda/${FUNCTION_NAME}"

echo "Tailing logs for: $LOG_GROUP"
echo "Press Ctrl+C to stop"
echo ""

aws logs tail "$LOG_GROUP" \
    --follow \
    --region "$REGION" \
    --format short
