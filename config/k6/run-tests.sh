#!/bin/bash
# Run k6 load tests
# Usage: ./run-tests.sh [api|ws|benchmark]

set -e

API_URL=${API_URL:-http://localhost:8000}
WS_URL=${WS_URL:-ws://localhost:8000}

case "${1:-all}" in
  api)
    echo "Running API load test..."
    k6 run --out json=k6-results-api.json -e API_URL=$API_URL config/k6/api-load-test.js
    ;;
  ws)
    echo "Running WebSocket load test..."
    k6 run --out json=k6-results-ws.json -e WS_URL=$WS_URL config/k6/ws-load-test.js
    ;;
  benchmark)
    echo "Running performance benchmark..."
    k6 run --out json=k6-results-benchmark.json -e API_URL=$API_URL config/k6/performance-benchmark.js
    ;;
  all)
    echo "Running all tests..."
    $0 api
    $0 ws
    $0 benchmark
    ;;
esac

echo "Tests complete. Results in k6-results-*.json"
