# Market Value Analysis (MVA) Data Fix

## Issues Fixed

### 1. ❌ Double `/api/` Prefix in URLs
**Problem**: API calls had `/api/api/mva/...` causing 404 errors
**Solution**: Removed extra `/api/` from fetch URLs in `MarketValueAnalysis.jsx`
- Changed: `${API_BASE}/api/mva/...` → `${API_BASE}/mva/...`

### 2. ❌ No Balance Data in Database
**Problem**: All values showing $0.00 because `wallet_balances` table was empty
**Solution**: Added automatic balance fetching to MVA endpoints
- Modified `@router.get("/address/{address}")` to auto-fetch balances if missing or stale (>1 hour)
- Modified `@router.get("/cluster/{cluster_id}")` to auto-fetch cluster balances if missing or stale
- Uses `BalanceAggregator` service to fetch real-time on-chain data via Alchemy RPC

### 3. ❌ Wrong Table Reference
**Problem**: Code was querying non-existent `address_clusters` table
**Solution**: Fixed to use correct `addresses` table with `cluster_id` column

## How It Works Now

### Address MVA Flow:
1. User clicks "Analyze" → "Market Value" on an address
2. Frontend calls `/api/mva/address/{address}`
3. Backend checks `wallet_balances` table
4. **If no data or stale**: Automatically fetches fresh balances from blockchain via Alchemy RPC
5. Fetches ETH + ERC20 balances (WETH, USDT, USDC, DAI)
6. Gets token prices from CoinGecko API
7. Calculates USD values and saves to database
8. Returns portfolio data to frontend

### Cluster MVA Flow:
1. User clicks "Analyze" → "Market Value" on a cluster
2. Frontend calls `/api/mva/cluster/{cluster_id}`
3. Backend gets all addresses in cluster from `addresses` table
4. **If no portfolio data or stale**: Fetches balances for all addresses
5. Aggregates portfolio across all cluster addresses
6. Saves to `cluster_portfolios` table
7. Returns aggregated portfolio data

## Files Modified

1. **crypto-aml-tracker/src/components/intelligence/MarketValueAnalysis.jsx**
   - Fixed API URL paths (removed double `/api/`)

2. **crypto-aml-tracker/backend-py/routes/mva.py**
   - Added automatic balance fetching for addresses
   - Added automatic balance fetching for clusters
   - Fixed table reference from `address_clusters` to `addresses`
   - Added staleness check (1 hour threshold)

## Configuration Required

### Environment Variables (already set):
- `ALCHEMY_RPC`: Ethereum RPC endpoint ✅ (configured in backend-py/.env)
- `COINGECKO_API_KEY`: Optional, for higher rate limits

### Supported Tokens:
- ETH (native)
- WETH (Wrapped ETH)
- USDT (Tether)
- USDC (USD Coin)
- DAI (Dai Stablecoin)

## Testing

### Test Address MVA:
1. Go to Placement/Layering/Integration page
2. Click "Analyze" on any address row
3. Select "Market Value"
4. **First load**: Will take 5-10 seconds (fetching from blockchain)
5. **Subsequent loads**: Instant (cached for 1 hour)
6. Should see:
   - Total portfolio value
   - ETH value
   - Stablecoin holdings
   - Asset breakdown
   - Allocation pie chart

### Test Cluster MVA:
1. Click "Analyze" on a cluster row
2. Select "Market Value"
3. **First load**: Will take longer (fetching for multiple addresses)
4. Should see aggregated portfolio across all cluster addresses

## Expected Behavior

### If Address Has Balances:
- Shows real USD values
- Shows token holdings
- Shows allocation chart
- Shows intelligence flags (if applicable)

### If Address is Empty:
- Shows $0.00 values
- Shows "No assets found"
- This is correct behavior for empty wallets

## Rate Limits

### Alchemy RPC:
- Free tier: 300M compute units/month
- Each balance check uses ~10 compute units
- Can check ~30M addresses/month

### CoinGecko API:
- Free tier: 10-50 calls/minute
- Prices cached for 5 minutes
- Should not hit limits with normal usage

## Troubleshooting

### If Still Showing $0.00:
1. Check backend logs for errors
2. Verify ALCHEMY_RPC is set correctly
3. Check if address actually has balances on Etherscan
4. Look for RPC errors in backend console

### If Slow Loading:
- First load is slow (fetching from blockchain)
- Subsequent loads use cached data (1 hour)
- Cluster with many addresses will be slower

### If 404 Errors:
- Restart backend server to load new code
- Check browser console for API URL
- Should be `/api/mva/...` not `/api/api/mva/...`

## Next Steps

1. ✅ Restart backend server
2. ✅ Test with a real address from Placement page
3. ✅ Verify balance data appears
4. ✅ Test cluster MVA
5. ⏳ Add more tokens (optional)
6. ⏳ Add DeFi protocol detection (optional)
