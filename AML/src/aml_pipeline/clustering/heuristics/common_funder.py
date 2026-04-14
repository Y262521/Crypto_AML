"""
Common funder heuristic.

Links recipient addresses that are funded by the same source and later converge
on the same outbound counterparty. This is a stronger variant of simple fan-out:
it requires both shared funding and shared operational cash-out behavior.
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge


class CommonFunderHeuristic(BaseHeuristic):
    name = "common_funder"
    description = (
        "Addresses funded by the same source and later converging on the same "
        "outbound counterparty are grouped as likely jointly controlled."
    )

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.max_pattern_size = cfg.clustering_max_pattern_size

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        funded_by_source: dict[str, set[str]] = defaultdict(set)
        outbound_counterparties: dict[str, set[str]] = defaultdict(set)
        links: List[ClusterEdge] = []
        seen: set[ClusterEdge] = set()

        for source, recipient, data in G.edges(data=True):
            if not self.is_meaningful_edge(data):
                continue
            if source == recipient:
                continue
            funded_by_source[source].add(recipient)

        for source, recipient, data in G.edges(data=True):
            if not self.is_meaningful_edge(data):
                continue
            if source == recipient:
                continue
            outbound_counterparties[source].add(recipient)

        for recipients in funded_by_source.values():
            recipients = {recipient for recipient in recipients if outbound_counterparties.get(recipient)}
            if len(recipients) < 2 or len(recipients) > self.max_pattern_size:
                continue

            recipients_list = sorted(recipients)
            for left in range(len(recipients_list)):
                addr_left = recipients_list[left]
                sinks_left = outbound_counterparties.get(addr_left, set())
                if not sinks_left:
                    continue
                for right in range(left + 1, len(recipients_list)):
                    addr_right = recipients_list[right]
                    sinks_right = outbound_counterparties.get(addr_right, set())
                    if not sinks_right:
                        continue
                    if not (sinks_left & sinks_right):
                        continue
                    pair = (addr_left, addr_right)
                    if pair in seen:
                        continue
                    links.append(pair)
                    seen.add(pair)

        return links
