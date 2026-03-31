"""
Peel Chain Heuristic
======================
A peel chain is a sequence of transactions where each hop:
  - Receives funds from the previous address
  - Sends most of the funds forward to a new address
  - Keeps a small "peel" (remainder) behind

Pattern:  A --[10 ETH]--> B --[9.8 ETH]--> C --[9.6 ETH]--> D ...

This is a classic layering technique used to:
  - Obscure the origin of funds
  - Break blockchain analysis tools that follow single large flows
  - Create the appearance of many unrelated transactions

Detection logic:
  1. For each node, find its dominant outgoing edge (largest value)
  2. If that edge carries >= FORWARD_RATIO of all incoming value,
     and the node has exactly one dominant receiver, it is a "relay" node
  3. Chain consecutive relay nodes together
  4. If the chain length >= MIN_CHAIN_LENGTH, link all members
"""

from __future__ import annotations

from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

# Minimum fraction of incoming value that must be forwarded to qualify as a relay
_FORWARD_RATIO = 0.85
# Minimum chain length to be considered a peel chain
_MIN_CHAIN_LENGTH = 3


class PeelChainHeuristic(BaseHeuristic):
    name = "peel_chain"
    description = (
        "Detects peel chains: sequences of addresses each forwarding "
        "most received funds to the next hop, keeping a small remainder. "
        "Classic layering technique to obscure fund origin."
    )

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # Build per-node value summaries
        in_value: dict[str, float] = {}
        out_value: dict[str, float] = {}
        out_edges: dict[str, list] = {}

        for u, v, data in G.edges(data=True):
            val = data.get("value_eth", 0.0) or 0.0
            out_value[u] = out_value.get(u, 0.0) + val
            in_value[v] = in_value.get(v, 0.0) + val
            out_edges.setdefault(u, []).append((v, val))

        # Identify relay nodes: forward >= FORWARD_RATIO of what they received
        relay_next: dict[str, str] = {}  # relay_node → next_node
        for node in G.nodes():
            iv = in_value.get(node, 0.0)
            if iv <= 0:
                continue
            edges = out_edges.get(node, [])
            if not edges:
                continue
            # Find the single dominant outgoing edge
            dominant = max(edges, key=lambda x: x[1])
            dominant_receiver, dominant_val = dominant
            # Check: dominant edge carries >= FORWARD_RATIO of incoming value
            if dominant_val / iv >= _FORWARD_RATIO:
                relay_next[node] = dominant_receiver

        # Walk chains: follow relay_next pointers
        visited: set = set()
        links: List[ClusterEdge] = []
        seen_pairs: set = set()

        for start in relay_next:
            if start in visited:
                continue
            # Walk the chain forward
            chain = [start]
            current = start
            while current in relay_next:
                nxt = relay_next[current]
                if nxt in chain:  # cycle — stop
                    break
                chain.append(nxt)
                current = nxt

            for node in chain:
                visited.add(node)

            if len(chain) < _MIN_CHAIN_LENGTH:
                continue

            # Link every pair in the chain
            for i in range(len(chain)):
                for j in range(i + 1, len(chain)):
                    pair = tuple(sorted([chain[i], chain[j]]))
                    if pair not in seen_pairs:
                        links.append(pair)  # type: ignore[arg-type]
                        seen_pairs.add(pair)

        return links
