"""
Fan-In / Fan-Out Heuristic
============================
Fan-out: one address distributes funds to many addresses.
Fan-in:  many addresses consolidate funds into one.

Addresses on the "many" side of a fan are linked together because they
often share a common controller, campaign, or operational purpose.
"""

from __future__ import annotations

from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge


class FanPatternHeuristic(BaseHeuristic):
    name = "fan_pattern"
    description = (
        "Addresses on the receiving end of a fan-out (or sending end of a "
        "fan-in) are grouped as likely related."
    )

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.threshold = cfg.clustering_fan_threshold

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        links: List[ClusterEdge] = []
        seen: set = set()
        meaningful_successors: dict[str, set[str]] = {}
        meaningful_predecessors: dict[str, set[str]] = {}

        for u, v, data in G.edges(data=True):
            if not self.is_meaningful_edge(data):
                continue
            meaningful_successors.setdefault(u, set()).add(v)
            meaningful_predecessors.setdefault(v, set()).add(u)

        # Fan-out: node with out-degree >= threshold
        for node in G.nodes():
            out_neighbours = list(meaningful_successors.get(node, set()))
            if len(out_neighbours) >= self.threshold:
                # Link all receivers together
                out_neighbours.sort()
                for i in range(len(out_neighbours)):
                    for j in range(i + 1, len(out_neighbours)):
                        pair = (out_neighbours[i], out_neighbours[j])
                        if pair not in seen:
                            links.append(pair)
                            seen.add(pair)

        # Fan-in: node with in-degree >= threshold
        for node in G.nodes():
            in_neighbours = list(meaningful_predecessors.get(node, set()))
            if len(in_neighbours) >= self.threshold:
                # Link all senders together
                in_neighbours.sort()
                for i in range(len(in_neighbours)):
                    for j in range(i + 1, len(in_neighbours)):
                        pair = (in_neighbours[i], in_neighbours[j])
                        if pair not in seen:
                            links.append(pair)
                            seen.add(pair)

        return links
