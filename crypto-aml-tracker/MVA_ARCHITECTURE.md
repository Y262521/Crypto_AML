# Market Value Analysis (MVA) - Architecture Diagram

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    App.jsx (Main)                             │  │
│  │  • Entity Workspace State Management                          │  │
│  │  • openEntityWorkspace(entityId, type, source)               │  │
│  │  • closeEntityWorkspace()                                     │  │
│  └────────────┬─────────────────────────────────────────────────┘  │
│               │                                                      │
│               ├─► Placement Page ──┐                                │
│               ├─► Layering Page ───┤                                │
│               ├─► Integration Page ─┤  All receive:                 │
│               └─► Clusters Page ────┘  onOpenEntityWorkspace prop   │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │     EntityIntelligenceWorkspace.jsx (Right Drawer)           │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │  Tabs: [Overview] [Market Value*] [Exchange Flow] ...  │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │         MarketValueAnalysis.jsx                        │ │  │
│  │  │  • Portfolio Summary Cards                             │ │  │
│  │  │  • Allocation Pie Chart (Recharts)                     │ │  │
│  │  │  • Asset Holdings Table (sortable)                     │ │  │
│  │  │  • Historical Value Chart (Recharts)                   │ │  │
│  │  │  • Intelligence Flags                                  │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  └──────────────────────┬───────────────────────────────────────┘  │
│                         │                                            │
│                         │ API Calls                                  │
│                         ▼                                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │         transactionService.js (API Layer)                     │  │
│  │  • getClusterMVA(clusterId)                                   │  │
│  │  • getAddressMVA(address)                                     │  │
│  │  • getMVAHistory(entityId, type, days)                        │  │
│  └──────────────────────┬───────────────────────────────────────┘  │
└────────────────────────┼────────────────────────────────────────────┘
                         │
                         │ HTTP/JSON
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    main.py                                    │  │
│  │  • FastAPI app initialization                                 │  │
│  │  • Router registration: /api/mva                              │  │
│  │  • Schema initialization on startup                           │  │
│  └────────────┬─────────────────────────────────────────────────┘  │
│               │                                                      │
│               ▼                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              routes/mva.py (API Routes)                       │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │  GET /api/mva/cluster/{cluster_id}                     │ │  │
│  │  │  • Fetch cluster portfolio summary                     │ │  │
│  │  │  • Get member addresses                                │ │  │
│  │  │  • Aggregate asset holdings                            │ │  │
│  │  │  • Calculate allocation percentages                    │ │  │
│  │  │  • Generate intelligence flags                         │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │  GET /api/mva/address/{address}                        │ │  │
│  │  │  • Fetch address balances                              │ │  │
│  │  │  • Calculate summary metrics                           │ │  │
│  │  │  • Generate flags                                      │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │  GET /api/mva/history/{entity_id}                      │ │  │
│  │  │  • Fetch historical snapshots                          │ │  │
│  │  │  • Return time-series data                             │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │  ensure_mva_schema()                                   │ │  │
│  │  │  • Create tables if not exist                          │ │  │
│  │  │  • Set up indexes                                      │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  └────────────┬─────────────────────────────────────────────────┘  │
│               │                                                      │
│               ▼                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │      services/balance_aggregator.py (Core Service)           │  │
│  │  ┌────────────────────────────────────────────────────────┐ │  │
│  │  │  BalanceAggregator Class                               │ │  │
│  │  │  • fetch_eth_balance(address)                          │ │  │
│  │  │  • fetch_erc20_balance(address, contract, decimals)    │ │  │
│  │  │  • fetch_token_prices() → CoinGecko API               │ │  │
│  │  │  • fetch_address_balances(address)                     │ │  │
│  │  │  • aggregate_cluster_portfolio(cluster_id, addresses)  │ │  │
│  │  │  • update_address(address)                             │ │  │
│  │  │  • update_cluster(cluster_id, addresses)               │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  └────────────┬─────────────────────────────────────────────────┘  │
│               │                                                      │
│               ├─► Ethereum RPC (Alchemy/Infura)                     │
│               │   • eth_getBalance                                  │
│               │   • eth_call (ERC20 balanceOf)                      │
│               │                                                      │
│               ├─► CoinGecko API                                     │
│               │   • /simple/price?ids=...&vs_currencies=usd         │
│               │   • 5-minute cache                                  │
│               │                                                      │
│               └─► MySQL/MariaDB                                     │
│                   • wallet_balances                                 │
│                   • cluster_portfolios                              │
│                   • token_price_cache                               │
│                   • portfolio_history                               │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Balance Update Flow

```
┌─────────────┐
│   CLI Tool  │  python scripts/update_balances.py 0x123...
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│  BalanceAggregator.update_address(address)              │
├─────────────────────────────────────────────────────────┤
│  1. Fetch token prices from CoinGecko (cached)          │
│  2. Fetch ETH balance via eth_getBalance                │
│  3. Fetch ERC20 balances via eth_call (5 tokens)        │
│  4. Calculate USD values (balance × price)              │
│  5. Save to wallet_balances table                       │
└─────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│  BalanceAggregator.aggregate_cluster_portfolio()        │
├─────────────────────────────────────────────────────────┤
│  1. Query all balances for cluster addresses            │
│  2. SUM balances by token                               │
│  3. Calculate totals (ETH, stablecoins, etc.)           │
│  4. Save to cluster_portfolios table                    │
│  5. Create snapshot in portfolio_history                │
└─────────────────────────────────────────────────────────┘
```

### 2. Frontend Query Flow

```
┌──────────────────┐
│  User clicks     │
│  address/cluster │
└────────┬─────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  App.jsx: openEntityWorkspace(entityId, type, source)   │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  EntityIntelligenceWorkspace opens (right drawer)       │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  User clicks "Market Value" tab                         │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  MarketValueAnalysis.jsx                                │
│  • Calls getClusterMVA() or getAddressMVA()             │
│  • Calls getMVAHistory()                                │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Backend: GET /api/mva/cluster/{id}                     │
│  1. Query cluster_portfolios for summary                │
│  2. Query wallet_balances for assets                    │
│  3. Calculate allocation percentages                    │
│  4. Generate intelligence flags                         │
│  5. Return JSON response                                │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Frontend renders:                                      │
│  • Summary cards                                        │
│  • Pie chart (allocation)                               │
│  • Asset table                                          │
│  • Historical chart                                     │
│  • Intelligence flags                                   │
└─────────────────────────────────────────────────────────┘
```

## Database Schema

```sql
┌─────────────────────────────────────────────────────────┐
│  wallet_balances                                        │
├─────────────────────────────────────────────────────────┤
│  id                BIGINT AUTO_INCREMENT PRIMARY KEY    │
│  address           VARCHAR(42) NOT NULL                 │
│  token_symbol      VARCHAR(20) NOT NULL                 │
│  token_contract    VARCHAR(42)                          │
│  balance           DECIMAL(36, 18) NOT NULL             │
│  balance_usd       DECIMAL(20, 2) NOT NULL              │
│  updated_at        TIMESTAMP                            │
│                                                          │
│  INDEX idx_address (address)                            │
│  INDEX idx_token (token_symbol)                         │
│  UNIQUE (address, token_symbol, token_contract)         │
└─────────────────────────────────────────────────────────┘
                         │
                         │ Aggregated by cluster
                         ▼
┌─────────────────────────────────────────────────────────┐
│  cluster_portfolios                                     │
├─────────────────────────────────────────────────────────┤
│  id                   BIGINT AUTO_INCREMENT PRIMARY KEY │
│  cluster_id           VARCHAR(255) NOT NULL             │
│  total_value_usd      DECIMAL(20, 2) NOT NULL           │
│  eth_value_usd        DECIMAL(20, 2) NOT NULL           │
│  stablecoin_value_usd DECIMAL(20, 2) NOT NULL           │
│  defi_exposure_usd    DECIMAL(20, 2) NOT NULL           │
│  token_count          INT NOT NULL                      │
│  wallet_count         INT NOT NULL                      │
│  updated_at           TIMESTAMP                         │
│                                                          │
│  INDEX idx_cluster (cluster_id)                         │
│  UNIQUE (cluster_id)                                    │
└─────────────────────────────────────────────────────────┘
                         │
                         │ Historical snapshots
                         ▼
┌─────────────────────────────────────────────────────────┐
│  portfolio_history                                      │
├─────────────────────────────────────────────────────────┤
│  id                   BIGINT AUTO_INCREMENT PRIMARY KEY │
│  entity_id            VARCHAR(255) NOT NULL             │
│  entity_type          ENUM('address', 'cluster')        │
│  total_value_usd      DECIMAL(20, 2) NOT NULL           │
│  eth_value_usd        DECIMAL(20, 2) NOT NULL           │
│  stablecoin_value_usd DECIMAL(20, 2) NOT NULL           │
│  snapshot_at          TIMESTAMP NOT NULL                │
│                                                          │
│  INDEX idx_entity (entity_id, entity_type)              │
│  INDEX idx_snapshot (snapshot_at)                       │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  token_price_cache                                      │
├─────────────────────────────────────────────────────────┤
│  id                BIGINT AUTO_INCREMENT PRIMARY KEY    │
│  token_symbol      VARCHAR(20) NOT NULL                 │
│  token_contract    VARCHAR(42)                          │
│  price_usd         DECIMAL(20, 8) NOT NULL              │
│  updated_at        TIMESTAMP                            │
│                                                          │
│  INDEX idx_symbol (token_symbol)                        │
│  UNIQUE (token_symbol, token_contract)                  │
└─────────────────────────────────────────────────────────┘
```

## Component Hierarchy

```
App.jsx
├── Sidebar
├── Main Content Area
│   ├── Dashboard
│   ├── GraphExplorer
│   ├── Placement ──────────┐
│   ├── Layering ───────────┤
│   ├── Integration ────────┤  All pass onOpenEntityWorkspace
│   ├── Clusters ───────────┤
│   ├── Analytics           │
│   └── RiskIntelligence    │
│                            │
└── EntityIntelligenceWorkspace (Conditional Render)
    ├── Header
    │   ├── Entity Type Badge
    │   ├── Entity ID
    │   ├── Source Page
    │   └── Close Button
    ├── Tab Navigation
    │   ├── Overview (🔒 Coming Soon)
    │   ├── Market Value (✅ Implemented)
    │   ├── Exchange Flow (🔒 Coming Soon)
    │   ├── Holder Behavior (🔒 Coming Soon)
    │   ├── Profitability (🔒 Coming Soon)
    │   └── DeFi Exposure (🔒 Coming Soon)
    └── Tab Content
        └── MarketValueAnalysis
            ├── Portfolio Summary Cards (5)
            ├── Portfolio Allocation (Pie Chart)
            ├── Intelligence Flags
            ├── Historical Chart (Line Chart)
            └── Asset Holdings Table
```

## API Endpoints

```
/api/mva/
├── GET /cluster/{cluster_id}
│   ├── Query: cluster_portfolios, wallet_balances
│   ├── Returns: summary, assets, allocation, flags
│   └── Response Time: ~100-300ms
│
├── GET /address/{address}
│   ├── Query: wallet_balances
│   ├── Returns: summary, assets, allocation, flags
│   └── Response Time: ~50-150ms
│
└── GET /history/{entity_id}
    ├── Query: portfolio_history
    ├── Params: entity_type, days (default 30)
    ├── Returns: time-series data
    └── Response Time: ~50-100ms
```

## External Dependencies

```
┌─────────────────────────────────────────────────────────┐
│  Ethereum RPC Providers                                 │
├─────────────────────────────────────────────────────────┤
│  • Alchemy (Recommended)                                │
│    - Free: 300M compute units/month                     │
│    - eth_getBalance: ~10 CU                             │
│    - eth_call: ~26 CU                                   │
│                                                          │
│  • Infura                                               │
│    - Free: 100K requests/day                            │
│                                                          │
│  • Public RPC (Not recommended for production)          │
│    - Rate limited                                       │
│    - Unreliable                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  CoinGecko API                                          │
├─────────────────────────────────────────────────────────┤
│  • Free Tier: 10-50 calls/minute                        │
│  • Pro Tier: Higher limits with API key                 │
│  • Endpoint: /simple/price                              │
│  • Cache: 5 minutes (configurable)                      │
└─────────────────────────────────────────────────────────┘
```

## Performance Characteristics

```
┌─────────────────────────────────────────────────────────┐
│  Balance Update (Single Address)                        │
├─────────────────────────────────────────────────────────┤
│  • RPC Calls: 6 (1 ETH + 5 ERC20)                       │
│  • Time: ~2-5 seconds                                   │
│  • Bottleneck: RPC latency                              │
│  • Optimization: Parallel async calls                   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Cluster Aggregation (10 addresses)                     │
├─────────────────────────────────────────────────────────┤
│  • RPC Calls: 60 (6 per address)                        │
│  • Time: ~5-15 seconds (parallel)                       │
│  • Database Writes: 50-60 rows                          │
│  • Aggregation Query: <100ms                            │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Frontend Query (Cached Data)                           │
├─────────────────────────────────────────────────────────┤
│  • API Call: ~100-300ms                                 │
│  • Chart Rendering: ~50-100ms                           │
│  • Total Load Time: <500ms                              │
└─────────────────────────────────────────────────────────┘
```

## Security Considerations

```
┌─────────────────────────────────────────────────────────┐
│  Input Validation                                       │
├─────────────────────────────────────────────────────────┤
│  • Address format validation (0x + 40 hex chars)        │
│  • Cluster ID sanitization                              │
│  • SQL injection prevention (parameterized queries)     │
│  • Rate limiting on API endpoints                       │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  API Key Management                                     │
├─────────────────────────────────────────────────────────┤
│  • RPC keys in .env (not committed)                     │
│  • CoinGecko key in .env                                │
│  • Database credentials in .env                         │
│  • No keys in frontend code                             │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Data Privacy                                           │
├─────────────────────────────────────────────────────────┤
│  • No PII stored                                        │
│  • Only public blockchain data                          │
│  • Addresses are pseudonymous                           │
│  • No user tracking                                     │
└─────────────────────────────────────────────────────────┘
```

This architecture provides a solid foundation for the MVA system and can be extended with additional intelligence mechanisms in the future.
