"""
Run analytics (clustering + placement + layering + integration) on existing data.

This script assumes ETL has already loaded transactions into MariaDB.
It runs all analytics stages on the existing data without re-extracting/transforming.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aml_pipeline.config import load_config
from aml_pipeline.etl.load.mariadb_loader import create_tables_if_not_exist

cfg = load_config()
print(f"Loaded config: {cfg.mysql_host} {cfg.mysql_db}")

# Ensure all tables exist
create_tables_if_not_exist(cfg)

# ────────────────────────────────────────────────────────────────────────────
# CLUSTERING
# ────────────────────────────────────────────────────────────────────────────
print("Running clustering for ethereum")
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
try:
    from aml_pipeline.clustering.engine import ClusteringEngine
    
    engine = ClusteringEngine(cfg=cfg, chain_name="ethereum")
    results = engine.run(
        source="auto",  # Try mariadb first, fallback to csv/mongo
        persist=True,
        min_cluster_size=cfg.clustering_min_cluster_size
    )
    print(f"Clusters persisted: {len(results) if results else 0}")
        
except Exception as e:
    print(f"Clustering error: {e}")
    import traceback
    traceback.print_exc()

# ────────────────────────────────────────────────────────────────────────────
# PLACEMENT
# ────────────────────────────────────────────────────────────────────────────
print("Running placement")
try:
    from aml_pipeline.analytics.placement import PlacementAnalysisEngine
    
    p_engine = PlacementAnalysisEngine(cfg=cfg, chain_name="ethereum")
    p_result = p_engine.run(source="mariadb", persist=True)
    print(f"Placement alerts: {len(p_result.placements)}")
except Exception as e:
    print(f"Placement error: {e}")
    p_result = None

# ────────────────────────────────────────────────────────────────────────────
# LAYERING
# ────────────────────────────────────────────────────────────────────────────
print("Running layering")
try:
    from aml_pipeline.analytics.layering import LayeringAnalysisEngine
    
    l_engine = LayeringAnalysisEngine(cfg=cfg, chain_name="ethereum")
    l_result = l_engine.run(source="mariadb", persist=True, placement_result=p_result)
    print(f"Layering alerts: {len(l_result.alerts)}")
except Exception as e:
    print(f"Layering error: {e}")
    l_result = None

# ────────────────────────────────────────────────────────────────────────────
# INTEGRATION
# ────────────────────────────────────────────────────────────────────────────
print("Running integration")
try:
    from aml_pipeline.analytics.integration import IntegrationAnalysisEngine
    
    i_engine = IntegrationAnalysisEngine(cfg=cfg, chain_name="ethereum")
    i_result = i_engine.run(source="mariadb", persist=True, layering_result=l_result)
    print(f"Integration alerts: {len(i_result.alerts)}")
except Exception as e:
    print(f"Integration error: {e}")

print("Done")
