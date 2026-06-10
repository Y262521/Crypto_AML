"""
Test clustering flow step by step
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from aml_pipeline.config import load_config
from aml_pipeline.clustering.engine import ClusteringEngine

cfg = load_config()
print("=" * 60)
print("CLUSTERING FLOW TEST")
print("=" * 60)

print(f"\nConfig:")
print(f"  DB: {cfg.mysql_db}")
print(f"  Min cluster size: {cfg.clustering_min_cluster_size}")
print(f"  Min heuristic support: {cfg.clustering_min_heuristic_support}")

print("\n" + "=" * 60)
print("Creating engine for 'ethereum'...")
print("=" * 60)

engine = ClusteringEngine(cfg=cfg, chain_name="ethereum")
print(f"Engine chain_name: {engine.chain_name}")
print(f"Engine chain_id: {engine.chain_id}")

print("\n" + "=" * 60)
print("Loading transactions...")
print("=" * 60)

# Test transaction loading
transactions = list(engine.adapter.iter_transactions(source="auto"))
print(f"Transactions loaded: {len(transactions)}")

if transactions:
    print("\nFirst 3 transactions:")
    for i, tx in enumerate(transactions[:3]):
        print(f"  {i+1}. chain={tx.chain_name} from={tx.from_address[:12]}... to={tx.to_address[:12]}... value={tx.value_eth}")
    
    # Count by chain
    from collections import Counter
    chain_counts = Counter(tx.chain_name for tx in transactions)
    print(f"\nTransactions by chain:")
    for chain, count in chain_counts.items():
        print(f"  {chain}: {count}")
else:
    print("NO TRANSACTIONS LOADED!")
    sys.exit(1)

print("\n" + "=" * 60)
print("Running clustering WITHOUT persist...")
print("=" * 60)

results = engine.run(source="auto", persist=False, min_cluster_size=cfg.clustering_min_cluster_size)
print(f"Clusters found: {len(results)}")

if results:
    print(f"\nTop 5 clusters:")
    for i, cluster in enumerate(results[:5]):
        print(f"  {i+1}. {cluster.cluster_id}: {len(cluster.addresses)} addresses, heuristics: {cluster.heuristic_names}")
else:
    print("NO CLUSTERS FOUND!")

print("\n" + "=" * 60)
print("DIAGNOSIS")
print("=" * 60)

if len(transactions) == 0:
    print("PROBLEM: No transactions loaded from database")
elif chain_counts and len(chain_counts) > 1:
    print(f"PROBLEM: Multiple chains loaded ({list(chain_counts.keys())})")
    print("The EthereumAdapter should only load 'ethereum' transactions!")
elif len(results) == 0:
    print("PROBLEM: Transactions loaded but no clusters found")
    print("This could be due to:")
    print("  - min_cluster_size too high")
    print("  - min_heuristic_support too high")
    print("  - heuristics not finding any links")
else:
    print(f"SUCCESS: Found {len(results)} clusters")
    print("Now test persistence separately...")
