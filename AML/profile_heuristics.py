"""Profile each heuristic individually to find the slow one"""
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent / "src"))

from aml_pipeline.config import load_config
from aml_pipeline.clustering.eth_adapter import EthereumAdapter
from aml_pipeline.clustering.graph_builder import build_graph
from aml_pipeline.clustering.heuristics import (
    BehavioralSimilarityHeuristic,
    CommonFunderHeuristic,
    CoordinatedCashoutHeuristic,
    ContractInteractionHeuristic,
    DepositAddressReuseHeuristic,
    FanPatternHeuristic,
    LoopDetectionHeuristic,
    TemporalHeuristic,
    TokenFlowHeuristic,
)

cfg = load_config()
adapter = EthereumAdapter(cfg)

print("Loading transactions...")
transactions = list(adapter.iter_transactions(source="mariadb"))
print(f"Loaded {len(transactions)} transactions")

print("\nBuilding graph...")
G = build_graph(transactions)
print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

heuristics = [
    DepositAddressReuseHeuristic,
    CoordinatedCashoutHeuristic,
    CommonFunderHeuristic,
    BehavioralSimilarityHeuristic,
    ContractInteractionHeuristic,
    TokenFlowHeuristic,
    TemporalHeuristic,
    FanPatternHeuristic,
    LoopDetectionHeuristic,
]

print("\nTesting each heuristic individually...")
print("="*60)

for HClass in heuristics:
    h = HClass(cfg)
    print(f"\nTesting: {h.name}")
    start = time.time()
    try:
        links = h.find_links(G)
        elapsed = time.time() - start
        print(f"  ✅ Completed in {elapsed:.2f}s, found {len(links)} links")
        if elapsed > 10:
            print(f"  ⚠️  SLOW HEURISTIC!")
    except Exception as e:
        elapsed = time.time() - start
        print(f"  ❌ Failed after {elapsed:.2f}s: {e}")
