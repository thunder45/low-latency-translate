#!/bin/bash

# Bundle Size Analysis Script
# Analyzes bundle sizes and checks against targets

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "📦 Analyzing Bundle Sizes..."
echo ""

# Target: 500KB gzipped
TARGET_SIZE_KB=500

# Function to analyze bundle
analyze_bundle() {
    local app_name=$1
    local dist_dir=$2
    
    echo "=== $app_name ==="
    
    if [ ! -d "$dist_dir" ]; then
        echo -e "${RED}❌ Build directory not found: $dist_dir${NC}"
        echo "Run 'npm run build' first"
        return 1
    fi
    
    # Calculate total size
    local total_size=$(du -sb "$dist_dir" | cut -f1)
    local total_size_kb=$((total_size / 1024))
    
    # Calculate gzipped size
    local gzip_size=0
    for file in "$dist_dir"/**/*.{js,css}; do
        if [ -f "$file" ]; then
            local file_gzip=$(gzip -c "$file" | wc -c)
            gzip_size=$((gzip_size + file_gzip))
        fi
    done
    local gzip_size_kb=$((gzip_size / 1024))
    
    echo "Total size:   ${total_size_kb} KB"
    echo "Gzipped size: ${gzip_size_kb} KB"
    echo "Target:       ${TARGET_SIZE_KB} KB (gzipped)"
    echo ""
    
    # Check against target
    if [ $gzip_size_kb -le $TARGET_SIZE_KB ]; then
        echo -e "${GREEN}✅ Bundle size within target${NC}"
    else
        local excess=$((gzip_size_kb - TARGET_SIZE_KB))
        echo -e "${RED}❌ Bundle exceeds target by ${excess} KB${NC}"
    fi
    
    echo ""
    
    # Show largest files
    echo "Largest files:"
    find "$dist_dir" -type f \( -name "*.js" -o -name "*.css" \) -exec du -h {} + | sort -rh | head -10
    echo ""
    
    # Check for stats.html
    local stats_file="$dist_dir/stats.html"
    if [ -f "$stats_file" ]; then
        echo "📊 Bundle visualization available at: $stats_file"
        echo ""
    fi
}

# Analyze both apps
cd "$(dirname "$0")/.."

echo "Building applications..."
npm run build --workspace=speaker-app --if-present
npm run build --workspace=listener-app --if-present
echo ""

analyze_bundle "Speaker App" "./speaker-app/dist"
analyze_bundle "Listener App" "./listener-app/dist"

echo "✅ Bundle analysis complete!"
