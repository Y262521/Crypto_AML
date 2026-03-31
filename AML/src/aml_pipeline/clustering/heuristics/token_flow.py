"""
Token Flow Heuristic
======================
Tracks ERC-20 token transfers (method IDs 0xa9059cbb / 0x23b872dd)
and groups addresses involved in repeated token flows between each other.

Two addresses are linked when they exchange tokens in both directions
(A→B and B→A) or when the same token flow path repeats >= N times.
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

_ERC20_METHODS = {"0xa9059cbb", "0x23b872dd"}
_MIN_REPEATED_FLOWS = 2   # minimum edge count to consider a flow "repeated"


class TokenFlowHeuristic(BaseHeuristic):
    name = "token_flow"
    description = (
        "Addresses with repeated ERC-20 token flows between each other "
        "are grouped as likely related entities."
    )

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # Count token-transfer edges between each ordered pair
        flow_count: dict[tuple, int] = defaultdict(int)
        for u, v, data in G.edges(data=True):
            if data.get("input_method_id", "")[:10] in _ERC20_METHODS:
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
