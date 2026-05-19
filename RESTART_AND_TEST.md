# Restart Backend and Test

## What I Fixed:
1. ✅ Updated RPC URL to use public endpoint as fallback
2. ✅ Added detailed logging to see what's happening
3. ✅ Made address endpoint always fetch fresh data (for testing)
4. ✅ Added manual trigger endpoint for debugging

## Steps to Test:

### 1. Stop Current Backend
Press `Ctrl+C` in the terminal running the backend

### 2. Restart Everything
```bash
cd ~/Crypto_AML
./start.sh
```

### 3. Watch the Backend Terminal
You should see output like:
```
🔗 Using RPC: https://eth-mainnet.g.alchemy.com/v2/demo...
```

### 4. Test in Browser
1. Go to Placement/Layering/Integration page
2. Click "Analyze" on ANY address
3. Select "Market Value"
4. **Watch the backend terminal** - you should see:
   ```
   ============================================================
   MVA REQUEST for address: 0x...
   ============================================================
   Fetching fresh balances...
   
   📊 Updating balances for 0x...
   💰 Fetching token prices from CoinGecko...
     ✓ ETH: $3500.00
     ✓ USDT: $1.00
     ✓ ETH balance for 0x...: 1.234
   ✓ Updated balances for 0x...: $4321.00 total value
   
   Found 5 assets in database
     - ETH: 1.234 ($4321.00)
     - USDT: 100.0 ($100.00)
   ```

### 5. If You See Errors:

**Error: "RPC error"**
- The RPC endpoint is not working
- Try updating ALCHEMY_RPC in `.env` with your own key

**Error: "CoinGecko API error"**
- Rate limited - wait 1 minute and try again

**Error: "No assets found"**
- The address actually has 0 balance (check on Etherscan)
- Or RPC call failed silently

### 6. Use Your Own Alchemy Key (Optional but Recommended)

Edit `crypto-aml-tracker/backend-py/.env`:
```bash
ALCHEMY_RPC=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY_HERE
```

Get your key from: https://www.alchemy.com/ (free)

## Manual Test Endpoint

You can also test directly via API:
```bash
curl -X POST http://localhost:4000/api/mva/trigger-update/0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
```

This will trigger a balance update for Vitalik's address (known to have funds).

## What to Look For:

✅ **Working**: You see prices, balances, and "Updated balances" message
❌ **Not Working**: You see "Error fetching" or "RPC error" messages

If it's still not working after restart, **copy the backend terminal output** and share it so I can see the exact error.
