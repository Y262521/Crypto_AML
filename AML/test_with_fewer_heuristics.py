"""Test clustering with minimal heuristics to find the slow one"""
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent / "src"))

from aml_pipeline.config import load_config
from aml_pipeline.clustering.engine import ClusteringEngine
from aml_pipeline.clustering.heuristics import (
    DepositAddressReuseHeuristic,
    CoordinatedCashoutHeuristic,
    CommonFunderHeuristic,
)

cfg = load_config()

print("Testing with just 3 simple heuristics...")
engine = ClusteringEngine(
    cfg=cfg, 
    chain_name="ethereum",
    heuristics=[
        DepositAddressReuseHeuristic,
        CoordinatedCashoutHeuristic,
        CommonFunderHeuristic,
    ]
)

print("Loading transactions...")
transactions = list(engine.adapter.iter_transactions(source="mariadb"))
print(f"Loaded {len(transactions)} transactions")

print("Building graph...")
from aml_pipeline.clustering.graph_builder import build_graph
G = build_graph(transactions)
print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

print("\nRunning heuristics (3 only)...")
start = time.time()
pair_heuristics = engine._find_pair_heuristics(G)
elapsed = time.time() - start
print(f"Heuristics completed in {elapsed:.2f}s, found {len(pair_heuristics)} pairs")

print("\nBuilding clusters...")
start = time.time()
results = engine._build_results(G, pair_heuristics, min_cluster_size=1)
elapsed = time.time() - start
print(f"Clustering completed in {elapsed:.2f}s, found {len(results)} clusters")

print(f"\n✅ SUCCESS with minimal heuristics!")
