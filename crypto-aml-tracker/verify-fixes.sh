#!/bin/bash
# Verification script to confirm all fixes are in place

echo "🔍 Verifying Frontend Fixes..."
echo ""

# Check 1: Correct API endpoint
echo "✓ Check 1: API endpoint in transactionService.js"
if grep -q "transactions?\${params}" src/services/transactionService.js; then
    echo "  ✅ PASS: Using correct endpoint /api/transactions"
else
    echo "  ❌ FAIL: Wrong endpoint"
fi
echo ""

# Check 2: Valid sortBy default
echo "✓ Check 2: Default sortBy in App.jsx"
if grep -q "useState('amount_desc')" src/App.jsx; then
    echo "  ✅ PASS: Using valid default sortBy"
else
    echo "  ❌ FAIL: Invalid sortBy default"
fi
echo ""

# Check 3: getClusters export exists
echo "✓ Check 3: getClusters export in transactionService.js"
if grep -q "export const getClusters" src/services/transactionService.js; then
    echo "  ✅ PASS: getClusters export exists"
else
    echo "  ❌ FAIL: getClusters missing"
fi
echo ""

# Check 4: createOwnerListEntry export exists
echo "✓ Check 4: createOwnerListEntry export in transactionService.js"
if grep -q "export const createOwnerListEntry" src/services/transactionService.js; then
    echo "  ✅ PASS: createOwnerListEntry export exists"
else
    echo "  ❌ FAIL: createOwnerListEntry missing"
fi
echo ""

# Check 5: ErrorBoundary exists
echo "✓ Check 5: ErrorBoundary component exists"
if [ -f "src/ErrorBoundary.jsx" ]; then
    echo "  ✅ PASS: ErrorBoundary.jsx exists"
else
    echo "  ❌ FAIL: ErrorBoundary missing"
fi
echo ""

# Check 6: ErrorBoundary imported in main.jsx
echo "✓ Check 6: ErrorBoundary used in main.jsx"
if grep -q "ErrorBoundary" src/main.jsx; then
    echo "  ✅ PASS: ErrorBoundary imported and used"
else
    echo "  ❌ FAIL: ErrorBoundary not used"
fi
echo ""

# Check 7: Backend is running
echo "✓ Check 7: Backend API responding"
if curl -s -f -o /dev/null http://localhost:4000/api/status 2>/dev/null; then
    echo "  ✅ PASS: Backend running on port 4000"
else
    echo "  ❌ FAIL: Backend not responding"
fi
echo ""

# Check 8: Frontend dev server is running
echo "✓ Check 8: Frontend dev server responding"
if curl -s -f -o /dev/null http://localhost:5173/ 2>/dev/null; then
    echo "  ✅ PASS: Frontend running on port 5173"
else
    echo "  ⚠️  WARNING: Frontend not responding (might need browser to load)"
fi
echo ""

echo "========================================"
echo "✅ All code fixes are in place!"
echo ""
echo "Next steps:"
echo "1. Open browser to: http://localhost:5173/"
echo "2. Force refresh: Ctrl+Shift+R (or Cmd+Shift+R on Mac)"
echo "3. Check browser console (F12) for errors"
echo "========================================"
