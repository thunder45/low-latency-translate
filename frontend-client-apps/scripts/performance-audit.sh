#!/bin/bash

# Performance Audit Script for Frontend Client Apps
# This script runs Lighthouse audits and checks Core Web Vitals

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🚀 Starting Performance Audit..."
echo ""

# Check if lighthouse is installed
if ! command -v lighthouse &> /dev/null; then
    echo -e "${RED}❌ Lighthouse CLI not found${NC}"
    echo "Install with: npm install -g lighthouse"
    exit 1
fi

# Configuration
SPEAKER_URL="${SPEAKER_URL:-http://localhost:3000}"
LISTENER_URL="${LISTENER_URL:-http://localhost:3001}"
OUTPUT_DIR="./performance-reports"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "📊 Running Lighthouse audits..."
echo ""

# Function to run Lighthouse audit
run_audit() {
    local url=$1
    local name=$2
    local output_file="$OUTPUT_DIR/${name}-$(date +%Y%m%d-%H%M%S)"
    
    echo "Auditing $name at $url..."
    
    lighthouse "$url" \
        --output=html \
        --output=json \
        --output-path="$output_file" \
        --chrome-flags="--headless" \
        --only-categories=performance,accessibility,best-practices,seo \
        --quiet
    
    # Parse JSON results
    local json_file="${output_file}.report.json"
    if [ -f "$json_file" ]; then
        local perf_score=$(jq '.categories.performance.score * 100' "$json_file")
        local a11y_score=$(jq '.categories.accessibility.score * 100' "$json_file")
        local bp_score=$(jq '.categories["best-practices"].score * 100' "$json_file")
        local seo_score=$(jq '.categories.seo.score * 100' "$json_file")
        
        # Core Web Vitals
        local lcp=$(jq '.audits["largest-contentful-paint"].numericValue' "$json_file")
        local fid=$(jq '.audits["max-potential-fid"].numericValue' "$json_file")
        local cls=$(jq '.audits["cumulative-layout-shift"].numericValue' "$json_file")
        local tti=$(jq '.audits.interactive.numericValue' "$json_file")
        
        echo ""
        echo "Results for $name:"
        echo "  Performance:    ${perf_score}%"
        echo "  Accessibility:  ${a11y_score}%"
        echo "  Best Practices: ${bp_score}%"
        echo "  SEO:            ${seo_score}%"
        echo ""
        echo "Core Web Vitals:"
        echo "  LCP: ${lcp}ms (target: <2500ms)"
        echo "  FID: ${fid}ms (target: <100ms)"
        echo "  CLS: ${cls} (target: <0.1)"
        echo "  TTI: ${tti}ms (target: <3000ms)"
        echo ""
        
        # Check if targets are met
        local all_passed=true
        
        if (( $(echo "$perf_score < 90" | bc -l) )); then
            echo -e "${YELLOW}⚠️  Performance score below 90%${NC}"
            all_passed=false
        fi
        
        if (( $(echo "$a11y_score < 90" | bc -l) )); then
            echo -e "${YELLOW}⚠️  Accessibility score below 90%${NC}"
            all_passed=false
        fi
        
        if (( $(echo "$lcp > 2500" | bc -l) )); then
            echo -e "${YELLOW}⚠️  LCP exceeds 2.5s target${NC}"
            all_passed=false
        fi
        
        if (( $(echo "$fid > 100" | bc -l) )); then
            echo -e "${YELLOW}⚠️  FID exceeds 100ms target${NC}"
            all_passed=false
        fi
        
        if (( $(echo "$cls > 0.1" | bc -l) )); then
            echo -e "${YELLOW}⚠️  CLS exceeds 0.1 target${NC}"
            all_passed=false
        fi
        
        if (( $(echo "$tti > 3000" | bc -l) )); then
            echo -e "${YELLOW}⚠️  TTI exceeds 3s target${NC}"
            all_passed=false
        fi
        
        if [ "$all_passed" = true ]; then
            echo -e "${GREEN}✅ All performance targets met!${NC}"
        fi
        
        echo ""
        echo "Full report: ${output_file}.report.html"
        echo ""
    else
        echo -e "${RED}❌ Failed to generate report${NC}"
    fi
}

# Run audits for both apps
echo "=== Speaker App Audit ==="
run_audit "$SPEAKER_URL" "speaker-app"

echo "=== Listener App Audit ==="
run_audit "$LISTENER_URL" "listener-app"

echo "✅ Performance audit complete!"
echo "Reports saved to: $OUTPUT_DIR"
