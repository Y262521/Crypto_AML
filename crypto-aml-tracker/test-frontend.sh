#!/bin/bash
# Quick test script to verify frontend can start

echo "Testing frontend startup..."
echo ""

# Kill any existing processes
pkill -f "npm run dev" 2>/dev/null
sleep 2

# Start Vite in background and capture output
npm run dev > /tmp/vite-test.log 2>&1 &
VITE_PID=$!

echo "Started Vite (PID: $VITE_PID)"
echo "Waiting 8 seconds for startup..."
sleep 8

echo ""
echo "=== Vite Output ==="
cat /tmp/vite-test.log | head -50

echo ""
echo "=== Testing HTTP Response ==="
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 2>&1)
echo "HTTP Response Code: $HTTP_CODE"

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Frontend is responding!"
else
    echo "❌ Frontend is NOT responding"
fi

# Kill the test process
kill $VITE_PID 2>/dev/null

echo ""
echo "Test complete. Check /tmp/vite-test.log for full output."
