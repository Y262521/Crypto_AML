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

_MIN_HIGH_OVERLAP_SHARED = 2
_MIN_JACCARD_OVERLAP = 0.75


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
        for u, v, data in G.edges(data=True):
            if not self.is_meaningful_edge(data, allow_contract=True):
                continue
            if u == v:
                continue
            counterparties[u].add(v)
            counterparties[v].add(u)

        shared_counts: dict[ClusterEdge, int] = defaultdict(int)
        counterparty_index: dict[str, list[str]] = defaultdict(list)
        for address, peers in counterparties.items():
            for peer in peers:
                counterparty_index[peer].append(address)

        for addresses in counterparty_index.values():
            if len(addresses) < 2:
                continue
            addresses = sorted(set(addresses))
            for i in range(len(addresses)):
                for j in range(i + 1, len(addresses)):
                    pair = (addresses[i], addresses[j])
                    shared_counts[pair] += 1

        links: List[ClusterEdge] = []
        for pair, count in shared_counts.items():
            if count >= self.min_shared:
                links.append(pair)
                continue

            if count < _MIN_HIGH_OVERLAP_SHARED:
                continue

            left_peers = counterparties.get(pair[0], set())
            right_peers = counterparties.get(pair[1], set())
            union_size = len(left_peers | right_peers)
            if union_size == 0:
                continue

            overlap = float(count) / float(union_size)
            if overlap >= _MIN_JACCARD_OVERLAP:
                links.append(pair)

        return links
