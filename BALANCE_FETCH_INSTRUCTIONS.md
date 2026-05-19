# How to Fix Balance Fetching

## The Problem
The balance data is showing $0.00 because the RPC calls are failing silently.

## Solution: Get a Proper Alchemy API Key

### Step 1: Get Free Alchemy API Key
1. Go to https://www.alchemy.com/
2. Sign up for free account
3. Create a new app:
   - Chain: Ethereum
   - Network: Mainnet
4. Copy the HTTPS URL (should look like: `https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY_HERE`)

### Step 2: Update .env File
Edit `crypto-aml-tracker/backend-py/.env`:

```bash
# Replace this line:
ALCHEMY_RPC=https://eth-mainnet.g.alchemy.com/v2/rGGUSUFNHfTrp5nrkZdH9

# With your new key:
ALCHEMY_RPC=https://eth-mainnet.g.alchemy.com/v2/YOUR_FULL_KEY_HERE
```

### Step 3: Restart Backend
```bash
# Stop the current backend (Ctrl+C)
# Then restart:
cd ~/Crypto_AML
./start.sh
```

### Step 4: Test
1. Go to Placement/Layering/Integration page
2. Click "Analyze" on any address
3. Select "Market Value"
4. Wait 5-10 seconds for first load
5. Should now show real balance data!

## Alternative: Use Public RPC (Slower, Less Reliable)

If you don't want to get an Alchemy key, the code will automatically fall back to a public RPC (`https://eth.llamarpc.com`), but it's:
- Slower
- Less reliable
- May have rate limits

The public RPC is already configured as fallback in the code I just updated.

## Verify It's Working

After restarting, check the backend terminal output. You should see:
```
🔗 Using RPC: https://eth-mainnet.g.alchemy.com/v2/...
📊 Updating balances for 0x...
💰 Fetching token prices from CoinGecko...
  ✓ ETH: $3500.00
  ✓ USDT: $1.00
  ✓ ETH balance for 0x...: 1.234
✓ Updated balances for 0x...: $4321.00 total value
```

If you see errors like:
- `✗ RPC error` - Your API key is invalid
- `✗ Error fetching` - Network/connection issue
- `✗ CoinGecko API error` - CoinGecko rate limit (wait a minute)

## No API Key Needed for CoinGecko

CoinGecko works without an API key (free tier). If you want higher rate limits, you can add:
```bash
COINGECKO_API_KEY=your_key_here
```

But it's optional.
