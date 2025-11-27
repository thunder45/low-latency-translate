#!/bin/bash
# Download FFmpeg for Lambda Layer
# This script downloads a pre-compiled FFmpeg binary for AWS Lambda

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAMBDA_LAYERS_DIR="$(cd "$SCRIPT_DIR/../lambda_layers" && pwd)"
FFMPEG_DIR="$LAMBDA_LAYERS_DIR/ffmpeg"
FFMPEG_BIN="$FFMPEG_DIR/bin/ffmpeg"

# FFmpeg version and download URL
# Using johnvansickle's static builds which work well in Lambda
FFMPEG_VERSION="6.0"
FFMPEG_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"

echo "=========================================="
echo "Downloading FFmpeg for Lambda Layer"
echo "=========================================="

# Create directories if they don't exist
mkdir -p "$FFMPEG_DIR/bin"

# Check if ffmpeg already exists
if [ -f "$FFMPEG_BIN" ]; then
    echo "✓ FFmpeg binary already exists at: $FFMPEG_BIN"
    "$FFMPEG_BIN" -version | head -n 1
    echo ""
    echo "To re-download, delete the file first:"
    echo "  rm $FFMPEG_BIN"
    exit 0
fi

echo "Downloading FFmpeg from johnvansickle.com..."
echo "URL: $FFMPEG_URL"
echo ""

# Download to temp directory
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

cd "$TEMP_DIR"

# Download
curl -L -o ffmpeg.tar.xz "$FFMPEG_URL"

# Extract
echo "Extracting FFmpeg..."
tar -xf ffmpeg.tar.xz

# Find the ffmpeg binary (it's in a versioned directory)
FFMPEG_EXTRACTED=$(find . -name "ffmpeg" -type f | head -n 1)

if [ -z "$FFMPEG_EXTRACTED" ]; then
    echo "❌ Error: Could not find ffmpeg binary in downloaded archive"
    exit 1
fi

# Copy to target location
echo "Installing FFmpeg to Lambda layer..."
cp "$FFMPEG_EXTRACTED" "$FFMPEG_BIN"
chmod +x "$FFMPEG_BIN"

# Verify
echo ""
echo "✓ FFmpeg installed successfully!"
echo "Location: $FFMPEG_BIN"
echo "Size: $(du -h "$FFMPEG_BIN" | cut -f1)"
echo ""
"$FFMPEG_BIN" -version | head -n 1

echo ""
echo "=========================================="
echo "FFmpeg ready for Lambda deployment"
echo "=========================================="
