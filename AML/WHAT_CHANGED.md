# What Changed - Visual Comparison

## File 1: eth_adapter.py (THE FIX)

### Location
```
AML/src/aml_pipeline/clustering/eth_adapter.py
Lines: 106-127
```

### Before (BROKEN)
```python
def _count_mariadb_transactions(self) -> int:
    try:
        engine = get_maria_engine(self.cfg)
        with engine.connect() as conn:
            return int(
                conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar_one()
                             # ^^^ BUG: No filter - counts ALL chains!
            )
    except Exception as exc:
        logger.warning("EthereumAdapter: MariaDB unavailable, falling back: %s", exc)
        return 0
    finally:
        if "engine" in locals():
            engine.dispose()
```

### After (FIXED)
```python
def _count_mariadb_transactions(self) -> int:
    try:
        engine = get_maria_engine(self.cfg)
        with engine.connect() as conn:
            # CRITICAL: Must filter by chain_name to match what _iter_from_mariadb() returns
            # Otherwise we count transactions from ALL chains but only iterate over THIS chain's transactions
            return int(
                conn.execute(
                    text("""
                        SELECT COUNT(*) FROM transactions
                        WHERE chain_name = :chain_name OR (chain_name IS NULL AND :chain_name = 'ethereum')
                        # ^^^ FIXED: Only counts Ethereum transactions
                    """),
                    {"chain_name": self.chain_name}
                ).scalar_one()
            )
    except Exception as exc:
        logger.warning("EthereumAdapter: MariaDB unavailable, falling back: %s", exc)
        return 0
    finally:
        if "engine" in locals():
            engine.dispose()
```

### SQL Query Comparison

**Before:**
```sql
SELECT COUNT(*) FROM transactions
```
→ Returns: Total count of ALL chains

**After:**
```sql
SELECT COUNT(*) FROM transactions
WHERE chain_name = :chain_name 
   OR (chain_name IS NULL AND :chain_name = 'ethereum')
```
→ Returns: Count of ONLY the specified chain (ethereum)

### Why This Matters

The iterator method `_iter_from_mariadb()` (line ~140) uses:
```sql
SELECT ... FROM transactions
WHERE chain_name = :chain_name OR (chain_name IS NULL AND :chain_name = 'ethereum')
```

**Before:** Count said "8000" but iterator returned 0 → Mismatch!
**After:** Count says "0" and iterator returns 0 → Consistent! ✓

---

## File 2: run_analytics_only.py (COSMETIC)

### Location
```
AML/scripts/run_analytics_only.py
Lines: 18-30
```

### Before
```python
print("Running clustering for ethereum")
import logging
logging.basicConfig(level=logging.INFO)
try:
    from aml_pipeline.clustering.engine import ClusteringEngine
    
    engine = ClusteringEngine(cfg=cfg, chain_name="ethereum")
    print(f"Engine created, about to run clustering...")
    results = engine.run(
        source="auto",
        persist=True,
        min_cluster_size=cfg.clustering_min_cluster_size
    )
    print(f"Clustering completed successfully")
    print(f"Clusters persisted: {len(results) if results else 0}")
```

### After
```python
print("Running clustering for ethereum")
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
#                                        ^^^ Added format for cleaner logs
try:
    from aml_pipeline.clustering.engine import ClusteringEngine
    
    engine = ClusteringEngine(cfg=cfg, chain_name="ethereum")
    results = engine.run(
        source="auto",
        persist=True,
        min_cluster_size=cfg.clustering_min_cluster_size
    )
    print(f"Clusters persisted: {len(results) if results else 0}")
    # ^^^ Removed redundant intermediate logging
```

### Impact
- Cleaner log output format
- Removed verbose intermediate messages
- **Non-functional change** - does not affect behavior

---

## Summary of Changes

| File | Lines | Type | Impact |
|------|-------|------|--------|
| `eth_adapter.py` | 106-127 | **BUG FIX** | Critical - fixes clustering |
| `run_analytics_only.py` | 18-30 | Cosmetic | Minor - improves logging |

**Total lines changed:** ~25 lines across 2 files
**Core fix:** 1 SQL query (7 lines)

---

## Diff View

### eth_adapter.py
```diff
  def _count_mariadb_transactions(self) -> int:
      try:
          engine = get_maria_engine(self.cfg)
          with engine.connect() as conn:
+             # CRITICAL: Must filter by chain_name to match what _iter_from_mariadb() returns
+             # Otherwise we count transactions from ALL chains but only iterate over THIS chain's transactions
              return int(
                  conn.execute(
-                     text("SELECT COUNT(*) FROM transactions")).scalar_one()
+                     text("""
+                         SELECT COUNT(*) FROM transactions
+                         WHERE chain_name = :chain_name OR (chain_name IS NULL AND :chain_name = 'ethereum')
+                     """),
+                     {"chain_name": self.chain_name}
+                 ).scalar_one()
              )
      except Exception as exc:
          logger.warning("EthereumAdapter: MariaDB unavailable, falling back: %s", exc)
          return 0
+     finally:
+         if "engine" in locals():
+             engine.dispose()
```

### run_analytics_only.py
```diff
  print("Running clustering for ethereum")
  import logging
- logging.basicConfig(level=logging.INFO)
+ logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
  try:
      from aml_pipeline.clustering.engine import ClusteringEngine
      
      engine = ClusteringEngine(cfg=cfg, chain_name="ethereum")
-     print(f"Engine created, about to run clustering...")
      results = engine.run(
          source="auto",
          persist=True,
          min_cluster_size=cfg.clustering_min_cluster_size
      )
-     print(f"Clustering completed successfully")
      print(f"Clusters persisted: {len(results) if results else 0}")
```

---

## Testing the Fix

### Before Running
```bash
# Check if fix is applied
grep -A 5 "_count_mariadb_transactions" AML/src/aml_pipeline/clustering/eth_adapter.py | grep "WHERE chain_name"
```

If output contains `WHERE chain_name`, fix is applied ✓

### After Running
```bash
cd AML
python scripts/run_analytics_only.py
```

**Look for:**
```
Running clustering for ethereum
INFO - EthereumAdapter: reading N transactions from MariaDB
                        ↑ Should show a count, not 0
Clusters persisted: X
                    ↑ Should be > 0 if you have ethereum data
```

---

**That's it! One SQL query fix in one file.**
