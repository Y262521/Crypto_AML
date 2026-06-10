"""Minimal clustering test with timeout"""
import sys
from pathlib import Path
import signal

sys.path.insert(0, str(Path(__file__).parent / "src"))

def timeout_handler(signum, frame):
    print("\nCLUSTERING TIMED OUT AFTER 30 SECONDS!")
    print("This suggests the clustering process is hanging")
    sys.exit(1)

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(30)  # 30 second timeout

try:
    from aml_pipeline.config import load_config
    from aml_pipeline.clustering.engine import ClusteringEngine
    
    cfg = load_config()
    print(f"Config loaded: min_cluster_size={cfg.clustering_min_cluster_size}, min_heuristic_support={cfg.clustering_min_heuristic_support}")
    
    engine = ClusteringEngine(cfg=cfg, chain_name="ethereum")
    print("Engine created")
    
    print("Starting clustering...")
    results = engine.run(
        source="auto",
        persist=False,  # Don't persist yet, just test clustering
        min_cluster_size=1  # Lower threshold to see if ANY clusters form
    )
    
    signal.alarm(0)  # Cancel timeout
    
    print(f"Clustering completed! Found {len(results)} clusters")
    if results:
        print(f"Sample: {results[0].cluster_id} with {len(results[0].addresses)} addresses")
    
except KeyboardInterrupt:
    print("\nInterrupted by user")
    sys.exit(1)
except Exception as e:
    signal.alarm(0)
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
