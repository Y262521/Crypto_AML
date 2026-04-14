"""
Coordinated cash-out heuristic.

Groups addresses that send near-identical amounts to the same collector address
within a short time window. This is a common pattern for exchange deposits,
airdrop collection, and multi-wallet cash-out behavior.
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge


class CoordinatedCashoutHeuristic(BaseHeuristic):
    name = "coordinated_cashout"
    description = (
        "Addresses cashing out similar amounts to the same collector in a short "
        "window are grouped as likely jointly controlled."
    )

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.window = cfg.clustering_cashout_window_seconds
        self.max_pattern_size = cfg.clustering_max_pattern_size

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        incoming_by_receiver: dict[str, list[tuple[float, str, float]]] = defaultdict(list)
        links: List[ClusterEdge] = []
        seen: set[ClusterEdge] = set()

        for sender, receiver, data in G.edges(data=True):
            if not self.is_meaningful_edge(data):
                continue
            if sender == receiver:
                continue
            incoming_by_receiver[receiver].append(
                (
                    float(data.get("timestamp", 0.0) or 0.0),
                    sender,
                    float(data.get("value_eth", 0.0) or 0.0),
                )
            )

        for entries in incoming_by_receiver.values():
            unique_senders = {sender for _, sender, _ in entries}
            if len(unique_senders) < 2 or len(unique_senders) > self.max_pattern_size:
                continue

            entries.sort(key=lambda item: item[0])
            for index, (ts_left, sender_left, value_left) in enumerate(entries):
                grouped = {sender_left}
                for ts_right, sender_right, value_right in entries[index + 1 :]:
                    if ts_right - ts_left > self.window:
                        break
                    if sender_left == sender_right:
                        continue
                    if not self.amounts_are_similar(value_left, value_right):
                        continue
                    grouped.add(sender_right)

                if len(grouped) < 2:
                    continue

                grouped_list = sorted(grouped)
                for left in range(len(grouped_list)):
                    for right in range(left + 1, len(grouped_list)):
                        pair = (grouped_list[left], grouped_list[right])
                        if pair in seen:
                            continue
                        links.append(pair)
                        seen.add(pair)

        return links
