"""
Fan-In / Fan-Out Heuristic
============================
Fan-out: one address distributes funds to many addresses.
Fan-in:  many addresses consolidate funds into one.

Both patterns are common in:
  - Exchange hot wallets (fan-out to users)
  - Mixer outputs (fan-out from tumbler)
  - Consolidation wallets (fan-in before mixing)

Addresses on the "many" side of a fan are linked together because
they likely belong to the same entity or campaign.
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

        # Fan-out: node with out-degree >= threshold
        for node in G.nodes():
            out_neighbours = list(set(G.successors(node)))
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
            in_neighbours = list(set(G.predecessors(node)))
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
