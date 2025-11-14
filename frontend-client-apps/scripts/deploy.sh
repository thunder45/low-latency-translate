#!/bin/bash

# Deployment script for frontend applications
# Usage: ./deploy.sh [speaker|listener] [dev|staging|prod]

set -e

APP=$1
ENV=$2

if [ -z "$APP" ] || [ -z "$ENV" ]; then
  echo "Usage: ./deploy.sh [speaker|listener] [dev|staging|prod]"
  exit 1
fi

if [ "$APP" != "speaker" ] && [ "$APP" != "listener" ]; then
  echo "Error: APP must be 'speaker' or 'listener'"
  exit 1
fi

if [ "$ENV" != "dev" ] && [ "$ENV" != "staging" ] && [ "$ENV" != "prod" ]; then
  echo "Error: ENV must be 'dev', 'staging', or 'prod'"
  exit 1
fi

echo "Deploying $APP app to $ENV environment..."

# Set environment-specific variables
case $ENV in
  dev)
    S3_BUCKET="low-latency-translate-${APP}-dev"
    CLOUDFRONT_ID="E1234567890DEV"
    ;;
  staging)
    S3_BUCKET="low-latency-translate-${APP}-staging"
    CLOUDFRONT_ID="E1234567890STG"
    ;;
  prod)
    S3_BUCKET="low-latency-translate-${APP}-prod"
    CLOUDFRONT_ID="E1234567890PRD"
    ;;
esac

# Navigate to app directory
cd "${APP}-app"

# Install dependencies
echo "Installing dependencies..."
npm ci

# Build the application
echo "Building application..."
npm run build

# Upload to S3
echo "Uploading to S3 bucket: $S3_BUCKET..."
aws s3 sync dist/ "s3://${S3_BUCKET}/" \
  --delete \
  --cache-control "public, max-age=31536000, immutable" \
  --exclude "index.html" \
  --exclude "*.map"

# Upload index.html with no-cache
aws s3 cp dist/index.html "s3://${S3_BUCKET}/index.html" \
  --cache-control "no-cache, no-store, must-revalidate" \
  --content-type "text/html"

# Invalidate CloudFront cache
echo "Invalidating CloudFront distribution: $CLOUDFRONT_ID..."
aws cloudfront create-invalidation \
  --distribution-id "$CLOUDFRONT_ID" \
  --paths "/*"

echo "Deployment complete!"
echo "URL: https://${S3_BUCKET}.cloudfront.net"
