"""Run ETH-only ETL + all engines. Use when ethereum was SKIP in run_all_chains.py."""
import sys
sys.path.insert(0, 'src')
from dotenv import load_dotenv
load_dotenv('C:/Users/yona/Desktop/Crypto_AML/crypto-aml-tracker/backend-py/.env')

from aml_pipeline.config import load_config
from aml_pipeline.etl.load.mariadb_loader import create_tables_if_not_exist
from aml_pipeline.utils.connections import get_maria_engine
from sqlalchemy import text

cfg = load_config()
create_tables_if_not_exist(cfg)

print("\n[ETHEREUM — EXTRACT + LOAD]")
try:
    from aml_pipeline.etl.extract.evm import EVMExtractor
    ext = EVMExtractor(cfg=cfg, chain="ethereum")
    fb, tb = ext.fetch_and_store_raw(batch=3)
    print(f"  ethereum: OK blocks {fb}->{tb}")

    from aml_pipeline.etl.transform.transformer import transform_raw_to_aml
    t = transform_raw_to_aml(start_block=fb, end_block=tb, cfg=cfg)
    from aml_pipeline.etl.load.mariadb_loader import load_to_mariadb
    load_to_mariadb(cfg=cfg, chain_name="ethereum")
    print(f"  Loaded {t['transactions_created']} ETH txs to MySQL")
except Exception as e:
    print(f"  ERROR: {e}")
    sys.exit(1)

print("\n[ETHEREUM — CLUSTERING]")
try:
    from aml_pipeline.clustering.engine import ClusteringEngine
    eng = ClusteringEngine(cfg=cfg, chain_name="ethereum")
    res = eng.run(persist=True, min_cluster_size=cfg.clustering_min_cluster_size)
    print(f"  ethereum clustering: OK  {len(res)} clusters")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n[ETHEREUM — PLACEMENT]")
try:
    from aml_pipeline.analytics.placement import PlacementAnalysisEngine
    eng = PlacementAnalysisEngine(cfg=cfg, chain_name="ethereum")
    res = eng.run(source="mariadb", persist=True)
    print(f"  ethereum placement: OK  {len(res.placements)} alerts")
    eth_placement = res
except Exception as e:
    print(f"  ERROR: {e}")
    eth_placement = None

print("\n[ETHEREUM — LAYERING]")
try:
    from aml_pipeline.analytics.layering import LayeringAnalysisEngine
    eng = LayeringAnalysisEngine(cfg=cfg, chain_name="ethereum")
    res = eng.run(source="mariadb", persist=True, placement_result=eth_placement)
    print(f"  ethereum layering: OK  {len(res.alerts)} alerts")
    eth_layering = res
except Exception as e:
    print(f"  ERROR: {e}")
    eth_layering = None

print("\n[ETHEREUM — INTEGRATION]")
try:
    from aml_pipeline.analytics.integration import IntegrationAnalysisEngine
    eng = IntegrationAnalysisEngine(cfg=cfg, chain_name="ethereum")
    res = eng.run(source="mariadb", persist=True, layering_result=eth_layering)
    print(f"  ethereum integration: OK  {len(res.alerts)} alerts")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n[FINAL DB COUNTS]")
engine = get_maria_engine(cfg)
with engine.connect() as conn:
    for tbl, col in [
        ("transactions","chain_name"),
        ("wallet_clusters","chain_name"),
        ("placement_detections","chain_name"),
        ("layering_alerts","chain_name"),
        ("integration_alerts","chain_name"),
    ]:
        rows = conn.execute(text(
            f"SELECT COALESCE({col},'(NULL)') as c, COUNT(*) as n FROM {tbl} GROUP BY {col} ORDER BY n DESC"
        )).all()
        total = sum(r[1] for r in rows)
        print(f"\n  {tbl}: {total:,}")
        for r in rows:
            print(f"    {str(r[0]).ljust(16)}: {r[1]:,}")
engine.dispose()
print("\nDone.")
