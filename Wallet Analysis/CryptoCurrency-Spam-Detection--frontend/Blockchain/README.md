# Blockchain Integration Module

This folder contains a standalone Python package for blockchain data collection, indexing, and lightweight risk analysis.

## What is included

- ETH, BSC, Polygon, and Arbitrum RPC and explorer-backed connectors
- Bitcoin public API connector
- Transaction normalization and SQLite indexing
- DApp, bridge, mixer, and contract-interaction detectors
- Risk engine backed by a local flagged-address database and heuristics
- Sync scripts for public sanction and abuse feeds
- Importable scanner module for downstream integration
- Cross-chain scan orchestration and connector health checks
- Retry/backoff for network requests and bounded fallback scans

## Quick start

1. Create a virtual environment.
2. Install the package:

```bash
pip install -e .
```

3. Copy `.env.example` into your preferred environment file or export variables manually.
   If you have an Etherscan V2 key, set `EXPLORER_API_KEY`. The connectors will prefer explorer APIs when available, then use Blockscout where configured, and finally fall back to a bounded RPC scan.
4. Run the feed sync:

```bash
python -m blockchain_engine.scripts.sync_public_feeds
```

5. Run a scan:

```bash
python -m blockchain_engine.scripts.run_scan --chain ethereum --address 0x0000000000000000000000000000000000000000
```

6. Check all connectors:

```bash
python -m blockchain_engine.scripts.check_connectors
```

7. Run a cross-chain scan:

```bash
python -m blockchain_engine.scripts.run_cross_chain_scan --ethereum 0x0000000000000000000000000000000000000000 --bitcoin 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
```

## Package entrypoints

- `blockchain_engine.BlockchainScanner`
- `blockchain_engine.RiskEngine`
- `blockchain_engine.ScannerConfig`

## Architecture

The `blockchain_engine` is built with a modular architecture:
- **Connectors**: Abstracts blockchain-specific communication (EVM via RPC/Explorer, Bitcoin via public APIs).
- **Indexer**: SQLite-based local storage for normalized transaction data.
- **Detectors**: Logic for identifying specific behaviors (DApps, mixers, bots, smart contracts).
- **Risk Engine**: Heuristic-based scoring system for evaluating address safety.
- **Graph Analyzer**: Builds relationship graphs and performs address clustering.
- **Watchlist Manager**: Local database for managing user-defined flagged addresses.
- **Scanner**: High-level orchestrator that combines all modules for comprehensive screening and analysis.
- **API Layer**: Lightweight HTTP server exposing core functionality via JSON endpoints.

## Assumptions

1. **RPC Availability**: Assumes access to functional JSON-RPC endpoints for bytecode and balance checks.
2. **Normalized Data**: Assumes transactions can be normalized into a common format for cross-chain analysis.
3. **Static Labels**: Relies on public feeds (OFAC, BitcoinAbuse, etc.) and internal watchlists as primary ground truth.
4. **Behavioral Heuristics**: Uses statistical patterns (frequency, fan-out, timing) to infer entity types like bots and exchanges.

## Limitations

1. **Darknet Data**: Does not actively crawl darknet markets; relies on third-party public feeds for such data.
2. **RPC Constraints**: Free public RPC providers often rate-limit or restrict certain calls like `eth_getCode`, which may impact deterministic contract detection.
3. **Clustering Accuracy**: Behavioral clustering is heuristic-based and may produce false positives in highly active environments.
4. **Historical Depth**: Default scans are bounded by `MAX_RPC_SCAN_BLOCKS` to maintain performance unless an explorer API is used.

## API Endpoints

- `GET /screen?chain=...&address=...`: Quick screening against watchlists and entity labeling.
- `GET /risk?chain=...&address=...`: Detailed risk score with breakdown and reasons.
- `GET /explore/address?chain=...&address=...`: Transaction history and balance summary.
- `GET /explore/tx?tx_hash=...`: Individual transaction lookup.
- `GET /graph?chain=...&address=...`: Data for graph visualization (nodes and edges).
- `GET /cluster?chain=...&address=...`: Behavioral clustering results.
- `GET /alerts?chain=...&address=...`: Triggered alerts for suspicious activity.
- `GET /watchlist`: List current watchlist entries.
