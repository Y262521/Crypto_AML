"""Base class every heuristic must extend."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple

import networkx as nx

from ...config import Config

# An edge in the union-find sense: (address_a, address_b)
ClusterEdge = Tuple[str, str]


class BaseHeuristic(ABC):
    """
    A heuristic analyses the transaction graph and returns pairs of addresses
    that should be merged into the same cluster.

    Subclasses implement `find_links` and declare `name` + `description`.
    """

    name: str = "base"
    description: str = ""

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def is_meaningful_edge(
        self,
        data: dict,
        *,
        allow_contract: bool = False,
        min_value_eth: float | None = None,
    ) -> bool:
        """Ignore zero-value approvals and dust unless the heuristic needs them."""
        if not allow_contract and data.get("is_contract_call"):
            return False
        threshold = (
            self.cfg.clustering_min_transfer_value_eth
            if min_value_eth is None
            else min_value_eth
        )
        value_eth = float(data.get("value_eth", 0.0) or 0.0)
        return value_eth >= threshold

    def amounts_are_similar(
        self,
        left: float,
        right: float,
        *,
        ratio: float | None = None,
        absolute_tolerance: float = 0.0,
    ) -> bool:
        """Compare value transfers using both relative and absolute tolerance."""
        if left < 0 or right < 0:
            return False
        allowed_ratio = (
            self.cfg.clustering_amount_similarity_ratio
            if ratio is None
            else ratio
        )
        baseline = max(left, right, 1e-9)
        delta = abs(left - right)
        return delta <= max(absolute_tolerance, baseline * allowed_ratio)

    @abstractmethod
    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        """
        Return a list of (addr_a, addr_b) pairs that should be in the same cluster.
        Both addresses must already be nodes in G.
        """
