# Multi-Chain ETL Usage Guide

## Quick Start

### Extract from Ethereum (default)
```bash
python -m aml_pipeline.pipelines.run_etl \
  --start-block 21000000 \
  --batch 100
```

### Extract from Other EVM Chains

**Polygon**
```bash
python -m aml_pipeline.pipelines.run_etl \
  --chain polygon \
  --start-block 50000000 \
  --batch 100
```

**Binance Smart Chain (BSC)**
```bash
python -m aml_pipeline.pipelines.run_etl \
  --chain bsc \
  --start-block 30000000 \
  --batch 100
```

**Arbitrum**
```bash
python -m aml_pipeline.pipelines.run_etl \
  --chain arbitrum \
  --start-block 180000000 \
  --batch 100
```

**Base**
```bash
python -m aml_pipeline.pipelines.run_etl \
  --chain base \
  --start-block 0 \
  --batch 100
```

## Environment Setup

Set RPC endpoints via environment variables (optional - falls back to config defaults):

```bash
# Ethereum (default)
export ALCHEMY_RPC="https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY"

# Polygon
export POLYGON_RPC="https://polygon-rpc.com"

# BSC
export BSC_RPC="https://bsc-dataseed.bnbchain.org"

# Arbitrum
export ARBITRUM_RPC="https://arb1.arbitrum.io/rpc"

# Base
export BASE_RPC="https://mainnet.base.org"
```

## Python API Usage

```python
from aml_pipeline.pipelines import daily_pipeline

# Extract from Polygon
start_block, end_block = daily_pipeline.run_daily_extract(
    chain="polygon",
    start_block=50000000,
    batch_size=100
)

# Full pipeline with extraction, clustering, and analytics for BSC
results = daily_pipeline.run_daily_pipeline(
    chain="bsc",
    start_block=30000000,
    batch_size=100,
    run_clustering=True,
    run_placement=True,
    run_layering=True,
    run_integration=True
)
```

## Key Features

### Per-Chain Isolation
- Each chain's data is completely separated in the database
- Transactions filtered by `chain_name` at each pipeline stage
- Addresses prefixed with chain context (e.g., `"polygon:0xabc..."`)
- Clustering graphs namespaced by chain

### Backward Compatibility
- Default chain is always Ethereum (`chain="ethereum"`)
- Existing code without chain parameter works unchanged
- Database migration is additive (no breaking changes)

### Chain Metadata Tracking
Result dataclasses now include chain information:

```python
placement_result: PlacementAnalysisResult
  ├─ chain_name: str  # e.g., "polygon", "bsc"
  └─ [other fields...]

layering_result: LayeringAnalysisResult
  ├─ chain_name: str  # e.g., "arbitrum"
  └─ [other fields...]

integration_result: IntegrationAnalysisResult
  ├─ chain_name: str  # e.g., "base"
  └─ [other fields...]
```

## Database Fields

### Transactions Table (`aml_transactions`)
```sql
chain_id              INT       -- EVM chain ID (1=Ethereum, 56=BSC, 137=Polygon, etc.)
chain_name            VARCHAR   -- Chain name (ethereum, bsc, polygon, arbitrum, base)
blockchain_type       VARCHAR   -- 'EVM' for all currently supported chains
native_asset_symbol   VARCHAR   -- Native symbol (ETH, MATIC, BNB, ARB, ETH)
```

### Addresses Table (`aml_addresses`)
```sql
chain_name            VARCHAR   -- Part of composite primary key with address
```

### Wallet Clusters (`wallet_clusters`)
```sql
chain_name            VARCHAR   -- Cluster's chain context
```

### Analysis Results
- `placement_analysis_runs` - placement results per chain
- `layering_analysis_runs` - layering results per chain  
- `integration_analysis_runs` - integration results per chain

## Monitoring & Debugging

### Check Chain Processing
```bash
# View extraction logs
tail -f logs/aml_pipeline.log | grep "chain="

# Check transaction counts per chain
mysql -e "SELECT chain_name, COUNT(*) as tx_count FROM aml_transactions GROUP BY chain_name;"
```

### Verify Chain Data Integrity
```python
from aml_pipeline.etl.extract import get_extractor
from aml_pipeline.config import get_chain_config

# Test chain connectivity
cfg = get_chain_config("polygon")
extractor = get_extractor("polygon", cfg)
latest_block = extractor.get_latest_block_number()
print(f"Polygon latest block: {latest_block}")
```

## Supported Chains

| Chain | Chain ID | Type | Status |
|-------|----------|------|--------|
| Ethereum | 1 | EVM | ✓ Supported |
| BSC | 56 | EVM | ✓ Supported |
| Polygon | 137 | EVM | ✓ Supported |
| Arbitrum | 42161 | EVM | ✓ Supported |
| Base | 8453 | EVM | ✓ Supported |
| Bitcoin | - | UTXO | ✓ Supported (via existing extractor) |
| Tron | - | Other | ✓ Supported (via existing extractor) |

## Adding a New EVM Chain

To add support for a new EVM chain (e.g., Optimism):

1. **Update Chain Registry** (`AML/src/aml_pipeline/config.py`):
```python
from dataclasses import dataclass

@dataclass
class ChainConfig:
    name: str
    chain_id: int
    blockchain_type: str
    native_asset_symbol: str
    rpc_url: str

CHAINS: Dict[str, ChainConfig] = {
    # ... existing chains ...
    "optimism": ChainConfig(
        name="optimism",
        chain_id=10,
        blockchain_type="EVM",
        native_asset_symbol="ETH",
        rpc_url=os.getenv("OPTIMISM_RPC", "https://mainnet.optimism.io")
    ),
}
```

2. **Set RPC Environment Variable**:
```bash
export OPTIMISM_RPC="https://mainnet.optimism.io"
```

3. **Use the New Chain**:
```bash
python -m aml_pipeline.pipelines.run_etl --chain optimism --start-block 0 --batch 100
```

## Performance Considerations

### Chain Processing Time
- Initial extract: 5-10 seconds per 100 blocks (network dependent)
- Transform + Load: 2-5 seconds per 10k transactions
- Clustering: 10-60 seconds depending on data volume
- Analytics: 30-120 seconds depending on transaction count

### Memory Usage
- Per-chain buffer: ~500MB for active transactions
- Graph clustering: ~1GB for 1M addresses
- Scaling: Memory usage scales linearly with transaction volume

### Optimization Tips
- Process chains sequentially to avoid RPC rate limiting
- Use larger batch sizes (1000+) for faster extraction if RPC allows
- Monitor database indexes for query performance
- Archive old chain data to separate tables for cold storage

## Troubleshooting

### Issue: "Chain not found in registry"
**Solution**: Verify chain name matches supported list. Use `ethereum`, `bsc`, `polygon`, `arbitrum`, or `base`.

### Issue: "Failed to fetch RPC endpoint"
**Solution**: 
- Verify environment variable is set: `echo $POLYGON_RPC`
- Check RPC endpoint is accessible: `curl $POLYGON_RPC`
- Review config defaults in `AML/src/aml_pipeline/config.py`

### Issue: "Mixed chain data in results"
**Solution**: Verify transaction filtering is working:
```bash
mysql -e "SELECT DISTINCT chain_name FROM aml_transactions WHERE block_number > 50000000;"
```

### Issue: "No transactions found for chain"
**Solution**: 
- Verify block range contains transactions for that chain
- Check that extraction completed: `grep "chain=polygon" logs/aml_pipeline.log`
- Verify RPC endpoint availability

## Next Steps

1. **Test multi-chain extraction**: Run extracts for 2-3 different chains
2. **Verify data isolation**: Ensure no cross-chain data mixing
3. **Monitor performance**: Track extraction, transform, and analysis times
4. **Deploy to production**: Follow standard deployment procedure
5. **Document chain-specific policies**: Update risk scoring per chain if needed

## Related Documentation

- [Implementation Summary](MULTI_CHAIN_IMPLEMENTATION_SUMMARY.md) - Technical architecture
- [README.md](../README.md) - General project documentation
- [Config Reference](AML/src/aml_pipeline/config.py) - Chain configuration
