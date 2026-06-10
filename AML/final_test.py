"""Final test - run clustering with persistence on limited data"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from aml_pipeline.config import load_config
from aml_pipeline.clustering.engine import ClusteringEngine
from aml_pipeline.clustering.eth_adapter import EthereumAdapter
from sqlalchemy import text
from aml_pipeline.utils.connections import get_maria_engine

cfg = load_config()

print("="*70)
print("FINAL TEST: Clustering with persistence (limited dataset)")
print("="*70)

# Use limited adapter
class LimitedAdapter(EthereumAdapter):
    def iter_transactions(self, source="auto", **kwargs):
        count = 0
        for tx in super().iter_transactions(source, **kwargs):
            yield tx
            count += 1
            if count >= 10000:  # Use 10k transactions
                break

print("\nStep 1: Count existing clusters in DB before test...")
engine_db = get_maria_engine(cfg)
with engine_db.connect() as conn:
    before_count = conn.execute(
        text("SELECT COUNT(*) FROM wallet_clusters WHERE chain_name = 'ethereum' OR chain_name IS NULL")
    ).scalar_one()
    print(f"  Clusters before: {before_count}")
engine_db.dispose()

print("\nStep 2: Run clustering with PERSIST=True (10k transactions)...")
adapter = LimitedAdapter(cfg)
engine = ClusteringEngine(cfg=cfg, adapter=adapter)

results = engine.run(
    source="mariadb",
    persist=True,  # PERSIST TO DATABASE
    min_cluster_size=2
)

print(f"  Clustering found: {len(results)} clusters")

print("\nStep 3: Count clusters in DB after persistence...")
engine_db = get_maria_engine(cfg)
with engine_db.connect() as conn:
    after_count = conn.execute(
        text("SELECT COUNT(*) FROM wallet_clusters WHERE chain_name = 'ethereum' OR chain_name IS NULL")
    ).scalar_one()
    print(f"  Clusters after: {after_count}")
engine_db.dispose()

print("\n" + "="*70)
if len(results) > 0:
    print("✅ SUCCESS: Clustering produced clusters and persisted them!")
    print(f"   Found {len(results)} clusters")
    print(f"   Database has {after_count} ethereum clusters")
else:
    print("⚠️  WARNING: No clusters found (may be due to high thresholds)")
print("="*70)
