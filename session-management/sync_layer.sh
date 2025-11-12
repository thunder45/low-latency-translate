#!/bin/bash
# Sync shared code to Lambda Layer structure

set -e

echo "Syncing shared code to Lambda Layer..."

# Create layer directory structure
mkdir -p lambda_layer/python

# Copy shared code
rsync -av --delete shared/ lambda_layer/python/shared/

echo "✅ Lambda Layer synced successfully"
echo "   lambda_layer/python/shared/ is ready for deployment"
