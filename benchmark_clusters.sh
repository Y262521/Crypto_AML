#!/bin/bash
# Quick benchmark script for cluster endpoints

echo "=========================================="
echo "Cluster Endpoints Performance Benchmark"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

BASE_URL="http://127.0.0.1:4000"

# Function to test endpoint
test_endpoint() {
    local endpoint=$1
    local name=$2
    local threshold=$3
    
    echo "Testing: $name"
    echo "Endpoint: $endpoint"
    
    # Make request and capture timing
    response=$(curl -s -w "\nHTTP_CODE:%{http_code}\nTIME_TOTAL:%{time_total}" -o /tmp/response.json "$BASE_URL$endpoint" 2>&1)
    
    http_code=$(echo "$response" | grep "HTTP_CODE:" | cut -d: -f2)
    time_total=$(echo "$response" | grep "TIME_TOTAL:" | cut -d: -f2)
    
    if [ "$http_code" == "200" ]; then
        # Count items in response
        if [ -f /tmp/response.json ]; then
            items=$(cat /tmp/response.json | grep -o "cluster_id" | wc -l)
        else
            items=0
        fi
        
        echo "  Status: HTTP $http_code ✓"
        echo "  Time: ${time_total}s"
        
        if [ ! -z "$items" ] && [ "$items" -gt 0 ]; then
            echo "  Items: $items"
        fi
        
        # Performance assessment
        if (( $(echo "$time_total < $threshold" | bc -l) )); then
            echo -e "  ${GREEN}Performance: EXCELLENT (< ${threshold}s)${NC}"
            return 0
        elif (( $(echo "$time_total < 3.0" | bc -l) )); then
            echo -e "  ${YELLOW}Performance: ACCEPTABLE (< 3s)${NC}"
            return 0
        else
            echo -e "  ${RED}Performance: SLOW (> 3s)${NC}"
            return 1
        fi
    else
        echo "  Status: HTTP $http_code ✗"
        echo -e "  ${RED}FAILED${NC}"
        return 1
    fi
}

# Run tests
echo ""
test_endpoint "/api/clusters/summary" "Cluster Summary" "1.0"
echo ""
echo "------------------------------------------"
echo ""
test_endpoint "/api/clusters/?limit=50" "Cluster List (50 items)" "0.5"
echo ""
echo "------------------------------------------"
echo ""
test_endpoint "/api/clusters/?limit=200" "Cluster List (200 items)" "1.5"
echo ""
echo "=========================================="
echo "Benchmark Complete"
echo "=========================================="
