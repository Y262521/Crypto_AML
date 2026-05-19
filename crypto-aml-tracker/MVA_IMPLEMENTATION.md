# Market Value Analysis (MVA) Implementation

## Overview

Market Value Analysis (MVA) is the first On-Chain Intelligence mechanism for the Ethereum AML platform. It provides portfolio intelligence and on-chain financial visibility for wallet clusters and addresses.

## Architecture

### Key Principles
- **Entity-centric workflow**: Investigation remains focused on entities (addresses/clusters)
- **Contextual investigation**: MVA opens as a right-side drawer, not a new page
- **Progressive disclosure**: Tabs reveal different intelligence layers
- **Professional AML workflow**: Institutional design, low navigation fatigue

### Components

#### Backend (`backend-py/`)

1. **Routes** (`routes/mva.py`)
   - `GET /api/mva/cluster/{cluster_id}` - Get cluster portfolio analysis
   - `GET /api/mva/address/{address}` - Get address portfolio analysis
   - `GET /api/mva/history/{entity_id}` - Get historical portfolio values

2. **Services** (`services/balance_aggregator.py`)
   - `BalanceAggregator` - Fetches on-chain balances via RPC
   - Token price integration with CoinGecko API
   - Automatic price caching (5-minute refresh)
   - Cluster portfolio aggregation

3. **Database Schema** (MySQL/MariaDB)
   - `wallet_balances` - Individual address token balances
   - `cluster_portfolios` - Aggregated cluster portfolios
   - `token_price_cache` - Cached token prices
   - `portfolio_history` - Historical snapshots

#### Frontend (`src/`)

1. **Components**
   - `EntityIntelligenceWorkspace.jsx` - Main workspace container
   - `MarketValueAnalysis.jsx` - MVA tab implementation
   - `EntityLink.jsx` - Reusable clickable entity component

2. **Features**
   - Portfolio summary cards (total value, ETH, stablecoins, etc.)
   - Interactive pie chart for allocation
   - Sortable asset holdings table
   - Historical portfolio value chart
   - Intelligence flags (high value, stablecoin heavy, dormant, etc.)

## Supported Tokens

Currently supports major Ethereum tokens:
- **ETH** (native)
- **WETH** (Wrapped ETH)
- **USDT** (Tether)
- **USDC** (USD Coin)
- **DAI** (Dai Stablecoin)

## Intelligence Flags

Simple analytical flags based on portfolio characteristics:

- **High Value Wallet**: Portfolio > $100K
- **Stablecoin Heavy**: Stablecoins > 70% of portfolio
- **Dormant Wealth**: No updates in 30+ days
- **ETH Dominant**: ETH > 80% of portfolio
- **Diversified Portfolio**: Holds 10+ different tokens

**Note**: These are NOT risk scores or POI (Person of Interest) indicators. They are purely informational flags for investigative context.

## Setup & Configuration

### Environment Variables

Add to `backend-py/.env`:

```bash
# RPC Provider (choose one)
ALCHEMY_RPC=https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY
# or
INFURA_RPC=https://mainnet.infura.io/v3/YOUR_API_KEY
# or use public RPC (rate-limited)
RPC_URL=https://ethereum-rpc.publicnode.com

# CoinGecko API (optional, for better rate limits)
COINGECKO_API_KEY=your_coingecko_api_key

# MySQL/MariaDB (should already be configured)
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=your_user
MYSQL_PASSWORD=your_password
MYSQL_DB=aml_db
```

### Installation

1. **Install Python dependencies**:
   ```bash
   cd crypto-aml-tracker/backend-py
   pip install -r requirements.txt
   ```

2. **Database schema** (auto-created on startup):
   - Tables are created automatically when the backend starts
   - Schema is defined in `routes/mva.py::ensure_mva_schema()`

3. **Start the backend**:
   ```bash
   python main.py
   ```

4. **Frontend** (no additional setup needed):
   - MVA components are integrated into the existing React app
   - No new dependencies required

## Usage

### From Any Page

1. Click on an **address** or **cluster** anywhere in the system
2. The **Entity Intelligence Workspace** opens as a right-side drawer
3. Navigate to the **Market Value** tab
4. View portfolio intelligence

### Manual Balance Updates (Testing)

To populate balance data for testing:

```bash
cd crypto-aml-tracker/backend-py
python scripts/update_balances.py 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
```

Or for a cluster:
```bash
python scripts/update_balances.py cluster_123
```

### API Testing

```bash
# Get cluster MVA
curl http://localhost:4000/api/mva/cluster/cluster_123

# Get address MVA
curl http://localhost:4000/api/mva/address/0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb

# Get portfolio history
curl "http://localhost:4000/api/mva/history/cluster_123?entity_type=cluster&days=30"
```

## Integration Points

### Making Entities Clickable

Use the `EntityLink` component:

```jsx
import EntityLink from '../components/common/EntityLink';

<EntityLink
  entityId="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
  entityType="address"
  onClick={(id, type) => openEntityWorkspace(id, type, 'YourPage')}
/>
```

Or use the callback directly:

```jsx
<button onClick={() => onOpenEntityWorkspace(entityId, 'cluster')}>
  View Intelligence
</button>
```

### Pages Already Integrated

- ✅ **Placement** - `onOpenEntityWorkspace` prop added
- ✅ **Layering** - `onOpenEntityWorkspace` prop added
- ✅ **Integration** - `onOpenEntityWorkspace` prop added
- ✅ **Clusters** - `onOpenEntityWorkspace` prop added

## Future Enhancements

### Planned Intelligence Mechanisms

1. **Exchange Flow Analysis** - Track deposits/withdrawals to exchanges
2. **Holder Behavior Analysis** - Analyze holding patterns and movements
3. **Profitability Analysis** - Calculate realized/unrealized gains
4. **DeFi Exposure Analysis** - Track DeFi protocol interactions
5. **Smart Contract Interaction Analysis** - Analyze contract calls

### Technical Improvements

1. **Automated Balance Updates**
   - Scheduled background jobs
   - Webhook-based updates on new transactions
   - Real-time balance tracking

2. **Extended Token Support**
   - Top 100 ERC20 tokens
   - NFT holdings (ERC721/ERC1155)
   - LP token valuation

3. **Performance Optimization**
   - Batch RPC calls
   - Redis caching layer
   - GraphQL API for flexible queries

4. **Historical Data**
   - Daily snapshots
   - Growth/decline analytics
   - Anomaly detection

## Troubleshooting

### No Balance Data Showing

1. Check RPC configuration in `.env`
2. Verify database connection
3. Run manual balance update script
4. Check backend logs for errors

### Price Data Not Updating

1. Verify CoinGecko API key (if using)
2. Check rate limits (free tier: 10-50 calls/minute)
3. Prices are cached for 5 minutes by design

### Slow Performance

1. Use Alchemy or Infura instead of public RPC
2. Reduce number of tokens being tracked
3. Implement Redis caching
4. Use batch RPC calls

## Architecture Decisions

### Why Right-Side Drawer?

- Maintains context of current investigation
- Allows comparison between entities
- Reduces navigation fatigue
- Professional AML workflow pattern

### Why MySQL for MVA Data?

- Structured financial data fits relational model
- Easy aggregation and reporting
- Existing infrastructure
- Good performance for time-series queries

### Why Not a Risk Engine?

MVA is **intelligence**, not **risk assessment**:
- Provides factual on-chain data
- No centralized scoring
- No alert orchestration
- Investigator makes decisions

This aligns with professional AML workflows where analysts interpret intelligence rather than relying on automated risk scores.

## Contributing

When adding new intelligence mechanisms:

1. Add a new tab in `EntityIntelligenceWorkspace.jsx`
2. Create a new component in `components/intelligence/`
3. Add backend routes in `routes/`
4. Update this documentation

## License

Part of the Crypto AML Tracker project.
