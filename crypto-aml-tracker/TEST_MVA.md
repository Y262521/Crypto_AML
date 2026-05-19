# MVA Testing Guide

## Quick Test Checklist

### 1. Backend Health Check

```bash
# Test backend is running
curl http://localhost:4000/api/status

# Expected: JSON response with server_time and scheduler info
```

### 2. Test MVA API Endpoints

```bash
# Test with a known Ethereum address (Vitalik's address)
curl http://localhost:4000/api/mva/address/0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045

# Expected: JSON with summary, assets, allocation, flags (may be empty if no data yet)
```

### 3. Update Balance Data (Required for Testing)

```bash
cd crypto-aml-tracker/backend-py

# Test with Vitalik's address
python scripts/update_balances.py 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045

# Expected output:
# Treating 0x... as an address
# Fetching balances...
# ✓ Updated balances for 0x...
```

### 4. Verify Data in Database

```bash
mysql -u hakim -p aml_clean -e "SELECT * FROM wallet_balances LIMIT 5;"
mysql -u hakim -p aml_clean -e "SELECT * FROM token_price_cache;"
```

### 5. Test Frontend

1. Open browser to `http://localhost:5173`
2. Navigate to any page (Placement, Layering, Clusters, Integration)
3. Look for addresses or clusters in the data
4. Click on an address or cluster
5. **Expected**: Right-side drawer opens with "Entity Intelligence Workspace"
6. Click the "Market Value" tab
7. **Expected**: Portfolio analysis displays (or "No data" if balance not updated)

### 6. Test with Real Data

```bash
# Update a few well-known addresses
cd crypto-aml-tracker/backend-py

# Ethereum Foundation
python scripts/update_balances.py 0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe

# Binance Hot Wallet (high value)
python scripts/update_balances.py 0x28C6c06298d514Db089934071355E5743bf21d60

# USDC Treasury (stablecoin heavy)
python scripts/update_balances.py 0x55FE002aefF02F77364de339a1292923A15844B8
```

Then test in frontend by clicking these addresses.

## Common Issues & Solutions

### Issue: "No balance data available"

**Solution**: Run the update script first
```bash
python scripts/update_balances.py YOUR_ADDRESS
```

### Issue: "Failed to fetch MVA data"

**Solution**: Check backend is running
```bash
curl http://localhost:4000/api/status
```

### Issue: Frontend shows "Loading..." forever

**Solution**: Check browser console for errors, verify API_BASE_URL

### Issue: Prices showing $0

**Solution**: 
1. Check CoinGecko API is accessible
2. Wait 1 minute (rate limit)
3. Add COINGECKO_API_KEY to .env

### Issue: RPC errors in backend logs

**Solution**:
1. Verify RPC URL in .env
2. Use Alchemy or Infura instead of public RPC
3. Check API key is valid

## Expected Behavior

### When clicking an address/cluster:

1. ✅ Right-side drawer slides in from right
2. ✅ Shows entity ID and type
3. ✅ Shows source page name
4. ✅ Has close button (✕)
5. ✅ Has tabs: Overview, Market Value, etc.
6. ✅ Market Value tab is clickable
7. ✅ Other tabs show "Coming Soon"

### In Market Value tab (with data):

1. ✅ 5 summary cards showing metrics
2. ✅ Pie chart showing allocation
3. ✅ Intelligence flags (if applicable)
4. ✅ Asset holdings table
5. ✅ Historical chart (if history exists)

### In Market Value tab (no data):

1. ✅ Shows "No portfolio data available"
2. ✅ No errors in console
3. ✅ Can still close workspace

## Performance Expectations

- Backend API response: < 500ms
- Frontend workspace open: < 300ms
- Chart rendering: < 100ms
- Balance update (1 address): 2-5 seconds
- Balance update (10 addresses): 5-15 seconds

## Success Criteria

✅ Backend starts without errors
✅ No deprecation warnings
✅ Frontend loads without errors
✅ Can click addresses/clusters
✅ Workspace opens smoothly
✅ Market Value tab displays
✅ Can close workspace
✅ No console errors
✅ API returns valid JSON
✅ Balance updates work

## Quick Smoke Test

```bash
# 1. Start services
./start.sh

# 2. In another terminal, test backend
curl http://localhost:4000/api/status

# 3. Update a test address
cd crypto-aml-tracker/backend-py
python scripts/update_balances.py 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045

# 4. Test API
curl http://localhost:4000/api/mva/address/0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 | jq

# 5. Open browser to http://localhost:5173
# 6. Navigate to Clusters page
# 7. Click any cluster or address
# 8. Verify workspace opens
# 9. Click Market Value tab
# 10. Verify data displays

# If all steps pass: ✅ MVA is working!
```

## Troubleshooting Commands

```bash
# Check backend logs
tail -f crypto-aml-tracker/backend-py/logs/*.log

# Check database
mysql -u hakim -p aml_clean -e "SHOW TABLES;"
mysql -u hakim -p aml_clean -e "SELECT COUNT(*) FROM wallet_balances;"

# Check frontend build
cd crypto-aml-tracker
npm run build

# Test API directly
curl -v http://localhost:4000/api/mva/address/0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045

# Check RPC connectivity
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  YOUR_RPC_URL
```

## Next Steps After Testing

1. ✅ Verify all tests pass
2. Configure production RPC provider
3. Set up automated balance updates
4. Integrate with investigation workflows
5. Train users on new feature
6. Monitor performance and errors
7. Plan next intelligence mechanism
