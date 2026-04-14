"""
Temporal Clustering Heuristic
================================
Addresses that transact within a very short time window in a coordinated
pattern are grouped together.

Logic:
  - Sort all transactions by timestamp.
  - Within a sliding window of W seconds, collect all active senders.
  - If >= 3 distinct senders are active in the same window AND they all
    send to the same receiver (or to each other), link them.
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

_MIN_COORDINATED_SENDERS = 3


class TemporalHeuristic(BaseHeuristic):
    name = "temporal_coordination"
    description = (
        "Addresses transacting within a short time window toward the same "
        "destination are flagged as coordinated."
    )

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.window = cfg.clustering_temporal_window_seconds

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # Collect all edges with timestamps
        edges_ts: list[tuple[float, str, str]] = []
        for u, v, data in G.edges(data=True):
            if not self.is_meaningful_edge(data):
                continue
            ts = data.get("timestamp", 0) or 0
            edges_ts.append((float(ts), u, v))

        if not edges_ts:
            return []

        edges_ts.sort(key=lambda x: x[0])

        links: List[ClusterEdge] = []
        seen: set = set()
        n = len(edges_ts)

        # Sliding window: group by destination within W seconds
        # receiver → list of (timestamp, sender)
        receiver_senders: dict[str, list] = defaultdict(list)
        left = 0

        for right in range(n):
            ts_r, u_r, v_r = edges_ts[right]
            receiver_senders[v_r].append((ts_r, u_r))

            # Evict entries outside the window
            while edges_ts[left][0] < ts_r - self.window:
                ts_l, u_l, v_l = edges_ts[left]
                lst = receiver_senders.get(v_l, [])
                if lst and lst[0] == (ts_l, u_l):
                    lst.pop(0)
                left += 1

            # Check if current receiver has >= N coordinated senders
            senders_in_window = {s for _, s in receiver_senders[v_r]}
            senders_in_window.discard(v_r)  # exclude self-loops
            if len(senders_in_window) >= _MIN_COORDINATED_SENDERS:
                sender_list = sorted(senders_in_window)
                for i in range(len(sender_list)):
                    for j in range(i + 1, len(sender_list)):
                        pair = (sender_list[i], sender_list[j])
                        if pair not in seen:
                            links.append(pair)
                            seen.add(pair)

        return links
