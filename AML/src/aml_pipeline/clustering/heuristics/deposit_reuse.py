"""
Deposit address reuse heuristic.

Inspired by Ethereum deposit-address forwarding behavior: a temporary address
receives funds from multiple source wallets and forwards those funds to a
single downstream collector within a bounded time/value tolerance.
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge


class DepositAddressReuseHeuristic(BaseHeuristic):
    name = "deposit_address_reuse"
    description = (
        "Addresses using the same forwarding deposit address are grouped as "
        "likely belonging to one operator or exchange account."
    )

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.window = cfg.clustering_pass_through_window_seconds
        self.absolute_tolerance = cfg.clustering_forwarding_value_tolerance_eth
        self.max_pattern_size = cfg.clustering_max_pattern_size

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        incoming_by_node: dict[str, list[tuple[float, str, float]]] = defaultdict(list)
        outgoing_by_node: dict[str, list[tuple[float, str, float]]] = defaultdict(list)
        links: List[ClusterEdge] = []
        seen: set[ClusterEdge] = set()

        for source, target, data in G.edges(data=True):
            if not self.is_meaningful_edge(data):
                continue
            if source == target:
                continue
            record = (
                float(data.get("timestamp", 0.0) or 0.0),
                source,
                float(data.get("value_eth", 0.0) or 0.0),
            )
            incoming_by_node[target].append(record)
            outgoing_by_node[source].append((record[0], target, record[2]))

        for candidate, incoming in incoming_by_node.items():
            if candidate not in outgoing_by_node:
                continue

            unique_sources = {source for _, source, _ in incoming}
            unique_targets = {target for _, target, _ in outgoing_by_node[candidate]}
            if len(unique_sources) < 2 or len(unique_sources) > self.max_pattern_size:
                continue
            if len(unique_targets) != 1:
                continue

            outgoing = sorted(outgoing_by_node[candidate], key=lambda item: item[0])
            incoming_sorted = sorted(incoming, key=lambda item: item[0])
            matched_sources: set[str] = set()

            for incoming_ts, source, incoming_value in incoming_sorted:
                for outgoing_ts, _, outgoing_value in outgoing:
                    if outgoing_ts < incoming_ts:
                        continue
                    if outgoing_ts - incoming_ts > self.window:
                        break
                    if outgoing_value > incoming_value + self.absolute_tolerance:
                        continue
                    if not self.amounts_are_similar(
                        incoming_value,
                        outgoing_value,
                        absolute_tolerance=self.absolute_tolerance,
                    ) and outgoing_value < incoming_value * (1.0 - (self.cfg.clustering_amount_similarity_ratio * 2.0)):
                        continue
                    matched_sources.add(source)
                    break

            if len(matched_sources) < 2:
                continue

            matched_list = sorted(matched_sources)
            for left in range(len(matched_list)):
                for right in range(left + 1, len(matched_list)):
                    pair = (matched_list[left], matched_list[right])
                    if pair in seen:
                        continue
                    links.append(pair)
                    seen.add(pair)

        return links
