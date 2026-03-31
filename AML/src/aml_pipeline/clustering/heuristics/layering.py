"""
Layering / Rapid Hop Heuristic
================================
Layering is the second stage of money laundering. Funds are moved rapidly
through multiple intermediate addresses to obscure their origin.

Unlike peel chains (which forward most value), layering hops may split,
recombine, or change amounts at each step.

Detection approach — "rapid multi-hop":
  1. Build a time-ordered transaction sequence
  2. For each address, check if it received funds and then forwarded them
     within a short time window (RAPID_HOP_SECONDS)
  3. If an address acts as a rapid relay (receive → forward quickly),
     link it with its predecessor and successor
  4. Chains of rapid relays are flagged as layering

This complements the peel chain heuristic by catching cases where
amounts change significantly between hops.

Also detects "structuring" (smurfing):
  - Multiple transactions just below reporting thresholds
  - Same sender splitting a large amount into many small ones
    to avoid detection (e.g., 9.9 ETH × 5 instead of 49.5 ETH × 1)
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

# Maximum seconds between receiving and forwarding to be a "rapid relay"
_RAPID_HOP_SECONDS = 300   # 5 minutes
# Minimum number of hops to constitute a layering chain
_MIN_HOP_CHAIN = 3
# Structuring: transactions just below this ETH threshold
_STRUCTURING_THRESHOLD = 10.0
# Minimum number of sub-threshold transactions from same sender to flag
_STRUCTURING_MIN_COUNT = 3


class LayeringHeuristic(BaseHeuristic):
    name = "layering"
    description = (
        "Detects rapid multi-hop fund movements (layering) and structuring "
        "(smurfing): splitting large amounts into sub-threshold transactions "
        "to avoid detection. Both are AML stage-2 techniques."
    )

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        links: List[ClusterEdge] = []
        seen_pairs: set = set()

        # ── Part 1: Rapid relay detection ────────────────────────────────────
        # For each node, find earliest receive time and earliest send time
        receive_time: dict[str, float] = {}
        send_time: dict[str, float] = {}
        send_to: dict[str, str] = {}   # node → dominant next hop

        for u, v, data in G.edges(data=True):
            ts = float(data.get("timestamp", 0) or 0)
            val = data.get("value_eth", 0.0) or 0.0
            if val <= 0:
                continue
            # Track earliest receive time per node
            if v not in receive_time or ts < receive_time[v]:
                receive_time[v] = ts
            # Track earliest send time per node
            if u not in send_time or ts < send_time[u]:
                send_time[u] = ts
                send_to[u] = v

        # Identify rapid relays: received then forwarded within window
        rapid_relay_next: dict[str, str] = {}
        for node in G.nodes():
            rt = receive_time.get(node)
            st = send_time.get(node)
            if rt is None or st is None:
                continue
            if st >= rt and (st - rt) <= _RAPID_HOP_SECONDS:
                nxt = send_to.get(node)
                if nxt and nxt != node:
                    rapid_relay_next[node] = nxt

        # Walk chains of rapid relays
        visited: set = set()
        for start in rapid_relay_next:
            if start in visited:
                continue
            chain = [start]
            current = start
            while current in rapid_relay_next:
                nxt = rapid_relay_next[current]
                if nxt in chain:
                    break
                chain.append(nxt)
                current = nxt
            for n in chain:
                visited.add(n)
            if len(chain) < _MIN_HOP_CHAIN:
                continue
            for i in range(len(chain)):
                for j in range(i + 1, len(chain)):
                    pair = tuple(sorted([chain[i], chain[j]]))
                    if pair not in seen_pairs:
                        links.append(pair)  # type: ignore[arg-type]
                        seen_pairs.add(pair)

        # ── Part 2: Structuring (smurfing) detection ─────────────────────────
        # Find senders with many sub-threshold transactions
        sender_sub_threshold: dict[str, list] = defaultdict(list)
        for u, v, data in G.edges(data=True):
            val = data.get("value_eth", 0.0) or 0.0
            if 0 < val < _STRUCTURING_THRESHOLD:
                sender_sub_threshold[u].append(v)

        for sender, receivers in sender_sub_threshold.items():
            if len(receivers) < _STRUCTURING_MIN_COUNT:
                continue
            # Link all receivers of structured payments together
            receiver_list = sorted(set(receivers))
            for i in range(len(receiver_list)):
                for j in range(i + 1, len(receiver_list)):
                    pair = tuple(sorted([receiver_list[i], receiver_list[j]]))
                    if pair not in seen_pairs:
                        links.append(pair)  # type: ignore[arg-type]
                        seen_pairs.add(pair)

        return links
