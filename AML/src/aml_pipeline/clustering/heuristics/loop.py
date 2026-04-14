"""
Loop / Circular Transaction Heuristic
========================================
Detects circular fund flows: A → B → C → ... → A

Circular flows often indicate a shared controller, automated routing,
or tightly-coupled wallet behavior. All addresses participating in a
detected cycle are linked together.
"""

from __future__ import annotations

from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge


class LoopDetectionHeuristic(BaseHeuristic):
    name = "loop_detection"
    description = (
        "Addresses forming circular transaction flows are grouped as "
        "likely coordinated or jointly controlled."
    )

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.max_depth = cfg.clustering_loop_max_depth

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # Work on a simple DiGraph (collapse parallel edges) for cycle detection
        simple = nx.DiGraph()
        for u, v, data in G.edges(data=True):
            if not self.is_meaningful_edge(data):
                continue
            simple.add_edge(u, v)

        links: List[ClusterEdge] = []
        seen_pairs: set = set()

        try:
            cycles = nx.simple_cycles(simple)
        except Exception:
            return links

        for cycle in cycles:
            if len(cycle) < 2 or len(cycle) > self.max_depth:
                continue
            # Link every pair of addresses in the cycle
            cycle_sorted = sorted(cycle)
            for i in range(len(cycle_sorted)):
                for j in range(i + 1, len(cycle_sorted)):
                    pair = (cycle_sorted[i], cycle_sorted[j])
                    if pair not in seen_pairs:
                        links.append(pair)
                        seen_pairs.add(pair)

        return links
