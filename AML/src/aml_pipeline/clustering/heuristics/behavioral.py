"""
Behavioral Similarity Heuristic
================================
Two addresses are linked when they share >= N common counterparties
(addresses they both sent to OR both received from).

This catches wallets controlled by the same entity that repeatedly
interact with the same set of exchanges, contracts, or peers.
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge


class BehavioralSimilarityHeuristic(BaseHeuristic):
    name = "behavioral_similarity"
    description = (
        "Addresses sharing >= N common counterparties are likely "
        "controlled by the same entity."
    )

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.min_shared = cfg.clustering_min_shared_counterparties

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # Build counterparty sets per address (union of out-neighbours + in-neighbours)
        counterparties: dict[str, set] = defaultdict(set)
        for u, v in G.edges():
            counterparties[u].add(v)
            counterparties[v].add(u)

        addresses = list(counterparties.keys())
        links: List[ClusterEdge] = []

        for i in range(len(addresses)):
            for j in range(i + 1, len(addresses)):
                a, b = addresses[i], addresses[j]
                shared = counterparties[a] & counterparties[b]
                # Exclude a and b themselves from the shared set
                shared.discard(a)
                shared.discard(b)
                if len(shared) >= self.min_shared:
                    links.append((a, b))

        return links
