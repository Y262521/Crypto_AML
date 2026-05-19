# Crypto AML System Components Analysis

## Overview

This is a comprehensive Ethereum-based Anti-Money Laundering (AML) system that detects suspicious wallet behaviors across three money laundering stages using advanced clustering and graph analysis algorithms.

---

## 1. TRANSACTION TABLE / TRANSACTIONS

### Purpose
Core data structure that stores all Ethereum transaction data extracted from blockchain blocks.

### Database Schema (MariaDB)

```sql
CREATE TABLE transactions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    tx_hash VARCHAR(66) NOT NULL UNIQUE,
    from_address VARCHAR(64),
    to_address VARCHAR(64),
    value_eth DECIMAL(38,18) NOT NULL DEFAULT 0,
    timestamp DATETIME,
    block_number BIGINT NOT NULL,
    is_contract_call TINYINT(1) NOT NULL DEFAULT 0,
    gas_used BIGINT,
    status TINYINT,
    
    -- Indexes
    KEY idx_transactions_block_number
    KEY idx_transactions_timestamp
    KEY idx_transactions_from_address
    KEY idx_transactions_to_address
    KEY idx_transactions_value_eth
)
```

### Related Tables

#### **addresses** table
- Stores address-level metadata (contract flag, first/last seen, balances, cluster assignment)
- Links addresses to wallet clusters via `cluster_id` foreign key
- Tracks transaction counts and total inbound/outbound values

#### **wallet_clusters** table
- Groups related addresses together as a single entity
- Stores cluster size, total balance, risk level, label status
- Links to owner_list for known wallet identification

#### **graph_edges** table (from ETL pipeline)
- Stores transaction relationships between addresses
- Used by Neo4j for graph analysis and visualization
- Contains normalized transaction data for efficient graph traversal

### Data Flow
1. **Extract**: Raw Ethereum blocks → MongoDB (raw_blocks + raw_transactions collections)
2. **Transform**: Raw transactions → CSV files (transactions.csv, graph_edges.csv)
3. **Load**: CSV → MariaDB transaction table + Neo4j graph database
4. **Analysis**: Clustering engine reads transaction data → builds in-memory graph → identifies clusters

### Transaction Record Structure (Python)
```python
@dataclass
class TxRecord:
    tx_hash: str
    block_number: int
    timestamp: float
    from_address: str
    to_address: str
    value_eth: float
    is_contract_call: bool
    gas_used: int
    status: int
    input_method_id: str = ""  # For contract interaction detection
```

---

## 2. WALLET CLUSTERING

### Purpose
Identifies groups of addresses likely controlled by the same entity using behavioral heuristics.

### Clustering Engine Architecture

**File**: `AML/src/aml_pipeline/clustering/engine.py`

The ClusteringEngine orchestrates:
1. Load transactions via BlockchainAdapter (EthereumAdapter)
2. Build directed multigraph from transactions (NetworkX)
3. Run all heuristics in parallel (thread pool, max 4 workers)
4. Merge detected links using Union-Find algorithm
5. Compile cluster evidence and compute indicators
6. Persist results to MySQL

### Clustering Heuristics (9 Total)

#### **1. Deposit Address Reuse Heuristic**
- **Algorithm**: Identifies forwarding addresses used by multiple sources
- **Pattern**: Multiple source → relay address → single destination (exchange)
- **Confidence**: Based on:
  - Time proximity (forwarding window: typically 30 minutes)
  - Value similarity (absolute tolerance in ETH)
  - Unique source count
- **Use Case**: Exchange deposit cluster linking
- **Test Pattern**:
  ```
  u1 → deposit → exchange
  u2 → deposit → exchange  (same deposit address)
  ```

#### **2. Coordinated Cashout Heuristic**
- **Algorithm**: Links addresses sending similar amounts to same collector
- **Pattern**: Similar values → same receiver (cashout collector) within time window
- **Confidence**: Based on:
  - Value similarity ratio (configurable: default 0.05 or 5%)
  - Temporal proximity (cashout window: default 5 minutes)
  - Number of coordinated senders (2–20)
- **Use Case**: Multi-wallet cash-out to exchange/collector
- **Test Pattern**:
  ```
  a1 → collector (1.0 ETH, time=10)
  a2 → collector (1.02 ETH, time=40)   (similar amounts, same collector)
  ```

#### **3. Common Funder Heuristic**
- **Algorithm**: Links recipients funded by same source with shared cash-out behavior
- **Pattern**: treasury → a1 → sink, treasury → a2 → sink
- **Confidence**: Based on:
  - Shared funder (inbound source)
  - Shared operational sinks (outbound destination)
  - Pattern size (2–20 nodes)
- **Use Case**: Funded wallet networks (airdrops, distribution campaigns)
- **Test Pattern**:
  ```
  treasury → a1 → sink
  treasury → a2 → sink    (same funder and sink)
  ```

#### **4. Behavioral Similarity Heuristic**
- **Algorithm**: Links addresses with high overlap in counterparties
- **Method**: Jaccard similarity on directional transaction partners
- **Confidence Scoring**:
  - Direct threshold: ≥ N shared counterparties (default: 3)
  - High overlap: Jaccard similarity ≥ 75% (even with <3 shared)
- **Use Case**: Operational behavior matching (e.g., exchanges used)
- **Test Pattern**:
  ```
  a1 → x, y
  a2 → x, y    (high overlap in counterparties)
  ```

#### **5. Contract Interaction Heuristic**
- **Algorithm**: Groups addresses that interact with the same contracts
- **Pattern**: Multiple source → contract → multiple targets
- **Confidence**: Based on:
  - Unique contract count
  - Community size/density
  - Value flows through contracts
- **Use Case**: DeFi yield farming, smart contract abuse

#### **6. Token Flow Heuristic**
- **Algorithm**: Detects coordinated ERC-20 token movements
- **Pattern**: Same token transfers in similar patterns/times
- **Confidence**: Based on:
  - Token similarity
  - Flow direction consistency
  - Temporal alignment

#### **7. Temporal Heuristic**
- **Algorithm**: Links addresses with temporally clustered activity
- **Pattern**: Synchronized transaction timing
- **Confidence**: Based on:
  - Activity window overlap
  - Burst pattern similarity
  - Time-of-day patterns

#### **8. Fan Pattern Heuristic**
- **Algorithm**: Detects fan-in/fan-out redistribution patterns
- **Pattern**: Many → one → many (deposit then distribution)
- **Confidence**: Based on:
  - Branching factor
  - Value preservation
  - Temporal structure

#### **9. Loop Detection Heuristic**
- **Algorithm**: Identifies circular transaction patterns
- **Pattern**: a → b → c → a (value rotation)
- **Confidence**: Based on:
  - Cycle count
  - Value consistency
  - Timing patterns

### Union-Find Merging

After heuristics run, detected address pairs are merged using Union-Find:
- **Input**: List of (address_a, address_b) links from each heuristic
- **Process**: 
  1. Normalize pairs (canonical ordering)
  2. Union-Find data structure groups connected components
  3. Each connected component = 1 cluster
- **Output**: Deterministic cluster IDs based on sorted member addresses

### Cluster Indicators

For each cluster, compute behavioral metrics:

```python
{
    "size": cluster_member_count,
    "total_eth_volume": total_value_across_all_tx,
    "internal_eth_volume": value_within_cluster_txs,
    "total_in": sum_of_all_inbound_values,
    "total_out": sum_of_all_outbound_values,
    "net_balance": total_in - total_out,
    "total_tx_count": all_transaction_count,
    "internal_tx_count": within_cluster_transaction_count,
    "contract_call_count": smart_contract_interactions,
    "time_span_seconds": first_tx_to_last_tx_duration,
    "min_shared_counterparties": configured_threshold
}
```

### Configuration Parameters
- `clustering_min_shared_counterparties`: 3 (for behavioral similarity)
- `clustering_cashout_window_seconds`: 300 (5 minutes)
- `clustering_pass_through_window_seconds`: 1800 (30 minutes)
- `clustering_amount_similarity_ratio`: 0.05 (5%)
- `clustering_max_pattern_size`: 20 (max nodes in a pattern)
- `clustering_min_transfer_value_eth`: 0.001

### Output

**wallet_clusters** table + evidence in **cluster_evidence**:
```sql
wallet_clusters:
  id (cluster_id)
  cluster_size
  total_balance
  risk_level
  label_status

cluster_evidence:
  cluster_id
  heuristic_name (e.g., "deposit_address_reuse")
  evidence_text
  confidence (0.0–1.0)
```

---

## 3. PLACEMENT DETECTION

### Purpose
Identifies the first stage of money laundering where illicit funds enter the financial system through placement activity (structuring, smurfing, mixing).

### Files
- **Engine**: `AML/src/aml_pipeline/analytics/placement.py`
- **Tests**: `AML/tests/test_placement_detection.py`

### Placement Analysis Engine

Inherits from ClusteringEngine, adds placement-specific detection:

```python
class PlacementAnalysisEngine(ClusteringEngine):
    def run(self) -> PlacementAnalysisResult:
        # 1. Run clustering (wallet grouping)
        # 2. Validate existing clusters for split entities
        # 3. Detect placement behaviors (below)
        # 4. Identify placement origins (trace to source)
        # 5. Generate alerts + persistence
```

### Placement Entity Definition

A **PlacementEntity** represents a suspected money laundering entity at placement stage:

```python
@dataclass
class PlacementEntity:
    entity_id: str                    # Unique entity identifier
    entity_type: str                  # "placement" | "collector"
    addresses: list[str]              # All addresses in entity
    validation_status: str            # "new" | "enhanced" | "confirmed"
    validation_confidence: float      # 0.0–1.0 score
    source_kind: str                  # "clustering" | "enhanced"
    source_cluster_ids: list[str]     # Backing cluster IDs
    first_seen_at: float              # Earliest transaction timestamp
    last_seen_at: float               # Latest transaction timestamp
    metrics: dict[str, Any]           # Behavioral + statistical data
```

### Placement Detection Algorithms

#### **1. Structuring Detection** (Smurfing Variant)
- **Pattern**: Multiple small, similar deposits to same collector
- **Indicators**:
  - Low variance in transaction amounts
  - Multiple inbound transactions within time window
  - Regular intervals
- **Configuration**:
  - `placement_structuring_window_minutes`: 30
  - `placement_structuring_min_tx_count`: 4
  - `placement_structuring_max_relative_variance`: 0.1 (10%)
- **Test Example**:
  ```
  fund_1 → collector (0.49 ETH)
  fund_2 → collector (0.50 ETH)
  fund_3 → collector (0.51 ETH)
  fund_4 → collector (0.50 ETH)
  
  → Confidence: HIGH (low variance = structuring)
  ```

#### **2. Smurfing Detection**
- **Pattern**: Many unique small-value senders to same collector
- **Indicators**:
  - High number of unique inbound senders (≥4)
  - Small per-transaction values
  - Young wallet age (most senders < 2 hours old)
- **Configuration**:
  - `placement_smurfing_min_unique_senders`: 4
  - `placement_smurfing_max_wallet_age_seconds`: 7200 (2 hours)
- **Use Case**: AML evasion via distributed small payments

#### **3. Micro-Funding Detection**
- **Pattern**: Accumulated small payments from diverse sources
- **Indicators**:
  - High transaction count (≥6)
  - Small per-TX value (≤0.1 ETH)
  - Total value accumulation (≥0.4 ETH)
  - Distributed sources
- **Configuration**:
  - `placement_micro_max_tx_eth`: 0.1
  - `placement_micro_min_tx_count`: 6
  - `placement_micro_min_total_eth`: 0.4

#### **4. Origin Trace Analysis**
- **Algorithm**: Backward trace through transaction graph to identify funding sources
- **Method**:
  1. Start from entity addresses
  2. Traverse inbound edges up to N hops
  3. Apply branching limit to control complexity
  4. Score paths by confidence (source service profile, behavior)
- **Configuration**:
  - `placement_origin_max_hops`: 3
  - `placement_origin_branching_limit`: 4
  - `placement_origin_service_tx_count`: 100
  - `placement_origin_service_degree`: 50

#### **5. Behavior Highlight Selection**
- **Logic**: Rank and display 1–3 dominant behaviors based on confidence
- **Modes**:
  - **Dominant**: One behavior >15% above others (show 1)
  - **Paired**: Two behaviors within 15% gap, third trails (show 2)
  - **Balanced**: All three behaviors within 6% gap (show all 3)

### Database Schema

```sql
placement_runs:
  id (run_id VARCHAR(64))
  source VARCHAR(32)
  status VARCHAR(32)
  created_at TIMESTAMP

placement_entities:
  id BIGINT
  run_id VARCHAR(64)
  entity_id VARCHAR(64)
  entity_type VARCHAR(16)
  validation_status VARCHAR(32)
  validation_confidence DECIMAL(6,4)
  source_kind VARCHAR(32)
  metrics_json LONGTEXT

placement_entity_addresses:
  run_id, entity_id, address

placement_behaviors:
  run_id, entity_id
  behavior_type VARCHAR(32)           -- "structuring" | "smurfing" | "micro_funding"
  confidence_score DECIMAL(6,4)
  metrics_json LONGTEXT

placement_traces:
  run_id, entity_id
  origin_entity_id VARCHAR(64)
  path_entity_ids LONGTEXT (JSON)
  score DECIMAL(6,4)
  terminal_reason VARCHAR(32)

placement_detections:
  entity_id, entity_type
  confidence_score DECIMAL(6,4)
  behaviors_json LONGTEXT
  supporting_tx_hashes LONGTEXT
```

### Output Example

```python
PlacementDetection(
    entity_id="P-001",
    entity_type="placement",
    addresses=["0x...", "0x...", "0x..."],
    confidence_score=0.87,
    behavior_score=0.92,
    behaviors=["structuring", "micro_funding"],
    placement_score=0.85,
    reasons=[
        "4 transactions with 10% variance to same collector",
        "Accumulated 0.4 ETH from 6 sources in 30 minutes"
    ]
)
```

---

## 4. LAYERING DETECTION

### Purpose
Identifies the second stage of money laundering where funds are moved through multiple transactions/hops to obscure the trail (peeling chains, mixing, bridge hopping).

### Files
- **Engine**: `AML/src/aml_pipeline/analytics/layering/engine.py`
- **Detectors**: `AML/src/aml_pipeline/analytics/layering/detectors/`
- **Tests**: `AML/tests/test_layering_detection.py`

### Layering Analysis Engine

```python
class LayeringAnalysisEngine(PlacementAnalysisEngine):
    def __init__(self):
        self.detectors = [
            PeelingChainDetector(),
            MixingInteractionDetector(),
            BridgeHoppingDetector(),
            ShellWalletNetworkDetector(),
            HighDepthTransactionChainingDetector(),
        ]
    
    def run(self) -> LayeringAnalysisResult:
        # 1. Run placement analysis (seed generation)
        # 2. Build entity profiles (aggregated address data)
        # 3. Run 5 detectors in sequence
        # 4. Normalize and rank alerts
        # 5. Persist to database
```

### Layering Detectors (5 Total)

#### **1. Peeling Chain Detector**
- **Pattern**: Main value stream continues across N hops while smaller fragments are repeatedly shaved off
- **Algorithm**:
  1. For each seed address, trace forward transactions
  2. Identify "main" (largest) and "fragment" (shaved) outputs
  3. Repeat pattern detection across hops
  4. Score based on decay ratio and fragment consistency
- **Configuration**:
  - `layering_peel_min_hops`: 3
  - `layering_peel_max_hops`: 5
  - `layering_peel_min_decay_ratio`: 0.01 (main value ≥99% retained)
  - `layering_peel_min_fragment_ratio`: 0.05 (shaved ≥5%)
  - `layering_peel_max_fragment_ratio`: 0.25 (shaved ≤25%)
  - `layering_peel_max_time_gap_seconds`: 300 (5 minutes between hops)
- **Scoring**: Confidence = f(hop_count, decay_ratio, time_gaps, fragment_consistency)
- **Test Pattern**:
  ```
  seed → main_1 (9 ETH) + frag_1 (1 ETH)
  main_1 → main_2 (8 ETH) + frag_2 (1 ETH)
  main_2 → main_3 (7 ETH) + frag_3 (1 ETH)
  
  → Peeling confidence: HIGH
  ```

#### **2. Mixing Interaction Detector**
- **Pattern**: Addresses interact with known mixer/anonymity tool contracts
- **Algorithm**:
  1. Identify service registry categories (mixer, tornado, coinswap, etc.)
  2. For each seed, find transactions with/from mixing contracts
  3. Assess repeated use of same/different mixers
  4. Analyze follow-on "concealment" transactions
  5. Calculate ego-density (mixer network topology)
- **Configuration**:
  - `layering_mixing_min_interactions`: 2 (to/from mixer)
  - `layering_mixing_min_repeated_denominations`: 2
  - `layering_mixing_max_time_gap_seconds`: 300
  - `layering_mixing_min_ego_density`: 0.1
- **Confidence Components** (weighted):
  - Registry score: 30% (known mixer interaction)
  - Interaction score: 25% (frequency)
  - Denomination score: 20% (repeated amounts)
  - Topology score: 15% (mixer network density)
  - Delay score: 10% (timing patterns)
- **Service Registry**: Maintained list of known mixers/contracts
  - Examples: Tornado Cash, Aztec, 1inch, Balancer

#### **3. Bridge Hopping Detector**
- **Pattern**: Cross-chain bridge usage for value obscuration
- **Algorithm**:
  1. Identify bridge contract transactions (deposit/withdrawal pairs)
  2. Match deposits to withdrawals on same bridge
  3. Apply amount tolerance (±3%) and latency threshold
  4. Assess address freshness at withdrawal
- **Configuration**:
  - `layering_bridge_amount_tolerance_ratio`: 0.03 (±3%)
  - `layering_bridge_max_latency_seconds`: 86400 (24 hours)
  - `layering_bridge_min_pairs`: 1
- **Confidence Components**:
  - Amount similarity: 40%
  - Latency score: 30% (exponential decay)
  - Consistency: 20%
  - Freshness of withdrawal address: 10%
- **Known Bridge Prefixes**:
  ```
  0xd551234  # Binance Bridge
  0xa9d1e08  # Coinbase Bridge
  0x3f5ce5f  # Uniswap Bridge
  ```

#### **4. Shell Wallet Network Detector**
- **Pattern**: Tightly connected network of intermediate wallets with high internal activity
- **Algorithm**:
  1. Build directed subgraph for seed addresses
  2. Identify communities (Louvain clustering)
  3. Calculate intra-community transaction density
  4. Score based on:
     - Community size (≥4 addresses)
     - Internal transaction ratio (≥70%)
     - Transaction density (≥0.2)
     - Temporal window consistency (≥2 windows)
- **Configuration**:
  - `layering_shell_window_seconds`: 120
  - `layering_shell_min_community_size`: 4
  - `layering_shell_min_internal_ratio`: 0.7
  - `layering_shell_min_density`: 0.2
  - `layering_shell_min_temporal_windows`: 2

#### **5. High-Depth Transaction Chaining Detector**
- **Pattern**: Long chains of sequential transactions with high value retention
- **Algorithm**:
  1. Trace transaction paths from seed addresses
  2. Measure path depth (number of hops)
  3. Calculate value retention (output/input ratio)
  4. Score paths on:
     - Depth (4–5 hops optimal)
     - Value preservation (≥70%)
     - Temporal consistency
     - Branching factor (≤2)
- **Configuration**:
  - `layering_depth_max_hops`: 5
  - `layering_depth_min_hops`: 4
  - `layering_depth_branching_limit`: 2
  - `layering_depth_min_value_retention`: 0.7
  - `layering_depth_max_latency_seconds`: 300
  - `layering_depth_min_score`: 0.5

### Database Schema

```sql
layering_runs:
  id, generated_at, source, placement_run_id

layering_entities:
  id, run_id, entity_id, entity_type
  validation_status, validation_confidence

layering_detector_hits:
  run_id, entity_id
  detector_type (peeling_chain | mixing_interaction | bridge_hopping | shell_wallets | high_depth)
  confidence_score, summary
  score_components_json
  metrics_json

layering_evidence:
  run_id, entity_id, detector_type
  evidence_type (path | interaction | bridge | community)
  metrics_json, tx_hashes_json

layering_bridge_pairs:
  run_id, entity_id
  deposit_tx, withdrawal_tx
  latency_seconds, confidence_score

layering_alerts:
  run_id, entity_id
  entity_type, addresses
  layering_score, confidence_score
  detector_summary_json
```

### Output Example

```python
LayeringDetection(
    entity_id="L-042",
    entity_type="layering",
    detector_type="peeling_chain",
    confidence_score=0.81,
    addresses=["0xMain1", "0xMain2", "0xMain3"],
    summary="Peeling pattern observed across 3 hops",
    metrics={
        "hop_count": 3,
        "average_hop_gap_seconds": 145,
        "decay_ratio": 0.012,
        "fragment_ratio_avg": 0.11
    }
)
```

---

## 5. INTEGRATIONS

### Purpose
Identifies the third stage of money laundering where layered funds are reintegrated into the legitimate financial system (convergence, dormancy activation, terminal exits).

### Files
- **Engine**: `AML/src/aml_pipeline/analytics/integration/engine.py`
- **Types**: `AML/src/aml_pipeline/analytics/integration/types.py`

### Integration Analysis Engine

```python
class IntegrationAnalysisEngine:
    def run(self) -> IntegrationAnalysisResult:
        # 1. Load transactions
        # 2. Run 5 integration detectors
        # 3. Aggregate confidence scores from placement + layering
        # 4. Generate alerts with confidence aggregation
        # 5. Persist to database
```

### Integration Detection Algorithms (5 Total)

#### **1. Convergence / Fan-In Detection**
- **Pattern**: Multiple previously isolated addresses funnel into single collector
- **Algorithm**:
  1. Identify "sinks" (high-indegree nodes receiving from many sources)
  2. Count unique incoming senders
  3. Assess value aggregation
- **Configuration**:
  - `DEFAULT_CONVERGENCE_MIN_SENDERS`: 5 (minimum unique sources)
- **Confidence**: Based on:
  - Sender count
  - Value concentration
  - Behavioral consistency
- **Use Case**: Final cash-out to exchange exit point

#### **2. Dormancy-to-Activation Pattern**
- **Pattern**: Long-idle wallets suddenly activate with large transactions
- **Algorithm**:
  1. Calculate time since last transaction (dormancy duration)
  2. Measure activation value
  3. Compare to historical baseline
- **Configuration**:
  - `DEFAULT_DORMANCY_SECONDS`: 30 days (2,592,000 seconds)
  - `DEFAULT_DORMANCY_MIN_ETH`: 1.0 (activation threshold)
- **Confidence**: Based on:
  - Dormancy length
  - Activation value magnitude
  - Activity velocity change
- **Use Case**: Sleeper wallets activated for final cash-out

#### **3. Terminal Node Attribution (Exit Detection)**
- **Pattern**: Funds flowing to known exchange exit addresses
- **Algorithm**:
  1. Match addresses to known exchange/CEX prefixes
  2. Trace all inbound value to exit node
  3. Calculate pathway confidence
- **Known Exit Prefixes**:
  ```python
  0xd551234  # Binance
  0xa9d1e08  # Coinbase
  0x3f5ce5f  # Binance 2
  0xbe0eb53  # Binance 3
  0x564286   # Binance 4
  0x4e9ce36  # Binance 5
  ```
- **Confidence**: Based on:
  - Address match confidence
  - Pathway consistency
  - Value preservation

#### **4. Value Reaggregation Scrutiny**
- **Pattern**: Fragmented values recombined before final exit
- **Algorithm**:
  1. Identify addresses with multiple inbound flows
  2. Calculate input fragmentation (number of sources)
  3. Measure reaggregation ratio (output / total_input)
- **Configuration**:
  - `DEFAULT_REAGGREGATION_MIN_INPUTS`: 4 (sources)
  - `DEFAULT_REAGGREGATION_MIN_RATIO`: 0.70 (70% of input exits)
- **Confidence**: Based on:
  - Input count (higher = more fragmentation)
  - Reaggregation efficiency
  - Timing consistency
- **Use Case**: Sophisticated layering with recombination before exit

#### **5. Confidence Aggregation Scoring**
- **Method**: Combines signals from all 3 stages (placement + layering + integration)
- **Formula**:
  ```
  final_confidence = weighted_sum(
      placement_score * 0.30,
      layering_score * 0.35,
      integration_score * 0.35
  )
  ```
- **Output**: Single risk score 0.0–1.0 for entity

### Database Schema

```sql
integration_runs:
  id, generated_at, source, layering_run_id

integration_convergence_alerts:
  run_id, destination_address
  sender_count, total_value_eth
  confidence_score, tx_count

integration_dormancy_alerts:
  run_id, wallet_address
  dormancy_seconds, activation_value_eth
  confidence_score

integration_exit_alerts:
  run_id, exit_address
  inbound_value_eth, confidence_score
  exchange_prefix VARCHAR(32)

integration_reaggregation_alerts:
  run_id, aggregator_address
  input_count, reaggregation_ratio
  confidence_score

integration_alerts (main):
  run_id, entity_id
  placement_score, layering_score, integration_score
  confidence_score (aggregated)
  signals_json
```

---

## FRONTEND INTEGRATIONS

### Architecture

**Technology**: React (Vite) + FastAPI backend

### System Flow

```
User Interface (React) → Placement/Layering/Integration Pages
                        ↓
                Click "Analyze" Button
                        ↓
        EntityIntelligenceWorkspace Component
                        ↓
            MarketValueAnalysis Tab (Primary)
                        ↓
        Backend API Routes (/api/mva/*)
                        ↓
        BalanceAggregator Service
                        ↓
        CoinGecko API + Blockchain RPC nodes
```

### Key Integration Points

#### **1. Entity Link Component** (`EntityLink.jsx`)
- **Purpose**: Clickable address/cluster links
- **Props**:
  ```jsx
  <EntityLink
    entityId={address}
    entityType="address" | "cluster"
    onClick={onOpenEntityWorkspace}
    displayText={optional_label}
  />
  ```
- **Styling**: Golden color (#C9A84C), underline on hover

#### **2. Entity Intelligence Workspace** (`EntityIntelligenceWorkspace.jsx`)
- **Purpose**: Right-panel intelligence dashboard
- **Tabs**:
  - Overview (entity metadata)
  - Market Value* (portfolio analysis)
  - Exchange Flow (transaction patterns)
  - Transaction Graph (Neo4j visualization)
  - Risk Assessment (placement/layering/integration scores)
- **Controls**: Close button, tab navigation

#### **3. Market Value Analysis Tab** (`MarketValueAnalysis.jsx`)
- **Components**:
  - Portfolio Summary Cards (total assets, allocation %)
  - Asset Allocation Pie Chart (Recharts)
  - Token Holdings Table (sortable by symbol, amount, USD value)
  - Historical Value Chart (time-series, price × holdings)
  - Intelligence Flags (AML signals)
- **Data Source**: `GET /api/mva/cluster/{cluster_id}` or `GET /api/mva/address/{address}`

#### **4. Backend API Routes** (`routes/mva.py`)
- **Endpoints**:
  ```
  GET /api/mva/cluster/{cluster_id}
    → Aggregate portfolio for all cluster members
    → Return: { total_eth, total_usd, asset_allocation, holdings[] }
  
  GET /api/mva/address/{address}
    → Fetch balances (ETH + ERC20)
    → Return: { eth_balance, erc20_holdings[], risk_flags }
  
  GET /api/mva/history/{entity_id}
    → Fetch historical snapshots (daily)
    → Return: [{ timestamp, total_usd, allocation[] }]
  
  POST /api/mva/refresh
    → Force balance cache refresh
    → Trigger balance aggregation service
  ```

#### **5. Balance Aggregator Service** (`balance_aggregator.py`)
- **Purpose**: Fetch live Ethereum balances and price data
- **Methods**:
  ```python
  fetch_eth_balance(address) → Decimal
  fetch_erc20_balance(address, contract, decimals) → Decimal
  fetch_token_prices() → dict[token_address] = usd_price
  aggregate_cluster_portfolio(cluster_id, addresses) → {
      total_eth,
      total_usd,
      assets: [
          {symbol, amount, decimals,
           contract_address, usd_value}
      ]
  }
  update_address(address) → stores in wallet_balances table
  update_cluster(cluster_id, addresses) → aggregates all members
  ```
- **RPC Provider**: Infura / Alchemy (configured in .env)
- **Price Source**: CoinGecko API (free tier)

### Page Integration Examples

#### **Placement Page**
```jsx
export default function Placement({ onOpenEntityWorkspace }) {
  return (
    <table>
      {placements.map(entity => (
        <tr key={entity.entity_id}>
          <td>
            <EntityLink
              entityId={entity.entity_id}
              entityType="placement"
              onClick={onOpenEntityWorkspace}
            />
          </td>
          <td>{entity.validation_confidence.toFixed(2)}</td>
          <td>
            <AnalyzeButton
              entityId={entity.entity_id}
              entityType="placement"
              onAnalyze={(id, type, analysisType) =>
                onOpenEntityWorkspace(id, type, 'Placement', analysisType)
              }
            />
          </td>
        </tr>
      ))}
    </table>
  );
}
```

#### **Layering Page**
```jsx
export default function Layering({ onOpenEntityWorkspace }) {
  return (
    <div className="layering-container">
      {/* Similar structure to Placement */}
      {alerts.map(alert => (
        <div key={alert.entity_id}>
          <button onClick={() => onOpenEntityWorkspace(
            alert.entity_id, 'layering', 'Layering'
          )}>
            View Details
          </button>
        </div>
      ))}
    </div>
  );
}
```

#### **Integration Page**
```jsx
export default function Integration({ onOpenEntityWorkspace }) {
  return (
    <div className="integration-alerts">
      {convergenceAlerts.map(alert => (
        <EntityLink
          entityId={alert.destination_address}
          entityType="address"
          onClick={onOpenEntityWorkspace}
        />
      ))}
    </div>
  );
}
```

### App.jsx Central Hub
```jsx
function App() {
  const [entityWorkspace, setEntityWorkspace] = useState(null);
  
  const openEntityWorkspace = (entityId, entityType, sourcePage, analysisType) => {
    setEntityWorkspace({
      entityId, entityType, sourcePage, analysisType
    });
  };
  
  return (
    <div>
      <Router>
        <Routes>
          <Route path="/placement"
            element={<Placement onOpenEntityWorkspace={openEntityWorkspace} />}
          />
          <Route path="/layering"
            element={<Layering onOpenEntityWorkspace={openEntityWorkspace} />}
          />
          <Route path="/integration"
            element={<Integration onOpenEntityWorkspace={openEntityWorkspace} />}
          />
        </Routes>
      </Router>
      
      {entityWorkspace && (
        <EntityIntelligenceWorkspace
          {...entityWorkspace}
          onClose={() => setEntityWorkspace(null)}
        />
      )}
    </div>
  );
}
```

---

## DATABASE RELATIONSHIPS

```
owner_list
    ↓ (1:N)
owner_list_addresses

wallet_clusters
    ↄ (1:N to addresses)
addresses (has cluster_id FK)
    ↓ (1:N)
cluster_evidence

transactions
    ↓ (1:N to)
addresses (via from_address, to_address)

placement_runs
    ↓ (1:N)
placement_entities
    ↓ (1:N)
placement_entity_addresses
    ↓ (1:1 to)
placement_behaviors
placement_detections
placement_labels

layering_runs
    ↓ (1:N)
layering_entities → layering_detector_hits
               → layering_evidence
               → layering_bridge_pairs
               → layering_alerts

integration_runs
    ↓ (1:N)
integration_convergence_alerts
integration_dormancy_alerts
integration_exit_alerts
integration_reaggregation_alerts
integration_alerts (main)
```

---

## CONFIGURATION & TUNING

### Critical Parameters by Component

**Clustering**:
- `clustering_min_shared_counterparties`: 3
- `clustering_cashout_window_seconds`: 300
- `clustering_max_pattern_size`: 20

**Placement**:
- `placement_structuring_window_minutes`: 30
- `placement_structuring_min_tx_count`: 4
- `placement_origin_max_hops`: 3

**Layering**:
- `layering_peel_min_hops`: 3
- `layering_peel_max_hops`: 5
- `layering_mixing_min_interactions`: 2

**Integration**:
- `DEFAULT_DORMANCY_SECONDS`: 2,592,000 (30 days)
- `DEFAULT_CONVERGENCE_MIN_SENDERS`: 5

All configurable in `config.py`.

---

## EXECUTION FLOW

```
ETL Pipeline:
  1. Extract: Ethereum blocks → MongoDB
  2. Transform: Blocks → CSV (transactions, graph_edges)
  3. Load: CSV → MySQL + Neo4j

Analysis Pipeline:
  1. ClusteringEngine.run()
     → Read transactions from MySQL
     → Build graph
     → Run 9 heuristics → Union-Find merge
     → Output: wallet_clusters + cluster_evidence
  
  2. PlacementAnalysisEngine.run()
     → Inherits clustering results
     → Run placement detectors (structuring, smurfing, micro)
     → Trace origins, validate clusters
     → Output: placement_entities, placement_detections
  
  3. LayeringAnalysisEngine.run()
     → Inherits placement results as seeds
     → Run 5 layering detectors
     → Output: layering_entities, layering_alerts
  
  4. IntegrationAnalysisEngine.run()
     → Inherits layering results
     → Run 5 integration detectors
     → Aggregate confidence from all 3 stages
     → Output: integration_alerts

Frontend:
  1. User navigates to Placement/Layering/Integration page
  2. Clicks "Analyze" → AnalyzeButton dropdown
  3. Selects "Market Value"
  4. EntityIntelligenceWorkspace opens
  5. MarketValueAnalysis tab loads
  6. Backend API fetches cluster/address balances
  7. BalanceAggregator queries RPC + CoinGecko
  8. Charts and tables render
```

---

## KEY METRICS & OUTPUTS

### Per Entity
- **Risk Score**: 0.0–1.0 (aggregated from all stages)
- **Entity Type**: placement | collector | layering | integration | address | cluster
- **Validation Status**: new | enhanced | confirmed
- **Supporting TX Count**: Evidence transaction count
- **First/Last Seen**: Temporal bounds
- **Associated Addresses**: All addresses in entity group
- **Behavioral Patterns**: Structuring, smurfing, peeling, mixing, etc.

### Confidence Breakdown
```
Placement Confidence = avg(structuring, smurfing, micro_funding)
Layering Confidence  = weighted_avg(peeling, mixing, bridge, shells, depth)
Integration Confidence = weighted_avg(convergence, dormancy, exit, reaggregation)
Final Score          = 0.30*placement + 0.35*layering + 0.35*integration
```

---

This comprehensive system enables detection of money laundering activities across the entire AML cycle using graph-based clustering, behavioral pattern recognition, and multi-stage confidence aggregation.
