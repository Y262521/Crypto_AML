"""Test complete clustering with small sample"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from aml_pipeline.config import load_config
from aml_pipeline.clustering.engine import ClusteringEngine

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')

cfg = load_config()

print("="*60)
print("Testing clustering with smaller dataset")
print("="*60)

# Modify adapter to load fewer transactions
from aml_pipeline.clustering.eth_adapter import EthereumAdapter

class LimitedEthAdapter(EthereumAdapter):
    def iter_transactions(self, source="auto", **kwargs):
        count = 0
        for tx in super().iter_transactions(source, **kwargs):
            yield tx
            count += 1
            if count >= 5000:  # Limit to first 5000 transactions
                break

adapter = LimitedEthAdapter(cfg)

engine = ClusteringEngine(cfg=cfg, adapter=adapter)

print("\nRunning clustering (LIMITED to 5000 transactions)...")
results = engine.run(
    source="mariadb",
    persist=False,  # Don't persist, just test
    min_cluster_size=2
)

print(f"\n{'='*60}")
print(f"Results: {len(results)} clusters")
print(f"{'='*60}")

if results:
    print(f"\nTop 5 clusters:")
    for i, cluster in enumerate(results[:5]):
        print(f"  {i+1}. {cluster.cluster_id}: {len(cluster.addresses)} addresses")
    print(f"\n✅ SUCCESS - Clustering completed!")
else:
    print("No clusters found - this might be OK if min_cluster_size is too high")
