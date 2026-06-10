"""Test just the graph building step"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from aml_pipeline.config import load_config
from aml_pipeline.clustering.eth_adapter import EthereumAdapter
from aml_pipeline.clustering.graph_builder import build_graph

cfg = load_config()

print("Loading transactions...")
adapter = EthereumAdapter(cfg)
transactions = list(adapter.iter_transactions(source="auto"))
print(f"Loaded {len(transactions)} transactions")

print("\nBuilding graph...")
import time
start = time.time()
G = build_graph(transactions)
elapsed = time.time() - start

print(f"Graph built in {elapsed:.2f}s")
print(f"Nodes: {G.number_of_nodes()}")
print(f"Edges: {G.number_of_edges()}")

print("\nSample nodes:")
for i, node in enumerate(list(G.nodes())[:5]):
    print(f"  {node}")
    if i >= 4:
        break

print("\nGraph building completed successfully!")
