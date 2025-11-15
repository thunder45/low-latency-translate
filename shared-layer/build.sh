#!/bin/bash
#
# Build script for shared Lambda layer
#
# This script:
# 1. Copies shared utilities from session-management
# 2. Installs dependencies
# 3. Creates deployment package (shared-layer.zip)
#

set -e

echo "Building shared Lambda layer..."

# Clean previous build
rm -rf build/
rm -f shared-layer.zip

# Create build directory structure
mkdir -p build/python/shared_utils

# Copy utilities from session-management
echo "Copying shared utilities..."
cp ../session-management/shared/utils/structured_logger.py build/python/shared_utils/
cp ../session-management/shared/utils/error_codes.py build/python/shared_utils/
cp ../session-management/shared/config/table_names.py build/python/shared_utils/
cp ../session-management/shared/models/websocket_messages.py build/python/shared_utils/

# Copy __init__.py
cp python/shared_utils/__init__.py build/python/shared_utils/

# Install dependencies (if any)
if [ -f requirements.txt ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt -t build/python/
fi

# Create deployment package
echo "Creating deployment package..."
cd build
zip -r ../shared-layer.zip python/
cd ..

# Cleanup
rm -rf build/

echo "✓ Shared layer built successfully: shared-layer.zip"
echo "  Size: $(du -h shared-layer.zip | cut -f1)"
