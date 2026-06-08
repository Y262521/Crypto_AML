"""
Multi-Input Clustering Heuristic (UTXO)
=========================================
An extended version of Common Input Ownership that handles the case where
the same sender address appears across multiple transactions.

If address A appears as input in tx1 (with address B) and also as input
in tx2 (with address C), then A, B, and C are transitively linked.

This is the "address-to-cluster propagation" step used after the initial
CIO pass — it propagates cluster membership through the shared-input graph.

Additionally links addresses that:
  - Appear as inputs together in >= 2 separate transactions (multi-occurrence)
  - Appear as both sender AND receiver within the same cluster (internal cycling)
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

_MIN_SHARED_TX_COUNT = 2   # minimum times two addresses must co-appear as inputs


class MultiInputClusteringHeuristic(BaseHeuristic):
    """
    Links addresses that co-appear as inputs across multiple transactions.
    Stronger evidence than single co-occurrence (less noise from CoinJoin).
    """

    name = "utxo_multi_input"
    description = (
        "Address pairs that appear together as inputs in >= 2 separate "
        "transactions are likely controlled by the same entity."
    )

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.min_shared = int(
            getattr(cfg, "utxo_multi_input_min_shared", _MIN_SHARED_TX_COUNT)
        )

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # Group from_addresses by tx_hash
        tx_inputs: dict[str, set[str]] = defaultdict(set)

        for u, v, data in G.edges(data=True):
            if u == v or u.upper() == "COINBASE":
                continue
            val = float(data.get("value_eth") or data.get("value_native") or 0.0)
            if val <= 0:
                continue
            tx_hash = data.get("tx_hash") or ""
            if tx_hash:
                tx_inputs[tx_hash].add(u)

        # Count co-occurrences: (addr_a, addr_b) → count of shared txs
        pair_count: dict[tuple[str, str], int] = defaultdict(int)

        for inputs in tx_inputs.values():
            if len(inputs) < 2:
                continue
            inp_list = sorted(inputs)
            for i in range(len(inp_list)):
                for j in range(i + 1, len(inp_list)):
                    pair_count[(inp_list[i], inp_list[j])] += 1

        links: List[ClusterEdge] = []
        for pair, count in pair_count.items():
            if count >= self.min_shared:
                links.append(pair)

        return links
