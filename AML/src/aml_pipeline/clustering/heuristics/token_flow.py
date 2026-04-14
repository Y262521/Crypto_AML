"""
Repeated Flow Heuristic
========================
Groups addresses that repeatedly transfer funds between each other.

Two addresses are linked when they exchange value in both directions
(A→B and B→A) or when the same flow repeats >= N times.
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

import networkx as nx

from .base_heuristic import BaseHeuristic, ClusterEdge

_MIN_REPEATED_FLOWS = 2   # minimum edge count to consider a flow "repeated"


class TokenFlowHeuristic(BaseHeuristic):
    name = "repeated_flow"
    description = (
        "Addresses with repeated value transfers between each other "
        "are grouped as likely related entities."
    )

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # Count meaningful transfers between each ordered pair
        flow_count: dict[tuple, int] = defaultdict(int)
        for u, v, data in G.edges(data=True):
            if not self.is_meaningful_edge(data, allow_contract=True):
                continue
            flow_count[(u, v)] += 1

        links: List[ClusterEdge] = []
        seen: set = set()

        for (u, v), count in flow_count.items():
            pair = tuple(sorted([u, v]))
            if pair in seen:
                continue
            # Bidirectional flow (A→B and B→A) — strong signal
            if flow_count.get((v, u), 0) > 0:
                links.append(pair)  # type: ignore[arg-type]
                seen.add(pair)
            # Repeated unidirectional flow
            elif count >= _MIN_REPEATED_FLOWS:
                links.append(pair)  # type: ignore[arg-type]
                seen.add(pair)

        return links
