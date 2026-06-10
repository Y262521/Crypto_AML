# Clustering Fix Verification Steps

## Quick Verification (Without Running)

### 1. Code Review - Verify the Fix is Applied

Check `AML/src/aml_pipeline/clustering/eth_adapter.py` line ~106:

**Should see:**
```python
def _count_mariadb_transactions(self) -> int:
    try:
        engine = get_maria_engine(self.cfg)
        with engine.connect() as conn:
            # CRITICAL: Must filter by chain_name...
            return int(
                conn.execute(
                    text("""
                        SELECT COUNT(*) FROM transactions
                        WHERE chain_name = :chain_name OR (chain_name IS NULL AND :chain_name = 'ethereum')
                    """),
                    {"chain_name": self.chain_name}
                ).scalar_one()
            )
```

**Should NOT see:**
```python
return int(
    conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar_one()
)
```

### 2. Compare with _iter_from_mariadb Method

Check `AML/src/aml_pipeline/clustering/eth_adapter.py` line ~140:

**Verify the WHERE clause matches:**
```python
def _iter_from_mariadb(self) -> Iterator[TxRecord]:
    # ...
    query = text(
        """
        SELECT ...
        FROM transactions
        WHERE chain_name = :chain_name OR (chain_name IS NULL AND :chain_name = 'ethereum')
        """
    )
```

**Both methods must use the same WHERE filter!**

### 3. Logic Flow Verification

The fix ensures this flow works correctly:

```
┌─────────────────────────────────────────────────────────┐
│ ClusteringEngine.run(source="auto")                     │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ EthereumAdapter.iter_transactions(source="auto")        │
│                                                          │
│  1. mariadb_count = _count_mariadb_transactions()       │
│     ├─ OLD BUG: SELECT COUNT(*) FROM transactions       │
│     │            Returns: 10000 (all chains)            │
│     │                                                    │
│     └─ NEW FIX: SELECT COUNT(*) FROM transactions       │
│                 WHERE chain_name = 'ethereum'           │
│                 Returns: 547 (only ethereum)            │
│                                                          │
│  2. if mariadb_count > 0:                               │
│     ├─ yield from _iter_from_mariadb()                  │
│     │  SELECT ... FROM transactions                     │
│     │  WHERE chain_name = 'ethereum'                    │
│     │  Returns: 547 ethereum transactions ✓             │
│     │                                                    │
│     └─ OLD BUG: Returns 0 transactions (mismatch!)      │
│        NEW FIX: Returns 547 transactions (matched!)     │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Clustering builds graph from 547 transactions           │
│ Finds clusters                                          │
│ Persists to database                                    │
└─────────────────────────────────────────────────────────┘
```

## Manual Test (When Ready to Run)

### Step 1: Check Current Database State

```bash
mysql -u hakim -phakim22 aml_clean -e "
SELECT 
    COALESCE(chain_name, 'NULL') as chain,
    COUNT(*) as tx_count
FROM transactions
GROUP BY chain_name;
"
```

**Expected output example:**
```
+----------+----------+
| chain    | tx_count |
+----------+----------+
| base     | 5000     |
| solana   | 3000     |
| ethereum | 547      |
+----------+----------+
```

This shows why the bug existed - multiple chains in one database.

### Step 2: Check Current Cluster State

```bash
mysql -u hakim -phakim22 aml_clean -e "
SELECT 
    chain_name,
    COUNT(*) as cluster_count
FROM wallet_clusters
GROUP BY chain_name;
"
```

**Before fix:** Might show ethereum with 0 clusters
**After fix:** Should show ethereum with some clusters

### Step 3: Run Clustering

```bash
cd AML
python scripts/run_analytics_only.py
```

**Expected output (before fix):**
```
Running clustering for ethereum
Clusters persisted: 0
```

**Expected output (after fix):**
```
Running clustering for ethereum
INFO - EthereumAdapter: reading 547 transactions from MariaDB
INFO - Building graph from 547 transactions
INFO - Running 9 heuristics in parallel
INFO - Clustering complete: 15 clusters found
INFO - Persisted 15 clusters to MySQL
Clusters persisted: 15
```

(Numbers are examples - actual values depend on your data)

### Step 4: Verify Database Was Updated

```bash
mysql -u hakim -phakim22 aml_clean -e "
SELECT COUNT(*) as ethereum_clusters
FROM wallet_clusters
WHERE chain_name = 'ethereum' OR (chain_name IS NULL AND 'ethereum' = 'ethereum');
"
```

**Expected:** Non-zero count

```bash
mysql -u hakim -phakim22 aml_clean -e "
SELECT COUNT(*) as clustered_addresses
FROM addresses
WHERE cluster_id IS NOT NULL;
"
```

**Expected:** Non-zero count

### Step 5: Verify Other Analytics Still Work

The script should continue with:
```
Running placement
Placement alerts: 548
Running layering
Layering alerts: 10
Running integration
Integration alerts: 4016
```

Numbers should be similar to before (they don't depend on clustering).

## Troubleshooting

### If clustering still returns 0:

1. **Check if you actually have Ethereum transactions:**
   ```sql
   SELECT COUNT(*) FROM transactions 
   WHERE chain_name = 'ethereum' OR (chain_name IS NULL AND 'ethereum' = 'ethereum');
   ```
   
   If this returns 0, you don't have Ethereum data - clustering correctly returns 0.

2. **Check if transactions have valid from/to addresses:**
   ```sql
   SELECT COUNT(*) FROM transactions
   WHERE (from_address IS NULL OR from_address = '' OR to_address IS NULL OR to_address = '')
   AND (chain_name = 'ethereum' OR chain_name IS NULL);
   ```
   
   If this matches your total, all transactions have invalid addresses.

3. **Check clustering configuration:**
   ```bash
   cd AML
   python -c "
   import sys
   sys.path.insert(0, 'src')
   from aml_pipeline.config import load_config
   cfg = load_config()
   print(f'Min cluster size: {cfg.clustering_min_cluster_size}')
   print(f'Min heuristic support: {cfg.clustering_min_heuristic_support}')
   print(f'Min shared counterparties: {cfg.clustering_min_shared_counterparties}')
   "
   ```
   
   If thresholds are too high, valid clusters might be filtered out.

4. **Enable DEBUG logging:**
   Edit `run_analytics_only.py` line 19:
   ```python
   logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')
   ```
   
   Re-run and check for error messages or warnings.

### If clustering works but count is lower than expected:

This is normal! Clustering is selective:

- Only creates clusters of size ≥ 2 (configurable)
- Requires heuristic evidence (deposit reuse, behavioral similarity, etc.)
- Not every address will be clustered

A dataset of 500 transactions might produce:
- 300 unique addresses
- 15 clusters
- 30 clustered addresses (10%)
- 270 singleton addresses (not clustered)

This is expected behavior.

## Success Criteria

✅ **Fix is successful if:**

1. `run_analytics_only.py` shows "Clusters persisted: X" where X > 0
2. Database has ethereum clusters: `SELECT COUNT(*) FROM wallet_clusters WHERE chain_name = 'ethereum'` returns > 0
3. Placement, layering, and integration still work (alert counts similar to before)
4. No errors or warnings in output

✅ **Fix is working as designed if:**

1. You have no Ethereum transactions and clustering returns 0
2. You have Ethereum transactions but they're too sparse for clustering (< 2 addresses linked by heuristics)

The key metric is: **Does clustering now correctly count and load Ethereum transactions?**

Not: Does clustering always produce X clusters?

Cluster count depends on your data. Zero clusters is only a bug if you have valid Ethereum transactions that should be linkable.
