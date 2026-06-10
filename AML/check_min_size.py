import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from aml_pipeline.config import load_config

cfg = load_config()
print(f"clustering_min_cluster_size: {cfg.clustering_min_cluster_size}")
print(f"clustering_min_heuristic_support: {cfg.clustering_min_heuristic_support}")

# Check what gets passed to run()
min_cluster_size_arg = cfg.clustering_min_cluster_size
persist_min_size = max(2, int(cfg.clustering_min_cluster_size or 2))

print(f"\nmin_cluster_size passed to run(): {min_cluster_size_arg}")
print(f"persist_min_size in _persist(): {persist_min_size}")
