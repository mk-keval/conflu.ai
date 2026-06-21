#!/bin/bash
# Frontend bundle size benchmark
set -e

echo "Analyzing frontend bundle size..."
cd frontend

# Build production bundle
npm run build

# Check bundle size
BUNDLE_DIR="dist/assets"
MAX_SIZE_KB=500  # Max 500KB gzipped

# Find largest JS chunk
LARGEST_JS=$(ls -S "$BUNDLE_DIR"/*.js 2>/dev/null | head -1)
if [ -n "$LARGEST_JS" ]; then
    GZIPPED_SIZE=$(gzip -c "$LARGEST_JS" | wc -c)
    SIZE_KB=$((GZIPPED_SIZE / 1024))
    echo "Largest JS chunk: $(basename "$LARGEST_JS")"
    echo "Gzipped size: ${SIZE_KB}KB"
    
    if [ "$SIZE_KB" -gt "$MAX_SIZE_KB" ]; then
        echo "FAIL: Bundle size ${SIZE_KB}KB exceeds limit ${MAX_SIZE_KB}KB"
        exit 1
    else
        echo "PASS: Bundle size ${SIZE_KB}KB within limit ${MAX_SIZE_KB}KB"
    fi
fi

# Check total assets size
TOTAL_SIZE=$(find "$BUNDLE_DIR" -type f \( -name "*.js" -o -name "*.css" \) | xargs gzip -c 2>/dev/null | wc -c)
TOTAL_SIZE_KB=$((TOTAL_SIZE / 1024))
echo "Total gzipped assets: ${TOTAL_SIZE_KB}KB"

echo "Frontend benchmarks complete."
