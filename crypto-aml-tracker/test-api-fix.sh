#!/bin/bash
# Test script to verify the API fix works

echo "Testing corrected API endpoint..."
echo ""

# Test 1: Correct endpoint should work
echo "✓ Testing: GET /api/transactions?limit=5&offset=0&sort_by=amount_desc"
curl -s "http://localhost:4000/api/transactions?limit=5&offset=0&sort_by=amount_desc" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'  ✓ Success: {data[\"total\"]} transactions, {len(data[\"items\"])} returned')"
echo ""

# Test 2: Wrong endpoint should fail (404)
echo "✗ Testing: GET /api/transactions/latest?limit=5 (should fail with 404)"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:4000/api/transactions/latest?limit=5")
if [ "$HTTP_CODE" = "404" ]; then
    echo "  ✓ Correctly returns 404 (as expected for wrong endpoint)"
else
    echo "  ✗ Unexpected response code: $HTTP_CODE"
fi
echo ""

# Test 3: Valid sort options
echo "✓ Testing: sort_by=latest"
curl -s "http://localhost:4000/api/transactions?limit=3&sort_by=latest" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'  ✓ Success: sort_by={data[\"sortBy\"]}')"
echo ""

echo "✓ Testing: sort_by=amount_desc" 
curl -s "http://localhost:4000/api/transactions?limit=3&sort_by=amount_desc" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'  ✓ Success: sort_by={data[\"sortBy\"]}')"
echo ""

echo "All API tests complete!"
