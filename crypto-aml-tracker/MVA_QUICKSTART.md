# Market Value Analysis (MVA) - Quick Start Guide

## 🚀 Get Started in 5 Minutes

### Prerequisites

- Backend running on `localhost:4000`
- Frontend running on `localhost:5173` (or your Vite port)
- MySQL/MariaDB database configured
- RPC provider configured (Alchemy, Infura, or public)

### Step 1: Configure RPC Access

Edit `crypto-aml-tracker/backend-py/.env`:

```bash
# Option 1: Alchemy (Recommended)
ALCHEMY_RPC=https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY

# Option 2: Infura
INFURA_RPC=https://mainnet.infura.io/v3/YOUR_API_KEY

# Option 3: Public RPC (rate-limited, for testing only)
RPC_URL=https://ethereum-rpc.publicnode.com

# Optional: CoinGecko API for better rate limits
COINGECKO_API_KEY=your_api_key_here
```

### Step 2: Start the Backend

```bash
cd crypto-aml-tracker/backend-py
python main.py
```

You should see:
```
✓ MVA schema initialized
MySQL connected → aml_db
Server started on http://0.0.0.0:4000
```

### Step 3: Test with a Real Ethereum Address

Let's use Vitalik's address as an example:

```bash
cd crypto-aml-tracker/backend-py
python scripts/update_balances.py 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
```

This will:
1. Fetch ETH balance
2. Fetch ERC20 balances (USDT, USDC, DAI, WETH)
3. Get current token prices from CoinGecko
4. Calculate USD values
5. Save to database

Expected output:
```
Treating 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 as an address
Fetching balances...
✓ Updated balances for 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
```

### Step 4: View in the Frontend

1. Open your browser to `http://localhost:5173`
2. Navigate to any page (Placement, Layering, Clusters, etc.)
3. Click on an address or cluster
4. The **Entity Intelligence Workspace** opens on the right
5. Click the **Market Value** tab
6. See the portfolio analysis!

### Step 5: Test the API Directly

```bash
# Get address MVA
curl http://localhost:4000/api/mva/address/0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 | jq

# Expected response:
{
  "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
  "summary": {
    "total_value_usd": 123456.78,
    "eth_value_usd": 100000.00,
    "stablecoin_value_usd": 20000.00,
    "token_count": 5,
    "wallet_count": 1
  },
  "assets": [...],
  "allocation": {...},
  "flags": [...]
}
```

## 🧪 Testing with Clusters

### Option 1: Use Existing Cluster

If you have clusters in your database:

```bash
# List clusters
mysql -u your_user -p aml_db -e "SELECT cluster_id, address_count FROM address_clusters LIMIT 5;"

# Update a cluster
python scripts/update_balances.py cluster_123
```

### Option 2: Create a Test Cluster

```sql
-- Connect to MySQL
mysql -u your_user -p aml_db

-- Insert a test cluster
INSERT INTO address_clusters (cluster_id, addresses, address_count, created_at)
VALUES (
  'test_cluster_001',
  '["0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"]',
  2,
  NOW()
);
```

Then update balances:

```bash
python scripts/update_balances.py test_cluster_001
```

## 📊 What You'll See

### Portfolio Summary Cards
- **Total Portfolio Value**: Sum of all token holdings in USD
- **ETH Holdings**: Value of ETH + WETH
- **Stablecoin Holdings**: Value of USDT + USDC + DAI
- **Wallets in Cluster**: Number of addresses
- **Tokens Held**: Number of different tokens

### Portfolio Allocation Pie Chart
- ETH %
- Stablecoins %
- Other ERC20 %
- DeFi exposure %

### Asset Holdings Table
- Token Symbol
- Contract Address
- Balance
- USD Value
- Portfolio %

### Intelligence Flags
Examples you might see:
- 🔴 **High Value Wallet** - Portfolio > $100K
- ⚠️ **Stablecoin Heavy** - Stablecoins > 70%
- 💤 **Dormant Wealth** - No updates in 30+ days
- ⟠ **ETH Dominant** - ETH > 80%

## 🔍 Testing Different Scenarios

### High-Value Wallet
```bash
# Ethereum Foundation address
python scripts/update_balances.py 0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe
```

### Stablecoin-Heavy Wallet
```bash
# Known USDC holder
python scripts/update_balances.py 0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503
```

### Exchange Wallet (Diversified)
```bash
# Binance hot wallet
python scripts/update_balances.py 0x28C6c06298d514Db089934071355E5743bf21d60
```

## 🐛 Troubleshooting

### "No balance data available"

**Cause**: Balances haven't been fetched yet

**Solution**:
```bash
python scripts/update_balances.py YOUR_ADDRESS
```

### "Failed to fetch MVA data"

**Cause**: Backend not running or database connection issue

**Solution**:
1. Check backend is running: `curl http://localhost:4000/api/status`
2. Check MySQL connection in `.env`
3. Check backend logs for errors

### "Price data showing $0"

**Cause**: CoinGecko API rate limit or network issue

**Solution**:
1. Wait 1 minute (rate limit cooldown)
2. Add `COINGECKO_API_KEY` to `.env`
3. Check internet connection

### RPC Errors

**Cause**: Rate limiting or invalid RPC URL

**Solution**:
1. Use Alchemy or Infura instead of public RPC
2. Check API key is valid
3. Verify RPC URL format

### Slow Performance

**Cause**: Public RPC rate limits

**Solution**:
1. Use Alchemy (free tier: 300M compute units/month)
2. Use Infura (free tier: 100K requests/day)
3. Reduce number of addresses being updated

## 📈 Next Steps

### 1. Automate Balance Updates

Add to your ETL pipeline or scheduler:

```python
# In scheduler.py or similar
from services.balance_aggregator import get_aggregator

async def update_top_clusters():
    """Update balances for top 10 clusters by transaction volume."""
    aggregator = get_aggregator()
    clusters = await get_top_clusters(limit=10)
    
    for cluster in clusters:
        await aggregator.update_cluster(
            cluster['cluster_id'],
            cluster['addresses']
        )
```

### 2. Add More Tokens

Edit `services/balance_aggregator.py`:

```python
SUPPORTED_TOKENS = {
    # ... existing tokens ...
    "UNI": {
        "symbol": "UNI",
        "contract": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
        "decimals": 18,
        "coingecko_id": "uniswap"
    },
    # Add more...
}
```

### 3. Enable Historical Tracking

Set up a daily cron job:

```bash
# crontab -e
0 0 * * * cd /path/to/backend-py && python scripts/snapshot_portfolios.py
```

### 4. Integrate with Other Pages

See `INTEGRATION_EXAMPLE.md` for detailed integration guide.

## 🎯 Success Criteria

You've successfully set up MVA when:

- ✅ Backend starts without errors
- ✅ Balance update script completes successfully
- ✅ API returns portfolio data
- ✅ Frontend shows Entity Intelligence Workspace
- ✅ Market Value tab displays portfolio analysis
- ✅ Intelligence flags appear based on portfolio characteristics

## 📚 Additional Resources

- **Full Documentation**: `MVA_IMPLEMENTATION.md`
- **Integration Guide**: `INTEGRATION_EXAMPLE.md`
- **API Reference**: `http://localhost:4000/docs` (FastAPI auto-docs)

## 💡 Pro Tips

1. **Use Alchemy** - Best free tier for development
2. **Cache aggressively** - Prices update every 5 minutes by default
3. **Batch updates** - Update multiple addresses in parallel
4. **Monitor rate limits** - Track API usage to avoid throttling
5. **Start small** - Test with 1-2 addresses before scaling

## 🆘 Need Help?

Common issues and solutions:

| Issue | Solution |
|-------|----------|
| No data showing | Run `update_balances.py` script |
| Slow loading | Use Alchemy/Infura RPC |
| Price errors | Add CoinGecko API key |
| Database errors | Check MySQL connection |
| Frontend not updating | Hard refresh (Ctrl+Shift+R) |

## 🎉 You're Ready!

You now have a working Market Value Analysis system. Start investigating on-chain wealth and portfolio intelligence for your AML investigations!

Next: Explore other intelligence mechanisms (Exchange Flow, Holder Behavior, etc.) as they become available.
